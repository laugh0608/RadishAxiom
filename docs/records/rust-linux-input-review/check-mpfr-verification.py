#!/usr/bin/env python3
"""Synthetic MPFR material, status, staging and fake-daemon tests; no Docker/GnuPG."""
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


run = load('run-mpfr-verification.py')
p = run.profile
inherited = load('check-musl-verification-execution.py')
packet, subpacket = inherited.packet, inherited.subpacket
NOW = 1790000000
PUB = b'\x04' + (1700000000).to_bytes(4, 'big') + b'\x16synthetic-ed-key'
SUB = PUB[:5] + b'\x12synthetic-encryption-key'
PRIMARY = hashlib.sha1(b'\x99' + len(PUB).to_bytes(2, 'big') + PUB).hexdigest().upper()
SUBKEY = hashlib.sha1(b'\x99' + len(SUB).to_bytes(2, 'big') + SUB).hexdigest().upper()
UIDS = [b'Synthetic:A', 'Synthetic 中文 B'.encode(), b'Synthetic C']


def signature(kind, created, foreign=False, extra=b''):
    hashed = subpacket(2, created.to_bytes(4, 'big')) + extra
    issuer = p.OLD if foreign else PRIMARY
    unhashed = subpacket(16, bytes.fromhex(issuer[-16:]))
    return bytes([4, kind, 17 if foreign else 22, 2 if foreign else 8]) + len(hashed).to_bytes(2, 'big') + hashed + \
        len(unhashed).to_bytes(2, 'big') + unhashed + b'\x12\x34\x00\x08\x71'


def raw_key(foreign=True, order=(0, 1, 2)):
    raw = packet(6, PUB)
    for i in order:
        raw += packet(13, UIDS[i]) + packet(2, signature(0x13, 1700000100 + i))
        if foreign:
            raw += packet(2, signature(0x10, 1700000200 + i, foreign=True))
    return raw + packet(14, SUB) + packet(2, signature(0x18, 1700000000))


def colons(order=(0, 1, 2)):
    text = f'pub:-:255:22:{PRIMARY[-16:]}:1700000000::::::scSC:\nfpr:::::::::{PRIMARY}:\n'
    for i in order:
        uid = UIDS[i].decode().replace(':', '\\x3a')
        text += f'uid:-::::{1700000100 + i}::::{uid}:::\n'
        text += f'sig:!::22:{PRIMARY[-16:]}:{1700000100 + i}:::::13x::{PRIMARY}:::8:\n'
    text += f'sub:-:255:18:{SUBKEY[-16:]}:1700000000::::::e:\nfpr:::::::::{SUBKEY}:\n'
    text += f'sig:!::22:{PRIMARY[-16:]}:1700000000:::::18x::{PRIMARY}:::8:\n'
    return text.encode()


def result(status, code=0, **changes):
    return {'failure': None, 'returncode': code, 'stdout': b'', 'stderr': b'synthetic diagnostic\n',
            'status': status.encode() if isinstance(status, str) else status, **changes}


def good():
    return (f'[GNUPG:] NEWSIG\n[GNUPG:] KEY_CONSIDERED {p.PRIMARY} 0\n'
            f'[GNUPG:] SIG_ID synthetic 2025-03-20 1742462545\n'
            f'[GNUPG:] GOODSIG {p.PRIMARY[-16:]} Synthetic\n'
            f'[GNUPG:] VALIDSIG {p.PRIMARY} 2025-03-20 1742462545 0 4 0 22 8 00 {p.PRIMARY}\n'
            '[GNUPG:] TRUST_UNDEFINED 0 pgp\n')


def missing():
    return (f'[GNUPG:] NEWSIG\n[GNUPG:] ERRSIG {p.PRIMARY[-16:]} 22 8 00 1742462545 9 {p.PRIMARY}\n'
            f'[GNUPG:] NO_PUBKEY {p.PRIMARY[-16:]}\n')


class MaterialChecks(unittest.TestCase):
    def setUp(self):
        for name, value in [('PRIMARY', PRIMARY), ('SUBKEY', SUBKEY)]:
            handle = patch.object(p, name, value)
            handle.start()
            self.addCleanup(handle.stop)

    def verify(self, raw=None, filtered=None, listing=None):
        return p.certifications(colons() if listing is None else listing, raw_key() if raw is None else raw,
                                raw_key(False) if filtered is None else filtered, NOW)

    def test_all_three_uids_and_encryption_binding(self):
        row = self.verify()
        self.assertEqual((row['uid_count'], row['self_certifications'], row['excluded_foreign_certifications']), (3, 4, 3))
        self.assertFalse(row['cryptography_executed_by_parser'])

    def test_import_may_reorder_uids_but_preserves_context(self):
        self.verify(filtered=raw_key(False, (2, 0, 1)), listing=colons((2, 0, 1)))

    def test_dropped_self_certification_is_rejected(self):
        changed = raw_key(False).replace(packet(2, signature(0x13, 1700000101)), b'')
        with self.assertRaises(ValueError):
            self.verify(filtered=changed)

    def test_changed_self_signature_value_is_rejected(self):
        original = signature(0x13, 1700000101)
        changed = raw_key(False).replace(original, original[:-1] + b'X')
        with self.assertRaisesRegex(ValueError, 'changed original'):
            self.verify(filtered=changed)

    def test_same_counts_with_uid_reassigned_certification_is_rejected(self):
        a, b = signature(0x13, 1700000100), signature(0x13, 1700000101)
        changed = raw_key(False).replace(a, b'SENTINEL').replace(b, a).replace(b'SENTINEL', b)
        with self.assertRaisesRegex(ValueError, 'reassigned'):
            self.verify(filtered=changed)

    def test_foreign_sha1_cannot_become_self_or_remain_in_filtered(self):
        with self.assertRaises(ValueError):
            self.verify(filtered=raw_key())
        changed = raw_key().replace(bytes([4, 19, 22, 8]), bytes([4, 19, 22, 2]))
        with self.assertRaises(ValueError):
            self.verify(raw=changed)

    def test_revocation_cannot_be_hidden_by_import(self):
        for kind in (0x20, 0x28, 0x30):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.verify(raw=raw_key() + packet(2, signature(kind, 1700000300)))

    def test_expiry_or_algorithm_changes_are_outside_fixed_profile(self):
        original = signature(0x13, 1700000100)
        for extra in (subpacket(3, b'\0\0\0\1'), subpacket(9, b'\0\0\0\1')):
            with self.assertRaises(ValueError):
                self.verify(raw=raw_key().replace(original, signature(0x13, 1700000100, extra=extra)))
        with self.assertRaises(ValueError):
            self.verify(raw=raw_key().replace(bytes([4, 19, 22, 8]), bytes([4, 19, 17, 8])))

    def test_extra_key_duplicate_uid_or_missing_subkey_rejected(self):
        for changed in [raw_key() + packet(6, PUB), raw_key(order=(0, 0, 2)),
                        raw_key().split(packet(14, SUB))[0]]:
            with self.assertRaises(ValueError):
                self.verify(raw=changed)

    def test_colons_cannot_replace_uid_or_move_signature(self):
        for changed in [colons().replace(b'Synthetic C', b'Synthetic D'),
                        colons().replace(b'1700000100', b'1700000101'),
                        colons().replace(b':13x:', b':18x:', 1)]:
            with self.subTest(listing=changed), self.assertRaises(ValueError):
                self.verify(listing=changed)

    def test_bad_missing_duplicate_or_foreign_colon_signature(self):
        lines = colons().splitlines(keepends=True)
        for changed in [colons().replace(b'sig:!', b'sig:?'), colons().replace(b':::8:', b':::2:'),
                        b''.join(lines[:3] + lines[4:]), colons() + lines[3],
                        colons().replace(PRIMARY.encode(), p.OLD.encode())]:
            with self.assertRaises(ValueError):
                self.verify(listing=changed)

    def test_expired_revoked_disabled_future_subjects(self):
        for changed in [colons().replace(b'uid:-:', b'uid:e:', 1), colons().replace(b'pub:-:', b'pub:r:', 1),
                        colons().replace(b':scSC:', b':scSCD:'),
                        colons().replace(b':1700000100:', b':1900000100:'),
                        colons().replace(b':1700000000:', b':1700000000:1780000000', 1)]:
            with self.assertRaises(ValueError):
                self.verify(listing=changed)

    def test_uid_escapes_are_decoded_strictly(self):
        self.assertEqual(p.unescape_uid(r'A\x3aB\\C'), b'A:B\\C')
        for value in ['A\\', r'A\x0', r'A\xZZ', r'A\q']:
            with self.assertRaises(ValueError):
                p.unescape_uid(value)

    def test_truncated_secret_oversized_and_unexpected_records(self):
        for raw in [b'', raw_key()[:-1], packet(5, PUB), b'x' * (1024**2 + 1)]:
            with self.assertRaises(ValueError):
                self.verify(raw=raw)
        for listing in [colons()[:-1], colons().replace(b'\n', b'\r\n'), colons() + b'unknown:\n',
                        colons() + b'x' * 8193 + b'\n']:
            with self.assertRaises(ValueError):
                self.verify(listing=listing)


class StatusChecks(unittest.TestCase):
    def test_fixed_detached_signature(self):
        self.assertEqual(p.verify(result(good()), NOW)['result'], 'signature-status-matched')

    def test_wrong_signer_class_algorithm_date_or_expiration_rejected(self):
        for changed in [good().replace(p.PRIMARY, p.OLD), good().replace('22 8 00', '22 2 00'),
                        good().replace('22 8 00', '17 8 00'), good().replace('22 8 00', '22 8 01'),
                        good().replace(' 0 4 0', ' 1800000000 4 0'),
                        good().replace('2025-03-20', '2025-03-21')]:
            with self.assertRaises(ValueError):
                p.verify(result(changed), NOW)

    def test_failures_unknown_and_additional_groups_cannot_hide_in_success(self):
        for suffix in ['NEWSIG', 'FAILURE verify 1', 'ERROR verify 1', 'EXPSIG 123 Synthetic',
                       'REVKEYSIG 123 Synthetic', 'FUTURE_STATUS', 'TRUST_FULLY 0 pgp']:
            with self.assertRaises(ValueError):
                p.verify(result(good() + '[GNUPG:] ' + suffix + '\n'), NOW)

    def test_missing_duplicate_or_reordered_positive_record(self):
        lines = good().splitlines(keepends=True)
        for changed in [''.join(lines[:2] + lines[3:]), good() + lines[3], good() + lines[4],
                        ''.join(lines[:3] + [lines[4], lines[3]] + lines[5:])]:
            with self.assertRaises(ValueError):
                p.verify(result(changed), NOW)

    def test_capture_exit_and_stdout_must_match(self):
        for changes in [{'failure': 'deadline'}, {'returncode': 2}, {'returncode': False}, {'stdout': b'wrong'}]:
            with self.assertRaises(ValueError):
                p.verify(result(good(), **changes), NOW)
        with self.assertRaises(ValueError):
            p.verify(result(good()), p.CREATED - 1)

    def test_tamper_requires_target_badsig(self):
        raw = f'[GNUPG:] NEWSIG\n[GNUPG:] KEY_CONSIDERED {p.PRIMARY} 0\n[GNUPG:] BADSIG {p.PRIMARY[-16:]} Synthetic\n'
        p.verify(result(raw, 1), NOW, 'tampered-body')
        for changed in [raw.replace(p.PRIMARY[-16:], p.OLD[-16:]), raw + good(), missing(),
                        raw.replace('BADSIG', 'GOODSIG')]:
            with self.assertRaises(ValueError):
                p.verify(result(changed, 1), NOW, 'tampered-body')

    def test_wrong_and_missing_primary_need_precise_missing_key_error(self):
        for case in ('wrong-primary', 'missing-primary'):
            p.verify(result(missing(), 2), NOW, case)
            for changed in [missing().replace(' 9 ', ' 4 '), missing().replace(p.PRIMARY, p.OLD),
                            missing().split('[GNUPG:] NO_PUBKEY')[0],
                            missing() + '[GNUPG:] FAILURE open 1\n', missing() + good()]:
                with self.assertRaises(ValueError):
                    p.verify(result(changed, 2), NOW, case)

    def test_negative_timeout_signal_or_success_exit_is_not_rejection(self):
        for changes in [{'returncode': 0}, {'returncode': 137}, {'failure': 'stdout-limit'}]:
            with self.assertRaises(ValueError):
                p.verify(result(missing(), 2, **changes), NOW, 'missing-primary')


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
        self.assertTrue(report['name'].startswith('rax-mpfr-verify-'))
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
            with patch.object(run.inputs, 'HERE', root):
                self.assertEqual(run.inputs.read_store(root, 'synthetic', 'reviewed.json', run.identity(raw)['sha256'])[0],
                                 {'synthetic.bin': data})
                (store / 'objects' / row['sha256']).write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'corruption'):
                    run.inputs.read_store(root, 'synthetic', 'reviewed.json', run.identity(raw)['sha256'])

    def test_cumulative_input_bound_and_readonly_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve()
            for i in range(3):
                run.inputs.write_new(folder / str(i), b'x' * 1505596)
            with self.assertRaisesRegex(ValueError, 'cumulative'):
                run.inputs.snapshot(folder)
            (folder / '0').chmod(0o644)
            with self.assertRaisesRegex(ValueError, 'mode drift'):
                run.inputs.snapshot(folder)

    def test_method_inventory_includes_deferred_rootfs_reader(self):
        methods = run.methods()
        for name in ('run-mpfr-verification.py', 'prepare-mpfr-verification.py', 'inspect-mpfr-verification.py',
                     'inspect-musl-verifier-rootfs.py', 'run-musl-verifier-smoke.py'):
            self.assertIn('docs/records/rust-linux-input-review/' + name, methods)

    def test_default_plan_does_not_construct_docker(self):
        with patch.object(run.smoke, 'Docker', side_effect=AssertionError('unexpected Docker')):
            plan = run.plan()
        self.assertEqual(list(plan['commands']), ['filter', 'certifications', 'verify', 'tampered-body',
                                                 'wrong-primary', 'missing-primary'])
        self.assertFalse(plan['actions_executed'])
        completed = subprocess.run([sys.executable, str(HERE / 'run-mpfr-verification.py')],
                                   capture_output=True, check=True, timeout=5)
        self.assertEqual(json.loads(completed.stdout), plan)


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
