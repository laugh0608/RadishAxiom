#!/usr/bin/env python3
"""Synthetic diagnostic boundary tests; no real signature verification."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('musl_auth', Path(__file__).with_name('inspect-musl-debian-auth.py'))
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)
NOW = 2000000000
SUB = 'B8E5F13176D2A7A75220028078DBA3BC47EF2265'


def status():
    return ''.join(f'[GNUPG:] VALIDSIG {signer} 2026-07-11 1783760580 0 4 0 1 8 01 {role}\n'
                   for role, signer in [(auth.ARCHIVE, SUB), (auth.RELEASE, auth.RELEASE)])


def row(kind, **values):
    fields = [''] * 17
    fields[0] = kind
    for index, value in values.items():
        fields[int(index.removeprefix('f')) - 1] = value
    return ':'.join(fields) + '\n'


def key():
    text = row('pub', f2='-', f6='1700000000', f7='2100000000', f12='scSC')
    text += row('fpr', f10=auth.ARCHIVE)
    text += row('uid', f2='-', f6='1700000000')
    text += row('sig', f2='!', f6='1700000000', f11='13x', f13=auth.ARCHIVE, f16='10')
    text += row('sub', f2='-', f6='1700000000', f7='2100000000', f12='s')
    text += row('fpr', f10=SUB)
    text += row('sig', f2='!', f6='1700000000', f11='18x', f13=auth.ARCHIVE, f16='10')
    return {'certifications': {'exit_code': 0, 'stdout': text}, 'export': {'exit_code': 0},
            'packets': {'exit_code': 0, 'stdout':
                'sigclass 0x18\ndigest algo 10\nsubpkt 32 len 563 (signature: v4, class 0x19, algo 1, digest algo 10)\n'}}


class Boundaries(unittest.TestCase):
    def test_required_signatures(self):
        self.assertEqual(set(auth.signatures(status(), NOW)), auth.ROLES)

    def test_signature_failures(self):
        for text in [status().splitlines(keepends=True)[0], status() + status(),
                     status().replace(' 8 01 ', ' 2 01 '),
                     status() + '[GNUPG:] ERROR test\n',
                     status().replace(auth.RELEASE, '0' * 40),
                     status().replace('1783760580', str(NOW + 1)),
                     status().replace(' 0 4 0 ', ' 1900000000 4 0 ')]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                auth.signatures(text, NOW)

    def test_strong_self_binding(self):
        result = auth.certifications(key(), auth.ARCHIVE, SUB, NOW)
        self.assertEqual(result['embedded_cross_certification_digests'], ['10'])

    def test_crashed_commands_rejected(self):
        for command in ('certifications', 'export', 'packets'):
            value = key()
            value[command]['exit_code'] = -6
            with self.subTest(command=command), self.assertRaises(ValueError):
                auth.certifications(value, auth.ARCHIVE, SUB, NOW)

    def test_self_signature_integrity(self):
        for old, new in [('sig:!', 'sig:-'), (':::10:', ':::2:'),
                         ('13x', '18x'), ('18x', '13x'),
                         (auth.ARCHIVE + ':::10', '0' * 40 + ':::10')]:
            value = key()
            self.assertIn(old, value['certifications']['stdout'])
            value['certifications']['stdout'] = value['certifications']['stdout'].replace(old, new)
            with self.subTest(old=old), self.assertRaises(ValueError):
                auth.certifications(value, auth.ARCHIVE, SUB, NOW)

    def test_expired_revoked_or_wrong_key(self):
        for old, new in [('pub:-', 'pub:r'), ('2100000000', '1900000000'),
                         ('1700000000', '2200000000'), (SUB, '0' * 40)]:
            value = key()
            value['certifications']['stdout'] = value['certifications']['stdout'].replace(old, new)
            with self.subTest(old=old), self.assertRaises(ValueError):
                auth.certifications(value, auth.ARCHIVE, SUB, NOW)

    def test_original_packets_and_cross_certification(self):
        for text in ['', 'digest algo 2', 'sigclass 0x20\ndigest algo 10',
                     'digest algo 10', key()['packets']['stdout'].replace('digest algo 10)', 'digest algo 2)')]:
            value = key()
            value['packets']['stdout'] = text
            with self.subTest(text=text), self.assertRaises(ValueError):
                auth.certifications(value, auth.ARCHIVE, SUB, NOW)

    def test_index_binding_and_selection(self):
        rows = [{'package': 'musl', 'version': '1.2.5-3.1~deb13u1'}]
        for changed in [[], rows * 2, [{'package': 'musl', 'version': '1.2.6-1'}]]:
            with self.subTest(rows=changed), self.assertRaises(ValueError):
                auth.chain.unique_selection(changed, {'musl': '1.2.5-3.1~deb13u1'}, binary=False)
        with self.assertRaises(ValueError):
            auth.chain.checksums('a' * 64 + ' 12 ../escape')

    def test_exact_source_names(self):
        value = '\n'.join('a' * 64 + ' 12 ' + name for name in sorted(auth.SOURCE_NAMES))
        self.assertEqual(auth.original_digest(value), {'sha256': 'a' * 64, 'bytes': 12})
        for changed in [value + '\n' + value, value.replace('~deb13u1', '~deb13u2'),
                        value.replace('.orig.tar.gz', '/../escape'),
                        value.replace('a' * 64, 'x' * 64), '\n'.join(value.splitlines()[1:])]:
            with self.subTest(value=changed), self.assertRaises(ValueError):
                auth.original_digest(changed)


if __name__ == '__main__':
    unittest.main()
