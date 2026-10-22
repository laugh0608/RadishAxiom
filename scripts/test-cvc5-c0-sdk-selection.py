#!/usr/bin/env python3
"""Synthetic offline SDK dependency and exact-source rejection checks."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('c0_sdk_selection', Path(__file__).with_name('cvc5-c0-sdk-selection.py'))
sdk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdk)


def binary(name='root', version='1.0-1', **fields):
    row = {'Package': name, 'Version': version, 'Architecture': 'arm64',
           'Filename': 'pool/main/r/root/' + name + '.deb', 'Size': '100', 'SHA256': 'a' * 64}
    row.update(fields)
    return row


def source(name='root', version='1.0-1', **fields):
    row = {'Package': name, 'Version': version, 'Directory': 'pool/main/r/root',
           'Checksums-Sha256': 'b' * 64 + ' 10 ' + name + '.dsc\n' + 'c' * 64 + ' 20 ' + name + '.tar.xz'}
    row.update(fields)
    return row


class SDKSelectionTests(unittest.TestCase):
    def resolve(self, packages, sources=None, roots=None):
        if sources is None:
            sources = [source(row['Package'], row['Version']) for row in packages]
        return sdk.resolve_closure(packages, sources, roots or ['root'])

    def test_dependency_predependency_and_essential(self):
        packages = [binary(**{'Pre-Depends': 'pre (>= 1.0-1)', 'Depends': 'dep'}),
                    binary('pre'), binary('dep'), binary('essential', Essential='yes'), binary('unused')]
        rows, edges, sources, essential = self.resolve(packages)
        self.assertEqual([row['Package'] for row in rows], ['dep', 'essential', 'pre', 'root'])
        self.assertEqual([edge['field'] for edge in edges], ['Pre-Depends', 'Depends'])
        self.assertEqual(essential, ['essential'])
        self.assertTrue(all(row['raw_digest'] is None and row['bytes'] is None for row in rows))
        self.assertEqual(len(sources), 4)

    def test_first_satisfiable_alternative(self):
        rows, edges, _, _ = self.resolve([binary(Depends='missing | dep (>= 1)'), binary('dep')])
        self.assertEqual(edges[0]['to'], 'dep')
        self.assertEqual(len(rows), 2)

    def test_unsatisfied_dependency_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unsatisfied-dependency'):
            self.resolve([binary(Depends='missing')])

    def test_version_drift_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unsatisfied-dependency'):
            self.resolve([binary(Depends='dep (= 2.0)'), binary('dep')])

    def test_versioned_virtual_provider(self):
        _, edges, _, _ = self.resolve([binary(Depends='virtual (>= 2)'), binary('provider', Provides='virtual (= 2)')])
        self.assertTrue(edges[0]['via_provides'])
        self.assertEqual(edges[0]['provided_version'], '2')

    def test_unversioned_provider_cannot_meet_version(self):
        with self.assertRaisesRegex(ValueError, 'unsatisfied-dependency'):
            self.resolve([binary(Depends='virtual (>= 2)'), binary('provider', Provides='virtual')])

    def test_any_requires_allowed_package(self):
        _, edges, _, _ = self.resolve([binary(Depends='dep:any'), binary('dep', **{'Multi-Arch': 'allowed'})])
        self.assertEqual(edges[0]['to'], 'dep')
        for multi in (None, 'no', 'same', 'foreign'):
            with self.subTest(multi=multi), self.assertRaisesRegex(ValueError, 'unsatisfied-dependency'):
                self.resolve([binary(Depends='dep:any'), binary('dep', **({'Multi-Arch': multi} if multi else {}))])

    def test_any_provider_requires_allowed(self):
        with self.assertRaisesRegex(ValueError, 'unsatisfied-dependency'):
            self.resolve([binary(Depends='virtual:any'), binary('provider', Provides='virtual')])
        _, edges, _, _ = self.resolve([binary(Depends='virtual:any'), binary('provider', Provides='virtual', **{'Multi-Arch': 'allowed'})])
        self.assertEqual(edges[0]['to'], 'provider')

    def test_native_and_all(self):
        rows, _, _, _ = self.resolve([binary(Depends='dep:native'), binary('dep', Architecture='all')])
        self.assertEqual(len(rows), 2)

    def test_other_architecture_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unexpected-package-architecture'):
            self.resolve([binary(Architecture='amd64')])

    def test_unknown_multiarch_and_noncanonical_essential(self):
        for fields in ({'Multi-Arch': 'sometimes'}, {'Essential': 'true'}, {'Essential': 'YES'}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.resolve([binary(**fields)])

    def test_conflicts_and_breaks(self):
        for field in ('Conflicts', 'Breaks'):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'selected-package-conflict'):
                self.resolve([binary(Depends='dep', **{field: 'dep (>= 1)'}), binary('dep')])

    def test_virtual_conflict(self):
        with self.assertRaisesRegex(ValueError, 'selected-package-conflict'):
            self.resolve([binary(Depends='dep', Conflicts='virtual'), binary('dep', Provides='virtual')])

    def test_self_provided_conflict_allowed(self):
        self.resolve([binary(Provides='virtual', Conflicts='virtual')])

    def test_source_explicit_name_and_version(self):
        rows, _, sources, _ = self.resolve([binary(Source='origin (2.0-1)')], [source('origin', '2.0-1')])
        self.assertEqual((rows[0]['source_package'], rows[0]['source_version']), ('origin', '2.0-1'))
        self.assertEqual(sources[0]['Package'], 'origin')

    def test_source_name_only_inherits_binary_version(self):
        rows, _, _, _ = self.resolve([binary(Source='origin')], [source('origin')])
        self.assertEqual(rows[0]['source_version'], '1.0-1')

    def test_missing_or_wrong_source_rejected(self):
        for sources in ([source('wrong')], [source(version='2.0')], []):
            with self.subTest(sources=sources), self.assertRaisesRegex(ValueError, 'missing-exact-source-version'):
                self.resolve([binary()], sources)

    def test_built_using_selects_sources_without_binary_dependency(self):
        for field in ('Built-Using', 'Static-Built-Using'):
            with self.subTest(field=field):
                rows, edges, sources, _ = self.resolve([binary(**{field: 'embedded (= 2.0)'})], [source(), source('embedded', '2.0')])
                self.assertEqual(len(rows), 1)
                self.assertEqual(edges, [])
                self.assertEqual(len(sources), 2)
                self.assertEqual(rows[0]['built_using_sources'], [{'field': field, 'source_package': 'embedded', 'source_version': '2.0'}])

    def test_built_using_missing_source_and_unknown_relation_rejected(self):
        for value in ('embedded (= 2.0)', 'embedded (>= 2.0)', 'embedded', 'embedded (= 2) | other (= 1)'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.resolve([binary(**{'Built-Using': value})])

    def test_no_built_using_has_explicit_empty_list(self):
        rows, _, _, _ = self.resolve([binary()])
        self.assertEqual(rows[0]['built_using_sources'], [])

    def test_source_binary_membership_mismatch(self):
        with self.assertRaisesRegex(ValueError, 'source-binary-membership-mismatch'):
            self.resolve([binary()], [source(Binary='different')])

    def test_invalid_version_and_provides_syntax(self):
        for version in ('', 'x1', '1-', '1-1:2', '1 2'):
            with self.subTest(version=version), self.assertRaises(ValueError):
                sdk.version_parts(version)
        for value in ('virtual (>= 1)', 'virtual | another', 'virtual:any'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.resolve([binary(Provides=value)])

    def test_duplicate_package_and_source_candidates(self):
        with self.assertRaisesRegex(ValueError, 'multiple-package-candidates'):
            self.resolve([binary(), binary(version='2')])
        with self.assertRaisesRegex(ValueError, 'duplicate-source-candidate'):
            self.resolve([binary()], [source(), source()])

    def test_pool_origin_rejected(self):
        for filename in ('https://evil.invalid/a.deb', 'pool/main/../a.deb', 'pool/contrib/a.deb'):
            with self.subTest(filename=filename), self.assertRaisesRegex(ValueError, 'unsafe-or-out-of-main'):
                self.resolve([binary(Filename=filename)])

    def test_bad_binary_hash_and_size(self):
        for fields in ({'SHA256': 'g' * 64}, {'Size': '0'}, {'Size': '-2'}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.resolve([binary(**fields)])

    def test_bad_source_hash_path_duplicate_and_incomplete(self):
        lines = [
            'x' * 64 + ' 2 root.dsc\n' + 'b' * 64 + ' 3 root.tar.xz',
            'a' * 64 + ' 2 ../root.dsc\n' + 'b' * 64 + ' 3 root.tar.xz',
            'a' * 64 + ' 2 root.dsc\n' + 'b' * 64 + ' 3 root.dsc',
            'a' * 64 + ' 2 root.dsc',
        ]
        for value in lines:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.resolve([binary()], [source(**{'Checksums-Sha256': value})])

    def test_debian_versions(self):
        for older, newer in [('1~rc1', '1'), ('1', '1-1'), ('1-9', '1-10'), ('1.9', '1.10'), ('1:9', '2:1'), ('1a', '1+')]:
            with self.subTest(older=older, newer=newer):
                self.assertLess(sdk.version_compare(older, newer), 0)
                self.assertGreater(sdk.version_compare(newer, older), 0)
        self.assertEqual(sdk.version_compare('1.01', '1.1'), 0)
        self.assertEqual(sdk.version_compare('1', '1-0'), 0)

    def test_unknown_syntax_fails_closed(self):
        for relation in ('dep [arm64]', 'dep <!nocheck>', 'dep:amd64', 'dep (=> 1)', 'dep,', 'dep || other'):
            with self.subTest(relation=relation), self.assertRaisesRegex(ValueError, 'unsupported-dependency-syntax'):
                sdk.relations(relation)

    def test_parse_errors(self):
        for raw in (b'', b'Package: root\npackage: other', b' orphan', b'Package: root\nPackage: other', b'Package root', b'Package: root\x00', b'Package: root\r\n'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                sdk.deb822(raw)

    def test_record_strict_types_and_duplicate_keys(self):
        with tempfile.TemporaryDirectory(prefix='cvc5-c0-sdk-test-') as tmp:
            path = Path(tmp) / 'record.json'
            path.write_text('{"packages":1,"packages":2}')
            with self.assertRaisesRegex(ValueError, 'duplicate-json-key'):
                sdk.read_record(path)
            path.write_text('{"packages":NaN}')
            with self.assertRaisesRegex(ValueError, 'nonfinite-json'):
                sdk.read_record(path)
            self.assertFalse(sdk.same_typed({'packages': 1}, {'packages': True}))

    def test_resolution_count_budgets(self):
        with patch.object(sdk, 'MAX_SELECTED_PACKAGES', 1), self.assertRaisesRegex(ValueError, 'selected-package-count-budget'):
            self.resolve([binary(Depends='dep'), binary('dep')])
        with patch.object(sdk, 'MAX_DEPENDENCY_EDGES', 1), self.assertRaisesRegex(ValueError, 'dependency-edge-count-budget'):
            self.resolve([binary(Depends='dep, other'), binary('dep'), binary('other')])
        with patch.object(sdk, 'MAX_INDEX_ROWS', 1), self.assertRaisesRegex(ValueError, 'metadata-index-row-budget'):
            self.resolve([binary(), binary('other')])
        self.assertEqual(len(sdk.relations(','.join(['dep'] * 2048))), 2048)
        with self.assertRaisesRegex(ValueError, 'dependency-relation-count-budget'):
            sdk.relations(','.join(['dep'] * 2049))
        with self.assertRaisesRegex(ValueError, 'dependency-field-budget-or-type'):
            sdk.relations('d' * 131073)

    def test_record_budget(self):
        with tempfile.TemporaryDirectory(prefix='cvc5-c0-sdk-test-') as tmp:
            path = Path(tmp) / 'large.json'
            path.write_bytes(b' ' * (sdk.RECORD_LIMIT + 1))
            with self.assertRaisesRegex(ValueError, 'sdk-record-size-budget'):
                sdk.read_record(path)

    def test_record_forged_acceptance_and_omitted_edge(self):
        observations = {'complete': True}
        selection = {'summary': {'packages': 1}, 'build_ready': False, 'dependency_edges': [{'to': 'dep'}]}
        with tempfile.TemporaryDirectory(prefix='cvc5-c0-sdk-test-') as tmp:
            observed, selected = Path(tmp) / 'metadata.json', Path(tmp) / 'selection.json'
            sdk.write_json(observed, observations)
            for mutate in (lambda value: value.update(build_ready=True), lambda value: value['dependency_edges'].clear(),
                           lambda value: value['summary'].update(packages=True)):
                value = copy.deepcopy(selection)
                mutate(value)
                sdk.write_json(selected, value)
                with patch.object(sdk, 'OBSERVATIONS', observed), patch.object(sdk, 'SELECTION', selected), patch.object(sdk, 'generate', return_value=(observations, selection)):
                    with self.assertRaisesRegex(ValueError, 'sdk-record-drift-or-false-acceptance'):
                        sdk.verify()


if __name__ == '__main__':
    unittest.main()
