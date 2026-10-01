#!/usr/bin/env python3
"""Export the first fixed verification attempt, checking original methods and logs; no Docker calls."""
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
            'collector_methods': {path.name: identity(read(path)) for path in
                                  [Path(__file__), HERE / 'collect-musl-smoke-execution.py']}}


if __name__ == '__main__':
    print(json.dumps(collect(), sort_keys=True, indent=2))
