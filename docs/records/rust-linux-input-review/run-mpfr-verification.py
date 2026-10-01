#!/usr/bin/env python3
"""Default offline plan; six fixed GnuPG calls only after explicit execution authorization."""
import argparse
import json
from pathlib import Path
import re
import stat
import sys
import time
from types import ModuleType
import uuid
import importlib.util

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load('run-musl-verification.py')
inputs = load('prepare-mpfr-verification.py')
profile = inputs.profile
smoke, require, identity = base.smoke, base.require, base.identity
IMAGE = base.inputs.IMAGE
OUTPUT = ROOT / '.tmp/mpfr-verification-20260925'
BATCH_SECONDS = 600


def commands():
    steps = [('filter', base.GPG + ['--import-options', 'import-export,self-sigs-only',
                                   '--output', '-', '--import', '/inputs/mpfr.raw.gpg']),
             ('certifications', base.gpg_keyring('mpfr.self.gpg') + base.COLONS + ['--check-sigs', profile.PRIMARY])]
    for case, ring, body in [('verify', 'mpfr.self.gpg', 'mpfr.tar.xz'),
                             ('tampered-body', 'mpfr.self.gpg', 'mpfr.tampered.xz'),
                             ('wrong-primary', 'wrong.gpg', 'mpfr.tar.xz'),
                             ('missing-primary', 'empty.gpg', 'mpfr.tar.xz')]:
        steps.append((case, base.gpg_keyring(ring) + ['--verify', '/inputs/mpfr.tar.xz.asc', '/inputs/' + body]))
    return steps


# The fixed musl invocation has a 1 MiB input bound. MPFR is 1,505,596 bytes.
# Keep its pinned historical method unchanged: this invocation uses the MPFR input snapshot
# (2 MiB/file, 4 MiB total), while reusing its capture, mounts, limits, ownership and cleanup rules.
def run_one(engine, output, folder, run_id, step, command, expected_inputs):
    name = 'rax-mpfr-verify-' + run_id + '-' + step
    report = {'step': step, 'name': name, 'command': command, 'passed': False,
              'expected_inputs': dict(expected_inputs), 'status_file': step + '.status'}
    status_path = output / (step + '.status')
    base.write_new(status_path, b'', 0o666)
    container, start_attempted, create_attempted = None, False, False
    result = None
    try:
        before_inputs = inputs.snapshot(folder)
        report['inputs'] = before_inputs
        require(before_inputs == expected_inputs, 'input identity drift before creation')
        create_attempted = True
        created = engine.call(base.create_args(name, run_id, command, folder, status_path))
        candidate = created['stdout'].decode('ascii', errors='replace').strip()
        if re.fullmatch('[0-9a-f]{64}', candidate):
            container = candidate
        require(smoke.ok(created) and not created['stderr'] and container is not None,
                'container creation failed or ambiguous')
        report['container_id'] = container
        before = smoke.inspect(engine, 'container', container, smoke.CONTAINER_FIELDS)
        base.validate_container(before, name, run_id, command, folder, status_path)
        require(before['Id'] == container and before['State.Status'] == 'created' and
                before['State.Running'] is False, 'container already started or ID changed')
        report['start_command_number'] = engine.sequence + 1
        start_attempted = True
        report['observed_at'] = int(time.time())
        result = engine.call(['container', 'start', '--attach', container], seconds=30, limit=profile.keys.LIMIT)
        report['invocation'] = {k: v for k, v in result.items() if k not in {'stdout', 'stderr'}}
        if result['failure'] is not None:
            report['termination'] = smoke.request_kill(engine, container)
        after = smoke.inspect(engine, 'container', container, smoke.CONTAINER_FIELDS)
        require(after['Id'] == container, 'final container ID drift')
        base.validate_container(after, name, run_id, command, folder, status_path)
        report['final_state'] = {k: v for k, v in after.items() if k.startswith('State.')}
        require(result['failure'] is None, 'incomplete command capture')
        base.exited(after, result['returncode'])
        require(inputs.snapshot(folder) == before_inputs, 'mounted inputs changed during invocation')
        require(stat.S_ISREG(status_path.lstat().st_mode), 'status file is no longer regular')
        raw_status = inputs.retention.read_regular(status_path, profile.keys.LIMIT)
        report.update(inputs=before_inputs, status=identity(raw_status), stdout=identity(result['stdout']),
                      stderr=identity(result['stderr']), passed=True)
        result['status'] = raw_status
    except (OSError, ValueError, KeyError, TypeError) as error:
        report['failure'] = str(error)
        if start_attempted and 'termination' not in report:
            report['termination'] = smoke.request_kill(engine, container)
    finally:
        if container is not None:
            report['cleanup'] = smoke.cleanup(engine, container, IMAGE, name, run_id)
        elif create_attempted:
            report['cleanup'] = {'removed': False, 'uncertain_name': name,
                                 'failure': 'manual reconciliation required; no confirmed container ID'}
        else:
            report['cleanup'] = {'removed': False, 'creation_not_attempted': True}
        try:
            final_status = inputs.retention.read_regular(status_path, profile.keys.LIMIT)
            report['status'] = identity(final_status)
            report['status_after_confirmed_cleanup'] = report['cleanup']['removed']
            if result is not None and 'status' in result:
                require(final_status == result['status'], 'status changed during cleanup')
            status_path.chmod(0o600)
        except (OSError, ValueError) as error:
            report.update(passed=False, status_finalization_failure=str(error))
    report['passed'] = report['passed'] and report['cleanup']['removed']
    return report, result


def assess(step, result, case, folder, files):
    if step == 'filter':
        require(smoke.ok(result), 'GnuPG filter failed')
        base.auxiliary_status(result['status'], base.IMPORT_ALLOWED)
        profile.filtered_material(files['mpfr.raw.gpg'], result['stdout'])
        inputs.write_new(folder / 'mpfr.self.gpg', result['stdout'])
        return {'result': 'all-original-self-material-retained', 'source_acceptance': 'not-assessed'}
    if step == 'certifications':
        require(smoke.ok(result), 'GnuPG self certification check failed')
        base.auxiliary_status(result['status'], {'KEY_CONSIDERED'})
        filtered = inputs.retention.read_regular(folder / 'mpfr.self.gpg', profile.keys.LIMIT)
        return profile.certifications(result['stdout'], files['mpfr.raw.gpg'], filtered, case['observed_at'])
    return profile.verify(result, case['observed_at'], step)


def methods():
    # Bind the actual transitive local Python methods, including inherited diagnostic primitives.
    # verified_inputs loads its tar reader only when called; include that dependency explicitly.
    paths, visited, pending = {Path(__file__).resolve()}, set(), [base, inputs, load('inspect-musl-verifier-rootfs.py')]
    while pending:
        module = pending.pop()
        if id(module) in visited:
            continue
        visited.add(id(module))
        path = Path(module.__file__).resolve() if getattr(module, '__file__', None) else None
        if path is None or not path.is_relative_to(ROOT):
            continue
        paths.add(path)
        pending.extend(value for value in vars(module).values() if isinstance(value, ModuleType))
    return {str(path.relative_to(ROOT)): identity(inputs.retention.read_regular(path)) for path in sorted(paths)}


def execute(output):
    base.safe_path(output)
    require(output.parent.is_dir() and output.parent == ROOT / '.tmp', 'output must be new and directly under .tmp')
    output.mkdir(mode=0o700)
    report = {'kind': 'diagnostic-mpfr-verification-run-v1', 'started_at': smoke.now(), 'run_id': uuid.uuid4().hex,
              'image_id': IMAGE, 'cases': [], 'passed': False, 'source_acceptance': 'not-assessed',
              'runtime_qualification': False, 'key_material_as_of': '2026-09-16',
              'current_all_channel_revocation_checked': False, 'methods': methods(),
              'docker_cli': {'path': smoke.DOCKER, 'sha256': smoke.DOCKER_SHA}, 'docker_socket': smoke.SOCKET}
    started = time.monotonic()
    try:
        prepared, files = inputs.prepare()
        tar, _ = smoke.verified_inputs()
        report.update(prepared_inputs=prepared, rootfs=identity(tar),
                      python={'version': sys.version, 'executable': sys.executable,
                              **identity(Path(sys.executable).read_bytes())})
        folder = inputs.stage(output, files)
        expected = inputs.snapshot(folder)
        engine = smoke.Docker(output)
        smoke.preflight(engine)
        smoke.validate_image(smoke.inspect(engine, 'image', IMAGE, smoke.IMAGE_FIELDS), IMAGE)
        for step, command in commands():
            require(time.monotonic() - started < BATCH_SECONDS - 150, 'batch launch deadline')
            case, result = run_one(engine, output, folder, report['run_id'], step, command, expected)
            report['cases'].append(case)
            require(case['passed'], 'execution or cleanup failed: ' + step)
            case['passed'] = False
            case['assessment'] = assess(step, result, case, folder, files)
            if step == 'filter':
                expected['mpfr.self.gpg'] = identity(result['stdout'])
            case['passed'] = True
        after, after_files = inputs.prepare()
        require(after == prepared and after_files == files and methods() == report['methods'],
                'retained inputs or methods changed during execution')
        report.update(passed=True, source_bytes_rechecked=True,
                      cryptography='performed-by-fixed-GnuPG; host-and-tools-remain-trusted')
    except (OSError, ValueError, KeyError, TypeError) as error:
        report['failure'] = str(error)
    finally:
        report['finished_at'] = smoke.now()
        with (output / 'result.json').open('x') as stream:
            json.dump(report, stream, sort_keys=True, indent=2)
            stream.write('\n')
    return report


def plan(output=OUTPUT):
    return {'kind': 'diagnostic-mpfr-verification-plan-v1', 'commands': dict(commands()),
            'image_id': IMAGE, 'output': str(output), 'docker_socket': smoke.SOCKET,
            'run_seconds_each': 30, 'control_seconds_each': 10, 'stream_and_status_bytes_each': profile.keys.LIMIT,
            'input_bytes_each': inputs.INPUT_LIMIT, 'input_bytes_total': 4 * 1024**2,
            'batch_seconds_budget': BATCH_SECONDS, 'fresh_tmpfs_each_invocation': base.TMPFS,
            'actions_executed': False, 'source_acceptance': 'not-assessed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized', action='store_true', help='records current approval, does not grant it')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = execute(args.output) if args.execute_authorized else plan(args.output)
    print(json.dumps(result, sort_keys=True, indent=2))
    raise SystemExit(0 if not args.execute_authorized or result['passed'] else 1)
