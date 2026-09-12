#!/usr/bin/env python3
"""Inventory verifier source candidates in the retained snapshot; no acceptance."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
METHOD = ROOT / 'scripts/inspect-debian-source-chain.py'
spec = importlib.util.spec_from_file_location('debian_chain', METHOD)
chain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chain)
RELEASE = {'bytes': 140416, 'sha256':
           '98b25b5cd185c59d34aa6e4c3e9b5b8f01bbe9d104fe2dcfbcd30dc0a14a59ed'}
SOURCES = {'bytes': 10527804, 'sha256':
           'e8bbadd8389119e841494630998187f961d7de4d5b1dcbeed4f792a1d423299f'}
PACKAGES = {'bytes': 9607412, 'sha256':
            '753da751bbc7a679f48bd1b623ffd4479cb6861c426118284c76eb82909e4908'}
NAMES = {'gnupg2', 'libgcrypt20', 'libgpg-error', 'libassuan', 'bzip2',
         'glibc', 'libksba', 'npth', 'readline', 'sqlite3', 'zlib', 'ncurses',
         'init-system-helpers'}


def inspect(sources):
    release = HERE / 'musl-debian-InRelease-2026-09-10'
    chain.hash_file(release, RELEASE)
    # This is text from fixed bytes, not newly authenticated plaintext.
    envelope = release.read_text()
    body = envelope.split('\n\n', 1)[1].split('-----BEGIN PGP SIGNATURE-----\n', 1)[0]
    clear = ''.join(line[2:] if line.startswith('- ') else line
                    for line in body.splitlines(keepends=True))
    rows = list(chain.stanzas(clear.splitlines(keepends=True)))
    if len(rows) != 1:
        raise ValueError('unexpected Release stanza count')
    indexes = chain.checksums(rows[0]['sha256'])
    if (indexes['main/source/Sources.xz'] != SOURCES or
            indexes['main/binary-arm64/Packages.xz'] != PACKAGES):
        raise ValueError('snapshot index identity drift')
    selected = [{key: row[key] for key in
                 ('package', 'version', 'binary', 'directory', 'checksums-sha256')}
                for row in chain.index_stanzas(sources, SOURCES)
                if row.get('package') in NAMES]
    if {row['package'] for row in selected} != NAMES:
        raise ValueError('missing candidate source family')
    identities = [(row['package'], row['version']) for row in selected]
    if len(set(identities)) != len(identities):
        raise ValueError('duplicate candidate source identity')
    return {
        'kind': 'diagnostic-verifier-source-candidates', 'acceptance': 'not-assessed',
        'signature_reverified': False, 'binary_selection_complete': False,
        'runtime_closure_assessed': False,
        'methods': {str(path.relative_to(ROOT)): chain.sha256(path.read_bytes())
                    for path in (Path(__file__), METHOD)},
        'inrelease': RELEASE, 'sources': SOURCES,
        'required_binary_index': {**PACKAGES, 'url':
            'https://deb.debian.org/debian/dists/trixie/main/binary-arm64/'
            'by-hash/SHA256/' + PACKAGES['sha256']},
        'candidate_source_rows': sorted(selected, key=lambda row:
                                        (row['package'], row['version'])),
        'multiple_source_versions': {
            name: sorted(row['version'] for row in selected if row['package'] == name)
            for name in sorted(NAMES)
            if sum(row['package'] == name for row in selected) > 1},
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.sources), sort_keys=True, indent=2))
