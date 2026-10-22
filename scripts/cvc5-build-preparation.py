#!/usr/bin/env python3
"""Prepare/check the fixed C1 acquisition plan and audit raw inputs offline.

This downstream C0 consumer has no fetch, extraction, installation or execution
mode. Matching archive bytes never grant input, tool or build acceptance.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / 'docs/records/solver-cvc5-c1-2026-10-22'
PLAN = RECORDS / 'acquisition-plan.json'
C0 = 'docs/records/solver-cvc5-c0-2026-10-17/'
REVIEW = 'docs/records/solver-cvc5-source-review-2026-10-17/'
BASE = 'https://snapshot.debian.org/archive/debian/20230612T000000Z/'
RETAINED = '.tmp/cvc5-c1-acquisition-2026-10-22'
LIMIT = 2 * 1024 * 1024
BLOCK = 1024 * 1024


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECK = load_module('check-cvc5-c0-input-selection')
SDK = load_module('cvc5-c0-sdk-selection')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def read_record(path):
    require(path.is_file() and not path.is_symlink(), 'record-not-regular-file')
    with path.open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    require(0 < len(raw) <= LIMIT, 'record-size-budget')
    return raw, json.loads(raw, object_pairs_hook=CHECK.reject_duplicates,
                           parse_constant=CHECK.reject_constant)


def reference(relative):
    path = ROOT / relative
    require(path.resolve() == path and path.is_file(), 'noncanonical-reference')
    raw = path.read_bytes()
    return {'path': relative, 'bytes': len(raw),
            'raw_digest': 'sha256:' + hashlib.sha256(raw).hexdigest()}


def entry(kind, url, size, sha, owner):
    require(isinstance(url, str) and url.startswith(BASE), 'outside-fixed-snapshot')
    relative = SDK.safe_pool_path(url[len(BASE):])
    require(type(size) is int and 0 < size <= 1024 * 1024 * 1024, 'invalid-declared-size')
    require(isinstance(sha, str) and re.fullmatch('[0-9a-f]{64}', sha), 'invalid-declared-hash')
    return {'kind': kind, 'url': url, 'relative_path': 'inputs/' + relative,
            'declared_bytes': size, 'declared_sha256': sha, 'owners': [owner]}


def acquisition_entries(sdk):
    """Project the existing selection; do not resolve a second package set."""
    require(sdk['base_url'] == BASE and sdk['selection'] == 'exact-metadata-only'
            and sdk['signature_verified'] is False and sdk['build_ready'] is False
            and sdk['tool_acceptance'] == 'not-accepted', 'sdk-boundary-drift')
    entries, seen_packages = {}, set()
    for row in sdk['packages']:
        require(row['Package'] not in seen_packages, 'duplicate-binary-package')
        seen_packages.add(row['Package'])
        require(row['Architecture'] in ('arm64', 'all') and row['bytes'] is None
                and row['raw_digest'] is None and row['package_status'] == 'not-obtained',
                'binary-status-or-architecture-drift')
        require(row['package_url'] == BASE + row['Filename'], 'binary-url-path-mismatch')
        owner = {'package': row['Package'], 'version': row['Version'],
                 'architecture': row['Architecture'], 'source_package': row['source_package'],
                 'source_version': row['source_version']}
        item = entry('binary', row['package_url'], row['Size'], row['SHA256'], owner)
        require(item['url'] not in entries, 'duplicate-binary-url')
        entries[item['url']] = item
    seen_sources = set()
    for row in sdk['source_packages']:
        key = (row['Package'], row['Version'])
        require(key not in seen_sources, 'duplicate-source-identity')
        seen_sources.add(key)
        owner = {'package': key[0], 'version': key[1]}
        seen_files = set()
        for file in row['files']:
            require(file['kind'] in ('dsc', 'orig', 'debian-patch', 'native-source')
                    and file['bytes'] is None and file['raw_digest'] is None
                    and file['status'] == 'not-obtained', 'source-status-or-kind-drift')
            require(file['url'] == BASE + row['Directory'] + '/' + file['filename']
                    and file['url'] not in seen_files, 'source-url-or-duplicate-file')
            seen_files.add(file['url'])
            item = entry(file['kind'], file['url'], file['size'], file['sha256'], owner)
            if item['url'] in entries:
                previous = entries[item['url']]
                require(all(previous[k] == item[k] for k in item if k != 'owners'),
                        'conflicting-shared-source-file')
                previous['owners'].append(owner)
            else:
                entries[item['url']] = item
    require(all((p['source_package'], p['source_version']) in seen_sources
                for p in sdk['packages']), 'missing-corresponding-source')
    rows = sorted(entries.values(), key=lambda row: (row['kind'] != 'binary', row['relative_path']))
    binary = [row for row in rows if row['kind'] == 'binary']
    source = [row for row in rows if row['kind'] != 'binary']
    summary = {'binary_files': len(binary), 'source_files': len(source),
               'source_versions': len(seen_sources), 'total_files': len(rows),
               'binary_bytes': sum(row['declared_bytes'] for row in binary),
               'source_bytes': sum(row['declared_bytes'] for row in source)}
    summary['total_bytes'] = summary['binary_bytes'] + summary['source_bytes']
    expected = sdk['summary']
    for ours, theirs in (('binary_files', 'packages'), ('source_files', 'unique_source_files'),
                        ('source_versions', 'source_packages'),
                        ('binary_bytes', 'binary_declared_bytes'), ('source_bytes', 'source_declared_bytes')):
        require(summary[ours] == expected[theirs], 'selection-summary-mismatch:' + ours)
    require(summary['binary_bytes'] <= 512 * 1024**2
            and summary['source_bytes'] <= 1024**3, 'existing-acquisition-budget-exceeded')
    return rows, summary


def review_retained_gaps():
    """Locate factual gaps in retained bytes; do not decide legal/trust policy."""
    _, source = read_record(ROOT / REVIEW / 'source-inputs.json')
    poly = next(row for row in source['sources'] if row['id'] == 'libpoly')
    _, tree = read_record(ROOT / poly['tree_inventory']['path'])
    entries = {row['path']: row for row in tree['entries'] if row['kind'] == 'file'}
    names = ('LICENCE', 'debian/copyright', 'include/poly.h', 'CMakeLists.txt',
             'src/CMakeLists.txt', 'include/CMakeLists.txt')
    refs = []
    for name in names:
        ref = reference(poly['source_root'] + '/' + name)
        original = entries[tree['top'] + '/' + name]
        require(ref['bytes'] == original['bytes']
                and ref['raw_digest'] == 'sha256:' + original['sha256'], 'libpoly-review-byte-drift')
        refs.append(ref)
    copyright_text = (ROOT / poly['source_root'] / 'debian/copyright').read_text()
    require('License: GPL-3+' in copyright_text and 'GNU Lesser General Public License' in copyright_text,
            'libpoly-conflict-observation-drift')
    _, metadata = read_record(ROOT / C0 / 'metadata-observations.json')
    old_record = 'docs/records/linux-builder-source-chain/release-verification.json'
    _, historical = read_record(ROOT / old_record)
    keyring = base64.b64decode(historical['keyring']['base64'], validate=True)
    key_hash = hashlib.sha256(keyring).hexdigest()
    require(len(keyring) == 55918
            and key_hash == historical['keyring']['sha256']
            == '506b815cbb32d9b6066b4a2aa524071e071761e7e7f68c3ac74f3061ba852017',
            'retained-keyring-byte-drift')
    require(historical['inrelease_sha256'] != next(row['raw_digest'].removeprefix('sha256:')
                for row in metadata['observations'] if row['relative_path'] == 'InRelease'),
            'historical-signature-target-confusion')
    return {
        'libpoly': {'input_files': refs, 'observation': 'GPL-3+ label conflicts with Lesser body',
                    'decision': 'pending-scoped-license-review; conflict-not-erased'},
        'snapshot_release_fields': metadata['release_fields'],
        'retained_keyring_candidate': {'source_record': reference(old_record),
            'decoded_bytes': len(keyring), 'decoded_sha256': key_hash,
            'historical_target_differs': True,
            'trust_for_this_task': 'not-accepted', 'current_signature_verified': False},
        'verifier_reuse_candidate': reference(
            'docs/records/rust-linux-input-review/musl-verifier-smoke-execution-2026-09-12.md'),
        'verifier_reuse_scope': 'historical evidence only; no daemon inspection or execution; new task requires explicit trust/scope review',
    }


def generate():
    raw, _ = read_record(ROOT / C0 / 'input-selection.json')
    CHECK.check(raw)  # Reuses the existing C0 and SDK checks, including retained metadata.
    _, sdk = read_record(ROOT / C0 / 'sdk-selection.json')
    rows, summary = acquisition_entries(sdk)
    return {
        'format': 'radishaxiom-private-cvc5-c1-acquisition-plan', 'version': '0.1',
        'generator': 'python3 scripts/cvc5-build-preparation.py generate',
        'inputs': [reference(path) for path in (
            'scripts/cvc5-build-preparation.py', C0 + 'input-selection.json',
            C0 + 'sdk-selection.json', C0 + 'metadata-observations.json',
            REVIEW + 'source-inputs.json', REVIEW + 'production-review.json',
            REVIEW + 'patch-review.json', 'patches/cvc5/1.3.4/explicit-inputs.patch')],
        'scope': 'raw-package-acquisition-for-review-only',
        'retained_gap_review': review_retained_gaps(),
        'authorization': 'pending-current-task-confirmation',
        'retention_directory': RETAINED,
        'summary': summary,
        'transport_policy': {
            'initial_url_prefix': BASE, 'https_only': True,
            'redirects': 'only observed same-host /file/<40-lowercase-hex>/<single-safe-name>; maximum 5; hash remains SHA256 from this plan',
            'concurrency': 1, 'retries': 0, 'fallback_sources': 0,
            'per_item_deadline_seconds': 180, 'batch_deadline_seconds': 5400,
            'response_body_byte_limit': summary['total_bytes'],
            'log_byte_limit': 8 * 1024 * 1024, 'minimum_free_bytes': 1024**3,
            'directory_policy': 'new exact batch directory only; no overwrite or implicit resume',
            'per_file_byte_limit': 'exact declared_bytes; size/hash mismatch stops entire batch',
            'failure': 'retain partial bytes and observations; no automatic restart or resume',
        },
        'entries': rows,
        'signature_verified': False, 'license_acceptance': 'not-accepted',
        'input_acceptance': 'not-accepted', 'build_ready': False,
        'not_included': ['trust-anchor retrieval', 'signature-verifier installation/execution',
                         'archive extraction', 'maintainer scripts', 'SDK assembly/install',
                         'CMake/configure/pkg-config/compiler/generator execution',
                         'container/VM', 'solver/probe execution', 'distribution'],
        'remaining_gates': ['LibPoly conflict scope decision',
                            'independently authenticated keyring and historical signature policy',
                            'SDK file inventory and source/patch/copyright review',
                            'explicit trusted compiler/linker/SDK acceptance',
                            'actual static closure, headers/libraries and ABI review',
                            'effective configuration and separate build/run authorizations'],
    }


def verify_plan(path=PLAN):
    _, actual = read_record(path)
    require(CHECK.same_typed(actual, generate()), 'acquisition-plan-drift')
    return actual


def canonical_directory(path):
    require(path.is_absolute() and path.resolve() == path and path.is_dir(),
            'input-root-missing-or-noncanonical')
    require(not path.is_symlink(), 'input-root-symlink')


def audit_archives(plan, directory):
    """Read raw bytes only. Inputs may be absent; corrupt/extra inputs fail closed.

    The directory is an immutable review snapshot, not an adversarial concurrent
    writer boundary. No resulting record is an execution authorization token.
    """
    canonical_directory(directory)
    expected = {row['relative_path']: row for row in plan['entries']}
    require(len(expected) == len(plan['entries']), 'duplicate-retained-path')
    require(len(expected) <= 17408, 'input-entry-budget')
    allowed_dirs = {'inputs'}
    for relative in expected:
        require(relative.startswith('inputs/'), 'input-path-outside-tree')
        SDK.safe_pool_path(relative[len('inputs/'):])
        allowed_dirs.update(str(p) for p in Path(relative).parents if str(p) != '.')
    inputs = directory / 'inputs'
    found = set()
    if inputs.exists() or inputs.is_symlink():
        require(inputs.is_dir() and not inputs.is_symlink(), 'inputs-not-regular-directory')
        todo = [inputs]
        visited = 0
        while todo:
            current = todo.pop()
            for path in current.iterdir():
                visited += 1
                require(visited <= len(expected) + len(allowed_dirs), 'input-tree-count-budget')
                relative = path.relative_to(directory).as_posix()
                mode = path.lstat().st_mode
                require(not stat.S_ISLNK(mode), 'input-symlink:' + relative)
                if stat.S_ISDIR(mode):
                    require(relative in allowed_dirs, 'extra-input-directory:' + relative)
                    todo.append(path)
                else:
                    require(stat.S_ISREG(mode) and relative in expected, 'extra-or-special-input:' + relative)
                    found.add(relative)
    matched, missing = [], []
    for relative, row in expected.items():
        if relative not in found:
            missing.append(relative)
            continue
        path = directory / relative
        size = row['declared_bytes']
        require(type(size) is int and 0 < size <= 1024**3, 'input-size-budget')
        require(path.stat().st_size == size, 'input-size-mismatch:' + relative)
        hasher, count = hashlib.sha256(), 0
        with path.open('rb') as stream:
            while data := stream.read(min(BLOCK, size - count + 1)):
                count += len(data)
                require(count <= size, 'input-grew-during-read:' + relative)
                hasher.update(data)
        require(count == size and hasher.hexdigest() == row['declared_sha256'],
                'input-digest-mismatch:' + relative)
        matched.append(relative)
    return {'scope': 'raw-archive-integrity-only', 'matched_files': len(matched),
            'missing_files': missing, 'archive_bytes_complete': not missing,
            'signature_verified': False, 'input_acceptance': 'not-accepted',
            'build_ready': False, 'executable': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('generate', 'verify', 'audit-archives'))
    parser.add_argument('--directory', type=Path,
                        help='Existing raw acquisition directory; audit-archives only')
    args = parser.parse_args()
    require(args.directory is None or args.action == 'audit-archives', 'unused-directory-argument')
    if args.action == 'generate':
        value = generate()
        raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
        RECORDS.mkdir(parents=True, exist_ok=True)
        if PLAN.exists():
            require(PLAN.read_bytes() == raw, 'existing-plan-differs-refuse-overwrite')
        else:
            with PLAN.open('xb') as stream:
                stream.write(raw)
    else:
        value = verify_plan()
    if args.action == 'audit-archives':
        result = audit_archives(value, args.directory or ROOT / RETAINED)
        print(json.dumps(result, indent=2))
        return 0 if result['archive_bytes_complete'] else 2
    print(json.dumps(dict(value['summary'], plan_consistent=True, build_ready=False,
                          signature_verified=False, authorization=value['authorization']), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
