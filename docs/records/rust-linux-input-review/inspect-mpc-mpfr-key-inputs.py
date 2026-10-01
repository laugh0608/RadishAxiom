#!/usr/bin/env python3
"""Inventory declared OpenPGP key fields; never authenticate identity or signatures."""
import base64
from collections import Counter
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


route = load('fetch-mpc-mpfr-key-inputs.py')
keys = load('inspect-musl-verification-keys.py')
retention = load('retain-musl-verifier-inputs.py')
require, identity = retention.require, retention.identity
EXPECTED = {'mpc': 'AD17A21EF8AED8F1CC02DBD9F7D5C9BF765C61E3',
            'mpfr': 'A534BE3F83E241D918280AEB5831D11A0D4DB02A'}


def armor(raw):
    require(0 < len(raw) <= 262144, 'armor bound')
    lines = raw.decode('ascii').splitlines()
    require(lines[0] == '-----BEGIN PGP PUBLIC KEY BLOCK-----' and
            lines[-1] == '-----END PGP PUBLIC KEY BLOCK-----' and
            lines[-2].startswith('=') and len(lines[-2]) == 5, 'unexpected public key armor')
    payload = lines[1:-2]
    while payload and (not payload[0] or payload[0].startswith(('Version:', 'Comment:'))):
        payload.pop(0)
    data = base64.b64decode(''.join(payload), validate=True)
    crc = 0xB704CE
    for byte in data:
        crc ^= byte << 16
        for _ in range(8):
            crc <<= 1
            if crc & 0x1000000:
                crc ^= 0x1864CFB
    require((crc & 0xffffff).to_bytes(3, 'big') == base64.b64decode(lines[-2][1:], validate=True),
            'armor CRC mismatch')
    return data


def signature_fields(body):
    require(len(body) >= 10 and body[0] == 4, 'unsupported signature version')
    offset, areas = 4, []
    for _ in range(2):
        size, offset = keys.take(body, offset, 2)
        data, offset = keys.take(body, offset, int.from_bytes(size, 'big'))
        areas.append(keys.subpackets(data))
    require(len(body) - offset >= 4, 'missing signature hash or value')
    issuers = []
    for kind, data in areas[0] + areas[1]:
        if kind == 16:
            require(len(data) == 8, 'invalid issuer key ID')
            issuers.append(data.hex().upper())
        if kind == 33:
            require(len(data) == 21 and data[0] == 4, 'invalid issuer fingerprint')
            issuers.append(data[1:].hex().upper())
    require(len(issuers) <= 2 and len({v[-16:] for v in issuers}) <= 1, 'issuer disagreement')
    fields = {}
    for kind, label in ((2, 'created_epoch'), (3, 'signature_expiry_seconds'), (9, 'key_expiry_seconds')):
        values = [data for tag, data in areas[0] if tag == kind]
        require(len(values) <= 1 and all(len(value) == 4 for value in values), 'ambiguous time field')
        fields[label] = int.from_bytes(values[0], 'big') if values else None
    return {'class': body[1], 'public_key_algorithm': body[2], 'digest_algorithm': body[3],
            'declared_issuers': issuers, 'declared_hashed_times': fields,
            'signature_body': identity(body), 'cryptography_executed': False}


def inventory(raw, expected):
    decoded = armor(raw)
    blocks = keys.key_blocks(decoded)
    require(expected in blocks, 'expected primary key absent')
    result = []
    for primary, block in blocks.items():
        packet_list = keys.packets(block)
        key_rows, signatures, uid_count, subject = [], [], 0, None
        for tag, body, _ in packet_list:
            if tag in {6, 14}:
                fpr = keys.fingerprint(body)
                subject = ('primary' if tag == 6 else 'subkey') + ':' + fpr
                key_rows.append({'fingerprint': fpr, 'algorithm': body[5], 'packet': identity(body),
                                 'created_epoch': int.from_bytes(body[1:5], 'big'), 'primary': tag == 6})
            elif tag == 13:
                uid_count += 1
                subject = 'uid:' + identity(body)['sha256']
            else:
                require(subject is not None, 'signature without subject')
                sig = signature_fields(body)
                sig.update(subject=subject, declared_self_signature=any(
                    issuer in {primary, primary[-16:]} for issuer in sig['declared_issuers']))
                signatures.append(sig)
        uid_declarations = [s for s in signatures if s['declared_self_signature'] and
                            s['class'] in {16, 17, 18, 19} and s['subject'].startswith('uid:')]
        expiry_hints = []
        for uid in sorted({s['subject'] for s in uid_declarations}):
            declarations = [s for s in uid_declarations if s['subject'] == uid]
            require(all(s['declared_hashed_times']['created_epoch'] is not None for s in declarations),
                    'UID declaration missing creation time')
            latest = max(s['declared_hashed_times']['created_epoch'] for s in declarations)
            candidates = [s for s in declarations if s['declared_hashed_times']['created_epoch'] == latest]
            durations = {s['declared_hashed_times']['key_expiry_seconds'] for s in candidates}
            require(len(durations) == 1, 'ambiguous latest declared key expiry')
            duration = durations.pop()
            expiry_hints.append({'subject': uid, 'latest_declared_created_epoch': latest,
                                 'declared_key_expiry_utc': datetime.fromtimestamp(
                                     key_rows[0]['created_epoch'] + duration, timezone.utc).isoformat()
                                 if duration else None, 'effective_validity_verified': False})
        result.append({'primary': primary, 'selected': primary == expected,
                       'keys': key_rows, 'uid_count': uid_count, 'packet_count': len(packet_list),
                       'signatures': signatures,
                       'latest_uid_expiry_hints': expiry_hints,
                       'declared_self_digest_counts': dict(Counter(str(s['digest_algorithm']) for s in signatures
                                                                   if s['declared_self_signature'])),
                       'revocation_packet_classes': [s['class'] for s in signatures if s['class'] in {32, 40, 48}]})
    return {'original': identity(raw), 'decoded': identity(decoded), 'blocks': result,
            'selected_primary': expected, 'public_key_identity_accepted': False,
            'cryptography_executed': False, 'source_acceptance': 'not-assessed'}


def inspect():
    records = []
    for name in sorted([*route.TARGETS, 'mpfr-key']):
        for attempt in (1, 2):
            stem = route.DIRECTORY / f'{name}-attempt-{attempt}'
            path = stem.with_suffix('.json')
            if not path.exists():
                continue
            row = json.loads(retention.read_regular(path))
            scope = json.loads(retention.read_regular(stem.with_suffix('.scope.json')))
            expected_target = route.linked_key('https://www.vinc17.net/key.asc') if name == 'mpfr-key' else route.TARGETS[name]
            require(scope['target'] == expected_target, 'unexpected fetch target')
            require(scope['routing_method'] == identity((HERE / 'fetch-mpc-mpfr-key-inputs.py').read_bytes()) and
                    row['method'] == identity((HERE / 'fetch-mpc-mpfr-inputs.py').read_bytes()), 'fetch method drift')
            require(row['target'] == name and row['attempt'] == attempt and
                    row['url'] == scope['target']['url'], 'fetch scope drift')
            require(row['body']['file'] == stem.name + '.' + scope['target']['suffix'], 'fetch filename drift')
            for channel in ('body', 'stdout', 'stderr'):
                source = route.DIRECTORY / row['body']['file'] if channel == 'body' else stem.with_suffix('.' + channel)
                data = retention.read_regular(source, 262144)
                require(identity(data) == {k: row[channel][k] for k in ('bytes', 'sha256')}, 'fetch bytes drift')
            records.append({'observation': row, 'scope': scope})
    selected = {}
    for name, expected in EXPECTED.items():
        matches = [r['observation'] for r in records if r['observation']['target'] == name + '-key'
                   and r['observation']['passed']]
        require(len(matches) == 1 and matches[0]['http_code'] == '200' and matches[0]['exit_code'] == 0,
                'expected one successful key fetch')
        selected[name] = inventory(retention.read_regular(route.DIRECTORY / matches[0]['body']['file']), expected)
    return {'kind': 'diagnostic-mpc-mpfr-key-inputs-v1', 'fetches': records, 'keys': selected,
            'methods': {name: identity((HERE / name).read_bytes()) for name in
                        ('inspect-mpc-mpfr-key-inputs.py', 'inspect-musl-verification-keys.py',
                         'retain-musl-verifier-inputs.py')},
            'identity_pages_are_trusted_inputs_not_independent_proofs': True}


if __name__ == '__main__':
    print(json.dumps(inspect(), sort_keys=True, indent=2))
