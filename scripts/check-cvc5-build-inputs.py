#!/usr/bin/env python3
"""Offline byte preflight for the existing private C0 build-input manifest.

No CMake, compiler, pkg-config or third-party program is invoked. The external
review declaration is checked for binding, not independently established.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cvc5_c0_check', ROOT / 'scripts/check-cvc5-c0-input-selection.py')
CHECK = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CHECK)
COMMIT = 'f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341'
TARGET = 'linux-aarch64-le-glibc-gcc12'
VERSIONS = {'gmp': '6.3.0', 'poly': '0.2.1', 'cadical': 'rel-2.1.3-elevate',
            'symfpu': '227a7246b8ce513b393cc2645d6d65d3490ea1de'}
HEADERS = {'gmp': {'gmp.h'}, 'gmpxx': {'gmpxx.h'},
           'cadical': {'cadical/cadical.hpp', 'cadical/tracer.hpp'},
           'poly': {'poly/poly.h', 'poly/version.h'},
           'symfpu': {'symfpu/core/unpackedFloat.h'}, 'editline': {'histedit.h'}}
CORE_ARCHIVES = {'gmp', 'gmpxx', 'cadical', 'poly', 'polyxx'}
BINDINGS = ('upstream_commit', 'target_abi', 'versions', 'archives', 'header_roots', 'editline_link_order')
ROOT_KEYS = set(BINDINGS) | {'format', 'version', 'review_state', 'closure_review'}
JSON_LIMIT = 8 * 1024 * 1024
FILE_LIMIT = 1024**3
TOTAL_LIMIT = 4 * 1024**3
ENTRY_LIMIT = 100000


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def keys(value, expected, reason):
    require(isinstance(value, dict) and set(value) == expected, reason)


def path_value(value, directory=False):
    require(isinstance(value, str) and re.fullmatch('/[A-Za-z0-9_./+@=-]+', value)
            and value != '/', 'noncanonical-input-path')
    path = Path(value)
    require(path.as_posix() == value and not any(part in ('.', '..') for part in value.split('/'))
            and path.resolve() == path and not path.is_symlink(), 'noncanonical-or-symlink-input')
    mode = path.stat().st_mode
    require(stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode), 'input-file-type')
    return path


def relative_value(value):
    require(isinstance(value, str) and re.fullmatch('[A-Za-z0-9_./+@=-]+', value), 'unsafe-header-path')
    path = PurePosixPath(value)
    require(not path.is_absolute() and str(path) == value
            and not any(part in ('', '.', '..') for part in value.split('/')), 'unsafe-header-path')
    return value


def hash_value(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'invalid-sha256')


def read_json(path):
    with path.open('rb') as stream:
        raw = stream.read(JSON_LIMIT + 1)
    require(0 < len(raw) <= JSON_LIMIT, 'json-size-budget')
    value = json.loads(raw, object_pairs_hook=CHECK.reject_duplicates,
                       parse_constant=CHECK.reject_constant)
    require(isinstance(value, dict), 'json-must-be-object')
    return raw, value


def verify_file(path, row, budget):
    require(type(row.get('bytes')) is int and 0 < row['bytes'] <= FILE_LIMIT, 'file-size-budget')
    hash_value(row.get('sha256'))
    budget['bytes'] += row['bytes']
    budget['files'] += 1
    require(budget['bytes'] <= TOTAL_LIMIT and budget['files'] <= ENTRY_LIMIT, 'total-input-budget')
    path = path_value(str(path))
    require(path.stat().st_size == row['bytes'], 'file-size-mismatch:' + str(path))
    hasher, count = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while data := stream.read(min(1024 * 1024, row['bytes'] - count + 1)):
            count += len(data)
            require(count <= row['bytes'], 'file-grew-during-read')
            hasher.update(data)
    require(count == row['bytes'] and hasher.hexdigest() == row['sha256'], 'file-hash-mismatch:' + str(path))


def header_inventory(root, budget):
    actual, todo = set(), [root]
    while todo:
        current = todo.pop()
        for path in current.iterdir():
            budget['entries'] += 1
            require(budget['entries'] <= ENTRY_LIMIT, 'header-tree-entry-budget')
            mode = path.lstat().st_mode
            require(not stat.S_ISLNK(mode), 'header-tree-symlink')
            relative = relative_value(path.relative_to(root).as_posix())
            if stat.S_ISDIR(mode):
                todo.append(path)
            else:
                require(stat.S_ISREG(mode), 'header-tree-special-file')
                actual.add(relative)
    return actual


def check(path, expected_sha256):
    hash_value(expected_sha256)
    path = path_value(str(path))
    raw, value = read_json(path)
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, 'manifest-hash-mismatch')
    keys(value, ROOT_KEYS, 'manifest-root-fields')
    require(value['format'] == 'radishaxiom-cvc5-private-build-inputs' and value['version'] == '0.1'
            and value['upstream_commit'] == COMMIT and value['target_abi'] == TARGET
            and value['review_state'] == 'reviewed-for-configuration', 'manifest-identity-or-review-state')
    require(CHECK.same_typed(value['versions'], VERSIONS), 'source-version-mismatch')
    budget = {'files': 0, 'bytes': 0, 'entries': 0}
    closure = value['closure_review']
    keys(closure, {'path', 'bytes', 'sha256'}, 'closure-reference-fields')
    closure_path = path_value(closure['path'])
    require(type(closure['bytes']) is int and 0 < closure['bytes'] <= JSON_LIMIT, 'closure-size-budget')
    verify_file(closure_path, closure, budget)
    closure_raw, review = read_json(closure_path)
    require(hashlib.sha256(closure_raw).hexdigest() == closure['sha256'], 'closure-changed-during-read')
    require(review.get('review_state') == 'static-closure-and-abi-reviewed', 'closure-review-state')
    for field in BINDINGS:
        require(CHECK.same_typed(review.get(field), value[field]), 'closure-binding-mismatch:' + field)
    keys(value['header_roots'], set(HEADERS), 'header-role-set')
    for role, required in HEADERS.items():
        item = value['header_roots'][role]
        keys(item, {'path', 'files'}, 'header-root-fields')
        root = path_value(item['path'], directory=True)
        rows = item['files']
        require(isinstance(rows, list) and 0 < len(rows) <= ENTRY_LIMIT, 'header-list-budget')
        expected = set()
        for row in rows:
            keys(row, {'path', 'bytes', 'sha256'}, 'header-file-fields')
            relative = relative_value(row['path'])
            require(relative not in expected, 'duplicate-header-path')
            expected.add(relative)
            verify_file(root / relative, row, budget)
        require(required <= expected, 'required-header-missing:' + role)
        require(header_inventory(root, budget) == expected, 'extra-or-missing-header:' + role)
    archives = value['archives']
    require(isinstance(archives, dict) and CORE_ARCHIVES | {'editline'} <= set(archives)
            and len(archives) <= 37, 'archive-role-set')
    for role, row in archives.items():
        require(re.fullmatch('[a-z][a-z0-9_]*', role), 'invalid-archive-role')
        keys(row, {'path', 'bytes', 'sha256'}, 'archive-fields')
        path = path_value(row['path'])
        require(path.suffix == '.a', 'archive-extension')
        verify_file(path, row, budget)
    order = value['editline_link_order']
    require(isinstance(order, list) and 0 < len(order) <= 32
            and all(isinstance(role, str) and role in archives and role not in CORE_ARCHIVES for role in order),
            'editline-link-order')
    require('editline' in order and set(order) | CORE_ARCHIVES == set(archives), 'unused-or-missing-archive')
    return {'scope': 'private-build-input-byte-and-declared-review-binding-only',
            'manifest_sha256': expected_sha256, 'byte_preflight_passed': True,
            'checked_file_references': budget['files'], 'checked_bytes': budget['bytes'],
            'editline_link_order': order, 'build_ready': False, 'tool_acceptance': 'not-accepted',
            'abi_verified': False, 'configuration_executed': False,
            'remaining': ['external closure/ABI/license/trust review',
                          'SDK tools/sysroot/CRT/specs inventory and execution plan',
                          'actual CMake and link behavior', 'separate build/run authorization']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--sha256', required=True, help='Separately reviewed raw manifest SHA-256')
    args = parser.parse_args()
    try:
        result = check(args.manifest, args.sha256)
    except (ValueError, OSError, RecursionError) as error:
        print('build-input-preflight-rejected: ' + str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
