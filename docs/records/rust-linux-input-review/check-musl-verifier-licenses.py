#!/usr/bin/env python3
"""Synthetic reference mismatch checks; no download or package execution."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('licenses',
    Path(__file__).with_name('inspect-musl-verifier-licenses.py'))
licenses = importlib.util.module_from_spec(spec)
spec.loader.exec_module(licenses)
PREFIX = licenses.PREFIX


class References(unittest.TestCase):
    def fixture(self):
        index = {path: {'type': 'directory'} for path in ['usr', 'usr/share', PREFIX.rstrip('/')]}
        files = {PREFIX + 'GPL-2': b'GNU GENERAL PUBLIC LICENSE\nVersion 2, June 1991\n',
                 PREFIX + 'LGPL-2.1': b'GNU LESSER GENERAL PUBLIC LICENSE\nVersion 2.1, February 1999\n',
                 PREFIX + 'LGPL-3': b'Version 3'}
        index.update({path: {'type': 'file', 'packages': ['test'], **licenses.identity(data)}
                      for path, data in files.items()})
        index[PREFIX + 'LGPL'] = {'type': 'symlink', 'destination': PREFIX + 'LGPL-3'}
        return index, files

    def gpg(self):
        return {'package': 'gpg', 'common_license_references': ['/' + PREFIX + 'GPL-2.0'],
                'text': 'complete text of the GPL license, version 2.0,'}

    def test_missing_path_is_not_repaired_by_text_candidate(self):
        result = licenses.reference_observations([self.gpg()], *self.fixture())[0]
        self.assertEqual(result['literal_resolution']['status'], 'missing')
        self.assertEqual(result['reviewed_text_candidate']['path'], PREFIX + 'GPL-2')
        self.assertFalse(result['literal_path_repaired'])

    def test_no_generic_rewrite_for_other_owners(self):
        owner = {**self.gpg(), 'package': 'other'}
        result = licenses.reference_observations([owner], *self.fixture())[0]
        self.assertEqual(result['literal_resolution']['status'], 'missing')
        self.assertNotIn('reviewed_text_candidate', result)

    def test_changed_declaration_or_target_heading_rejected(self):
        index, files = self.fixture()
        owner = self.gpg()
        with self.assertRaises(ValueError):
            licenses.reference_observations([{**owner, 'text': 'version 3'}], index, files)
        files[PREFIX + 'GPL-2'] = b'Version 3'
        with self.assertRaises(ValueError):
            licenses.reference_observations([owner], index, files)

    def test_alias_and_library_declaration_remain_distinct(self):
        owner = {'package': 'libgcrypt20', 'common_license_references': ['/' + PREFIX + 'LGPL'],
                 'text': 'version 2.1'}
        result = licenses.reference_observations([owner], *self.fixture())[0]
        self.assertEqual(result['literal_resolution']['path'], PREFIX + 'LGPL-3')
        self.assertEqual(result['library_declaration_text_candidate']['path'], PREFIX + 'LGPL-2.1')
        self.assertFalse(result['literal_alias_determines_component_license'])

    def test_missing_alternative_rejected(self):
        index, files = self.fixture()
        del index[PREFIX + 'GPL-2']
        with self.assertRaises(ValueError):
            licenses.reference_observations([self.gpg()], index, files)


if __name__ == '__main__':
    unittest.main()
