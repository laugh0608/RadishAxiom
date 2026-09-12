#!/usr/bin/env python3
"""Read fixed Debian payloads in memory; never extract or execute their programs."""
import argparse
import gzip
import importlib.util
import io
import json
import lzma
from pathlib import Path
import re
import tarfile

HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reader = load('trust_inputs', 'inspect-musl-trust-inputs.py')
elf = load('selected_inputs', 'inspect-selected-inputs.py')
require = reader.require
identity = reader.identity


def canonical(name):
    name = name.removeprefix('./')
    require(name == '.' or name and not name.startswith('/') and
            all(part not in {'', '.', '..'} for part in name.split('/')),
            'noncanonical archive member')
    require(len(name.encode()) <= 1024 and not any(ord(c) < 32 for c in name),
            'invalid archive member name')
    return name


def link_destination(name, target, hard=False):
    require(bool(target) and len(target.encode()) <= 1024 and
            not any(ord(c) < 32 for c in target), 'invalid link target')
    parts = [] if hard or target.startswith('/') else name.split('/')[:-1]
    for part in target.split('/'):
        if part in {'', '.'}:
            continue
        if part == '..':
            require(bool(parts), 'link escapes candidate root')
            parts.pop()
        else:
            parts.append(part)
    return '/'.join(parts) or '.'


def read_tar(data, limit):
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=128 * 1024**2)
    raw = decoder.decompress(data, max_length=limit + 1)
    require(len(raw) <= limit and decoder.eof and not decoder.unused_data,
            'oversized, truncated or concatenated XZ')
    require(len(raw) % 512 == 0, 'tar block alignment')
    rows, contents, seen = [], {}, set()
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            name = canonical(member.name)
            require(len(rows) < 10000 and name not in seen and not member.pax_headers,
                    'duplicate, excessive or extended tar members')
            require(member.uid == 0 and member.gid == 0 and
                    0 <= member.size <= 16 * 1024**2, 'owner or file size outside profile')
            seen.add(name)
            row = {'path': name, 'mode': member.mode, 'uid': member.uid, 'gid': member.gid}
            if member.isdir():
                row['type'] = 'directory'
            elif member.isfile():
                row['type'] = 'file'
                content = archive.extractfile(member).read(16 * 1024**2 + 1)
                require(len(content) == member.size, 'truncated tar file')
                row.update(identity(content))
                contents[name] = content
            elif member.issym() or member.islnk():
                row.update(type='hardlink' if member.islnk() else 'symlink',
                           target=member.linkname,
                           destination=link_destination(name, member.linkname, member.islnk()))
            else:
                raise ValueError('unsupported special tar member: ' + name)
            require(name != '.' or member.isdir(), 'root must be directory')
            require(member.isfile() or member.size == 0, 'non-file has data')
            rows.append(row)
        tail = raw[archive.offset:]
        require(len(tail) >= 1024 and not any(tail), 'nonzero or missing tar end blocks')
    by_name = {row['path']: row for row in rows}
    for name in by_name:
        for parent in Path(name).parents:
            key = str(parent)
            require(key not in by_name or by_name[key]['type'] == 'directory',
                    'archive member below non-directory')
    return {'expanded_tar': identity(raw), 'members': rows}, contents


def resolve(index, path):
    path = canonical(path.lstrip('/'))
    visited = set()
    for _ in range(32):
        require(path not in visited, 'candidate link cycle')
        visited.add(path)
        parts = path.split('/')
        for count in range(1, len(parts) + 1):
            prefix = '/'.join(parts[:count])
            row = index.get(prefix)
            if row is None:
                return {'status': 'missing', 'path': path, 'missing_component': prefix}
            if row['type'] in {'symlink', 'hardlink'}:
                require(row['type'] != 'hardlink' or count == len(parts),
                        'hardlink used as directory')
                suffix = '/'.join(parts[count:])
                path = row['destination'] + ('/' + suffix if suffix else '')
                break
            if count < len(parts):
                require(row['type'] == 'directory', 'non-directory in candidate path')
        else:
            return {'status': 'found', 'path': path, 'type': row['type'],
                    'packages': row['packages'],
                    **{key: row[key] for key in ('bytes', 'sha256') if key in row}}
    raise ValueError('candidate link depth limit')


def root_candidates(rows):
    by_path = {row['path']: row for row in rows}
    roots = ['usr/bin/gpg', 'usr/bin/gpgconf']
    pending, selected, missing = roots.copy(), {}, []
    while pending:
        path = pending.pop(0)
        if path in selected:
            continue
        require(path in by_path, 'candidate is not inventoried ELF')
        row = by_path[path]
        selected[path] = {key: row[key] for key in ('path', 'bytes', 'sha256', 'packages')}
        for name, candidate in row['library_path_candidates'].items():
            if candidate['status'] == 'found' and candidate['type'] == 'file':
                pending.append(candidate['path'])
            else:
                missing.append({'from': path, 'needed': name, 'candidate': candidate})
    return {'roots': roots, 'files': [selected[key] for key in sorted(selected)],
            'file_count': len(selected), 'file_bytes': sum(row['bytes'] for row in selected.values()),
            'unresolved_needed': missing, 'loader_resolution_assessed': False}


def inspect(directory, include_text=False):
    manifest_path = HERE / 'musl-verifier-packages-2026-09-12.json'
    manifest_raw = manifest_path.read_bytes()
    require(identity(manifest_raw)['sha256'] ==
            'a67e2c07302b945d4d5add12851e5714418614aaba9a28254bef1662bd8b4861',
            'candidate manifest digest drift')
    manifest = json.loads(manifest_raw)
    require(manifest['package_count'] == 17 and manifest['total_package_bytes'] == 5906300,
            'wrong candidate manifest')
    index, contents, packages, expanded = {}, {}, [], 0
    for package in manifest['packages']:
        name = package['package']
        stem = name.replace('.', '_')
        attempt = 2 if name == 'gcc-14-base' else 1
        data = reader.fixed(directory / f'{stem}-attempt-{attempt}.deb',
                            package['bytes'], package['sha256'])
        ar = reader.ar_members(data)
        control, controls = read_tar(ar['control.tar.xz'], 4 * 1024**2)
        payload, files = read_tar(ar['data.tar.xz'], 64 * 1024**2)
        expanded += control['expanded_tar']['bytes'] + payload['expanded_tar']['bytes']
        require(expanded <= 256 * 1024**2, 'cumulative tar limit')
        fields = list(reader.CHAIN.stanzas(controls['control'].decode().splitlines(keepends=True)))
        require(len(fields) == 1, 'unexpected control record count')
        fields = fields[0]
        for key in ('package', 'version', 'architecture'):
            require(fields.get(key) == package[key], 'control identity drift: ' + name)
        for key in ('depends', 'pre-depends', 'recommends', 'suggests', 'conflicts',
                    'breaks', 'replaces', 'provides', 'essential'):
            require(fields.get(key) == package['declared_relationships'].get(key),
                    'control relationship drift: ' + name + '/' + key)
        source = fields.get('source', fields['package'])
        match = re.fullmatch(r'([a-z0-9+.-]+)(?: \(([^)]+)\))?', source)
        require(match is not None and match[1] == package['source_package'] and
                (match[2] or fields['version']) == package['source_version'], 'control source drift')
        for row in payload['members']:
            path = row['path']
            if path in index:
                previous = {k: v for k, v in index[path].items() if k != 'packages'}
                require(row == previous and row['type'] == 'directory', 'cross-package path collision')
                index[path]['packages'].append(name)
            else:
                index[path] = {**row, 'packages': [name]}
        contents.update(files)
        scripts = {path: identity(content) for path, content in controls.items()
                   if path in {'preinst', 'postinst', 'prerm', 'postrm', 'triggers', 'conffiles'}}
        if include_text:
            scripts = {path: {**value, 'text': controls[path].decode()} for path, value in scripts.items()}
        packages.append({'package': name, 'input': identity(data), 'control': control,
                         'control_fields': fields, 'payload': payload, 'installation_metadata': scripts})
    elf_rows = []
    for path, data in sorted(contents.items()):
        if data.startswith(b'\x7fELF'):
            metadata = elf.elf_dependencies(data)
            require(metadata['machine'] == 183, 'non-AArch64 ELF')
            candidates = {name: resolve(index, 'usr/lib/aarch64-linux-gnu/' + name)
                          for name in metadata['needed']}
            elf_rows.append({'path': path, **identity(data), **metadata,
                             'packages': index[path]['packages'],
                             'library_path_candidates': candidates,
                             'interpreter_in_package_tree': resolve(index, metadata['interpreter'])
                             if metadata['interpreter'] else None})
    for package in packages:
        path = 'usr/share/doc/' + package['package'] + '/copyright'
        target = resolve(index, path)
        require(target['status'] == 'found' and target['type'] == 'file', 'copyright not found')
        text = contents[target['path']].decode('utf-8')
        package['copyright'] = {'requested_path': path, **target,
            'license_fields': sorted(set(re.findall(r'^License: (.+)$', text, re.M))),
            'common_license_references': sorted({value.rstrip('.') for value in
                re.findall(r'/usr/share/common-licenses/[A-Za-z0-9.+-]+', text)})}
        package['copyright']['common_license_path_candidates'] = {
            value: resolve(index, value) for value in package['copyright']['common_license_references']}
        if include_text:
            package['copyright']['text'] = text
    return {'kind': 'diagnostic-verifier-package-content', 'acceptance': 'not-assessed',
            'candidate_manifest': identity(manifest_raw), 'package_count': len(packages),
            'expanded_tar_bytes': expanded, 'packages': packages, 'elf_files': elf_rows,
            'root_static_candidates': root_candidates(elf_rows),
            'links': [{**row, 'resolved': resolve(index, path)} for path, row in sorted(index.items())
                      if row['type'] in {'symlink', 'hardlink'}],
            'runtime_closure_assessed': False, 'symbol_versions_inspected': False,
            'signature_reverified': False, 'programs_executed': False,
            'methods': {str(path.relative_to(HERE.parents[2])): identity(path.read_bytes()) for path in
                        (Path(__file__), HERE / 'inspect-musl-trust-inputs.py',
                         HERE / 'inspect-selected-inputs.py', reader.ROOT / 'scripts/inspect-debian-source-chain.py')}}


def summarize(result):
    raw = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode()
    summary = {key: result[key] for key in (
        'kind', 'acceptance', 'candidate_manifest', 'package_count', 'expanded_tar_bytes',
        'root_static_candidates', 'methods', 'runtime_closure_assessed',
        'symbol_versions_inspected', 'signature_reverified', 'programs_executed')}
    summary.update(inventory_gzip=identity(gzip.compress(raw, mtime=0)), inventory_json=identity(raw),
        elf_count=len(result['elf_files']), link_count=len(result['links']),
        total_payload_members=sum(len(p['payload']['members']) for p in result['packages']),
        package_copyrights=[{'package': p['package'], **p['copyright']} for p in result['packages']],
        interpreter_observations=[{key: row[key] for key in
            ('path', 'interpreter', 'interpreter_in_package_tree')}
            for row in result['elf_files'] if row['interpreter']],
        fetch_record=identity((HERE / 'musl-verifier-package-fetch-2026-09-12.json').read_bytes()))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--include-text', action='store_true')
    mode.add_argument('--summary', action='store_true')
    args = parser.parse_args()
    result = inspect(args.directory, args.include_text)
    print(json.dumps(summarize(result) if args.summary else result, sort_keys=True, indent=2))
