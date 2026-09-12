#!/usr/bin/env python3
"""Synthetic process and daemon-state checks. Never connects to Docker or runs downloaded programs."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('smoke', HERE / 'run-musl-verifier-smoke.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
IMAGE, CID = 'sha256:' + 'a' * 64, 'b' * 64


def result(stdout=b'', code=0, failure=None, stderr=b''):
    return {'stdout': stdout, 'stderr': stderr, 'returncode': code, 'failure': failure}


def image_fixture():
    return {'Id': IMAGE, 'Os': 'linux', 'Architecture': 'arm64',
        'Config.Labels': {smoke.LABEL: smoke.TAR_SHA}, 'Config.User': '', 'Config.Env': None,
        'Config.Cmd': None, 'Config.Entrypoint': None, 'Config.Volumes': None, 'Config.OnBuild': None,
        'Config.Healthcheck': None}


def container_fixture(name, run_id, command):
    # Explicit API fixture for the reviewed configuration, independent of create_args/validation.
    return {'Id': CID, 'Name': '/' + name, 'Image': IMAGE, 'Path': command[0], 'Args': command[1:],
        'Config.User': '1000:1000', 'Config.Env': ['PATH=/usr/bin', 'HOME=/work', 'LC_ALL=C', 'TZ=UTC0'],
        'Config.Labels': {smoke.LABEL: smoke.TAR_SHA, smoke.RUN_LABEL: run_id},
        'Config.WorkingDir': '/work', 'Config.Entrypoint': [command[0]], 'Config.Cmd': command[1:],
        'Config.Tty': False, 'Config.OpenStdin': False, 'Config.Volumes': None,
        'Config.AttachStdout': True, 'Config.AttachStderr': True, 'Config.AttachStdin': False,
        'Config.Healthcheck': {'Test': ['NONE']}, 'HostConfig.ReadonlyRootfs': True,
        'HostConfig.Privileged': False, 'HostConfig.NetworkMode': 'none', 'HostConfig.PortBindings': {},
        'HostConfig.PublishAllPorts': False, 'HostConfig.Binds': None, 'HostConfig.Mounts': None,
        'HostConfig.VolumesFrom': None, 'HostConfig.Devices': [], 'HostConfig.DeviceRequests': None,
        'HostConfig.CapAdd': None, 'HostConfig.CapDrop': ['ALL'],
        'HostConfig.SecurityOpt': ['no-new-privileges=true'], 'HostConfig.CgroupnsMode': 'private',
        'HostConfig.PidMode': '', 'HostConfig.IpcMode': 'none', 'HostConfig.UTSMode': '', 'HostConfig.UsernsMode': '',
        'HostConfig.Memory': 134217728, 'HostConfig.MemorySwap': 134217728, 'HostConfig.NanoCpus': 1000000000,
        'HostConfig.PidsLimit': 32,
        'HostConfig.Tmpfs': {'/tmp': 'rw,noexec,nosuid,nodev,size=16777216,mode=1777'},
        'HostConfig.LogConfig': {'Type': 'none', 'Config': {}},
        'HostConfig.RestartPolicy': {'Name': 'no', 'MaximumRetryCount': 0}, 'HostConfig.AutoRemove': False,
        'HostConfig.Ulimits': [{'Name': 'core', 'Soft': 0, 'Hard': 0}], 'HostConfig.Runtime': 'runc',
        'Mounts': [], 'State.Status': 'created', 'State.Running': False, 'State.Paused': False,
        'State.Restarting': False, 'State.Dead': False, 'State.OOMKilled': False,
        'State.ExitCode': 0, 'State.Error': ''}


class FakeDocker:
    def __init__(self, changes=None, run_failure=None, kill_failure=False, remove_failure=False,
                 create_failure=False, inspect_failure=False):
        self.calls, self.value = [], None
        self.changes = changes or {}
        self.run_failure, self.kill_failure = run_failure, kill_failure
        self.remove_failure, self.create_failure, self.inspect_failure = remove_failure, create_failure, inspect_failure
        self.count = 0

    def call(self, args, **limits):
        self.calls.append((args, limits))
        operation = tuple(args[:2])
        if operation == ('image', 'inspect'):
            return result(json.dumps(image_fixture()).encode())
        if operation == ('container', 'create'):
            self.count += 1
            if self.create_failure:
                return result(code=-9, failure='deadline')
            name = args[args.index('--name') + 1]
            run_id = args[args.index('--label') + 1].split('=', 1)[1]
            command = [args[args.index('--entrypoint') + 1]] + args[args.index(IMAGE) + 1:]
            self.value = container_fixture(name, run_id, command)
            self.value.update(self.changes)
            return result((CID + '\n').encode())
        if operation == ('container', 'inspect'):
            if self.inspect_failure:
                return result(code=1, stderr=b'synthetic daemon unavailable')
            return result(json.dumps(self.value).encode())
        if operation == ('container', 'start'):
            self.value.update({'State.Status': 'running' if self.run_failure else 'exited',
                               'State.Running': bool(self.run_failure)})
            if self.run_failure:
                return result(code=-9, failure=self.run_failure)
            output = [b'gpg (GnuPG) 2.4.7\n', b'homedir:/work/full\n',
                      b'libc.so.6 => /lib/aarch64-linux-gnu/libc.so.6 (0x12)\n/lib/ld-linux-aarch64.so.1 (0x34)\n']
            return result(output[min(self.count - 1, 2)])
        if operation == ('container', 'kill'):
            if self.kill_failure:
                return result(code=1, failure='deadline')
            self.value.update({'State.Status': 'exited', 'State.Running': False, 'State.ExitCode': 137})
            return result((CID + '\n').encode())
        if operation == ('container', 'rm'):
            return result(code=1 if self.remove_failure else 0)
        raise AssertionError('unexpected command: ' + repr(args))


class ProcessChecks(unittest.TestCase):
    def capture(self, code, seconds=2, limit=65536):
        return smoke.capture([sys.executable, '-c', code], {'PATH': '/usr/bin:/bin'}, seconds, limit)

    def test_dual_streams_and_stdin_eof(self):
        actual = self.capture("import os,sys; assert not sys.stdin.read(); os.write(1,b'x'*60000); os.write(2,b'y'*60000)")
        self.assertTrue(smoke.ok(actual))
        self.assertEqual(actual['stdout'], b'x' * 60000)
        self.assertEqual(actual['stderr'], b'y' * 60000)

    def test_exact_limit_and_one_byte_over(self):
        self.assertTrue(smoke.ok(self.capture("import os; os.write(1,b'x'*64)", limit=64)))
        for fd, channel in [(1, 'stdout'), (2, 'stderr')]:
            actual = self.capture(f"import os; os.write({fd},b'x'*65)", limit=64)
            self.assertEqual(actual['failure'], channel + '-limit')
            self.assertEqual(len(actual[channel]), 64)

    def test_deadline_kills_and_reaps_process(self):
        actual = self.capture("import os,time; print(os.getpid(),flush=True); time.sleep(30)", seconds=0.2)
        self.assertEqual(actual['failure'], 'deadline')
        self.assertLess(actual['seconds'], 2)
        with self.assertRaises(ProcessLookupError):
            os.kill(int(actual['stdout']), 0)

    def test_closed_pipes_do_not_bypass_deadline(self):
        actual = self.capture("import os,time; os.close(1); os.close(2); time.sleep(30)", seconds=0.2)
        self.assertEqual(actual['failure'], 'deadline')

    def test_nonzero_exit_is_not_success(self):
        actual = self.capture("import sys; print('failure',file=sys.stderr); sys.exit(3)")
        self.assertEqual(actual['returncode'], 3)
        self.assertFalse(smoke.ok(actual))

    def test_success_with_warning_requires_review(self):
        with self.assertRaises(ValueError):
            smoke.checked(result(code=0, stderr=b'synthetic daemon warning'))

    def test_docker_env_and_numbered_logs_are_isolated(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine = smoke.Docker(Path(temporary))
            with patch.object(smoke, 'capture', return_value=result(b'synthetic')) as runner:
                engine.call(['version'])
            argv, env, seconds, limit = runner.call_args.args
            self.assertEqual(argv[:3], [smoke.DOCKER, '--host', 'unix://' + smoke.SOCKET])
            self.assertEqual(set(env), {'PATH', 'HOME', 'LC_ALL', 'DOCKER_API_VERSION', 'DOCKER_CLI_HINTS'})
            self.assertEqual((seconds, limit), (10, 262144))
            self.assertEqual((Path(temporary) / '001.stdout').read_bytes(), b'synthetic')
            self.assertEqual(json.loads((Path(temporary) / '001.json').read_bytes())['stdout']['bytes'], 9)


class LifecycleChecks(unittest.TestCase):
    def test_version_template_uses_cli_go_field_and_preserves_record_key(self):
        self.assertEqual(smoke.template(['Server.ApiVersion']),
                         '{"Server.ApiVersion":{{json .Server.APIVersion}}}')

    def test_resource_template_uses_cli_go_cpu_fields(self):
        self.assertEqual(smoke.template(['CpuCfsPeriod', 'CpuCfsQuota']),
                         '{"CpuCfsPeriod":{{json .CPUCfsPeriod}},"CpuCfsQuota":{{json .CPUCfsQuota}}}')

    def test_inspect_optional_keys_use_map_lookup(self):
        self.assertEqual(smoke.template(['Config.Env'], maps=True),
                         '{"Config.Env":{{json (index . "Config" "Env")}}}')
        value = image_fixture()
        value['Architecture'] = None
        with self.assertRaises(ValueError):
            smoke.validate_image(value, IMAGE)

    def one(self, engine):
        return smoke.run_one(engine, IMAGE, 'synthetic', 0, smoke.COMMANDS[0])

    def test_success_inspects_before_start_and_remove(self):
        engine = FakeDocker()
        actual = self.one(engine)
        self.assertTrue(actual['passed'])
        self.assertEqual([args[1] for args, _ in engine.calls],
                         ['create', 'inspect', 'start', 'inspect', 'inspect', 'inspect', 'rm'])
        start_limits = engine.calls[2][1]
        self.assertEqual(start_limits, {'seconds': 30, 'limit': 1048576})

    def test_resource_mount_and_environment_drift_prevent_start(self):
        for key, value in [('HostConfig.Memory', 0), ('HostConfig.MemorySwap', -1),
                ('HostConfig.Privileged', True), ('HostConfig.Binds', ['/synthetic:/data']),
                ('HostConfig.SecurityOpt', ['seccomp=unconfined']), ('HostConfig.AutoRemove', True),
                ('HostConfig.NetworkMode', 'host'), ('HostConfig.LogConfig', {'Type': 'json-file'}),
                ('Config.Env', smoke.ENV + ['LD_PRELOAD=/synthetic']), ('HostConfig.PidsLimit', True)]:
            with self.subTest(key=key):
                engine = FakeDocker({key: value})
                self.assertFalse(self.one(engine)['passed'])
                self.assertNotIn('start', [args[1] for args, _ in engine.calls])
                self.assertTrue(any(args[:2] == ['container', 'rm'] for args, _ in engine.calls))

    def test_timeout_and_overflow_kill_before_inspecting(self):
        for failure in ['deadline', 'stdout-limit', 'stderr-limit']:
            engine = FakeDocker(run_failure=failure)
            actual = self.one(engine)
            self.assertFalse(actual['passed'])
            self.assertTrue(actual['cleanup']['removed'])
            operations = [args[1] for args, _ in engine.calls]
            self.assertEqual(operations[operations.index('start') + 1], 'kill')
            self.assertTrue(all(args[-1] == CID for args, _ in engine.calls if args[1] in ['kill', 'rm']))

    def test_kill_or_remove_failure_cannot_pass(self):
        for engine in [FakeDocker(run_failure='deadline', kill_failure=True), FakeDocker(remove_failure=True)]:
            actual = self.one(engine)
            self.assertFalse(actual['passed'])
            self.assertFalse(actual['cleanup']['removed'])

    def test_ambiguous_create_never_deletes_by_name(self):
        engine = FakeDocker(create_failure=True)
        actual = self.one(engine)
        self.assertFalse(actual['passed'])
        self.assertEqual(actual['cleanup']['uncertain_name'], 'rax-musl-synthetic-0')
        self.assertEqual(len(engine.calls), 1)

    def test_unowned_container_is_never_started_or_removed(self):
        engine = FakeDocker({'Config.Labels': {'synthetic': 'someone-else'}})
        actual = self.one(engine)
        self.assertFalse(actual['passed'])
        self.assertTrue(all(args[1] in ['create', 'inspect'] for args, _ in engine.calls))

    def test_daemon_loss_does_not_claim_cleanup(self):
        actual = self.one(FakeDocker(inspect_failure=True))
        self.assertFalse(actual['cleanup']['removed'])
        self.assertIn('failure', actual['cleanup'])

    def test_changed_inspect_id_cannot_pass_or_be_removed(self):
        engine = FakeDocker()
        original = engine.call

        def changed_id(args, **limits):
            actual = original(args, **limits)
            if args[:2] == ['container', 'start']:
                engine.value['Id'] = 'c' * 64
            return actual

        engine.call = changed_id
        actual = self.one(engine)
        self.assertFalse(actual['passed'])
        self.assertFalse(actual['cleanup']['removed'])
        self.assertTrue(all(args[-1] == CID for args, _ in engine.calls if args[1] == 'kill'))
        self.assertFalse(any(args[1] == 'rm' for args, _ in engine.calls))

    def test_log_failure_after_start_still_requests_termination(self):
        engine = FakeDocker()
        original = engine.call

        def failing_call(args, **limits):
            actual = original(args, **limits)
            if args[:2] == ['container', 'start']:
                raise OSError('synthetic log write failure')
            return actual

        engine.call = failing_call
        actual = self.one(engine)
        self.assertFalse(actual['passed'])
        self.assertTrue(actual['termination']['requested'])
        operations = [args[1] for args, _ in engine.calls]
        self.assertEqual(operations[operations.index('start') + 1], 'kill')

    def test_oom_nonzero_and_state_error_rejected(self):
        for key, value in [('State.OOMKilled', True), ('State.ExitCode', 2), ('State.Error', 'synthetic failure')]:
            actual = self.one(FakeDocker({key: value}))
            self.assertFalse(actual['passed'])
            self.assertTrue(actual['cleanup']['removed'])

    def test_four_cases_sequential_and_first_failure_stops_batch(self):
        plan = json.loads(smoke.PLAN.read_bytes())
        engine = FakeDocker()
        self.assertTrue(smoke.smoke(engine, IMAGE, plan)['passed'])
        self.assertEqual(engine.count, 4)
        engine = FakeDocker(run_failure='deadline')
        self.assertFalse(smoke.smoke(engine, IMAGE, plan)['passed'])
        self.assertEqual(engine.count, 1)

    def test_image_defaults_and_platform_drift_rejected(self):
        for key, value in [('Architecture', 'amd64'), ('Config.Volumes', {'/data': {}}),
                           ('Config.Entrypoint', ['/bin/sh']), ('Config.Labels', {})]:
            value_fixture = image_fixture()
            value_fixture[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                smoke.validate_image(value_fixture, IMAGE)

    def test_omitted_image_user_is_unset_but_declared_user_rejected(self):
        value = image_fixture()
        value['Config.User'] = None
        smoke.validate_image(value, IMAGE)
        for user in ['root', '0', '1000']:
            value['Config.User'] = user
            with self.assertRaises(ValueError):
                smoke.validate_image(value, IMAGE)

    def test_output_version_home_and_loader_boundary(self):
        plan = json.loads(smoke.PLAN.read_bytes())
        for number, text in [(0, 'gpg (GnuPG) 2.4.8\n'), (1, 'homedir:/elsewhere\n'),
                (1, 'homedir:/work/full\nhomedir:/work/full\n'), (2, 'libc.so.6 => not found\n'),
                (2, '/unlisted/library.so (0x12)\n'), (2, '/tmp (0x12)\n')]:
            with self.subTest(number=number, text=text), self.assertRaises(ValueError):
                smoke.validate_output(number, text, plan)

    def test_default_plan_never_calls_docker(self):
        actual = subprocess.run([sys.executable, str(HERE / 'run-musl-verifier-smoke.py')],
                                capture_output=True, check=True, timeout=5)
        self.assertFalse(json.loads(actual.stdout)['actions_executed'])

    def test_import_is_bounded_and_records_id_before_inspect_failure(self):
        class ImportDocker:
            def __init__(self, output):
                self.output = output

            def call(self, args, **limits):
                if args[:2] == ['image', 'import']:
                    self_test.assertEqual(limits, {'seconds': 60})
                    self_test.assertIn(str(smoke.TAR), args)
                    return result((IMAGE + '\n').encode())
                self_test.assertEqual(args[:2], ['image', 'inspect'])
                return result(code=1, stderr=b'synthetic inspection failure')

        self_test = self
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve() / 'import'
            with patch.object(smoke, 'Docker', ImportDocker), patch.object(smoke, 'preflight'), \
                    patch.object(smoke, 'verified_inputs', return_value=(b'synthetic', {'entries': []})):
                actual = smoke.execute('import', None, output)
            self.assertFalse(actual['passed'])
            self.assertEqual(actual['image_id'], IMAGE)
            self.assertTrue(actual['image_retained'])
            self.assertEqual(json.loads((output / 'result.json').read_bytes())['image_id'], IMAGE)

    def test_changed_daemon_capabilities_stop_before_mutation(self):
        class ChangedDaemon:
            def call(self, args, **limits):
                self_test.assertIn(args[0], ['version', 'info'])
                if args[0] == 'version':
                    return result(json.dumps({'Server.Version': '29.4.0', 'Server.ApiVersion': '1.54',
                                              'Server.Os': 'linux', 'Server.Arch': 'arm64'}).encode())
                return result(b'{"MemoryLimit":false}')

        self_test = self
        with self.assertRaises(ValueError):
            smoke.preflight(ChangedDaemon())


if __name__ == '__main__':
    unittest.main()
