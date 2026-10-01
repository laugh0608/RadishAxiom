#!/usr/bin/env python3
"""Synthetic replay binding and encoding checks; no external processes."""
import base64
import copy
import json
import tempfile
import subprocess
import sys
from unittest.mock import patch
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('collector', HERE / 'collect-gmp-verification-v2.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def row():
    return {'argv': [collector.run.smoke.DOCKER, '--host', 'unix://' + collector.run.smoke.SOCKET,
                     '--config', str(collector.CACHE / 'docker-config'), 'container', 'rm', 'synthetic'],
            'seconds_limit': 10, 'bytes_limit': 262144, 'returncode': 0, 'failure': None,
            'stdout': b'synthetic\n', 'stderr': b''}


class ReplayChecks(unittest.TestCase):
    def test_exact_call_consumes_one_record(self):
        engine = collector.Replay([row()])
        self.assertEqual(engine.call(['container', 'rm', 'synthetic']), row())
        self.assertEqual(engine.sequence, 1)

    def test_wrong_target_or_operation_does_not_consume(self):
        for args in [['container', 'rm', 'other'], ['container', 'start', 'synthetic']]:
            engine = collector.Replay([row()])
            with self.assertRaises(ValueError):
                engine.call(args)
            self.assertEqual(engine.sequence, 0)

    def test_different_socket_or_config_is_rejected(self):
        for index in (0, 2, 4):
            changed = row()
            changed['argv'][index] = '/synthetic/other'
            with self.assertRaises(ValueError):
                collector.Replay([changed]).call(['container', 'rm', 'synthetic'])

    def test_capture_limit_drift_is_rejected(self):
        for kwargs in [{'seconds': 30}, {'limit': 1048576}]:
            with self.assertRaises(ValueError):
                collector.Replay([row()]).call(['container', 'rm', 'synthetic'], **kwargs)

    def test_exhaustion_never_falls_back_to_execution(self):
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            collector.Replay([]).call(['container', 'rm', 'synthetic'])

    def test_failed_record_remains_failed(self):
        changed = {**row(), 'returncode': 1, 'failure': 'deadline'}
        result = collector.Replay([changed]).call(['container', 'rm', 'synthetic'])
        with self.assertRaises(ValueError):
            collector.run.smoke.checked(result)

    def test_binary_and_unicode_streams_round_trip(self):
        for raw in [b'', b'\xff\x00\x80', '合成记录\n'.encode()]:
            encoded = collector.encoded(raw)
            restored = (encoded['data'].encode() if encoded['encoding'] == 'utf-8'
                        else base64.b64decode(encoded['data'], validate=True))
            self.assertEqual(restored, raw)

    def test_entry_identity_path_and_resource_bounds(self):
        self.assertEqual(collector.unpack({'example': collector.entry(b'\xffsynthetic')}), {'example': b'\xffsynthetic'})
        for name in ('../escape', '/absolute', 'a//b', './a'):
            with self.assertRaises(ValueError):
                collector.unpack({name: collector.entry(b'x')})
        changed = collector.entry(b'x')
        changed['data'] = 'y'
        with self.assertRaises(ValueError):
            collector.unpack({'example': changed})
        with patch.object(collector, 'FILE_LIMIT', 2), self.assertRaises(ValueError):
            collector.unpack({'example': collector.entry(b'xxx')})
        with patch.object(collector, 'TOTAL_LIMIT', 3), self.assertRaises(ValueError):
            collector.unpack({'a': collector.entry(b'xx'), 'b': collector.entry(b'xx')})

    def test_failed_run_never_acquires_success(self):
        bundle = {'kind': 'diagnostic-gmp-verification-bundle-v2',
                  'collector_method': collector.entry(Path(collector.__file__).read_bytes()),
                  'files': {'result.json': collector.entry(json.dumps({'kind': 'diagnostic-gmp-verification-run-v2', 'assessment_profile': collector.run.PROFILE, 'passed': False, 'failure': 'deadline'}).encode())}}
        self.assertFalse(collector.replay(bundle)['replayed_success'])

    def test_previous_bundle_and_unknown_revision_are_rejected(self):
        for kind in ('diagnostic-gmp-verification-bundle-v1', 'diagnostic-gmp-verification-bundle-v3'):
            with self.assertRaisesRegex(ValueError, 'version drift'):
                collector.replay({'kind': kind})
        bundle = {'kind': 'diagnostic-gmp-verification-bundle-v2',
                  'collector_method': collector.entry(Path(collector.__file__).read_bytes()),
                  'files': {'result.json': collector.entry(json.dumps({
                      'kind': 'diagnostic-gmp-verification-run-v2', 'assessment_profile': 'wrong',
                      'passed': False}).encode())}}
        with self.assertRaisesRegex(ValueError, 'profile version drift'):
            collector.replay(bundle)


spec = importlib.util.spec_from_file_location('synthetic', HERE / 'check-gmp-verification.py')
synthetic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(synthetic)
run = collector.run
synthetic.p = run.profile


class RecordingDocker(synthetic.inherited.FakeDocker):
    """Only synthesize outputs; exercise the real lifecycle, capture bindings and replay."""
    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self.responses = []

    def call(self, args, *, seconds=10, limit=262144):
        if args[0] == 'version':
            value = {'Server.Version': '29.4.0', 'Server.ApiVersion': '1.54', 'Server.Os': 'linux', 'Server.Arch': 'arm64'}
        elif args[0] == 'info':
            value = {name: True for name in ('MemoryLimit', 'SwapLimit', 'PidsLimit', 'CpuCfsPeriod', 'CpuCfsQuota')}
            value.update(CgroupVersion='2', SecurityOptions=['name=seccomp,profile=builtin', 'name=cgroupns'])
        elif args[:2] == ['image', 'inspect']:
            value = synthetic.inherited.smoke_tests.image_fixture()
            value['Id'] = run.IMAGE
        else:
            value = None
        if value is not None:
            self.sequence += 1
            result = synthetic.inherited.smoke_tests.result(json.dumps(value).encode())
        else:
            if args[:2] == ['container', 'create']:
                self.step = args[args.index('--name') + 1].split('-test-', 1)[1]
                self.status_raw = {'filter': (f'[GNUPG:] KEYEXPIRED {run.profile.EXPIRES["pub"]}\n'
                    '[GNUPG:] IMPORT_RES 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n').encode(),
                    'certifications': (f'[GNUPG:] KEYEXPIRED {run.profile.EXPIRES["pub"]}\n'
                                       f'[GNUPG:] KEY_CONSIDERED {run.profile.PRIMARY} 0\n').encode(),
                    'verify': synthetic.good().encode(),
                    'tampered-body': (f'[GNUPG:] NEWSIG\n[GNUPG:] KEY_CONSIDERED {run.profile.PRIMARY} 0\n'
                                      f'[GNUPG:] BADSIG {run.profile.PRIMARY[-16:]} Synthetic\n').encode(),
                    'wrong-primary': synthetic.missing().encode(), 'missing-primary': synthetic.missing().encode()}[self.step]
                self.code = 1 if self.step == 'tampered-body' else 2 if self.step in {'wrong-primary', 'missing-primary'} else 0
            result = super().call(args, seconds=seconds, limit=limit)
            if args[:2] == ['container', 'start']:
                result['stdout'] = (synthetic.raw_key() if self.step == 'filter' else
                                    synthetic.colons() if self.step == 'certifications' else b'')
        result['seconds'] = 0.001
        record = {**result, 'argv': [run.smoke.DOCKER, '--host', 'unix://' + run.smoke.SOCKET,
                  '--config', str(self.directory / 'docker-config'), *args],
                  'seconds_limit': seconds, 'bytes_limit': limit, 'started_at': run.smoke.now(), 'finished_at': run.smoke.now()}
        self.responses.append(record)
        return result


class FullRecordChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        for target, name, value in [(collector, 'run', run), (run.profile, 'PRIMARY', synthetic.PRIMARY),
                                    (run.profile, 'SUBKEY', synthetic.SUBKEY),
                                    (run.profile, 'REVOCATION_SHA', run.identity(synthetic.sig(revocation=True))['sha256']),
                                    (run.inputs.source, 'archive_binding', lambda raw: None),
                                    (run.profile.material, 'armor', lambda raw: synthetic.raw_key(True))]:
            handle = patch.object(target, name, value)
            handle.start()
            self.addCleanup(handle.stop)
        raw = synthetic.raw_key(True)
        strong, projection = run.profile.project(raw)
        staged = {'gmp.tar.xz': b'synthetic archive', 'gmp.tar.xz.asc': b'synthetic signature',
                  'gmp.original.asc': b'synthetic armor', 'gmp.raw.gpg': raw, 'gmp.strong.gpg': strong,
                  'gmp.tampered.xz': b'synthetic archivf', 'wrong.gpg': b'synthetic wrong key', 'empty.gpg': b''}
        prepared = {'store': {'manifest': {'sha256': run.inputs.STORE[2]}}, 'source_acceptance': 'not-assessed',
                    'inputs': {k: run.identity(v) for k, v in staged.items()}, 'projection': projection}
        self.prepared = prepared
        folder = run.inputs.stage(self.directory, staged)
        expected = run.inputs.snapshot(folder)
        engine = RecordingDocker(self.directory)
        run.smoke.preflight(engine)
        run.smoke.validate_image(run.smoke.inspect(engine, 'image', run.IMAGE, run.smoke.IMAGE_FIELDS), run.IMAGE)
        cases = []
        # The fake parses this human-readable sentinel; the saved names use a valid UUID-like run ID.
        for step, command in run.commands():
            case, result = run.run_one(engine, self.directory, folder, 'test', step, command, expected)
            self.assertTrue(case['passed'])
            case['assessment'] = run.assess(step, result, case, folder, staged)
            if step == 'filter':
                expected['gmp.self.gpg'] = run.identity(result['stdout'])
            cases.append(case)
        run_id = 'a' * 32
        for case in cases:
            case['name'] = case['name'].replace('-test-', '-' + run_id + '-')
        files = {'inputs/' + name: collector.entry(path.read_bytes()) for name, path in
                 ((path.name, path) for path in folder.iterdir())}
        for number, response in enumerate(engine.responses, 1):
            # Replace the synthetic run sentinel in recorded inspect structures and commands.
            response['argv'] = [arg.replace('-test-', '-' + run_id + '-').replace('=test', '=' + run_id)
                                for arg in response['argv']]
            for channel in ('stdout', 'stderr'):
                stream = response[channel].replace(b'-test-', ('-' + run_id + '-').encode()).replace(
                    b'"test"', ('"' + run_id + '"').encode())
                files[f'{number:03d}.{channel}'] = collector.entry(stream)
                response[channel] = run.identity(stream)
            files[f'{number:03d}.json'] = collector.entry(json.dumps(response).encode())
        for case in cases:
            files[case['status_file']] = collector.entry((self.directory / case['status_file']).read_bytes())
        result = {'kind': 'diagnostic-gmp-verification-run-v2', 'assessment_profile': run.PROFILE, 'run_id': run_id, 'passed': True,
                  'source_acceptance': 'not-assessed', 'runtime_qualification': False,
                  'historical_validity': 'not-established', 'current_key_state': 'expired',
                  'current_all_channel_revocation_checked': False, 'methods': run.methods(),
                  'image_id': run.IMAGE, 'rootfs': {'sha256': run.smoke.TAR_SHA},
                  'docker_cli': {'path': run.smoke.DOCKER, 'sha256': run.smoke.DOCKER_SHA},
                  'docker_socket': run.smoke.SOCKET, 'prepared_inputs': prepared, 'cases': cases}
        files['result.json'] = collector.entry(json.dumps(result).encode())
        self.bundle = {'kind': 'diagnostic-gmp-verification-bundle-v2', 'original_directory': str(self.directory),
                       'collector_method': collector.entry(Path(collector.__file__).read_bytes()),
                       'files': files, 'methods': {name: collector.entry((run.ROOT / name).read_bytes()) for name in run.methods()}}

    def test_six_cases_replay_after_original_directory_removed(self):
        self.temp.cleanup()
        with patch.object(run.smoke, 'Docker', side_effect=AssertionError('unexpected live Docker')):
            row = collector.replay(self.bundle)
        self.assertTrue(row['replayed_success'])
        self.assertEqual(row['historical_validity'], 'not-established')

    def test_collect_preserves_inputs_logs_and_original_methods(self):
        run.retain_methods(self.directory, run.methods())
        for name, raw in collector.unpack(self.bundle['files']).items():
            path = self.directory / name
            if path.exists():
                self.assertEqual(path.read_bytes(), raw)
            else:
                path.write_bytes(raw)
        with patch.object(run.inputs, 'prepare', return_value=(self.prepared, {})):
            collected = collector.collect(self.directory)
        self.assertEqual(collected['files'], self.bundle['files'])
        self.assertEqual(collected['methods'], self.bundle['methods'])
        self.assertTrue(collected['replay']['replayed_success'])
        self.assertEqual(collector.replay(json.loads(json.dumps(collected))), collected['replay'])

    def test_partial_failed_run_exports_without_running_or_accepting(self):
        run.retain_methods(self.directory, run.methods())
        failed = {'kind': 'diagnostic-gmp-verification-run-v2', 'assessment_profile': run.PROFILE, 'passed': False, 'methods': run.methods(), 'failure': 'synthetic deadline'}
        (self.directory / 'result.json').write_text(json.dumps(failed))
        with patch.object(run.inputs, 'prepare', side_effect=AssertionError('unexpected re-prepare')):
            bundle = collector.collect(self.directory)
        self.assertEqual(collector.replay(bundle)['result'], 'failed-run-retained')
        self.assertFalse(bundle['replay']['replayed_success'])

    def test_command_limit_status_cleanup_and_method_tampering(self):
        changes = [('004.json', lambda row: row['argv'].append('--network=host')),
                   ('006.json', lambda row: row.update(bytes_limit=999)),
                   ('result.json', lambda row: row['cases'][0]['cleanup'].update(removed=False)),
                   ('result.json', lambda row: row['cases'][2].update(observed_at=run.profile.CREATED)),
                   ('result.json', lambda row: row.update(source_acceptance='accepted'))]
        for name, mutate in changes:
            bundle = copy.deepcopy(self.bundle)
            raw = json.loads(collector.unpack({name: bundle['files'][name]})[name])
            mutate(raw)
            bundle['files'][name] = collector.entry(json.dumps(raw).encode())
            with self.subTest(name=name), self.assertRaises(ValueError):
                collector.replay(bundle)
        bundle = copy.deepcopy(self.bundle)
        bundle['files']['verify.status'] = collector.entry(b'[GNUPG:] GOODSIG synthetic\n')
        with self.assertRaises(ValueError):
            collector.replay(bundle)

        bundle = copy.deepcopy(self.bundle)
        bundle['methods'][next(iter(bundle['methods']))] = collector.entry(b'changed method')
        with self.assertRaises(ValueError):
            collector.replay(bundle)


class AuxiliaryChecks(unittest.TestCase):
    def setUp(self):
        for name, value in [('PRIMARY', synthetic.PRIMARY), ('SUBKEY', synthetic.SUBKEY)]:
            handle = patch.object(run.profile, name, value)
            handle.start()
            self.addCleanup(handle.stop)
        self.original = synthetic.raw_key()
        self.expired = f'[GNUPG:] KEYEXPIRED {run.profile.EXPIRES["pub"]}\n'.encode()
        self.considered = f'[GNUPG:] KEY_CONSIDERED {run.profile.PRIMARY} 0\n'.encode()
        self.imported = b'[GNUPG:] IMPORT_RES 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n'

    def result(self, status, stdout=None, **changes):
        return synthetic.result(status, stdout=self.original if stdout is None else stdout, **changes)

    def filter(self, status=None, original=None, **changes):
        return run.assess_output('filter', self.result(self.expired + self.imported if status is None else status, **changes),
                                 synthetic.NOW, self.original if original is None else original)

    def cert(self, status, **changes):
        return run.assess_output('certifications', self.result(status, synthetic.colons(), **changes),
                                 synthetic.NOW, self.original, self.original)

    def test_filter_reports_expiry_without_claiming_authentication(self):
        row = self.filter()
        self.assertEqual(row['current_key_state'], 'expired')
        self.assertFalse(row['self_certifications_checked'])
        self.assertTrue(row['auxiliary_status']['expiry_reported_in_status'])
        self.assertEqual(row['historical_validity'], 'not-established')
        self.assertEqual(row['source_acceptance'], 'not-assessed')

    def test_filter_requires_exact_order_counts_and_time(self):
        for status in (b'', self.imported, self.expired, self.imported + self.expired,
                       self.expired * 2 + self.imported, self.expired + self.imported * 2,
                       self.expired.replace(b'1736961163', b'1736961679') + self.imported,
                       self.expired + self.imported.replace(b'IMPORT_RES 1', b'IMPORT_RES 2'),
                       (self.expired + self.imported).replace(b'\n', b'\r\n')):
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.filter(status)

    def test_filter_rejects_all_unexpected_success_failure_or_revocation(self):
        for tag in ('FAILURE import 1', 'ERROR import 1', 'IMPORT_PROBLEM 1 synthetic',
                    'REVKEYSIG synthetic', 'GOODSIG synthetic', 'EXPKEYSIG synthetic',
                    'IMPORT_OK 1 synthetic', 'KEY_CONSIDERED ' + run.profile.PRIMARY + ' 0'):
            with self.assertRaises(ValueError):
                self.filter(self.expired + self.imported + ('[GNUPG:] ' + tag + '\n').encode())

    def test_material_subject_and_digest_cannot_hide_behind_correct_status(self):
        for original in (self.original.replace(synthetic.PUB, synthetic.SUB),
                         self.original.replace(synthetic.sig(), synthetic.sig(old=True))):
            with self.assertRaises(ValueError):
                self.filter(original=original)
        for exported in (self.original[:-1] + b'X', self.original.replace(synthetic.UID, b'Other UID'),
                         self.original[:-1], self.original + self.original):
            with self.assertRaises(ValueError):
                self.filter(stdout=exported)

    def test_certifications_require_exact_considered_subject_with_optional_prefix(self):
        for status in (self.considered, self.expired + self.considered):
            row = self.cert(status)
            self.assertEqual(row['current_key_state'], 'expired')
            self.assertEqual(row['self_certifications'], 2)
            self.assertEqual(row['auxiliary_status']['expiry_reported_in_status'], status.startswith(self.expired))

    def test_certification_status_rejects_wrong_flags_subject_time_order_and_duplicates(self):
        for status in (b'', self.expired, self.considered * 2, self.expired * 2 + self.considered,
                       self.considered + self.expired, self.considered.replace(b' 0\n', b' 1\n'),
                       self.considered.replace(run.profile.PRIMARY.encode(), run.profile.SUBKEY.encode()),
                       self.expired.replace(b'1736961163', b'1736961679') + self.considered,
                       self.considered + b'[GNUPG:] FAILURE check 1\n'):
            with self.assertRaises(ValueError):
                self.cert(status)

    def test_status_never_substitutes_for_colon_certifications(self):
        for listing in (b'', synthetic.colons().replace(b'sig:!', b'sig:?'),
                        synthetic.colons().replace(b'pub:e:', b'pub:r:'),
                        synthetic.colons().replace(b':1736961163:', b':1736961679:')):
            with self.assertRaises(ValueError):
                run.assess_output('certifications', self.result(self.considered, listing),
                                  synthetic.NOW, self.original, self.original)

    def test_capture_abnormal_exit_or_early_clock_stops_auxiliary_processing(self):
        for changes in ({'returncode': False}, {'returncode': 2}, {'returncode': 137}, {'failure': 'deadline'}):
            with self.assertRaises(ValueError):
                self.filter(**changes)
            with self.assertRaises(ValueError):
                self.cert(self.considered, **changes)
        for observed in (False, run.profile.CREATED, run.profile.EXPIRES['pub']):
            with self.assertRaises(ValueError):
                run.assess_output('filter', self.result(self.expired + self.imported), observed, self.original)

    def test_status_bound_and_wrong_stage_rejected(self):
        with self.assertRaises(ValueError):
            self.filter(b'x' * 257)
        with self.assertRaises(ValueError):
            run.auxiliary_status('verify', self.expired, self.original, synthetic.NOW)

    def test_invalid_filter_never_writes_derived_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve()
            with self.assertRaises(ValueError):
                run.assess('filter', self.result(self.imported), {'observed_at': synthetic.NOW},
                           folder, {'gmp.strong.gpg': self.original})
            self.assertFalse(list(folder.iterdir()))
            row = run.assess('filter', self.result(self.expired + self.imported), {'observed_at': synthetic.NOW},
                             folder, {'gmp.strong.gpg': self.original})
            self.assertEqual(row['current_key_state'], 'expired')
            self.assertEqual((folder / 'gmp.self.gpg').read_bytes(), self.original)

    def test_default_plan_preserves_commands_limits_and_uses_new_directory(self):
        with patch.object(run.profile, 'PRIMARY', synthetic.run.profile.PRIMARY):
            with patch.object(run.smoke, 'Docker', side_effect=AssertionError('unexpected daemon')):
                plan = run.plan()
            self.assertEqual(run.commands(), run.prior.commands())
            self.assertEqual(plan['input_bytes_total'], run.prior.plan()['input_bytes_total'])
            self.assertEqual(plan['image_id'], run.prior.IMAGE)
            self.assertNotEqual(run.OUTPUT, run.prior.OUTPUT)
            self.assertEqual(plan['assessment_profile'], run.PROFILE)
            output = subprocess.run([sys.executable, str(HERE / 'run-gmp-verification-v2.py')],
                                    capture_output=True, check=True, timeout=5)
            self.assertEqual(json.loads(output.stdout), plan)
            self.assertIn('docs/records/rust-linux-input-review/run-gmp-verification-v2.py', run.methods())

    def test_review_and_execution_modes_cannot_be_combined(self):
        result = subprocess.run([sys.executable, str(HERE / 'run-gmp-verification-v2.py'),
                                 '--review-retained-filter', '--execute-authorized'],
                                capture_output=True, check=False, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'not allowed with argument', result.stderr)

class BatchChecks(synthetic.BatchChecks):
    def setUp(self):
        handle = patch.object(synthetic, 'run', run)
        handle.start()
        self.addCleanup(handle.stop)


if __name__ == '__main__':
    unittest.main()
