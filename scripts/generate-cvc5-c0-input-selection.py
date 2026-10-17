#!/usr/bin/env python3
"""Generate the private, blocked C0 selection record from retained observations.

No network, package resolution, installation, or build is performed. This entry
contains reviewed selection decisions; it never promotes them to acceptance.
Version 0.3 explicitly replaces the 0.1/0.2 drafts; old drafts must
be regenerated and are not silently interpreted with the new meaning.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/records/solver-cvc5-c0-2026-10-17/input-selection.json'
COMMIT = 'f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341'
SNAPSHOT = 'https://snapshot.debian.org/archive/debian/20230612T000000Z/'
SOURCE_INDEXES = (
    ('docs/records/cvc5-cli-dependencies-2026-10-17/source-inputs.json', '.tmp/solver-cli-licenses-2026-10-17'),
    ('docs/records/cvc5-provenance-followup-2026-10-17/source-inputs.json', '.tmp/cvc5-provenance-followup-2026-10-17'),
)
REVIEW_DIRECTORY = 'docs/records/solver-cvc5-source-review-2026-10-17/'
SDK_ITEMS = (
    ('compiler', ['gcc-12', 'g++-12', 'cpp-12', 'gcc-12-base'], ['gcc-12 explicit executable path unresolved', 'g++-12 explicit executable path unresolved', 'cpp-12 explicit executable path unresolved']),
    ('binutils', ['binutils', 'binutils-aarch64-linux-gnu', 'binutils-common'], ['as', 'ld.bfd', 'ar', 'ranlib', 'strip', 'readelf', 'nm', 'objdump']),
    ('gcc-runtime', ['libgcc-12-dev', 'libstdc++-12-dev', 'libgcc-s1', 'libstdc++6'], ['crtbegin.o', 'crtend.o', 'libgcc.a', 'libgcc_eh.a', 'libstdc++.a']),
    ('glibc-sysroot', ['libc6', 'libc6-dev', 'libc-dev-bin', 'linux-libc-dev'], ['crt1.o', 'crti.o', 'crtn.o', 'libc.a', 'libm.a', 'libpthread.a', 'libdl.a', 'librt.a', 'headers']),
    ('editline', ['libedit-dev', 'libedit2'], ['histedit.h', 'libedit.a', 'libedit.pc']),
    ('terminfo', ['libncurses-dev', 'libtinfo6'], ['libtinfo.a', 'tinfo.pc', 'headers']),
    ('bsd', ['libbsd-dev', 'libbsd0'], ['libbsd.a', 'libbsd.pc', 'headers']),
    ('md', ['libmd-dev', 'libmd0'], ['libmd.a', 'libmd.pc', 'headers']),
    ('cmake', ['cmake', 'cmake-data'], ['cmake', 'CMake modules']),
    ('make', ['make'], ['make']),
    ('python-generator', ['python3', 'python3-minimal', 'python3.11', 'python3.11-minimal', 'libpython3.11-stdlib', 'libpython3.11-minimal', 'python3-pyparsing'], ['python3', 'stdlib', 'pyparsing; imports statically reviewed, package contents unverified']),
    ('gmp-assembly-generator', ['m4'], ['m4; GMP arm64 assembly generation, package contents unverified']),
    ('pkg-config', ['pkgconf', 'pkgconf-bin', 'libpkgconf3'], ['pkgconf; explicit executable, no implicit pkg-config alias']),
    ('shell', ['dash', 'bash'], ['sh', 'bash']),
    ('text-and-digest', ['coreutils', 'sed', 'grep', 'gawk', 'findutils', 'diffutils', 'patch'], ['sha256sum', 'sort', 'cp', 'sed', 'grep', 'awk', 'find', 'diff', 'patch']),
    ('archive', ['tar', 'gzip', 'bzip2', 'xz-utils'], ['tar', 'gzip', 'bzip2', 'xz']),
    ('inspection', ['file', 'libmagic1', 'libmagic-mgc'], ['file', 'magic database']),
)


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def read_sdk_record(relative):
    with (ROOT / relative).open('rb') as stream:
        raw = stream.read(2 * 1024 * 1024 + 1)
    if not 0 < len(raw) <= 2 * 1024 * 1024:
        raise ValueError('sdk-record-size-budget')
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('duplicate-sdk-json-key')
            result[key] = item
        return result
    data = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite-sdk-json')))
    if not isinstance(data, dict):
        raise ValueError('sdk-or-review-record-must-be-object')
    return raw, data


def reference(relative, limit=8 * 1024 * 1024):
    if not isinstance(relative, str) or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('unsafe-reviewed-input-path')
    path = ROOT / relative
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError('reviewed-input-type-or-size')
    raw = path.read_bytes()
    return {'path': relative, 'bytes': len(raw), 'raw_digest': digest(raw)}


def reviewed_sources(archives):
    source_path = REVIEW_DIRECTORY + 'source-inputs.json'
    raw, source = read_sdk_record(source_path)
    if (source.get('format') != 'radishaxiom-private-cvc5-c0-source-inputs'
            or source.get('scope') != 'source-byte-static-review-only'
            or source.get('version') != '0.1' or source.get('build_ready') is not False
            or source.get('license_acceptance') != 'not-accepted'
            or source.get('tool_acceptance') != 'not-accepted'
            or source.get('signature_authentication') != 'not-established'
            or source.get('executed_upstream_programs') is not False):
        raise ValueError('source-review-policy-or-acceptance-drift')
    rows = source.get('sources')
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('source-review-component-shape')
    by_id = {row.get('id'): row for row in rows}
    if len(rows) != 5 or set(by_id) != {row['id'] for row in archives}:
        raise ValueError('source-review-component-drift')
    for archive in archives:
        row = by_id[archive['id']]
        actual = reference(row['archive']['path'], archive['max_download_bytes'])
        if actual != row['archive'] or row['selected_commit'] != archive['commit']:
            raise ValueError('source-archive-bytes-or-commit-drift')
        expected_hash = archive['expected_archive_sha256']
        if expected_hash is not None and actual['raw_digest'] != 'sha256:' + expected_hash:
            raise ValueError('source-archive-expected-hash-mismatch')
        for name in ('tree_inventory', 'license_inventory'):
            if reference(row[name]['path']) != row[name]:
                raise ValueError('source-inventory-bytes-drift')
        archive.update(raw_digest=actual['raw_digest'], bytes=actual['bytes'],
            status='obtained-static-reviewed-not-accepted',
            expected_archive_hash_matches=None if expected_hash is None else True,
            observation_scope='retained-archive-and-inventory-consistency-not-signature-or-license-acceptance',
            tree_inventory=row['tree_inventory'], license_inventory=row['license_inventory'],
            retained_git_blob_check=row['cvc5_retained_git_blob_check'])
    return {'path': source_path, 'bytes': len(raw), 'raw_digest': digest(raw)}


def reviewed_configuration():
    production_path = REVIEW_DIRECTORY + 'production-review.json'
    patch_path = REVIEW_DIRECTORY + 'patch-review.json'
    production_raw, production = read_sdk_record(production_path)
    patch_raw, patch = read_sdk_record(patch_path)
    if (production.get('format') != 'radishaxiom-private-cvc5-production-source-review'
            or production.get('version') != '0.1'
            or production.get('status') != 'static-reviewed-not-configured-not-accepted'
            or any(production.get(key) is not False for key in ('build_ready', 'configuration_executed',
                'build_executed', 'probe_executed', 'solver_executed', 'tool_accepted'))
            or production.get('source_input_record') != reference(REVIEW_DIRECTORY + 'source-inputs.json')
            or production.get('new_required_sdk_roots') != ['python3-pyparsing', 'm4']
            or not set(production.get('new_required_sdk_roots', [])) <= {
                name for _, packages, _ in SDK_ITEMS for name in packages}):
        raise ValueError('production-review-policy-or-acceptance-drift')
    if (patch.get('format') != 'radishaxiom-cvc5-build-patch-review' or patch.get('version') != '0.1'
            or patch.get('patch_state') != 'prepared-static-candidate-not-executed'
            or patch.get('build_ready') is not False or patch.get('acceptance') != 'not-accepted'
            or patch.get('scope') != 'static-text-review-only-not-configure-or-build'
            or patch.get('upstream_commit') != COMMIT
            or patch.get('executed') != ['self-authored Python text inventory/diff/exact-application',
                                        'host git apply --check (text only)']
            or patch.get('not_executed') != ['upstream scripts', 'CMake', 'Make', 'autotools',
                                           'compiler', 'solver', 'probe']
            or patch.get('actual_dependency_manifest') is not None
            or patch.get('actual_sdk_archive_inputs') is not None
            or reference(patch['patch']['path']) != patch['patch']):
        raise ValueError('patch-review-policy-or-bytes-drift')
    return ({'path': production_path, 'bytes': len(production_raw), 'raw_digest': digest(production_raw)},
            {'path': patch_path, 'bytes': len(patch_raw), 'raw_digest': digest(patch_raw)}, patch['patch'])


def generate():
    indexes, observations = [], []
    for rel, retained in SOURCE_INDEXES:
        raw = (ROOT / rel).read_bytes()
        data = json.loads(raw)
        indexes.append({'path': rel, 'bytes': len(raw), 'raw_digest': digest(raw)})
        for row in data['sources']:
            original = (ROOT / retained / row['file']).read_bytes()
            if digest(original) != row['raw_digest'] or len(original) != row['bytes']:
                raise ValueError('retained observation mismatch: ' + row['file'])
            observations.append({'index': rel, 'file': retained + '/' + row['file'], 'url': row['url'], 'bytes': len(original), 'raw_digest': digest(original), 'role': row['role']})
    recipes = json.loads((ROOT / SOURCE_INDEXES[1][0]).read_text())['archive_download']['archives']
    commits = {'cadical': json.loads((ROOT / '.tmp/solver-cli-licenses-2026-10-17/cadical-commit.json').read_text())['sha'],
               'libpoly': json.loads((ROOT / '.tmp/solver-cli-licenses-2026-10-17/libpoly-commit.json').read_text())['sha'],
               'symfpu': '227a7246b8ce513b393cc2645d6d65d3490ea1de', 'gmp': None}
    cvc5 = json.loads((ROOT / '.tmp/solver-cli-licenses-2026-10-17/cvc5-commit.json').read_text())['sha']
    if cvc5 != COMMIT:
        raise ValueError('cvc5 commit drift')
    archives = [{'id': 'cvc5', 'version': '1.3.4', 'commit': COMMIT, 'selection': 'selected', 'url': 'https://github.com/cvc5/cvc5/archive/' + COMMIT + '.tar.gz', 'expected_archive_sha256': None, 'expected_hash_basis': 'not-published-in-retained-material', 'raw_digest': None, 'bytes': None, 'status': 'not-obtained', 'license_acceptance': 'not-accepted', 'max_download_bytes': 67108864}]
    for row in recipes:
        archives.append({'id': row['component'], 'version': row.get('version'), 'commit': commits[row['component']], 'selection': 'selected', 'url': row['recipe_url'], 'expected_archive_sha256': row['archive_sha256'], 'expected_hash_basis': 'pinned-cvc5-Find-module-declaration-not-recomputed', 'raw_digest': None, 'bytes': None, 'status': 'not-obtained', 'license_acceptance': 'not-accepted', 'max_download_bytes': 33554432})
    source_review = reviewed_sources(archives)
    production_review, patch_review, patch_reference = reviewed_configuration()
    sdk_path = 'docs/records/solver-cvc5-c0-2026-10-17/sdk-selection.json'
    observations_path = 'docs/records/solver-cvc5-c0-2026-10-17/metadata-observations.json'
    sdk_raw, sdk_result = read_sdk_record(sdk_path)
    metadata_raw, _ = read_sdk_record(observations_path)
    if (sdk_result['format'] != 'radishaxiom-private-cvc5-c0-sdk-selection' or sdk_result['version'] != '0.1'
            or sdk_result['selection'] != 'exact-metadata-only' or sdk_result['base_url'] != SNAPSHOT
            or sdk_result['build_ready'] is not False or sdk_result['signature_verified'] is not False
            or sdk_result['metadata_authentication'] != 'not-established'):
        raise ValueError('sdk-result-format-policy-or-acceptance-drift')
    groups = [{'id': ident, 'package_names': packages} for ident, packages, _ in SDK_ITEMS]
    if sdk_result['root_groups'] != groups:
        raise ValueError('sdk-root-role-drift')
    selected_items = [{'id': ident, 'selection': 'exact-metadata-roots-selected-contents-unverified',
        'selected_package_names': packages, 'required_roles_not_verified_package_contents': files,
        'package_contents_acceptance': 'not-accepted', 'license_acceptance': 'not-accepted'}
        for ident, packages, files in SDK_ITEMS]
    sdk_reference = {'path': sdk_path, 'bytes': len(sdk_raw), 'raw_digest': digest(sdk_raw),
                     'format': sdk_result['format'], 'version': sdk_result['version']}
    metadata_reference = {'path': observations_path, 'bytes': len(metadata_raw), 'raw_digest': digest(metadata_raw)}
    return {'format': 'radishaxiom-private-cvc5-c0-input-selection', 'version': '0.3', 'observation_date': '2026-10-17', 'generator': 'scripts/generate-cvc5-c0-input-selection.py', 'generator_identity': {'path': 'scripts/generate-cvc5-c0-input-selection.py', 'bytes': Path(__file__).stat().st_size, 'raw_digest': digest(Path(__file__).read_bytes())}, 'scope': 'candidate-selection-only-no-acceptance', 'c0_state': 'static-reviewed-blocked-on-sdk-content-effective-configuration-and-acceptance', 'executable': False, 'build_ready': False, 'original_cli_acceptance': 'not-accepted', 'new_payload_acceptance': 'not-accepted', 'source_indexes': indexes, 'rechecked_retained_observations': observations, 'source_archives': archives, 'source_review_record': source_review,
        'sdk': {'selection': 'exact-metadata-only', 'distribution': 'Debian 12 bookworm', 'snapshot': '20230612T000000Z', 'architecture': 'arm64', 'base_url': SNAPSHOT, 'snapshot_availability': 'observed-for-four-retained-metadata-targets', 'metadata_authentication': 'not-established', 'package_dependency_closure': 'closed-for-declared-roots-and-essential-metadata-only', 'package_contents_acceptance': 'not-accepted', 'recursive_guest_rebuild': False, 'binary_sdk_trust': 'proposed-not-accepted', 'selection_record': sdk_reference, 'metadata_record': metadata_reference, 'closure_summary': sdk_result['summary'], 'closure_scope': sdk_result['dependency_policy']['resolution_scope'], 'metadata_targets': [SNAPSHOT + 'dists/bookworm/' + p for p in ('InRelease', 'Release', 'main/binary-arm64/Packages.xz', 'main/source/Sources.xz')], 'items': selected_items},
        'metadata_acquisition': {'authorized': True, 'scope': 'fixed-snapshot Release/InRelease/Packages/Sources metadata only', 'record': metadata_reference},
        'metadata_observation_history': [{'url': SNAPSHOT+'dists/bookworm/Release', 'method': 'sandbox Python urllib HTTPS GET', 'result': 'URLError: [Errno 1] Operation not permitted', 'bytes_obtained': 0, 'raw_digest': None}, {'url': SNAPSHOT+'dists/bookworm/', 'method': 'metadata-only escalated Python urllib for Release/Packages/Sources', 'result': 'approval-waiting call interrupted after 1062.0 seconds; no successful execution output; target directory absent on local recheck', 'bytes_obtained': 0, 'raw_digest': None}, {'url': 'https://packages.debian.org/bookworm/g%2B%2B-12', 'method': 'web open rendered official metadata page', 'result': 'page reports 12.2.0-14+deb12u1; current page is not selected snapshot metadata and is not used as package selection evidence', 'bytes_obtained': None, 'raw_digest': None}],
        'configuration': {'production_expansion': 'static-reviewed-not-configured', 'production_review_record': production_review, 'source_patch': patch_reference, 'patch_review_record': patch_review, 'patch_status': 'prepared-static-candidate-not-executed', 'bindings': 'CLI-only candidate; Java/Python bindings explicitly disabled in static review; required Python interpreter/pyparsing retained; no JDK selected', 'feature_requirements': ['Production', 'static-glibc', 'non-GPL', 'Editline', 'Poly', 'GMP/GMPXX', 'CaDiCaL', 'SymFPU'], 'optional_features': 'statically-reviewed-candidate-overrides; effective-dynamic-configuration-unverified', 'auto_download': False},
        'future_acquisition': {'source_archive_acquisition_authorized': False, 'sdk_package_acquisition_authorized': False, 'source_correspondence_acquisition_authorized': False, 'further_metadata_acquisition_authorized': False, 'retention_directory': '.tmp/cvc5-c0-acquisition-2026-10-17', 'source_archive_max_total_bytes': sum(row['max_download_bytes'] for row in archives), 'metadata_max_total_bytes': 29360128, 'sdk_package_max_total_bytes': 536870912, 'source_correspondence_max_total_bytes': 1073741824, 'estimated_network_minutes': [10, 30], 'sdk_package_index_declared_total_bytes': sdk_result['summary']['binary_declared_bytes'], 'source_correspondence_index_declared_total_bytes': sdk_result['summary']['source_declared_bytes'], 'estimate_basis': 'caps remain planning limits; exact declared sizes now summed from metadata, not package observations or acceptance', 'timeout_seconds_per_item': 180, 'retries': 0, 'source_fallbacks': 0, 'cleanup': 'future exact acquired paths only; preserve original ZIP and prior evidence; no cleanup authorized'},
        'blockers': ['snapshot signature trust and historical validity policy not accepted', 'exact metadata binary/source selection is not obtained package contents or copyright acceptance', 'declared package runtime metadata closure is not verified package contents or a runtime filesystem', 'static Production/options/import review and text patch are not executed effective configuration or generator compatibility', 'SDK binary/corresponding-source bytes and file inventories not obtained', '.pc static closure, actual library/header hashes and link map not created', 'LibPoly Debian copyright label/body conflict and GMP multi-license scope require acceptance', 'local source/license/configuration delta/trusted SDK acceptance not decided']}


def main():
    value = generate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print('generated', OUTPUT.relative_to(ROOT), 'C0 blocked; no acceptance')


if __name__ == '__main__':
    main()
