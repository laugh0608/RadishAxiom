#!/usr/bin/env python3
"""Synthetic boundary checks; no network, GnuPG or upstream execution."""
import base64
import gzip
import importlib.util
import io
import json
import lzma
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('inputs', HERE / 'inspect-mpc-mpfr-inputs.py')
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)


def synthetic_tar(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:') as tar:
        for name, data, kind in entries:
            member = tarfile.TarInfo(name)
            member.type, member.size = kind, len(data)
            if kind == tarfile.SYMTYPE:
                member.linkname = '/outside'
            tar.addfile(member, io.BytesIO(data))
    return stream.getvalue()


def signature(digest=8, kind=0, issuer=None):
    hashed = b'\x05\x02\x00\x00\x00\x01' + b'\x16\x21\x04' + b'\x11' * 20
    unhashed = b'' if issuer is None else b'\x09\x10' + issuer
    body = bytes([4, kind, 17, digest]) + len(hashed).to_bytes(2, 'big') + hashed
    body += len(unhashed).to_bytes(2, 'big') + unhashed + b'\x00\x00\x00\x01\x01\x00\x01\x01'
    return bytes([0xc2, len(body)]) + body


class SourceBoundaryTests(unittest.TestCase):
    def test_valid_inventory(self):
        raw = synthetic_tar([('fixture/README', b'synthetic', tarfile.REGTYPE)])
        result, texts = inputs.inventory(raw, 'fixture', {'README'})
        self.assertEqual(result['file_count'], 1)
        self.assertEqual(texts, {'README': 'synthetic'})
        self.assertFalse(result['physical_tar_profile_verified'])

    def test_traversal(self):
        with self.assertRaises(ValueError):
            inputs.inventory(synthetic_tar([('fixture/../escape', b'x', tarfile.REGTYPE)]), 'fixture', set())

    def test_symlink(self):
        with self.assertRaises(ValueError):
            inputs.inventory(synthetic_tar([('fixture/link', b'', tarfile.SYMTYPE)]), 'fixture', set())

    def test_duplicate(self):
        entry = ('fixture/a', b'x', tarfile.REGTYPE)
        with self.assertRaises(ValueError):
            inputs.inventory(synthetic_tar([entry, entry]), 'fixture', set())

    def test_missing_review_file(self):
        with self.assertRaises(ValueError):
            inputs.inventory(synthetic_tar([]), 'fixture', {'COPYING'})

    def test_nonzero_tail(self):
        with self.assertRaises(ValueError):
            inputs.inventory(synthetic_tar([]) + b'X', 'fixture', set())

    def test_member_limit(self):
        with patch.object(inputs, 'MAX_MEMBER', 2), self.assertRaises(ValueError):
            inputs.inventory(synthetic_tar([('fixture/a', b'abc', tarfile.REGTYPE)]), 'fixture', set())

    def test_compression_roundtrip(self):
        for encoding, compressed in [('gz', gzip.compress(b'fixture')), ('xz', lzma.compress(b'fixture'))]:
            self.assertEqual(inputs.unpack(compressed, encoding), b'fixture')

    def test_concatenation_and_truncation(self):
        for encoding, compressed in [('gz', gzip.compress(b'fixture')), ('xz', lzma.compress(b'fixture'))]:
            for changed in (compressed + compressed, compressed[:-1], compressed + b'x'):
                with self.subTest(encoding=encoding, size=len(changed)), self.assertRaises(ValueError):
                    inputs.unpack(changed, encoding)

    def test_expansion_limit(self):
        for encoding, compressed in [('gz', gzip.compress(b'x' * 100)), ('xz', lzma.compress(b'x' * 100))]:
            with patch.object(inputs, 'MAX_TAR', 32), self.assertRaises(ValueError):
                inputs.unpack(compressed, encoding)


class SignatureBoundaryTests(unittest.TestCase):
    def test_declared_metadata_not_verification(self):
        result = inputs.signature_metadata(signature())
        self.assertEqual(result['declared_issuer'], '11' * 20)
        self.assertEqual(result['source_acceptance'], 'not-assessed')
        self.assertFalse(result['cryptography_executed'])
        self.assertFalse(result['signature_mpis_verified'])

    def test_weak_digest(self):
        with self.assertRaises(ValueError):
            inputs.signature_metadata(signature(digest=2))

    def test_non_document_signature(self):
        with self.assertRaises(ValueError):
            inputs.signature_metadata(signature(kind=0x13))

    def test_issuer_disagreement(self):
        with self.assertRaises(ValueError):
            inputs.signature_metadata(signature(issuer=b'\x22' * 8))

    def test_duplicate_or_truncated_packet(self):
        for data in (signature() * 2, signature()[:-1]):
            with self.assertRaises(ValueError):
                inputs.signature_metadata(data)

    def test_wrong_armor_crc(self):
        armored = b'-----BEGIN PGP SIGNATURE-----\n\n' + base64.b64encode(signature())
        armored += b'\n=AAAA\n-----END PGP SIGNATURE-----\n'
        with self.assertRaisesRegex(ValueError, 'CRC'):
            inputs.signature_metadata(armored)


class FetchFailureTests(unittest.TestCase):
    def test_timeout_is_recorded(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(inputs.fetch, 'DIRECTORY', Path(folder).resolve()), \
                patch.object(inputs.fetch.subprocess, 'run', side_effect=subprocess.TimeoutExpired('synthetic', 65)):
            self.assertEqual(inputs.fetch.fetch('mpc-signature', 1), 1)
            record = json.loads((Path(folder) / 'mpc-signature-attempt-1.json').read_bytes())
            self.assertTrue(record['parent_timeout'])
            self.assertFalse(record['passed'])
            with self.assertRaises(ValueError):
                inputs.fetch.fetch('mpc-signature', 2)

    def test_refuse_existing_attempt(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(inputs.fetch, 'DIRECTORY', Path(folder).resolve()), \
                patch.object(inputs.fetch.subprocess, 'run') as run:
            (Path(folder) / 'mpc-signature-attempt-1.json').write_text('synthetic')
            with self.assertRaises(ValueError):
                inputs.fetch.fetch('mpc-signature', 1)
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
