#!/usr/bin/env python3
"""Export either fixed verification attempt and replay the successful observations; no Docker calls."""
import argparse
import base64
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CACHE = ROOT / '.tmp/musl-verification-20260916'
spec = importlib.util.spec_from_file_location('smoke_records', HERE / 'collect-musl-smoke-execution.py')
records = importlib.util.module_from_spec(spec)
spec.loader.exec_module(records)
read, identity = records.read, records.identity


def collect():
    raw = read(CACHE / 'result.json')
    observation = json.loads(raw)
    if observation['run_id'] != '323cfa18cd764502865dddb7e8cc7b73' or observation['passed'] is not False:
        raise ValueError('unexpected first attempt')
    methods = {}
    recorded = {**observation['methods'], **observation['prepared_inputs']['methods']}
    for name, expected in recorded.items():
        path = (ROOT / 'scripts' / name) if name == 'inspect-debian-source-chain.py' else HERE / name
        if name == 'run-musl-verification.py':
            path = HERE / 'musl-verification-method-initial-2026-09-16.py'
        if identity(read(path)) != expected:
            raise ValueError('original execution method missing or changed: ' + name)
        methods[name] = str(path.relative_to(ROOT))
    command_paths = sorted(CACHE.glob('[0-9][0-9][0-9].json'))
    if [path.name for path in command_paths] != [f'{n:03d}.json' for n in range(1, 9)]:
        raise ValueError('first-attempt command set changed')
    commands = []
    for path in command_paths:
        command_raw = read(path)
        command = json.loads(command_raw)
        item = {'record': command, 'record_identity': identity(command_raw)}
        for channel in ('stdout', 'stderr'):
            data = read(path.with_suffix('.' + channel))
            if identity(data) != command[channel]:
                raise ValueError('original command stream changed')
            item[channel] = data.decode('utf-8', errors='strict')
        commands.append(item)
    case, = observation['cases']
    if {path.name for path in (CACHE / 'inputs').iterdir()} != set(case['expected_inputs']):
        raise ValueError('first-attempt input set changed')
    for name, expected in case['expected_inputs'].items():
        if identity(read(CACHE / 'inputs' / name)) != expected:
            raise ValueError('first-attempt input changed: ' + name)
    status = read(CACHE / case['status_file'])
    if identity(status) != case['status']:
        raise ValueError('original status changed')
    return {'kind': 'diagnostic-musl-verification-execution-record-v1',
            'source_acceptance': 'not-assessed', 'runtime_qualification': False,
            'result': observation, 'result_identity': identity(raw), 'commands': commands,
            'status_text': status.decode('utf-8', errors='strict'), 'original_method_paths': methods,
            'collector_methods': {
                'collect-musl-verification-execution.py': identity(read(HERE / 'musl-verification-collector-initial-2026-09-16.py')),
                'collect-musl-smoke-execution.py': identity(read(HERE / 'collect-musl-smoke-execution.py'))}}


def collect_success():
    directory = ROOT / '.tmp/musl-verification-20260916-attempt-2'
    raw = read(directory / 'result.json')
    observation = json.loads(raw)
    if observation['run_id'] != '07728cfa67cc44adb284f7b0613815b6' or observation['passed'] is not True:
        raise ValueError('unexpected second attempt')
    for name, expected in {**observation['methods'], **observation['prepared_inputs']['methods']}.items():
        path = ROOT / 'scripts' / name if name == 'inspect-debian-source-chain.py' else HERE / name
        if identity(read(path)) != expected:
            raise ValueError('successful execution method drift: ' + name)
    entry_spec = importlib.util.spec_from_file_location('verification_entry', HERE / 'run-musl-verification.py')
    entry = importlib.util.module_from_spec(entry_spec)
    entry_spec.loader.exec_module(entry)
    prepared, files = entry.inputs.prepare(entry.STORE)
    entry.require(prepared == observation['prepared_inputs'], 'retained source chain changed')
    command_paths = sorted(directory.glob('[0-9][0-9][0-9].json'))
    entry.require([path.name for path in command_paths] == [f'{n:03d}.json' for n in range(1, 67)],
                  'successful command set drift')
    commands, streams = [], []
    for path in command_paths:
        command_raw = read(path)
        command = json.loads(command_raw)
        item = {'record': command, 'record_identity': identity(command_raw)}
        channels = {}
        for channel in ('stdout', 'stderr'):
            data = read(path.with_suffix('.' + channel))
            entry.require(identity(data) == command[channel] and len(data) <= command['bytes_limit'], 'log stream drift')
            channels[channel] = data
            # Key export stdout is binary; retain exact bytes without lossy text decoding.
            try:
                item[channel] = {'encoding': 'utf-8', 'data': data.decode('utf-8', errors='strict')}
            except UnicodeDecodeError:
                item[channel] = {'encoding': 'base64', 'data': base64.b64encode(data).decode('ascii')}
        commands.append(item)
        streams.append(channels)
    folder = directory / 'inputs'
    final_inputs = entry.snapshot(folder)
    expected_steps = entry.commands()
    entry.require([c['step'] for c in observation['cases']] == [step for step, _ in expected_steps], 'case order drift')
    originals = {role: entry.key_material.decoded_key(files[role + '.asc']) for role in ('archive', 'release')}
    statuses, replayed = {}, {}
    for case, (step, command) in zip(observation['cases'], expected_steps):
        entry.require(case['command'] == command and case['passed'] is True and case['cleanup']['removed'] is True,
                      'case command or cleanup drift')
        entry.require(case['inputs'] == case['expected_inputs'] and
                      all(final_inputs.get(name) == expected for name, expected in case['inputs'].items()), 'case input drift')
        number = case['start_command_number']
        record = commands[number - 1]['record']
        entry.require(record['argv'][5:] == ['container', 'start', '--attach', case['container_id']] and
                      record['returncode'] == case['invocation']['returncode'] and record['failure'] is None and
                      record['seconds_limit'] == 30 and record['bytes_limit'] == 1048576, 'invocation binding drift')
        entry.exited(case['final_state'], record['returncode'])
        status = read(directory / case['status_file'])
        entry.require(identity(status) == case['status'] and len(status) <= 1048576, 'status drift')
        statuses[step] = status.decode('utf-8', errors='strict')
        result = {**streams[number - 1], 'status': status, 'returncode': record['returncode'], 'failure': record['failure']}
        entry.require(identity(result['stdout']) == case['stdout'] and identity(result['stderr']) == case['stderr'],
                      'case stream binding drift')
        if step.endswith('-filter'):
            role = step.removesuffix('-filter')
            entry.auxiliary_status(status, entry.IMPORT_ALLOWED)
            entry.require(record['returncode'] == 0, 'filter failed')
            entry.keys.filtered_material(originals[role], result['stdout'], entry.key_material.KEYS[role]['primary'])
            entry.require(read(folder / (role + '.self.gpg')) == result['stdout'], 'derived self key drift')
            assessed = {'result': 'self-material-retained', 'raw_key_unchanged': True}
        else:
            assessed = entry.assess(step, result, case, folder, originals, files, prepared)
        entry.require(assessed == case['assessment'], 'offline assessment disagrees with execution')
        replayed[step] = assessed
    return {'kind': 'diagnostic-musl-verification-success-record-v1', 'result': observation,
            'result_identity': identity(raw), 'commands': commands, 'status_text': statuses,
            'offline_assessment_replay': replayed, 'source_bytes_rechecked': True,
            'source_acceptance': 'not-assessed', 'runtime_qualification': False,
            'collector_methods': {path.name: identity(read(path)) for path in
                                  [Path(__file__), HERE / 'collect-musl-smoke-execution.py']}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=int, choices=[1, 2], default=1)
    args = parser.parse_args()
    print(json.dumps(collect() if args.attempt == 1 else collect_success(), sort_keys=True, indent=2))
