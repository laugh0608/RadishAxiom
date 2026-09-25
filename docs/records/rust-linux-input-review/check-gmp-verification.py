#!/usr/bin/env python3
"""Synthetic GMP material, status, staging and fake-daemon tests; no Docker/GnuPG."""
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


run = load('run-gmp-verification.py')
p = run.profile
inherited = load('check-musl-verification-execution.py')
packet, subpacket = inherited.packet, inherited.subpacket

NOW = 1790000000
PUB = b'\x04' + p.KEY_CREATED.to_bytes(4, 'big') + b'\x01synthetic-rsa-primary'
SUB = PUB[:6] + b'synthetic-rsa-encryption'
PRIMARY, SUBKEY = p.keys.fingerprint(PUB), p.keys.fingerprint(SUB)
UID = b'Synthetic: GMP'


def sig(kind='uid', old=False, revocation=False, extra=b''):
    issuer = '598F95AAF6C99C5F' if revocation else PRIMARY[-16:]
    created = p.KEY_CREATED if old or revocation else p.SELF_CREATED[kind]
    hashed = subpacket(2, created.to_bytes(4, 'big'))
    if not revocation:
        hashed += subpacket(9, (315360000 if old else p.EXPIRES[kind] - p.KEY_CREATED).to_bytes(4, 'big'))
        hashed += subpacket(27, b'\x03' if kind == 'uid' else b'\x0c')
        hashed += subpacket(33, b'\x04' + bytes.fromhex(PRIMARY))
    hashed += extra
    unhashed = subpacket(16, bytes.fromhex(issuer))
    return bytes([4, 0x30 if revocation else 0x13 if kind == 'uid' else 0x18, 1, 2 if old else 8]) + \
        len(hashed).to_bytes(2, 'big') + hashed + len(unhashed).to_bytes(2, 'big') + unhashed + b'\x12\x34\x00\x08\x71'


def raw_key(full=False):
    raw = packet(6, PUB) + packet(13, UID) + packet(2, sig())
    if full:
        raw += packet(2, sig(old=True)) + packet(2, sig(revocation=True))
    raw += packet(14, SUB) + packet(2, sig('sub'))
    if full:
        raw += packet(2, sig('sub', old=True))
    return raw


def colons():
    text = f'pub:e:2048:1:{PRIMARY[-16:]}:{p.KEY_CREATED}:{p.EXPIRES["pub"]}:::::sc:\n'
    text += f'fpr:::::::::{PRIMARY}:\nuid:e::::{p.SELF_CREATED["uid"]}::::Synthetic\\x3a GMP:::\n'
    text += f'sig:!::1:{PRIMARY[-16:]}:{p.SELF_CREATED["uid"]}:::::13x::{PRIMARY}:::8:\n'
    text += f'sub:e:2048:1:{SUBKEY[-16:]}:{p.KEY_CREATED}:{p.EXPIRES["sub"]}:::::e:\n'
    text += f'fpr:::::::::{SUBKEY}:\n'
    text += f'sig:!::1:{PRIMARY[-16:]}:{p.SELF_CREATED["sub"]}:::::18x::{PRIMARY}:::8:\n'
    return text.encode()


def result(status, code=0, **changes):
    return {'failure': None, 'returncode': code, 'stdout': b'', 'stderr': b'synthetic diagnostic\n',
            'status': status.encode() if isinstance(status, str) else status, **changes}


def good():
    return (f'[GNUPG:] NEWSIG\n[GNUPG:] KEY_CONSIDERED {p.PRIMARY} 0\n'
            f'[GNUPG:] KEYEXPIRED {p.EXPIRES["pub"]}\n[GNUPG:] SIG_ID synthetic 2023-07-30 {p.CREATED}\n'
            f'[GNUPG:] EXPKEYSIG {p.PRIMARY[-16:]} Synthetic\n'
            f'[GNUPG:] VALIDSIG {p.PRIMARY} 2023-07-30 {p.CREATED} 0 4 0 1 10 00 {p.PRIMARY}\n')


def missing():
    return (f'[GNUPG:] NEWSIG\n[GNUPG:] ERRSIG {p.PRIMARY[-16:]} 1 10 00 {p.CREATED} 9 {p.PRIMARY}\n'
            f'[GNUPG:] NO_PUBKEY {p.PRIMARY[-16:]}\n')


class MaterialChecks(unittest.TestCase):
    def setUp(self):
        for name, value in [('PRIMARY', PRIMARY), ('SUBKEY', SUBKEY),
                            ('REVOCATION_SHA', p.identity(sig(revocation=True))['sha256'])]:
            handle = patch.object(p, name, value)
            handle.start()
            self.addCleanup(handle.stop)

    def verify(self, original=None, filtered=None, listing=None, now=NOW):
        return p.certifications(colons() if listing is None else listing, raw_key() if original is None else original,
                                raw_key() if filtered is None else filtered, now)

    def test_expired_key_keeps_signature_time_separate(self):
        checked = self.verify()
        self.assertEqual(checked['current_key_state'], 'expired')
        self.assertEqual(checked['historical_validity'], 'not-established')
        self.assertEqual(checked['source_acceptance'], 'not-assessed')

    def test_projection_accounts_for_old_self_and_revocation(self):
        raw, report = p.project(raw_key(True))
        self.assertEqual(raw, raw_key())
        self.assertEqual(len(report['excluded']), 3)
        self.assertEqual(len(report['revocations']), 1)
        self.assertEqual(report['revocation_authentication'], 'not-performed')

    def test_new_self_key_subkey_or_uid_revocation_stops(self):
        for kind in (0x20, 0x28, 0x30):
            extra = sig()[:1] + bytes([kind]) + sig()[2:]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                p.project(raw_key(True) + packet(2, extra))

    def test_changed_foreign_revocation_needs_review(self):
        body = sig(revocation=True)
        for changed in (body[:-1] + b'X', body.replace(bytes.fromhex('598F95AAF6C99C5F'), bytes.fromhex('1234567890ABCDEF'))):
            with self.assertRaises(ValueError):
                p.project(raw_key(True).replace(body, changed))

    def test_missing_duplicate_or_weak_selected_self_rejected(self):
        for changed in (raw_key().replace(packet(2, sig()), b''), raw_key() + packet(2, sig()),
                        raw_key().replace(sig(), sig(old=True)), raw_key(True)):
            with self.assertRaises(ValueError):
                self.verify(filtered=changed)

    def test_changed_self_value_or_subject_rejected(self):
        for changed in (raw_key().replace(sig(), sig()[:-1] + b'X'), raw_key().replace(UID, b'Synthetic: BAD')):
            with self.assertRaises(ValueError):
                self.verify(filtered=changed)

    def test_unknown_critical_revoker_and_embedded_subpackets_rejected(self):
        for tag in (12, 32, 99, 128 | 2):
            changed = raw_key().replace(sig(), sig(extra=subpacket(tag, b'\0\0\0\1')))
            with self.assertRaises(ValueError):
                p.inventory(changed)

    def test_time_expiry_and_capability_changes_rejected(self):
        for old, new in [(p.EXPIRES['uid'] - p.KEY_CREATED, 1), (p.SELF_CREATED['uid'], p.CREATED + 1)]:
            with self.assertRaises(ValueError):
                p.inventory(raw_key().replace(old.to_bytes(4, 'big'), new.to_bytes(4, 'big')))
        with self.assertRaises(ValueError):
            p.inventory(raw_key().replace(subpacket(27, b'\x03'), subpacket(27, b'\x01')))

    def test_colon_expiry_revocation_disable_missing_or_wrong_uid(self):
        for changed in (colons().replace(b'pub:e:', b'pub:r:'), colons().replace(b'uid:e:', b'uid:r:'),
                        colons().replace(b':sc:', b':scD:'), colons().replace(b'Synthetic', b'Changed'),
                        colons().replace(str(p.EXPIRES['pub']).encode(), b'0'),
                        colons().replace(b'sig:!', b'sig:?'), colons().replace(b':::8:', b':::2:'),
                        colons().replace(b':13x:', b':18x:'), colons() + colons().splitlines(keepends=True)[3],
                        colons() + b'rvk::::::::::::\n'):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.verify(listing=changed)

    def test_faked_or_earlier_observation_not_a_profile_option(self):
        for now in (False, p.CREATED, p.EXPIRES['pub']):
            with self.assertRaises(ValueError):
                self.verify(now=now)

    def test_truncated_secret_oversized_or_line_overflow(self):
        for raw in (b'', raw_key()[:-1], packet(5, PUB), b'x' * (1024**2 + 1)):
            with self.assertRaises(ValueError):
                p.inventory(raw)
        for text in (colons()[:-1], colons().replace(b'\n', b'\r\n'), colons() + b'x' * 8193 + b'\n'):
            with self.assertRaises(ValueError):
                self.verify(listing=text)


class StatusChecks(unittest.TestCase):
    def test_expired_positive_is_diagnostic_only(self):
        row = p.verify(result(good()), NOW)
        self.assertEqual(row['result'], 'signature-relation-matched-with-expired-key')
        self.assertEqual(row['historical_validity'], 'not-established')
        self.assertEqual(row['source_acceptance'], 'not-assessed')

    def test_expiry_cannot_be_silently_ignored(self):
        for changed in (good().replace('EXPKEYSIG', 'GOODSIG'),
                        good().replace(f'[GNUPG:] KEYEXPIRED {p.EXPIRES["pub"]}\n', ''),
                        good().replace(str(p.EXPIRES['pub']), str(p.EXPIRES['sub'])),
                        good().replace('EXPKEYSIG', 'REVKEYSIG')):
            with self.assertRaises(ValueError):
                p.verify(result(changed), NOW)

    def test_binding_algorithm_signer_time_and_class_mutations(self):
        for changed in (good().replace('1 10 00', '1 2 00'), good().replace('1 10 00', '1 8 00'),
                        good().replace('1 10 00', '1 10 01'), good().replace(p.PRIMARY, 'A' * 40),
                        good().replace('2023-07-30', '2023-07-31'), good().replace(' 0 4 0 ', ' 1 4 0 ')):
            with self.assertRaises(ValueError):
                p.verify(result(changed), NOW)

    def test_unexpected_status_duplicate_or_missing_success_fails(self):
        for suffix in ('NEWSIG', 'FAILURE verify 1', 'ERROR verify 1', 'TRUST_FULLY 0 pgp',
                       'EXPSIG synthetic', 'REVKEYSIG synthetic', 'FUTURE_STATUS'):
            with self.assertRaises(ValueError):
                p.verify(result(good() + '[GNUPG:] ' + suffix + '\n'), NOW)
        lines = good().splitlines(keepends=True)
        for changed in (''.join(lines[:-1]), good() + lines[-1], ''.join(lines[:3] + lines[4:])):
            with self.assertRaises(ValueError):
                p.verify(result(changed), NOW)

    def test_incomplete_capture_or_abnormal_exit_not_positive(self):
        for changes in ({'failure': 'deadline'}, {'returncode': 2}, {'returncode': False}, {'stdout': b'x'}):
            with self.assertRaises(ValueError):
                p.verify(result(good(), **changes), NOW)

    def test_tampered_body_requires_target_badsig(self):
        text = f'[GNUPG:] NEWSIG\n[GNUPG:] KEY_CONSIDERED {p.PRIMARY} 0\n[GNUPG:] BADSIG {p.PRIMARY[-16:]} Synthetic\n'
        p.verify(result(text, 1), NOW, 'tampered-body')
        for changed in (text.replace('BADSIG', 'EXPKEYSIG'), text + good(), text.replace(p.PRIMARY[-16:], 'A' * 16)):
            with self.assertRaises(ValueError):
                p.verify(result(changed, 1), NOW, 'tampered-body')

    def test_wrong_and_missing_key_require_precise_reason(self):
        for case in ('wrong-primary', 'missing-primary'):
            p.verify(result(missing(), 2), NOW, case)
            for changed in (missing().replace(' 9 ', ' 4 '), missing().split('[GNUPG:] NO_PUBKEY')[0],
                            missing() + '[GNUPG:] FAILURE open 1\n', missing() + good()):
                with self.assertRaises(ValueError):
                    p.verify(result(changed, 2), NOW, case)

    def test_timeout_oom_or_signal_is_not_expected_rejection(self):
        for changes in ({'returncode': 0}, {'returncode': 137}, {'failure': 'stdout-limit'}):
            with self.assertRaises(ValueError):
                p.verify(result(missing(), **changes), NOW, 'missing-primary')

class ExecutionChecks(unittest.TestCase):
    def one(self, engine, expected=None):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve()
            folder = output / 'inputs'
            folder.mkdir()
            run.inputs.write_new(folder / 'synthetic', b'x' * 1505596)
            return run.run_one(engine, output, folder, 'synthetic', 'verify', dict(run.commands())['verify'],
                               run.inputs.snapshot(folder) if expected is None else expected)

    def test_larger_readonly_input_uses_same_output_and_status_limits(self):
        engine = inherited.FakeDocker()
        report, _ = self.one(engine)
        self.assertTrue(report['passed'])
        self.assertTrue(report['name'].startswith('rax-gmp-verify-'))
        self.assertEqual(engine.calls[2][1], {'seconds': 30, 'limit': 1048576})

    def test_input_drift_blocks_start_and_race_blocks_success(self):
        engine = inherited.FakeDocker()
        self.assertFalse(self.one(engine, {})[0]['passed'])
        self.assertEqual(engine.calls, [])
        self.assertFalse(self.one(inherited.FakeDocker(mutate_inputs=True))[0]['passed'])

    def test_mount_or_resource_drift_prevents_start(self):
        for change in [{'HostConfig.NetworkMode': 'host'}, {'HostConfig.Memory': 0},
                       {'HostConfig.Mounts': []}, {'Mounts': []}, {'HostConfig.Tmpfs': {}}]:
            engine = inherited.FakeDocker(changes=change)
            self.assertFalse(self.one(engine)[0]['passed'])
            self.assertNotIn('start', [args[1] for args, _ in engine.calls])

    def test_failures_terminate_and_ambiguous_cleanup_stays_failed(self):
        for failure in ['deadline', 'stdout-limit', 'stderr-limit']:
            row, _ = self.one(inherited.FakeDocker(failure=failure))
            self.assertFalse(row['passed'])
            self.assertTrue(row['termination']['requested'])
            self.assertTrue(row['cleanup']['removed'])
        for engine in [inherited.FakeDocker(remove_failure=True), inherited.FakeDocker(create_failure=True),
                       inherited.FakeDocker(daemon_loss=True)]:
            row, _ = self.one(engine)
            self.assertFalse(row['passed'])
            self.assertFalse(row['cleanup']['removed'])

    def test_status_overflow_and_oom_rejected(self):
        for engine in [inherited.FakeDocker(status_raw=b'x' * (1024**2 + 1)),
                       inherited.FakeDocker(changes={'State.OOMKilled': True})]:
            self.assertFalse(self.one(engine)[0]['passed'])

    def test_unowned_container_is_never_started_or_removed(self):
        engine = inherited.FakeDocker(changes={'Config.Labels': {'other-owner': 'synthetic'}})
        self.assertFalse(self.one(engine)[0]['passed'])
        self.assertTrue(all(args[1] in {'create', 'inspect'} for args, _ in engine.calls))

    def test_log_write_error_after_start_still_cleans_up(self):
        engine = inherited.FakeDocker()
        original = engine.call

        def call(args, **limits):
            value = original(args, **limits)
            if args[:2] == ['container', 'start']:
                raise OSError('synthetic log failure')
            return value

        engine.call = call
        report, _ = self.one(engine)
        self.assertFalse(report['passed'])
        self.assertTrue(report['termination']['requested'])
        self.assertTrue(report['cleanup']['removed'])

    def test_staging_bounds_symlinks_and_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve()
            run.inputs.write_new(folder / 'x', b'x')
            with self.assertRaises(FileExistsError):
                run.inputs.write_new(folder / 'x', b'y')
            (folder / 'alias').symlink_to(folder / 'x')
            with self.assertRaises(ValueError):
                run.inputs.snapshot(folder)
            with self.assertRaises(ValueError):
                run.inputs.write_new(folder / 'oversized', b'x' * (2 * 1024**2 + 1))

    def test_store_corruption_is_detected_without_external_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            store = root / 'artifacts/source-inputs/synthetic'
            (store / 'objects').mkdir(parents=True)
            data = b'synthetic'
            row = {'path': 'synthetic.bin', **run.identity(data)}
            raw = json.dumps({'kind': 'diagnostic-musl-retention-manifest-v1', 'files': [row]}).encode()
            (store / 'manifest.json').write_bytes(raw)
            (root / 'reviewed.json').write_bytes(raw)
            (store / 'objects' / row['sha256']).write_bytes(data)
            with patch.object(run.inputs.prior, 'HERE', root):
                self.assertEqual(run.inputs.prior.read_store(root, 'synthetic', 'reviewed.json', run.identity(raw)['sha256'])[0],
                                 {'synthetic.bin': data})
                (store / 'objects' / row['sha256']).write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'corruption'):
                    run.inputs.prior.read_store(root, 'synthetic', 'reviewed.json', run.identity(raw)['sha256'])

    def test_cumulative_input_bound_and_readonly_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve()
            for i in range(4):
                run.inputs.write_new(folder / str(i), b'x' * 1505596)
            with self.assertRaisesRegex(ValueError, 'cumulative'):
                run.inputs.snapshot(folder)
            (folder / '0').chmod(0o644)
            with self.assertRaisesRegex(ValueError, 'mode drift'):
                run.inputs.snapshot(folder)

    def test_method_inventory_includes_deferred_rootfs_reader(self):
        methods = run.methods()
        for name in ('run-gmp-verification.py', 'prepare-gmp-verification.py', 'inspect-gmp-verification.py',
                     'inspect-musl-verifier-rootfs.py', 'run-musl-verifier-smoke.py'):
            self.assertIn('docs/records/rust-linux-input-review/' + name, methods)

    def test_default_plan_does_not_construct_docker(self):
        with patch.object(run.smoke, 'Docker', side_effect=AssertionError('unexpected Docker')):
            plan = run.plan()
        self.assertEqual(list(plan['commands']), ['filter', 'certifications', 'verify', 'tampered-body',
                                                 'wrong-primary', 'missing-primary'])
        self.assertFalse(plan['actions_executed'])
        completed = subprocess.run([sys.executable, str(HERE / 'run-gmp-verification.py')],
                                   capture_output=True, check=True, timeout=5)
        self.assertEqual(json.loads(completed.stdout), plan)

    def test_commands_cannot_enable_weak_digest_or_fake_time(self):
        for _, argv in run.commands():
            self.assertTrue({'--no-options', '--disable-dirmngr', '--no-auto-key-retrieve'} <= set(argv))
            self.assertFalse(any('faked' in arg or 'ignore-time' in arg or 'ignore-valid-from' in arg or
                                 'allow-weak' in arg or 'trust-model' in arg for arg in argv))
        self.assertIn('/inputs/gmp.strong.gpg', dict(run.commands())['filter'])

    def test_retained_methods_preserve_exact_source_bytes(self):
        methods = run.methods()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve()
            run.retain_methods(output, methods)
            for name, expected in methods.items():
                self.assertEqual(run.identity((output / 'methods' / name).read_bytes()), expected)
            with self.assertRaises(FileExistsError):
                run.retain_methods(output, methods)


class BatchChecks(unittest.TestCase):
    def execute(self, failed=None, rejected=None, drift=False):
        calls = []

        def stage(output, files):
            folder = output / 'inputs'
            folder.mkdir()
            return folder

        def one(engine, output, folder, run_id, step, command, expected):
            calls.append(step)
            return {'step': step, 'passed': step != failed}, {'stdout': b'synthetic'}

        def assess(step, *args):
            if step == rejected:
                raise ValueError('synthetic assessment failure')
            return {'synthetic': True}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / '.tmp').mkdir()
            output = root / '.tmp/test'
            image = inherited.smoke_tests.image_fixture()
            image['Id'] = run.IMAGE
            with patch.object(run, 'ROOT', root), patch.object(run, 'methods', return_value={'synthetic': True}), \
                    patch.object(run, 'retain_methods'), \
                    patch.object(run.inputs, 'prepare', side_effect=[({}, {}), ({'drift': True} if drift else {}, {})]), \
                    patch.object(run.inputs, 'stage', side_effect=stage), \
                    patch.object(run.smoke, 'verified_inputs', return_value=(b'synthetic', {})), \
                    patch.object(run.smoke, 'preflight'), patch.object(run.smoke, 'inspect', return_value=image), \
                    patch.object(run, 'run_one', side_effect=one), patch.object(run, 'assess', side_effect=assess):
                report = run.execute(output)
            self.assertEqual(json.loads((output / 'result.json').read_bytes()), report)
        return report, calls

    def test_complete_batch_does_not_accept_source_or_qualify_runtime(self):
        report, calls = self.execute()
        self.assertTrue(report['passed'])
        self.assertEqual(len(calls), 6)
        self.assertEqual(report['source_acceptance'], 'not-assessed')
        self.assertFalse(report['runtime_qualification'])
        self.assertFalse(report['current_all_channel_revocation_checked'])

    def test_failed_execution_or_cleanup_stops_consumption(self):
        report, calls = self.execute(failed='certifications')
        self.assertFalse(report['passed'])
        self.assertEqual(calls, ['filter', 'certifications'])
        self.assertNotIn('assessment', report['cases'][-1])

    def test_rejected_assessment_stops_next_case(self):
        report, calls = self.execute(rejected='verify')
        self.assertFalse(report['passed'])
        self.assertFalse(report['cases'][-1]['passed'])
        self.assertEqual(calls[-1], 'verify')

    def test_retained_input_drift_prevents_batch_success(self):
        report, calls = self.execute(drift=True)
        self.assertEqual(len(calls), 6)
        self.assertFalse(report['passed'])
        self.assertIn('changed during execution', report['failure'])


if __name__ == '__main__':
    unittest.main()
