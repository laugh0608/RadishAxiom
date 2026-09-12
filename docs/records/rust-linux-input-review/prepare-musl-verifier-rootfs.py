#!/usr/bin/env python3
"""Plan a fixed diagnostic rootfs; --assemble writes a tar only after separate authorization."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


content = load('content', HERE / 'inspect-musl-verifier-content.py')
retention = load('retention', HERE / 'retain-musl-verifier-inputs.py')
identity, require = content.identity, content.require
PREFIX = 'docs/records/rust-linux-input-review/'
CACHE = '.tmp/musl-verifier-d04b225-20260912/'
MANIFEST_SHA = '3937d4570faa72ec359dbedf8fdc9c62aa5f26942cc08ee29d1a809e03a54ae9'
CONFIG = {
    'etc/passwd': 'verifier:x:1000:1000:Verifier:/work:/nonexistent\n',
    'etc/group': 'verifier:x:1000:\n',
    'etc/nsswitch.conf': 'passwd: files\ngroup: files\nhosts: files\n',
    'work/full/common.conf': '', 'work/self/common.conf': '',
}


def validate_rows(rows, files):
    index = {}
    for row in rows:
        path = content.canonical(row['path'])
        require(path not in index and row['type'] in {'file', 'directory', 'symlink'}, 'duplicate or unsupported entry')
        require(type(row['mode']) is int and 0 <= row['mode'] <= 0o777 and
                row['uid'] in {0, 1000} and row['gid'] in {0, 1000}, 'unsupported mode or owner')
        if row['type'] == 'file':
            require(path in files and identity(files[path]) == {k: row[k] for k in ('bytes', 'sha256')},
                    'rootfs file identity mismatch')
        if row['type'] == 'symlink':
            require(content.link_destination(path, row['target']) == row['destination'], 'link destination drift')
        index[path] = row
    for path, row in index.items():
        for parent in Path(path).parents:
            require(str(parent) in index and index[str(parent)]['type'] == 'directory', 'missing/non-directory parent')
        if row['type'] == 'symlink':
            require(content.resolve(index, path)['status'] == 'found', 'unresolved link')
    require(set(files) == {p for p, row in index.items() if row['type'] == 'file'}, 'unlisted file bytes')


def prepare(store):
    manifest_raw = retention.read_regular(store / 'manifest.json', 1024**2)
    require(identity(manifest_raw)['sha256'] == MANIFEST_SHA, 'retained manifest drift')
    manifest = {row['path']: row for row in retention.manifest_rows(manifest_raw)}
    inputs = {}

    def read(path):
        row = manifest[path]
        data = retention.read_regular(store / 'objects' / row['sha256'])
        require(identity(data) == {k: row[k] for k in ('bytes', 'sha256')}, 'retained input corruption')
        inputs[path] = identity(data)
        return data

    previous = json.loads(read(PREFIX + 'musl-verifier-layout-summary-2026-09-12.json'))
    licenses = json.loads(read(PREFIX + 'musl-verifier-licenses-2026-09-12.json'))
    rows = previous['layout']['entries'] + licenses['supplemental_layout_entries']
    require(len(rows) == 70 and len({r['path'] for r in rows}) == 70, 'static layout drift')
    selected = {row['path'] for row in rows if row['type'] == 'file'}
    packages = json.loads(read(PREFIX + 'musl-verifier-packages-2026-09-12.json'))['packages']
    files = {}
    for name in [p['package'] for p in packages] + ['base-files']:
        attempt = 2 if name in {'gcc-14-base', 'base-files'} else 1
        raw = read(CACHE + name.replace('.', '_') + f'-attempt-{attempt}.deb')
        _, payload = content.read_tar(content.reader.ar_members(raw)['data.tar.xz'], 64 * 1024**2)
        for path, data in payload.items():
            if path in selected:
                require(path not in files, 'selected payload collision')
                files[path] = data
    rows = [dict(row) for row in rows]
    for path in ['etc', 'etc/gnupg', 'work', 'work/full', 'work/self', 'tmp', 'dev', 'proc', 'sys']:
        private = path.startswith('work')
        rows.append({'path': path, 'type': 'directory', 'mode': 0o700 if private else 0o755,
                     'uid': 1000 if private else 0, 'gid': 1000 if private else 0,
                     'origin': 'generated-config', 'packages': []})
    for path, text in CONFIG.items():
        private = path.startswith('work/')
        files[path] = text.encode()
        rows.append({'path': path, 'type': 'file', 'mode': 0o600 if private else 0o644,
                     'uid': 1000 if private else 0, 'gid': 1000 if private else 0,
                     'origin': 'generated-config', 'packages': [], 'text': text, **identity(files[path])})
    rows.sort(key=lambda row: row['path'])
    validate_rows(rows, files)
    return {'kind': 'diagnostic-verifier-rootfs-plan-v1', 'source_acceptance': 'not-assessed',
            'retention_manifest': identity(manifest_raw), 'inputs': inputs, 'entries': rows,
            'entry_count': len(rows), 'file_bytes': sum(map(len, files.values())),
            'rootfs_assembled': False, 'programs_executed': False,
            'scope': 'read-only version/path/loader smoke; writable key import profile is separate',
            'methods': {str(path.relative_to(HERE.parents[2])): identity(path.read_bytes()) for path in
                        (Path(__file__), HERE / 'retain-musl-verifier-inputs.py',
                         HERE / 'inspect-musl-verifier-content.py', HERE / 'inspect-musl-trust-inputs.py',
                         HERE / 'inspect-selected-inputs.py', HERE.parents[2] / 'scripts/inspect-debian-source-chain.py')}}, files


def assemble(rows, files, output):
    validate_rows(rows, files)
    require(output.absolute() == output.resolve(), 'symlink in output path')
    # A regular tar artifact only: no chown, host extraction, package script or Docker call.
    with output.open('xb') as stream:
        with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            for row in rows:
                member = tarfile.TarInfo(row['path'])
                member.mode, member.uid, member.gid = row['mode'], row['uid'], row['gid']
                member.mtime = 0
                if row['type'] == 'directory':
                    member.type = tarfile.DIRTYPE
                    archive.addfile(member)
                elif row['type'] == 'symlink':
                    member.type, member.linkname = tarfile.SYMTYPE, row['target']
                    archive.addfile(member)
                else:
                    member.size = row['bytes']
                    archive.addfile(member, io.BytesIO(files[row['path']]))
    return identity(retention.read_regular(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--assemble', type=Path, help='explicitly authorized new tar path; never overwritten')
    args = parser.parse_args()
    result, files = prepare(args.store)
    if args.assemble is not None:
        result.update(rootfs_assembled=True, tar=assemble(result['entries'], files, args.assemble))
    print(json.dumps(result, sort_keys=True, indent=2))
