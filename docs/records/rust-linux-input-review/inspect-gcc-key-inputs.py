#!/usr/bin/env python3
"""Inventory GCC signer/subkey declarations; opaque signatures remain unresolved, never trusted."""
import argparse
from collections import Counter
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


route = load('fetch-gcc-key-inputs.py')
refresh = load('inspect-binutils-key-refresh.py')
declarations = refresh.prior.keys
keys = declarations.keys
require, identity, read = refresh.require, refresh.identity, refresh.read
SIGNER = route.PRIMARY  # Historical fetch plan assumed a primary; observed packet is a subkey.
PRIMARY = '13975A70E63C361C73AE69EF6EEB81F8981C74C7'
SIGNATURE = HERE.parents[2] / '.tmp/gcc-inputs-dac0405-20260925/signature-attempt-1.sig'


class IdentityItems(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items, self.current = [], None

    def handle_starttag(self, tag, attrs):
        if tag == 'li':
            self.current = []

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == 'li' and self.current is not None:
            self.items.append(' '.join(' '.join(self.current).split()))
            self.current = None


def identity_statement(raw):
    require(0 < len(raw) <= 262144, 'identity page bound')
    page = IdentityItems()
    page.feed(raw.decode('utf-8'))
    expected = ('2048R/FC26A641 2005-09-13 Richard Guenther <richard.guenther@gmail.com> '
                'Key fingerprint = 7F74 F97C 1034 68EE 5D75 0B58 3AB0 0996 FC26 A641')
    require(page.items.count(expected) == 1, 'exact official identity item missing or duplicated')
    return {'item': expected, 'page': identity(raw), 'identity_accepted': False}


def embedded_signatures(body):
    offset, rows = 4, []
    for area in ('hashed', 'unhashed'):
        size, offset = keys.take(body, offset, 2)
        data, offset = keys.take(body, offset, int.from_bytes(size, 'big'))
        for kind, value in keys.subpackets(data):
            if kind == 32:
                require(value, 'empty embedded signature')
                row = {'area': area, 'body': identity(value), 'version': value[0]}
                if value[0] == 4:
                    row['declaration'] = declarations.signature_fields(value)
                else:
                    row['semantics_inspected'] = False
                rows.append(row)
    return rows


def inventory(raw, primary=PRIMARY, signer=SIGNER):
    require(set(keys.key_blocks(raw)) == {primary}, 'unexpected primary set')
    public, uids, signatures, opaque, subject = [], [], [], [], None
    for tag, body, _ in keys.packets(raw):
        if tag in (6, 14):
            fpr = keys.fingerprint(body)
            require(fpr not in {row['fingerprint'] for row in public}, 'duplicate public key')
            subject = ('primary:' if tag == 6 else 'subkey:') + fpr
            public.append({'fingerprint': fpr, 'primary': tag == 6, 'algorithm': body[5],
                           'created_epoch': int.from_bytes(body[1:5], 'big'), 'body': identity(body)})
        elif tag == 13:
            subject = 'uid:' + identity(body)['sha256']
            uids.append({'subject': subject, 'text': body.decode('utf-8'), 'body': identity(body)})
        else:
            require(subject is not None, 'signature without subject')
            if body[0] != 4:
                opaque.append({'subject': subject, 'version': body[0], 'body': identity(body),
                               'semantics_inspected': False})
                continue
            row = declarations.signature_fields(body)
            row.update(subject=subject, declared_self_signature=any(
                issuer in {primary, primary[-16:]} for issuer in row['declared_issuers']),
                embedded=embedded_signatures(body))
            signatures.append(row)
    require(any(row['fingerprint'] == signer and not row['primary'] for row in public),
            'expected signing subkey missing')
    self_rows = [row for row in signatures if row['declared_self_signature']]
    bindings = [row for row in self_rows if row['subject'] == 'subkey:' + signer and row['class'] == 24]
    require(bindings, 'signing subkey binding declaration missing')
    return {'primary': primary, 'signer': signer, 'public_keys': public, 'uids': uids,
            'v4_signatures': signatures, 'opaque_signatures': opaque,
            'declared_v4_self_digest_counts': dict(Counter(str(row['digest_algorithm']) for row in self_rows)),
            'signer_binding_declarations': bindings,
            'declared_v4_revocations': [row for row in signatures if row['class'] in (32, 40, 48)],
            'complete_signature_semantics_inspected': not opaque,
            'effective_validity_verified': False, 'cryptography_executed': False}


def inspect(directory=route.DIRECTORY, ring_path=refresh.DEFAULT / 'gnu-keyring-attempt-1.gpg',
            signature_path=SIGNATURE):
    require(json.loads(read(directory / 'fetch-plan.json')) == route.plan(), 'fetch plan drift')
    fetches, bodies = [], {}
    for name, target in route.TARGETS.items():
        stem, filename = name + '-attempt-1', name + '-attempt-1.' + target['suffix']
        row = json.loads(read(directory / (stem + '.json')))
        argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--proto', '=https', '--tlsv1.2',
                '--max-time', '60', '--max-filesize', str(target['limit']),
                '--output', str(route.DIRECTORY / filename), '--write-out', '%{http_code}\n', target['url']]
        require(row['argv'] == argv and row['target'] == name and row['url'] == target['url'] and
                row['attempt'] == 1 and row['body']['file'] == filename and row['method'] == route.plan()['method'],
                'fetch scope drift')
        require(row['exit_code'] == 0 and row['http_code'] == '200' and row['parent_timeout'] is False and
                row['passed'] is True and row['transport_passed'] is True, 'fetch outcome drift')
        for channel in ('body', 'stdout', 'stderr'):
            raw = read(directory / (filename if channel == 'body' else stem + '.' + channel), target['limit'])
            require(identity(raw) == {k: row[channel][k] for k in ('bytes', 'sha256')}, 'fetch bytes drift')
            if channel == 'body':
                bodies[name] = raw
            else:
                require(raw.decode('utf-8') == row[channel]['text'], 'fetch stream drift')
                require(raw == (b'200\n' if channel == 'stdout' else b''), 'unexpected fetch stream')
        fetches.append(row)
    ring = read(ring_path)
    require(identity(ring) == refresh.RING, 'previous GNU keyring drift')
    selected, selection = refresh.select(ring, PRIMARY)
    ubuntu = declarations.armor(bodies['public-key'])
    failures = []
    for label, operation, expected in (
        ('gnu-assumed-primary', lambda: refresh.select(ring, SIGNER), 'target primary absent'),
        ('ubuntu-assumed-primary', lambda: declarations.inventory(bodies['public-key'], SIGNER),
         'expected primary key absent'),
        ('ubuntu-existing-v4-only-profile', lambda: declarations.inventory(bodies['public-key'], PRIMARY),
         'unsupported signature version'),
    ):
        try:
            operation()
        except ValueError as error:
            require(str(error) == expected, 'unexpected previous diagnostic failure')
            failures.append({'diagnostic': label, 'error': str(error)})
        else:
            raise ValueError('previous diagnostic failure no longer reproduced')
    detached = read(signature_path, 65536)
    require(identity(detached) == {'bytes': 310, 'sha256':
            '764f191a8679cf7269dd73a5b313d5597b28424dd7c74a82d43570ba5da0eced'}, 'detached signature drift')
    packet_list = keys.packets(detached)
    require(len(packet_list) == 1 and packet_list[0][0] == 2, 'detached signature packet mismatch')
    signature = keys.signature(packet_list[0][1])
    require(signature['issuer'] == SIGNER and signature['class'] == 0 and signature['digest'] == 8,
            'detached signer declaration drift')
    inventories = {'gnu': inventory(selected), 'ubuntu': inventory(ubuntu)}
    bindings = [inventories[name]['signer_binding_declarations'] for name in ('gnu', 'ubuntu')]
    return {'kind': 'diagnostic-gcc-key-inputs-v1', 'fetches': fetches,
            'official_statement': identity_statement(bodies['identity']), 'inventories': inventories,
            'gnu_keyring': refresh.RING, 'gnu_selection': selection,
            'reproduced_narrow_profile_failures': failures,
            'detached_signature': {'input': identity(detached), 'declaration': signature},
            'historical_expected_primary_is_actually_subkey': True,
            'signer_binding_declarations_equal': bindings[0] == bindings[1],
            'key_identity_accepted': False, 'cryptography_executed': False, 'source_acceptance': 'not-assessed',
            'methods': {name: identity(read(HERE / name)) for name in
                        ('inspect-gcc-key-inputs.py', 'fetch-gcc-key-inputs.py', 'fetch-mpc-mpfr-inputs.py',
                         'inspect-binutils-key-refresh.py', 'inspect-binutils-key-inputs.py',
                         'inspect-mpc-mpfr-key-inputs.py', 'fetch-mpc-mpfr-key-inputs.py',
                         'inspect-musl-verification-keys.py',
                         'inspect-musl-verification-status.py', 'retain-musl-verifier-inputs.py')}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=route.DIRECTORY)
    parser.add_argument('--ring', type=Path, default=refresh.DEFAULT / 'gnu-keyring-attempt-1.gpg')
    parser.add_argument('--signature', type=Path, default=SIGNATURE)
    args = parser.parse_args()
    print(json.dumps(inspect(args.directory, args.ring, args.signature), sort_keys=True, indent=2))
