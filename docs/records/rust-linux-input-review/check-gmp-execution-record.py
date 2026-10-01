#!/usr/bin/env python3
"""Synthetic replay binding and encoding checks; no external processes."""
import base64
import copy
import json
import tempfile
from unittest.mock import patch
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('collector', HERE / 'collect-gmp-verification-execution.py')
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
        bundle = {'kind': 'diagnostic-gmp-verification-bundle-v1',
                  'collector_method': collector.entry(Path(collector.__file__).read_bytes()),
                  'files': {'result.json': collector.entry(json.dumps({'passed': False, 'failure': 'deadline'}).encode())}}
        self.assertFalse(collector.replay(bundle)['replayed_success'])


spec = importlib.util.spec_from_file_location('synthetic', HERE / 'check-gmp-verification.py')
synthetic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(synthetic)
run = synthetic.run


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
                self.status_raw = {'filter': b'', 'certifications': b'',
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
        result = {'kind': 'diagnostic-gmp-verification-run-v1', 'run_id': run_id, 'passed': True,
                  'source_acceptance': 'not-assessed', 'runtime_qualification': False,
                  'historical_validity': 'not-established', 'current_key_state': 'expired',
                  'current_all_channel_revocation_checked': False, 'methods': run.methods(),
                  'image_id': run.IMAGE, 'rootfs': {'sha256': run.smoke.TAR_SHA},
                  'docker_cli': {'path': run.smoke.DOCKER, 'sha256': run.smoke.DOCKER_SHA},
                  'docker_socket': run.smoke.SOCKET, 'prepared_inputs': prepared, 'cases': cases}
        files['result.json'] = collector.entry(json.dumps(result).encode())
        self.bundle = {'kind': 'diagnostic-gmp-verification-bundle-v1', 'original_directory': str(self.directory),
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
        failed = {'passed': False, 'methods': run.methods(), 'failure': 'synthetic deadline'}
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


if __name__ == '__main__':
    unittest.main()
