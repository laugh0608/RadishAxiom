#!/usr/bin/env python3
"""Derive an offline SDK layout candidate; never materialize or execute it."""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('c2_recipe', ROOT / 'scripts/prepare-cvc5-offline-build.py')
C2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C2)
require = C2.require
FORMAT = 'radishaxiom-private-cvc5-execution-review'
SELF = 'scripts/prepare-cvc5-execution-review.py'
RULES = 'scripts/cvc5-build-support/event_rules.py'
ENTRY_LIMIT = 100000


def name(value):
    require(isinstance(value, str) and 0 < len(value.encode()) <= 4096, 'layout-path-size')
    require(not any(ord(c) < 32 or ord(c) == 127 for c in value), 'layout-path-control')
    C2.SOURCES.path_name(value)
    return value


def link_target(path, target, hardlink):
    require(isinstance(target, str) and 0 < len(target.encode()) <= 4096
            and '\\' not in target and not any(ord(c) < 32 or ord(c) == 127 for c in target),
            'layout-link-target')
    # Absolute symlinks mean the future isolated root, never the host root.
    parts = [] if hardlink or target.startswith('/') else path.split('/')[:-1]
    descended = False
    for part in target.split('/'):
        if part in ('', '.'):
            continue
        if part == '..':
            # Lexical normalization after traversing a link can disagree with
            # kernel pathname lookup. Refuse that ambiguous target entirely.
            require(not descended, 'layout-link-ambiguous-parent')
            require(bool(parts), 'layout-link-escape')
            parts.pop()
        else:
            parts.append(part)
            descended = True
    return '/'.join(parts)


def resolve(index, path):
    seen, trail = set(), []
    for _ in range(40):
        require(path not in seen, 'layout-link-cycle:' + path)
        seen.add(path)
        parts = path.split('/') if path else []
        for n in range(1, len(parts) + 1):
            prefix = '/'.join(parts[:n])
            row = index.get(prefix)
            if row is None:
                return {'status': 'missing', 'path': prefix, 'trail': trail}
            if row['kind'] in ('symlink', 'hardlink'):
                target = link_target(prefix, row['target'], row['kind'] == 'hardlink')
                path = '/'.join(([target] if target else []) + parts[n:])
                trail.append(prefix)
                break
            require(n == len(parts) or row['kind'] == 'directory', 'layout-nondirectory-ancestor')
        else:
            return {'status': 'resolved', 'path': path,
                    'kind': index[path]['kind'] if path else 'directory', 'trail': trail}
    raise ValueError('layout-link-depth')


def layout(packages):
    require(isinstance(packages, list) and 0 < len(packages) <= 1000, 'layout-package-budget')
    index, seen_packages, count = {}, set(), 0
    for package in packages:
        owner = (package['package'], package['version'])
        require(all(isinstance(x, str) and x for x in owner) and owner[0] not in seen_packages,
                'layout-package-identity')
        seen_packages.add(owner[0])
        seen = set()
        for source in package['data']['entries']:
            count += 1
            require(count <= ENTRY_LIMIT, 'layout-entry-budget')
            path = name(source['path'])
            require(path not in seen, 'layout-package-duplicate')
            seen.add(path)
            kind = source['kind']
            require(kind in ('file', 'directory', 'symlink', 'hardlink'), 'layout-entry-kind')
            mode = source['mode']
            require(isinstance(mode, str) and re.fullmatch('[0-7]{4}', mode), 'layout-mode')
            size = source['bytes']
            require(type(size) is int and 0 <= size <= 128 * 1024**2, 'layout-file-budget')
            require(kind == 'file' or size == 0, 'layout-nonfile-payload')
            row = {'path': path, 'kind': kind, 'bytes': size, 'archive_mode': mode,
                   'candidate_mode': format(int(mode, 8) & ~0o6000, '04o')}
            if kind == 'file':
                C2.BUILD.hash_value(source['sha256'])
                row['sha256'] = source['sha256']
            elif kind in ('symlink', 'hardlink'):
                row['target'] = source['target']
                link_target(path, row['target'], kind == 'hardlink')
            prior = index.get(path)
            if prior is not None:
                require({k: v for k, v in prior.items() if k != 'owners'} == row,
                        'layout-collision:' + path)
                prior['owners'].append(list(owner))
            else:
                index[path] = {**row, 'owners': [list(owner)]}
    # Missing parent directories are explicit planned entries, not side effects.
    for path in list(index):
        parts = path.split('/')
        for n in range(1, len(parts)):
            parent = '/'.join(parts[:n])
            if parent not in index:
                index[parent] = {'path': parent, 'kind': 'directory', 'bytes': 0,
                                 'archive_mode': None, 'candidate_mode': '0755', 'owners': []}
            require(index[parent]['kind'] == 'directory', 'layout-nondirectory-ancestor:' + parent)
            require(len(index) <= ENTRY_LIMIT, 'layout-entry-budget')
    missing, mode_changes = [], []
    for path, row in sorted(index.items()):
        if row['archive_mode'] is not None and row['archive_mode'] != row['candidate_mode']:
            mode_changes.append({'path': path, 'from': row['archive_mode'], 'to': row['candidate_mode']})
        if row['kind'] in ('symlink', 'hardlink'):
            resolution = resolve(index, path)
            row['resolution'] = resolution
            if row['kind'] == 'hardlink':
                require(resolution['status'] == 'resolved' and resolution['kind'] == 'file',
                        'layout-hardlink-target')
                require(all(index[p]['kind'] == 'hardlink' for p in resolution['trail']),
                        'layout-hardlink-through-symlink')
                require(index[resolution['path']]['candidate_mode'] == row['candidate_mode'],
                        'layout-hardlink-mode')
            elif resolution['status'] != 'resolved':
                missing.append({'link_path': path, **resolution})
    entries = [index[path] for path in sorted(index)]
    size = sum(x['bytes'] for x in entries)
    require(size <= C2.TOTAL_LIMIT, 'layout-total-byte-budget')
    return {'entries': entries, 'summary': {'packages': len(packages), 'archive_entries': count,
            'unique_paths': len(entries), 'regular_bytes': size,
            'kinds': dict(sorted(Counter(x['kind'] for x in entries).items())),
            'implicit_directories': sum(not x['owners'] for x in entries)},
            'unresolved_symlinks': missing, 'permission_changes': mode_changes}


def generate(recipe_path, digest):
    recipe = C2.checked_plan(recipe_path, digest)
    ref = recipe['sdk']['inventory']
    path = C2.local(ref['path'])
    with C2.regular(path).open('rb') as stream:
        compressed = stream.read(C2.JSON_LIMIT + 1)
    require(len(compressed) == ref['bytes'] and len(compressed) <= C2.JSON_LIMIT
            and hashlib.sha256(compressed).hexdigest() == ref['sha256'], 'layout-inventory-binding')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        raw = stream.read(C2.JSON_LIMIT + 1)
    require(len(raw) <= C2.JSON_LIMIT, 'layout-inventory-budget')
    inventory = json.loads(raw, object_pairs_hook=C2.PREP.CHECK.reject_duplicates,
                           parse_constant=C2.PREP.CHECK.reject_constant)
    candidate = layout([p for p in inventory['observations'] if p['kind'] == 'binary'])
    return {'format': FORMAT, 'version': '0.1', 'scope': 'offline-candidate-no-execution',
            'recipe_sha256': digest, 'inventory': ref,
            'methods': [C2.identity(ROOT / p) for p in (SELF, RULES)],
            'assembly_ready': False, 'execution_ready': False, 'build_ready': False,
            'layout': candidate,
            'assembly_order': ['exclusive fresh root; no host destination resolution',
                               'directories; regular files streamed from verified deb data members',
                               'hardlinks to resolved regular members; symlinks last',
                               'lstat/readback every path/type/mode/byte identity and reject extras',
                               'freeze read-only; read back mounts and full tree before first command'],
            'pending_decisions': ['C1 acceptance and separate assembly authorization',
                                  'review every unresolved symlink; never invent alternatives or host targets',
                                  'accept explicit setuid/setgid removal and rootless ownership mapping',
                                  'qualify native host, read observer, watchdog and quota enforcement',
                                  'set explicit pids/inode limits and observation interval before execution'],
            'supervision': {'rules': RULES, 'scope': 'pure event declarations, not OS observations',
                            'schedule': 'exact dependency_steps only; main phase needs its own bound manifest',
                            'resources': recipe['policy']['resources'],
                            'log_limits': recipe['evidence']['log_limits'],
                            'runtime_acceptance': False},
            'executed_steps': [], 'materialized_paths': []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = generate(args.recipe, args.sha256)
        C2.write_new(args.output, result)
        print(json.dumps({'review_written': str(args.output),
                          'sha256': hashlib.sha256(C2.encoded(result)).hexdigest(),
                          'layout': result['layout']['summary'],
                          'unresolved_symlinks': len(result['layout']['unresolved_symlinks']),
                          'permission_changes': result['layout']['permission_changes'],
                          'assembly_ready': False, 'execution_ready': False, 'build_ready': False}))
        return 2
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'review': 'failed', 'reason': str(exc), 'execution_ready': False}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
