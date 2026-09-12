#!/usr/bin/env python3
"""Synthetic capability filtering and tar assembly checks; no daemon or real payload execution."""
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


capabilities = load('capabilities', 'inspect-musl-verifier-capabilities.py')
rootfs = load('rootfs', 'prepare-musl-verifier-rootfs.py')
readback = load('readback', 'inspect-musl-verifier-rootfs.py')


class Preflight(unittest.TestCase):
    def rows(self):
        return [{'path': '.', 'type': 'directory', 'mode': 0o755, 'uid': 0, 'gid': 0, 'packages': []},
                {'path': 'data', 'type': 'file', 'mode': 0o644, 'uid': 0, 'gid': 0,
                 'packages': [], **rootfs.identity(b'abc')},
                {'path': 'alias', 'type': 'symlink', 'mode': 0o777, 'uid': 0, 'gid': 0,
                 'packages': [], 'target': 'data', 'destination': 'data'}]

    def test_whitelist_and_absence_are_explicit(self):
        result = capabilities.select_fields({'MemoryLimit': False, 'SwapLimit': None,
            'HttpProxy': 'synthetic-private-setting'}, {'MemoryLimit': bool, 'SwapLimit': bool, 'PidsLimit': bool})
        self.assertEqual(result['selected_fields'], {'MemoryLimit': False})
        self.assertEqual(result['absent_fields'], ['SwapLimit', 'PidsLimit'])

    def test_type_and_control_characters_rejected(self):
        for value in [1, 'true']:
            with self.assertRaises(ValueError):
                capabilities.select_fields({'MemoryLimit': value}, {'MemoryLimit': bool})
        for value in ['x\ny', 'x' * 513]:
            with self.assertRaises(ValueError):
                capabilities.select_fields({'Version': value}, {'Version': str})
        with self.assertRaises(ValueError):
            capabilities.select_fields({'SecurityOptions': [False]}, {'SecurityOptions': list})

    def test_unapproved_endpoint_rejected_before_connect(self):
        with self.assertRaises(ValueError):
            capabilities.query(Path('/no-socket'), '/containers/json', {})

    def test_synthetic_tar_content_metadata_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve() / 'synthetic.tar'
            rootfs.assemble(self.rows(), {'data': b'abc'}, output)
            raw = output.read_bytes()
            with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
                self.assertEqual(archive.extractfile('data').read(), b'abc')
                self.assertEqual(archive.getmember('data').mode, 0o644)
                self.assertEqual(archive.getmember('alias').linkname, 'data')
                self.assertTrue(all(m.uid == 0 and m.gid == 0 and m.mtime == 0 for m in archive))
            with self.assertRaises(FileExistsError):
                rootfs.assemble(self.rows(), {'data': b'abc'}, output)
            self.assertEqual(output.read_bytes(), raw)

    def test_wrong_bytes_and_unlisted_bytes_rejected(self):
        for files in [{'data': b'abd'}, {'data': b'abc', 'extra': b'x'}]:
            with self.assertRaises(ValueError):
                rootfs.validate_rows(self.rows(), files)

    def test_duplicate_unsafe_or_privileged_entry_rejected(self):
        for field, value in [('path', '../escape'), ('path', 'data/child'), ('mode', 0o4755), ('uid', 1)]:
            rows = self.rows()
            rows[2][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                rootfs.validate_rows(rows, {'data': b'abc'})
        rows = self.rows()
        with self.assertRaises(ValueError):
            rootfs.validate_rows(rows + [dict(rows[1])], {'data': b'abc'})

    def test_link_escape_and_missing_target_rejected(self):
        for target in ['../escape', 'missing']:
            rows = self.rows()
            rows[2].update(target=target, destination=target)
            with self.assertRaises(ValueError):
                rootfs.validate_rows(rows, {'data': b'abc'})

    def readback_fixture(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve() / 'synthetic.tar'
            rows = self.rows()
            rootfs.assemble(rows, {'data': b'abc'}, output)
            return output.read_bytes(), {'entries': rows, 'entry_count': 3, 'file_bytes': 3}

    def test_readback_matches_and_rejects_payload_corruption(self):
        raw, plan = self.readback_fixture()
        self.assertEqual(readback.inspect(raw, plan)['result'], 'matched-reviewed-plan')
        changed = bytearray(raw)
        changed[1024] ^= 1
        with self.assertRaisesRegex(ValueError, 'file identity mismatch'):
            readback.inspect(bytes(changed), plan)

    def test_readback_rejects_metadata_link_and_missing_entry(self):
        for field, value in [('mode', 0o600), ('uid', 1000), ('target', 'elsewhere'), ('type', 'file')]:
            raw, plan = self.readback_fixture()
            plan['entries'][2 if field in {'target', 'type'} else 1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                readback.inspect(raw, plan)
        raw, plan = self.readback_fixture()
        plan['entries'].append({'path': 'missing'})
        plan['entry_count'] += 1
        with self.assertRaisesRegex(ValueError, 'missing entries'):
            readback.inspect(raw, plan)

    def test_readback_rejects_header_tail_padding_and_duplicate(self):
        raw, plan = self.readback_fixture()
        for position in [0, 1027, len(raw) - 1]:
            changed = bytearray(raw)
            changed[position] ^= 1
            with self.subTest(position=position), self.assertRaises((ValueError, tarfile.TarError)):
                readback.inspect(bytes(changed), plan)
        for changed in [raw[:2048], raw[:2048] + raw[:512] + raw[2048:]]:
            with self.assertRaises(ValueError):
                readback.inspect(changed, plan)


if __name__ == '__main__':
    unittest.main()
