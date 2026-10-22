#!/usr/bin/env python3
"""Synthetic rejection checks for the private, intentionally blocked C0 v0.3 selection."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('cvc5_c0_check', Path(__file__).with_name('check-cvc5-c0-input-selection.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
generator_spec = importlib.util.spec_from_file_location('cvc5_c0_generate_test',
    Path(__file__).with_name('generate-cvc5-c0-input-selection.py'))
generator = importlib.util.module_from_spec(generator_spec)
generator_spec.loader.exec_module(generator)


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
        for version in ('0.1', '0.2'):
            with self.subTest(version=version):
                self.value['version'] = version
                with self.assertRaisesRegex(ValueError, 'legacy-selection-version-requires-regeneration'):
                    checker.check(json.dumps(self.value).encode())

    def test_obtained_source_is_not_license_acceptance(self):
        self.check_mutation(lambda v: v['source_archives'][0].update(license_acceptance='accepted'))

    def test_source_bytes_cannot_revert_to_unobtained(self):
        self.check_mutation(lambda v: v['source_archives'][0].update(bytes=None, raw_digest=None))

    def test_source_record_reference_drift(self):
        self.check_mutation(lambda v: v['source_review_record'].update(raw_digest='sha256:' + 'a' * 64))

    def test_static_configuration_is_not_dynamic(self):
        self.check_mutation(lambda v: v['configuration'].update(production_expansion='configured'))

    def test_patch_candidate_is_not_executed(self):
        self.check_mutation(lambda v: v['configuration'].update(patch_status='executed'))

    def test_patch_bytes_reference_drift(self):
        self.check_mutation(lambda v: v['configuration']['source_patch'].update(raw_digest='sha256:' + 'a' * 64))

    def test_production_record_reference_drift(self):
        self.check_mutation(lambda v: v['configuration']['production_review_record'].update(bytes=1))

    def test_patch_review_reference_drift(self):
        self.check_mutation(lambda v: v['configuration']['patch_review_record'].update(path='other.json'))

    def test_auto_download_remains_disabled(self):
        self.check_mutation(lambda v: v['configuration'].update(auto_download=True))

    def reject_review_mutation(self, filename, change):
        read_record = generator.read_sdk_record
        def mutated(relative):
            raw, data = read_record(relative)
            if relative.endswith('/' + filename):
                change(data)
            return raw, data
        with patch.object(generator, 'read_sdk_record', side_effect=mutated):
            with self.assertRaises(ValueError):
                generator.generate()

    def test_source_review_acceptance_promotions_rejected_at_input(self):
        for key, value in (('build_ready', True), ('tool_acceptance', 'accepted'),
                ('license_acceptance', 'accepted'), ('executed_upstream_programs', True),
                ('signature_authentication', 'authenticated'), ('scope', 'configured')):
            with self.subTest(key=key):
                self.reject_review_mutation('source-inputs.json', lambda v: v.update({key: value}))

    def test_source_review_duplicate_or_missing_component_rejected(self):
        for change in (lambda v: v['sources'].pop(),
                       lambda v: v['sources'].__setitem__(1, copy.deepcopy(v['sources'][0]))):
            self.reject_review_mutation('source-inputs.json', change)

    def test_production_review_execution_promotions_rejected_at_input(self):
        for key in ('build_ready', 'configuration_executed', 'build_executed',
                    'probe_executed', 'solver_executed', 'tool_accepted'):
            with self.subTest(key=key):
                self.reject_review_mutation('production-review.json', lambda v: v.update({key: True}))

    def test_production_review_status_and_new_roots_rejected_at_input(self):
        for change in (lambda v: v.update(status='configured'),
                       lambda v: v['new_required_sdk_roots'].pop(),
                       lambda v: v['source_input_record'].update(bytes=1)):
            self.reject_review_mutation('production-review.json', change)

    def test_patch_review_acceptance_or_execution_rejected_at_input(self):
        for key, value in (('build_ready', True), ('acceptance', 'accepted'),
                ('patch_state', 'executed'), ('scope', 'configured'),
                ('executed', ['CMake']), ('actual_dependency_manifest', {}),
                ('actual_sdk_archive_inputs', {})):
            with self.subTest(key=key):
                self.reject_review_mutation('patch-review.json', lambda v: v.update({key: value}))

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
