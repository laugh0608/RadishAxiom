#!/usr/bin/env python3
"""Read retained tool documentation and source-index identities; no network or GnuPG."""
import gzip
import importlib.util
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stored = load('prepare-mpfr-verification.py')
content = load('inspect-musl-verifier-content.py')
sources = load('inspect-musl-verifier-sources.py')
require, identity = stored.require, stored.identity
STORE = ('musl-verifier-2fb2e70-20260912', 'musl-retention-manifest-2026-09-12.json',
         '3937d4570faa72ec359dbedf8fdc9c62aa5f26942cc08ee29d1a809e03a54ae9')
PACKAGE = '.tmp/musl-verifier-d04b225-20260912/gpg-attempt-1.deb'
SOURCE_INDEX = '.tmp/musl-auth-chain-0a66901/Sources.xz'


def inspect():
    files, store = stored.read_store(ROOT, *STORE)
    package = files[PACKAGE]
    require(identity(package) == {'bytes': 578896, 'sha256':
            '840abc3e9178b9578fbc9c9674ebb2f3b983790f713ffd2b6a0371d8670dc8e7'}, 'gpg package drift')
    ar = content.reader.ar_members(package)
    _, control = content.read_tar(ar['control.tar.xz'], 4 * 1024**2)
    payload, members = content.read_tar(ar['data.tar.xz'], 64 * 1024**2)
    fields, = content.reader.CHAIN.stanzas(control['control'].decode().splitlines(keepends=True))
    require((fields['package'], fields['version'], fields['architecture'], fields['source']) ==
            ('gpg', '2.4.7-21+deb13u1+b4', 'arm64', 'gnupg2 (2.4.7-21+deb13u1)'),
            'binary/source identity drift')
    with gzip.GzipFile(fileobj=io.BytesIO(members['usr/share/man/man1/gpg.1.gz'])) as stream:
        manual = stream.read(256 * 1024 + 1)
    require(identity(manual) == {'bytes': 181578, 'sha256':
            '1c3f57387f18152a63d383a4c289a055c679666fc5d7acfef36067ac990ace29'}, 'manual drift')
    lines = manual.decode('utf-8').splitlines()
    require(not any(Path(row['path']).name in {'DETAILS', 'DETAILS.gz', 'gpg.texi'}
                    for row in payload['members']), 'review missing-material conclusion again')

    # Re-read the complete retained index, rather than trusting only its old projection.
    require(identity(files[SOURCE_INDEX]) == sources.SOURCES, 'source index drift')
    index_path = ROOT / 'artifacts/source-inputs' / STORE[0] / 'objects' / sources.SOURCES['sha256']
    source_report = sources.inspect(index_path)
    row, = [r for r in source_report['candidate_source_rows'] if r['package'] == 'gnupg2']
    old_source = stored.retention.read_regular(HERE / 'musl-verifier-sources-2026-09-12.json')
    require(identity(old_source)['sha256'] ==
            '17acf569395db05de249f249057c00cf6d55ee7695e02a7fc1fd65581d997f81', 'old source report drift')
    require(row == next(r for r in json.loads(old_source)['candidate_source_rows']
                        if r['package'] == 'gnupg2') and row['version'] == '2.4.7-21+deb13u1',
            'source projection drift')
    targets = []
    for name, entry in sorted(sources.chain.checksums(row['checksums-sha256']).items()):
        targets.append({'name': name, **entry,
                        'url': 'https://deb.debian.org/debian/' + row['directory'] + '/' + name,
                        'object_present_in_checked_store': entry['sha256'] in
                        {identity(data)['sha256'] for data in files.values()}})
    require(len(targets) == 4 and sum(t['bytes'] for t in targets) == 8146831,
            'source acquisition scope drift')
    require(not any(t['object_present_in_checked_store'] for t in targets),
            'source material already retained; review it before proposing acquisition')

    # These are observations about retained material, not a replacement verification profile.
    return {'kind': 'diagnostic-gmp-tool-materials-review-v1', 'retention': store,
            'gpg_package': identity(package),
            'control_identity': {k: fields[k] for k in ('package', 'version', 'architecture', 'source')},
            'gpg_payload_regular_files': sorted(members),
            'manual': {'path_in_package': 'usr/share/man/man1/gpg.1.gz', **identity(manual),
                       'details_reference_lines': [i + 1 for i, line in enumerate(lines) if 'DETAILS' in line],
                       'keyexpired_literal_present': 'KEYEXPIRED' in manual.decode(),
                       'key_considered_literal_present': 'KEY_CONSIDERED' in manual.decode(),
                       'reviewed_line_ranges': [[324, 338], [2962, 2968], [3355, 3362]]},
            'source_index': identity(files[SOURCE_INDEX]), 'source_row': row,
            'supplemental_material_targets': targets, 'request_count': len(targets),
            'expected_response_bytes_total': sum(t['bytes'] for t in targets),
            'status_repetition_semantics': 'not-established-from-reviewed-local-material',
            'effective_subkey_expiry_semantics': 'not-established-from-reviewed-local-material',
            'absence_scope': 'checked-retention-store-and-fixed-gpg-payload-only',
            'assessment_revision_prepared': False, 'network_requests_executed': False,
            'new_cryptography_executed': False, 'source_acceptance': 'not-assessed',
            'historical_validity': 'not-established',
            'methods': {str(p.relative_to(ROOT)): identity(p.read_bytes()) for p in
                        (Path(__file__).resolve(), Path(stored.__file__), Path(content.__file__),
                         Path(sources.__file__), Path(stored.retention.__file__),
                         Path(content.reader.__file__), sources.METHOD)}}


if __name__ == '__main__':
    print(json.dumps(inspect(), sort_keys=True, indent=2))
