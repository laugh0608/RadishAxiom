#!/usr/bin/env python3
"""Authorized C1 raw-byte acquisition; stop at first error, no automatic retry.

No archive contents are inspected or executed. The offline preparation entry
remains separate and unchanged; this consumer freezes its approved plan bytes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import signal
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cvc5_prep', ROOT / 'scripts/cvc5-build-preparation.py')
PREP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PREP)
APPROVED_PLAN_SHA256 = '165672c67dcaea6963f00dc13e2128a3563fc8a59b58e27326ae58e47f1749cc'
HEADER_NAMES = frozenset(('content-length', 'content-encoding', 'content-type',
                         'date', 'last-modified', 'etag', 'content-range', 'transfer-encoding'))
REQUEST_HEADERS = {'User-Agent': 'RadishAxiom-C1-byte-acquisition/0.1', 'Accept-Encoding': 'identity'}
BLOCK = 1024 * 1024
ORIGINAL_RECORDS = {
    'acquisition-plan.json': APPROVED_PLAN_SHA256,
    'fetch-helper.py': 'd7d3c548fe1ec24324c5cb20c0f58421dfaa3343b247b2044c0f73e24188f965',
    'events.jsonl': 'ad2bd7b496c117f0303947535b4a4245b634c6992f70f199e72e2e4d60509fc4',
    'result.json': 'eadebcfe3fbaed9d2b06f8159614fcffd1d1d6a4a12fa5abe5213f24eac225c8',
}
CONTINUATION_PLAN = ROOT / 'docs/records/solver-cvc5-c1-2026-10-22/continuation-2-plan.json'
CONTINUATION_SHA256 = 'fb4860b00bdcd2a399392ce7d5fb26ca9837d8fa483b6a3714810c837862874c'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + '\n').encode()


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def headers(value):
    result = {}
    for key in HEADER_NAMES:
        entries = value.get_all(key, [])
        require(len(entries) <= 1, 'duplicate-response-header:' + key)
        if entries:
            require(len(entries[0]) <= 4096, 'response-header-size')
            result[key] = entries[0]
    return result


def allowed_redirect(url):
    require(isinstance(url, str) and len(url) <= 4096, 'redirect-url-size')
    parts = urllib.parse.urlsplit(url)
    require(parts.scheme == 'https' and parts.netloc == 'snapshot.debian.org'
            and not parts.query and not parts.fragment
            and re.fullmatch(r'/file/[0-9a-f]{40}/(?:[A-Za-z0-9_+~.=-]|%2[Bb])+', parts.path),
            'redirect-outside-approved-content-address-path')
    # Snapshot percent-encodes literal '+' in package revisions. Permit only
    # this observed equivalent spelling; encoded slash/dot/% remain rejected.
    name = urllib.parse.unquote(parts.path.rsplit('/', 1)[1])
    require(name not in ('.', '..'), 'redirect-dot-segment')


class Redirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, observation, event):
        self.observation, self.event = observation, event

    def http_error_302(self, req, fp, code, msg, response_headers):
        # urllib's default redirect handler reads an unbounded redirect body.
        # Close it instead: the authorized payload is the final pinned object.
        try:
            require(not self.observation.get('range_request'), 'range-redirect-forbidden')
            locations = response_headers.get_all('location', [])
            require(len(locations) == 1 and len(locations[0]) <= 4096, 'redirect-location-count-or-size')
            target = urllib.parse.urljoin(req.full_url, locations[0])
            allowed_redirect(target)
            chain = self.observation['redirects']
            require(len(chain) < 5, 'redirect-count-limit')
            seen = {self.observation['requested_url']} | {hop['to_url'] for hop in chain}
            require(target not in seen, 'redirect-loop')
            hop = {'status': code, 'from_url': req.full_url, 'to_url': target}
            chain.append(hop)
            self.event({'event': 'redirect', **hop})
        except Exception:
            self.observation['rejected_redirect'] = {
                'status': code, 'from_url': req.full_url,
                'location': response_headers.get('location', '')[:4096]}
            raise
        finally:
            fp.close()
        return self.parent.open(urllib.request.Request(target, headers=REQUEST_HEADERS), timeout=req.timeout)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


class Journal:
    def __init__(self, path, limit):
        self.stream = path.open('xb')
        self.limit, self.bytes = limit, 0

    def append(self, value):
        raw = (json.dumps(dict(utc=now(), **value), ensure_ascii=True, separators=(',', ':')) + '\n').encode()
        require(self.bytes + len(raw) <= self.limit, 'journal-byte-budget')
        self.stream.write(raw)
        self.stream.flush()
        self.bytes += len(raw)

    def close(self):
        self.stream.close()


def timeout(signum, frame):
    raise TimeoutError('item-or-batch-deadline')


def interrupted(signum, frame):
    raise InterruptedError('acquisition-interrupted')


def error_info(error):
    # Never record arbitrary environment/proxy exception strings or credentials.
    result = {'type': type(error).__name__}
    if isinstance(error, urllib.error.HTTPError):
        result['http_status'] = error.code
        try:
            result['response_headers'] = headers(error.headers)
        except ValueError as header_error:
            result['response_header_error'] = str(header_error)
    elif isinstance(error, urllib.error.URLError):
        result['reason_type'] = type(error.reason).__name__
        result['errno'] = getattr(error.reason, 'errno', None)
    elif isinstance(error, (ValueError, TimeoutError, InterruptedError)):
        result['reason'] = str(error)[:512]
    elif isinstance(error, OSError):
        result['errno'] = error.errno
    return result


def fetch_one(row, directory, observation, budget, event, seconds):
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    opener = urllib.request.build_opener(Redirect(observation, event), urllib.request.HTTPSHandler(context=context))
    path = directory / row['relative_path']
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists() and not path.is_symlink(), 'input-already-exists')
    require(path.parent.resolve() == path.parent, 'input-parent-symlink')
    request = urllib.request.Request(row['url'], headers=REQUEST_HEADERS)
    with opener.open(request, timeout=seconds) as response:
        observation['http_status'] = response.status
        observation['final_url'] = response.geturl()
        observation['response_headers'] = headers(response.headers)
        require(response.status == 200, 'non-200-response')
        expected_url = observation['redirects'][-1]['to_url'] if observation['redirects'] else row['url']
        require(response.geturl() == expected_url, 'unobserved-final-url')
        length = observation['response_headers'].get('content-length')
        require(length is None or length.isdigit() and int(length) == row['declared_bytes'],
                'content-length-mismatch')
        require(observation['response_headers'].get('content-encoding', 'identity') == 'identity',
                'unexpected-content-encoding')
        with path.open('xb') as stream:
            hasher = hashlib.sha256()
            while True:
                # At most one overflow byte is read to detect a false length.
                capacity = min(BLOCK, row['declared_bytes'] - observation['bytes'] + 1,
                               budget['limit'] - budget['received'])
                if capacity == 0:
                    # At the total ceiling, a matching HTTP Content-Length is
                    # needed to establish completion without reading beyond it.
                    require(length is not None and observation['bytes'] == int(length),
                            'body-budget-before-established-eof')
                    break
                data = response.read(capacity)
                if not data:
                    break
                observation['bytes'] += len(data)
                budget['received'] += len(data)
                stream.write(data)
                hasher.update(data)
                observation['sha256'] = hasher.hexdigest()
                require(observation['bytes'] <= row['declared_bytes'], 'payload-size-overflow')
                require(budget['received'] <= budget['limit'], 'batch-body-budget')
            observation['sha256'] = hasher.hexdigest()
        require(observation['bytes'] == row['declared_bytes'], 'payload-size-mismatch')
        require(observation['sha256'] == row['declared_sha256'], 'payload-sha256-mismatch')


def fetch_rows(plan, directory, journal, result, start_index=1, first_url=None):
    policy = plan['transport_policy']
    deadline = time.monotonic() + policy['batch_deadline_seconds']
    retained_bytes = sum(row['declared_bytes'] for row in plan['entries'][:start_index - 1])
    budget = {'received': 0, 'limit': policy['response_body_byte_limit'] - retained_bytes}
    for index, original_row in enumerate(plan['entries'][start_index - 1:], start_index):
        row = dict(original_row)
        if index == start_index and first_url is not None:
            row['url'] = first_url
        observation = {'index': index, 'requested_url': row['url'], 'relative_path': row['relative_path'],
                       'planned_url': original_row['url'],
                       'started_utc': now(), 'redirects': [], 'bytes': 0, 'status': 'started'}
        result['observations'].append(observation)
        started = time.monotonic()
        try:
            seconds = min(policy['per_item_deadline_seconds'], deadline - started)
            require(seconds > 0, 'batch-deadline-before-next-request')
            journal.append({'event': 'request-start', **observation})
            signal.setitimer(signal.ITIMER_REAL, seconds)
            try:
                fetch_one(row, directory, observation, budget, journal.append, seconds)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            require(time.monotonic() <= deadline, 'batch-deadline-after-response')
            observation['status'] = 'obtained-byte-matched'
            observation['finished_utc'] = now()
            observation['elapsed_seconds'] = round(time.monotonic() - started, 6)
            journal.append({'event': 'request-finished', **observation})
            result['matched_files'] += 1
            result['matched_bytes'] += observation['bytes']
            if index == 1 or index % 10 == 0 or index == len(plan['entries']):
                print(json.dumps({'matched_files': result['matched_files'], 'total_files': len(plan['entries']),
                                  'matched_bytes': result['matched_bytes']}), flush=True)
        except (Exception, KeyboardInterrupt) as error:
            signal.setitimer(signal.ITIMER_REAL, 0)
            observation.update(status='failed', finished_utc=now(), error=error_info(error),
                               elapsed_seconds=round(time.monotonic() - started, 6))
            result['failure'] = {'index': index, 'relative_path': row['relative_path'], **observation['error']}
            result['response_body_bytes'] = budget['received']
            # Reserve space separately from the journal for this final result.
            if journal.bytes < journal.limit - 16384:
                journal.append({'event': 'stopped-at-first-error', **observation})
            print(json.dumps({'stopped': True, 'failure': result['failure'],
                              'matched_files': result['matched_files']}), flush=True)
            return
    result['response_body_bytes'] = budget['received']
    result['download_complete'] = True


def continuation_preflight(plan, directory):
    """Bind one explicit continuation to the preserved zero-body seventh failure."""
    PREP.canonical_directory(directory)
    originals = {}
    for name, expected in ORIGINAL_RECORDS.items():
        path = directory / name
        require(path.is_file() and not path.is_symlink(), 'original-record-not-regular:' + name)
        originals[name] = identity(path)
        require(originals[name]['sha256'] == expected, 'original-record-drift:' + name)
    prior = json.loads((directory / 'result.json').read_bytes())
    require(prior['matched_files'] == 6 and prior['matched_bytes'] == 239168
            and prior['failure']['index'] == 7 and len(prior['observations']) == 7,
            'original-failure-shape')
    failed, row = prior['observations'][-1], plan['entries'][6]
    require(failed['requested_url'] == row['url'] and failed['relative_path'] == row['relative_path']
            and failed['bytes'] == 0 and failed['status'] == 'failed', 'original-failure-binding')
    rejected = failed['rejected_redirect']
    require(rejected['status'] == 302 and rejected['from_url'] == row['url'], 'original-redirect-binding')
    target = urllib.parse.urljoin(row['url'], rejected['location'])
    allowed_redirect(target)
    require(urllib.parse.unquote(urllib.parse.urlsplit(target).path.rsplit('/', 1)[1])
            == Path(row['relative_path']).name, 'continuation-filename-binding')
    audit = PREP.audit_archives(plan, directory)
    require(audit['matched_files'] == 6
            and audit['missing_files'] == [r['relative_path'] for r in plan['entries'][6:]],
            'continuation-requires-exact-six-retained')
    return target, {'original_records': originals, 'retained_readback': audit,
                    'start_index': 7, 'remaining_files': 494, 'remaining_bytes': 691366296,
                    'first_requested_url': target}


def fetch(continue_from_7=False):
    raw = PREP.PLAN.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == APPROVED_PLAN_SHA256, 'approved-plan-sha256-drift')
    plan = PREP.verify_plan()
    require(plan['summary']['total_files'] == 500 and plan['summary']['total_bytes'] == 691605464,
            'approved-count-or-bytes-drift')
    directory = ROOT / plan['retention_directory']
    require(directory == ROOT / '.tmp/cvc5-c1-acquisition-2026-10-22', 'retention-target-drift')
    require(directory.parent.resolve() == directory.parent, 'retention-parent-noncanonical')
    continuation, first_url = None, None
    logs = directory
    if continue_from_7:
        first_url, continuation = continuation_preflight(plan, directory)
        logs = directory / 'continuation-1'
    require(not logs.exists() and not logs.is_symlink(), 'batch-exists-refuse-resume')
    free = shutil.disk_usage(directory.parent).free
    require(free >= plan['transport_policy']['minimum_free_bytes'], 'insufficient-free-space')
    logs.mkdir(mode=0o700)
    for name, data in (('acquisition-plan.json', raw), ('fetch-helper.py', Path(__file__).read_bytes())):
        with (logs / name).open('xb') as stream:
            stream.write(data)
    # The approved plan stays immutable and records its preparation-time state;
    # current authorization is recorded separately, never forged into C0 data.
    result = {'format': 'radishaxiom-private-cvc5-c1-acquisition', 'version': '0.1',
              'scope': 'authorized-raw-download-and-byte-check-only',
              'authorization': 'owner-confirmed-500-files-stop-first-error-no-unpack-install-build-or-payload-execution',
              'started_utc': now(), 'initial_free_bytes': free,
              'plan': identity(logs / 'acquisition-plan.json'),
              'fetch_method': identity(logs / 'fetch-helper.py'),
              'download_complete': False, 'readback_complete': False,
              'matched_files': 0, 'matched_bytes': 0, 'response_body_bytes': 0,
              'failure': None, 'observations': [], 'signature_verified': False,
              'input_acceptance': 'not-accepted', 'build_ready': False,
              'unpacked': False, 'installed': False, 'built': False, 'payload_executed': False}
    # Physical journal+result budgets total at most the authorized 8 MiB.
    if continuation is not None:
        result.update(authorization='owner-confirmed-remaining-494-from-7-preserve-six-and-original-failure',
                      continuation=continuation, matched_files=6, matched_bytes=239168)
    journal = Journal(logs / 'events.jsonl', 6 * 1024 * 1024)
    old_alarm = signal.signal(signal.SIGALRM, timeout)
    old_term = signal.signal(signal.SIGTERM, interrupted)
    try:
        fetch_rows(plan, directory, journal, result, 7 if continue_from_7 else 1, first_url)
        if result['download_complete']:
            audit = PREP.audit_archives(plan, directory)
            require(audit['archive_bytes_complete'], 'final-readback-incomplete')
            result['readback_complete'] = True
            result['readback'] = audit
    except (Exception, KeyboardInterrupt) as error:
        result['failure'] = {'stage': 'batch-or-final-readback', **error_info(error)}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_alarm)
        signal.signal(signal.SIGTERM, old_term)
        journal.close()
        result['finished_utc'] = now()
        result['journal'] = identity(logs / 'events.jsonl')
        data = encoded(result)
        require(len(data) <= 2 * 1024 * 1024, 'result-byte-budget')
        with (logs / 'result.json').open('xb') as stream:
            stream.write(data)
    print(json.dumps({key: result[key] for key in ('download_complete', 'readback_complete',
        'matched_files', 'matched_bytes', 'response_body_bytes', 'failure', 'build_ready')}), flush=True)
    return 0 if result['download_complete'] and result['readback_complete'] and result['failure'] is None else 1


class ContinuationDeadlines:
    """One monotonic batch clock; progress never extends the item or batch end."""
    def __init__(self, seconds):
        self.batch_end = time.monotonic() + seconds
        self.item_end = self.phase_end = None
        self.phase = None

    def __enter__(self):
        self.old_alarm = signal.signal(signal.SIGALRM, self.expired)
        self.old_term = signal.signal(signal.SIGTERM, interrupted)
        try:
            self.arm()
        except BaseException:
            self.__exit__()
            raise
        return self

    def __exit__(self, *args):
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self.old_alarm)
        signal.signal(signal.SIGTERM, self.old_term)

    def nearest(self):
        bounds = [(self.batch_end, 'batch-deadline')]
        if self.item_end is not None:
            bounds.append((self.item_end, 'item-deadline'))
        if self.phase_end is not None:
            bounds.append((self.phase_end, self.phase))
        return min(bounds, key=lambda pair: pair[0])

    def expired(self, signum, frame):
        raise TimeoutError(self.nearest()[1])

    def arm(self):
        end, reason = self.nearest()
        remaining = end - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(reason)
        signal.setitimer(signal.ITIMER_REAL, remaining)
        return remaining

    def start_item(self, seconds):
        self.item_end = time.monotonic() + seconds
        self.phase_end = self.phase = None
        self.arm()

    def start_headers(self):
        self.phase, self.phase_end = 'headers-deadline', time.monotonic() + 60
        return self.arm()

    def body_progress(self):
        # Check the old idle limit before refreshing it, including after read1.
        self.arm()
        self.phase, self.phase_end = 'body-no-progress', time.monotonic() + 60
        self.arm()

    def finish_item(self):
        self.arm()
        self.item_end = self.phase_end = self.phase = None
        self.arm()


def continuation2_bindings(proposal, plan):
    """Check the explicit split inventory even though the proposal is hash-pinned."""
    retained, requests = proposal['retained_complete_files'], proposal['requests_detail']
    require(len(plan['entries']) == 500, 'original-inventory-count')
    require([row['index'] for row in retained] == list(range(1, 41)), 'retained-index-binding')
    require([row['index'] for row in requests] == list(range(41, 501)), 'request-index-binding')
    base = ROOT / plan['retention_directory']
    require(ROOT / proposal['new_directory'] == base / 'continuation-2', 'new-directory-binding')
    for row, original in zip(retained, plan['entries'][:40]):
        require(row['path'] == str((base / original['relative_path']).relative_to(ROOT))
                and row['bytes'] == original['declared_bytes']
                and row['sha256'] == original['declared_sha256'], 'retained-input-binding')
    partial = proposal['retained_partial']
    require(partial['index'] == 41 and partial['bytes'] == 12582912
            and partial['path'] == str((base / plan['entries'][40]['relative_path']).relative_to(ROOT)),
            'partial-input-binding')
    for row, original in zip(requests, plan['entries'][40:]):
        offset = partial['bytes'] if row['index'] == 41 else 0
        require(row['planned_url'] == original['url']
                and row['complete_bytes'] == original['declared_bytes']
                and row['complete_sha256'] == original['declared_sha256']
                and row['output_path'] == proposal['new_directory'] + '/' + original['relative_path']
                and row['network_body_bytes'] == original['declared_bytes'] - offset
                and row['total_deadline_seconds'] == max(300, 120 + (row['network_body_bytes'] + 32767) // 32768),
                'request-input-binding')


def continuation2_retained(proposal, plan):
    base = ROOT / plan['retention_directory']
    for expected in proposal['prior_records']:
        path = ROOT / expected['path']
        require(path.resolve() == path and path.is_file() and not path.is_symlink(), 'prior-record-path')
        require(identity(path) == expected, 'prior-record-drift')
    # The old partial is checked as retained failure bytes, never as a complete
    # original package. The full manifest and its original digest stay intact.
    retained_plan = dict(plan, entries=[dict(row) for row in plan['entries']])
    retained_plan['entries'][40].update(declared_bytes=proposal['retained_partial']['bytes'],
                                      declared_sha256=proposal['retained_partial']['sha256'])
    audit = PREP.audit_archives(retained_plan, base)
    require(audit['matched_files'] == 41
            and audit['missing_files'] == [row['relative_path'] for row in plan['entries'][41:]],
            'retained-tree-drift')
    return {'complete_files': 40, 'complete_bytes': sum(row['declared_bytes'] for row in plan['entries'][:40]),
            'partial_bytes': proposal['retained_partial']['bytes'], 'old_records_unchanged': True}


def continuation2_preflight():
    require(hashlib.sha256(CONTINUATION_PLAN.read_bytes()).hexdigest() == CONTINUATION_SHA256,
            'continuation-plan-sha256-drift')
    require(hashlib.sha256(PREP.PLAN.read_bytes()).hexdigest() == APPROVED_PLAN_SHA256,
            'approved-plan-sha256-drift')
    proposal, plan = json.loads(CONTINUATION_PLAN.read_bytes()), PREP.verify_plan()
    continuation2_bindings(proposal, plan)
    retained = continuation2_retained(proposal, plan)
    directory = ROOT / proposal['new_directory']
    require(directory.parent.resolve() == directory.parent, 'new-directory-parent-symlink')
    require(not directory.exists() and not directory.is_symlink(), 'continuation-already-exists')
    free = shutil.disk_usage(directory.parent).free
    require(free >= proposal['transport_policy']['minimum_free_bytes'], 'insufficient-free-space')
    return proposal, plan, retained, free


def fetch_continuation_item(row, partial, observation, budget, event, deadlines):
    path = ROOT / row['output_path']
    path.parent.mkdir(parents=True, exist_ok=True)
    require(path.parent.resolve() == path.parent and not path.is_symlink(), 'output-parent-or-file-symlink')
    hasher = hashlib.sha256()
    with path.open('xb') as output:
        if partial is not None:
            source = ROOT / partial['path']
            require(source.resolve() == source and source.is_file() and not source.is_symlink(), 'prefix-path')
            with source.open('rb') as stream:
                while data := stream.read(min(65536, partial['bytes'] - observation['bytes'] + 1)):
                    deadlines.arm()
                    observation['bytes'] += len(data)
                    output.write(data)
                    hasher.update(data)
                    observation['sha256'] = hasher.hexdigest()
                    require(observation['bytes'] <= partial['bytes'], 'prefix-size-overflow')
            require(observation['bytes'] == partial['bytes'] and hasher.hexdigest() == partial['sha256'],
                    'prefix-byte-mismatch')
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        opener = urllib.request.build_opener(Redirect(observation, event),
                                            urllib.request.HTTPSHandler(context=context))
        request = urllib.request.Request(row['request_url'],
                                         headers=dict(REQUEST_HEADERS, **row['request_headers']))
        header_seconds = deadlines.start_headers()
        event({'event': 'request-start', 'index': row['index'], 'url': row['request_url'],
               'request_headers': row['request_headers']})
        with opener.open(request, timeout=header_seconds) as response:
            deadlines.arm()
            observation.update(http_status=response.status, final_url=response.geturl(),
                               response_headers=headers(response.headers))
            require(response.status == row['expected_status'], 'unexpected-response-status')
            final = observation['redirects'][-1]['to_url'] if observation['redirects'] else row['request_url']
            require(response.geturl() == final, 'unobserved-final-url')
            response_headers = observation['response_headers']
            length = response_headers.get('content-length')
            require(length is None or length.isdigit() and int(length) == row['network_body_bytes'],
                    'content-length-mismatch')
            require(response_headers.get('content-encoding', 'identity') == 'identity', 'unexpected-content-encoding')
            require(not (length is not None and 'transfer-encoding' in response_headers), 'conflicting-body-framing')
            if partial is not None:
                require(response_headers.get('content-range') == row['expected_content_range'], 'content-range-mismatch')
                require(length is not None, 'range-content-length-required')
                require('etag' not in response_headers or response_headers['etag'] == row['request_headers']['If-Range'],
                        'range-etag-mismatch')
            else:
                require('content-range' not in response_headers, 'unexpected-content-range')
            deadlines.body_progress()
            observation['body_started_utc'] = now()
            event({'event': 'body-start', 'index': row['index'], 'headers': response_headers})
            next_progress = time.monotonic() + 30
            while True:
                deadlines.arm()
                capacity = min(65536, row['network_body_bytes'] - observation['network_bytes'] + 1,
                               budget['limit'] - budget['received'])
                if capacity == 0:
                    require(length is not None and observation['network_bytes'] == int(length),
                            'body-budget-before-established-eof')
                    break
                data = response.read1(capacity)
                if not data:
                    deadlines.arm()
                    break
                # Account for bytes returned to the application before any
                # operation that can fail; final file integrity is checked too.
                observation['network_bytes'] += len(data)
                budget['received'] += len(data)
                output.write(data)
                observation['bytes'] += len(data)
                hasher.update(data)
                observation['sha256'] = hasher.hexdigest()
                deadlines.body_progress()
                require(observation['network_bytes'] <= row['network_body_bytes'], 'payload-size-overflow')
                require(budget['received'] <= budget['limit'], 'batch-body-budget')
                if time.monotonic() >= next_progress:
                    event({'event': 'body-progress', 'index': row['index'], 'network_bytes': observation['network_bytes'],
                           'output_bytes': observation['bytes']})
                    next_progress = time.monotonic() + 30
    require(observation['network_bytes'] == row['network_body_bytes']
            and observation['bytes'] == row['complete_bytes'], 'payload-size-mismatch')
    require(hasher.hexdigest() == row['complete_sha256'], 'payload-sha256-mismatch')


def continuation2_rows(proposal, journal, result, deadlines):
    budget = {'received': 0, 'limit': proposal['transport_policy']['new_response_body_byte_limit']}
    for row in proposal['requests_detail']:
        observation = {'index': row['index'], 'requested_url': row['request_url'], 'planned_url': row['planned_url'],
                       'output_path': row['output_path'], 'range_request': row['index'] == 41,
                       'started_utc': now(), 'redirects': [], 'bytes': 0, 'network_bytes': 0, 'status': 'started'}
        result['observations'].append(observation)
        started = time.monotonic()
        try:
            deadlines.start_item(row['total_deadline_seconds'])
            journal.append({'event': 'item-start', **observation})
            partial = proposal['retained_partial'] if row['index'] == 41 else None
            fetch_continuation_item(row, partial, observation, budget, journal.append, deadlines)
            deadlines.finish_item()
            observation.update(status='obtained-byte-matched', finished_utc=now(),
                               elapsed_seconds=round(time.monotonic() - started, 6))
            journal.append({'event': 'item-finished', **observation})
            result['matched_files'] += 1
            result['matched_bytes'] += observation['bytes']
            print(json.dumps({'matched_files': result['matched_files'], 'matched_bytes': result['matched_bytes']}), flush=True)
        except (Exception, KeyboardInterrupt) as error:
            # No subsequent request, even when the error was a timeout or a
            # server that ignored Range. Cancellation leaves retained bytes.
            signal.setitimer(signal.ITIMER_REAL, 0)
            observation.update(status='failed', finished_utc=now(), error=error_info(error),
                               elapsed_seconds=round(time.monotonic() - started, 6))
            if isinstance(error, urllib.error.HTTPError):
                error.close()
            result['failure'] = {'index': row['index'], **observation['error']}
            result['response_body_bytes'] = budget['received']
            if journal.bytes < journal.limit - 16384:
                journal.append({'event': 'stopped-at-first-error', **observation})
            return
    result['response_body_bytes'] = budget['received']
    result['download_complete'] = True


def continuation2_readback(proposal, plan):
    continuation2_bindings(proposal, plan)
    retained = continuation2_retained(proposal, plan)
    new_plan = dict(plan, entries=plan['entries'][40:])
    new_audit = PREP.audit_archives(new_plan, ROOT / proposal['new_directory'])
    require(new_audit['archive_bytes_complete'] and new_audit['matched_files'] == 460, 'new-inventory-incomplete')
    return {'matched_files': 500, 'matched_bytes': plan['summary']['total_bytes'],
            'retained': retained, 'new_inputs': new_audit,
            'inventory': [{'index': row['index'], 'path': row['path']} for row in proposal['retained_complete_files']]
                         + [{'index': row['index'], 'path': row['output_path']} for row in proposal['requests_detail']],
            'old_partial_is_complete_input': False, 'input_acceptance': 'not-accepted', 'build_ready': False}


def fetch_continuation2(check_only=False):
    started_utc, started = now(), time.monotonic()
    with ContinuationDeadlines(21600) as deadlines:
        proposal, plan, retained, free = continuation2_preflight()
        if check_only:
            print(json.dumps({'scope': 'offline-preflight-only', 'proposal_sha256': CONTINUATION_SHA256,
                              'retained': retained, 'new_requests': 0, 'new_directory_created': False,
                              'network_authorization': 'pending-owner-confirmation', 'build_ready': False}))
            return 0
        directory = ROOT / proposal['new_directory']
        directory.mkdir(mode=0o700)
        for name, data in (('acquisition-plan.json', PREP.PLAN.read_bytes()),
                           ('continuation-plan.json', CONTINUATION_PLAN.read_bytes()),
                           ('fetch-helper.py', Path(__file__).read_bytes())):
            with (directory / name).open('xb') as stream:
                stream.write(data)
        result = {'format': 'radishaxiom-private-cvc5-c1-range-continuation', 'version': '0.1',
                  'scope': 'raw-download-and-byte-check-only',
                  'authorization': 'owner-confirmed-range-tail-and-459-full-files-stop-first-error',
                  'started_utc': started_utc, 'initial_free_bytes': free, 'retained_preflight': retained,
                  'batch_deadline_seconds': 21600,
                  'proposal': identity(directory / 'continuation-plan.json'),
                  'fetch_method': identity(directory / 'fetch-helper.py'),
                  'download_complete': False, 'readback_complete': False, 'failure': None,
                  'matched_files': 40, 'matched_bytes': 42872372, 'response_body_bytes': 0, 'observations': [],
                  'signature_verified': False, 'input_acceptance': 'not-accepted', 'build_ready': False,
                  'unpacked': False, 'installed': False, 'built': False, 'payload_executed': False}
        journal = Journal(directory / 'events.jsonl', 6 * 1024 * 1024)
        try:
            continuation2_rows(proposal, journal, result, deadlines)
            if result['download_complete']:
                deadlines.arm()
                result['readback'] = continuation2_readback(proposal, plan)
                deadlines.arm()
                result['readback_complete'] = True
        except (Exception, KeyboardInterrupt) as error:
            detail = {'stage': 'batch-or-final-readback', **error_info(error)}
            if result['failure'] is None:
                result['failure'] = detail
            else:
                result['secondary_error'] = detail
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            journal.close()
            result['finished_utc'] = now()
            result['elapsed_seconds'] = round(time.monotonic() - started, 6)
            result['journal'] = identity(directory / 'events.jsonl')
            data = encoded(result)
            require(len(data) <= 2 * 1024 * 1024, 'result-byte-budget')
            with (directory / 'result.json').open('xb') as stream:
                stream.write(data)
        print(json.dumps({key: result[key] for key in ('download_complete', 'readback_complete',
            'matched_files', 'matched_bytes', 'response_body_bytes', 'failure', 'build_ready')}), flush=True)
        return 0 if result['readback_complete'] and result['failure'] is None else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirmed-plan-sha256', required=True)
    continuation = parser.add_mutually_exclusive_group()
    continuation.add_argument('--continue-from-7', action='store_true',
                              help='Explicitly authorized one-time continuation; preserves original records and six inputs')
    continuation.add_argument('--check-continuation-from-41', action='store_true',
                              help='Read-only local preflight; no requests or new output directory')
    continuation.add_argument('--continue-from-41', action='store_true',
                              help='Owner-confirmed tail Range and remaining 459 files; no fallback or retries')
    parser.add_argument('--confirmed-continuation-sha256')
    args = parser.parse_args()
    require(args.confirmed_plan_sha256 == APPROVED_PLAN_SHA256, 'explicit-approved-plan-hash-required')
    if args.continue_from_41:
        require(args.confirmed_continuation_sha256 == CONTINUATION_SHA256, 'explicit-continuation-hash-required')
        raise SystemExit(fetch_continuation2())
    if args.check_continuation_from_41:
        raise SystemExit(fetch_continuation2(check_only=True))
    raise SystemExit(fetch(args.continue_from_7))
