#!/usr/bin/env python3
"""Generate the private, blocked C0 selection record from retained observations.

No network, package resolution, installation, or build is performed. This entry
contains reviewed selection decisions; it never promotes them to acceptance.
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
SDK_ITEMS = (
    ('compiler', ['gcc-12', 'g++-12', 'cpp-12', 'gcc-12-base'], ['gcc', 'g++', 'cpp']),
    ('binutils', ['binutils', 'binutils-aarch64-linux-gnu', 'binutils-common'], ['as', 'ld.bfd', 'ar', 'ranlib', 'strip', 'readelf', 'nm', 'objdump']),
    ('gcc-runtime', ['libgcc-12-dev', 'libstdc++-12-dev', 'libgcc-s1', 'libstdc++6'], ['crtbegin.o', 'crtend.o', 'libgcc.a', 'libgcc_eh.a', 'libstdc++.a']),
    ('glibc-sysroot', ['libc6', 'libc6-dev', 'libc-dev-bin', 'linux-libc-dev'], ['crt1.o', 'crti.o', 'crtn.o', 'libc.a', 'libm.a', 'libpthread.a', 'libdl.a', 'librt.a', 'headers']),
    ('editline', ['libedit-dev', 'libedit2'], ['histedit.h', 'libedit.a', 'libedit.pc']),
    ('terminfo', ['libncurses-dev', 'libtinfo6'], ['libtinfo.a', 'tinfo.pc', 'headers']),
    ('bsd', ['libbsd-dev', 'libbsd0'], ['libbsd.a', 'libbsd.pc', 'headers']),
    ('md', ['libmd-dev', 'libmd0'], ['libmd.a', 'libmd.pc', 'headers']),
    ('cmake', ['cmake', 'cmake-data'], ['cmake', 'CMake modules']),
    ('make', ['make'], ['make']),
    ('python-generator', ['python3', 'python3-minimal', 'python3.11', 'python3.11-minimal', 'libpython3.11-stdlib', 'libpython3.11-minimal'], ['python3', 'stdlib; additional imported modules unresolved']),
    ('pkg-config', ['pkgconf', 'pkgconf-bin', 'libpkgconf3'], ['pkgconf; explicit executable, no implicit pkg-config alias']),
    ('shell', ['dash', 'bash'], ['sh', 'bash']),
    ('text-and-digest', ['coreutils', 'sed', 'grep', 'gawk', 'findutils', 'diffutils', 'patch'], ['sha256sum', 'sort', 'cp', 'sed', 'grep', 'awk', 'find', 'diff', 'patch']),
    ('archive', ['tar', 'gzip', 'bzip2', 'xz-utils'], ['tar', 'gzip', 'bzip2', 'xz']),
    ('inspection', ['file', 'libmagic1', 'libmagic-mgc'], ['file', 'magic database']),
)


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


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
    unresolved = []
    for ident, packages, files in SDK_ITEMS:
        unresolved.append({'id': ident, 'selection': 'unresolved', 'candidate_package_names_not_verified_in_snapshot': packages, 'required_roles_not_verified_package_contents': files, 'version': None, 'architecture': 'arm64-or-all', 'package_url': None, 'source_package': None, 'source_urls': [], 'index_declared_sha256': None, 'raw_digest': None, 'bytes': None, 'license_acceptance': 'not-accepted', 'blocker': 'snapshot-index-not-obtained; exact version/file/closure/copyright unresolved'})
    return {'format': 'radishaxiom-private-cvc5-c0-input-selection', 'version': '0.1', 'observation_date': '2026-10-17', 'generator': 'scripts/generate-cvc5-c0-input-selection.py', 'scope': 'candidate-selection-only-no-acceptance', 'c0_state': 'blocked-exact-sdk-and-config-unresolved', 'executable': False, 'build_ready': False, 'original_cli_acceptance': 'not-accepted', 'new_payload_acceptance': 'not-accepted', 'source_indexes': indexes, 'rechecked_retained_observations': observations, 'source_archives': archives,
        'sdk': {'selection': 'selected-distribution-snapshot-only', 'distribution': 'Debian 12 bookworm', 'snapshot': '20230612T000000Z', 'architecture': 'arm64', 'base_url': SNAPSHOT, 'snapshot_availability': 'unverified', 'metadata_authentication': 'not-established', 'package_dependency_closure': 'not-established', 'recursive_guest_rebuild': False, 'binary_sdk_trust': 'proposed-not-accepted', 'metadata_targets': [SNAPSHOT + 'dists/bookworm/' + p for p in ('InRelease', 'Release', 'main/binary-arm64/Packages.xz', 'main/source/Sources.xz')], 'items': unresolved},
        'metadata_observations': [{'url': SNAPSHOT+'dists/bookworm/Release', 'method': 'sandbox Python urllib HTTPS GET', 'result': 'URLError: [Errno 1] Operation not permitted', 'bytes_obtained': 0, 'raw_digest': None}, {'url': SNAPSHOT+'dists/bookworm/', 'method': 'metadata-only escalated Python urllib for Release/Packages/Sources', 'result': 'approval-waiting call interrupted after 1062.0 seconds; no successful execution output; target directory absent on local recheck', 'bytes_obtained': 0, 'raw_digest': None}, {'url': 'https://packages.debian.org/bookworm/g%2B%2B-12', 'method': 'web open rendered official metadata page', 'result': 'page reports 12.2.0-14+deb12u1; current page is not selected snapshot metadata and is not used as package selection evidence', 'bytes_obtained': None, 'raw_digest': None}],
        'configuration': {'production_expansion': 'unresolved-not-obtained', 'source_patch': None, 'patch_status': 'not-created-without-full-source', 'bindings': 'CLI-only intended; Python interpreter retained; Java effect unresolved; no JDK selected', 'feature_requirements': ['Production', 'static-glibc', 'non-GPL', 'Editline', 'Poly', 'GMP/GMPXX', 'CaDiCaL', 'SymFPU'], 'optional_features': 'unresolved-fixed-Production-expansion-required', 'auto_download': False},
        'future_acquisition': {'authorized': False, 'retention_directory': '.tmp/cvc5-c0-acquisition-2026-10-17', 'source_archive_max_total_bytes': sum(row['max_download_bytes'] for row in archives), 'metadata_max_total_bytes': 29360128, 'sdk_package_max_total_bytes': 536870912, 'source_correspondence_max_total_bytes': 1073741824, 'estimated_network_minutes': [10, 30], 'estimate_basis': 'planning cap, not observed sizes; exact package sizes must be summed from accepted metadata before requesting bytes', 'timeout_seconds_per_item': 180, 'retries': 0, 'source_fallbacks': 0, 'cleanup': 'future exact acquired paths only; preserve original ZIP and prior evidence; no cleanup authorized'},
        'blockers': ['signed snapshot metadata and signature trust not obtained', 'SDK exact binary versions/filenames/sizes/digests/source and copyright mappings unresolved', 'build-tool runtime package closure unresolved; no entire guest chosen', 'full cvc5 source/embedded components/Production expansion/CLI generation imports unresolved', 'actual source and SDK package bytes/tree digests not obtained', 'build patch bytes, SDK file inventories, .pc static closure and link map not created', 'configuration delta and local license/trusted SDK acceptance not decided']}


def main():
    value = generate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print('generated', OUTPUT.relative_to(ROOT), 'C0 blocked; no acceptance')


if __name__ == '__main__':
    main()
