#!/usr/bin/env python3
"""Read back pinned MPFR source/key stores and prepare a bounded offline diagnostic plan."""
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


profile = load('inspect-mpfr-verification.py')
source = load('inspect-mpc-mpfr-inputs.py')
retention = source.retention
identity, require = retention.identity, retention.require
INPUT_LIMIT = 2 * 1024**2
STORES = (
    ('mpc-mpfr-aa13d7c-20260916', 'mpc-mpfr-retention-manifest-2026-09-16.json',
     '44b09c5f5f79404286731e7036f3f48c3439f9af4b153906b387a40c2645c11a'),
    ('mpc-mpfr-keys-ee917c7-20260916', 'mpc-mpfr-key-retention-manifest-2026-09-16.json',
     '9e3f4aba665533924ba58a77dd501c68a82aa9eaa81d5733dfc263b65c6dfbeb'),
)
SOURCE_PREFIX = '.tmp/musl-remaining-source-fetch-aa13d7c-20260916/'
KEY_PREFIX = '.tmp/mpc-mpfr-keys-ee917c7-20260916/'


def read_store(root, name, manifest_name, digest):
    store = root / 'artifacts/source-inputs' / name
    raw = retention.read_regular(store / 'manifest.json', 1024**2)
    require(identity(raw)['sha256'] == digest and raw == retention.read_regular(HERE / manifest_name),
            'retention manifest drift')
    rows = retention.manifest_rows(raw)
    require({p.name for p in (store / 'objects').iterdir()} == {r['sha256'] for r in rows}, 'store object set drift')
    files = {}
    for row in rows:
        data = retention.read_regular(store / 'objects' / row['sha256'])
        require(identity(data) == {k: row[k] for k in ('bytes', 'sha256')}, 'retained object corruption')
        files[row['path']] = data
    return files, {'store': name, 'manifest': identity(raw), 'files_checked': len(rows),
                   'objects_checked': len({r['sha256'] for r in rows})}


def prepare(root=ROOT):
    files, stores = {}, []
    for args in STORES:
        restored, report = read_store(root, *args)
        require(all(path not in files or files[path] == raw for path, raw in restored.items()),
                'conflicting retained paths')
        files.update(restored)
        stores.append(report)
    archive = files[SOURCE_PREFIX + 'mpfr-attempt-1.tar.xz']
    signature = files[SOURCE_PREFIX + 'mpfr-signature-attempt-1.asc']
    armor = files[KEY_PREFIX + 'mpfr-key-attempt-1.asc']
    require(identity(archive) == {'bytes': 1505596,
            'sha256': 'b67ba0383ef7e8a8563734e2e889ef5ec3c3b898a01d00fa0a6869ad81c6ce01'}, 'source identity drift')
    sig = source.signature_metadata(signature)
    require(sig['declared_issuer'] == profile.PRIMARY and sig['declared_digest_algorithm'] == 8 and
            sig['declared_public_key_algorithm'] == 22 and sig['issuer_fingerprint_in_hashed_area'] and
            sig['declared_created_at'] == '2025-03-20T09:22:25+00:00', 'source signature profile drift')
    blocks = profile.keys.key_blocks(profile.material.armor(armor))
    require(set(blocks) == {profile.PRIMARY, profile.OLD}, 'original public key set drift')
    selected = blocks[profile.PRIMARY]
    inventory = profile.inventory(selected)
    require(len(inventory['foreign']) == 3, 'original foreign material drift')
    # The wrong-key case is a separately retained, structurally inventoried Debian release key.
    # Using it avoids interpreting old MPFR expiry/weak certifications as this negative's cause.
    musl = load('prepare-musl-verification-inputs.py')
    old_inputs, musl_files = musl.prepare(root / 'artifacts/source-inputs/musl-verifier-2fb2e70-20260912')
    wrong = load('inspect-musl-key-status.py').decoded_key(musl_files['release.asc'])
    require(profile.PRIMARY not in profile.keys.key_blocks(wrong), 'wrong key contains target primary')
    tampered = archive[:len(archive) // 2] + bytes([archive[len(archive) // 2] ^ 1]) + archive[len(archive) // 2 + 1:]
    staged = {'mpfr.tar.xz': archive, 'mpfr.tar.xz.asc': signature, 'mpfr.original.asc': armor,
              'mpfr.raw.gpg': selected, 'wrong.gpg': wrong, 'empty.gpg': b'', 'mpfr.tampered.xz': tampered}
    report = {'kind': 'diagnostic-mpfr-verification-inputs-v1', 'stores': stores,
              'wrong_key_store_manifest': old_inputs['manifest'],
              'inputs': {name: identity(raw) for name, raw in staged.items()},
              'selected_primary': profile.PRIMARY, 'uid_count': 3, 'self_certifications': 4,
              'excluded_foreign_sha1_certifications': 3, 'signature': sig,
              'cryptography_executed': False, 'source_acceptance': 'not-assessed',
              'off_device_backup_verified': False}
    return report, staged


def write_new(path, raw):
    require(path.is_absolute() and path == path.resolve() and 0 <= len(raw) <= INPUT_LIMIT,
            'unsafe or oversized staged input')
    with path.open('xb') as stream:
        stream.write(raw)
    path.chmod(0o444)
    require(retention.read_regular(path, INPUT_LIMIT) == raw, 'staged readback mismatch')


def stage(output, files):
    folder = output / 'inputs'
    require(folder == folder.resolve(), 'symlink staging path')
    require(set(files) == {'mpfr.tar.xz', 'mpfr.tar.xz.asc', 'mpfr.original.asc', 'mpfr.raw.gpg',
                           'wrong.gpg', 'empty.gpg', 'mpfr.tampered.xz'}, 'staging file set drift')
    folder.mkdir(mode=0o755)
    for name, raw in files.items():
        write_new(folder / name, raw)
    return folder


def snapshot(folder):
    require(folder.is_absolute() and folder == folder.resolve(), 'unsafe snapshot path')
    paths = sorted(folder.iterdir())
    require(len(paths) <= 8 and all(re.fullmatch('[A-Za-z0-9.-]+', p.name) for p in paths), 'input set bound')
    require(all(p.lstat().st_mode & 0o777 == 0o444 for p in paths), 'input mode drift')
    result = {p.name: identity(retention.read_regular(p, INPUT_LIMIT)) for p in paths}
    require(sum(row['bytes'] for row in result.values()) <= 4 * 1024**2, 'cumulative input bound')
    return result


if __name__ == '__main__':
    print(json.dumps(prepare()[0], sort_keys=True, indent=2))
