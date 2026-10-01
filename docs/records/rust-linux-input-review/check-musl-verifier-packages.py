#!/usr/bin/env python3
"""Synthetic metadata rejection checks; no downloads, apt, or cryptography."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('packages',
    Path(__file__).with_name('inspect-musl-verifier-packages.py'))
packages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packages)


def row(name='gpg', version='2.4.7-21+deb13u1+b4', **fields):
    return {'package': name, 'version': version, 'architecture': 'arm64', **fields}


class Boundaries(unittest.TestCase):
    def test_version_order(self):
        for low, high in [('1.9', '1.10'), ('1.0~rc1', '1.0'), ('1.0~~', '1.0~'),
                          ('2.4.7-21+deb13u1', '2.4.7-21+deb13u1+b4'),
                          ('1.0-2', '1.0-10'), ('9.9', '1:1.0'),
                          ('1.0a', '1.0+'), ('1.69~deb13u1', '1.69')]:
            with self.subTest(low=low, high=high):
                self.assertLess(packages.compare_versions(low, high), 0)
                self.assertGreater(packages.compare_versions(high, low), 0)
        for left, right in [('1.0', '1.0-0'), ('0:1.0', '1.0'), ('1.01', '1.1')]:
            self.assertEqual(packages.compare_versions(left, right), 0)

    def test_explicit_dependencies_with_cycle(self):
        selected, edges = packages.closure([
            row(depends='libxx (>= 1.10)', recommends='not-selected'),
            row('libxx', '1.11', **{'pre-depends': 'gpg (= 2.4.7-21+deb13u1+b4)'})])
        self.assertEqual(set(selected), {'gpg', 'libxx'})
        self.assertEqual(len(edges), 2)
        self.assertTrue(all(edge['constraint_satisfied'] for edge in edges))

    def test_missing_duplicate_wrong_architecture(self):
        for rows in [[], [row(), row()], [row(architecture='amd64')],
                     [row(depends='missing')]]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                packages.closure(rows)

    def test_unsatisfied_versions(self):
        for constraint in ['libxx (>= 1.10)', 'libxx (= 1.10)']:
            with self.subTest(constraint=constraint), self.assertRaises(ValueError):
                packages.closure([row(depends=constraint), row('libxx', '1.9')])

    def test_unsupported_syntax_stops(self):
        for value in ['libxx | libyy', 'libxx:any', 'libxx [arm64]', 'libxx (<< 2)',
                      'libxx (>= 1) junk', 'libxx,', 'libxx (>= nope)']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                packages.dependencies(value)

    def test_source_version_identity(self):
        value = row(source='gnupg2 (2.4.7-21+deb13u1)')
        self.assertEqual(packages.source_identity(value), ('gnupg2', '2.4.7-21+deb13u1'))
        self.assertEqual(packages.source_identity(row('libxx', '1.2')), ('libxx', '1.2'))

    def test_source_and_artifact_binding(self):
        value = row(source='gnupg2 (2.4.7-21+deb13u1)',
                    filename='pool/main/g/gnupg2/gpg_2.4.7-21+deb13u1+b4_arm64.deb',
                    sha256='a' * 64, size='578896')
        source = {'package': 'gnupg2', 'version': '2.4.7-21+deb13u1',
                  'binary': 'gpg, gpgconf', 'directory': 'pool/main/g/gnupg2'}
        self.assertEqual(len(packages.bind_sources({'gpg': value}, [source])), 1)
        for sources in [[], [source, source], [dict(source, version='2.4.7-21')],
                        [dict(source, binary='gpgconf')]]:
            with self.subTest(sources=sources), self.assertRaises(ValueError):
                packages.bind_sources({'gpg': value}, sources)
        for changed in [dict(value, filename='pool/main/g/gnupg2/../bad_arm64.deb'),
                        dict(value, filename='pool/main/g/gnupg2/bad_amd64.deb'),
                        dict(value, sha256='a' * 40), dict(value, size='0')]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                packages.bind_sources({'gpg': changed}, [source])


if __name__ == '__main__':
    unittest.main()
