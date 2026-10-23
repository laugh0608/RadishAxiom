#!/usr/bin/env python3
"""C2 recipe and preflight rejection tests; never execute a recipe command."""
import ast
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
SPEC = importlib.util.spec_from_file_location('cvc5_offline', ROOT / 'scripts/prepare-cvc5-offline-build.py')
C2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C2)


class PathAndInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cvc5-c2-test-', dir=ROOT / '.tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.file = self.root / 'input'
        self.file.write_bytes(b'synthetic bytes\n')
        self.row = {'path': 'input', 'bytes': self.file.stat().st_size,
                    'sha256': hashlib.sha256(self.file.read_bytes()).hexdigest()}

    def check(self, row=None):
        with patch.object(C2, 'ROOT', self.root):
            C2.check_file(row or self.row, [0])

    def test_real_byte_readback(self):
        self.check()

    def test_same_length_corruption(self):
        self.file.write_bytes(b'x' * self.row['bytes'])
        with self.assertRaisesRegex(ValueError, 'digest-mismatch'):
            self.check()

    def test_truncation(self):
        self.file.write_bytes(b'x')
        with self.assertRaisesRegex(ValueError, 'size-mismatch'):
            self.check()

    def test_boolean_size_rejected(self):
        with self.assertRaisesRegex(ValueError, 'size-budget'):
            self.check(dict(self.row, bytes=True))

    def test_bad_digest_rejected(self):
        with self.assertRaisesRegex(ValueError, 'sha256'):
            self.check(dict(self.row, sha256='0' * 63))

    def test_total_budget(self):
        with patch.object(C2, 'ROOT', self.root):
            with self.assertRaisesRegex(ValueError, 'total-input-byte-budget'):
                C2.check_file(self.row, [C2.TOTAL_LIMIT])

    def test_parent_symlink(self):
        (self.root / 'alias').symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'noncanonical'):
            self.check(dict(self.row, path='alias/input'))

    def test_fifo_rejected_without_opening(self):
        fifo = self.root / 'fifo'
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, 'not-regular'):
            C2.read_json(fifo)

    def test_path_traversal(self):
        for name in ('../input', '/input', 'a/../input', 'a//input', 'a\\input'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.check(dict(self.row, path=name))

    def test_json_duplicate_and_nan(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}'):
            self.file.write_bytes(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                C2.read_json(self.file)

    def test_json_size_limit(self):
        self.file.write_bytes(b'{"extra":123}')
        with patch.object(C2, 'JSON_LIMIT', 4), self.assertRaisesRegex(ValueError, 'json-size-budget'):
            C2.read_json(self.file)

    def test_output_refuses_overwrite_and_symlink(self):
        original = self.file.read_bytes()
        with self.assertRaisesRegex(ValueError, 'output-already-exists'):
            C2.write_new(self.file, {})
        self.assertEqual(self.file.read_bytes(), original)
        alias = self.root / 'alias'
        alias.symlink_to(self.root / 'not-created')
        with self.assertRaisesRegex(ValueError, 'output-already-exists'):
            C2.write_new(alias, {})
        self.assertFalse((self.root / 'not-created').exists())

    def test_output_exclusive_and_byte_identity(self):
        out = self.root / 'new.json'
        C2.write_new(out, {'a': False})
        self.assertEqual(out.read_bytes(), C2.encoded({'a': False}))

    def test_batch_path_no_creation_or_reuse(self):
        (self.root / 'artifacts').mkdir()
        with patch.object(C2, 'ROOT', self.root):
            p = Path(C2.batch_path('candidate-1'))
            self.assertFalse(p.exists())
            p.mkdir()
            with self.assertRaisesRegex(ValueError, 'batch-already-occupied'):
                C2.batch_path('candidate-1')
            for bad in ('', '../x', 'a/b', '/tmp', '-x', 'X', 'a' * 49):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    C2.batch_path(bad)


class RecipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = json.loads((ROOT / C2.SOURCE_RECORDS / 'source-inputs.json').read_bytes())
        cls.config = json.loads((ROOT / C2.SOURCE_RECORDS / 'production-review.json').read_bytes())['configuration']
        cls.roots = {r['id']: ROOT / r['source_root'] for r in cls.sources['sources']}

    def test_all_cadical_probe_branches(self):
        raw = (self.roots['cadical'] / 'makefile.in').read_bytes()
        variants = C2.transformations(self.sources)['cadical']['variants']
        self.assertEqual(len(variants), 4)
        self.assertEqual(len({r['sha256'] for r in variants}), 4)
        for row in variants:
            branch = row['when']
            body = C2.cadical_makefile(raw, branch['unlocked_io'], branch['closefrom'])
            self.assertEqual(hashlib.sha256(body).hexdigest(), row['sha256'])
            self.assertEqual(b'-DNUNLOCKED' in body, not branch['unlocked_io'])
            self.assertEqual(b'-DNCLOSEFROM' in body, not branch['closefrom'])
            self.assertIn(b'CXX=/usr/bin/aarch64-linux-gnu-g++-12', body)
            self.assertIn(b'-fPIC -O3 -DNDEBUG -DQUIET -std=c++11', body)
            self.assertNotIn(b'-march=native', body)

    def test_missing_or_nonboolean_probe_does_not_default(self):
        for invalid in (None, 'false', 0, 1):
            with self.subTest(value=invalid), self.assertRaisesRegex(ValueError, 'not-booleans'):
                C2.cadical_makefile(b'@CXXFLAGS@', invalid, True)

    def test_poly_transform_preserves_static_pic_and_original(self):
        path = self.roots['libpoly'] / 'src/CMakeLists.txt'
        raw = path.read_bytes()
        body = C2.poly_cmake(raw)
        self.assertEqual(path.read_bytes(), raw)
        self.assertIn(b'install(TARGETS static_pic_poly ', body)
        self.assertIn(b'install(TARGETS static_pic_polyxx ', body)
        self.assertNotIn(b'install(TARGETS poly ', body)
        with self.assertRaisesRegex(ValueError, 'source-drift'):
            C2.poly_cmake(body)

    def test_poly_capability_branches_are_explicit(self):
        choice = next(x for x in C2.dependency_steps() if x['id'] == 'poly-configure-choice')
        self.assertEqual([x['when'] for x in choice['choices']], [False, True])
        a, b = [x['step']['argv'] for x in choice['choices']]
        self.assertNotIn('deprecated-literal', ' '.join(a))
        self.assertIn('-Wno-error=deprecated-literal-operator', ' '.join(b))

    def test_main_command_preserves_profile_and_real_digest(self):
        digest = 'a' * 64
        rows = C2.cvc5_commands(self.config, digest)
        argv = rows[0]['argv']
        for arg in ('-DCMAKE_BUILD_TYPE=Production', '-DSTATIC_BINARY=ON', '-DUSE_POLY=ON',
                    '-DUSE_EDITLINE=ON', '-DBUILD_GMP=OFF', '-DENABLE_AUTO_DOWNLOAD=OFF',
                    '-DUSE_PYTHON_VENV=OFF', '-DBUILD_BINDINGS_PYTHON=OFF', '-DBUILD_BINDINGS_JAVA=OFF',
                    '-DCVC5_C0_INPUT_MANIFEST_SHA256=' + digest):
            self.assertIn(arg, argv)
        build = next(r for r in rows if r['id'] == 'cvc5-build')
        self.assertIn('--target', build['argv'])
        self.assertIn('cvc5-bin', build['argv'])
        self.assertIn('-Wl,-Map,/work/evidence/cvc5.map,--cref,-t,-t', ' '.join(argv))
        self.assertNotIn('no new proof compile flag', ' '.join(argv))
        self.assertFalse(any('/work/output/cvc5.unstripped' == x.get('argv', [''])[0] for x in rows))
        stripped = next(r for r in rows if r['id'] == 'strip-copy')
        self.assertEqual(stripped['argv'][-1], '/work/output/cvc5.unstripped')

    def test_missing_manifest_digest_is_rejected(self):
        for value in ('', None, '0' * 63):
            with self.subTest(value=value), self.assertRaises(ValueError):
                C2.cvc5_commands(self.config, value)

    def test_each_command_has_preserved_streams_and_stop(self):
        rows = C2.dependency_steps() + C2.cvc5_commands(self.config, '1' * 64)
        for row in rows:
            if row['operation'] != 'command':
                continue
            self.assertTrue(row['argv'][0].startswith('/'))
            self.assertEqual(row['on_failure'], 'stop-entire-batch-retain-everything-no-retry')
            self.assertTrue(row['stdout'].endswith('/stdout.bin'))
            self.assertNotEqual(row['stdout'], row['stderr'])
        self.assertNotIn('curl', str(rows))
        self.assertNotIn('apt-get', str(rows))

    def test_critical_reviews_cannot_auto_pass(self):
        gates = [x for x in C2.dependency_steps() if x['operation'] == 'review-gate']
        self.assertEqual(len(gates), 4)
        self.assertTrue(all(x['no_automatic_pass'] is True for x in gates))

    def test_recipe_tampering_even_when_rehashed(self):
        with tempfile.TemporaryDirectory(prefix='cvc5-plan-test-', dir=ROOT / '.tmp') as directory:
            path = Path(directory) / 'recipe.json'
            expected = {'format': C2.FORMAT, 'version': '0.1', 'batch_id': 'synthetic',
                        'build_ready': False, 'steps': [{'argv': [C2.MAKE, '-j4']}],
                        'policy': {'network': 'none', 'delete': False}}
            changes = [lambda v: v.update(build_ready=True), lambda v: v.update(build_ready=0),
                       lambda v: v['steps'][0]['argv'].append('install'),
                       lambda v: v['policy'].update(network='host'),
                       lambda v: v['policy'].update(delete=True), lambda v: v.update(extra='ignored')]
            with patch.object(C2, 'generate', return_value=expected):
                path.write_bytes(C2.encoded(expected))
                self.assertEqual(C2.checked_plan(path, hashlib.sha256(path.read_bytes()).hexdigest()), expected)
                for change in changes:
                    value = copy.deepcopy(expected)
                    change(value)
                    path.write_bytes(C2.encoded(value))
                    with self.assertRaisesRegex(ValueError, 'recipe-drift'):
                        C2.checked_plan(path, hashlib.sha256(path.read_bytes()).hexdigest())
                with self.assertRaisesRegex(ValueError, 'recipe-hash-mismatch'):
                    C2.checked_plan(path, '0' * 64)

    def test_cli_has_no_execution_or_cleanup_mode(self):
        for mode in ('run', 'execute', 'install', 'configure', 'build', 'cleanup'):
            with patch('sys.argv', ['prepare', mode]), contextlib_redirect(), self.assertRaises(SystemExit) as caught:
                C2.main()
            self.assertEqual(caught.exception.code, 2)

    def test_entry_has_no_process_network_or_deletion_calls(self):
        tree = ast.parse((ROOT / C2.SELF).read_text())
        forbidden = {'subprocess', 'socket', 'urllib', 'requests', 'shutil'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse(forbidden & {x.name.split('.')[0] for x in node.names})
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else ''
                self.assertNotIn(name, {'system', 'popen', 'execv', 'spawnv', 'unlink', 'rmdir', 'rmtree'})

    def test_policy_reserves_finalization_and_keeps_data(self):
        value = C2.policy('unit-review-only', 123)
        self.assertFalse(value['environment']['inherit'])
        self.assertEqual(value['environment']['values']['AWK'], '/usr/bin/gawk')
        self.assertFalse(value['cleanup']['automatic_deletion'])
        self.assertEqual(value['cleanup']['shell_delete_commands'], [])
        self.assertEqual(value['resources']['deadline_seconds'], 5400)
        self.assertEqual(value['resources']['memory_bytes'], 8 * 1024**3)
        self.assertEqual(value['isolation']['network'], 'none')
        self.assertIn('never truncate and report success', C2.evidence_policy()['overflow'])


class LateBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cvc5-binding-test-', dir=ROOT / '.tmp')
        self.addCleanup(self.temp.cleanup)
        self.plan_path = Path(self.temp.name) / 'plan.json'
        self.config = json.loads((ROOT / C2.SOURCE_RECORDS / 'production-review.json').read_bytes())['configuration']
        self.recipe = {'format': C2.FORMAT, 'version': '0.1', 'build_ready': False, 'execution_ready': False,
                       'references': [C2.identity(ROOT / name) for name in
                           (C2.SELF, 'scripts/check-cvc5-build-inputs.py', C2.SOURCE_RECORDS + 'production-review.json')],
                       'main_phase': {'configuration': copy.deepcopy(self.config)}}
        self.manifest = {'header_roots': {'gmp': {'path': '/work/prefix/gmp/include'}},
                         'archives': {'editline': {'path': '/usr/lib/aarch64-linux-gnu/libedit.a'}},
                         'closure_review': {'path': '/work/review/closure.json'}}

    def call(self, manifest_path='/work/review/build-inputs.json'):
        self.plan_path.write_bytes(C2.encoded(self.recipe))
        sha = hashlib.sha256(self.plan_path.read_bytes()).hexdigest()
        original = C2.read_json
        def read(path):
            if str(path) == '/work/review/build-inputs.json':
                return C2.encoded(self.manifest), self.manifest
            return original(path)
        with patch.object(C2, 'read_json', side_effect=read), patch.object(C2.BUILD, 'check',
                return_value={'byte_preflight_passed': True, 'build_ready': False}) as check:
            result = C2.bind_inputs(self.plan_path, sha, Path(manifest_path), 'b' * 64)
            check.assert_called_once_with(Path(manifest_path), 'b' * 64)
            return result

    def test_matching_manifest_only_emits_blocked_command_data(self):
        result = self.call()
        self.assertFalse(result['build_ready'])
        self.assertFalse(result['execution_ready'])
        self.assertEqual(result['executed_recipe_steps'], [])
        self.assertIn('-DCVC5_C0_INPUT_MANIFEST_SHA256=' + 'b' * 64, result['steps'][0]['argv'])

    def test_changed_configuration_rejected_before_manifest_check(self):
        self.recipe['main_phase']['configuration'][0]['candidate'] = 'Debug'
        with self.assertRaisesRegex(ValueError, 'main-configuration-drift'):
            self.call()

    def test_changed_preflight_implementation_rejected(self):
        self.recipe['references'][1]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'entry-or-review-drift'):
            self.call()

    def test_foreign_manifest_path_rejected(self):
        with self.assertRaisesRegex(ValueError, 'manifest-namespace-path'):
            self.call('/host/manifest.json')

    def test_foreign_archive_path_rejected(self):
        self.manifest['archives']['editline']['path'] = '/opt/homebrew/lib/libedit.a'
        with self.assertRaisesRegex(ValueError, 'outside-build-namespace'):
            self.call()

    def test_foreign_closure_path_rejected(self):
        self.manifest['closure_review']['path'] = '/tmp/unchecked.json'
        with self.assertRaisesRegex(ValueError, 'closure-outside-review-namespace'):
            self.call()

    def test_false_acceptance_in_recipe_rejected(self):
        self.recipe['build_ready'] = True
        with self.assertRaisesRegex(ValueError, 'recipe-boundary'):
            self.call()


# Redirect argparse diagnostics for expected rejection cases only.
def contextlib_redirect():
    import contextlib
    import io
    return contextlib.redirect_stderr(io.StringIO())


if __name__ == '__main__':
    unittest.main()
