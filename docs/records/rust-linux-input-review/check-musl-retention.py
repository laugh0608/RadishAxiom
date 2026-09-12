#!/usr/bin/env python3
"""Local synthetic retention corruption, path and overwrite checks."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('retention', Path(__file__).with_name('retain-musl-verifier-inputs.py'))
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)


class Retention(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        for name in ['a', 'b']:
            (self.source / name).write_bytes(b'abc')
        self.manifest = {'kind': 'diagnostic-musl-retention-manifest-v1',
                         'files': [{'path': name, **retention.identity(b'abc')} for name in ['a', 'b']]}
        self.raw = json.dumps(self.manifest).encode()
        self.store = self.root / 'store'
        self.restored = self.root / 'restored'

    def tearDown(self):
        self.temporary.cleanup()

    def test_restore_without_originals_and_deduplicate(self):
        result = retention.pack(self.source, self.raw, self.store)
        self.assertEqual(result['object_count'], 1)
        (self.source / 'a').unlink()
        (self.source / 'b').unlink()
        result = retention.restore(self.store, self.raw, self.restored)
        self.assertTrue(result['restored_bytes_match'])
        self.assertFalse(result['off_device_backup_verified'])
        self.assertEqual((self.restored / 'a').read_bytes(), b'abc')

    def test_corrupted_object_rejected_before_restore(self):
        retention.pack(self.source, self.raw, self.store)
        next((self.store / 'objects').iterdir()).write_bytes(b'abd')
        with self.assertRaises(ValueError):
            retention.restore(self.store, self.raw, self.restored)
        self.assertFalse(self.restored.exists())

    def test_source_drift_does_not_create_store(self):
        (self.source / 'b').write_bytes(b'bad')
        with self.assertRaises(ValueError):
            retention.pack(self.source, self.raw, self.store)
        self.assertFalse(self.store.exists())

    def test_unsafe_duplicate_and_ancestor_paths(self):
        for paths in [['../a'], ['/a'], ['a/../b'], ['.git/config'], ['a', 'a'], ['a', 'a/b']]:
            raw = json.dumps({**self.manifest, 'files': [
                {'path': p, **retention.identity(b'abc')} for p in paths]}).encode()
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                retention.manifest_rows(raw)

    def test_symlink_source_and_destination_rejected(self):
        (self.source / 'a').unlink()
        (self.source / 'a').symlink_to(self.source / 'b')
        with self.assertRaises(ValueError):
            retention.pack(self.source, self.raw, self.store)
        (self.source / 'a').unlink()
        (self.source / 'a').write_bytes(b'abc')
        alias = self.root / 'alias'
        alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ValueError):
            retention.pack(self.source, self.raw, alias / 'new-store')

    def test_existing_destination_never_overwritten(self):
        retention.pack(self.source, self.raw, self.store)
        with self.assertRaises(FileExistsError):
            retention.pack(self.source, self.raw, self.store)
        self.restored.mkdir()
        (self.restored / 'keep').write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            retention.restore(self.store, self.raw, self.restored)
        self.assertEqual((self.restored / 'keep').read_bytes(), b'keep')

    def test_changed_manifest_and_extra_object_rejected(self):
        retention.pack(self.source, self.raw, self.store)
        with self.assertRaises(ValueError):
            retention.restore(self.store, self.raw + b' ', self.restored)
        (self.store / 'objects' / ('0' * 64)).write_bytes(b'extra')
        with self.assertRaises(ValueError):
            retention.restore(self.store, self.raw, self.restored)


if __name__ == '__main__':
    unittest.main()
