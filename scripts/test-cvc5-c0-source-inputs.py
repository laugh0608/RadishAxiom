#!/usr/bin/env python3
"""Synthetic positive and adversarial cases; no network or upstream execution."""
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('c0sources', Path(__file__).with_name('cvc5-c0-source-inputs.py'))
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
CHECK_SPEC = importlib.util.spec_from_file_location('c0independent', Path(__file__).with_name('check-cvc5-c0-source-independent.py'))
CHECK = importlib.util.module_from_spec(CHECK_SPEC)
CHECK_SPEC.loader.exec_module(CHECK)


def archive(entries, format=tarfile.PAX_FORMAT):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w', format=format) as stream:
        for name, kind, data in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.mode = 0o4755
            if kind in {tarfile.SYMTYPE, tarfile.LNKTYPE}:
                member.linkname = data.decode()
                data = b''
            member.size = len(data)
            stream.addfile(member, io.BytesIO(data))
    return output.getvalue()


def base(extra=()):
    return [('root', tarfile.DIRTYPE, b''), ('root/data', tarfile.REGTYPE, b'bytes\n')] + list(extra)


def audit(entries, **kwargs):
    raw = archive(entries, **kwargs)
    return MOD.audit_tar(MOD.Reader([raw]))


class Safety(unittest.TestCase):
    def test_valid_files_modes_and_contained_links(self):
        result = audit(base([('root/soft', tarfile.SYMTYPE, b'data'), ('root/hard', tarfile.LNKTYPE, b'root/data')]))
        self.assertEqual(result['type_counts'], {'directory': 1, 'file': 1, 'symlink': 1, 'hardlink': 1})
        self.assertEqual(result['entries'][1]['original_mode'], '4755')
        self.assertEqual(result['entries'][2]['resolved_path'], 'root/data')

    def test_paths_and_cross_platform_aliases_rejected(self):
        for name in ['/outside', 'root/../outside', 'root//alias', 'root/./alias', 'root/new\\x', 'root/new\nx', 'root/data', 'root/DATA']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                audit(base([(name, tarfile.REGTYPE, b'x')]))
        with self.assertRaises(ValueError):
            audit(base([('root/caf\u00e9', tarfile.REGTYPE, b'a'), ('root/cafe\u0301', tarfile.REGTYPE, b'b')]))

    def test_types_links_and_ancestor_rejected(self):
        for kind, name, target in [(tarfile.FIFOTYPE, 'root/fifo', b''), (tarfile.CHRTYPE, 'root/dev', b''),
                                   (tarfile.SYMTYPE, 'root/a', b'../../escape'), (tarfile.SYMTYPE, 'root/a', b'/absolute'),
                                   (tarfile.SYMTYPE, 'root/a', b'missing'), (tarfile.SYMTYPE, 'root/a', b'a'),
                                   (tarfile.LNKTYPE, 'root/hard', b'root/missing'), (tarfile.REGTYPE, 'root/data/child', b'x')]:
            with self.subTest(kind=kind, target=target), self.assertRaises(ValueError):
                audit(base([(name, kind, target)]))
        with self.assertRaises(ValueError):
            audit(base([('root/a', tarfile.SYMTYPE, b'b'), ('root/b', tarfile.SYMTYPE, b'a')]))
        with self.assertRaises(ValueError):
            audit(base([('root/a', tarfile.SYMTYPE, b'../outside'), ('root/b', tarfile.SYMTYPE, b'a')]))

    def test_explicit_budgets_and_truncation(self):
        for key, value in [('entries', 1), ('file_bytes', 2), ('expanded_tar_bytes', 100)]:
            with self.subTest(key=key), patch.dict(MOD.LIMITS, {key: value}), self.assertRaises(ValueError):
                audit(base())
        raw = archive(base())
        with self.assertRaises(ValueError):
            MOD.audit_tar(MOD.Reader([raw[:600]]))
        corrupt = bytearray(raw)
        corrupt[10] ^= 1
        with self.assertRaises(tarfile.HeaderError):
            MOD.audit_tar(MOD.Reader([bytes(corrupt)]))
        with self.assertRaises(ValueError):
            MOD.audit_tar(MOD.Reader([raw + b'not-zero']))

    def test_full_audit_precedes_write_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'archive'
            with tarfile.open(path, 'w:gz') as stream:
                for name, kind, raw in base([('root/link', tarfile.SYMTYPE, b'data')]):
                    info = tarfile.TarInfo(name)
                    info.type, info.mode = kind, 0o4755
                    if kind == tarfile.SYMTYPE:
                        info.linkname, raw = raw.decode(), b''
                    info.size = len(raw)
                    stream.addfile(info, io.BytesIO(raw))
            result = MOD.audit(path)
            destination = Path(temp) / 'tree'
            MOD.materialize(path, result, destination)
            self.assertEqual((destination / 'root/data').stat().st_mode & 0o7777, 0o600)
            self.assertEqual((destination / 'root').stat().st_mode & 0o7777, 0o700)
            self.assertEqual((destination / 'root/link').read_bytes(), b'bytes\n')
            with self.assertRaises(FileExistsError):
                MOD.materialize(path, result, destination)
            self.assertEqual((destination / 'root/data').read_bytes(), b'bytes\n')

    def test_independent_parser_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'archive'
            with tarfile.open(path, 'w:gz') as stream:
                for name, kind, raw in base():
                    info = tarfile.TarInfo(name)
                    info.type, info.mode, info.size = kind, 0o644, len(raw)
                    stream.addfile(info, io.BytesIO(raw))
            result = MOD.audit(path)
            CHECK.verify_archive(path, result)
            result['entries'][1]['sha256'] = '0' * 64
            with self.assertRaises(ValueError):
                CHECK.verify_archive(path, result)

    def test_gnu_and_pax_long_paths(self):
        for format in [tarfile.GNU_FORMAT, tarfile.PAX_FORMAT]:
            name = 'root/' + 'a' * 150
            self.assertTrue(audit(base([(name, tarfile.REGTYPE, b'x')]), format=format)['entries'])

    def test_exact_redirect_policy(self):
        rows = {row['id']: row for row in MOD.inputs()}
        MOD.allowed_urls(rows['cvc5'], 'https://codeload.github.com/cvc5/cvc5/tar.gz/f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341')
        MOD.allowed_urls(rows['cadical'], 'https://codeload.github.com/arminbiere/cadical/tar.gz/refs/heads/rel-2.1.3-elevate')
        for url in ['https://codeload.github.com/arminbiere/cadical/tar.gz/refs/heads/other',
                    'https://codeload.github.com/other/cadical/tar.gz/refs/heads/rel-2.1.3-elevate']:
            with self.assertRaises(ValueError):
                MOD.allowed_urls(rows['cadical'], url)
        MOD.allowed_urls(rows['gmp'], 'https://raw.githubusercontent.com/cvc5/cvc5-deps/main/gmp-6.3.0.tar.bz2')
        for url in ['http://codeload.github.com/cvc5/cvc5/tar.gz/f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341',
                    'https://evil.example/archive.tar.gz', 'https://codeload.github.com/cvc5/cvc5/tar.gz/main',
                    'https://codeload.github.com/cvc5/cvc5/tar.gz/f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341?extra=1']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                MOD.allowed_urls(rows['cvc5'], url)


if __name__ == '__main__':
    unittest.main()
