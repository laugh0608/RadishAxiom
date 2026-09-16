#!/usr/bin/env python3
"""Package the fixed accepted-source snapshot and curated local inputs; no network or Docker."""
import argparse
import gzip
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVISION = 'aa13d7ce88a39177fa389adc9ddfe2068276fbb3'
STORE = 'artifacts/source-inputs/musl-verifier-2fb2e70-20260912'


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


retention = load('retain-musl-verifier-inputs.py')
require, identity = retention.require, retention.identity


def serialize(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def files():
    verification = load('collect-musl-verification-execution.py')
    for name, result in [('musl-verification-execution-2026-09-16.json', verification.collect()),
                         ('musl-verification-success-2026-09-16.json', verification.collect_success())]:
        require(serialize(result) == retention.read_regular(HERE / name), 'execution export drift')
    smoke = load('collect-musl-smoke-execution.py')
    require(serialize(smoke.collect()) == retention.read_regular(HERE / 'musl-verifier-smoke-execution-2026-09-12.json'),
            'smoke export drift')
    archive = subprocess.run(['git', 'archive', '--format=tar', REVISION], cwd=ROOT,
                             capture_output=True, check=True, timeout=30).stdout
    require(len(archive) <= 64 * 1024**2, 'repository snapshot too large')
    selected = {}

    def add(path, data, mode=0o600):
        require(not path.startswith('/') and all(p not in {'', '.', '..', '.git'} for p in path.split('/')),
                'unsafe backup member')
        require(path not in selected and len(data) <= 16 * 1024**2, 'duplicate or oversized member')
        selected[path] = (data, mode)

    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as source:
        for member in source:
            if member.isdir():
                continue
            require(member.isfile(), 'unexpected Git snapshot member type')
            add('RadishAxiom/' + member.name, source.extractfile(member).read(), member.mode & 0o777)

    def local(path):
        data = retention.read_regular(ROOT / path)
        add('RadishAxiom/' + path, data, (ROOT / path).stat().st_mode & 0o777)

    manifest = retention.read_regular(ROOT / STORE / 'manifest.json')
    require(manifest == retention.read_regular(HERE / 'musl-retention-manifest-2026-09-12.json'), 'manifest drift')
    rows = retention.manifest_rows(manifest)
    digests = {row['sha256'] for row in rows}
    require({p.name for p in (ROOT / STORE / 'objects').iterdir()} == digests, 'object set drift')
    for row in rows:
        require(identity(retention.read_regular(ROOT / STORE / 'objects' / row['sha256'])) ==
                {k: row[k] for k in ('bytes', 'sha256')}, 'retained object drift')
    local(STORE + '/manifest.json')
    for digest in sorted(digests):
        local(STORE + '/objects/' + digest)
    for folder, count in [('.tmp/musl-verification-20260916', 8),
                          ('.tmp/musl-verification-20260916-attempt-2', 66)]:
        local(folder + '/result.json')
        for number in range(1, count + 1):
            for suffix in ('json', 'stdout', 'stderr'):
                local(f'{folder}/{number:03d}.{suffix}')
        result = json.loads(retention.read_regular(ROOT / folder / 'result.json'))
        for case in result['cases']:
            local(folder + '/' + case['status_file'])
        for name in sorted({name for case in result['cases'] for name in case['expected_inputs']}):
            local(folder + '/inputs/' + name)
    for attempt, count in smoke.ATTEMPTS.items():
        folder = '.tmp/musl-smoke-dbab49c-20260912/' + attempt
        local(folder + '/result.json')
        for number in range(1, count + 1):
            for suffix in ('json', 'stdout', 'stderr'):
                local(f'{folder}/{number:03d}.{suffix}')
    rootfs = '.tmp/musl-preflight-80768b6-20260912/rootfs.tar'
    require(identity(retention.read_regular(ROOT / rootfs)) == {
        'bytes': 8407040, 'sha256': 'f1ac49bc29d33182a9c9a070b70509c739d857369876afbe307b9e9898d6b8b3'}, 'rootfs drift')
    local(rootfs)
    # The packaging method is supplemental to, not part of, the pinned Git snapshot.
    local(str(Path(__file__).resolve().relative_to(ROOT)))
    readme = HERE / 'musl-backup-restore-instructions.md'
    add('RESTORE.md', retention.read_regular(readme), 0o644)
    require(len(selected) <= 2048 and sum(len(v[0]) for v in selected.values()) <= 128 * 1024**2,
            'backup exceeds fixed scope')
    return selected


def package(output):
    selected = files()
    manifest = {'kind': 'private-musl-source-backup-v1', 'repository_revision': REVISION,
                'includes_git_history': False, 'off_device_backup_verified': False,
                'files': [{'path': name, 'mode': mode, **identity(data)}
                          for name, (data, mode) in sorted(selected.items())]}
    selected['MANIFEST.json'] = (serialize(manifest), 0o644)
    require(output.absolute() == output.resolve() and output.parent.is_dir(), 'unsafe output path')
    with output.open('xb') as target:
        with gzip.GzipFile(filename='', fileobj=target, mode='wb', compresslevel=6, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as tar:
                for name, (data, mode) in sorted(selected.items()):
                    member = tarfile.TarInfo(name)
                    member.size, member.mode = len(data), mode
                    member.uid = member.gid = member.mtime = 0
                    tar.addfile(member, io.BytesIO(data))
    # Reopen the completed archive; validate every member before offering it for transfer.
    with tarfile.open(output, 'r:gz') as tar:
        seen = set()
        for member in tar:
            require(member.isfile() and member.name in selected and member.name not in seen, 'backup member drift')
            data, mode = selected[member.name]
            require(member.mode == mode and member.size == len(data) and tar.extractfile(member).read() == data,
                    'backup readback differs')
            seen.add(member.name)
        require(seen == set(selected), 'incomplete backup')
    result = identity(retention.read_regular(output, 128 * 1024**2))
    with Path(str(output) + '.sha256').open('x') as checksum:
        checksum.write(result['sha256'] + '  ' + output.name + '\n')
    return {'archive': result, 'file_count': len(selected), 'content_bytes': sum(len(v[0]) for v in selected.values()),
            'repository_revision': REVISION, 'full_archive_readback': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='new .tar.gz path; never overwrite')
    args = parser.parse_args()
    print(json.dumps(package(args.output), indent=2, sort_keys=True))
