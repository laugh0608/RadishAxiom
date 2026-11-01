#!/usr/bin/env python3
"""Synthetic archive/adversarial checks only; no Docker, network or ELF execution."""
import base64
import copy
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import struct
import tarfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('channel_image', Path(__file__).with_name('inspect-linux-channel-image.py'))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
REFERENCE_SPEC = importlib.util.spec_from_file_location('source_tree', Path(__file__).with_name('check-linux-channel-source-tree.py'))
R = importlib.util.module_from_spec(REFERENCE_SPEC)
REFERENCE_SPEC.loader.exec_module(R)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def archive(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as out:
        for name, kind, data, mode, uid, gid in entries:
            item = tarfile.TarInfo(name)
            item.mode, item.uid, item.gid = mode, uid, gid
            item.type = kind
            if kind == tarfile.REGTYPE:
                item.size = len(data)
                out.addfile(item, io.BytesIO(data))
            else:
                if kind == tarfile.SYMTYPE:
                    item.linkname = data
                out.addfile(item)
    return stream.getvalue()


def minimal_elf():
    ident = b'\x7fELF\x02\x01\x01' + b'\0' * 9
    return (struct.pack('<16sHHIQQQIHHHHHH', ident, 3, 183, 1, 0x1000, 64, 0, 0,
                        64, 56, 1, 0, 0, 0)
            + struct.pack('<IIQQQQQQ', 1, 5, 0, 0x1000, 0x1000, 120, 120, 4096))


def fixture(mismatch=False, env=None, subject_bad=False, sbom_bad=False, source_extra=False):
    binary = minimal_elf()
    checksum = base64.b64encode(hashlib.sha1(binary).digest()).decode()
    origin = 'source-origin' if source_extra else 'busybox'
    db = ('P:busybox\nV:1.0-r0\nA:aarch64\nL:GPL-2.0-only\no:' + origin + '\nc:'
          + '0' * 40 + '\nF:bin\nR:busybox\nZ:Q1' + checksum + '\n')
    if mismatch:
        db += 'F:etc\nR:synthetic\nZ:Q1' + base64.b64encode(hashlib.sha1(b'old').digest()).decode() + '\n'
    files = {'bin/busybox': binary, 'lib/ld-musl-aarch64.so.1': binary,
             'lib/apk/db/installed': db.encode(), 'etc/synthetic': b'new'}
    links = {'bin/sh': '/bin/busybox', 'usr/bin/env': '/bin/busybox',
             'usr/bin/timeout': '/bin/busybox', 'lib/libc.musl-aarch64.so.1': 'ld-musl-aarch64.so.1'}
    dirs = {str(p) for n in files | links for p in PurePosixPath(n).parents if str(p) != '.'}
    rows = [(p, tarfile.DIRTYPE, b'', 0o755, 0, 0) for p in sorted(dirs)]
    rows += [(p, tarfile.REGTYPE, b, 0o755 if p in ['bin/busybox', 'lib/ld-musl-aarch64.so.1'] else 0o644, 0, 0)
             for p, b in sorted(files.items())]
    rows += [(p, tarfile.SYMTYPE, target, 0o777, 0, 0) for p, target in sorted(links.items())]
    plain = archive(rows)
    blobs = {}

    def blob(raw, media):
        digest = hashlib.sha256(raw).hexdigest()
        blobs['blobs/sha256/' + digest] = raw
        return {'digest': 'sha256:' + digest, 'size': len(raw), 'mediaType': media}

    config = {'architecture': 'arm64', 'os': 'linux', 'variant': 'v8',
              'config': {'Env': env if env is not None else [
                  'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin']},
              'rootfs': {'type': 'layers', 'diff_ids': ['sha256:' + hashlib.sha256(plain).hexdigest()]}}
    cfg = blob(encoded(config), 'application/vnd.oci.image.config.v1+json')
    layer = blob(gzip.compress(plain, mtime=0), M.LAYER)
    platform = blob(encoded({'schemaVersion': 2, 'mediaType': M.MANIFEST,
                             'config': cfg, 'layers': [layer]}), M.MANIFEST)
    platform['platform'] = {'architecture': 'arm64', 'os': 'linux', 'variant': 'v8'}
    statement_layers = []
    sbom_packages = [{'name': 'busybox', 'SPDXID': 'SPDX-binary',
                      'versionInfo': '9.0-r0' if sbom_bad else '1.0-r0',
                      'externalRefs': [{'referenceLocator': 'pkg:apk/alpine/busybox@1.0-r0'}]}]
    relationships = []
    if source_extra:
        sbom_packages.append({'name': 'source-origin', 'versionInfo': '1.0-r0', 'SPDXID': 'SPDX-source',
                              'externalRefs': [{'referenceLocator': 'pkg:apk/alpine/source-origin@1.0-r0'}]})
        relationships.append({'spdxElementId': 'SPDX-binary', 'relatedSpdxElement': 'SPDX-source',
                              'relationshipType': 'GENERATED_FROM'})
    for predicate, value in [
        ('https://slsa.dev/provenance/v0.2', {'materials': []}),
        ('https://spdx.dev/Document', {'packages': sbom_packages, 'relationships': relationships})]:
        subject = 'f' * 64 if subject_bad else platform['digest'][7:]
        desc = blob(encoded({'_type': 'https://in-toto.io/Statement/v0.1',
                             'subject': [{'digest': {'sha256': subject}}],
                             'predicateType': predicate, 'predicate': value}), 'application/vnd.in-toto+json')
        desc['annotations'] = {'in-toto.io/predicate-type': predicate}
        statement_layers.append(desc)
    attest = blob(encoded({'schemaVersion': 2, 'mediaType': M.MANIFEST,
                          'config': blob(b'{}', 'application/vnd.oci.image.config.v1+json'),
                          'layers': statement_layers}), M.MANIFEST)
    attest['annotations'] = {'vnd.docker.reference.digest': platform['digest']}
    root = blob(encoded({'schemaVersion': 2, 'mediaType': M.INDEX,
                         'manifests': [platform, attest]}), M.INDEX)
    blobs.update({'index.json': encoded({'schemaVersion': 2, 'manifests': [root]}),
                  'oci-layout': encoded({'imageLayoutVersion': '1.0.0'}),
                  'manifest.json': encoded([{'Config': 'blobs/sha256/' + cfg['digest'][7:],
                                            'Layers': ['blobs/sha256/' + layer['digest'][7:]]}])})
    outer = [('blobs', tarfile.DIRTYPE, b'', 0o755, 0, 0),
             ('blobs/sha256', tarfile.DIRTYPE, b'', 0o755, 0, 0)]
    outer += [(p, tarfile.REGTYPE, b, 0o644, 0, 0) for p, b in sorted(blobs.items())]
    candidate = {'scope': 'local-docker-metadata-only-not-accepted',
                 'selected_candidate_metadata': {'Id': root['digest'], 'Os': 'linux',
                 'Architecture': 'arm64', 'RootFS': {'Layers': config['rootfs']['diff_ids']}}}
    return archive(outer), candidate


class ArchiveTests(unittest.TestCase):
    def test_synthetic_graph_never_accepts(self):
        raw, candidate = fixture()
        result = M.inspect(raw, candidate)
        self.assertEqual(result['packages'][0]['name'], 'busybox')
        self.assertEqual(result['apk_file_checksums_checked'], 1)
        self.assertEqual(result['apk_checksum_mismatches'], [])
        self.assertEqual(result['execution_aliases']['usr/bin/timeout'], 'bin/busybox')
        self.assertEqual(result['image_acceptance'], 'not-accepted')
        self.assertIs(result['execution_ready'], False)
        self.assertTrue(next(a for a in result['attestations'] if 'matches_apk_database' in a)['matches_apk_database'])

    def test_candidate_index_and_diff_cannot_be_swapped(self):
        raw, candidate = fixture()
        for key in ['Id', 'RootFS']:
            value = copy.deepcopy(candidate)
            value['selected_candidate_metadata'][key] = ('sha256:' + 'f' * 64 if key == 'Id'
                                                         else {'Layers': ['sha256:' + 'f' * 64]})
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'candidate-index|layer-diff-id'):
                M.inspect(raw, value)

    def test_real_mismatch_is_retained_without_success(self):
        result = M.inspect(*fixture(mismatch=True))
        self.assertEqual(result['package_file_check'], 'mismatches-found')
        self.assertEqual(result['apk_checksum_mismatches'][0]['path'], 'etc/synthetic')
        self.assertEqual(result['apk_checksum_mismatches'][0]['declared_sha1'], hashlib.sha1(b'old').hexdigest())
        self.assertIs(result['runtime_qualification'], False)

    def test_attestation_wrong_subject_rejected(self):
        with self.assertRaisesRegex(ValueError, 'attestation-subject'):
            M.inspect(*fixture(subject_bad=True))

    def test_sbom_conflict_is_visible(self):
        result = M.inspect(*fixture(sbom_bad=True))
        self.assertIs(next(a for a in result['attestations'] if 'matches_apk_database' in a)['matches_apk_database'], False)

    def test_source_origin_declaration_does_not_become_installed_package(self):
        result = M.inspect(*fixture(source_extra=True))
        record = next(a for a in result['attestations'] if 'matches_apk_database' in a)
        self.assertFalse(record['matches_apk_database'])
        self.assertTrue(record['installed_packages_covered'])
        self.assertTrue(record['additional_records'][0]['declared_source_origin'])
        self.assertEqual(len(result['packages']), 1)

    def test_gzip_expansion_budget(self):
        raw, candidate = fixture()
        with patch.object(M, 'LAYER_LIMIT', 4096), self.assertRaisesRegex(ValueError, 'expanded-layer-limit'):
            M.inspect(raw, candidate)

    def test_unreferenced_blob_is_not_silently_ignored(self):
        raw, candidate = fixture()
        entries = []
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as t:
            for member in t:
                entries.append((member.name, member.type, t.extractfile(member).read() if member.isfile() else b'',
                                member.mode, member.uid, member.gid))
        extra = b'unreferenced'
        entries.append(('blobs/sha256/' + hashlib.sha256(extra).hexdigest(), tarfile.REGTYPE, extra, 0o644, 0, 0))
        with self.assertRaisesRegex(ValueError, 'unreferenced-or-other-platform-blob'):
            M.inspect(archive(entries), candidate)

    def test_loader_environment_not_echoed(self):
        with self.assertRaisesRegex(ValueError, '^image-env-not-allowed$'):
            M.inspect(*fixture(env=['LD_PRELOAD=/synthetic/injected']))

    def test_json_duplicates_depth_and_boolean_sizes(self):
        for raw in [b'{"x":1,"x":2}', b'{"x":NaN}', b'[' * 65 + b'0' + b']' * 65]:
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                M.json_value(raw)
        with self.assertRaisesRegex(ValueError, 'descriptor-shape'):
            M.descriptor({'size': False, 'digest': 'sha256:' + '0' * 64}, {})

    def test_descriptor_missing_size_and_digest(self):
        data = b'abc'; digest = hashlib.sha256(data).hexdigest()
        for size, blobs in [(4, {'blobs/sha256/' + digest: data}), (3, {}),
                            (3, {'blobs/sha256/' + digest: b'xyz'})]:
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, 'descriptor-missing'):
                M.descriptor({'size': size, 'digest': 'sha256:' + digest}, blobs)

    def test_tar_paths_duplicates_types_and_owners(self):
        for rows in [
            [('../escape', tarfile.REGTYPE, b'x', 0o644, 0, 0)],
            [('x', tarfile.REGTYPE, b'x', 0o644, 0, 0)] * 2,
            [('x', tarfile.FIFOTYPE, b'', 0o644, 0, 0)],
            [('x', tarfile.REGTYPE, b'x', 0o4755, 0, 0)],
            [('x', tarfile.REGTYPE, b'x', 0o644, 1, 0)]]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                M.tar_members(archive(rows))

    def test_rootfs_group_metadata_preserved(self):
        rows, _ = M.tar_members(archive([('synthetic', tarfile.REGTYPE, b'x', 0o640, 0, 42)]), rootfs=True)
        self.assertEqual(rows['synthetic']['gid'], 42)

    def test_tar_hidden_extension_trailing_and_missing_parent(self):
        raw = archive([('x', tarfile.REGTYPE, b'x', 0o644, 0, 0)])
        for data in [raw[:-512] + b'x' * 512, raw[:512],
                     archive([('x/y', tarfile.REGTYPE, b'x', 0o644, 0, 0)])]:
            with self.assertRaises(ValueError):
                M.tar_members(data)
        changed = bytearray(raw); changed[156] = ord('x')
        with self.assertRaisesRegex(ValueError, 'tar-type-or-extension'):
            M.tar_members(bytes(changed))

    def test_virtual_links_escape_loop_and_nondirectory(self):
        for rows in [{'x': {'kind': 'symlink', 'target': '../outside'}},
                     {'x': {'kind': 'symlink', 'target': 'x'}}]:
            with self.assertRaisesRegex(ValueError, 'link-escape|link-depth'):
                M.resolve(rows, 'x')
        with self.assertRaisesRegex(ValueError, 'nondirectory'):
            M.resolve({'x': {'kind': 'file'}}, 'x/y')

    def test_elf_arch_and_bounds(self):
        self.assertEqual(M.elf(minimal_elf())['type'], 'ET_DYN')
        for raw in [b'not-elf', minimal_elf()[:-1], minimal_elf()[:18] + b'\x3e\0' + minimal_elf()[20:]]:
            with self.assertRaises(ValueError):
                M.elf(raw)


class SourceTreeTests(unittest.TestCase):
    def fixture(self, changed=False, malformed=False):
        src_rows = [('.', tarfile.DIRTYPE, b'', 0o711, 0, 0),
                    ('./synthetic', tarfile.REGTYPE, b'original', 0o640, 0, 42)]
        if malformed:
            src_rows.append(('./unsafe/../escape', tarfile.REGTYPE, b'x', 0o644, 0, 0))
        source = gzip.compress(archive(src_rows), mtime=0)
        layer = gzip.compress(archive([('synthetic', tarfile.REGTYPE,
                                       b'changed' if changed else b'original', 0o640, 0, 42)]), mtime=0)
        layer_sha = hashlib.sha256(layer).hexdigest()
        image = archive([('blobs', tarfile.DIRTYPE, b'', 0o755, 0, 0),
                         ('blobs/sha256', tarfile.DIRTYPE, b'', 0o755, 0, 0),
                         ('blobs/sha256/' + layer_sha, tarfile.REGTYPE, layer, 0o644, 0, 0)])
        checksum = (hashlib.sha512(source).hexdigest()
                    + '  aarch64/alpine-minirootfs-3.23.5-aarch64.tar.gz\n').encode()
        return [image, layer_sha, hashlib.sha256(gzip.decompress(layer)).hexdigest(), source,
                hashlib.sha256(source).hexdigest(),
                hashlib.sha1(b'blob ' + str(len(source)).encode() + b'\0' + source).hexdigest(), checksum]

    def test_normalization_root_metadata_and_scope(self):
        result = R.compare(*self.fixture())
        self.assertTrue(result['relative_trees_equal'])
        self.assertEqual(result['source_count'], 1)
        self.assertEqual(result['source_root_header_not_present_in_image_layer']['mode'], 0o711)
        self.assertIn('runtime root directory metadata', result['not_compared'])
        self.assertIs(result['execution_ready'], False)

    def test_content_difference_is_not_normalized_away(self):
        result = R.compare(*self.fixture(changed=True))
        self.assertFalse(result['relative_trees_equal'])
        self.assertEqual(result['difference_paths'], ['synthetic'])

    def test_source_digest_and_checksum_bindings(self):
        for index, value in [(4, 'f' * 64), (5, 'f' * 40), (6, b'wrong')]:
            args = self.fixture(); args[index] = value
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'source-'):
                R.compare(*args)

    def test_parent_path_and_duplicate_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unsafe-tree-path'):
            R.compare(*self.fixture(malformed=True))
        with self.assertRaisesRegex(ValueError, 'duplicate-or-special'):
            R.tree(archive([('x', tarfile.REGTYPE, b'x', 0o644, 0, 0)] * 2), False)


if __name__ == '__main__':
    unittest.main()
