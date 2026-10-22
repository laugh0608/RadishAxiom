#!/usr/bin/env python3
"""Offline acquisition projection and build-input preflight rejection tests."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


PREP = module('cvc5-build-preparation')
BUILD = module('check-cvc5-build-inputs')


def encoded(value):
    return (json.dumps(value, indent=2) + '\n').encode()


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


class AcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sdk = json.loads((ROOT / PREP.C0 / 'sdk-selection.json').read_bytes())

    def test_actual_selection_projection(self):
        rows, summary = PREP.acquisition_entries(self.sdk)
        self.assertEqual(summary, {'binary_files': 172, 'source_files': 328,
                                  'source_versions': 101, 'total_files': 500,
                                  'binary_bytes': 120870556, 'source_bytes': 570734908,
                                  'total_bytes': 691605464})
        self.assertEqual(len({row['relative_path'] for row in rows}), 500)
        self.assertEqual(len({row['url'] for row in rows}), 500)
        self.assertTrue(any(row['kind'] == 'orig' and row['relative_path'].endswith('.asc') for row in rows))

    def test_retained_review_does_not_accept_historical_target(self):
        review = PREP.review_retained_gaps()
        self.assertEqual(len(review['libpoly']['input_files']), 6)
        self.assertIsNone(review['snapshot_release_fields']['Valid-Until'])
        candidate = review['retained_keyring_candidate']
        self.assertEqual(candidate['decoded_bytes'], 55918)
        self.assertTrue(candidate['historical_target_differs'])
        self.assertFalse(candidate['current_signature_verified'])
        self.assertEqual(candidate['trust_for_this_task'], 'not-accepted')

    def test_acquisition_plan_tampering(self):
        original = json.loads(PREP.PLAN.read_bytes())
        mutations = (
            lambda v: v.update(build_ready=True),
            lambda v: v.update(build_ready=0),
            lambda v: v.update(signature_verified=True),
            lambda v: v.update(authorization='approved'),
            lambda v: v['transport_policy'].update(retries=1),
            lambda v: v['entries'][0].update(declared_bytes=1),
            lambda v: v['entries'][0].update(declared_sha256='0' * 64),
            lambda v: v['entries'][0].update(url='https://example.invalid/input'),
            lambda v: v['entries'].pop(),
            lambda v: v['inputs'].pop(),
        )
        with tempfile.TemporaryDirectory(prefix='cvc5-plan-test-', dir=ROOT / '.tmp') as directory:
            path = Path(directory) / 'plan.json'
            with patch.object(PREP, 'generate', return_value=original):
                for index, mutate in enumerate(mutations):
                    with self.subTest(index=index):
                        value = copy.deepcopy(original)
                        mutate(value)
                        path.write_bytes(encoded(value))
                        with self.assertRaisesRegex(ValueError, 'acquisition-plan-drift'):
                            PREP.verify_plan(path)

    def reject(self, change):
        value = copy.deepcopy(self.sdk)
        change(value)
        with self.assertRaises(ValueError):
            PREP.acquisition_entries(value)

    def test_wrong_snapshot(self):
        self.reject(lambda v: v.update(base_url='https://example.invalid/'))

    def test_false_signature_acceptance(self):
        self.reject(lambda v: v.update(signature_verified=True))

    def test_wrong_architecture(self):
        self.reject(lambda v: v['packages'][0].update(Architecture='amd64'))

    def test_duplicate_binary(self):
        self.reject(lambda v: v['packages'].append(v['packages'][0]))

    def test_duplicate_source(self):
        self.reject(lambda v: v['source_packages'].append(v['source_packages'][0]))

    def test_missing_source(self):
        self.reject(lambda v: v['source_packages'].pop())

    def test_conflicting_shared_source(self):
        def mutate(v):
            other = copy.deepcopy(v['source_packages'][0])
            other['Version'] += '+synthetic'
            other['files'][0]['sha256'] = '0' * 64
            v['source_packages'].append(other)
        self.reject(mutate)

    def test_url_path_disagreement(self):
        self.reject(lambda v: v['packages'][0].update(package_url=PREP.BASE + 'pool/main/x/other.deb'))

    def test_traversal(self):
        self.reject(lambda v: v['packages'][0].update(Filename='pool/main/../evil', package_url=PREP.BASE + 'pool/main/../evil'))

    def test_boolean_size(self):
        self.reject(lambda v: v['packages'][0].update(Size=True))

    def test_invalid_hash(self):
        self.reject(lambda v: v['packages'][0].update(SHA256='0' * 63))

    def test_summary_not_recomputed_to_hide_drift(self):
        self.reject(lambda v: v['summary'].update(binary_declared_bytes=1))

    def test_unobtained_cannot_be_promoted(self):
        self.reject(lambda v: v['packages'][0].update(package_status='accepted'))


class ArchiveAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cvc5-c1-test-', dir=ROOT / '.tmp')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        self.raw = b'synthetic raw archive bytes; never extracted or executed\n'
        self.row = PREP.entry('binary', PREP.BASE + 'pool/main/s/synthetic/input.deb',
                              len(self.raw), hashlib.sha256(self.raw).hexdigest(), {})
        self.plan = {'entries': [self.row]}
        self.path = self.directory / self.row['relative_path']

    def materialize(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(self.raw)

    def test_missing_is_not_success(self):
        result = PREP.audit_archives(self.plan, self.directory)
        self.assertFalse(result['archive_bytes_complete'])
        self.assertEqual(result['missing_files'], [self.row['relative_path']])

    def test_matching_bytes_are_not_acceptance(self):
        self.materialize()
        result = PREP.audit_archives(self.plan, self.directory)
        self.assertTrue(result['archive_bytes_complete'])
        self.assertFalse(result['build_ready'])
        self.assertFalse(result['signature_verified'])
        self.assertEqual(result['input_acceptance'], 'not-accepted')

    def test_truncated_and_same_length_corrupt(self):
        self.materialize()
        for raw in (self.raw[:-1], b'x' * len(self.raw)):
            self.path.write_bytes(raw)
            with self.assertRaises(ValueError):
                PREP.audit_archives(self.plan, self.directory)

    def test_extra_file(self):
        self.materialize()
        self.path.with_name('extra.deb').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'extra-or-special'):
            PREP.audit_archives(self.plan, self.directory)

    def test_extra_empty_directory(self):
        (self.directory / 'inputs/extra').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'extra-input-directory'):
            PREP.audit_archives(self.plan, self.directory)

    def test_symlink_parent(self):
        (self.directory / 'inputs').symlink_to(self.directory, target_is_directory=True)
        with self.assertRaises(ValueError):
            PREP.audit_archives(self.plan, self.directory)

    def test_special_file(self):
        self.path.parent.mkdir(parents=True)
        os.mkfifo(self.path)
        with self.assertRaisesRegex(ValueError, 'extra-or-special'):
            PREP.audit_archives(self.plan, self.directory)


class BuildInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cvc5-c2-test-', dir=ROOT / '.tmp')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        self.manifest = self.directory / 'manifest.json'
        self.closure = self.directory / 'closure.json'
        self.value = {'format': 'radishaxiom-cvc5-private-build-inputs', 'version': '0.1',
                      'upstream_commit': BUILD.COMMIT, 'target_abi': BUILD.TARGET,
                      'versions': dict(BUILD.VERSIONS), 'review_state': 'reviewed-for-configuration',
                      'archives': {}, 'header_roots': {},
                      'editline_link_order': ['editline', 'bsd', 'tinfo', 'bsd']}
        # Deliberately synthetic non-ELF bytes: a passing byte check must not
        # imply archive-object ABI, license, compiler or tool acceptance.
        for role in sorted(BUILD.CORE_ARCHIVES | {'editline', 'bsd', 'tinfo'}):
            path = self.directory / (role + '.a')
            path.write_bytes(b'synthetic-non-ELF-' + role.encode())
            self.value['archives'][role] = identity(path)
        for role, required in BUILD.HEADERS.items():
            root, files = self.directory / role, []
            for relative in sorted(required):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'synthetic-header-' + relative.encode())
                files.append(dict(identity(path), path=relative))
            self.value['header_roots'][role] = {'path': str(root), 'files': files}

    def write(self, bind=True):
        if bind:
            review = {field: self.value[field] for field in BUILD.BINDINGS}
            review.update(review_state='static-closure-and-abi-reviewed', evidence='synthetic-test-only')
            self.closure.write_bytes(encoded(review))
            self.value['closure_review'] = identity(self.closure)
        raw = encoded(self.value)
        self.manifest.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def check(self):
        return BUILD.check(self.manifest, self.write())

    def reject(self, change):
        change(self.value)
        with self.assertRaises(ValueError):
            self.check()

    def test_byte_success_keeps_all_execution_gates(self):
        result = self.check()
        self.assertTrue(result['byte_preflight_passed'])
        self.assertEqual(result['editline_link_order'], ['editline', 'bsd', 'tinfo', 'bsd'])
        self.assertFalse(result['abi_verified'])
        self.assertFalse(result['configuration_executed'])
        self.assertFalse(result['build_ready'])
        self.assertEqual(result['tool_acceptance'], 'not-accepted')

    def test_wrong_manifest_hash(self):
        self.write()
        with self.assertRaisesRegex(ValueError, 'manifest-hash'):
            BUILD.check(self.manifest, '0' * 64)

    def test_unknown_root_field(self):
        self.reject(lambda v: v.update(build_ready=True))

    def test_duplicate_json_key(self):
        self.write()
        raw = self.manifest.read_bytes().replace(b'"version": "0.1",', b'"version": "0.1", "version": "0.1",')
        self.manifest.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'duplicate-json-key'):
            BUILD.check(self.manifest, hashlib.sha256(raw).hexdigest())

    def test_json_budget(self):
        self.write()
        with patch.object(BUILD, 'JSON_LIMIT', 8):
            with self.assertRaisesRegex(ValueError, 'json-size-budget'):
                BUILD.check(self.manifest, '0' * 64)

    def test_manifest_identity_version_abi_review(self):
        for field in ('format', 'version', 'upstream_commit', 'target_abi', 'review_state'):
            with self.subTest(field=field):
                saved = self.value[field]
                self.reject(lambda v: v.update({field: 'wrong'}))
                self.value[field] = saved

    def test_source_version(self):
        self.reject(lambda v: v['versions'].update(gmp='6.2.1'))

    def test_closure_same_files_wrong_order(self):
        self.write()
        self.value['editline_link_order'].reverse()
        sha = self.write(bind=False)
        with self.assertRaisesRegex(ValueError, 'closure-binding-mismatch:editline_link_order'):
            BUILD.check(self.manifest, sha)

    def test_closure_false_state(self):
        self.write()
        review = json.loads(self.closure.read_bytes())
        review['review_state'] = 'not-reviewed'
        self.closure.write_bytes(encoded(review))
        self.value['closure_review'] = identity(self.closure)
        sha = self.write(bind=False)
        with self.assertRaisesRegex(ValueError, 'closure-review-state'):
            BUILD.check(self.manifest, sha)

    def test_boolean_bytes(self):
        self.reject(lambda v: v['archives']['gmp'].update(bytes=True))

    def test_path_traversal(self):
        self.reject(lambda v: v['header_roots']['gmp']['files'][0].update(path='../gmp/gmp.h'))

    def test_duplicate_header(self):
        self.reject(lambda v: v['header_roots']['gmp']['files'].append(v['header_roots']['gmp']['files'][0]))

    def test_extra_unlisted_header(self):
        (self.directory / 'gmp/extra.h').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'extra-or-missing-header'):
            self.check()

    def test_required_header_missing_even_with_consistent_inventory(self):
        root = self.directory / 'gmp'
        (root / 'gmp.h').rename(root / 'wrong.h')
        self.value['header_roots']['gmp']['files'][0]['path'] = 'wrong.h'
        with self.assertRaisesRegex(ValueError, 'required-header-missing'):
            self.check()

    def test_header_symlink(self):
        (self.directory / 'gmp/extra').symlink_to(self.directory / 'gmp', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'header-tree-symlink'):
            self.check()

    def test_archive_symlink(self):
        path = self.directory / 'alias.a'
        path.symlink_to(self.directory / 'gmp.a')
        self.reject(lambda v: v['archives']['gmp'].update(path=str(path)))

    def test_archive_fifo(self):
        path = self.directory / 'special.a'
        os.mkfifo(path)
        self.reject(lambda v: v['archives']['gmp'].update(path=str(path)))

    def test_file_hash_mismatch(self):
        self.reject(lambda v: v['archives']['gmp'].update(sha256='0' * 64))

    def test_missing_archive(self):
        self.reject(lambda v: v['archives'].pop('gmp'))

    def test_unconsumed_archive(self):
        self.reject(lambda v: v['editline_link_order'].remove('tinfo'))

    def test_core_archive_in_editline_order(self):
        self.reject(lambda v: v['editline_link_order'].append('gmp'))

    def test_link_order_budget(self):
        self.reject(lambda v: v.update(editline_link_order=['editline'] * 33))

    def test_cumulative_budget(self):
        with patch.object(BUILD, 'TOTAL_LIMIT', 16):
            with self.assertRaisesRegex(ValueError, 'total-input-budget'):
                self.check()

    def test_tree_budget(self):
        with patch.object(BUILD, 'ENTRY_LIMIT', 2):
            with self.assertRaisesRegex(ValueError, 'budget'):
                self.check()


if __name__ == '__main__':
    unittest.main()
