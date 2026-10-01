#!/usr/bin/env python3
"""Fixed diagnostic Docker import/smoke entry points. Default is an offline plan; execution needs review."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TAR = ROOT / '.tmp/musl-preflight-80768b6-20260912/rootfs.tar'
TAR_SHA = 'f1ac49bc29d33182a9c9a070b70509c739d857369876afbe307b9e9898d6b8b3'
PLAN = HERE / 'musl-verifier-rootfs-plan-2026-09-12.json'
PLAN_SHA = 'bb17cb1a11e8209fadc37d1d2c40bf96197162b623d1f80a95e0ab3a7f82c14b'
DOCKER = '/usr/local/bin/docker'
DOCKER_SHA = 'c93921f27c941f7661e5478e8af4042e546b66e69707a2b43f31a86cfe9c85d2'
SOCKET = '/Users/luobo/.orbstack/run/docker.sock'
LABEL = 'org.radishaxiom.musl-rootfs-sha256'
RUN_LABEL = 'org.radishaxiom.musl-smoke-run'
ENV = ['PATH=/usr/bin', 'HOME=/work', 'LC_ALL=C', 'TZ=UTC0']
TMPFS = {'/tmp': 'rw,noexec,nosuid,nodev,size=16777216,mode=1777'}
COMMANDS = [
    ['/usr/bin/gpg', '--batch', '--no-tty', '--no-options', '--homedir', '/work/full',
     '--no-autostart', '--disable-dirmngr', '--version'],
    ['/usr/bin/gpgconf', '--homedir', '/work/full', '--list-dirs'],
    ['/lib/ld-linux-aarch64.so.1', '--list', '/usr/bin/gpg'],
    ['/lib/ld-linux-aarch64.so.1', '--list', '/usr/bin/gpgconf'],
]
CONTROL_SECONDS, RUN_SECONDS = 10, 30
CONTROL_BYTES, RUN_BYTES = 256 * 1024, 1024**2
CONTAINER_FIELDS = ['Id', 'Name', 'Image', 'Path', 'Args', 'Config.User', 'Config.Env', 'Config.Labels',
    'Config.WorkingDir', 'Config.Entrypoint', 'Config.Cmd', 'Config.Tty', 'Config.OpenStdin',
    'Config.AttachStdout', 'Config.AttachStderr', 'Config.AttachStdin',
    'Config.Volumes', 'Config.Healthcheck', 'HostConfig.ReadonlyRootfs', 'HostConfig.Privileged',
    'HostConfig.NetworkMode', 'HostConfig.PortBindings', 'HostConfig.PublishAllPorts', 'HostConfig.Binds',
    'HostConfig.Mounts', 'HostConfig.VolumesFrom', 'HostConfig.Devices', 'HostConfig.DeviceRequests',
    'HostConfig.CapAdd', 'HostConfig.CapDrop', 'HostConfig.SecurityOpt', 'HostConfig.CgroupnsMode',
    'HostConfig.PidMode', 'HostConfig.IpcMode', 'HostConfig.UTSMode', 'HostConfig.UsernsMode',
    'HostConfig.Memory', 'HostConfig.MemorySwap', 'HostConfig.NanoCpus', 'HostConfig.PidsLimit',
    'HostConfig.Tmpfs', 'HostConfig.LogConfig', 'HostConfig.RestartPolicy', 'HostConfig.AutoRemove',
    'HostConfig.Ulimits', 'HostConfig.Runtime', 'Mounts', 'State.Status', 'State.Running',
    'State.Paused', 'State.Restarting', 'State.Dead', 'State.OOMKilled', 'State.ExitCode', 'State.Error']
IMAGE_FIELDS = ['Id', 'Os', 'Architecture', 'Config.Labels', 'Config.Env', 'Config.Entrypoint',
                'Config.Cmd', 'Config.Volumes', 'Config.OnBuild', 'Config.Healthcheck', 'Config.User']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def now():
    return datetime.now(timezone.utc).isoformat()


def capture(argv, env, seconds, limit):
    """Drain both streams with one monotonic deadline; kill/reap the client group on failure."""
    started = time.monotonic()
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    reason = None
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=env, start_new_session=True)
    try:
        with selectors.DefaultSelector() as selector:
            for name, stream in [('stdout', process.stdout), ('stderr', process.stderr)]:
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            while selector.get_map() or process.poll() is None:
                remaining = seconds - (time.monotonic() - started)
                if remaining <= 0:
                    reason = 'deadline'
                    break
                for key, _ in selector.select(min(remaining, 0.05)):
                    data = os.read(key.fd, 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    buffer = buffers[key.data]
                    available = limit - len(buffer)
                    buffer.extend(data[:available])
                    if len(data) > available:
                        reason = key.data + '-limit'
                        break
                if reason:
                    break
    except OSError as error:
        reason = f'capture-io-errno-{error.errno}'
    finally:
        # A completed CLI is not evidence that its daemon-side container has stopped.
        if reason or process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.stdout.close()
        process.stderr.close()
        process.wait(timeout=2)
    return {'returncode': process.returncode, 'failure': reason,
            'seconds': time.monotonic() - started, **{k: bytes(v) for k, v in buffers.items()}}


def template(fields):
    return '{' + ','.join(json.dumps(key) + ':{{json .' + key + '}}' for key in fields) + '}'


class Docker:
    def __init__(self, output):
        self.output, self.sequence = output, 0
        config = output / 'docker-config'
        config.mkdir(mode=0o700)
        self.prefix = [DOCKER, '--host', 'unix://' + SOCKET, '--config', str(config)]
        self.env = {'PATH': '/usr/bin:/bin', 'HOME': str(config), 'LC_ALL': 'C',
                    'DOCKER_API_VERSION': '1.54', 'DOCKER_CLI_HINTS': 'false'}

    def call(self, args, *, seconds=CONTROL_SECONDS, limit=CONTROL_BYTES):
        self.sequence += 1
        stem = self.output / f'{self.sequence:03d}'
        argv = self.prefix + args
        started = now()
        try:
            result = capture(argv, self.env, seconds, limit)
        except (OSError, subprocess.TimeoutExpired) as error:
            result = {'returncode': None, 'failure': type(error).__name__, 'errno': getattr(error, 'errno', None),
                      'stdout': b'', 'stderr': b''}
        record = {k: v for k, v in result.items() if k not in {'stdout', 'stderr'}}
        record.update(argv=argv, started_at=started, finished_at=now(), seconds_limit=seconds, bytes_limit=limit)
        for channel in ('stdout', 'stderr'):
            with Path(str(stem) + '.' + channel).open('xb') as stream:
                stream.write(result[channel])
            record[channel] = identity(result[channel])
        with Path(str(stem) + '.json').open('x') as stream:
            json.dump(record, stream, sort_keys=True, indent=2)
            stream.write('\n')
        return result


def ok(result):
    return result['failure'] is None and result['returncode'] == 0


def checked(result):
    require(ok(result), 'Docker command failed; see numbered command logs')
    require(not result['stderr'], 'Docker diagnostic on stderr; review numbered command logs')
    return result['stdout']


def inspect(engine, kind, target, fields):
    raw = checked(engine.call([kind, 'inspect', '--format', template(fields), target]))
    value = json.loads(raw)
    require(isinstance(value, dict) and set(value) == set(fields), 'inspect schema mismatch')
    return value


def validate_image(value, image):
    require(re.fullmatch(r'sha256:[0-9a-f]{64}', image) is not None, 'full image ID required')
    for key, expected in {'Id': image, 'Os': 'linux', 'Architecture': 'arm64',
                          'Config.Labels': {LABEL: TAR_SHA}, 'Config.User': ''}.items():
        require(value[key] == expected, 'image mismatch: ' + key)
    for key in ['Config.Env', 'Config.Entrypoint', 'Config.Cmd', 'Config.Volumes', 'Config.OnBuild', 'Config.Healthcheck']:
        require(not value[key], 'unexpected image defaults: ' + key)


def create_args(image, name, run_id, command):
    return ['container', 'create', '--name', name, '--label', RUN_LABEL + '=' + run_id,
        '--platform', 'linux/arm64', '--pull', 'never', '--user', '1000:1000', '--workdir', '/work',
        '--attach', 'stdout', '--attach', 'stderr',
        '--read-only', '--network', 'none', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges=true',
        '--cgroupns', 'private', '--ipc', 'none', '--runtime', 'runc', '--memory', '128m', '--memory-swap', '128m',
        '--cpus', '1', '--pids-limit', '32', '--ulimit', 'core=0:0', '--log-driver', 'none', '--restart', 'no',
        '--no-healthcheck', '--tmpfs', '/tmp:' + TMPFS['/tmp'],
        *[arg for item in ENV for arg in ['--env', item]], '--entrypoint', command[0], image, *command[1:]]


def owned(value, image, name, run_id):
    require(re.fullmatch(r'[0-9a-f]{64}', value['Id']) is not None, 'invalid container ID')
    require(value['Name'] == '/' + name and value['Image'] == image and
            value['Config.Labels'] == {LABEL: TAR_SHA, RUN_LABEL: run_id}, 'container ownership mismatch')


def validate_container(value, image, name, run_id, command):
    owned(value, image, name, run_id)
    exact = {'Path': command[0], 'Args': command[1:], 'Config.User': '1000:1000',
        'Config.WorkingDir': '/work', 'Config.Entrypoint': [command[0]], 'Config.Cmd': command[1:],
        'Config.Tty': False, 'Config.OpenStdin': False, 'Config.Healthcheck': {'Test': ['NONE']},
        'Config.AttachStdout': True, 'Config.AttachStderr': True, 'Config.AttachStdin': False,
        'HostConfig.ReadonlyRootfs': True, 'HostConfig.Privileged': False, 'HostConfig.NetworkMode': 'none',
        'HostConfig.PublishAllPorts': False, 'HostConfig.CgroupnsMode': 'private', 'HostConfig.PidMode': '',
        'HostConfig.IpcMode': 'none', 'HostConfig.UTSMode': '', 'HostConfig.UsernsMode': '',
        'HostConfig.Memory': 128 * 1024**2, 'HostConfig.MemorySwap': 128 * 1024**2,
        'HostConfig.NanoCpus': 10**9, 'HostConfig.PidsLimit': 32, 'HostConfig.Tmpfs': TMPFS,
        'HostConfig.LogConfig': {'Type': 'none', 'Config': {}},
        'HostConfig.RestartPolicy': {'Name': 'no', 'MaximumRetryCount': 0}, 'HostConfig.AutoRemove': False,
        'HostConfig.Ulimits': [{'Name': 'core', 'Hard': 0, 'Soft': 0}], 'HostConfig.Runtime': 'runc'}
    for key, expected in exact.items():
        require(type(value[key]) is type(expected) and value[key] == expected, 'container config mismatch: ' + key)
    require(sorted(value['Config.Env']) == sorted(ENV), 'container environment mismatch')
    require(value['HostConfig.CapDrop'] in [['ALL'], ['all']], 'capability drop mismatch')
    require(value['HostConfig.SecurityOpt'] in [['no-new-privileges'], ['no-new-privileges=true']],
            'security options mismatch')
    for key in ['Config.Volumes', 'HostConfig.PortBindings', 'HostConfig.Binds', 'HostConfig.Mounts',
                'HostConfig.VolumesFrom', 'HostConfig.Devices', 'HostConfig.DeviceRequests', 'HostConfig.CapAdd']:
        require(not value[key], 'unexpected mount/device/capability/port: ' + key)
    # API versions can expose the explicitly requested tmpfs here or only under HostConfig.Tmpfs.
    for mount in value['Mounts']:
        require(mount.get('Type') == 'tmpfs' and mount.get('Destination') == '/tmp' and
                not mount.get('Source') and mount.get('RW') is True, 'unexpected effective mount')


def final_state(value):
    require(value['State.Status'] == 'exited' and value['State.Running'] is False and
            all(value[key] is False for key in ['State.Paused', 'State.Restarting', 'State.Dead', 'State.OOMKilled']) and
            type(value['State.ExitCode']) is int and value['State.ExitCode'] == 0 and
            value['State.Error'] == '', 'container did not exit cleanly')


def cleanup(engine, container, image, name, run_id):
    report = {'container_id': container, 'removed': False}
    try:
        before = inspect(engine, 'container', container, CONTAINER_FIELDS)
        owned(before, image, name, run_id)
        require(before['Id'] == container, 'cleanup ID drift')
        if before['State.Running'] or before['State.Restarting'] or before['State.Paused']:
            report['kill_ok'] = ok(engine.call(['container', 'kill', '--signal', 'KILL', container]))
        after = inspect(engine, 'container', container, CONTAINER_FIELDS)
        owned(after, image, name, run_id)
        require(after['Id'] == container, 'cleanup final ID drift')
        report['state_before_remove'] = {k: v for k, v in after.items() if k.startswith('State.')}
        require(not after['State.Running'] and not after['State.Restarting'] and not after['State.Paused'],
                'container termination unconfirmed')
        report['removed'] = ok(engine.call(['container', 'rm', container]))
        require(report['removed'], 'container removal unconfirmed')
    except (OSError, ValueError, KeyError, TypeError) as error:
        report['failure'] = str(error)
    return report


def request_kill(engine, container):
    try:
        return {'requested': True, 'command_ok': ok(engine.call(['container', 'kill', '--signal', 'KILL', container]))}
    except (OSError, ValueError) as error:
        return {'requested': True, 'command_ok': False, 'failure': str(error)}


def run_one(engine, image, run_id, number, command):
    name = f'rax-musl-{run_id}-{number}'
    report = {'name': name, 'command': command, 'passed': False, 'cleanup': {'removed': False}}
    container = None
    start_attempted = False
    try:
        created = engine.call(create_args(image, name, run_id, command))
        candidate = created['stdout'].decode('ascii', errors='replace').strip()
        if re.fullmatch(r'[0-9a-f]{64}', candidate):
            container = candidate
        require(ok(created) and not created['stderr'] and container is not None, 'container create failed or ambiguous')
        report['container_id'] = container
        before = inspect(engine, 'container', container, CONTAINER_FIELDS)
        validate_container(before, image, name, run_id, command)
        require(before['Id'] == container and before['State.Status'] == 'created' and
                before['State.Running'] is False, 'container already started or ID changed')
        start_attempted = True
        result = engine.call(['container', 'start', '--attach', container], seconds=RUN_SECONDS, limit=RUN_BYTES)
        if not ok(result):
            report['termination'] = request_kill(engine, container)
        # Preserve status even when the CLI timed out or exceeded output limits.
        after = inspect(engine, 'container', container, CONTAINER_FIELDS)
        require(after['Id'] == container, 'final container ID drift')
        report['final_state'] = {k: v for k, v in after.items() if k.startswith('State.')}
        validate_container(after, image, name, run_id, command)
        checked(result)
        final_state(after)
        require(not result['stderr'], 'unexpected smoke stderr; manual review required')
        report['stdout'] = result['stdout'].decode('utf-8', errors='strict')
        report['passed'] = True
    except (OSError, ValueError, KeyError, TypeError) as error:
        report['failure'] = str(error)
        if start_attempted and 'termination' not in report:
            report['termination'] = request_kill(engine, container)
    finally:
        if container is not None:
            report['cleanup'] = cleanup(engine, container, image, name, run_id)
        else:
            # A timed-out create may complete later: never infer absence or delete by an unverified name.
            report['cleanup'] = {'removed': False, 'uncertain_name': name,
                                 'failure': 'no confirmed container ID; manual reconciliation required'}
    report['passed'] = report['passed'] and report['cleanup']['removed']
    return report


def load_method(filename):
    spec = importlib.util.spec_from_file_location(filename, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_output(number, text, plan):
    require(text and all(ord(c) >= 32 or c in '\n\t' for c in text), 'invalid smoke text')
    if number == 0:
        require(text.splitlines()[0] == 'gpg (GnuPG) 2.4.7', 'unexpected GnuPG version')
    elif number == 1:
        lines = text.splitlines()
        pairs = [line.split(':', 1) for line in lines]
        require(all(len(pair) == 2 for pair in pairs), 'invalid gpgconf directory output')
        dirs = dict(pairs)
        require(len(dirs) == len(pairs) and dirs.get('homedir') == '/work/full', 'unexpected gpgconf home')
        # Compiled auxiliary paths may name programs not included in this read-only smoke image.
    else:
        content = load_method('inspect-musl-verifier-content.py')
        index = {row['path']: row for row in plan['entries']}
        paths = []
        for line in text.splitlines():
            if re.fullmatch(r'\s*linux-vdso\.so\.1 \(0x[0-9a-f]+\)', line):
                continue
            match = re.fullmatch(r'\s*(?:[A-Za-z0-9_.+-]+ => )?(/[^\s]+) \(0x[0-9a-f]+\)', line)
            require(match is not None, 'unrecognized loader mapping')
            path = match[1]
            resolved = content.resolve(index, path)
            require(resolved['status'] == 'found' and resolved['type'] == 'file',
                    'loader path outside reviewed rootfs files: ' + path)
            paths.append(path)
        require(len(paths) >= 2 and any(path.endswith('/libc.so.6') for path in paths), 'incomplete loader mapping')


def smoke(engine, image, plan):
    validate_image(inspect(engine, 'image', image, IMAGE_FIELDS), image)
    run_id = uuid.uuid4().hex
    results = []
    for number, command in enumerate(COMMANDS):
        result = run_one(engine, image, run_id, number, command)
        results.append(result)
        if result['passed']:
            try:
                validate_output(number, result.pop('stdout'), plan)
            except (ValueError, KeyError, TypeError) as error:
                result.update(passed=False, failure=str(error))
        if not result['passed']:
            break
    return {'run_id': run_id, 'image_id': image, 'cases': results,
            'passed': len(results) == 4 and all(case['passed'] for case in results)}


def preflight(engine):
    version = json.loads(checked(engine.call(['version', '--format', template(['Server.Version', 'Server.ApiVersion',
                                                                             'Server.Os', 'Server.Arch'])])))
    require(version == {'Server.Version': '29.4.0', 'Server.ApiVersion': '1.54', 'Server.Os': 'linux',
                        'Server.Arch': 'arm64'}, 'reviewed daemon version changed')
    fields = ['MemoryLimit', 'SwapLimit', 'PidsLimit', 'CpuCfsPeriod', 'CpuCfsQuota', 'CgroupVersion', 'SecurityOptions']
    info = json.loads(checked(engine.call(['info', '--format', template(fields)])))
    require(all(info.get(key) is True for key in fields[:5]) and info.get('CgroupVersion') == '2' and
            info.get('SecurityOptions') == ['name=seccomp,profile=builtin', 'name=cgroupns'], 'resource report changed')


def verified_inputs():
    require(stat.S_ISSOCK(Path(SOCKET).stat().st_mode), 'existing Docker socket required')
    require(identity(Path(DOCKER).read_bytes())['sha256'] == DOCKER_SHA, 'Docker CLI changed')
    readback = load_method('inspect-musl-verifier-rootfs.py')
    plan_raw = readback.read_bounded(PLAN, 1024**2)
    require(identity(plan_raw)['sha256'] == PLAN_SHA, 'reviewed plan changed')
    plan = json.loads(plan_raw)
    raw = readback.read_bounded(TAR, 16 * 1024**2)
    require(identity(raw)['sha256'] == TAR_SHA, 'reviewed rootfs changed')
    readback.inspect(raw, plan)
    return raw, plan


def execute(action, image, output):
    require(output.absolute() == output.resolve() and output.parent.is_dir(), 'output parent must exist without symlinks')
    output = output.resolve()
    raw, plan = verified_inputs()
    output.mkdir(mode=0o700)
    result = {'kind': 'diagnostic-verifier-smoke-v1', 'action': action, 'started_at': now(),
              'method': identity(Path(__file__).read_bytes()), 'tar': identity(raw),
              'source_acceptance': 'not-assessed', 'runtime_qualification': False, 'passed': False}
    try:
        engine = Docker(output)
        preflight(engine)
        if action == 'import':
            imported = engine.call(['image', 'import', '--platform', 'linux/arm64', '--change',
                                   'LABEL ' + LABEL + '=' + TAR_SHA, str(TAR)], seconds=60)
            image = checked(imported).decode('ascii').strip()
            require(re.fullmatch(r'sha256:[0-9a-f]{64}', image) is not None, 'image import result ambiguous')
            result.update(image_id=image, image_retained=True)
            validate_image(inspect(engine, 'image', image, IMAGE_FIELDS), image)
            result.update(passed=True, image_retained=True, containers_started=False)
        else:
            result.update(smoke(engine, image, plan))
    except (OSError, ValueError, KeyError, TypeError) as error:
        result['failure'] = str(error)
        if action == 'import' and 'image_id' not in result:
            result['image_state'] = 'unconfirmed; inspect numbered logs before retrying import'
    finally:
        result['finished_at'] = now()
        with (output / 'result.json').open('x') as stream:
            json.dump(result, stream, sort_keys=True, indent=2)
            stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', choices=['plan', 'import', 'run'], default='plan')
    parser.add_argument('--authorized', action='store_true', help='explicit current-task approval; flag is not approval itself')
    parser.add_argument('--image-id', help='full ID returned by the separately authorized import')
    parser.add_argument('--output', type=Path, help='new output directory under an existing task directory')
    args = parser.parse_args()
    if args.action == 'plan':
        print(json.dumps({'commands': COMMANDS, 'run_seconds_each': RUN_SECONDS, 'run_bytes_per_stream': RUN_BYTES,
                          'control_seconds_each': CONTROL_SECONDS, 'tar': str(TAR), 'tar_sha256': TAR_SHA,
                          'docker': DOCKER, 'socket': SOCKET, 'actions_executed': False}, indent=2))
    else:
        require(args.authorized and args.output is not None, 'reviewed authorization and new output required')
        require(args.action != 'run' or args.image_id is not None and
                re.fullmatch(r'sha256:[0-9a-f]{64}', args.image_id) is not None, 'full image ID required')
        result = execute(args.action, args.image_id, args.output)
        print(json.dumps(result, sort_keys=True, indent=2))
        raise SystemExit(0 if result['passed'] else 1)
