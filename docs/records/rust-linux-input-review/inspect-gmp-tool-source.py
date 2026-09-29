#!/usr/bin/env python3
"""Bounded static GnuPG source/patch inventory; never extract or execute upstream files."""
import argparse
import bz2
import gzip
import importlib.util
import io
import json
import lzma
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


route = load('fetch-gmp-tool-materials.py')
retention = load('retain-musl-verifier-inputs.py')
paths = load('inspect-archives.py')
chain_spec = importlib.util.spec_from_file_location('chain', HERE.parents[2] / 'scripts/inspect-debian-source-chain.py')
chain = importlib.util.module_from_spec(chain_spec)
chain_spec.loader.exec_module(chain)
identity, require = retention.identity, retention.require
LIMITS = {'compressed': 16 * 1024**2, 'tar': 128 * 1024**2, 'member': 8 * 1024**2, 'members': 10000}
SELECTED = {'doc/DETAILS', 'doc/gpg.texi', 'g10/getkey.c', 'g10/keylist.c', 'g10/sig-check.c',
            'g10/import.c', 'g10/mainproc.c', 'g10/packet.h', 'common/status.c',
            'COPYING', 'AUTHORS', 'README'}


def inventory(data, compression, top):
    require(0 < len(data) <= LIMITS['compressed'], 'compressed bound')
    decoder = (bz2.BZ2Decompressor() if compression == 'bz2' else
               lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=128 * 1024**2)
               if compression == 'xz' else None)
    require(decoder is not None, 'unsupported compression')
    raw = decoder.decompress(data, max_length=LIMITS['tar'] + 1)
    require(len(raw) <= LIMITS['tar'] and decoder.eof and not decoder.unused_data,
            'oversized, truncated or trailing stream')
    require(len(raw) % 512 == 0, 'tar alignment')
    rows, texts = {}, {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            name = paths.path_name(member.name, top, member.isdir())
            require(name not in rows and len(rows) < LIMITS['members'], 'duplicate or member count bound')
            require((member.isfile() or member.isdir()) and not member.issparse(), 'linked, sparse or special member')
            require(0 <= member.size <= LIMITS['member'] and (not member.isdir() or member.size == 0),
                    'member size or directory payload')
            row = {'path': name, 'kind': 'directory' if member.isdir() else 'file',
                   'mode': member.mode, 'uid': member.uid, 'gid': member.gid, 'bytes': member.size}
            if member.isfile():
                require(name.startswith(top + '/'), 'file at root')
                body = archive.extractfile(member).read(LIMITS['member'] + 1)
                require(len(body) == member.size, 'truncated member')
                row.update(identity(body))
                relative = name[len(top) + 1:]
                if top == 'debian' or relative in SELECTED:
                    texts[relative] = body.decode('utf-8')
            rows[name] = row
        tail = raw[archive.offset:]
        require(len(tail) >= 1024 and not any(tail), 'missing or nonzero tar tail')
    require(rows, 'empty tar')
    for name in rows:
        for parent in Path(name).parents:
            require(str(parent) not in rows or rows[str(parent)]['kind'] == 'directory', 'file ancestor')
    require(top != 'gnupg-2.4.7' or SELECTED <= texts.keys(), 'missing selected source')
    return {'archive': identity(data), 'tar': identity(raw), 'member_count': len(rows),
            'members': [rows[n] for n in sorted(rows)],
            'selected': {n: identity(t.encode()) for n, t in sorted(texts.items())}}, texts


def inspect(directory):
    plan = route.plan()
    result = json.loads(retention.read_regular(directory / 'fetch-result.json'))
    require(result['passed'] is True and result['plan'] == plan and len(result['invocations']) == 4,
            'fetch result or plan drift')
    require(json.loads(retention.read_regular(directory / 'fetch-plan.json')) == plan, 'saved plan drift')
    bodies = {}
    for expected, recorded in zip(plan['targets'], result['invocations']):
        name = expected['name']
        row = recorded['transport']
        stem = directory / (name + '-attempt-1')
        require(json.loads(retention.read_regular(Path(str(stem) + '.json'))) == row, 'transport log drift')
        argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--proto', '=https',
                '--tlsv1.2', '--max-time', '60', '--max-filesize', str(expected['bytes']),
                '--output', str(route.DIRECTORY / (name + '-attempt-1.body')),
                '--write-out', '%{http_code}\n', expected['url']]
        require(row['argv'] == argv and row['target'] == name and row['attempt'] == 1 and
                row['exit_code'] == 0 and row['http_code'] == '200' and row['parent_timeout'] is False and
                row['passed'] is True and recorded['source_index_bytes_match'] is True and
                row['method'] == plan['methods']['fetch-mpc-mpfr-inputs.py'], 'request identity drift')
        body = retention.read_regular(Path(str(stem) + '.body'), expected['bytes'])
        require(identity(body) == {k: expected[k] for k in ('bytes', 'sha256')} and
                row['body'] == {'file': name + '-attempt-1.body', **identity(body)}, 'source bytes drift')
        for channel in ('stdout', 'stderr'):
            raw = retention.read_regular(Path(str(stem) + '.' + channel), 65536)
            require(row[channel] == {**identity(raw), 'text': raw.decode()}, 'request stream drift')
        bodies[name] = body
    upstream, upstream_text = inventory(bodies[route.ORDER[1]], 'bz2', 'gnupg-2.4.7')
    debian, debian_text = inventory(bodies[route.ORDER[3]], 'xz', 'debian')
    envelope = bodies[route.ORDER[0]].decode('utf-8')
    require(envelope.startswith('-----BEGIN PGP SIGNED MESSAGE-----\n'), 'dsc envelope drift')
    clear = envelope.split('\n\n', 1)[1].split('-----BEGIN PGP SIGNATURE-----\n', 1)[0]
    clear = ''.join(line[2:] if line.startswith('- ') else line for line in clear.splitlines(keepends=True))
    dsc, = chain.stanzas(clear.splitlines(keepends=True))
    require(dsc['source'] == 'gnupg2' and dsc['version'] == '2.4.7-21+deb13u1' and
            chain.checksums(dsc['checksums-sha256']) ==
            {r['name']: {k: r[k] for k in ('bytes', 'sha256')} for r in plan['targets'] if not r['name'].endswith('.dsc')},
            'dsc/source index mismatch')
    series = [line.strip() for line in debian_text['patches/series'].splitlines()
              if line.strip() and not line.startswith('#')]
    require(len(series) == len(set(series)), 'duplicate patch series')
    patch_targets = {}
    for patch in series:
        require('patches/' + patch in debian_text and len(patch.split()) == 1, 'unsupported patch series')
        patch_targets[patch] = [line for line in debian_text['patches/' + patch].splitlines()
                                if line.startswith(('--- ', '+++ '))]
    report = {'kind': 'diagnostic-gmp-tool-source-review-v1', 'fetch_result': identity(
              retention.read_regular(directory / 'fetch-result.json')), 'upstream': upstream, 'debian': debian,
              'patch_series': series, 'patch_targets': patch_targets, 'limits': LIMITS,
              'dsc_source': dsc['source'], 'dsc_version': dsc['version'], 'dsc_index_bytes_match': True,
              'dsc_signature_checked': False,
              'source_acceptance': 'not-assessed', 'new_cryptography_executed': False,
              'upstream_programs_executed': False, 'physical_tar_profile_verified': False,
              'methods': {p.name: identity(retention.read_regular(p)) for p in
                          (Path(__file__), Path(route.__file__), Path(paths.__file__), Path(retention.__file__),
                           Path(chain.__file__))}}
    return report, {'upstream': upstream_text, 'debian': debian_text,
                    'dsc': bodies[route.ORDER[0]].decode()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=route.DIRECTORY)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--texts', type=Path, required=True)
    args = parser.parse_args()
    report, texts = inspect(args.directory)
    for path, data, compressed in ((args.output, report, True), (args.texts, texts, False)):
        raw = (json.dumps(data, sort_keys=True, indent=2) + '\n').encode()
        with path.open('xb') as stream:
            stream.write(gzip.compress(raw, mtime=0) if compressed else raw)
    print(json.dumps({'upstream_members': report['upstream']['member_count'],
                      'debian_members': report['debian']['member_count'],
                      'patches': len(report['patch_series'])}, indent=2))
