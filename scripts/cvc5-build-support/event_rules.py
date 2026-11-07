"""Pure checks on declared build events, with no execution or acceptance API.

The caller must validate the frozen recipe using the C2 entry first. These
rules detect inconsistent declarations; they cannot authenticate a monitor,
enforce an OS limit, approve a review, or establish complete input observation.
"""
import copy
import hashlib
import json
import re


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def natural(value):
    require(type(value) is int and 0 <= value < 2**64, 'event-unsigned-integer')
    return value


def digest(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'event-sha256')
    return value


def binding(step):
    return hashlib.sha256(json.dumps(step, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class DeclaredBuildTrace:
    """One fixed dependency schedule; first failure is sticky, time never renews."""

    def __init__(self, recipe, recipe_sha256, start_ns):
        self.recipe_sha256 = digest(recipe_sha256)
        self.steps = copy.deepcopy(recipe['dependency_steps'])
        self.resources = copy.deepcopy(recipe['policy']['resources'])
        self.limits = copy.deepcopy(recipe['evidence']['log_limits'])
        require(0 < len(self.steps) <= 1000 and len({s['id'] for s in self.steps}) == len(self.steps),
                'event-schedule')
        require(all(s['operation'] in ('command', 'review-gate', 'select-command',
                                      'write-selected-transformation', 'apply-recorded-transformation')
                    for s in self.steps), 'event-operation')
        for key in ('memory_bytes', 'swap_bytes', 'writable_bytes', 'deadline_seconds',
                    'termination_reserve_seconds', 'finalization_reserve_bytes'):
            natural(self.resources[key])
        for value in self.limits.values():
            natural(value)
        require(self.resources['deadline_seconds'] > self.resources['termination_reserve_seconds']
                and self.resources['writable_bytes'] > self.resources['finalization_reserve_bytes'],
                'event-reserve')
        self.last_ns = natural(start_ns)
        self.stop_ns = natural(start_ns + (self.resources['deadline_seconds']
                              - self.resources['termination_reserve_seconds']) * 10**9)
        self.position, self.event_count, self.total_log_bytes = 0, 0, 0
        self.active, self.failure = None, None
        self.completed, self.reviews = [], []
        self.peaks = {key: 0 for key in ('memory_peak_bytes', 'swap_peak_bytes', 'oom_kill',
                                        'pids_denied', 'events_bytes', 'inventory_bytes')}
        self.sample_seen = False

    def feed(self, event):
        if self.failure is not None:
            raise ValueError(self.failure)
        try:
            self._feed(event)
        except (ValueError, KeyError, TypeError) as exc:
            self.failure = str(exc)
            raise ValueError(self.failure) from exc

    def _feed(self, event):
        require(type(event) is dict and set(event) >= {'kind', 'at_ns'}, 'event-object')
        now = natural(event['at_ns'])
        require(now >= self.last_ns, 'event-clock-rollback')
        require(now < self.stop_ns, 'event-work-deadline-reserve')
        self.last_ns = now
        self.event_count += 1
        require(self.event_count <= 100000, 'event-count-budget')
        fields = {
            'start': {'step_id', 'step_sha256'},
            'review': {'step_id', 'evidence_sha256'},
            'log': {'stream', 'data'},
            'close-log': {'stream'},
            'sample': {'memory_peak_bytes', 'swap_peak_bytes', 'writable_bytes', 'oom_kill',
                       'pids_denied', 'events_bytes', 'inventory_bytes'},
            'finish': {'exit_code', 'capture_sha256'},
            'cancel': {'reason'},
            'observer-loss': {'reason'},
            'input-failure': {'reason'},
        }
        kind = event['kind']
        require(isinstance(kind, str) and kind in fields, 'event-kind')
        require(set(event) == {'kind', 'at_ns'} | fields[kind], 'event-fields')
        if kind in ('cancel', 'observer-loss', 'input-failure'):
            require(isinstance(event['reason'], str) and 0 < len(event['reason']) <= 1024, 'event-reason')
            raise ValueError(kind + ':' + event['reason'])
        if kind == 'sample':
            self.sample(event)
            return
        if kind in ('start', 'review'):
            require(self.active is None and self.position < len(self.steps), 'event-step-state')
            step = self.steps[self.position]
            require(event['step_id'] == step['id'], 'event-step-order')
            if kind == 'review':
                require(step['operation'] == 'review-gate', 'event-not-review-gate')
                self.reviews.append({'step_id': step['id'], 'external_evidence_sha256': digest(event['evidence_sha256']),
                                     'scope': 'unverified-review-declaration'})
                self.position += 1
                return
            require(step['operation'] != 'review-gate', 'event-gate-cannot-execute')
            choices = [x['step'] for x in step['choices']] if step['operation'] == 'select-command' else [step]
            candidates = [x for x in choices if binding(x) == digest(event['step_sha256'])]
            require(len(candidates) == 1, 'event-step-binding')
            selected = candidates[0]
            streams = ['stdout', 'stderr'] if selected['operation'] == 'command' else []
            if selected['operation'] == 'command' and '--trace-format=json-v1' in selected['argv']:
                streams.append('cmake_trace')
            self.active = {'step_id': step['id'], 'selected_sha256': event['step_sha256'],
                           'streams': {s: {'bytes': 0, 'hash': hashlib.sha256(), 'closed': False} for s in streams}}
            self.sample_seen = False
            return
        require(self.active is not None, 'event-no-active-step')
        if kind in ('log', 'close-log'):
            stream = event['stream']
            require(isinstance(stream, str) and stream in self.active['streams'], 'event-stream')
            state = self.active['streams'][stream]
            require(not state['closed'], 'event-stream-closed')
            if kind == 'close-log':
                state['closed'] = True
                return
            raw = event['data']
            require(type(raw) is bytes and 0 < len(raw) <= 1024**2, 'event-log-chunk-budget')
            require(state['bytes'] + len(raw) <= self.limits[stream + '_per_step_bytes'],
                    'event-stream-budget')
            require(self.total_log_bytes + len(raw) <= self.limits['all_logs_bytes'], 'event-total-log-budget')
            state['hash'].update(raw)
            state['bytes'] += len(raw)
            self.total_log_bytes += len(raw)
            self.sample_seen = False
            return
        require(kind == 'finish', 'event-kind-state')
        require(type(event['exit_code']) is int and event['exit_code'] == 0,
                'event-step-exit:' + str(event['exit_code']))
        require(self.sample_seen, 'event-missing-final-resource-sample')
        require(all(s['closed'] for s in self.active['streams'].values()), 'event-incomplete-log')
        self.completed.append({'step_id': self.active['step_id'], 'selected_sha256': self.active['selected_sha256'],
                               'declared_capture_sha256': digest(event['capture_sha256']),
                               'streams': {k: {'bytes': v['bytes'], 'sha256': v['hash'].hexdigest()}
                                           for k, v in self.active['streams'].items()}})
        self.position += 1
        self.active = None

    def sample(self, event):
        for key in self.peaks:
            value = natural(event[key])
            require(value >= self.peaks[key], 'event-counter-rollback:' + key)
            self.peaks[key] = value
        used = natural(event['writable_bytes'])
        require(event['memory_peak_bytes'] <= self.resources['memory_bytes'], 'event-memory-limit')
        require(event['swap_peak_bytes'] <= self.resources['swap_bytes'], 'event-swap-limit')
        require(event['oom_kill'] == 0 and event['pids_denied'] == 0, 'event-cgroup-failure')
        require(used <= self.resources['writable_bytes'] - self.resources['finalization_reserve_bytes'],
                'event-disk-reserve')
        require(event['events_bytes'] <= self.limits['events_jsonl_bytes']
                and event['inventory_bytes'] <= self.limits['inventory_bytes'], 'event-evidence-budget')
        require(used >= self.total_log_bytes + event['events_bytes'] + event['inventory_bytes'],
                'event-storage-accounting')
        self.sample_seen = True

    def result(self):
        return {'scope': 'offline-event-consistency-only', 'recipe_sha256': self.recipe_sha256,
                'sequence_complete': self.failure is None and self.active is None and self.position == len(self.steps),
                'failure': self.failure, 'termination_required': self.failure is not None,
                'retention_required': True, 'automatic_cleanup': False,
                'execution_ready': False, 'build_ready': False,
                'completed': copy.deepcopy(self.completed), 'reviews': copy.deepcopy(self.reviews),
                'partial': None if self.active is None else {
                    'step_id': self.active['step_id'],
                    'streams': {k: {'bytes': v['bytes'], 'sha256': v['hash'].hexdigest(), 'closed': v['closed']}
                                for k, v in self.active['streams'].items()}},
                'log_bytes': self.total_log_bytes, 'events_checked': self.event_count}
