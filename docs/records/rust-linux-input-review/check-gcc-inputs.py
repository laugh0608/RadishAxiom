#!/usr/bin/env python3
"""Synthetic checksum/link and single-request recovery boundaries; no network calls."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load('inspect-gcc-inputs.py')
recovery = load('fetch-gcc-archive-recovery.py')


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.archive, self.signature = b'synthetic archive', b'synthetic signature'
        self.entries = {name: hashlib.sha512(self.signature if name.endswith('.sig') else self.archive).hexdigest()
                        for name in ('gcc-9.4.0.tar.gz', 'gcc-9.4.0.tar.gz.sig',
                                     'gcc-9.4.0.tar.xz', 'gcc-9.4.0.tar.xz.sig')}
        self.raw = ''.join(digest + '  ' + name + '\n' for name, digest in self.entries.items()).encode()

    def test_exact_release_entries(self):
        self.assertEqual(m.checksum_entries(self.raw), self.entries)

    def test_missing_duplicate_or_variant(self):
        for raw in (self.raw.split(b'\n', 1)[1], self.raw + self.raw.splitlines()[0] + b'\n',
                    self.raw.replace(b'9.4.0', b'9.5.0'), self.raw.replace(b'.tar.xz\n', b'.tar.xz.sig\n')):
            with self.assertRaises(ValueError):
                m.checksum_entries(raw)

    def test_encoding_bound_and_malformed(self):
        for raw in (b'', b'x' * 65537, b'\xff', self.raw.replace(b'  ', b' ')):
            with self.assertRaises((ValueError, UnicodeError)):
                m.checksum_entries(raw)

    def test_bindings_and_tampering(self):
        with patch.object(m, 'RECIPE_SHA1', hashlib.sha1(self.archive).hexdigest()):
            result = m.verify_bindings(self.archive, self.signature, self.raw)
            self.assertEqual(result['archive'], m.identity(self.archive))
            for archive, signature in ((self.archive + b'X', self.signature),
                                       (self.archive, self.signature + b'X')):
                with self.assertRaisesRegex(ValueError, 'SHA-512'):
                    m.verify_bindings(archive, signature, self.raw)
        with self.assertRaisesRegex(ValueError, 'recipe SHA-1'):
            m.verify_bindings(self.archive, self.signature, self.raw)

    def test_directory_exact_links(self):
        raw = b'<a href="sha512.sum">sum</a><a href="gcc-9.4.0.tar.xz">xz</a><a href="gcc-9.4.0.tar.xz.sig">sig</a>'
        m.directory_links(raw)
        for changed in (raw.replace(b'9.4.0', b'9.5.0'), raw.replace(b'href="sha512', b'href="https://example.invalid/sha512'),
                        b'\xff', b'x' * 262145):
            with self.assertRaises((ValueError, UnicodeError)):
                m.directory_links(changed)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        self.partial = b'synthetic partial'
        (self.directory / 'gcc-attempt-1.tar.xz').write_bytes(self.partial)
        first = {'url': recovery.TARGET['url'], 'exit_code': 28, 'passed': False,
                 'body': {'file': 'gcc-attempt-1.tar.xz', **m.identity(self.partial)}}
        (self.directory / 'gcc-attempt-1.json').write_text(json.dumps(first))
        self.patch = patch.object(recovery, 'DIRECTORY', self.directory)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def fake_run(self, argv, stdout, stderr, timeout):
        self.assertEqual(timeout, 185)
        self.assertEqual(argv[argv.index('--max-time') + 1], '180')
        self.assertNotIn('--location', argv)
        self.assertNotIn('--retry', argv)
        Path(argv[argv.index('--output') + 1]).write_bytes(b'synthetic complete')
        stdout.write(b'200\n')
        return SimpleNamespace(returncode=0)

    def test_success_preserves_first_and_refuses_repeat(self):
        with patch.object(recovery.subprocess, 'run', side_effect=self.fake_run) as run, patch('builtins.print'):
            self.assertEqual(recovery.execute(), 0)
            self.assertEqual((self.directory / 'gcc-attempt-1.tar.xz').read_bytes(), self.partial)
            result = json.loads((self.directory / 'gcc-attempt-2.json').read_bytes())
            self.assertTrue(result['passed'])
            self.assertEqual(result['source_acceptance'], 'not-assessed')
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                recovery.execute()
            self.assertEqual(run.call_count, 1)

    def test_changed_partial_refused_before_network(self):
        (self.directory / 'gcc-attempt-1.tar.xz').write_bytes(b'changed')
        with patch.object(recovery.subprocess, 'run') as run, self.assertRaises(ValueError):
            recovery.execute()
        run.assert_not_called()

    def test_existing_destination_refused(self):
        (self.directory / 'gcc-attempt-2.stdout').write_bytes(b'keep')
        with patch.object(recovery.subprocess, 'run') as run, self.assertRaises(ValueError):
            recovery.execute()
        run.assert_not_called()

    def test_parent_timeout_recorded(self):
        with patch.object(recovery.subprocess, 'run', side_effect=subprocess.TimeoutExpired('synthetic', 185)), \
                patch('builtins.print'):
            self.assertEqual(recovery.execute(), 1)
        result = json.loads((self.directory / 'gcc-attempt-2.json').read_bytes())
        self.assertTrue(result['parent_timeout'])
        self.assertIsNone(result['exit_code'])
        self.assertFalse(result['passed'])


if __name__ == '__main__':
    unittest.main()
