#!/usr/bin/env python3
"""Synthetic v3 batch, lifecycle, export and replay checks; no Docker or GnuPG."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collector = load('collect-gmp-verification-v3.py')
run = collector.run
s = load('check-gmp-verification.py')
s.p = run.profile


class RecordingDocker(s.inherited.FakeDocker):
    """Record synthetic responses through the real six-step batch and lifecycle."""
    def __init__(self, directory, *, bad_cert=False, fail_step=None, **kwargs):
        super().__init__(**kwargs)
        self.directory, self.bad_cert, self.fail_step = directory, bad_cert, fail_step
        self.responses = []
        (directory / 'docker-config').mkdir()

    def call(self, args, *, seconds=10, limit=262144):
        if args[0] == 'version':
            value = {'Server.Version': '29.4.0', 'Server.ApiVersion': '1.54', 'Server.Os': 'linux', 'Server.Arch': 'arm64'}
        elif args[0] == 'info':
            value = {name: True for name in ('MemoryLimit', 'SwapLimit', 'PidsLimit', 'CpuCfsPeriod', 'CpuCfsQuota')}
            value.update(CgroupVersion='2', SecurityOptions=['name=seccomp,profile=builtin', 'name=cgroupns'])
        elif args[:2] == ['image', 'inspect']:
            value = s.inherited.smoke_tests.image_fixture()
            value['Id'] = run.IMAGE
        else:
            value = None
        if value is not None:
            self.sequence += 1
            result = s.inherited.smoke_tests.result(json.dumps(value).encode())
        else:
            if args[:2] == ['container', 'create']:
                self.step = args[args.index('--name') + 1].split('-', 4)[4]
                expired = f'[GNUPG:] KEYEXPIRED {run.profile.EXPIRES["pub"]}\n'
                considered = f'[GNUPG:] KEY_CONSIDERED {run.profile.PRIMARY} 0\n'
                self.status_raw = {'filter': (expired + '[GNUPG:] IMPORT_RES 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n').encode(),
                    'certifications': (expired + considered + expired * (3 if self.bad_cert else 2)).encode(),
                    'verify': s.good().encode(),
                    'tampered-body': (f'[GNUPG:] NEWSIG\n{considered}'
                                      f'[GNUPG:] BADSIG {run.profile.PRIMARY[-16:]} Synthetic\n').encode(),
                    'wrong-primary': s.missing().encode(), 'missing-primary': s.missing().encode()}[self.step]
                self.code = 1 if self.step == 'tampered-body' else 2 if self.step in {'wrong-primary', 'missing-primary'} else 0
                self.failure = 'deadline' if self.step == self.fail_step else None
            result = super().call(args, seconds=seconds, limit=limit)
            if args[:2] == ['container', 'start']:
                result['stdout'] = (s.raw_key() if self.step == 'filter' else
                                    s.colons().replace(b'1736961679', b'1736961163')
                                    if self.step == 'certifications' else b'')
        result['seconds'] = 0.001
        record = {**result, 'argv': [run.smoke.DOCKER, '--host', 'unix://' + run.smoke.SOCKET,
                  '--config', str(self.directory / 'docker-config'), *args],
                  'seconds_limit': seconds, 'bytes_limit': limit,
                  'started_at': run.smoke.now(), 'finished_at': run.smoke.now()}
        self.responses.append(record)
        saved = dict(record)
        for channel in ('stdout', 'stderr'):
            (self.directory / f'{self.sequence:03d}.{channel}').write_bytes(record[channel])
            saved[channel] = run.identity(record[channel])
        (self.directory / f'{self.sequence:03d}.json').write_text(json.dumps(saved))
        return result


class BatchReplayChecks(unittest.TestCase):
    def setUp(self):
        self.bindings = run.methods()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / '.tmp').mkdir()
        self.output = self.root / '.tmp/run'
        for target, name, value in [(run.profile, 'PRIMARY', s.PRIMARY), (run.profile, 'SUBKEY', s.SUBKEY),
                (run.profile, 'REVOCATION_SHA', run.identity(s.sig(revocation=True))['sha256']),
                (run.inputs.source, 'archive_binding', lambda raw: None),
                (run.profile.material, 'armor', lambda raw: s.raw_key(True)),
                (run.smoke, 'TAR_SHA', run.identity(b'synthetic rootfs')['sha256']),
                (s.inherited.smoke_tests.smoke, 'TAR_SHA', run.identity(b'synthetic rootfs')['sha256'])]:
            handle = patch.object(target, name, value)
            handle.start()
            self.addCleanup(handle.stop)
        raw = s.raw_key(True)
        strong, projection = run.profile.project(raw)
        self.files = {'gmp.tar.xz': b'synthetic archive', 'gmp.tar.xz.asc': b'synthetic signature',
                      'gmp.original.asc': b'synthetic armor', 'gmp.raw.gpg': raw, 'gmp.strong.gpg': strong,
                      'gmp.tampered.xz': b'synthetic archivf', 'wrong.gpg': b'synthetic wrong key', 'empty.gpg': b''}
        self.prepared = {'store': {'manifest': {'sha256': run.inputs.STORE[2]}}, 'source_acceptance': 'not-assessed',
                         'inputs': {k: run.identity(v) for k, v in self.files.items()}, 'projection': projection}

    def execute(self, *, drift=False, method_drift=False, **kwargs):
        def docker(directory):
            self.engine = RecordingDocker(directory, **kwargs)
            return self.engine

        with patch.object(run, 'ROOT', self.root), \
                patch.object(run, 'methods', side_effect=[self.bindings, {} if method_drift else self.bindings]), \
                patch.object(run.inputs, 'prepare', side_effect=[(self.prepared, self.files),
                    ({**self.prepared, 'changed': True} if drift else self.prepared, self.files)]), \
                patch.object(run.smoke, 'verified_inputs', return_value=(b'synthetic rootfs', {})), \
                patch.object(run.smoke, 'Docker', side_effect=docker):
            result = run.execute(self.output)
        self.assertEqual(json.loads((self.output / 'result.json').read_bytes()), result)
        return result

    def collect(self):
        with patch.object(run.inputs, 'prepare', return_value=(self.prepared, self.files)), \
                patch.object(run.smoke, 'Docker', side_effect=AssertionError('unexpected live Docker')):
            return collector.collect(self.output)

    def change_result(self, bundle, mutate):
        row = json.loads(collector.unpack({'result.json': bundle['files']['result.json']})['result.json'])
        mutate(row)
        bundle['files']['result.json'] = collector.entry(json.dumps(row).encode())

    def test_six_steps_collect_and_replay_without_original_directory(self):
        result = self.execute()
        self.assertTrue(result['passed'], result.get('failure'))
        self.assertEqual(len(self.engine.responses), 45)
        self.assertEqual([c['step'] for c in result['cases']], [step for step, _ in run.commands()])
        self.assertTrue(all(c['cleanup']['removed'] for c in result['cases']))
        cert = result['cases'][1]['assessment']
        self.assertEqual(cert['packet_declared_expiry']['sub'], 1736961679)
        self.assertEqual(cert['listed_effective_expiry']['sub'], 1736961163)
        self.assertEqual(cert['status_records'], 4)
        self.assertEqual(result['source_acceptance'], 'not-assessed')
        self.assertFalse(result['runtime_qualification'])
        self.assertEqual(result['historical_validity'], 'not-established')
        bundle = self.collect()
        self.assertTrue(bundle['replay']['replayed_success'])
        self.temp.cleanup()
        with patch.object(run.smoke, 'Docker', side_effect=AssertionError('unexpected live Docker')), \
                patch.object(run.inputs, 'prepare', side_effect=AssertionError('unexpected source preparation')):
            self.assertEqual(collector.replay(json.loads(json.dumps(bundle))), bundle['replay'])

    def test_rejected_certification_stops_after_cleanup_and_preserves_failure(self):
        result = self.execute(bad_cert=True)
        self.assertFalse(result['passed'])
        self.assertIn('fixed v3 certification status mismatch', result['failure'])
        self.assertEqual([c['step'] for c in result['cases']], ['filter', 'certifications'])
        self.assertEqual(len(self.engine.responses), 17)
        self.assertFalse(result['cases'][-1]['passed'])
        self.assertTrue(result['cases'][-1]['cleanup']['removed'])
        with patch.object(run.inputs, 'prepare', side_effect=AssertionError('unexpected preparation')):
            bundle = collector.collect(self.output)
        self.assertEqual(bundle['replay']['result'], 'failed-run-retained')
        self.assertFalse(bundle['replay']['failure_logs_replayed'])
        self.assertFalse(bundle['replay']['replayed_success'])
        self.assertEqual(len(collector.unpack(bundle['files'])['certifications.status'].splitlines()), 5)

    def test_timeout_kills_cleans_and_stops_batch(self):
        result = self.execute(fail_step='certifications')
        self.assertFalse(result['passed'])
        self.assertEqual(len(result['cases']), 2)
        self.assertIn('termination', result['cases'][-1])
        self.assertTrue(result['cases'][-1]['cleanup']['removed'])
        self.assertFalse(self.collect()['replay']['replayed_success'])

    def test_cleanup_failure_stops_before_assessment(self):
        result = self.execute(remove_failure=True)
        self.assertFalse(result['passed'])
        self.assertEqual(len(result['cases']), 1)
        self.assertFalse(result['cases'][0]['cleanup']['removed'])
        self.assertNotIn('assessment', result['cases'][0])
        self.assertFalse(self.collect()['replay']['replayed_success'])

    def test_source_drift_prevents_success_after_six_steps(self):
        result = self.execute(drift=True)
        self.assertFalse(result['passed'])
        self.assertEqual(len(result['cases']), 6)
        self.assertIn('changed during execution', result['failure'])

    def test_method_drift_prevents_success_after_six_steps(self):
        result = self.execute(method_drift=True)
        self.assertFalse(result['passed'])
        self.assertEqual(len(result['cases']), 6)
        self.assertIn('changed during execution', result['failure'])

    def test_success_report_and_basis_tampering_rejected(self):
        self.assertTrue(self.execute()['passed'])
        original = self.collect()
        for mutate in [lambda r: r.update(source_acceptance='accepted'),
                       lambda r: r.update(source_bytes_rechecked=False),
                       lambda r: r.update(passed=1),
                       lambda r: r.update(assessment_profile='gmp-auxiliary-expiry-v2'),
                       lambda r: r.update(certification_assessment_profile='other'),
                       lambda r: r['tool_source_inventory'].update(sha256='0' * 64),
                       lambda r: r['cases'][1]['assessment']['listed_effective_expiry'].update(sub=1736961679),
                       lambda r: r['cases'][1]['cleanup'].update(removed=False),
                       lambda r: r['cases'][2].update(observed_at=run.profile.CREATED),
                       lambda r: r['cases'].reverse()]:
            bundle = copy.deepcopy(original)
            self.change_result(bundle, mutate)
            with self.assertRaises(ValueError):
                collector.replay(bundle)

    def test_command_capture_status_and_retained_method_tampering_rejected(self):
        self.assertTrue(self.execute()['passed'])
        original = self.collect()
        for name, mutate in [('004.json', lambda r: r['argv'].append('--network=host')),
                             ('013.json', lambda r: r.update(bytes_limit=999))]:
            bundle = copy.deepcopy(original)
            row = json.loads(collector.unpack({name: bundle['files'][name]})[name])
            mutate(row)
            bundle['files'][name] = collector.entry(json.dumps(row).encode())
            with self.assertRaises(ValueError):
                collector.replay(bundle)
        for area, name, raw in [('files', 'certifications.status', b'[GNUPG:] KEYEXPIRED 1736961163\n'),
                               ('files', '013.stdout', b'changed listing'),
                               ('methods', 'docs/records/rust-linux-input-review/inspect-gmp-certification-v3.py', b'changed'),
                               ('methods', 'docs/records/rust-linux-input-review/gmp-tool-source-2026-09-29.json.gz', b'changed')]:
            bundle = copy.deepcopy(original)
            bundle[area][name] = collector.entry(raw)
            with self.assertRaises(ValueError):
                collector.replay(bundle)

    def test_failed_export_still_requires_bound_methods_and_trust_fields(self):
        self.execute(bad_cert=True)
        original = self.collect()
        for mutate in [lambda r: r.update(runtime_qualification=True), lambda r: r.update(failure=''),
                       lambda r: r.update(passed=None), lambda r: r.update(methods={})]:
            bundle = copy.deepcopy(original)
            self.change_result(bundle, mutate)
            with self.assertRaises(ValueError):
                collector.replay(bundle)

    def test_replay_reassesses_consistently_rehashed_certification_output(self):
        self.assertTrue(self.execute()['passed'])
        original = self.collect()
        for change_status in (True, False):
            bundle = copy.deepcopy(original)
            files = collector.unpack(bundle['files'])
            result = json.loads(files['result.json'])
            case = result['cases'][1]
            if change_status:
                name = 'certifications.status'
                raw = files[name] + b'[GNUPG:] KEYEXPIRED 1736961163\n'
                case['status'] = run.identity(raw)
                message = 'fixed v3 certification status mismatch'
            else:
                name = f'{case["start_command_number"]:03d}.stdout'
                raw = files[name].replace(b'sig:!', b'sig:?')
                case['stdout'] = run.identity(raw)
                log_name = f'{case["start_command_number"]:03d}.json'
                log = json.loads(files[log_name])
                log['stdout'] = run.identity(raw)
                bundle['files'][log_name] = collector.entry(json.dumps(log).encode())
                message = 'strong self certification not checked'
            bundle['files'][name] = collector.entry(raw)
            bundle['files']['result.json'] = collector.entry(json.dumps(result).encode())
            with self.assertRaisesRegex(ValueError, message):
                collector.replay(bundle)

    def test_existing_output_never_restarts_or_overwrites(self):
        self.assertTrue(self.execute()['passed'])
        original = (self.output / 'result.json').read_bytes()
        with patch.object(run, 'ROOT', self.root), patch.object(run, 'methods', return_value=self.bindings), \
                patch.object(run.smoke, 'Docker', side_effect=AssertionError('unexpected restart')):
            with self.assertRaises(FileExistsError):
                run.execute(self.output)
        self.assertEqual((self.output / 'result.json').read_bytes(), original)


class PlanChecks(unittest.TestCase):
    def test_default_cli_is_offline_and_preserves_limits_commands(self):
        with patch.object(run.smoke, 'Docker', side_effect=AssertionError('unexpected daemon')):
            plan = run.plan()
        result = subprocess.run([sys.executable, str(HERE / 'run-gmp-verification-v3.py')],
                                capture_output=True, check=True, timeout=5)
        self.assertEqual(json.loads(result.stdout), plan)
        self.assertFalse(plan['actions_executed'])
        self.assertEqual(run.commands(), run.prior.commands())
        self.assertNotEqual(run.OUTPUT, run.prior.OUTPUT)
        for field in ('image_id', 'run_seconds_each', 'batch_seconds_budget', 'input_bytes_total', 'fresh_tmpfs_each_invocation'):
            self.assertEqual(plan[field], run.prior.plan()[field])

    def test_source_basis_drift_stops_before_any_execution(self):
        with patch.object(run.candidate, 'BASIS_SHA', '0' * 64), \
                patch.object(run.smoke, 'Docker', side_effect=AssertionError('unexpected daemon')):
            with self.assertRaisesRegex(ValueError, 'source inventory drift'):
                run.plan()
            with self.assertRaisesRegex(ValueError, 'source inventory drift'):
                run.methods()

    def test_methods_cover_candidate_basis_and_exporter(self):
        bindings = run.methods()
        self.assertTrue(set(run.prior.methods()) <= set(bindings))
        for name in ('run-gmp-verification-v3.py', 'collect-gmp-verification-v3.py',
                     'inspect-gmp-certification-v3.py', 'gmp-tool-source-2026-09-29.json.gz'):
            self.assertEqual(bindings[str((HERE / name).relative_to(run.ROOT))], run.identity((HERE / name).read_bytes()))

    def test_old_bundle_versions_rejected(self):
        for version in ('v1', 'v2', 'v4'):
            with self.assertRaisesRegex(ValueError, 'bundle version drift'):
                collector.replay({'kind': 'diagnostic-gmp-verification-bundle-' + version})


if __name__ == '__main__':
    unittest.main()
