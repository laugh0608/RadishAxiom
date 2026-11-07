#!/usr/bin/env python3
"""Phase/version/capture adversarial tests; only synthetic child processes."""
import ast
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


R = load('phase_rules_test', 'scripts/cvc5-build-support/phase_rules.py')
P = load('phase_recipe_test', 'scripts/cvc5-build-support/phase_recipe.py')
C = load('capture_test', 'scripts/cvc5-build-support/capture_link.py')
I = load('independent_fixture', 'scripts/check-cvc5-phases-independent.py')
C2 = load('offline_phase_test', 'scripts/prepare-cvc5-offline-build.py')


class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cvc5-phase-test-', dir=ROOT / '.tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.recipe = I.fixture_recipe()
        self.sha = I.digest(I.encoded(self.recipe))
        self.value, _ = I.prepare(self.recipe, self.sha, self.root / 'synthetic')

    def check(self):
        return R.check_declarations(self.value, self.recipe, self.sha)

    def bad(self, change, reason):
        saved = copy.deepcopy(self.value)
        change(self.value)
        with self.assertRaisesRegex(ValueError, reason):
            self.check()
        self.value = saved

    def test_independent_plan_matches_and_no_qualification(self):
        self.assertEqual(R.plan(), I.phase_plan())
        result = self.check()
        self.assertEqual(result['checked_prefix'], ['dependencies', 'main-compile'])
        self.assertFalse(result['runtime_qualification'])
        self.assertFalse(result['build_ready'])
        self.assertFalse(result['execution_ready'])

    def test_all_four_declared_stages_still_do_not_accept(self):
        available = self.check()['unverified_outputs']
        for index, (name, inputs, outputs) in enumerate(I.STAGES[2:], 2):
            stage = copy.deepcopy(self.value['stages'][0])
            stage.update(id=name, started_ns=index * 100 + 1, ended_ns=index * 100 + 2,
                         inputs=[{'id': x, 'sha256': available[x]} for x in inputs],
                         outputs=[{'id': x, 'sha256': I.digest(x.encode())} for x in outputs])
            stage['usage']['total_bytes'] = 100000 * (index + 1)
            stage['usage']['log_bytes'] = 100 * (index + 1)
            available.update({x['id']: x['sha256'] for x in stage['outputs']})
            self.value['stages'].append(stage)
        self.assertEqual(len(self.check()['checked_prefix']), 4)
        self.assertEqual(self.check()['acceptance'], 'not-accepted')

    def test_strict_json_duplicates_nan_and_depth(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'[' * 2000 + b'0' + b']' * 2000):
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                R.decode(raw)
        with self.assertRaisesRegex(ValueError, 'budget'):
            R.decode(b'12345', 4)

    def test_scope_version_boolean_and_extra_fields(self):
        for field, value in (('version', '0.1'), ('scope', 'qualified'), ('runtime_qualification', 0), ('extra', True)):
            self.bad(lambda v: v.update({field: value}), 'phase-(scope|root-fields)')

    def test_duplicate_skip_reordered_and_future_stage(self):
        self.bad(lambda v: v['stages'].__setitem__(1, copy.deepcopy(v['stages'][0])), 'stage-order')
        self.bad(lambda v: v['stages'].reverse(), 'stage-order')
        self.bad(lambda v: v['stages'][1].update(id='final-link'), 'stage-order')

    def test_plan_cycle_or_readiness_change(self):
        for change in (lambda p: p['stages'][0].update(after=['postprocess']),
                       lambda p: p.update(reset_resource_budget=True),
                       lambda p: p['link'].update(reenter_make=True)):
            recipe = copy.deepcopy(self.recipe)
            change(recipe['phase_plan'])
            with self.assertRaisesRegex(ValueError, 'plan-drift'):
                R.check_declarations(self.value, recipe, self.sha)

    def test_missing_duplicate_and_unknown_inputs(self):
        self.bad(lambda v: v['stages'][1]['inputs'].pop(), 'reference-count')
        self.bad(lambda v: v['stages'][1]['inputs'][3].update(id='sdk'), 'reference-order')
        self.bad(lambda v: v['stages'][1]['inputs'][3].update(id='future'), 'reference-order')

    def test_producer_hash_replacement_rejected(self):
        self.bad(lambda v: v['stages'][1]['inputs'][3].update(sha256='a' * 64), 'input-origin')
        self.bad(lambda v: v['external_inputs'][0].update(sha256='a' * 64), 'external-input-binding')

    def test_before_first_error_cannot_be_hidden_by_capture(self):
        self.bad(lambda v: v['stages'][1].update(first_error='compiler failed'), 'first-error')

    def test_zero_build_exit_and_missing_or_duplicate_capture(self):
        self.bad(lambda v: v['stages'][1].update(build_exit=0), 'expected-interception')
        self.bad(lambda v: v['stages'][1].update(interceptions=[]), 'expected-interception')
        self.bad(lambda v: v['stages'][1]['interceptions'].append(v['stages'][1]['interceptions'][0]), 'expected-interception')

    def test_forged_capture_target_exit_and_fake_output(self):
        for field, value in (('target', 'main'), ('exit_code', 0), ('exit_code', True),
                             ('driver_executed', True), ('output_existed', True)):
            self.bad(lambda v: v['stages'][1]['interceptions'][0].update({field: value}), 'interception-boundary')
        self.bad(lambda v: v['stages'][1]['interceptions'][0].update(sha256='b' * 64), 'capture-binding')

    def test_closure_writers_aliases_and_boolean_counts(self):
        for field, value in (('streams_closed', False), ('frozen', False), ('descendants', 1),
                             ('writers', 1), ('writable_aliases', 1), ('writers', False)):
            self.bad(lambda v: v['stages'][1].update({field: value}), 'phase-(not-closed|live-writer|natural)')

    def test_time_rollbacks_and_batch_deadline_not_renewed(self):
        self.bad(lambda v: v['stages'][1].update(started_ns=0), 'time-order')
        end = (self.recipe['policy']['resources']['deadline_seconds'] - 60) * 10**9
        self.bad(lambda v: v['stages'][1].update(ended_ns=end), 'batch-deadline')

    def test_resource_limits_reserve_and_log_reset(self):
        r = self.recipe['policy']['resources']
        for field, value in (('memory_peak_bytes', r['memory_bytes'] + 1), ('swap_peak_bytes', 1),
                             ('oom_kill', 1), ('pids_denied', 1), ('inventory_bytes', 2**40)):
            self.bad(lambda v: v['stages'][1]['usage'].update({field: value}), 'resource-limit')
        self.bad(lambda v: v['stages'][1]['usage'].update(total_bytes=r['writable_bytes']), 'storage-budget')
        self.bad(lambda v: v['stages'][1]['usage'].update(log_bytes=0), 'log-budget-or-reset')

    def test_unused_or_missing_stage_field_is_not_ignored(self):
        self.bad(lambda v: v['stages'][0].update(success=True), 'stage-fields')
        self.bad(lambda v: v['stages'][0].pop('control_record_sha256'), 'stage-fields')

    def test_cumulative_counters_cannot_reset_at_stage_boundary(self):
        for field in ('memory_peak_bytes', 'events_bytes', 'inventory_bytes'):
            self.bad(lambda v: v['stages'][1]['usage'].update({field: 0}), 'counter-rollback')


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cvc5-capture-test-', dir=ROOT / '.tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.output = self.root / 'capture.json'
        self.environment = C2.policy('capture-synthetic', 123)['environment']['values']
        self.tool = ROOT / 'scripts/cvc5-build-support/capture_link.py'

    def invoke(self, argv=None, environment=None):
        # Darwin Python injects a CoreFoundation key even with env=closed.
        # The synthetic harness removes only that host artifact after import;
        # the production Linux allowlist is deliberately not widened for it.
        harness = ('import importlib.util,os,sys; '
                   'p=sys.argv.pop(1); s=importlib.util.spec_from_file_location("capture",p); '
                   'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                   'os.environ.pop("__CF_USER_TEXT_ENCODING",None); sys.exit(m.main())')
        command = [sys.executable, '-c', harness, str(self.tool), '--output', str(self.output), '--']
        command += argv if argv is not None else ['/synthetic/driver', 'one two', '-la', '-la', '', 'line\nbreak']
        return subprocess.run(command, cwd=self.root, env=environment or self.environment,
                              capture_output=True, timeout=10, check=False)

    def test_actual_child_stops_without_running_marking_driver(self):
        marker = self.root / 'driver-was-run'
        fake = self.root / 'synthetic-driver.py'
        fake.write_text('from pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("unexpected")\n')
        result = self.invoke([sys.executable, str(fake), '-la', '-la', 'with space', ''])
        self.assertEqual(result.returncode, 78, result.stderr)
        self.assertFalse(marker.exists())
        value = json.loads(self.output.read_bytes())
        self.assertEqual(value['argv'], [sys.executable, str(fake), '-la', '-la', 'with space', ''])
        self.assertEqual(value['cwd'], str(self.root))
        self.assertFalse(value['driver_executed'])
        self.assertEqual(value['exit_code'], 78)

    def test_repeated_capture_cannot_replace_first(self):
        first = self.invoke()
        self.assertEqual(first.returncode, 78, first.stderr)
        raw = self.output.read_bytes()
        self.assertEqual(self.invoke(['/different/driver']).returncode, 1)
        self.assertEqual(self.output.read_bytes(), raw)

    def test_unknown_environment_fails_without_copying_values(self):
        secret = 'synthetic-only-never-copy-this-value'
        result = self.invoke(environment=dict(self.environment, SYNTHETIC_SECRET=secret))
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.output.exists())
        self.assertNotIn(secret.encode(), result.stdout + result.stderr)

    def test_symlink_output_does_not_touch_target(self):
        other = self.root / 'target'
        other.write_bytes(b'keep')
        self.output.symlink_to(other)
        self.assertEqual(self.invoke().returncode, 1)
        self.assertEqual(other.read_bytes(), b'keep')

    def test_partial_write_failure_is_preserved(self):
        class FailingStream(io.BytesIO):
            def __exit__(self, *args):
                return False

            def write(self, raw):
                super().write(raw[:8])
                raise OSError('synthetic disk full')
        stream = FailingStream()
        with patch.object(Path, 'open', return_value=stream), self.assertRaises(OSError):
            C.write_capture(self.output, b'partial-record-kept')
        self.assertEqual(stream.getvalue(), b'partial-')

    def test_count_input_and_encoded_budgets(self):
        for args in ([], ['x'] * (C.ARG_LIMIT + 1), ['x' * C.BYTE_LIMIT], ['\n' * (C.BYTE_LIMIT // 2)]):
            with self.subTest(size=len(args)), self.assertRaises(ValueError):
                C.observation(args, '/synthetic', self.environment)

    def test_no_process_network_delete_or_exec_calls(self):
        for name in ('capture_link', 'phase_rules', 'phase_recipe', 'link_formats', 'link_materials'):
            tree = ast.parse((ROOT / 'scripts/cvc5-build-support' / (name + '.py')).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse({'subprocess', 'socket', 'requests', 'urllib', 'shutil'} & {x.name.split('.')[0] for x in node.names})
                if isinstance(node, ast.Call):
                    method = node.func.attr if isinstance(node.func, ast.Attribute) else ''
                    self.assertNotIn(method, ('system', 'popen', 'execv', 'execve', 'spawnv', 'unlink', 'rmtree'))


class VersionAndPatchTests(unittest.TestCase):
    def test_explicit_version_and_rehashed_extra_field_rejected(self):
        expected = I.fixture_recipe()
        with tempfile.TemporaryDirectory(prefix='cvc5-version-test-', dir=ROOT / '.tmp') as temp:
            path = Path(temp).resolve() / 'recipe.json'
            path.write_bytes(I.encoded(expected))
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'recipe-format'):
                C2.checked_plan(path, sha)
            with patch.object(C2, 'generate', return_value=expected):
                self.assertEqual(C2.checked_plan(path, sha, '0.2'), expected)
                mutated = dict(expected, extra='not-ignored')
                path.write_bytes(I.encoded(mutated))
                with self.assertRaisesRegex(ValueError, 'recipe-drift'):
                    C2.checked_plan(path, hashlib.sha256(path.read_bytes()).hexdigest(), '0.2')

    def test_old_frozen_bytes_and_new_bound_command_changes_are_exact(self):
        self.assertEqual(hashlib.sha256(I.OLD.read_bytes()).hexdigest(), I.OLD_SHA)
        config = I.fixture_recipe()['main_phase']['configuration']
        old = C2.cvc5_commands(config, 'a' * 64)
        new = P.bound_steps(old)
        self.assertEqual(old[0], new[0])
        self.assertEqual(old[2]['argv'], new[2]['argv'])
        self.assertEqual(old[3:], new[-4:])
        self.assertEqual([r['id'] for r in new[3:7]], ['link-interception-review', 'freeze-main-inputs',
                                                       'cvc5-final-link', 'final-link-review'])
        self.assertNotIn('expected_exit', old[2])
        self.assertFalse(new[5]['executed'])

    def test_exact_source_patch_only_adds_target_launcher(self):
        base = I.fixture_recipe()
        review = P.patch_review(base, ROOT, C2.identity, C2.PATCH)
        previous = json.loads((ROOT / C2.SOURCE_RECORDS / 'patch-review.json').read_bytes())
        self.assertEqual(review['before_tree_digest'], previous['after']['inventory_digest'])
        self.assertEqual(review['changed_files'], ['src/main/CMakeLists.txt'])
        self.assertFalse(review['configured'])
        self.assertFalse(review['materialized'])
        source = next(x for x in base['source_inputs'] if x['id'] == 'cvc5')
        original = (ROOT / source['source_root'] / 'src/main/CMakeLists.txt').read_bytes()
        raw = (ROOT / P.PATCH_PATH).read_bytes()
        with self.assertRaisesRegex(ValueError, 'preimage-mismatch'):
            C2.PATCH.apply_exact(raw, {'src/main/CMakeLists.txt': original.replace(b'add_executable(cvc5-bin', b'add_executable(other')}, {'src/main/CMakeLists.txt'})

    def test_bound_envelope_rejects_unknown_fields_and_duplicate_references(self):
        recipe = P.upgrade(json.loads(I.OLD.read_bytes()), ROOT, C2.identity, C2.PATCH)
        P.check_bound_structure(recipe)
        for change in (lambda v: v.update(extra=True), lambda v: v.update(preparation_only=1),
                       lambda v: v['main_phase'].update(extra=True),
                       lambda v: v['references'].append(v['references'][0])):
            bad = copy.deepcopy(recipe)
            change(bad)
            with self.assertRaises(ValueError):
                P.check_bound_structure(bad)

    def test_v2_manifest_binding_emits_stage_data_and_keeps_blockers(self):
        recipe = P.upgrade(json.loads(I.OLD.read_bytes()), ROOT, C2.identity, C2.PATCH)
        recipe['references'] = [C2.identity(ROOT / r['path']) for r in recipe['references']]
        raw = C2.encoded(recipe)
        sha = hashlib.sha256(raw).hexdigest()
        manifest_path = Path('/work/review/build-inputs.json')
        manifest = {'header_roots': {}, 'archives': {}, 'closure_review': {'path': '/work/review/closure.json'}}
        actual_reader = C2.read_json

        def read(path):
            return (b'synthetic-manifest', manifest) if path == manifest_path else actual_reader(path)

        with patch.object(C2, 'read_phase_json', return_value=(raw, recipe)), \
                patch.object(C2, 'read_json', side_effect=read), \
                patch.object(C2.BUILD, 'check', return_value={'scope': 'synthetic-byte-preflight'}) as check:
            value = C2.bind_inputs(Path('/synthetic/recipe.json'), sha, manifest_path, 'a' * 64, '0.2')
        check.assert_called_once_with(manifest_path, 'a' * 64)
        self.assertEqual(value['version'], '0.2')
        self.assertEqual(value['blocking_conditions'], recipe['blocking_conditions'])
        self.assertFalse(value['execution_ready'])
        self.assertFalse(value['build_ready'])
        self.assertEqual(value['executed_recipe_steps'], [])
        self.assertEqual(value['steps'][5]['operation'], 'dispatch-reviewed-captured-driver')


if __name__ == '__main__':
    unittest.main()
