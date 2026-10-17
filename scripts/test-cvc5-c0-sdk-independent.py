#!/usr/bin/env python3
"""Synthetic negative checks for the independently written SDK audit path."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'independent_c0', Path(__file__).with_name('check-cvc5-c0-sdk-independent.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def package(name, **fields):
    return dict(Package=name, Version='1.0-1', Architecture='arm64', Size='10', **fields)


def source(name, version='1.0-1'):
    return {'Package': name, 'Version': version, 'Binary': name, 'Directory': 'pool/main/x/' + name,
            'Checksums-Sha256': 'a' * 64 + ' 5 input.dsc\n' + 'b' * 64 + ' 7 input.tar.xz'}


class IndependentAuditTests(unittest.TestCase):
    def inspect(self, packages, names, sources=None):
        sources = sources if sources is not None else [source(row['Package']) for row in packages]
        def retained(path):
            return iter(sources if path.name == 'main__source__Sources.xz' else packages)
        with patch.object(audit, 'paragraphs', side_effect=retained):
            return audit.inspect(set(names))

    def test_missing_predependency_and_essential_rejected(self):
        with self.assertRaises(ValueError):
            self.inspect([package('root', **{'Pre-Depends': 'dependency'}), package('dependency')], ['root'])
        with self.assertRaises(ValueError):
            self.inspect([package('root'), package('essential', Essential='yes')], ['root'])

    def test_dependency_version_and_provider_version_checked(self):
        for provides in ('virtual', 'virtual (= 1)'):
            with self.subTest(provides=provides), self.assertRaises(ValueError):
                self.inspect([package('root', Depends='virtual (>= 2)'), package('provider', Provides=provides)], ['root', 'provider'])
        self.inspect([package('root', Depends='virtual (>= 2)'), package('provider', Provides='virtual (= 2)')], ['root', 'provider'])

    def test_conflict_and_breaks_rejected(self):
        for field in ('Conflicts', 'Breaks'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.inspect([package('root', **{field: 'dep (>= 1)'}), package('dep')], ['root', 'dep'])

    def test_wrong_architecture_and_source_rejected(self):
        wrong = package('root')
        wrong['Architecture'] = 'amd64'
        with self.assertRaises(ValueError):
            self.inspect([wrong], ['root'])
        with self.assertRaises(ValueError):
            self.inspect([package('root', Source='origin (2.0-1)')], ['root'], [source('origin')])

    def test_built_using_source_is_required_and_counted(self):
        rows = [package('root', **{'Built-Using': 'origin (= 2.0-1)'})]
        with self.assertRaises(ValueError):
            self.inspect(rows, ['root'])
        _, _, result = self.inspect(rows, ['root'], [source('root'), source('origin', '2.0-1')])
        self.assertEqual(result['source_family_versions'], 2)
        with self.assertRaises(ValueError):
            self.inspect([package('root', **{'Static-Built-Using': 'origin (>= 2)'})], ['root'])

    def test_any_requires_multi_arch_allowed(self):
        for multi in ('no', 'same', 'foreign'):
            row = package('dep', **{'Multi-Arch': multi})
            self.assertEqual(audit.matches('dep:any', [row]), [])
        self.assertEqual(audit.matches('dep:any', [package('dep', **{'Multi-Arch': 'allowed'})]), ['dep'])

    def test_epoch_tilde_binnmu_and_leading_zeros(self):
        for older, newer in [('2', '1:1'), ('1~rc1', '1'), ('1-1', '1-1+b1'), ('1a', '1+')]:
            self.assertLess(audit.version_compare(older, newer), 0)
            self.assertGreater(audit.version_compare(newer, older), 0)
        self.assertEqual(audit.version_compare('1.01', '1.1'), 0)

    def test_record_duplicate_keys_and_floating_values_rejected(self):
        with tempfile.TemporaryDirectory(prefix='c0-independent-test-') as tmp:
            path = Path(tmp) / 'input.json'
            for text in ('{"count":1,"count":2}', '{"count":1.0}', '{"count":NaN}'):
                path.write_text(text)
                with self.subTest(text=text), self.assertRaises(ValueError):
                    audit.read_json(path)

    def test_json_record_limit_rejected(self):
        with tempfile.TemporaryDirectory(prefix='c0-independent-budget-') as tmp:
            path = Path(tmp) / 'oversized.json'
            path.write_bytes(b' ' * (2 * 1024**2 + 1))
            with self.assertRaisesRegex(ValueError, 'json-record-size'):
                audit.read_json(path)

    def test_deb822_line_limit_rejected(self):
        with tempfile.TemporaryDirectory(prefix='c0-independent-line-') as tmp:
            path = Path(tmp) / 'Packages'
            path.write_text('Package: ' + 'a' * audit.LINE_LIMIT + '\n')
            with self.assertRaisesRegex(ValueError, 'deb822-line-budget'):
                list(audit.paragraphs(path))

    def test_edge_omission_target_and_version_tampering_rejected(self):
        rows = [package('root', Depends='dep (>= 1)'), package('dep')]
        atom = dict(name='dep', qualifier=None, operator='>=', version='1')
        edge = {'from': 'root', 'field': 'Depends', 'group_index': 0, 'alternatives': [atom],
                'selected_alternative': atom, 'to': 'dep', 'target_version': '1.0-1',
                'via_provides': False, 'provided_version': None}
        with patch.object(audit, 'paragraphs', return_value=iter(rows)):
            audit.check_edges(rows, [edge])
        for change in ('omit', 'target', 'version', 'clause'):
            altered = copy.deepcopy(edge)
            if change == 'target':
                altered['to'] = 'root'
            elif change == 'version':
                altered['target_version'] = '999'
            elif change == 'clause':
                altered['alternatives'][0]['version'] = '0'
            with self.subTest(change=change), patch.object(audit, 'paragraphs', return_value=iter(rows)), self.assertRaises(ValueError):
                audit.check_edges(rows, [] if change == 'omit' else [altered])

    @unittest.skipUnless((audit.RAW / 'main__source__Sources.xz').exists()
                         and (audit.ROOT / 'docs/records/solver-cvc5-c0-2026-10-17/sdk-selection.json').exists(),
                         'retained real metadata and selection are unavailable')
    def test_real_selection_tampering_rejected(self):
        original = json.loads((audit.ROOT / 'docs/records/solver-cvc5-c0-2026-10-17/sdk-selection.json').read_text())
        with tempfile.TemporaryDirectory(prefix='c0-independent-real-') as tmp:
            path = Path(tmp) / 'tampered.json'
            for kind in ('removed-edge', 'wrong-source-version', 'source-hash', 'false-ready'):
                altered = copy.deepcopy(original)
                if kind == 'removed-edge':
                    altered['dependency_edges'].pop()
                elif kind == 'wrong-source-version':
                    altered['packages'][0]['source_version'] = '0.0-0'
                elif kind == 'source-hash':
                    altered['source_packages'][0]['files'][0]['sha256'] = '0' * 64
                else:
                    altered['build_ready'] = True
                path.write_text(json.dumps(altered))
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    audit.audit(path)


if __name__ == '__main__':
    unittest.main()
