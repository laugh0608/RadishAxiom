#!/usr/bin/env python3
"""Offline positive and adversarial cases for the AX-B01 Poly-disabled plan."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cvc5_no_poly', ROOT / 'scripts/prepare-cvc5-no-poly.py')
NP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(NP)


class RecipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads((ROOT / NP.INPUTS).read_bytes())
        cls.recipe = json.loads((ROOT / NP.RECIPE).read_bytes())

    def test_retained_inputs_without_reading_libpoly(self):
        local = NP.C2.local

        def reject_poly_path(name):
            self.assertNotRegex(str(name), r'(?i)libpoly|picpoly')
            return local(name)

        with patch.object(NP.C2, 'local', reject_poly_path):
            self.assertEqual(NP.checked_inputs(NP.historical()), self.inputs)
        self.assertEqual(self.inputs['sdk']['matched_files'], 500)

    def test_retained_recipe_and_production_differences(self):
        raw = (ROOT / NP.RECIPE).read_bytes()
        self.assertEqual(NP.checked_recipe(ROOT / NP.RECIPE, NP.sha(raw)), self.recipe)
        baseline = NP.historical()
        old = {row['name']: row['candidate'] for row in baseline['main_phase']['configuration']}
        new = {row['name']: row['candidate'] for row in self.recipe['main_phase']['configuration']}
        self.assertEqual(old['USE_POLY'], 'ON')
        self.assertEqual(new, dict(old, USE_POLY='OFF'))
        self.assertEqual(self.recipe['phase_plan'], baseline['phase_plan'])
        self.assertNotRegex(json.dumps(self.recipe), r'(?i)libpoly|picpoly|deprecated.literal|open_memstream')
        self.assertEqual([s['id'] for s in self.recipe['source_inputs']], list(NP.SOURCES))
        self.assertEqual(len(self.recipe['dependency_steps']), 29)
        probes = next(step for step in self.recipe['dependency_steps'] if step['id'] == 'dependency-probes')
        self.assertIn('-DCMAKE_CXX_STANDARD=11', probes['argv'])
        probe_source = (ROOT / NP.PROBES).read_bytes()
        self.assertIn(b'check_cxx_symbol_exists(getc_unlocked "cstdio"', probe_source)
        self.assertIn(b'check_cxx_symbol_exists(closefrom "unistd.h"', probe_source)
        self.assertEqual(len(self.recipe['main_phase']['steps']), 11)
        self.assertIs(self.recipe['build_ready'], False)
        self.assertIs(self.recipe['execution_ready'], False)

    def test_patch_application_and_exact_gate(self):
        base = NP.historical()
        refs = {r['path']: r for r in base['references']}
        src = ROOT / self.inputs['sources'][0]['source_root']
        applied = {}
        for raw, files, _ in NP.patch_chain(refs):
            self.assertNotIn('cmake/FindPoly.cmake', files)
            originals = {name: applied[name] if name in applied else (src / name).read_bytes()
                         for name in files if name in applied or (src / name).is_file()}
            applied.update(NP.PATCH.apply_exact(raw, originals, files))
        helper = applied['cmake/cvc5-c0-inputs.cmake']
        self.assertIn(b'set(CMAKE_DISABLE_FIND_PACKAGE_Poly TRUE)', helper)
        self.assertIn(b'USE_POLY NO_GLOBAL_POLY_CTX BUILD_BINDINGS_PYTHON', helper)
        self.assertIn(b'NOT "${${option}}" STREQUAL "OFF"', helper)
        self.assertNotIn(b'cvc5_c0_get(poly_version', helper)
        self.assertIn(b'CXX_LINKER_LAUNCHER', applied['src/main/CMakeLists.txt'])

    def test_rehashed_recipe_mutations(self):
        cases = {
            'extra source': ('source_inputs', lambda d: d['source_inputs'].append({'id': 'other'})),
            'Poly source': ('source_inputs', lambda d: d['source_inputs'].append({'id': 'libpoly'})),
            'Poly step': ('dependency_steps', lambda d: d['dependency_steps'].append({'id': 'poly-configure'})),
            'staged Poly archive': ('staging', lambda d: d['staging']['new_directories'].append('/work/prefix/poly/lib')),
            'Poly patch': ('transformations', lambda d: d['transformations']['patch_chain'].append({'files': ['cmake/FindPoly.cmake']})),
            'extra SDK package': ('sdk', lambda d: d['sdk'].update(package_count=173)),
            'probe drift': ('probe_output', lambda d: d['probe_output']['boolean_keys'].append('deprecated_literal_flag')),
            'option drift': ('main_phase', lambda d: next(row for row in d['main_phase']['configuration']
                                                        if row['name'] == 'USE_POLY').update(candidate='ON')),
            'argv drift': ('main_phase', lambda d: d['main_phase']['steps'][0]['argv'].append('-DSTATIC_BINARY=OFF')),
            'acceptance overclaim': ('build_ready', lambda d: d.update(build_ready=True)),
        }
        with tempfile.TemporaryDirectory() as name, patch.object(NP, 'checked_inputs', return_value=self.inputs):
            path = Path(name).resolve() / 'candidate.json'
            for label, (field, mutate) in cases.items():
                with self.subTest(case=label):
                    forged = copy.deepcopy(self.recipe)
                    mutate(forged)
                    raw = NP.C2.encoded(forged)
                    path.write_bytes(raw)
                    with self.assertRaisesRegex(ValueError, 'candidate-recipe-drift:' + field):
                        NP.checked_recipe(path, NP.sha(raw))

    def test_legacy_inputs_are_not_candidates(self):
        for path in (ROOT / NP.BASELINE, ROOT / NP.INPUTS):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'candidate-recipe-identity'):
                NP.checked_recipe(path, NP.sha(path.read_bytes()))

    def test_poly_on_entry_rejects_new_candidate(self):
        legacy = ROOT / NP.RECIPE
        for version in ('0.1', '0.2'):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'recipe-format'):
                NP.C2.checked_plan(legacy, NP.sha(legacy.read_bytes()), version)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.inputs = json.loads((ROOT / NP.INPUTS).read_bytes())
        self.spec = self.inputs['dependency_manifest']
        self.manifest = {k: self.inputs[k] for k in ('candidate_id', 'upstream_commit', 'target_abi')}
        self.manifest.update(format=NP.MANIFEST_FORMAT, version=NP.VERSION, versions=self.spec['versions'].copy(),
                             review_state='reviewed-for-configuration', header_roots={}, archives={},
                             editline_link_order=['editline', 'tinfo', 'bsd', 'md', 'bsd'])
        # Substitute synthetic bytes for actual future material. The real plan's
        # paths, role policy and file names stay intact.
        for role, declaration in self.spec['headers'].items():
            rows = []
            for name, pin in declaration['files'].items():
                ref = self.put(declaration['path'] + '/' + name, b'synthetic header ' + name.encode())
                identity = {k: ref[k] for k in ('bytes', 'sha256')}
                if pin is not None:
                    declaration['files'][name] = identity
                rows.append({'path': name, **identity})
            self.manifest['header_roots'][role] = {'path': declaration['path'], 'files': rows}
        for role, path in self.spec['generated_archives'].items():
            self.manifest['archives'][role] = self.put(path, b'synthetic archive ' + role.encode())
        for role, old in self.spec['sdk_archives'].items():
            ref = self.put(old['path'], b'synthetic SDK archive ' + role.encode())
            self.spec['sdk_archives'][role] = ref
            self.manifest['archives'][role] = ref.copy()

    def put(self, name, raw):
        path = self.root / name.lstrip('/')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return {'path': name, 'bytes': len(raw), 'sha256': NP.sha(raw)}

    def envelope(self):
        review = {k: self.manifest[k] for k in NP.BINDINGS}
        review['review_state'] = 'static-closure-and-abi-reviewed'
        self.manifest['closure_review'] = self.put(NP.CLOSURE_PATH, NP.C2.encoded(review))
        return self.put(NP.MANIFEST_PATH, NP.C2.encoded(self.manifest))['sha256']

    def test_complete_roles_and_ordered_repetitions(self):
        result = NP.check_manifest(self.root, self.envelope(), self.inputs)
        self.assertEqual(result['editline_link_order'], ['editline', 'tinfo', 'bsd', 'md', 'bsd'])
        self.assertIs(result['build_ready'], False)

    def test_bind_only_the_reviewed_manifest_argument(self):
        raw = (ROOT / NP.RECIPE).read_bytes()
        planned = json.loads(raw)
        digest = self.envelope()
        bound = NP.bound_main(planned, NP.sha(raw), self.root, digest, self.inputs)
        expected = copy.deepcopy(planned['main_phase']['steps'])
        argv = expected[0]['argv']
        argv[argv.index(NP.PENDING_MANIFEST_ARG)] = NP.MANIFEST_ARG + digest
        self.assertEqual(bound['steps'], expected)
        self.assertIn(NP.PENDING_MANIFEST_ARG, planned['main_phase']['steps'][0]['argv'])
        self.assertEqual(bound['executed_recipe_steps'], [])
        self.assertIs(bound['execution_ready'], False)

    def test_libmd_may_be_omitted_only_with_matching_reviewed_order(self):
        del self.manifest['archives']['md']
        with self.assertRaisesRegex(ValueError, 'candidate-editline-order-roles'):
            NP.check_manifest(self.root, self.envelope(), self.inputs)
        self.manifest['editline_link_order'].remove('md')
        self.assertTrue(NP.check_manifest(self.root, self.envelope(), self.inputs)['passed'])

    def test_poly_and_extra_archive_roles_even_if_rehashed(self):
        for role in ('poly', 'polyxx', 'unexpected'):
            with self.subTest(role=role):
                self.manifest['archives'][role] = self.put('/work/prefix/' + role + '.a', b'extra')
                self.manifest['editline_link_order'].append(role)
                try:
                    with self.assertRaisesRegex(ValueError, 'candidate-archive-role-set'):
                        NP.check_manifest(self.root, self.envelope(), self.inputs)
                finally:
                    self.manifest['editline_link_order'].pop()
                    del self.manifest['archives'][role]

    def test_poly_path_cannot_hide_under_allowed_role(self):
        self.manifest['archives']['gmp'] = self.put('/work/prefix/gmp/lib/libpicpoly.a', b'extra')
        with self.assertRaisesRegex(ValueError, 'candidate-generated-archive-path'):
            NP.check_manifest(self.root, self.envelope(), self.inputs)

    def test_extra_pinned_sdk_archive_bytes(self):
        path = self.manifest['archives']['editline']['path']
        self.manifest['archives']['editline'] = self.put(path, b'replaced and rehashed')
        with self.assertRaisesRegex(ValueError, 'candidate-sdk-archive-drift:editline'):
            NP.check_manifest(self.root, self.envelope(), self.inputs)

    def test_physical_poly_header_even_if_omitted_from_manifest(self):
        self.put('/work/prefix/editline/include/poly/poly.h', b'extra')
        with self.assertRaisesRegex(ValueError, 'candidate-staged-header-set:editline'):
            NP.check_manifest(self.root, self.envelope(), self.inputs)

    def test_extra_declared_header(self):
        ref = self.put('/work/prefix/editline/include/extra.h', b'extra')
        self.manifest['header_roots']['editline']['files'].append({**ref, 'path': 'extra.h'})
        with self.assertRaisesRegex(ValueError, 'candidate-header-file-set:editline'):
            NP.check_manifest(self.root, self.envelope(), self.inputs)

    def test_poly_version_residual(self):
        self.manifest['versions']['poly'] = '0.2.1'
        with self.assertRaisesRegex(ValueError, 'candidate-manifest-identity-or-versions'):
            NP.check_manifest(self.root, self.envelope(), self.inputs)

    def test_review_must_bind_candidate(self):
        self.envelope()
        path = self.root / NP.CLOSURE_PATH.lstrip('/')
        review = json.loads(path.read_bytes())
        review['candidate_id'] = 'old-candidate'
        self.manifest['closure_review'] = self.put(NP.CLOSURE_PATH, NP.C2.encoded(review))
        digest = self.put(NP.MANIFEST_PATH, NP.C2.encoded(self.manifest))['sha256']
        with self.assertRaisesRegex(ValueError, 'candidate-closure-binding'):
            NP.check_manifest(self.root, digest, self.inputs)

    def test_symlink_cannot_escape_material_root(self):
        path = self.root / self.manifest['archives']['gmp']['path'].lstrip('/')
        path.unlink()
        path.symlink_to(self.root / 'elsewhere')
        with self.assertRaisesRegex(ValueError, 'noncanonical-or-symlink-input'):
            NP.check_manifest(self.root, self.envelope(), self.inputs)


if __name__ == '__main__':
    unittest.main()
