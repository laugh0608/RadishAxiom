#!/usr/bin/env python3
"""Bounded source inventory and unverified signature metadata for the four fetched inputs."""
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import lzma
from pathlib import Path
import re
import tarfile
import zlib

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch = load('fetch-mpc-mpfr-inputs.py')
remaining = load('inspect-musl-remaining-sources.py')
retention = load('retain-musl-verifier-inputs.py')
archive = load('inspect-archives.py')
keys = load('inspect-musl-verification-keys.py')
identity, require = retention.identity, retention.require
MAX_TAR, MAX_MEMBER, MAX_MEMBERS = 32 * 1024**2, 8 * 1024**2, 5000
SELECTED = {'mpc': {'COPYING.LESSER', 'README', 'src/mpc.h', 'doc/mpc.texi', 'build-aux/config.sub'},
            'mpfr': {'COPYING', 'COPYING.LESSER', 'README', 'src/mpfr.h', 'doc/mpfr.texi', 'config.sub'}}
TOP = {'mpc': 'mpc-1.3.1', 'mpfr': 'mpfr-4.2.2'}


def unpack(data, compression):
    require(len(data) <= 4 * 1024**2, 'compressed input limit')
    if compression == 'gz':
        decoder = zlib.decompressobj(31)
        raw = decoder.decompress(data, MAX_TAR + 1)
    else:
        require(compression == 'xz', 'unknown compression')
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=128 * 1024**2)
        raw = decoder.decompress(data, max_length=MAX_TAR + 1)
    require(len(raw) <= MAX_TAR and decoder.eof and not decoder.unused_data, 'expanded/truncated/trailing stream')
    return raw


def inventory(raw, top, selected):
    require(len(raw) <= MAX_TAR, 'tar bound')
    seen, rows, texts = set(), [], {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as tar:
        for member in tar:
            name = archive.path_name(member.name, top, member.isdir())
            require(name not in seen and len(seen) < MAX_MEMBERS, 'duplicate/member count')
            seen.add(name)
            require(member.isfile() or member.isdir(), 'linked or special member')
            require(0 <= member.size <= MAX_MEMBER, 'member bound')
            if member.isdir():
                require(member.size == 0, 'directory with data')
                continue
            require(name.startswith(top + '/'), 'file at archive root')
            data = tar.extractfile(member).read()
            require(len(data) == member.size, 'truncated member')
            path = name[len(top) + 1:]
            rows.append({'path': path, 'mode': member.mode, **identity(data)})
            if path in selected:
                texts[path] = data.decode('utf-8', errors='strict')
        require(not any(raw[tar.offset:]), 'nonzero tar tail')
    require(set(texts) == selected, 'required review file missing')
    return {'tar': identity(raw), 'member_count': len(seen), 'file_count': len(rows),
            'files': sorted(rows, key=lambda r: r['path']),
            'selected_review_files': sorted(texts), 'physical_tar_profile_verified': False}, texts


def signature_metadata(raw):
    require(0 < len(raw) <= 65536, 'signature input limit')
    armored = raw.startswith(b'-----BEGIN PGP SIGNATURE-----')
    if armored:
        lines = raw.decode('ascii').splitlines()
        require(lines[0] == '-----BEGIN PGP SIGNATURE-----' and lines[1] == '' and
                lines[-1] == '-----END PGP SIGNATURE-----' and
                re.fullmatch(r'=[A-Za-z0-9+/]{4}', lines[-2]) is not None, 'unsupported signature armor')
        data = base64.b64decode(''.join(lines[2:-2]), validate=True)
        crc = 0xB704CE
        for byte in data:
            crc ^= byte << 16
            for _ in range(8):
                crc <<= 1
                if crc & 0x1000000:
                    crc ^= 0x1864CFB
        require((crc & 0xffffff).to_bytes(3, 'big') == base64.b64decode(lines[-2][1:]), 'armor CRC mismatch')
    else:
        data = raw
    packets = keys.packets(data)
    require(len(packets) == 1 and packets[0][0] == 2, 'expected one signature packet')
    body = packets[0][1]
    fields = keys.signature(body)
    require(fields['class'] == 0 and not fields['embedded'], 'not a detached binary-document signature')
    hashed_size = int.from_bytes(body[4:6], 'big')
    hashed = keys.subpackets(body[6:6 + hashed_size])
    created = [value for kind, value in hashed if kind == 2]
    require(len(created) == 1 and len(created[0]) == 4, 'missing or ambiguous signature creation time')
    return {'armored': armored, 'decoded': identity(data), 'version': body[0], 'class': fields['class'],
            'declared_public_key_algorithm': body[2], 'declared_digest_algorithm': fields['digest'],
            'declared_issuer': fields['issuer'],
            'declared_created_at': datetime.fromtimestamp(int.from_bytes(created[0], 'big'), timezone.utc).isoformat(),
            'issuer_fingerprint_in_hashed_area': any(kind == 33 for kind, _ in hashed),
            'cryptography_executed': False, 'public_key_identity_accepted': False,
            'signature_mpis_verified': False, 'source_acceptance': 'not-assessed'}


def observations():
    rows, inputs = [], {}
    for name, target in fetch.TARGETS.items():
        successes = []
        for attempt in (1, 2):
            path = fetch.DIRECTORY / f'{name}-attempt-{attempt}.json'
            if not path.exists():
                continue
            raw = retention.read_regular(path)
            row = json.loads(raw)
            require(row['target'] == name and row['attempt'] == attempt and row['url'] == target['url'] and
                    row['method'] == identity((HERE / 'fetch-mpc-mpfr-inputs.py').read_bytes()), 'fetch identity drift')
            require(row['body']['file'] == f"{name}-attempt-{attempt}.{target['suffix']}", 'unexpected fetched filename')
            content = retention.read_regular(fetch.DIRECTORY / row['body']['file'], target['limit'])
            require(identity(content) == {k: row['body'][k] for k in ('bytes', 'sha256')}, 'fetch body drift')
            for channel in ('stdout', 'stderr'):
                data = retention.read_regular(path.with_suffix('.' + channel), 65536)
                require(identity(data) == {k: row[channel][k] for k in ('bytes', 'sha256')} and
                        data.decode('utf-8') == row[channel]['text'], 'fetch stream drift')
            rows.append(row)
            if row['passed']:
                require(row['exit_code'] == 0 and row['http_code'] == '200' and not row['parent_timeout'],
                        'unsuccessful fetch labeled passed')
                successes.append(content)
        require(len(successes) == 1, 'expected exactly one successful fetch for ' + name)
        inputs[name] = successes[0]
    return rows, inputs


def inspect():
    fetched, inputs = observations()
    candidates = {r['dependency']: r for r in remaining.inspect()['dependencies']}
    results = {}
    for name in ('mpc', 'mpfr'):
        expected = fetch.TARGETS[name]
        body = inputs[name]
        require(identity(body) == {'bytes': expected['limit'], 'sha256': expected['sha256']}, 'archive identity mismatch')
        recipe_sha1 = hashlib.sha1(body).hexdigest()
        require(recipe_sha1 == candidates[name]['recipe_sha1_statement_only'] == expected['recipe_sha1'], 'recipe mismatch')
        candidate, = candidates[name]['index_candidates']
        original, = candidate['originals'].values()
        require(original == identity(body), 'complete Sources candidate does not match archive')
        raw = unpack(body, expected['suffix'].split('.')[-1])
        result, texts = inventory(raw, TOP[name], SELECTED[name])
        version = TOP[name].removeprefix(name + '-')
        require(f'#define {name.upper()}_VERSION_STRING "{version}"' in texts['src/' + name + '.h'], 'header version drift')
        result.update(archive=identity(body), recipe_sha1=recipe_sha1, index_candidate=candidate,
                      signature=signature_metadata(inputs[name + '-signature']), source_acceptance='not-assessed',
                      license_review_complete=False)
        results[name] = result
    return {'kind': 'diagnostic-mpc-mpfr-input-review-v1', 'fetches': fetched, 'inputs': results,
            'methods': {name: identity((HERE / name).read_bytes()) for name in
                        ('inspect-mpc-mpfr-inputs.py', 'fetch-mpc-mpfr-inputs.py', 'inspect-musl-remaining-sources.py',
                         'inspect-archives.py', 'inspect-musl-verification-keys.py')},
            'upstream_programs_executed': False, 'cryptography_executed': False}


if __name__ == '__main__':
    print(json.dumps(inspect(), sort_keys=True, indent=2))
