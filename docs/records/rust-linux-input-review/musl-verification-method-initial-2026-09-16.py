#!/usr/bin/env python3
"""Plan, or explicitly authorized bounded musl signature diagnostics using the retained image."""
import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import importlib.util
import json
from pathlib import Path
import re
import stat
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke = load('run-musl-verifier-smoke.py')
inputs = load('prepare-musl-verification-inputs.py')
keys = load('inspect-musl-verification-keys.py')
key_material = load('inspect-musl-key-status.py')
status = keys.status
require, identity = smoke.require, smoke.identity
STORE = ROOT / 'artifacts/source-inputs/musl-verifier-2fb2e70-20260912'
OUTPUT = ROOT / '.tmp/musl-verification-20260916'
HOME = '/work/full'
HOME_OPTIONS = 'rw,noexec,nosuid,nodev,size=16777216,mode=0700,uid=1000,gid=1000'
TMPFS = {**smoke.TMPFS, HOME: HOME_OPTIONS}
ULIMITS = [{'Name': 'core', 'Hard': 0, 'Soft': 0}, {'Name': 'fsize', 'Hard': 1048576, 'Soft': 1048576}]
GPG = ['/usr/bin/gpg', '--batch', '--no-tty', '--no-options', '--homedir', HOME,
       '--no-autostart', '--disable-dirmngr', '--no-auto-key-retrieve', '--auto-key-locate', 'clear',
       '--no-auto-check-trustdb', '--no-sig-cache', '--lock-never', '--require-cross-certification',
       '--status-file', '/work/status', '--exit-on-status-write-error']
COLONS = ['--with-colons', '--fixed-list-mode', '--with-fingerprint', '--with-subkey-fingerprint']
IMPORT_ALLOWED = {'IMPORT_OK', 'IMPORT_RES', 'IMPORTED', 'KEY_CONSIDERED'}
BATCH_SECONDS = 600


def gpg_keyring(name):
    return GPG + ['--no-default-keyring', '--keyring', '/inputs/' + name]


def commands():
    steps = []
    for role in ('archive', 'release'):
        primary = key_material.KEYS[role]['primary']
        steps.append((role + '-filter', GPG + ['--import-options', 'import-export,self-sigs-only',
                                              '--output', '-', '--import', '/inputs/' + role + '.raw.gpg']))
        steps.append((role + '-certifications', gpg_keyring(role + '.self.gpg') + COLONS + ['--check-sigs', primary]))
    for name, ring, envelope in [('verify', 'debian-archive-keyring.gpg', 'InRelease'),
            ('tampered-text', 'debian-archive-keyring.gpg', 'InRelease.tampered'),
            ('missing-archive', 'release.raw.gpg', 'InRelease'),
            ('missing-release', 'archive.raw.gpg', 'InRelease'),
            ('bad-cross-certification', 'keyring.bad-cross.gpg', 'InRelease')]:
        steps.append((name, gpg_keyring(ring) + ['--proc-all-sigs', '--output', '-', '--decrypt', '/inputs/' + envelope]))
    return steps


def safe_path(path):
    require(path.is_absolute() and path == path.resolve() and
            re.fullmatch(r'/[A-Za-z0-9_./-]+', str(path)), 'unsafe bind/output path')


def write_new(path, raw, mode=0o444):
    safe_path(path)
    with path.open('xb') as stream:
        stream.write(raw)
    path.chmod(mode)
    require(inputs.retention.read_regular(path, keys.LIMIT) == raw, 'written input readback mismatch')


def snapshot(folder):
    safe_path(folder)
    paths = sorted(folder.iterdir())
    require(len(paths) <= 10 and all(re.fullmatch('[A-Za-z0-9.-]+', path.name) for path in paths), 'input set bound')
    require(all(path.lstat().st_mode & 0o777 == 0o444 for path in paths), 'input mode drift')
    return {path.name: identity(inputs.retention.read_regular(path, keys.LIMIT)) for path in paths}


def stage(output, files):
    folder = output / 'inputs'
    inputs.stage(folder, files)
    blocks = keys.key_blocks(files['debian-archive-keyring.gpg'])
    originals = {}
    for role, expected in key_material.KEYS.items():
        raw = key_material.decoded_key(files[role + '.asc'])
        require(blocks.get(expected['primary']) == raw, 'official raw key differs from full original keyring')
        keys.inventory(raw, expected['primary'])
        originals[role] = raw
        write_new(folder / (role + '.raw.gpg'), raw)
    corrupted = keys.corrupt_backsignature(originals['archive'], status.ARCHIVE)
    require(files['debian-archive-keyring.gpg'].count(originals['archive']) == 1, 'archive block not unique')
    write_new(folder / 'keyring.bad-cross.gpg',
              files['debian-archive-keyring.gpg'].replace(originals['archive'], corrupted, 1))
    needle = b'Origin: Debian\n'
    require(files['InRelease'].count(needle) == 1, 'tamper target not unique')
    write_new(folder / 'InRelease.tampered', files['InRelease'].replace(needle, b'Origin: DebiaX\n', 1))
    return folder, originals


def mounts(folder, status_path):
    safe_path(folder)
    safe_path(status_path)
    return [{'Type': 'bind', 'Source': str(folder), 'Target': '/inputs', 'ReadOnly': True,
             'BindOptions': {'Propagation': 'rprivate'}},
            {'Type': 'bind', 'Source': str(status_path), 'Target': '/work/status', 'ReadOnly': False,
             'BindOptions': {'Propagation': 'rprivate'}}]


def create_args(name, run_id, command, folder, status_path):
    args = smoke.create_args(inputs.IMAGE, name, run_id, command)
    extra = ['--tmpfs', HOME + ':' + HOME_OPTIONS, '--ulimit', 'fsize=1048576:1048576']
    for mount in mounts(folder, status_path):
        value = 'type=bind,source=' + mount['Source'] + ',target=' + mount['Target'] + ',bind-propagation=rprivate'
        extra += ['--mount', value + (',readonly' if mount['ReadOnly'] else '')]
    return args[:2] + extra + args[2:]


def validate_container(value, name, run_id, command, folder, status_path):
    expected = mounts(folder, status_path)
    require(value['HostConfig.Mounts'] == expected, 'verification bind specification drift')
    limits = value['HostConfig.Ulimits']
    require(isinstance(limits, list) and all(isinstance(item, dict) and set(item) == {'Name', 'Hard', 'Soft'} and
            isinstance(item['Name'], str) and type(item['Hard']) is int and type(item['Soft']) is int for item in limits),
            'malformed verification ulimits')
    require(value['HostConfig.Tmpfs'] == TMPFS and sorted(limits, key=lambda item: item['Name']) == ULIMITS,
            'verification tmpfs/file-size limit drift')
    effective = {}
    for mount in value['Mounts']:
        destination = mount.get('Destination')
        require(destination not in effective, 'duplicate effective mount')
        effective[destination] = mount
    require({'/inputs', '/work/status'} <= effective.keys() <= {'/inputs', '/work/status', '/tmp', HOME},
            'unexpected effective mount set')
    for requested in expected:
        mount = effective[requested['Target']]
        require(mount.get('Type') == 'bind' and mount.get('Source') == requested['Source'] and
                mount.get('RW') is (not requested['ReadOnly']) and mount.get('Propagation') == 'rprivate',
                'effective bind drift')
    for destination in {'/tmp', HOME} & effective.keys():
        mount = effective[destination]
        require(mount.get('Type') == 'tmpfs' and not mount.get('Source') and mount.get('RW') is True,
                'effective tmpfs drift')
    # Check the explicit differences above, then reuse every original smoke isolation invariant.
    base = dict(value)
    base.update({'HostConfig.Mounts': None, 'HostConfig.Tmpfs': smoke.TMPFS,
                 'HostConfig.Ulimits': ULIMITS[:1], 'Mounts': []})
    smoke.validate_container(base, inputs.IMAGE, name, run_id, command)


def exited(value, code):
    require(type(code) is int and 0 <= code <= 255 and type(value['State.ExitCode']) is int and value['State.ExitCode'] == code,
            'CLI and container exit disagree')
    base = dict(value)
    base['State.ExitCode'] = 0
    smoke.final_state(base)


def run_one(engine, output, folder, run_id, step, command, expected_inputs):
    name = 'rax-musl-verify-' + run_id + '-' + step
    report = {'step': step, 'name': name, 'command': command, 'passed': False,
              'expected_inputs': dict(expected_inputs), 'status_file': step + '.status'}
    status_path = output / (step + '.status')
    write_new(status_path, b'', 0o666)
    container, start_attempted, create_attempted = None, False, False
    result = None
    try:
        before_inputs = snapshot(folder)
        report['inputs'] = before_inputs
        require(before_inputs == expected_inputs, 'input identity drift before creation')
        create_attempted = True
        created = engine.call(create_args(name, run_id, command, folder, status_path))
        candidate = created['stdout'].decode('ascii', errors='replace').strip()
        if re.fullmatch('[0-9a-f]{64}', candidate):
            container = candidate
        require(smoke.ok(created) and not created['stderr'] and container is not None,
                'container creation failed or ambiguous')
        report['container_id'] = container
        before = smoke.inspect(engine, 'container', container, smoke.CONTAINER_FIELDS)
        validate_container(before, name, run_id, command, folder, status_path)
        require(before['Id'] == container and before['State.Status'] == 'created' and
                before['State.Running'] is False, 'container already started or ID changed')
        report['start_command_number'] = engine.sequence + 1
        start_attempted = True
        report['observed_at'] = int(time.time())
        result = engine.call(['container', 'start', '--attach', container], seconds=30, limit=keys.LIMIT)
        report['invocation'] = {k: v for k, v in result.items() if k not in {'stdout', 'stderr'}}
        if result['failure'] is not None:
            report['termination'] = smoke.request_kill(engine, container)
        after = smoke.inspect(engine, 'container', container, smoke.CONTAINER_FIELDS)
        require(after['Id'] == container, 'final container ID drift')
        validate_container(after, name, run_id, command, folder, status_path)
        report['final_state'] = {k: v for k, v in after.items() if k.startswith('State.')}
        require(result['failure'] is None, 'incomplete command capture')
        exited(after, result['returncode'])
        require(snapshot(folder) == before_inputs, 'mounted inputs changed during invocation')
        require(stat.S_ISREG(status_path.lstat().st_mode), 'status file is no longer regular')
        raw_status = inputs.retention.read_regular(status_path, keys.LIMIT)
        report.update(inputs=before_inputs, status=identity(raw_status), stdout=identity(result['stdout']),
                      stderr=identity(result['stderr']), passed=True)
        result['status'] = raw_status
    except (OSError, ValueError, KeyError, TypeError) as error:
        report['failure'] = str(error)
        if start_attempted and 'termination' not in report:
            report['termination'] = smoke.request_kill(engine, container)
    finally:
        if container is not None:
            report['cleanup'] = smoke.cleanup(engine, container, inputs.IMAGE, name, run_id)
        elif create_attempted:
            report['cleanup'] = {'removed': False, 'uncertain_name': name,
                                 'failure': 'manual reconciliation required; no confirmed container ID'}
        else:
            report['cleanup'] = {'removed': False, 'creation_not_attempted': True}
        try:
            final_status = inputs.retention.read_regular(status_path, keys.LIMIT)
            report['status'] = identity(final_status)
            report['status_after_confirmed_cleanup'] = report['cleanup']['removed']
            if result is not None and 'status' in result:
                require(final_status == result['status'], 'status changed during cleanup')
            status_path.chmod(0o600)
        except (OSError, ValueError) as error:
            report.update(passed=False, status_finalization_failure=str(error))
    report['passed'] = report['passed'] and report['cleanup']['removed']
    return report, result


def auxiliary_status(raw, allowed):
    # Auxiliary commands may emit no status records. Their typed output and exit are still mandatory.
    if raw == b'':
        return
    for line in keys.text_lines(raw):
        require(line.startswith('[GNUPG:] '), 'malformed auxiliary status')
        keyword = line[9:].partition(' ')[0]
        require(keyword in allowed, 'unexpected auxiliary status: ' + keyword)


def negative(result, step):
    require(result['failure'] is None and type(result['returncode']) is int and 0 < result['returncode'] < 126,
            'negative case did not produce a normal GnuPG failure')
    lines = keys.text_lines(result['status'])
    require(all(line.startswith('[GNUPG:] ') for line in lines), 'malformed negative status')
    fields = [line[9:].split() for line in lines]
    require(all(f for f in fields), 'empty negative status')
    allowed = {'NEWSIG', 'KEY_CONSIDERED', 'SIG_ID', 'GOODSIG', 'VALIDSIG', 'PLAINTEXT',
               'TRUST_UNDEFINED', 'VERIFICATION_COMPLIANCE_MODE', 'BADSIG', 'ERRSIG', 'NO_PUBKEY', 'FAILURE'}
    require(all(f[0] in allowed for f in fields), 'unexpected negative-case status')
    require(all(f[0] != 'FAILURE' or len(f) == 3 and f[1] == 'gpg-exit' and f[2].isdigit() for f in fields),
            'unrelated failure in negative case')
    if step == 'bad-cross-certification':
        signer = status.SIGNERS[status.ARCHIVE][0][-16:]
        require(any(len(f) in {7, 8} and f[:5] == ['ERRSIG', signer, '1', '8', '01'] and f[6] == '1'
                    for f in fields), 'bad back-signature did not reach expected archive signature error')
        require(not any(f[0] in {'VALIDSIG', 'GOODSIG', 'NO_PUBKEY'} and len(f) >= 2 and
                        f[1] in {signer, status.SIGNERS[status.ARCHIVE][0]} for f in fields),
                'bad back-signature accepted or archive key unavailable')
    elif step == 'tampered-text':
        known = {binding[0][-16:] for binding in status.SIGNERS.values()}
        require(any(f[0] == 'BADSIG' and len(f) >= 3 and f[1] in known for f in fields),
                'tamper did not reach a known signature mismatch')
    else:
        role = status.ARCHIVE if step == 'missing-archive' else status.RELEASE
        signer = status.SIGNERS[role][0][-16:]
        require(any(f == ['NO_PUBKEY', signer] for f in fields), 'missing role did not reach expected key failure')
    return {'result': 'expected-verification-rejection', 'case': step}


def release_body(envelope):
    require(envelope.startswith(b'-----BEGIN PGP SIGNED MESSAGE-----\n') and
            envelope.count(b'-----BEGIN PGP SIGNATURE-----\n') == 1, 'invalid fixed cleartext envelope')
    body = envelope.split(b'\n\n', 1)[1].split(b'-----BEGIN PGP SIGNATURE-----\n', 1)[0]
    return b'\n'.join(line[2:] if line.startswith(b'- ') else line for line in body.split(b'\n'))


def assess(step, result, report, folder, originals, files, prepared):
    if step in {'tampered-text', 'missing-archive', 'missing-release', 'bad-cross-certification'}:
        return negative(result, step)
    require(smoke.ok(result), 'GnuPG command failed')
    if step.endswith('-filter'):
        auxiliary_status(result['status'], IMPORT_ALLOWED)
        role = step.removesuffix('-filter')
        keys.filtered_material(originals[role], result['stdout'], key_material.KEYS[role]['primary'])
        write_new(folder / (role + '.self.gpg'), result['stdout'])
        return {'result': 'self-material-retained', 'raw_key_unchanged': True}
    if step.endswith('-certifications'):
        auxiliary_status(result['status'], {'KEY_CONSIDERED'})
        role = step.removesuffix('-certifications')
        filtered = inputs.retention.read_regular(folder / (role + '.self.gpg'), keys.LIMIT)
        return keys.certifications(result['stdout'], originals[role], filtered,
                                   key_material.KEYS[role]['primary'], report['observed_at'])
    matched = status.verify(result['status'], exit_code=result['returncode'], observed_at=report['observed_at'],
                            failure=result['failure'])
    require(result['stdout'] == release_body(files['InRelease']), 'GnuPG Release plaintext differs from snapshot')
    release = list(inputs.auth.chain.stanzas(result['stdout'].decode('utf-8').splitlines(keepends=True)))
    require(len(release) == 1, 'multiple Release stanzas')
    observed = datetime.fromtimestamp(report['observed_at'], timezone.utc)
    require(parsedate_to_datetime(release[0]['date']) <= observed and
            ('valid-until' not in release[0] or parsedate_to_datetime(release[0]['valid-until']) > observed),
            'Release outside its declared validity')
    require(inputs.auth.chain.checksums(release[0]['sha256'])['main/source/Sources.xz'] ==
            prepared['host_only']['Sources.xz'], 'verified Release/Sources identity mismatch')
    return {'result': 'two-role-signatures-and-plaintext-matched', 'signature_status': matched,
            'source_acceptance': 'not-assessed'}


def execute(output):
    safe_path(output)
    require(output.parent.is_dir() and output.parent == ROOT / '.tmp', 'new task output must be directly under .tmp')
    output.mkdir(mode=0o700)
    report = {'kind': 'diagnostic-musl-verification-run-v1', 'started_at': smoke.now(), 'run_id': uuid.uuid4().hex,
              'image_id': inputs.IMAGE, 'cases': [],
              'docker_cli': {'path': smoke.DOCKER, 'sha256': smoke.DOCKER_SHA}, 'docker_socket': smoke.SOCKET,
              'source_acceptance': 'not-assessed', 'runtime_qualification': False, 'passed': False,
              'key_material_as_of': '2026-09-10', 'current_all_channel_revocation_checked': False,
              'methods': {name: identity((HERE / name).read_bytes()) for name in
                          ['run-musl-verification.py', 'inspect-musl-verification-keys.py',
                           'inspect-musl-verification-status.py', 'run-musl-verifier-smoke.py',
                           'inspect-musl-key-status.py', 'inspect-musl-verifier-rootfs.py',
                           'inspect-musl-verifier-content.py', 'inspect-selected-inputs.py']}}
    started = time.monotonic()
    try:
        prepared, files = inputs.prepare(STORE)
        tar, _ = smoke.verified_inputs()
        report.update(rootfs=identity(tar), prepared_inputs=prepared,
                      python={'version': sys.version, 'executable': sys.executable,
                              **identity(Path(sys.executable).read_bytes())})
        folder, originals = stage(output, files)
        expected_inputs = snapshot(folder)
        engine = smoke.Docker(output)
        smoke.preflight(engine)
        smoke.validate_image(smoke.inspect(engine, 'image', inputs.IMAGE, smoke.IMAGE_FIELDS), inputs.IMAGE)
        for step, command in commands():
            # Leave room for one invocation, inspection and confirmed cleanup within the batch budget.
            require(time.monotonic() - started < BATCH_SECONDS - 150, 'batch launch deadline')
            case, result = run_one(engine, output, folder, report['run_id'], step, command, expected_inputs)
            report['cases'].append(case)
            require(case['passed'], 'execution or cleanup failed: ' + step)
            case['passed'] = False
            case['assessment'] = assess(step, result, case, folder, originals, files, prepared)
            if step.endswith('-filter'):
                expected_inputs[step.removesuffix('-filter') + '.self.gpg'] = identity(result['stdout'])
            case['passed'] = True
        rechecked, rechecked_files = inputs.prepare(STORE)
        require(rechecked == prepared and rechecked_files == files, 'retained source inputs changed during run')
        report.update(passed=True, source_bytes_rechecked=True,
                      cryptography='performed-by-fixed-GnuPG; host-and-tools-remain-trusted',
                      cross_certification='required-by-GnuPG-for-archive-signer')
    except (OSError, ValueError, KeyError, TypeError) as error:
        report['failure'] = str(error)
    finally:
        report['finished_at'] = smoke.now()
        with (output / 'result.json').open('x') as stream:
            json.dump(report, stream, sort_keys=True, indent=2)
            stream.write('\n')
    return report


def plan():
    return {'commands': dict(commands()), 'image_id': inputs.IMAGE, 'store': str(STORE), 'output': str(OUTPUT),
            'run_seconds_each': 30, 'control_seconds_each': 10, 'stream_bytes_each': keys.LIMIT,
            'status_file_bytes_limit': keys.LIMIT, 'batch_seconds_budget': BATCH_SECONDS,
            'fresh_tmpfs_each_invocation': TMPFS, 'source_acceptance': 'not-assessed', 'actions_executed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized', action='store_true', help='flag records approval; does not grant it')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = execute(args.output) if args.execute_authorized else plan()
    print(json.dumps(result, sort_keys=True, indent=2))
    raise SystemExit(0 if not args.execute_authorized or result['passed'] else 1)
