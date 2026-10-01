#!/usr/bin/env python3
"""Export and replay the fixed MPFR run from local logs; never calls Docker or GnuPG."""
import base64
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CACHE = ROOT / '.tmp/mpfr-verification-20260925'
RESULT_SHA = '601bd0d92811382c378eb6e3c8f51c05c93d90aa0636ce79b69332b161b2d129'
spec = importlib.util.spec_from_file_location('mpfr_run', HERE / 'run-mpfr-verification.py')
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
read, identity, require = run.inputs.retention.read_regular, run.identity, run.require


def encoded(raw):
    try:
        return {'encoding': 'utf-8', 'data': raw.decode('utf-8', errors='strict')}
    except UnicodeDecodeError:
        return {'encoding': 'base64', 'data': base64.b64encode(raw).decode('ascii')}


def command_logs():
    paths = sorted(CACHE.glob('[0-9][0-9][0-9].json'))
    require([p.name for p in paths] == [f'{i:03d}.json' for i in range(1, 46)], 'command log set drift')
    exported, responses = [], []
    for path in paths:
        raw = read(path)
        record = json.loads(raw)
        item, streams = {'record': record, 'record_identity': identity(raw)}, {}
        for channel in ('stdout', 'stderr'):
            data = read(path.with_suffix('.' + channel), 1024**2)
            require(identity(data) == record[channel] and len(data) <= record['bytes_limit'], 'command stream drift')
            streams[channel] = data
            item[channel] = encoded(data)
        exported.append(item)
        responses.append({**record, **streams})
    return exported, responses


class Replay:
    """Consume only retained responses for exact requested commands and capture limits."""
    def __init__(self, responses):
        self.responses, self.sequence = responses, 0

    def call(self, args, *, seconds=10, limit=262144):
        require(self.sequence < len(self.responses), 'replay exhausted')
        row = self.responses[self.sequence]
        prefix = [run.smoke.DOCKER, '--host', 'unix://' + run.smoke.SOCKET,
                  '--config', str(CACHE / 'docker-config')]
        require(row['argv'] == prefix + args and row['seconds_limit'] == seconds and row['bytes_limit'] == limit,
                'command or capture limit binding drift')
        self.sequence += 1
        return row


def collect():
    raw = read(CACHE / 'result.json')
    require(identity(raw)['sha256'] == RESULT_SHA, 'fixed result changed')
    result = json.loads(raw)
    require(result['passed'] is True and result['run_id'] == 'f8c585f059a34940a4b926bab812c807', 'wrong run')
    require(run.methods() == result['methods'], 'execution method drift')
    prepared, files = run.inputs.prepare()
    require(prepared == result['prepared_inputs'], 'source/key store drift')
    folder = CACHE / 'inputs'
    final_inputs = run.inputs.snapshot(folder)
    expected = dict(prepared['inputs'])
    for name, data in files.items():
        require(read(folder / name, run.inputs.INPUT_LIMIT) == data, 'staged input differs from retained source')
    exported, responses = command_logs()
    engine = Replay(responses)
    run.smoke.preflight(engine)
    run.smoke.validate_image(run.smoke.inspect(engine, 'image', run.IMAGE, run.smoke.IMAGE_FIELDS), run.IMAGE)
    steps = run.commands()
    require([c['step'] for c in result['cases']] == [name for name, _ in steps], 'case order drift')
    statuses, assessments = {}, {}
    for case, (step, command) in zip(result['cases'], steps):
        name, run_id, cid = case['name'], result['run_id'], case['container_id']
        require(name == 'rax-mpfr-verify-' + run_id + '-' + step and case['command'] == command and
                case['passed'] is True and case['status_file'] == step + '.status' and
                case['expected_inputs'] == case['inputs'] == expected, 'case binding drift')
        status_path = CACHE / case['status_file']
        created = engine.call(run.base.create_args(name, run_id, command, folder, status_path))
        require(run.smoke.checked(created) == (cid + '\n').encode(), 'created container ID mismatch')
        before = run.smoke.inspect(engine, 'container', cid, run.smoke.CONTAINER_FIELDS)
        run.base.validate_container(before, name, run_id, command, folder, status_path)
        require(before['Id'] == cid and before['State.Status'] == 'created' and before['State.Running'] is False,
                'container already started')
        require(case['start_command_number'] == engine.sequence + 1, 'start command number drift')
        invocation = engine.call(['container', 'start', '--attach', cid], seconds=30, limit=1024**2)
        require(all(invocation[k] == case['invocation'][k] for k in ('returncode', 'failure', 'seconds')),
                'invocation result drift')
        after = run.smoke.inspect(engine, 'container', cid, run.smoke.CONTAINER_FIELDS)
        run.base.validate_container(after, name, run_id, command, folder, status_path)
        run.base.exited(after, invocation['returncode'])
        require({k: v for k, v in after.items() if k.startswith('State.')} == case['final_state'], 'final state drift')
        cleanup = run.smoke.cleanup(engine, cid, run.IMAGE, name, run_id)
        require(cleanup == case['cleanup'] and cleanup['removed'] is True and
                case['status_after_confirmed_cleanup'] is True, 'cleanup mismatch')
        status = read(status_path, 1024**2)
        require(identity(status) == case['status'] and all(identity(invocation[k]) == case[k]
                for k in ('stdout', 'stderr')), 'case stream mismatch')
        invocation = {**invocation, 'status': status}
        if step == 'filter':
            require(run.smoke.ok(invocation), 'filter failed')
            run.base.auxiliary_status(status, run.base.IMPORT_ALLOWED)
            run.profile.filtered_material(files['mpfr.raw.gpg'], invocation['stdout'])
            require(read(folder / 'mpfr.self.gpg') == invocation['stdout'], 'derived key mismatch')
            expected['mpfr.self.gpg'] = identity(invocation['stdout'])
            assessed = {'result': 'all-original-self-material-retained', 'source_acceptance': 'not-assessed'}
        else:
            assessed = run.assess(step, invocation, case, folder, files)
        require(assessed == case['assessment'], 'offline assessment disagrees with run')
        statuses[step], assessments[step] = status.decode('utf-8'), assessed
    require(engine.sequence == 45 and final_inputs == expected, 'unconsumed log or final input drift')
    return {'kind': 'diagnostic-mpfr-verification-execution-record-v1', 'result': result,
            'result_identity': identity(raw), 'commands': exported, 'status_text': statuses,
            'offline_assessment_replay': assessments, 'source_bytes_rechecked': True,
            'source_acceptance': 'not-assessed', 'runtime_qualification': False,
            'collector_methods': {Path(__file__).name: identity(read(Path(__file__)))}}


if __name__ == '__main__':
    print(json.dumps(collect(), sort_keys=True, indent=2))
