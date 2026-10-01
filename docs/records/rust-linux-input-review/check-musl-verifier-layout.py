#!/usr/bin/env python3
"""Synthetic negative checks for the static observation profile; no tool invocation."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('layout',
    Path(__file__).with_name('inspect-musl-verifier-layout.py'))
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


def observation(version='TEST_1', definition=False, weak=False):
    header = '<stdin>:\tfile format elf64-littleaarch64\n'
    if definition:
        header += f'Version definitions:\n1 0x00 0x1234 {version}\n'
    else:
        header += f'Version References:\n  required from libtest.so:\n    0x1234 0x00 02 {version}\n'
    flags = 'g    DF' if definition else ' w   DF' if weak else '     DF'
    section = '.text' if definition else '*UND*'
    token = version if definition else '(' + version + ')'
    return header + f'DYNAMIC SYMBOL TABLE:\n0000000000000000 {flags} {section}\t0000000000000000 {token} example\n'


class Boundaries(unittest.TestCase):
    def fixtures(self):
        rows = {'app': layout.parse_observation(observation()),
                'lib': layout.parse_observation(observation(definition=True))}
        elf = {'app': {'library_path_candidates': {'libtest.so': {'status': 'found', 'path': 'lib'}}},
               'lib': {'library_path_candidates': {}}}
        return rows, elf

    def test_matching_version_and_export_remain_static(self):
        result = layout.compare_versions(*self.fixtures())
        self.assertTrue(result['version_requirements'][0]['definition_matches'])
        self.assertEqual(result['unmatched_versioned_symbols'], [])
        self.assertFalse(result['exact_symbol_provider_binding_assessed'])
        self.assertFalse(result['loader_resolution_assessed'])

    def test_version_missing_or_wrong_hash(self):
        for definitions in [{}, {'TEST_1': '0x9999'}]:
            rows, elf = self.fixtures()
            rows['lib']['definitions'] = definitions
            self.assertFalse(layout.compare_versions(rows, elf)['version_requirements'][0]['definition_matches'])

    def test_version_exists_but_symbol_wrong(self):
        for key, value in [('name', 'different'), ('version', 'TEST_2'), ('exported', False)]:
            rows, elf = self.fixtures()
            rows['lib']['symbols'][0][key] = value
            self.assertEqual(len(layout.compare_versions(rows, elf)['unmatched_versioned_symbols']), 1)

    def test_shared_version_namespace_keeps_candidates(self):
        rows, elf = self.fixtures()
        rows['app']['references']['other.so'] = copy.deepcopy(rows['app']['references']['libtest.so'])
        rows['other'] = copy.deepcopy(rows['lib'])
        rows['other']['symbols'][0]['name'] = 'other'
        elf['app']['library_path_candidates']['other.so'] = {'status': 'found', 'path': 'other'}
        elf['other'] = {'library_path_candidates': {}}
        row = layout.compare_versions(rows, elf)['versioned_symbol_candidates'][0]
        self.assertEqual(row['candidate_providers'], ['lib', 'other'])
        self.assertEqual(row['matching_exports'], ['lib'])

    def test_weak_unresolved_stays_visible(self):
        rows, elf = self.fixtures()
        rows['app'] = layout.parse_observation(observation(weak=True))
        rows['lib']['symbols'] = []
        self.assertTrue(layout.compare_versions(rows, elf)['unmatched_versioned_symbols'][0]['weak'])

    def test_nondefault_export_does_not_satisfy_unversioned_candidate(self):
        rows, elf = self.fixtures()
        rows['app']['symbols'][0]['version'] = None
        rows['lib']['symbols'][0]['default_version'] = False
        result = layout.compare_versions(rows, elf)['unversioned_undefined_symbol_candidates'][0]
        self.assertEqual(result['matching_direct_dependency_exports'], [])

    def test_missing_dependency_rejected(self):
        rows, elf = self.fixtures()
        elf['app']['library_path_candidates'] = {}
        with self.assertRaises(ValueError):
            layout.compare_versions(rows, elf)

    def test_format_drift_rejected(self):
        text = observation()
        for changed in [text.replace('elf64-littleaarch64', 'elf64-x86-64'),
                        text.replace('TEST_1\nDYNAMIC', 'TEST_1 extra\nDYNAMIC'),
                        text + 'unparsed output\n', text.replace('DYNAMIC SYMBOL TABLE:', 'SYMBOL TABLE:'),
                        text.replace('(TEST_1) example', '(TEST_1) .hidden example')]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                layout.parse_observation(changed)


if __name__ == '__main__':
    unittest.main()
