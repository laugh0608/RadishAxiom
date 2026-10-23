#!/usr/bin/env python3
"""Synthetic adversarial layout and event checks; no SDK or command execution."""
import ast
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


LAYOUT = load('execution_review', 'scripts/prepare-cvc5-execution-review.py')
RULES = load('build_events', 'scripts/cvc5-build-support/event_rules.py')
ZERO = '0' * 64
RECIPE = json.loads((ROOT / 'docs/records/solver-cvc5-c2-2026-10-23/offline-build-recipe.json').read_bytes())


def file(path, mode='0644'):
    return {'path': path, 'kind': 'file', 'mode': mode, 'bytes': 3,
            'sha256': hashlib.sha256(b'abc').hexdigest()}


def link(path, target, kind='symlink', mode='0777'):
    return {'path': path, 'kind': kind, 'mode': mode, 'bytes': 0, 'target': target}


def package(entries, name='synthetic'):
    return {'package': name, 'version': '1', 'data': {'entries': entries}}


class LayoutTests(unittest.TestCase):
    def layout(self, entries):
        return LAYOUT.layout([package(entries)])

    def test_parents_order_and_identity(self):
        result = self.layout([file('usr/lib/a'), link('usr/lib/b', 'a')])
        self.assertEqual([e['path'] for e in result['entries']], ['usr', 'usr/lib', 'usr/lib/a', 'usr/lib/b'])
        self.assertEqual(result['summary']['implicit_directories'], 2)
        self.assertEqual(result['entries'][-1]['resolution']['path'], 'usr/lib/a')
        self.assertEqual(result['summary']['regular_bytes'], 3)

    def test_identical_overlap_preserves_both_owners(self):
        result = LAYOUT.layout([package([file('a')]), package([file('a')], 'second')])
        self.assertEqual(result['entries'][0]['owners'], [['synthetic', '1'], ['second', '1']])
        self.assertEqual(result['summary']['regular_bytes'], 3)

    def test_conflicting_overlap(self):
        for changed in ({'sha256': ZERO}, {'bytes': 4}, {'mode': '0755'}):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'collision'):
                LAYOUT.layout([package([file('a')]), package([{**file('a'), **changed}], 'second')])

    def test_duplicate_package_and_entry(self):
        with self.assertRaisesRegex(ValueError, 'package-identity'):
            LAYOUT.layout([package([file('a')]), package([file('b')])])
        with self.assertRaisesRegex(ValueError, 'package-duplicate'):
            self.layout([file('a'), file('a')])

    def test_nondirectory_ancestors(self):
        for parent in (file('a'), link('a', '/b')):
            with self.subTest(parent=parent), self.assertRaisesRegex(ValueError, 'nondirectory-ancestor'):
                self.layout([parent, file('a/x')])

    def test_path_rejection(self):
        for path in ('../a', '/a', 'a//b', 'a/./b', 'a\\b', 'a\x00b', 'a\nb'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.layout([file(path)])

    def test_link_escape_and_ambiguous_parent(self):
        for target in ('../../outside', 'x/../y', 'a\\b', '\x00'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.layout([link('lib/a', target)])

    def test_absolute_link_stays_virtual(self):
        result = self.layout([file('lib/a'), link('usr/b', '/lib/a')])
        self.assertEqual(result['entries'][-1]['resolution']['path'], 'lib/a')

    def test_parent_relative_link(self):
        result = self.layout([file('lib/a'), link('usr/b', '../lib/a')])
        self.assertEqual(result['entries'][-1]['resolution']['path'], 'lib/a')

    def test_link_cycle_and_depth(self):
        with self.assertRaisesRegex(ValueError, 'cycle'):
            self.layout([link('a', 'b'), link('b', 'a')])
        with self.assertRaisesRegex(ValueError, 'depth'):
            self.layout([link('p' + str(n), 'p' + str(n + 1)) for n in range(41)] + [file('p41')])

    def test_dangling_link_is_explicit_blocker(self):
        result = self.layout([link('usr/a', '/etc/alternatives/a')])
        self.assertEqual(result['unresolved_symlinks'][0]['link_path'], 'usr/a')
        self.assertEqual(result['unresolved_symlinks'][0]['status'], 'missing')

    def test_hardlink_resolved_and_modes_bound(self):
        result = self.layout([file('bin/a', '0755'), link('bin/b', './bin/a', 'hardlink', '0755')])
        self.assertEqual(result['entries'][-1]['resolution']['path'], 'bin/a')
        for target, mode in (('missing', '0755'), ('bin', '0755'), ('bin/a', '0644')):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'hardlink'):
                self.layout([file('bin/a', '0755'), link('b', target, 'hardlink', mode)])

    def test_special_modes_are_explicit_changes(self):
        result = self.layout([file('a', '4755'), file('b', '2755')])
        self.assertEqual(result['permission_changes'], [
            {'path': 'a', 'from': '4755', 'to': '0755'}, {'path': 'b', 'from': '2755', 'to': '0755'}])

    def test_special_files_and_bool_size_rejected(self):
        for changed in ({'kind': 'fifo'}, {'kind': 'device'}, {'bytes': True}, {'mode': '9999'},
                        {'bytes': 129 * 1024**2}, {'sha256': 'bad'}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.layout([{**file('a'), **changed}])

    def test_nonfile_bytes_rejected(self):
        with self.assertRaisesRegex(ValueError, 'nonfile-payload'):
            self.layout([{**link('a', 'b'), 'bytes': 1}])

    def test_entry_and_total_budget(self):
        with patch.object(LAYOUT, 'ENTRY_LIMIT', 1), self.assertRaisesRegex(ValueError, 'entry-budget'):
            self.layout([file('a/b')])
        with patch.object(LAYOUT.C2, 'TOTAL_LIMIT', 2), self.assertRaisesRegex(ValueError, 'total-byte-budget'):
            self.layout([file('a')])

    def test_hardlink_through_symlink_rejected(self):
        with self.assertRaisesRegex(ValueError, 'hardlink-through-symlink'):
            self.layout([file('a'), link('b', 'a'), link('c', 'b', 'hardlink', '0644')])

    def test_real_retained_inventory_correspondence(self):
        ref = RECIPE['sdk']['inventory']
        raw = (ROOT / ref['path']).read_bytes()
        self.assertEqual(len(raw), ref['bytes'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), ref['sha256'])
        inventory = json.loads(gzip.decompress(raw))
        packages = [p for p in inventory['observations'] if p['kind'] == 'binary']
        result = LAYOUT.layout(packages)
        actual = {e['path']: e for e in result['entries']}
        expected_paths = {e['path'] for p in packages for e in p['data']['entries']}
        self.assertEqual(set(actual), expected_paths)
        for p in packages:
            for e in p['data']['entries']:
                row = actual[e['path']]
                self.assertIn([p['package'], p['version']], row['owners'])
                for key in ('kind', 'bytes', 'sha256', 'target'):
                    self.assertEqual(row.get(key), e.get(key))
                self.assertEqual(row['archive_mode'], e['mode'])
                self.assertEqual(int(row['candidate_mode'], 8), int(e['mode'], 8) & 0o1777)
        self.assertEqual(result['summary'], {'packages': 172, 'archive_entries': 17125,
            'unique_paths': 14719, 'regular_bytes': 537445262,
            'kinds': {'directory': 1367, 'file': 12525, 'hardlink': 5, 'symlink': 822},
            'implicit_directories': 0})
        self.assertEqual(result['unresolved_symlinks'], [
            {'link_path': 'etc/rmt', 'status': 'missing', 'path': 'usr/sbin/rmt', 'trail': ['etc/rmt']}])
        self.assertEqual({r['path'] for r in result['permission_changes']},
                         {'bin/su', 'sbin/unix_chkpwd', 'usr/bin/newgrp', 'usr/bin/wall', 'var/local'})
        for row in result['entries']:
            if row['kind'] in ('symlink', 'hardlink') and row['path'] != 'etc/rmt':
                self.assertEqual(row['resolution']['status'], 'resolved')


class EventTests(unittest.TestCase):
    def setUp(self):
        self.recipe = copy.deepcopy(RECIPE)
        self.rule = RULES.DeclaredBuildTrace(self.recipe, ZERO, 0)

    def send(self, kind, **values):
        self.rule.feed({'kind': kind, 'at_ns': 1, **values})

    def start(self, step=None):
        step = step or self.recipe['dependency_steps'][0]
        self.send('start', step_id=step['id'], step_sha256=RULES.binding(step))

    def sample(self, **overrides):
        self.send('sample', memory_peak_bytes=overrides.pop('memory_peak_bytes', 1),
                  swap_peak_bytes=overrides.pop('swap_peak_bytes', 0),
                  writable_bytes=overrides.pop('writable_bytes', self.rule.total_log_bytes),
                  oom_kill=overrides.pop('oom_kill', 0), pids_denied=overrides.pop('pids_denied', 0),
                  events_bytes=overrides.pop('events_bytes', 0), inventory_bytes=overrides.pop('inventory_bytes', 0),
                  **overrides)

    def finish(self):
        self.send('finish', exit_code=0, capture_sha256=ZERO)

    def test_full_frozen_schedule_synthetic_only(self):
        for step in self.recipe['dependency_steps']:
            if step['operation'] == 'review-gate':
                self.send('review', step_id=step['id'], evidence_sha256=ZERO)
                continue
            selected = step['choices'][1]['step'] if step['operation'] == 'select-command' else step
            self.send('start', step_id=step['id'], step_sha256=RULES.binding(selected))
            for stream in list(self.rule.active['streams']):
                self.send('log', stream=stream, data=b'synthetic\n')
                self.send('close-log', stream=stream)
            self.sample()
            self.finish()
        result = self.rule.result()
        self.assertTrue(result['sequence_complete'])
        self.assertFalse(result['execution_ready'])
        self.assertFalse(result['build_ready'])
        self.assertEqual(len(result['completed']) + len(result['reviews']), 32)
        self.assertEqual(result['completed'][0]['streams']['stdout']['sha256'], hashlib.sha256(b'synthetic\n').hexdigest())

    def test_step_order_and_changed_command(self):
        for event in ({'step_id': 'gmp-build', 'step_sha256': ZERO},
                      {'step_id': self.recipe['dependency_steps'][0]['id'], 'step_sha256': ZERO}):
            self.rule = RULES.DeclaredBuildTrace(self.recipe, ZERO, 0)
            with self.subTest(event=event), self.assertRaisesRegex(ValueError, 'step-(order|binding)'):
                self.send('start', **event)

    def test_gate_cannot_be_command(self):
        gate = next(s for s in self.recipe['dependency_steps'] if s['operation'] == 'review-gate')
        self.recipe['dependency_steps'] = [gate]
        self.rule = RULES.DeclaredBuildTrace(self.recipe, ZERO, 0)
        with self.assertRaisesRegex(ValueError, 'gate-cannot-execute'):
            self.start(gate)

    def test_missing_review_cannot_skip(self):
        self.recipe['dependency_steps'] = self.recipe['dependency_steps'][13:15]
        self.rule = RULES.DeclaredBuildTrace(self.recipe, ZERO, 0)
        with self.assertRaisesRegex(ValueError, 'order'):
            self.start(self.recipe['dependency_steps'][1])

    def test_clock_rollback_and_deadline(self):
        self.sample()
        with self.assertRaisesRegex(ValueError, 'clock-rollback'):
            self.sample(at_ns=0)
        self.rule = RULES.DeclaredBuildTrace(self.recipe, ZERO, 0)
        with self.assertRaisesRegex(ValueError, 'deadline-reserve'):
            self.sample(at_ns=5340 * 10**9)

    def test_no_deadline_renewal_between_steps(self):
        self.start()
        self.sample(at_ns=5339 * 10**9)
        with self.assertRaisesRegex(ValueError, 'deadline-reserve'):
            self.send('close-log', stream='stdout', at_ns=5340 * 10**9)

    def test_budget_and_counter_failures(self):
        cases = [({'memory_peak_bytes': 8 * 1024**3 + 1}, 'memory-limit'),
                 ({'swap_peak_bytes': 1}, 'swap-limit'), ({'oom_kill': 1}, 'cgroup-failure'),
                 ({'pids_denied': 1}, 'cgroup-failure'), ({'writable_bytes': 20 * 1024**3}, 'disk-reserve'),
                 ({'events_bytes': 32 * 1024**2 + 1}, 'evidence-budget'),
                 ({'inventory_bytes': 64 * 1024**2 + 1}, 'evidence-budget'),
                 ({'events_bytes': 1, 'writable_bytes': 0}, 'storage-accounting')]
        for kwargs, error in cases:
            self.rule = RULES.DeclaredBuildTrace(self.recipe, ZERO, 0)
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, error):
                self.sample(**kwargs)
        self.rule = RULES.DeclaredBuildTrace(self.recipe, ZERO, 0)
        self.sample(memory_peak_bytes=100)
        with self.assertRaisesRegex(ValueError, 'counter-rollback'):
            self.sample(memory_peak_bytes=99)

    def test_log_budget_sticky_failure_and_partial_digest(self):
        self.recipe['evidence']['log_limits']['stdout_per_step_bytes'] = 3
        self.rule = RULES.DeclaredBuildTrace(self.recipe, ZERO, 0)
        self.start()
        self.send('log', stream='stdout', data=b'abc')
        with self.assertRaisesRegex(ValueError, 'stream-budget'):
            self.send('log', stream='stdout', data=b'd')
        with self.assertRaisesRegex(ValueError, 'stream-budget'):
            self.sample()
        result = self.rule.result()
        self.assertTrue(result['termination_required'])
        self.assertTrue(result['retention_required'])
        self.assertFalse(result['automatic_cleanup'])
        self.assertEqual(result['partial']['streams']['stdout']['sha256'], hashlib.sha256(b'abc').hexdigest())

    def test_aggregate_log_budget(self):
        self.recipe['evidence']['log_limits']['all_logs_bytes'] = 3
        self.rule = RULES.DeclaredBuildTrace(self.recipe, ZERO, 0)
        self.start()
        self.send('log', stream='stdout', data=b'abc')
        with self.assertRaisesRegex(ValueError, 'total-log-budget'):
            self.send('log', stream='stderr', data=b'd')

    def test_event_count_and_chunk_budget(self):
        self.rule.event_count = 100000
        with self.assertRaisesRegex(ValueError, 'count-budget'):
            self.sample()
        self.rule = RULES.DeclaredBuildTrace(self.recipe, ZERO, 0)
        self.start()
        with self.assertRaisesRegex(ValueError, 'chunk-budget'):
            self.send('log', stream='stdout', data=b'x' * (1024**2 + 1))

    def test_bool_exit_and_unbound_review(self):
        self.start()
        with self.assertRaisesRegex(ValueError, 'step-exit'):
            self.send('finish', exit_code=False, capture_sha256=ZERO)
        gate = next(s for s in self.recipe['dependency_steps'] if s['operation'] == 'review-gate')
        self.recipe['dependency_steps'] = [gate]
        self.rule = RULES.DeclaredBuildTrace(self.recipe, ZERO, 0)
        with self.assertRaisesRegex(ValueError, 'sha256'):
            self.send('review', step_id=gate['id'], evidence_sha256='accepted')

    def test_trace_log_required(self):
        step = next(s for s in self.recipe['dependency_steps'] if s['id'] == 'dependency-probes')
        self.recipe['dependency_steps'] = [step]
        self.rule = RULES.DeclaredBuildTrace(self.recipe, ZERO, 0)
        self.start(step)
        self.send('close-log', stream='stdout')
        self.send('close-log', stream='stderr')
        self.sample()
        with self.assertRaisesRegex(ValueError, 'incomplete-log'):
            self.finish()

    def test_sample_required_after_log(self):
        self.start()
        self.sample()
        self.send('log', stream='stdout', data=b'x')
        self.send('close-log', stream='stdout')
        self.send('close-log', stream='stderr')
        with self.assertRaisesRegex(ValueError, 'missing-final-resource'):
            self.finish()

    def test_stream_after_close(self):
        self.start()
        self.send('close-log', stream='stdout')
        with self.assertRaisesRegex(ValueError, 'stream-closed'):
            self.send('log', stream='stdout', data=b'x')

    def test_nonzero_exit_and_losses(self):
        for kind, extra in [('finish', {'exit_code': 7, 'capture_sha256': ZERO}),
                            ('cancel', {'reason': 'synthetic cancel'}),
                            ('observer-loss', {'reason': 'synthetic overflow'}),
                            ('input-failure', {'reason': 'unmapped header'})]:
            self.rule = RULES.DeclaredBuildTrace(self.recipe, ZERO, 0)
            self.start()
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.send(kind, **extra)
            self.assertFalse(self.rule.result()['sequence_complete'])

    def test_boolean_number_unknown_field_and_kind(self):
        for event in ({'kind': 'sample', 'at_ns': True}, {'kind': 'tick', 'at_ns': 0},
                      {'kind': 'cancel', 'at_ns': 0, 'reason': 'x', 'approved': True}):
            self.rule = RULES.DeclaredBuildTrace(self.recipe, ZERO, 0)
            with self.subTest(event=event), self.assertRaises(ValueError):
                self.rule.feed(event)

    def test_inputs_and_results_not_mutable_aliases(self):
        self.recipe['dependency_steps'][0]['argv'].append('wrong')
        self.start(self.rule.steps[0])
        self.send('log', stream='stdout', data=b'x')
        result = self.rule.result()
        result['partial']['streams']['stdout']['bytes'] = 900
        self.assertEqual(self.rule.result()['partial']['streams']['stdout']['bytes'], 1)

    def test_no_external_execution_imports(self):
        for path in ('scripts/prepare-cvc5-execution-review.py', 'scripts/cvc5-build-support/event_rules.py'):
            tree = ast.parse((ROOT / path).read_text())
            imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
            imports |= {a.name for node in ast.walk(tree) if isinstance(node, ast.Import) for a in node.names}
            self.assertFalse(imports & {'subprocess', 'socket', 'urllib', 'requests', 'shutil', 'tarfile'})


if __name__ == '__main__':
    unittest.main()
