#!/usr/bin/env python3
"""Read pinned retained GMP bytes and derive a transparent strong-signature projection offline."""
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


prior = load('prepare-mpfr-verification.py')
source = load('inspect-gmp-inputs.py')
profile = load('inspect-gmp-verification.py')
retention, identity, require = prior.retention, prior.identity, prior.require
INPUT_LIMIT, TOTAL_LIMIT = 2 * 1024**2, 5 * 1024**2
STORE = ('gmp-inputs-50ef87c-20260925', 'gmp-retention-manifest-2026-09-25.json',
         '7d2d36dfe650ca3bd9c3aa678023fdb8001fd000f95c84847310be8793f337ab')
PREFIX = '.tmp/gmp-inputs-50ef87c-20260925/'
WRONG_PRIMARY = '3A24BC1E8FB409FA9F14371813FCEF89DD9E3C4F'
write_new = prior.write_new


def prepare(root=ROOT):
    files, store = prior.read_store(root, *STORE)
    archive, signature, armor = (files[PREFIX + name] for name in
                                ('gmp-attempt-1.tar.xz', 'signature-attempt-1.sig', 'public-key-attempt-1.asc'))
    source.archive_binding(archive)
    require(identity(signature) == {'bytes': 374, 'sha256':
            '94def8c1a731854de684689126046ec93589147abd4cd0025f12d741d323aa82'}, 'signature bytes drift')
    require(identity(armor) == {'bytes': 32347, 'sha256':
            '50561c50f40cd9746af214c995fb219bbe7f3b9c5f038b918f5df543bb3f846f'}, 'full key bytes drift')
    pages = source.pages(files[PREFIX + 'identity-attempt-1.html'], files[PREFIX + 'announcement-attempt-1.html'])
    sig = source.inputs.signature_metadata(signature)
    require(sig['declared_issuer'] == profile.PRIMARY and sig['declared_digest_algorithm'] == 10 and
            sig['declared_public_key_algorithm'] == 1 and sig['issuer_fingerprint_in_hashed_area'] and
            sig['declared_created_at'] == '2023-07-30T12:18:33+00:00' and sig['class'] == 0,
            'detached signature profile drift')
    raw = profile.material.armor(armor)
    strong, projection = profile.project(raw)
    ring = files['.tmp/binutils-key-refresh-383b570-20260925/gnu-keyring-attempt-1.gpg']
    require(identity(ring) == source.refresh.RING, 'wrong-key source ring drift')
    wrong, wrong_report = source.refresh.select(ring, WRONG_PRIMARY)
    require(profile.PRIMARY not in profile.keys.key_blocks(wrong), 'wrong key includes GMP primary')
    midpoint = len(archive) // 2
    tampered = archive[:midpoint] + bytes([archive[midpoint] ^ 1]) + archive[midpoint + 1:]
    staged = {'gmp.tar.xz': archive, 'gmp.tar.xz.asc': signature, 'gmp.original.asc': armor,
              'gmp.raw.gpg': raw, 'gmp.strong.gpg': strong, 'gmp.tampered.xz': tampered,
              'wrong.gpg': wrong, 'empty.gpg': b''}
    require(all(len(v) <= INPUT_LIMIT for v in staged.values()) and
            sum(map(len, staged.values())) + len(strong) <= TOTAL_LIMIT, 'prepared input bound')
    report = {'kind': 'diagnostic-gmp-verification-inputs-v1', 'store': store,
              'inputs': {name: identity(data) for name, data in staged.items()},
              'projection': projection, 'wrong_key_selection': wrong_report, 'official_pages': pages,
              'signature': sig, 'key_material_as_of': '2026-09-25',
              'signature_time_is_signer_claim_not_independent_timestamp': True,
              'historical_validity': 'not-established', 'cryptography_executed': False,
              'source_acceptance': 'not-assessed', 'off_device_backup_verified': False}
    return report, staged


def stage(output, files):
    folder = output / 'inputs'
    require(folder == folder.resolve(), 'symlink staging path')
    require(set(files) == {'gmp.tar.xz', 'gmp.tar.xz.asc', 'gmp.original.asc', 'gmp.raw.gpg',
                           'gmp.strong.gpg', 'gmp.tampered.xz', 'wrong.gpg', 'empty.gpg'}, 'staging file set drift')
    folder.mkdir(mode=0o755)
    for name, raw in files.items():
        write_new(folder / name, raw)
    snapshot(folder)
    return folder


def snapshot(folder):
    require(folder.is_absolute() and folder == folder.resolve(), 'unsafe snapshot path')
    paths = sorted(folder.iterdir())
    require(len(paths) <= 9 and all(re.fullmatch('[A-Za-z0-9.-]+', p.name) for p in paths), 'input set bound')
    require(all(p.lstat().st_mode & 0o777 == 0o444 for p in paths), 'input mode drift')
    result = {p.name: identity(retention.read_regular(p, INPUT_LIMIT)) for p in paths}
    require(sum(row['bytes'] for row in result.values()) <= TOTAL_LIMIT, 'cumulative input bound')
    return result


if __name__ == '__main__':
    print(json.dumps(prepare()[0], sort_keys=True, indent=2))
