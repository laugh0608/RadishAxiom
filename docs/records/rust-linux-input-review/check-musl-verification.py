#!/usr/bin/env python3
"""Synthetic status and staging boundary checks; no container or cryptographic execution."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def load(filename):
    spec = importlib.util.spec_from_file_location(filename, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


status = load('inspect-musl-verification-status.py')
inputs = load('prepare-musl-verification-inputs.py')
NOW = 1790000000


def group(primary):
    signer, algorithm = status.SIGNERS[primary]
    return ('[GNUPG:] NEWSIG\n'
            f'[GNUPG:] KEY_CONSIDERED {primary} 0\n'
            '[GNUPG:] SIG_ID SyntheticSignature 2026-07-11 1783760580\n'
            f'[GNUPG:] GOODSIG {signer[-16:]} Synthetic public test key\n'
            f'[GNUPG:] VALIDSIG {signer} 2026-07-11 1783760580 0 4 0 {algorithm} 8 01 {primary}\n'
            '[GNUPG:] TRUST_UNDEFINED 0 pgp\n')


def stream():
    return group(status.ARCHIVE) + group(status.RELEASE)


class SignatureStatus(unittest.TestCase):
    def verify(self, text, **kwargs):
        return status.verify(text.encode() if isinstance(text, str) else text,
                             exit_code=kwargs.get('exit_code', 0), observed_at=kwargs.get('observed_at', NOW),
                             failure=kwargs.get('failure'))

    def test_both_required_roles(self):
        actual = self.verify(stream())
        self.assertEqual(set(actual['signatures']), status.REQUIRED)
        self.assertEqual(actual['source_acceptance'], 'not-assessed')
        self.assertFalse(actual['cross_certification_assessed'])

    def test_optional_bookworm_does_not_replace_missing_role(self):
        other = next(primary for primary in status.SIGNERS if primary not in status.REQUIRED)
        self.assertEqual(len(self.verify(group(other) + stream())['signatures']), 3)
        for primary in status.REQUIRED:
            with self.assertRaises(ValueError):
                self.verify(group(other) + group(primary))

    def test_wrong_signer_for_right_primary_is_rejected(self):
        original = status.SIGNERS[status.ARCHIVE][0]
        for changed in ['0' * 40, status.ARCHIVE, status.RELEASE]:
            with self.subTest(signer=changed), self.assertRaises(ValueError):
                self.verify(stream().replace(original, changed))

    def test_bad_expired_revoked_and_unknown_statuses(self):
        for token in status.FAILURES | {'UNKNOWN_NEW_STATUS', 'TRUST_FULLY'}:
            with self.subTest(token=token), self.assertRaises(ValueError):
                self.verify(stream() + f'[GNUPG:] {token} synthetic\n')

    def test_exit_and_collector_failures_override_valid_status(self):
        for options in [{'exit_code': 1}, {'exit_code': -6}, {'exit_code': True},
                        {'failure': 'deadline'}, {'failure': 'stdout-limit'}, {'failure': 'log-write-failure'}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.verify(stream(), **options)

    def test_duplicate_missing_and_unpaired_groups(self):
        for text in [group(status.ARCHIVE), stream() + group(status.ARCHIVE),
                     stream() + '[GNUPG:] NEWSIG\n', stream().replace('[GNUPG:] NEWSIG\n', '', 1),
                     '\n'.join(line for line in stream().splitlines() if 'GOODSIG' not in line) + '\n',
                     '\n'.join(line for line in stream().splitlines() if 'VALIDSIG' not in line) + '\n']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.verify(text)

    def test_good_and_valid_signature_key_ids_must_agree(self):
        good = status.SIGNERS[status.ARCHIVE][0][-16:]
        with self.assertRaises(ValueError):
            self.verify(stream().replace('GOODSIG ' + good, 'GOODSIG ' + '0' * 16))

    def test_strong_algorithm_class_and_v4_boundaries(self):
        for old, new in [(' 8 01 ', ' 2 01 '), (' 8 01 ', ' 8 00 '), (' 4 0 1 ', ' 5 0 1 '),
                         (' 4 0 1 ', ' 4 1 1 '), (' 4 0 22 ', ' 4 0 1 ')]:
            with self.subTest(new=new), self.assertRaises(ValueError):
                self.verify(stream().replace(old, new))

    def test_dates_expiration_and_future_signature(self):
        for text in [stream().replace('2026-07-11', '2026-07-12'),
                     stream().replace('1783760580', str(NOW + 1)),
                     stream().replace(' 0 4 0 ', f' {NOW} 4 0 '),
                     stream().replace(' 0 4 0 ', ' 1 4 0 ')]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.verify(text)

    def test_sig_id_time_and_considered_key_context(self):
        for text in [stream().replace('SyntheticSignature 2026-07-11 1783760580',
                                     'SyntheticSignature 2026-07-11 1783760581'),
                     stream().replace('KEY_CONSIDERED ' + status.ARCHIVE, 'KEY_CONSIDERED ' + status.RELEASE),
                     stream().replace(status.ARCHIVE + ' 0\n', status.ARCHIVE + ' 2\n')]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.verify(text)

    def test_trust_is_annotation_and_plaintext_is_bounded(self):
        self.assertEqual(self.verify('[GNUPG:] PLAINTEXT 74 0 \n' + stream())['result'],
                         'required-role-statuses-matched')
        self.verify(stream().replace('[GNUPG:] TRUST_UNDEFINED 0 pgp\n', ''))
        for text in [stream() + '[GNUPG:] PLAINTEXT 74 0 \n',
                     stream().replace('TRUST_UNDEFINED 0 pgp', 'TRUST_UNDEFINED 1 pgp'),
                     '[GNUPG:] PLAINTEXT 62 0 hidden\n' + stream()]:
            with self.assertRaises(ValueError):
                self.verify(text)

    def test_stream_bounds_and_nonstatus_text(self):
        for text in ['', stream().rstrip('\n'), stream().replace('\n', '\r\n'),
                     stream() + 'gpg: human diagnostic\n', stream() + '\x00\n',
                     '[GNUPG:] NEWSIG ' + 'x' * 8192 + '\n', b'x' * (1024**2 + 1),
                     b'\xff\n', '[GNUPG:] NEWSIG\n' * 4097]:
            with self.subTest(size=len(text)), self.assertRaises(ValueError):
                self.verify(text)

    def test_only_lf_separates_status_records(self):
        for separator in ['\u0085', '\u2028', '\u2029']:
            with self.subTest(separator=repr(separator)), self.assertRaises(ValueError):
                self.verify(stream().replace('\n', separator, 1))


class Staging(unittest.TestCase):
    def files(self):
        return {name: b'synthetic public bytes' for name in [*inputs.DIRECT, 'debian-archive-keyring.gpg']}

    def test_four_files_readonly_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary).resolve() / 'inputs'
            files = self.files()
            inputs.stage(target, files)
            self.assertEqual({path.name for path in target.iterdir()}, set(files))
            for name, raw in files.items():
                self.assertEqual((target / name).read_bytes(), raw)
                self.assertEqual((target / name).stat().st_mode & 0o777, 0o444)
            with self.assertRaises(FileExistsError):
                inputs.stage(target, files)

    def test_extra_or_missing_filename_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary).resolve() / 'inputs'
            for files in [{**self.files(), '../escape': b'x'}, {'InRelease': b'x'}]:
                with self.assertRaises(ValueError):
                    inputs.stage(target, files)
                self.assertFalse(target.exists())

    def test_symlink_parent_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'alias').symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                inputs.stage(root / 'alias' / 'inputs', self.files())


if __name__ == '__main__':
    unittest.main()
