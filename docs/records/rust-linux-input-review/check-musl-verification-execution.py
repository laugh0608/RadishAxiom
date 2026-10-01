#!/usr/bin/env python3
"""Synthetic key, orchestration and failure tests; never starts Docker or GnuPG."""
import hashlib
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


run = load('run-musl-verification.py')
smoke_tests = load('check-musl-smoke.py')
status_tests = load('check-musl-verification.py')
keys = run.keys
NOW = 1790000000
PUB_BODY = b'\x04' + (1700000000).to_bytes(4, 'big') + b'\x01\x00\x08\x91\x00\x02\x03'
SUB_BODY = PUB_BODY[:-1] + b'\x05'
PRIMARY = hashlib.sha1(b'\x99' + len(PUB_BODY).to_bytes(2, 'big') + PUB_BODY).hexdigest().upper()
SIGNER = hashlib.sha1(b'\x99' + len(SUB_BODY).to_bytes(2, 'big') + SUB_BODY).hexdigest().upper()


def packet(tag, body):
    return bytes([0xc0 | tag, 255]) + len(body).to_bytes(4, 'big') + body


def subpacket(tag, body):
    return bytes([len(body) + 1, tag]) + body


def signature(kind, issuer=PRIMARY, digest=8, embedded=None, revoker=None):
    hashed = subpacket(2, (1700000000).to_bytes(4, 'big'))
    if revoker is not None:
        hashed += subpacket(12, b'\x80\x01' + bytes.fromhex(revoker))
    unhashed = subpacket(16, bytes.fromhex(issuer[-16:]))
    if embedded is not None:
        unhashed += subpacket(32, embedded)
    return bytes([4, kind, 1, digest]) + len(hashed).to_bytes(2, 'big') + hashed + \
        len(unhashed).to_bytes(2, 'big') + unhashed + b'\x12\x34\x00\x08\x71'


def raw_key(*, cross=True, foreign=False, revoked=False):
    raw = packet(6, PUB_BODY) + packet(13, b'Synthetic public key') + packet(2, signature(0x13))
    if foreign:
        raw += packet(2, signature(0x13, issuer='E' * 40))
    raw += packet(14, SUB_BODY) + packet(2, signature(0x18, embedded=signature(0x19, SIGNER) if cross else None))
    if revoked:
        raw += packet(2, signature(0x28))
    return raw


def colons():
    return (f'pub:-:8:1:{PRIMARY[-16:]}:1700000000:1900000000:::::scSC:\n'
            f'fpr:::::::::{PRIMARY}:\n'
            'uid:-::::1700000000::::Synthetic public key:::\n'
            f'sig:!::1:{PRIMARY[-16:]}:1700000000::::Synthetic public key:13x::{PRIMARY}:::8:\n'
            f'sub:-:8:1:{SIGNER[-16:]}:1700000000:1900000000:::::s:\n'
            f'fpr:::::::::{SIGNER}:\n'
            f'sig:!::1:{PRIMARY[-16:]}:1700000000::::Synthetic public key:18x::{PRIMARY}:::8:\n').encode()


class KeyChecks(unittest.TestCase):
    def setUp(self):
        self.mapping = patch.dict(keys.status.SIGNERS, {PRIMARY: (SIGNER, '1')})
        self.mapping.start()
        self.addCleanup(self.mapping.stop)

    def verify(self, raw=None, filtered=None, listing=None):
        return keys.certifications(colons() if listing is None else listing, raw_key() if raw is None else raw,
                                   raw_key() if filtered is None else filtered, PRIMARY, NOW)

    def test_synthetic_structure_and_checked_self_signatures(self):
        result = self.verify()
        self.assertEqual(result['self_certifications'], 2)
        self.assertFalse(result['cryptography_executed_by_parser'])

    def test_foreign_certifications_can_be_filtered_but_original_is_retained(self):
        self.assertEqual(self.verify(raw=raw_key(foreign=True))['self_certifications'], 2)
        with self.assertRaisesRegex(ValueError, 'foreign'):
            self.verify(filtered=raw_key(foreign=True))

    def test_original_revocation_cannot_be_hidden_by_filter(self):
        with self.assertRaisesRegex(ValueError, 'revocation'):
            self.verify(raw=raw_key(revoked=True))

    def test_weak_original_foreign_signature_rejected(self):
        raw = raw_key() + packet(2, signature(0x18, issuer='E' * 40, digest=2))
        with self.assertRaisesRegex(ValueError, 'weak'):
            self.verify(raw=raw)

    def test_missing_weak_wrong_or_nested_back_signature(self):
        original = raw_key()
        for embedded in [signature(0x19, SIGNER, digest=2), signature(0x19, PRIMARY), signature(0x18, SIGNER),
                         signature(0x19, SIGNER, embedded=signature(0x19, SIGNER))]:
            raw = original.replace(packet(2, signature(0x18, embedded=signature(0x19, SIGNER))),
                                   packet(2, signature(0x18, embedded=embedded)))
            with self.subTest(embedded=embedded), self.assertRaises(ValueError):
                self.verify(raw=raw, filtered=raw)
        with self.assertRaisesRegex(ValueError, 'cross-certification'):
            self.verify(raw=raw_key(cross=False), filtered=raw_key(cross=False))

    def test_import_cannot_silently_discard_a_bad_self_signature(self):
        raw = raw_key().replace(packet(13, b'Synthetic public key'),
                                packet(13, b'Synthetic public key') + packet(2, signature(0x13)[:-1] + b'X'))
        with self.assertRaisesRegex(ValueError, 'discarded'):
            self.verify(raw=raw)

    def test_key_uid_and_original_signatures_must_be_identical(self):
        for raw in [raw_key().replace(b'Synthetic public key', b'Synthetic public kez'),
                    raw_key().replace(packet(2, signature(0x13)), packet(2, signature(0x13, digest=10)))]:
            with self.assertRaises(ValueError):
                self.verify(filtered=raw)

    def test_colon_revocations_unknown_records_bad_signatures_and_context(self):
        for raw in [colons() + b'rev:!:\n', colons() + b'unknown:\n',
                    colons().replace(b'sig:!', b'sig:-'), colons().replace(b':18x:', b':13x:'),
                    colons().replace(b'pub:-:', b'pub:r:'), colons().replace(b'sub:-:', b'sub:e:'),
                    colons().replace(b'1900000000', str(NOW).encode()),
                    colons().replace(b':1700000000:', b':1990000000:'),
                    colons().replace(b':::8:', b':::2:'),
                    colons().replace(b':scSC:', b':scSCD:')]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.verify(listing=raw)

    def test_missing_duplicate_and_wrong_fingerprints(self):
        for raw in [colons().replace(f'fpr:::::::::{SIGNER}:\n'.encode(), b''),
                    colons() + colons(), colons().replace(SIGNER.encode(), b'F' * 40),
                    colons().replace(b'sig:!', b'sig:%', 1)]:
            with self.assertRaises(ValueError):
                self.verify(listing=raw)

    def test_original_counts_not_just_one_good_uid_and_binding(self):
        raw = raw_key().replace(packet(2, signature(0x13)), packet(2, signature(0x13)) * 2)
        with self.assertRaisesRegex(ValueError, 'every original'):
            self.verify(raw=raw, filtered=raw)

    def test_backsignature_negative_changes_one_unsigned_signature_byte(self):
        original = raw_key()
        changed = keys.corrupt_backsignature(original, PRIMARY)
        self.assertEqual(len(original), len(changed))
        differences = [index for index, (a, b) in enumerate(zip(original, changed)) if a != b]
        self.assertEqual(len(differences), 1)
        back = signature(0x19, SIGNER)
        self.assertEqual(differences[0], original.index(back) + len(back) - 1)

    def test_designated_revoker_is_bound_to_original_without_claiming_revocation(self):
        revoker = 'E' * 40
        direct = packet(2, signature(0x1f, revoker=revoker))
        raw = raw_key().replace(packet(6, PUB_BODY), packet(6, PUB_BODY) + direct)
        listing = colons().replace(f'fpr:::::::::{PRIMARY}:\n'.encode(),
            (f'rvk:::1::::::{revoker}:80:\n' + f'fpr:::::::::{PRIMARY}:\n' +
             f'sig:!::1:{PRIMARY[-16:]}:1700000000::::Synthetic public key:1fx::{PRIMARY}:::8:\n').encode())
        result = self.verify(raw=raw, filtered=raw, listing=b'tru::1:1700000000:0:3:1:5\n' + listing)
        self.assertEqual(result['self_certifications'], 3)
        for changed in [listing.replace(revoker.encode(), b'F' * 40),
                        listing.replace(f'rvk:::1::::::{revoker}:80:\n'.encode(), b'')]:
            with self.assertRaises(ValueError):
                self.verify(raw=raw, filtered=raw, listing=changed)

    def test_unreviewed_hashed_backsignature_mutation_is_rejected(self):
        original = signature(0x18, embedded=signature(0x19, SIGNER))
        hashed_size = int.from_bytes(original[4:6], 'big')
        offset = 6 + hashed_size
        unhashed_size = int.from_bytes(original[offset:offset + 2], 'big')
        hashed = original[6:offset] + original[offset + 2:offset + 2 + unhashed_size]
        changed = original[:4] + len(hashed).to_bytes(2, 'big') + hashed + b'\x00\x00' + original[-5:]
        raw = raw_key().replace(packet(2, original), packet(2, changed))
        with self.assertRaisesRegex(ValueError, 'unexpectedly hashed'):
            keys.corrupt_backsignature(raw, PRIMARY)

    def test_packet_truncation_secret_partial_and_overflow_boundaries(self):
        for raw in [b'', raw_key()[:-1], b'\xc6\xe0', b'\x9bX', packet(5, PUB_BODY),
                    b'x' * (1024**2 + 1), packet(6, PUB_BODY) * 513,
                    packet(6, PUB_BODY) + packet(2, b'\x04\x13\x01\x08\xff\xff')]:
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                keys.inventory(raw, PRIMARY)

    def test_lf_and_colon_bounds(self):
        for raw in [colons().replace(b'\n', b'\r\n'), colons()[:-1], b'\xff\n', b'x' * 8193 + b'\n',
                    colons().replace(b'\n', '\u2028'.encode(), 1), b'tru::1:1:0:3:1:5\n' * 4097]:
            with self.assertRaises(ValueError):
                self.verify(listing=raw)


class FakeDocker:
    def __init__(self, *, changes=None, code=0, failure=None, remove_failure=False, create_failure=False,
                 daemon_loss=False, mutate_inputs=False, status_raw=b'[GNUPG:] KEY_CONSIDERED synthetic 0\n'):
        self.sequence, self.calls = 0, []
        self.changes, self.code, self.failure = changes or {}, code, failure
        self.remove_failure, self.create_failure, self.daemon_loss = remove_failure, create_failure, daemon_loss
        self.mutate_inputs, self.status_raw = mutate_inputs, status_raw

    def call(self, args, **limits):
        self.calls.append((args, limits))
        self.sequence += 1
        operation = tuple(args[:2])
        result = smoke_tests.result
        if operation == ('container', 'create'):
            if self.create_failure:
                return result(code=-9, failure='deadline')
            name = args[args.index('--name') + 1]
            run_id = args[args.index('--label') + 1].split('=', 1)[1]
            command = [args[args.index('--entrypoint') + 1]] + args[args.index(run.inputs.IMAGE) + 1:]
            self.value = smoke_tests.container_fixture(name, run_id, command)
            self.value['Image'] = run.inputs.IMAGE
            mount_values = [args[i + 1] for i, value in enumerate(args) if value == '--mount']
            sources = [dict(part.split('=', 1) for part in value.split(',') if '=' in part)['source']
                       for value in mount_values]
            self.folder, self.status_path = Path(sources[0]), Path(sources[1])
            requested = [
                {'Type': 'bind', 'Source': sources[0], 'Target': '/inputs', 'ReadOnly': True,
                 'BindOptions': {'Propagation': 'rprivate'}},
                {'Type': 'bind', 'Source': sources[1], 'Target': '/work/status', 'ReadOnly': False,
                 'BindOptions': {'Propagation': 'rprivate'}}]
            self.value.update({'HostConfig.Mounts': requested,
                'HostConfig.Tmpfs': {'/tmp': 'rw,noexec,nosuid,nodev,size=16777216,mode=1777',
                    '/work/full': 'rw,noexec,nosuid,nodev,size=16777216,mode=0700,uid=1000,gid=1000'},
                'HostConfig.Ulimits': [{'Name': 'core', 'Hard': 0, 'Soft': 0},
                                      {'Name': 'fsize', 'Hard': 1048576, 'Soft': 1048576}],
                'Mounts': [{'Type': 'bind', 'Source': sources[0], 'Destination': '/inputs', 'RW': False,
                            'Propagation': 'rprivate'},
                           {'Type': 'bind', 'Source': sources[1], 'Destination': '/work/status', 'RW': True,
                            'Propagation': 'rprivate'}]})
            self.value.update(self.changes)
            return result((smoke_tests.CID + '\n').encode())
        if operation == ('container', 'inspect'):
            if self.daemon_loss:
                return result(code=1, stderr=b'synthetic daemon unavailable')
            return result(json.dumps(self.value).encode())
        if operation == ('container', 'start'):
            self.status_path.write_bytes(self.status_raw)
            self.value.update({'State.Status': 'running' if self.failure else 'exited',
                               'State.Running': bool(self.failure), 'State.ExitCode': self.code})
            if self.mutate_inputs:
                path = self.folder / 'synthetic'
                path.chmod(0o644)
                path.write_bytes(b'changed')
                path.chmod(0o444)
            return result(b'synthetic output', self.code, self.failure, b'gpg: synthetic diagnostic\n')
        if operation == ('container', 'kill'):
            self.value.update({'State.Running': False, 'State.Status': 'exited', 'State.ExitCode': 137})
            return result()
        if operation == ('container', 'rm'):
            return result(code=1 if self.remove_failure else 0)
        raise AssertionError(args)


class ExecutionChecks(unittest.TestCase):
    def one(self, engine, before=None):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve()
            folder = output / 'inputs'
            folder.mkdir()
            run.write_new(folder / 'synthetic', b'synthetic input')
            return run.run_one(engine, output, folder, 'synthetic', 'verify', dict(run.commands())['verify'],
                               run.snapshot(folder) if before is None else before)

    def test_separate_status_human_stderr_and_input_binding(self):
        engine = FakeDocker()
        report, result = self.one(engine)
        self.assertTrue(report['passed'])
        self.assertTrue(report['cleanup']['removed'])
        self.assertEqual(report['start_command_number'], 3)
        self.assertEqual(result['status'], engine.status_raw)
        self.assertIn('synthetic', report['inputs'])
        self.assertEqual(engine.calls[2][1], {'seconds': 30, 'limit': 1048576})

    def test_nonzero_exit_is_collected_for_negative_assessment(self):
        report, result = self.one(FakeDocker(code=2))
        self.assertTrue(report['passed'])
        self.assertEqual(result['returncode'], 2)
        with self.assertRaises(ValueError):
            run.status.verify(result['status'], exit_code=2, observed_at=NOW)

    def test_exit_state_mismatch_and_oom_rejected(self):
        for changes in [{'State.OOMKilled': True}, {'State.Error': 'synthetic'}, {'State.Dead': True}]:
            report, _ = self.one(FakeDocker(changes=changes))
            self.assertFalse(report['passed'])
        fixture = smoke_tests.container_fixture('synthetic', 'synthetic', ['/synthetic'])
        fixture['State.Status'] = 'exited'
        for value in [True, 2]:
            fixture['State.ExitCode'] = value
            with self.assertRaises(ValueError):
                run.exited(fixture, 0)

    def test_failed_capture_kills_and_cleans_before_next_step(self):
        for reason in ['deadline', 'stdout-limit', 'stderr-limit']:
            engine = FakeDocker(failure=reason)
            report, _ = self.one(engine)
            self.assertFalse(report['passed'])
            self.assertTrue(report['cleanup']['removed'])
            self.assertEqual(report['status'], run.identity(engine.status_raw))
            self.assertTrue(report['status_after_confirmed_cleanup'])
            operations = [args[1] for args, _ in engine.calls]
            self.assertEqual(operations[operations.index('start') + 1], 'kill')

    def test_status_overflow_and_input_race_fail(self):
        for engine in [FakeDocker(status_raw=b'x' * (1024**2 + 1)), FakeDocker(mutate_inputs=True)]:
            report, _ = self.one(engine)
            self.assertFalse(report['passed'])
            self.assertTrue(report['cleanup']['removed'])
            if len(engine.status_raw) > 1024**2:
                self.assertIn('status_finalization_failure', report)

    def test_changed_inputs_prevent_create(self):
        engine = FakeDocker()
        report, _ = self.one(engine, before={'synthetic': {'bytes': 0, 'sha256': '0' * 64}})
        self.assertFalse(report['passed'])
        self.assertEqual(engine.calls, [])
        self.assertTrue(report['cleanup']['creation_not_attempted'])

    def test_mount_tmpfs_permissions_and_inherited_isolation_drift(self):
        for changes in [{'HostConfig.Tmpfs': run.smoke.TMPFS}, {'HostConfig.Mounts': []}, {'Mounts': []},
                        {'HostConfig.Ulimits': [{'Name': 'core', 'Hard': 0, 'Soft': 0}]},
                        {'HostConfig.NetworkMode': 'host'}, {'HostConfig.Memory': 0},
                        {'Config.OpenStdin': True}, {'Config.Env': run.smoke.ENV + ['LD_PRELOAD=/x']}]:
            engine = FakeDocker(changes=changes)
            report, _ = self.one(engine)
            self.assertFalse(report['passed'])
            self.assertNotIn('start', [args[1] for args, _ in engine.calls])

    def test_ulimit_order_is_irrelevant_but_duplicate_or_boolean_is_rejected(self):
        report, _ = self.one(FakeDocker(changes={'HostConfig.Ulimits': list(reversed(run.ULIMITS))}))
        self.assertTrue(report['passed'])
        for limits in [run.ULIMITS + run.ULIMITS[:1], [{'Name': 'core', 'Hard': False, 'Soft': 0}, run.ULIMITS[1]]]:
            report, _ = self.one(FakeDocker(changes={'HostConfig.Ulimits': limits}))
            self.assertFalse(report['passed'])

    def mount_readonly_case(self, target, value, *, omit=False):
        engine = FakeDocker()
        original = engine.call

        def call(args, **limits):
            result = original(args, **limits)
            if args[:2] == ['container', 'create']:
                mount = next(item for item in engine.value['HostConfig.Mounts'] if item['Target'] == target)
                if omit:
                    del mount['ReadOnly']
                else:
                    mount['ReadOnly'] = value
            return result

        engine.call = call
        return self.one(engine)[0]

    def test_docker_omits_false_readonly_on_status_bind(self):
        report = self.mount_readonly_case('/work/status', None, omit=True)
        self.assertTrue(report['passed'])

    def test_missing_input_readonly_and_wrong_status_types_still_reject(self):
        self.assertFalse(self.mount_readonly_case('/inputs', None, omit=True)['passed'])
        for value in [None, 0, '', True]:
            with self.subTest(value=value):
                self.assertFalse(self.mount_readonly_case('/work/status', value)['passed'])

    def test_ambiguous_create_or_lost_daemon_never_claims_cleanup(self):
        for engine in [FakeDocker(create_failure=True), FakeDocker(daemon_loss=True), FakeDocker(remove_failure=True)]:
            report, _ = self.one(engine)
            self.assertFalse(report['passed'])
            self.assertFalse(report['cleanup']['removed'])
            self.assertTrue(all(args[-1] == smoke_tests.CID for args, _ in engine.calls if args[1] in {'kill', 'rm'}))

    def test_unowned_container_never_starts_or_gets_removed(self):
        engine = FakeDocker(changes={'Config.Labels': {'unowned': 'synthetic'}})
        report, _ = self.one(engine)
        self.assertFalse(report['passed'])
        self.assertTrue(all(args[1] in {'create', 'inspect'} for args, _ in engine.calls))

    def test_auxiliary_status_never_ignores_failures_or_unknown_keywords(self):
        run.auxiliary_status(b'', {'KEY_CONSIDERED'})
        for raw in [b'[GNUPG:] FAILURE import 1\n', b'[GNUPG:] FUTURE_STATUS\n', b'gpg: warning\n']:
            with self.assertRaises(ValueError):
                run.auxiliary_status(raw, run.IMPORT_ALLOWED)

    def test_real_negative_expectations_require_specific_failure(self):
        archive_signer = run.status.SIGNERS[run.status.ARCHIVE][0][-16:]
        result = {'returncode': 2, 'failure': None, 'status': f'[GNUPG:] BADSIG {archive_signer} Synthetic\n'.encode()}
        self.assertEqual(run.negative(result, 'tampered-text')['result'], 'expected-verification-rejection')
        result['status'] = f'[GNUPG:] NO_PUBKEY {archive_signer}\n'.encode()
        run.negative(result, 'missing-archive')
        for changed in [{'returncode': 0}, {'returncode': 137}, {'failure': 'deadline'},
                        {'status': b'[GNUPG:] NO_PUBKEY 0000000000000000\n'},
                        {'status': b'[GNUPG:] FAILURE decrypt 1\n'},
                        {'status': result['status'] + b'[GNUPG:] ERROR memory 1\n'},
                        {'status': result['status'] + b'[GNUPG:] FAILURE decrypt 1\n'}]:
            with self.assertRaises(ValueError):
                run.negative({**result, **changed}, 'missing-archive')

    def test_good_signature_status_does_not_hide_wrong_release_plaintext(self):
        result = {'returncode': 0, 'failure': None, 'status': status_tests.stream().encode(), 'stdout': b'wrong'}
        envelope = b'-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA256\n\nexpected\n-----BEGIN PGP SIGNATURE-----\nx\n'
        with self.assertRaisesRegex(ValueError, 'plaintext'):
            run.assess('verify', result, {'observed_at': NOW}, None, {}, {'InRelease': envelope}, {})

    def test_default_plan_has_nine_steps_and_no_docker_calls(self):
        result = subprocess.run([sys.executable, str(HERE / 'run-musl-verification.py')],
                                capture_output=True, check=True, timeout=5)
        plan = json.loads(result.stdout)
        self.assertEqual(len(plan['commands']), 9)
        self.assertFalse(plan['actions_executed'])
        for command in plan['commands'].values():
            self.assertEqual(command[0], '/usr/bin/gpg')
            self.assertIn('--require-cross-certification', command)
            self.assertIn('--no-autostart', command)
            self.assertIn('/work/status', command)

    def test_backsignature_negative_cannot_pass_as_missing_key_or_good_signature(self):
        signer = run.status.SIGNERS[run.status.ARCHIVE][0][-16:]
        raw = f'[GNUPG:] ERRSIG {signer} 1 8 01 1783760580 1\n'.encode()
        result = {'returncode': 2, 'failure': None, 'status': raw}
        run.negative(result, 'bad-cross-certification')
        for changed in [raw.replace(b'0580 1', b'0580 9'), raw.replace(signer.encode(), b'0' * 16),
                        raw + f'[GNUPG:] NO_PUBKEY {signer}\n'.encode(),
                        raw + f'[GNUPG:] GOODSIG {signer} Synthetic\n'.encode()]:
            with self.assertRaises(ValueError):
                run.negative({**result, 'status': changed}, 'bad-cross-certification')

    def test_unsafe_path_and_overwrite_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'alias').symlink_to(root, target_is_directory=True)
            for path in [root / 'alias' / 'x', root / 'a,b', Path('relative')]:
                with self.assertRaises(ValueError):
                    run.safe_path(path)
            run.write_new(root / 'x', b'synthetic')
            with self.assertRaises(FileExistsError):
                run.write_new(root / 'x', b'changed')

    def test_log_failure_after_start_still_terminates_and_cleans(self):
        engine = FakeDocker()
        original = engine.call

        def call(args, **limits):
            result = original(args, **limits)
            if args[:2] == ['container', 'start']:
                raise OSError('synthetic log write failure')
            return result

        engine.call = call
        report, _ = self.one(engine)
        self.assertFalse(report['passed'])
        self.assertTrue(report['termination']['requested'])
        self.assertTrue(report['cleanup']['removed'])


class BatchChecks(unittest.TestCase):
    def execute(self, *, fail_step=None, assessment_failure=None, changed_archive=False):
        called = []

        def stage(output, files):
            folder = output / 'inputs'
            folder.mkdir()
            run.write_new(folder / 'synthetic', b'synthetic')
            return folder, {}

        def one(engine, output, folder, run_id, step, command, expected):
            called.append(step)
            return ({'step': step, 'passed': step != fail_step, 'cleanup': {'removed': step != fail_step}},
                    {'stdout': b'synthetic-filtered-' + step.encode(), 'returncode': 0})

        def assess(step, *args):
            if step == assessment_failure:
                raise ValueError('synthetic assessment rejected')
            return {'result': 'synthetic-only'}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / '.tmp').mkdir()
            output = root / '.tmp' / 'case'
            prepared = {'synthetic': True}
            second = {'synthetic': False} if changed_archive else prepared
            image = smoke_tests.image_fixture()
            image['Id'] = run.inputs.IMAGE
            with patch.object(run, 'ROOT', root), patch.object(run.inputs, 'prepare', side_effect=[(prepared, {}), (second, {})]), \
                    patch.object(run.smoke, 'verified_inputs', return_value=(b'synthetic-rootfs', {})), \
                    patch.object(run, 'stage', side_effect=stage), patch.object(run.smoke, 'preflight'), \
                    patch.object(run.smoke, 'inspect', return_value=image), patch.object(run, 'run_one', side_effect=one), \
                    patch.object(run, 'assess', side_effect=assess):
                result = run.execute(output)
            self.assertEqual(json.loads((output / 'result.json').read_bytes()), result)
            return result, called

    def test_complete_batch_keeps_source_acceptance_unassessed(self):
        result, called = self.execute()
        self.assertTrue(result['passed'])
        self.assertEqual(called, ['archive-filter', 'archive-certifications', 'release-filter', 'release-certifications',
                                  'verify', 'tampered-text', 'missing-archive', 'missing-release', 'bad-cross-certification'])
        self.assertEqual(result['source_acceptance'], 'not-assessed')
        self.assertFalse(result['runtime_qualification'])
        self.assertFalse(result['current_all_channel_revocation_checked'])

    def test_cleanup_failure_stops_before_consumption_and_next_step(self):
        result, called = self.execute(fail_step='archive-certifications')
        self.assertFalse(result['passed'])
        self.assertEqual(len(called), 2)
        self.assertNotIn('assessment', result['cases'][-1])

    def test_assessment_failure_is_recorded_and_no_next_case_runs(self):
        result, called = self.execute(assessment_failure='verify')
        self.assertFalse(result['passed'])
        self.assertFalse(result['cases'][-1]['passed'])
        self.assertEqual(called[-1], 'verify')
        self.assertIn('synthetic assessment rejected', result['failure'])

    def test_source_archive_drift_after_signatures_cannot_pass(self):
        result, called = self.execute(changed_archive=True)
        self.assertEqual(len(called), 9)
        self.assertFalse(result['passed'])
        self.assertIn('retained source inputs changed', result['failure'])


if __name__ == '__main__':
    unittest.main()
