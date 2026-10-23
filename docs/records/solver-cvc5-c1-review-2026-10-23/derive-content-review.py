#!/usr/bin/env python3
"""Derive package-path/copyright/source correspondence from the bounded inventory."""
from collections import defaultdict, Counter
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import posixpath
import re

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
INVENTORY = ROOT / 'artifacts/cvc5-c1-content-review-2026-10-23-attempt-4/content-inventory.json.gz'
spec = importlib.util.spec_from_file_location('chain', ROOT / 'scripts/inspect-debian-source-chain.py')
chain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chain)


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def require(value, message):
    if not value:
        raise ValueError(message)


def resolve(index, path):
    path = path.removeprefix('/')
    trail, seen = [], set()
    for _ in range(40):
        require(path not in seen, 'link cycle: ' + path)
        seen.add(path)
        parts = path.split('/')
        redirected = False
        for n in range(1, len(parts) + 1):
            prefix = '/'.join(parts[:n])
            rows = index.get(prefix, [])
            if not rows:
                continue
            row = rows[0]
            if row['kind'] in {'symlink', 'hardlink'}:
                target = row['target']
                joined = target if target.startswith('/') or row['kind'] == 'hardlink' else posixpath.join(posixpath.dirname(prefix), target)
                path = posixpath.normpath(posixpath.join(joined, *parts[n:])).removeprefix('/')
                require(path != '..' and not path.startswith('../'), 'link escapes virtual root')
                trail.append({'path': prefix, 'target': target, 'packages': [r['package'] for r in rows]})
                redirected = True
                break
        if not redirected:
            rows = index.get(path, [])
            return {'resolved_path': path, 'links': trail,
                    'status': 'resolved' if rows and rows[0]['kind'] == 'file' else 'missing-or-not-file',
                    'files': rows}
    raise ValueError('link depth exceeded')


def main():
    inventory = json.loads(gzip.decompress(INVENTORY.read_bytes()))
    require(inventory['complete'], 'incomplete inventory')
    binaries = [o for o in inventory['observations'] if o['kind'] == 'binary']
    index = defaultdict(list)
    for package in binaries:
        for entry in package['data']['entries']:
            if entry['kind'] != 'directory':
                index[entry['path']].append({**entry, 'package': package['package'], 'version': package['version'],
                                           'source_package': package['source_package'], 'source_version': package['source_version']})
    collisions = []
    for path, rows in index.items():
        if len(rows) > 1:
            identities = {(r['kind'], r.get('sha256'), r.get('target')) for r in rows}
            require(len(identities) == 1, 'conflicting package payload: ' + path)
            collisions.append({'path': path, 'packages': [r['package'] for r in rows]})
    copyrights = []
    for p in binaries:
        path = 'usr/share/doc/' + p['package'] + '/copyright'
        resolved = resolve(index, path)
        require(resolved['status'] == 'resolved', 'copyright unresolved: ' + path)
        copyrights.append({'package': p['package'], 'requested': path, **resolved})
    wanted = ['usr/bin/aarch64-linux-gnu-' + s for s in ['gcc-12', 'g++-12', 'ld', 'ar', 'ranlib', 'strip', 'as']]
    wanted += ['usr/bin/' + s for s in ['cmake', 'make', 'python3', 'pkgconf', 'm4', 'cc', 'gcc', 'g++']]
    wanted += ['bin/sh']
    wanted += sorted(p for p in index if p.startswith(('usr/lib/gcc/aarch64-linux-gnu/12/', 'usr/lib/aarch64-linux-gnu/')) and
                     (p.endswith('.o') or p.rsplit('/', 1)[-1] in {'libc.a', 'libm.a', 'libgcc.a', 'libgcc_eh.a', 'libstdc++.a', 'libedit.a', 'libtermcap.a', 'libtinfo.a', 'libbsd.a', 'libmd.a'}))
    paths = [{'requested_path': p, **resolve(index, p)} for p in wanted]
    pc = [row for entries in index.values() for row in entries if row['path'].endswith('.pc') and row['path'].rsplit('/', 1)[-1] in {'libedit.pc', 'libbsd.pc', 'libmd.pc', 'tinfo.pc'}]
    sdk = json.loads((ROOT / 'docs/records/solver-cvc5-c0-2026-10-17/sdk-selection.json').read_bytes())
    retained = json.loads((HERE / 'retained-inventory.json').read_bytes())
    plan = json.loads((ROOT / 'docs/records/solver-cvc5-c1-2026-10-22/acquisition-plan.json').read_bytes())
    by_name = {row['relative_path'].removeprefix('inputs/'): retained['inventory'][n] for n, row in enumerate(plan['entries'])}
    sources = []
    for src in sdk['source_packages']:
        dsc = next(f for f in src['files'] if f['kind'] == 'dsc')
        p = ROOT / by_name[src['Directory'] + '/' + dsc['filename']]['path']
        raw = p.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == dsc['sha256'] and len(raw) == dsc['size'], 'dsc identity')
        body = raw.decode('utf-8').split('\n\n', 1)[1].split('-----BEGIN PGP SIGNATURE-----')[0]
        body = '\n'.join(line[2:] if line.startswith('- ') else line for line in body.split('\n'))
        fields = list(chain.stanzas(body.splitlines(keepends=True)))
        require(len(fields) == 1, 'dsc stanza count')
        fields = fields[0]
        require((fields['source'], fields['version'], fields['format']) == (src['Package'], src['Version'], src['Format']), 'dsc fields')
        expected = {f['filename']: {'bytes': f['size'], 'sha256': f['sha256']} for f in src['files'] if f['kind'] != 'dsc'}
        require(chain.checksums(fields['checksums-sha256']) == expected, 'dsc source checksums')
        sources.append({'package': src['Package'], 'version': src['Version'], 'format': src['Format'], 'dsc': identity(p),
                        'source_files_matched': len(expected), 'maintainer_signature_verified': False})
    libpoly = ROOT / '.tmp/cvc5-c0-acquisition-2026-10-17/sources/libpoly/libpoly-0.2.1'
    selected = []
    for folder in ('src', 'include'):
        for path in sorted((libpoly / folder).rglob('*')):
            if path.is_file() and path.suffix in {'.c', '.cpp', '.h', '.in'}:
                raw = path.read_text()
                selected.append({**identity(path), 'relative_path': str(path.relative_to(libpoly)),
                                 'lgpl_notice': 'GNU Lesser General Public License' in raw,
                                 'lgpl_3_or_later_notice': 'either version 3' in raw and 'any later version' in raw})
    output = {'format': 'radishaxiom-private-cvc5-c1-derived-review', 'version': '0.1',
              'method': identity(Path(__file__)), 'inventory': identity(INVENTORY), 'package_count': len(binaries),
              'non_directory_paths': len(index), 'identical_overlapping_paths': collisions,
              'copyright_resolution': copyrights, 'selected_paths': paths, 'pkgconfig_texts': pc,
              'dsc_source_correspondence': sources, 'libpoly_source_and_header_notices': selected,
              'source_patch_applied': False, 'copyright_legal_acceptance': 'not-accepted',
              'pkgconf_executed': False, 'input_acceptance': 'not-accepted', 'build_ready': False}
    (HERE / 'derived-content-review.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'copyrights_resolved': len(copyrights), 'sources_matched': len(sources),
                      'unresolved_selected_paths': [p['requested_path'] for p in paths if p['status'] != 'resolved'],
                      'libpoly_notice_counts': dict(Counter(str(p['lgpl_notice']) + ':' + str(p['lgpl_3_or_later_notice']) for p in selected))}, default=str))


if __name__ == '__main__':
    main()
