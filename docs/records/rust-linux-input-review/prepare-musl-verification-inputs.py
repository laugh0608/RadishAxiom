#!/usr/bin/env python3
"""Plan or stage four exact public verification inputs from the retained object store; no Docker/GnuPG."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREFIX = 'docs/records/rust-linux-input-review/'
MANIFEST_SHA = '3937d4570faa72ec359dbedf8fdc9c62aa5f26942cc08ee29d1a809e03a54ae9'
IMAGE = 'sha256:55063921d0e996f717092e07dce8041cb2376cc171a070bf9a0a38a5dd16c777'
SOURCES = '.tmp/musl-auth-chain-0a66901/Sources.xz'
MUSL = '.tmp/musl-source-review-c7f7f60/musl-1.2.5.tar.gz'
PACKAGE = '.tmp/musl-trust-bbbe083-20260910/keyring-attempt-2.deb'
DIRECT = {'InRelease': PREFIX + 'musl-debian-InRelease-2026-09-10',
          'archive.asc': PREFIX + 'debian-trixie-archive-2026-09-10.asc',
          'release.asc': PREFIX + 'debian-trixie-release-2026-09-10.asc'}


def load(filename):
    spec = importlib.util.spec_from_file_location(filename, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


retention = load('retain-musl-verifier-inputs.py')
trust = load('inspect-musl-trust-inputs.py')
auth = load('inspect-musl-debian-auth.py')
require, identity = trust.require, trust.identity


def prepare(store):
    raw = retention.read_regular(store / 'manifest.json', 1024**2)
    require(identity(raw)['sha256'] == MANIFEST_SHA, 'retention manifest drift')
    rows = {row['path']: row for row in retention.manifest_rows(raw)}
    inputs = {}

    def read(path):
        row = rows[path]
        data = retention.read_regular(store / 'objects' / row['sha256'])
        require(identity(data) == {key: row[key] for key in ['bytes', 'sha256']}, 'archived input corruption: ' + path)
        inputs[path] = identity(data)
        return data

    files = {name: read(path) for name, path in DIRECT.items()}
    package = read(PACKAGE)
    require(identity(package)['sha256'] == trust.DEB_SHA, 'keyring package drift')
    _, package_files = trust.read_tar(trust.ar_members(package)['data.tar.xz'])
    keyring = package_files['usr/share/keyrings/debian-archive-keyring.gpg']
    require(identity(keyring) == {'bytes': 55918, 'sha256': trust.KEY_SHA}, 'keyring payload drift')
    files['debian-archive-keyring.gpg'] = keyring
    sources, musl = read(SOURCES), read(MUSL)
    envelope = files['InRelease'].decode('utf-8')
    require(envelope.startswith('-----BEGIN PGP SIGNED MESSAGE-----\n'), 'invalid cleartext envelope')
    body = envelope.split('\n\n', 1)[1].split('-----BEGIN PGP SIGNATURE-----\n', 1)[0]
    cleartext = ''.join(line[2:] if line.startswith('- ') else line for line in body.splitlines(keepends=True))
    release = list(auth.chain.stanzas(cleartext.splitlines(keepends=True)))
    require(len(release) == 1 and release[0].get('codename') == 'trixie', 'unexpected Release')
    sources_identity = auth.chain.checksums(release[0]['sha256'])['main/source/Sources.xz']
    require(sources_identity == identity(sources), 'Sources not bound by supplied Release text')
    source_path = store / 'objects' / identity(sources)['sha256']
    selected = auth.chain.unique_selection(auth.chain.index_stanzas(source_path, sources_identity),
                                          {'musl': '1.2.5-3.1~deb13u1'}, binary=False)['musl']
    require(selected.get('directory') == 'pool/main/m/musl', 'musl source directory drift')
    require(auth.original_digest(selected['checksums-sha256']) == identity(musl) == auth.SOURCE,
            'musl original bytes not bound by supplied Sources')
    require(set(files) == set(DIRECT) | {'debian-archive-keyring.gpg'} and sum(map(len, files.values())) == 209579,
            'verification input set drift')
    result = {'kind': 'diagnostic-musl-verification-input-plan-v1', 'manifest': identity(raw),
              'archived_inputs': inputs, 'container_inputs': {name: identity(data) for name, data in files.items()},
              'image_id': IMAGE, 'staged': False, 'container_input_bytes': 209579,
              'host_only': {'Sources.xz': identity(sources), 'musl-1.2.5.tar.gz': identity(musl)},
              'source_record': {key: selected[key] for key in ['package', 'version', 'directory']},
              'unsigned_snapshot_bindings_checked': True, 'signature_reverified': False,
              'source_acceptance': 'not-assessed', 'methods': {path.name: identity(path.read_bytes()) for path in
                  [Path(__file__), HERE / 'retain-musl-verifier-inputs.py', HERE / 'inspect-musl-trust-inputs.py',
                   HERE / 'inspect-musl-debian-auth.py', ROOT / 'scripts/inspect-debian-source-chain.py']}}
    return result, files


def stage(target, files):
    require(target.absolute() == target.resolve() and target.parent.is_dir(), 'unsafe or missing staging parent')
    require(set(files) == set(DIRECT) | {'debian-archive-keyring.gpg'}, 'unexpected staging filenames')
    target.mkdir(mode=0o755)
    for name, data in files.items():
        path = target / name
        with path.open('xb') as stream:
            stream.write(data)
        path.chmod(0o444)
        require(retention.read_regular(path) == data, 'staged input readback failed')
    require({path.name for path in target.iterdir()} == set(files), 'unexpected staged entries')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, default=ROOT / 'artifacts/source-inputs/musl-verifier-2fb2e70-20260912')
    parser.add_argument('--stage', type=Path, help='new project task directory; no overwrite')
    args = parser.parse_args()
    result, files = prepare(args.store)
    if args.stage is not None:
        stage(args.stage, files)
        result.update(staged=True, staging_path=str(args.stage))
    print(json.dumps(result, sort_keys=True, indent=2))
