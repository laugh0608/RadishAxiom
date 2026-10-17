#!/usr/bin/env python3
"""Synthetic refusals for the C0 retained-source binding checker."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'production_review', Path(__file__).with_name('check-cvc5-production-source-review.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = b'# synthetic static input only\n'
        self.record = json.loads(checker.RECORD.read_text())
        identities = {name: (location, checker.digest(self.raw)[7:])
                      for name, (location, _) in checker.IDENTITIES.items()}
        self.patcher = patch.dict(checker.IDENTITIES, identities, clear=True)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

        def write(relative):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.raw)
            return {'path': relative, 'bytes': len(self.raw), 'raw_digest': checker.digest(self.raw)}

        for row in self.record['source_identities']:
            row['archive'] = write(row['archive']['path'])
            row['tree_inventory'] = write(row['tree_inventory']['path'])
        for row in self.record['source_files'].values():
            identity = write(row['retained_path'])
            row.update(bytes=identity['bytes'], raw_digest=identity['raw_digest'],
                       excerpts=[{'start': 1, 'end': 1, 'text': self.raw.decode().strip()}])
        for row in self.record['python_generators']:
            row['imports'] = []
        for row in self.record['source_identities']:
            component = row['id']
            top = checker.IDENTITIES[component][0].split('/', 1)[1]
            entries = [{'path': top + '/' + name.split('/', 1)[1], 'kind': 'file',
                        'bytes': len(self.raw), 'sha256': checker.digest(self.raw)[7:]}
                       for name in self.record['source_files'] if name.startswith(component + '/')]
            inventory = {'source_id': component, 'archive': row['archive'], 'entries': entries}
            raw = json.dumps(inventory).encode()
            path = self.root / row['tree_inventory']['path']
            path.write_bytes(raw)
            row['tree_inventory'].update(bytes=len(raw), raw_digest=checker.digest(raw))
        path = self.root / checker.INPUTS
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps({'sources': self.record['source_identities']}).encode()
        path.write_bytes(raw)
        self.record['source_input_record'] = {
            'path': checker.INPUTS, 'bytes': len(raw), 'raw_digest': checker.digest(raw)}
        self.source = self.root / self.record['source_files']['cvc5/configure.sh']['retained_path']

    def test_binding(self):
        self.assertEqual(checker.verify(self.record, self.root), 62)

    def test_tampered_source(self):
        self.source.write_bytes(self.raw.replace(b'static', b'dynamic'))
        with self.assertRaisesRegex(ValueError, 'source bytes differ'):
            checker.verify(self.record, self.root)

    def test_tampered_excerpt(self):
        row = copy.deepcopy(self.record)
        row['source_files']['cvc5/configure.sh']['excerpts'][0]['text'] = 'set(ENABLE_SAFE_MODE ON)'
        with self.assertRaisesRegex(ValueError, 'excerpt differs'):
            checker.verify(row, self.root)

    def test_source_and_review_changed_together(self):
        row = copy.deepcopy(self.record)
        raw = b'# malicious replacement\n'
        self.source.write_bytes(raw)
        evidence = row['source_files']['cvc5/configure.sh']
        evidence.update(bytes=len(raw), raw_digest=checker.digest(raw))
        evidence['excerpts'][0]['text'] = raw.decode().strip()
        with self.assertRaisesRegex(ValueError, 'differs from archive inventory'):
            checker.verify(row, self.root)

    def test_unbound_claim(self):
        row = copy.deepcopy(self.record)
        row['configuration'][0]['evidence'] = ['absent']
        with self.assertRaisesRegex(ValueError, 'lacks source evidence'):
            checker.verify(row, self.root)

    def test_boundary_upgrade(self):
        for name in ('build_ready', 'configuration_executed', 'build_executed',
                     'probe_executed', 'solver_executed', 'tool_accepted'):
            with self.subTest(name=name):
                row = copy.deepcopy(self.record)
                row[name] = True
                with self.assertRaisesRegex(ValueError, 'boundary violated'):
                    checker.verify(row, self.root)

    def test_path_escape(self):
        row = copy.deepcopy(self.record)
        row['source_files']['cvc5/configure.sh']['retained_path'] = '../source.cmake'
        with self.assertRaisesRegex(ValueError, 'not bound to selected root'):
            checker.verify(row, self.root)

    def test_missing_matrix(self):
        row = copy.deepcopy(self.record)
        row['configuration'] = []
        with self.assertRaisesRegex(ValueError, 'matrix is incomplete'):
            checker.verify(row, self.root)

    def test_deleted_section(self):
        row = copy.deepcopy(self.record)
        del row['python_generators']
        with self.assertRaisesRegex(ValueError, 'review section'):
            checker.verify(row, self.root)

    def test_duplicate_keys(self):
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            json.loads('{"status":false,"status":true}', object_pairs_hook=checker.reject_duplicates)

    def test_symlink_ancestor(self):
        actual = self.source.parent
        moved = actual.with_name('moved-root')
        actual.rename(moved)
        actual.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink source path'):
            checker.verify(self.record, self.root)

    def test_changed_source_identity(self):
        row = copy.deepcopy(self.record)
        row['source_identities'][0]['source_root'] += '-replacement'
        with self.assertRaisesRegex(ValueError, 'unexpected source root'):
            checker.verify(row, self.root)


if __name__ == '__main__':
    unittest.main()
