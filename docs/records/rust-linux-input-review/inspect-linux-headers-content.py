#!/usr/bin/env python3
"""Logical headers/link inventory and comparisons; no filesystem extraction or build execution."""
from collections import Counter
import importlib.util
import io
from pathlib import Path
import re
import tarfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('inputs', HERE / 'inspect-mpc-mpfr-inputs.py')
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)
require, identity = inputs.require, inputs.identity
LINK_HOPS = 64
SELECTED = {'README.md', 'Makefile', 'tools/install.sh', 'generic/include/linux/version.h',
            'generic/include/linux/libc-compat.h', 'arm64/include/asm/unistd.h',
            'UPDATE.sh', 'create-dist.sh', 'test.sh'}


def target_parts(target):
    require(isinstance(target, str) and 0 < len(target.encode()) <= 4096 and
            not target.startswith('/') and '\\' not in target and
            not any(ord(c) < 32 or ord(c) == 127 for c in target), 'unsafe symbolic target')
    parts = target.split('/')
    require(all(parts), 'empty symbolic target component')
    return parts


def resolve(rows, name, top):
    """Resolve each component, including symlinks before '..'; never touch disk."""
    pending, done, hops, states = name.split('/'), [], 0, set()
    require(pending[0] == top, 'path outside root')
    while pending:
        state = (tuple(done), tuple(pending))
        require(state not in states, 'symbolic link cycle')
        states.add(state)
        part = pending.pop(0)
        if part == '.':
            continue
        if part == '..':
            require(len(done) > 1, 'symbolic target escapes root')
            done.pop()
            continue
        path = '/'.join([*done, part])
        require(path in rows, 'dangling link or missing path')
        row = rows[path]
        if row['kind'] == 'symlink':
            hops += 1
            require(hops <= LINK_HOPS, 'symbolic link hop bound')
            pending = target_parts(row['target']) + pending
        else:
            require(not pending or row['kind'] == 'directory', 'file traversed as directory')
            done.append(part)
    return '/'.join(done)


def inventory(raw, top):
    require(0 < len(raw) <= inputs.MAX_TAR, 'tar size bound')
    rows, texts = {}, {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        comment = archive.pax_headers.get('comment')
        for member in archive:
            name = inputs.archive.path_name(member.name, top, member.isdir())
            require(name not in rows and len(rows) < inputs.MAX_MEMBERS, 'duplicate or member count bound')
            require((member.isfile() or member.isdir() or member.issym()) and not member.issparse(),
                    'hardlink, sparse or special member')
            require(0 <= member.size <= inputs.MAX_MEMBER, 'member size bound')
            kind = 'file' if member.isfile() else 'directory' if member.isdir() else 'symlink'
            require(kind == 'file' or member.size == 0, 'non-file payload')
            row = {'path': name, 'kind': kind, 'bytes': member.size, 'mode': member.mode,
                   'uid': member.uid, 'gid': member.gid, 'mtime': member.mtime}
            relative = name[len(top) + 1:]
            if kind == 'symlink':
                target_parts(member.linkname)
                row['target'] = member.linkname
            elif kind == 'file':
                data = archive.extractfile(member).read(inputs.MAX_MEMBER + 1)
                require(len(data) == member.size, 'truncated or oversized member')
                row.update(identity(data))
                # Record only literal header declarations; this is not a license classifier.
                row['spdx_declarations'] = [m.decode('ascii').strip().removesuffix('*/').strip()
                                            for m in re.findall(rb'SPDX-License-Identifier:[^\r\n]*', data[:4096])]
                if relative in SELECTED or relative.startswith('patches/'):
                    texts[relative] = data.decode('utf-8')
            rows[name] = row
        require(not any(raw[archive.offset:]), 'nonzero tar tail')
    require(top in rows and rows[top]['kind'] == 'directory', 'missing directory root')
    for name, row in rows.items():
        if name != top:
            parent = name.rsplit('/', 1)[0]
            require(parent in rows and rows[parent]['kind'] == 'directory', 'missing or linked physical ancestor')
        if row['kind'] == 'symlink':
            row['resolved_target'] = resolve(rows, name, top)
    return {'tar': identity(raw), 'top': top, 'pax_comment': comment,
            'members': [rows[name] for name in sorted(rows)],
            'type_counts': dict(Counter(row['kind'] for row in rows.values())),
            'selected_review_files': sorted(texts), 'physical_tar_profile_verified': False,
            'links_resolved_in_memory_only': True, 'source_acceptance': 'not-assessed'}, texts


def compare(left, right):
    def indexed(report):
        return {row['path'][len(report['top']) + 1:]: row for row in report['members']}
    a, b = indexed(left), indexed(right)
    changed, modes, metadata = [], [], []
    for path in sorted(a.keys() & b.keys()):
        if any(a[path].get(k) != b[path].get(k) for k in ('kind', 'bytes', 'sha256', 'target')):
            changed.append(path)
        if a[path]['mode'] != b[path]['mode']:
            modes.append(path)
        if any(a[path][k] != b[path][k] for k in ('uid', 'gid', 'mtime')):
            metadata.append(path)
    return {'only_in_mirror': sorted(a.keys() - b.keys()), 'only_in_candidate': sorted(b.keys() - a.keys()),
            'content_link_or_type_differences': changed, 'mode_differences': modes,
            'owner_or_mtime_differences': metadata,
            'normalized_all_members_equal': not (a.keys() ^ b.keys() or changed or modes),
            'complete_tar_bytes_equal': left['tar'] == right['tar'], 'comparison_does_not_authenticate_source': True}


def include_projection(report, arch='arm64'):
    """Enumerate in-memory reachable .h paths within the five documented glob depths, not a make run."""
    top = report['top']
    rows = {row['path']: row for row in report['members']}
    root = resolve(rows, top + '/' + arch + '/include', top)
    children = {}
    for name in rows:
        if '/' in name:
            children.setdefault(name.rsplit('/', 1)[0], []).append(name)
    output, stack, visited = [], [(root, '', frozenset())], 0
    while stack:
        actual, virtual, ancestors = stack.pop()
        require(actual not in ancestors, 'directory projection cycle')
        visited += 1
        require(visited <= inputs.MAX_MEMBERS, 'projection directory bound')
        for child in children.get(actual, []):
            base = child.rsplit('/', 1)[-1]
            if base.startswith('.'):
                continue
            relative = virtual + base
            target = resolve(rows, child, top)
            row = rows[target]
            if row['kind'] == 'directory' and relative.count('/') < 4:
                stack.append((target, relative + '/', ancestors | {actual}))
            elif row['kind'] == 'file' and relative.endswith('.h'):
                require(len(output) < inputs.MAX_MEMBERS, 'projection file bound')
                output.append({'include_path': relative, 'source_path': target[len(top) + 1:],
                               'bytes': row['bytes'], 'sha256': row['sha256']})
    return {'arch': arch, 'headers': sorted(output, key=lambda row: row['include_path']),
            'make_executed': False, 'actual_installation_verified': False}
