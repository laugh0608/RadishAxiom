#!/usr/bin/env python3
"""Inspect the fixed, single-layer Linux channel candidate without extracting or running it.

No Docker, network, package installation, acceptance or qualification operations.
The candidate metadata is the separately retained local observation, not a registry signature.
"""
import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
import tarfile

ARCHIVE_LIMIT = 64 * 1024**2
LAYER_LIMIT = 32 * 1024**2
JSON_LIMIT = 1024**2
MEMBER_LIMIT = 4096
INDEX = 'application/vnd.oci.image.index.v1+json'
MANIFEST = 'application/vnd.oci.image.manifest.v1+json'
LAYER = 'application/vnd.oci.image.layer.v1.tar+gzip'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'duplicate-json-key')
        result[key] = value
    return result


def reject_constant(_):
    raise ValueError('nonfinite-json')


def json_value(raw):
    require(0 < len(raw) <= JSON_LIMIT, 'json-byte-limit')
    # A bounded pre-scan keeps json.loads away from recursion-sized inputs.
    depth, quoted, escaped = 0, False, False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            require(depth <= 64, 'json-depth-limit')
        elif byte in (93, 125):
            depth -= 1
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject_constant)


def path_name(name):
    require(type(name) is str and 0 < len(name.encode()) <= 4096, 'tar-path-size')
    require(not name.startswith('/') and '\\' not in name
            and all(ord(c) >= 32 and ord(c) != 127 for c in name), 'tar-path')
    require(str(PurePosixPath(name)) == name
            and all(p not in ('', '.', '..') for p in name.split('/')), 'tar-path-components')
    return name


def tar_members(raw, rootfs=False):
    require(len(raw) <= (LAYER_LIMIT if rootfs else ARCHIVE_LIMIT)
            and len(raw) % 512 == 0, 'tar-size')
    # Reject extensions before tarfile can consume hidden PAX / GNU headers.
    offset, count = 0, 0
    while offset + 512 <= len(raw) and any(raw[offset:offset + 512]):
        header = raw[offset:offset + 512]
        require(header[156:157] in ((b'0', b'\0', b'5', b'2') if rootfs
                                   else (b'0', b'\0', b'5')), 'tar-type-or-extension')
        field = header[124:136].strip(b'\0 ')
        require(not field or re.fullmatch(b'[0-7]+', field), 'tar-size-encoding')
        size = int(field or b'0', 8)
        offset += 512 + ((size + 511) // 512) * 512
        count += 1
        require(count <= MEMBER_LIMIT and offset <= len(raw), 'tar-count-or-bounds')
    require(count > 0 and len(raw) - offset >= 1024 and not any(raw[offset:]),
            'tar-end-or-trailing-data')
    rows, content, total = {}, {}, 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        require(not archive.pax_headers, 'tar-global-pax')
        for member in archive:
            name = path_name(member.name)
            require(name not in rows and not member.pax_headers, 'tar-duplicate-or-pax')
            require(not member.mode & 0o6000, 'tar-privileged-mode')
            require(0 <= member.uid <= 65535 and 0 <= member.gid <= 65535
                    and (rootfs or member.uid == member.gid == 0), 'tar-unexpected-owner')
            require(member.isfile() or member.isdir() or (rootfs and member.issym()),
                    'tar-special-member')
            row = {'path': name, 'mode': format(member.mode, '04o'),
                   'uid': member.uid, 'gid': member.gid, 'bytes': member.size}
            if member.isfile():
                require(0 <= member.size <= LAYER_LIMIT, 'tar-member-size')
                total += member.size
                require(total <= (LAYER_LIMIT if rootfs else ARCHIVE_LIMIT), 'tar-total-size')
                data = archive.extractfile(member).read(member.size + 1)
                require(len(data) == member.size, 'tar-member-truncated')
                content[name] = data
                row.update(kind='file', sha256=sha(data))
            elif member.issym():
                require(member.size == 0 and 0 < len(member.linkname.encode()) <= 4096
                        and '\\' not in member.linkname
                        and all(ord(c) >= 32 and ord(c) != 127 for c in member.linkname),
                        'tar-link')
                row.update(kind='symlink', target=member.linkname)
            else:
                require(member.size == 0, 'tar-nonempty-directory')
                row.update(kind='directory')
            rows[name] = row
    require(len(rows) == count, 'tar-hidden-headers')
    for name in rows:
        for parent in PurePosixPath(name).parents:
            if str(parent) != '.':
                require(str(parent) in rows and rows[str(parent)]['kind'] == 'directory',
                        'tar-missing-or-nondirectory-parent')
    return rows, content


def resolve(rows, name):
    pending, stack, links = name.split('/'), [], 0
    while pending:
        part = pending.pop(0)
        if part in ('', '.'):
            continue
        if part == '..':
            require(bool(stack), 'rootfs-link-escape')
            stack.pop()
            continue
        stack.append(part)
        current = '/'.join(stack)
        row = rows.get(current)
        require(row is not None, 'rootfs-missing-path')
        if row['kind'] == 'symlink':
            links += 1
            require(links <= 40, 'rootfs-link-depth')
            target = row['target']
            stack = [] if target.startswith('/') else stack[:-1]
            pending = target.split('/') + pending
        elif pending:
            require(row['kind'] == 'directory', 'rootfs-nondirectory-ancestor')
    return '/'.join(stack)


def descriptor(value, blobs):
    require(type(value) is dict and type(value.get('size')) is int, 'descriptor-shape')
    digest = value.get('digest')
    require(type(digest) is str and re.fullmatch('sha256:[0-9a-f]{64}', digest),
            'descriptor-digest')
    key = 'blobs/sha256/' + digest[7:]
    require(key in blobs and len(blobs[key]) == value['size']
            and sha(blobs[key]) == digest[7:], 'descriptor-missing-size-or-digest')
    return blobs[key]


def elf(raw):
    require(len(raw) >= 64 and raw[:7] == b'\x7fELF\x02\x01\x01', 'elf64-le')
    h = struct.unpack_from('<16sHHIQQQIHHHHHH', raw)
    require(h[1] in (2, 3) and h[2] == 183 and h[3] == 1
            and h[8] == 64 and h[9] == 56 and 0 < h[10] <= 128, 'elf-aarch64-shape')
    require(h[5] >= 64 and h[5] + 56 * h[10] <= len(raw), 'elf-program-bounds')
    headers, interpreter, dynamic = [], [], []
    for index in range(h[10]):
        p = struct.unpack_from('<IIQQQQQQ', raw, h[5] + 56 * index)
        require(p[2] + p[5] <= len(raw) and (p[0] != 1 or p[5] <= p[6]),
                'elf-segment-bounds')
        headers.append(p)
        if p[0] == 3:
            text = raw[p[2]:p[2] + p[5]]
            require(text.endswith(b'\0') and b'\0' not in text[:-1], 'elf-interpreter')
            interpreter.append(text[:-1].decode('ascii'))
        if p[0] == 2:
            require(p[5] % 16 == 0, 'elf-dynamic-size')
            entries = [struct.unpack_from('<qQ', raw, off)
                       for off in range(p[2], p[2] + p[5], 16)]
            require(any(tag == 0 for tag, _ in entries), 'elf-dynamic-terminator')
            dynamic += entries[:next(n for n, entry in enumerate(entries) if entry[0] == 0)]
    require(len(interpreter) <= 1, 'elf-interpreter-count')
    needed, search = [], []
    if dynamic:
        strings = [v for t, v in dynamic if t == 5]
        sizes = [v for t, v in dynamic if t == 10]
        require(len(strings) == len(sizes) == 1 and sizes[0] <= JSON_LIMIT, 'elf-string-table')
        locations = [p[2] + strings[0] - p[3] for p in headers if p[0] == 1
                     and p[3] <= strings[0] and strings[0] + sizes[0] <= p[3] + p[5]]
        require(len(locations) == 1, 'elf-string-address')
        table = raw[locations[0]:locations[0] + sizes[0]]
        for tag, offset in dynamic:
            if tag in (1, 15, 29):
                require(offset < len(table) and b'\0' in table[offset:], 'elf-dynamic-string')
                text = table[offset:table.index(b'\0', offset)].decode('ascii')
                (needed if tag == 1 else search).append(text)
    return {'machine': 'AArch64', 'type': 'ET_DYN' if h[1] == 3 else 'ET_EXEC',
            'interpreter': interpreter, 'needed': needed, 'rpath_or_runpath': search,
            'scope': 'program-header-and-dynamic-layout-only'}


def apk_records(raw, rows, content):
    require(len(raw) <= JSON_LIMIT, 'apk-database-size')
    packages, names, checked, mismatches = [], set(), 0, []
    for block in raw.decode('utf-8').strip().split('\n\n'):
        metadata, directory, filename, checksums = {}, None, None, []
        for line in block.splitlines():
            require(len(line) >= 2 and line[1] == ':', 'apk-field')
            tag, value = line[0], line[2:]
            if tag in ('P', 'V', 'A', 'L', 'o', 'c'):
                require(tag not in metadata and value, 'apk-duplicate-or-empty-metadata')
                metadata[tag] = value
            elif tag == 'F':
                directory = path_name(value) if value else ''
                filename = None
            elif tag == 'R':
                require(directory is not None and value and '/' not in value, 'apk-file-path')
                filename = path_name('/'.join(x for x in (directory, value) if x))
            elif tag == 'Z':
                require(filename is not None and value.startswith('Q1'), 'apk-checksum-scope')
                checksum = base64.b64decode(value[2:], validate=True)
                require(len(checksum) == 20 and filename in rows, 'apk-checksum-path-or-size')
                row = rows[filename]
                require(row['kind'] in ('file', 'symlink'), 'apk-checksum-kind')
                data = content[filename] if row['kind'] == 'file' else row['target'].encode()
                # Q1 is the existing APK v2 file checksum, not an authentication claim.
                if hashlib.sha1(data).digest() != checksum:
                    mismatches.append({'path': filename, 'package': metadata.get('P'),
                                       'declared_sha1': checksum.hex(),
                                       'observed_sha1': hashlib.sha1(data).hexdigest()})
                checksums.append(filename)
        require(set(metadata) == {'P', 'V', 'A', 'L', 'o', 'c'}
                and metadata['A'] == 'aarch64' and metadata['P'] not in names
                and re.fullmatch('[0-9a-f]{40}', metadata['c']), 'apk-metadata')
        names.add(metadata['P'])
        checked += len(checksums)
        packages.append({'name': metadata['P'], 'version': metadata['V'], 'arch': metadata['A'],
                         'declared_license': metadata['L'], 'origin': metadata['o'],
                         'declared_aports_commit': metadata['c'],
                         'checked_file_checksums': len(checksums)})
    require(0 < len(packages) <= 128, 'apk-package-count')
    return sorted(packages, key=lambda p: p['name']), checked, mismatches


def inspect(raw, candidate):
    require(type(candidate) is dict, 'candidate-object')
    expected = candidate['selected_candidate_metadata']
    require(candidate['scope'] == 'local-docker-metadata-only-not-accepted'
            and expected['Architecture'] == 'arm64' and expected['Os'] == 'linux',
            'candidate-scope')
    outer, blobs = tar_members(raw)
    require(set(outer) <= {'blobs', 'blobs/sha256', 'index.json', 'manifest.json', 'oci-layout'}
            | {n for n in outer if re.fullmatch('blobs/sha256/[0-9a-f]{64}', n)},
            'archive-unexpected-path')
    for name, data in blobs.items():
        if name.startswith('blobs/'):
            require(sha(data) == name.split('/')[-1], 'blob-digest')
    require(json_value(blobs['oci-layout']) == {'imageLayoutVersion': '1.0.0'}, 'oci-layout')
    entry = json_value(blobs['index.json'])
    require(entry.get('schemaVersion') == 2 and len(entry['manifests']) == 1, 'oci-entry')
    root = entry['manifests'][0]
    require(root['digest'] == expected['Id'] and root['mediaType'] == INDEX, 'candidate-index')
    index = json_value(descriptor(root, blobs))
    require(index.get('schemaVersion') == 2 and index.get('mediaType') == INDEX, 'oci-index')
    platforms = [d for d in index['manifests']
                 if d.get('platform') == {'architecture': 'arm64', 'os': 'linux', 'variant': 'v8'}]
    require(len(platforms) == 1, 'selected-platform-count')
    platform = platforms[0]
    require(platform['mediaType'] == MANIFEST, 'platform-media-type')
    manifest = json_value(descriptor(platform, blobs))
    require(manifest.get('schemaVersion') == 2 and manifest.get('mediaType') == MANIFEST
            and len(manifest['layers']) == 1, 'single-layer-manifest')
    config = json_value(descriptor(manifest['config'], blobs))
    require(config.get('architecture') == 'arm64' and config.get('os') == 'linux'
            and config.get('variant') == 'v8', 'platform-config')
    require(config.get('config', {}).get('Env') == [
        'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'], 'image-env-not-allowed')
    layer = manifest['layers'][0]
    retained_digests = {root['digest'], platform['digest'], manifest['config']['digest'], layer['digest']}
    require(layer['mediaType'] == LAYER, 'layer-media-type')
    compressed = descriptor(layer, blobs)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        plain = stream.read(LAYER_LIMIT + 1)
    require(len(plain) <= LAYER_LIMIT, 'expanded-layer-limit')
    diff_ids = ['sha256:' + sha(plain)]
    require(config.get('rootfs') == {'type': 'layers', 'diff_ids': diff_ids}
            and diff_ids == expected['RootFS']['Layers'], 'layer-diff-id')
    legacy = json_value(blobs['manifest.json'])
    require(type(legacy) is list and len(legacy) == 1
            and legacy[0]['Config'] == 'blobs/sha256/' + manifest['config']['digest'][7:]
            and legacy[0]['Layers'] == ['blobs/sha256/' + layer['digest'][7:]], 'legacy-manifest')
    rows, content = tar_members(plain, rootfs=True)
    packages, checked, mismatches = apk_records(content['lib/apk/db/installed'], rows, content)
    executables = []
    for path in ('bin/busybox', 'lib/ld-musl-aarch64.so.1'):
        require(path in content and int(rows[path]['mode'], 8) & 0o111, 'required-executable')
        require(rows[path]['uid'] == rows[path]['gid'] == 0, 'execution-owner')
        executables.append({'path': path, 'bytes': len(content[path]),
                            'sha256': sha(content[path]), 'elf': elf(content[path])})
    aliases = {path: resolve(rows, path) for path in
               ('bin/sh', 'usr/bin/env', 'usr/bin/timeout', 'lib/libc.musl-aarch64.so.1')}
    require(all(aliases[p] == 'bin/busybox' for p in ('bin/sh', 'usr/bin/env', 'usr/bin/timeout'))
            and aliases['lib/libc.musl-aarch64.so.1'] == 'lib/ld-musl-aarch64.so.1',
            'execution-alias-drift')
    attestations = []
    for desc in index['manifests']:
        if desc.get('annotations', {}).get('vnd.docker.reference.digest') != platform['digest']:
            continue
        att = json_value(descriptor(desc, blobs))
        descriptor(att['config'], blobs)
        retained_digests.update((desc['digest'], att['config']['digest']))
        for statement_desc in att['layers']:
            retained_digests.add(statement_desc['digest'])
            require(statement_desc['mediaType'] == 'application/vnd.in-toto+json', 'attestation-media')
            statement = json_value(descriptor(statement_desc, blobs))
            require(statement.get('_type') == 'https://in-toto.io/Statement/v0.1'
                    and statement.get('subject')
                    and all(s.get('digest') == {'sha256': platform['digest'][7:]}
                            for s in statement['subject']), 'attestation-subject')
            require(statement_desc.get('annotations', {}).get('in-toto.io/predicate-type')
                    == statement.get('predicateType'), 'attestation-predicate-binding')
            predicate = statement.get('predicate', {})
            record = {'blob': statement_desc['digest'], 'predicate_type': statement.get('predicateType'),
                      'subject_digest': platform['digest'], 'authentication': 'not-established'}
            if statement.get('predicateType') == 'https://slsa.dev/provenance/v0.2':
                record.update(materials=predicate.get('materials'),
                              config_source=predicate.get('invocation', {}).get('configSource'))
            elif statement.get('predicateType') == 'https://spdx.dev/Document':
                apk = [p for p in predicate.get('packages', []) if any(
                    r.get('referenceLocator', '').startswith('pkg:apk/')
                    for r in p.get('externalRefs', []))]
                sbom = sorted((p.get('name'), p.get('versionInfo')) for p in apk)
                actual = sorted((p['name'], p['version']) for p in packages)
                actual_set = set(actual)
                installed_ids = {p.get('SPDXID'): (p.get('name'), p.get('versionInfo'))
                                 for p in apk if p.get('SPDXID')
                                 and (p.get('name'), p.get('versionInfo')) in actual_set}
                origins = {(p['origin'], p['version']) for p in packages}
                extras = []
                for p in apk:
                    identity = (p.get('name'), p.get('versionInfo'))
                    if identity in actual_set:
                        continue
                    parents = [installed_ids[r['spdxElementId']]
                               for r in predicate.get('relationships', [])
                               if r.get('relationshipType') == 'GENERATED_FROM'
                               and r.get('relatedSpdxElement') == p.get('SPDXID')
                               and r.get('spdxElementId') in installed_ids]
                    extras.append({'name': identity[0], 'version': identity[1],
                                   'declared_source_origin': identity in origins and bool(parents),
                                   'declared_generated_from_by': sorted(parents)})
                record.update(apk_package_versions=sbom, matches_apk_database=sbom == actual,
                              installed_packages_covered=actual_set <= set(sbom),
                              additional_records=sorted(extras, key=lambda p: (p['name'], p['version'])))
            else:
                raise ValueError('unreviewed-attestation-predicate')
            attestations.append(record)
    require(len(attestations) == 2 and {a['predicate_type'] for a in attestations}
            == {'https://slsa.dev/provenance/v0.2', 'https://spdx.dev/Document'},
            'selected-attestation-count')
    require({n for n in blobs if n.startswith('blobs/sha256/')}
            == {'blobs/sha256/' + d[7:] for d in retained_digests}, 'unreferenced-or-other-platform-blob')
    inventory = [rows[p] for p in sorted(rows)]
    return {'scope': 'offline-selected-platform-byte-consistency-only',
            'index_digest': root['digest'], 'platform_digest': platform['digest'],
            'config_digest': manifest['config']['digest'], 'compressed_layer_digest': layer['digest'],
            'diff_ids': diff_ids, 'expanded_tar_bytes': len(plain),
            'unretained_other_platform_descriptors': sum(
                d['digest'] not in retained_digests for d in index['manifests']),
            'platform_annotations': manifest.get('annotations', {}),
            'config': {k: config[k] for k in ('architecture', 'os', 'variant', 'rootfs', 'config')},
            'history_count': len(config.get('history', [])),
            'inventory': inventory, 'packages': packages,
            'apk_file_checksums_checked': checked, 'apk_checksum_mismatches': mismatches,
            'package_file_check': 'mismatches-found' if mismatches else 'listed-checksums-match',
            'executables': executables,
            'execution_aliases': aliases, 'attestations': attestations,
            'license_file_paths': [p for p in sorted(rows)
                                   if re.search(r'(^|/)(copying|copyright|licen[cs]e)(\.|$)', p, re.I)],
            'image_acceptance': 'not-accepted', 'execution_ready': False,
            'runtime_qualification': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--archive-sha256', required=True)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        require(re.fullmatch('[0-9a-f]{64}', args.archive_sha256), 'archive-sha256-shape')
        require(args.archive.is_file() and args.archive.stat().st_size <= ARCHIVE_LIMIT,
                'archive-size-limit')
        with args.archive.open('rb') as stream:
            raw = stream.read(ARCHIVE_LIMIT + 1)
        require(len(raw) <= ARCHIVE_LIMIT and sha(raw) == args.archive_sha256, 'archive-digest')
        with args.candidate.open('rb') as stream:
            candidate_raw = stream.read(JSON_LIMIT + 1)
        result = inspect(raw, json_value(candidate_raw))
        result.update(format='radishaxiom-private-linux-channel-image-inspection', version='0.1',
                      archive={'bytes': len(raw), 'sha256': sha(raw)},
                      method_sha256=sha(Path(__file__).read_bytes()),
                      candidate_sha256=sha(candidate_raw))
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
        if result['apk_checksum_mismatches'] or any(
                a.get('matches_apk_database') is False for a in result['attestations']):
            print('offline inspection retained: package metadata mismatch; image not-accepted')
            return 2
        print('offline image consistency checked; no extraction/execution; image not-accepted')
        return 0
    except (ValueError, OSError, KeyError, TypeError, tarfile.TarError, UnicodeError) as exc:
        reason = str(exc) if type(exc) is ValueError and re.fullmatch('[a-z0-9-]+', str(exc)) else type(exc).__name__
        if isinstance(exc, OSError):
            reason += ':errno=' + str(exc.errno)
        print('offline image inspection failed: ' + reason)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
