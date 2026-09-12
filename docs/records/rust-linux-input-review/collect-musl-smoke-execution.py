#!/usr/bin/env python3
"""Export this fixed diagnostic batch's original bounded logs and method identities; no Docker calls."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE.parents[2] / '.tmp/musl-smoke-dbab49c-20260912'
ATTEMPTS = {'import': 1, 'import-attempt-2': 1, 'import-attempt-3': 2,
            'import-attempt-4': 4, 'run': 3, 'run-attempt-2': 31}
METHODS = ['musl-smoke-method-initial-2026-09-12.py', 'musl-smoke-method-version-fix-2026-09-12.py',
           'musl-smoke-method-info-fix-2026-09-12.py', 'musl-smoke-method-map-fix-2026-09-12.py',
           'run-musl-verifier-smoke.py', 'check-musl-smoke.py', 'collect-musl-smoke-execution.py',
           'inspect-musl-verifier-rootfs.py', 'inspect-musl-verifier-content.py',
           'inspect-musl-trust-inputs.py', 'inspect-selected-inputs.py']


def identity(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def read(path):
    if path.resolve() != path.absolute() or not path.is_file():
        raise ValueError('non-regular or symlink input: ' + str(path))
    with path.open('rb') as stream:
        raw = stream.read(2 * 1024**2 + 1)
    if len(raw) > 2 * 1024**2:
        raise ValueError('input exceeds diagnostic bound')
    return raw


def collect():
    methods = {name: identity(read(HERE / name)) for name in METHODS}
    result = {'kind': 'diagnostic-musl-smoke-execution-record-v1', 'methods': methods, 'attempts': {},
              'source_acceptance': 'not-assessed', 'runtime_qualification': False}
    known_methods = list(methods.values())
    for name, count in ATTEMPTS.items():
        folder = CACHE / name
        raw = read(folder / 'result.json')
        observation = json.loads(raw)
        if observation['method'] not in known_methods:
            raise ValueError('original method source not retained: ' + name)
        commands = []
        if len(list(folder.glob('[0-9][0-9][0-9].json'))) != count:
            raise ValueError('unexpected command count: ' + name)
        for number in range(1, count + 1):
            stem = folder / f'{number:03d}'
            command_raw = read(stem.with_suffix('.json'))
            command = json.loads(command_raw)
            item = {'record': command, 'record_identity': identity(command_raw)}
            for channel in ('stdout', 'stderr'):
                content = read(stem.with_suffix('.' + channel))
                if identity(content) != command[channel]:
                    raise ValueError('original stream hash mismatch')
                item[channel] = content.decode('utf-8', errors='strict')
            commands.append(item)
        result['attempts'][name] = {'result': observation, 'result_identity': identity(raw), 'commands': commands}
    return result


if __name__ == '__main__':
    print(json.dumps(collect(), sort_keys=True, indent=2))
