#!/usr/bin/env python3
"""Synthetic rejection checks for the private, intentionally blocked C0 v0.2 selection."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('cvc5_c0_check', Path(__file__).with_name('check-cvc5-c0-input-selection.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.value = checker.expected()

    def check_mutation(self, change):
        change(self.value)
        with self.assertRaises(ValueError):
            checker.check(json.dumps(self.value).encode())

    def test_draft_does_not_mean_ready(self):
        result = checker.check(json.dumps(self.value).encode())
        self.assertTrue(result['selection_consistent'])
        self.assertFalse(result['build_ready'])

    def test_scope_promotion(self):
        self.check_mutation(lambda v: v.update(executable=True))

    def test_boolean_type(self):
        self.check_mutation(lambda v: v.update(executable=0))

    def test_false_accepted(self):
        self.check_mutation(lambda v: v.update(original_cli_acceptance='accepted'))

    def test_false_archive_authentication(self):
        self.check_mutation(lambda v: v['source_archives'][0].update(raw_digest='sha256:' + 'a' * 64))

    def test_duplicate_component(self):
        self.check_mutation(lambda v: v['source_archives'].append(copy.deepcopy(v['source_archives'][0])))

    def test_false_sdk_version(self):
        self.check_mutation(lambda v: v['sdk']['items'][0].update(selected_package_names=['gcc-11']))

    def test_archive_expected_hash_drift(self):
        self.check_mutation(lambda v: v['source_archives'][1].update(expected_archive_sha256='a' * 64))

    def test_budget_change(self):
        self.check_mutation(lambda v: v['future_acquisition'].update(sdk_package_max_total_bytes=2 ** 40))

    def test_legacy_draft_requires_explicit_regeneration(self):
        self.value['version'] = '0.1'
        with self.assertRaisesRegex(ValueError, 'legacy-selection-version-requires-regeneration'):
            checker.check(json.dumps(self.value).encode())

    def test_false_metadata_authentication(self):
        self.check_mutation(lambda v: v['sdk'].update(metadata_authentication='authenticated'))

    def test_false_package_content_acceptance(self):
        self.check_mutation(lambda v: v['sdk'].update(package_contents_acceptance='accepted'))

    def test_sdk_result_hash_drift(self):
        self.check_mutation(lambda v: v['sdk']['selection_record'].update(raw_digest='sha256:' + 'a' * 64))

    def test_metadata_result_source_drift(self):
        self.check_mutation(lambda v: v['sdk']['metadata_record'].update(path='other.json'))

    def test_metadata_closure_does_not_grant_package_download(self):
        self.assertTrue(self.value['metadata_acquisition']['authorized'])
        self.assertFalse(self.value['future_acquisition']['sdk_package_acquisition_authorized'])
        self.check_mutation(lambda v: v['future_acquisition'].update(sdk_package_acquisition_authorized=True))

    def test_retained_observation_omission(self):
        self.check_mutation(lambda v: v['rechecked_retained_observations'].pop())

    def test_invalid_json_utf8_and_nonfinite(self):
        for raw in (b'{', b'\xff', b'{"format":NaN}', b'null', b'[]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                checker.check(raw)

    def test_duplicate_key(self):
        with self.assertRaises(ValueError):
            checker.check(b'{"executable":false,"executable":true}')

    def test_size_limit(self):
        with self.assertRaises(ValueError):
            checker.check(b' ' * (checker.LIMIT + 1))


if __name__ == '__main__':
    unittest.main()
