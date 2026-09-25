#!/usr/bin/env python3
"""Fixed GMP snapshot and expired-key diagnostics; no cryptography or source acceptance."""
from collections import Counter
import importlib.util
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mpfr = load('inspect-mpfr-verification.py')
material, keys, require = mpfr.material, mpfr.keys, mpfr.require
identity = material.identity
PRIMARY = '343C2FF0FBEE5EC2EDBEF399F3599FF828C67298'
SUBKEY = '48C9DE74746361F8617018347520153007F35B23'
CREATED = 1690719513
KEY_CREATED = 1357586787
SELF_CREATED = {'uid': 1579281163, 'sub': 1579281679}
EXPIRES = {'pub': 1736961163, 'uid': 1736961163, 'sub': 1736961679}
REVOCATION_SHA = 'f10200d9f5fd7bca0ac077164da53094bb785fb24fb49ec42b1768836f4701bb'


def areas(body):
    offset, result = 4, []
    for _ in range(2):
        size, offset = keys.take(body, offset, 2)
        raw, offset = keys.take(body, offset, int.from_bytes(size, 'big'))
        # Unlike the old declaration reader, do not discard unknown critical flags.
        pos, fields = 0, []
        while pos < len(raw):
            length, pos = keys.length(raw, pos)
            value, pos = keys.take(raw, pos, length)
            require(value and not value[0] & 128, 'critical subpacket outside GMP profile')
            fields.append((value[0], value[1:]))
            require(len(fields) <= 128, 'subpacket count bound')
        result.append(fields)
    return result


def inventory(raw):
    """Only the explicit five-packet strong projection is eligible for this diagnostic."""
    packets = keys.packets(raw)
    require([tag for tag, _, _ in packets] == [6, 13, 2, 14, 2], 'strong subject/packet order drift')
    subjects, certs = [], []
    for tag, body, _ in packets:
        if tag in {6, 14}:
            kind = 'pub' if tag == 6 else 'sub'
            subject = (kind, keys.fingerprint(body))
            require(subject[1] == (PRIMARY if tag == 6 else SUBKEY) and body[5] == 1 and
                    int.from_bytes(body[1:5], 'big') == KEY_CREATED, 'key identity/algorithm/time drift')
            subjects.append((subject, body))
        elif tag == 13:
            body.decode('utf-8', errors='strict')
            subject = ('uid', body.hex())
            subjects.append((subject, body))
        else:
            sig = material.signature_fields(body)
            parsed = keys.signature(body)
            hashed, unhashed = areas(body)
            kind = subject[0]
            require(set(t for t, _ in hashed) <= {2, 9, 11, 21, 22, 23, 27, 30, 33} and
                    len({t for t, _ in hashed}) == len(hashed) and
                    unhashed == [(16, bytes.fromhex(PRIMARY[-16:]))], 'self subpacket profile drift')
            require(dict(hashed).get(33) == b'\x04' + bytes.fromhex(PRIMARY) and
                    dict(hashed).get(27) == (b'\x03' if kind == 'uid' else b'\x0c'),
                    'signing/encryption capability or hashed issuer drift')
            require(sig['class'] == (0x13 if kind == 'uid' else 0x18) and
                    sig['public_key_algorithm'] == 1 and parsed['digest'] == 8 and not parsed['embedded'] and
                    sig['declared_hashed_times'] == {'created_epoch': SELF_CREATED[kind],
                        'signature_expiry_seconds': None, 'key_expiry_seconds': EXPIRES[kind] - KEY_CREATED},
                    'strong self certification profile drift')
            require(KEY_CREATED <= SELF_CREATED[kind] <= CREATED < EXPIRES[kind],
                    'signature claim outside selected certification interval')
            certs.append((subject, body, SELF_CREATED[kind], sig['class']))
    return {'subjects': subjects, 'certs': certs}


def project(raw):
    """Account for every original packet; selecting strong signatures is not a revocation verdict."""
    require(set(keys.key_blocks(raw)) == {PRIMARY}, 'original primary drift')
    selected, excluded, self_rows, revocations = [], [], [], []
    subject = None
    for index, (tag, body, packet) in enumerate(keys.packets(raw)):
        if tag in {6, 14, 13}:
            subject = ('uid', body.hex()) if tag == 13 else (
                'pub' if tag == 6 else 'sub', keys.fingerprint(body))
            selected.append(packet)
            continue
        sig = material.signature_fields(body)
        issuers = sig['declared_issuers']
        is_self = any(i in {PRIMARY, PRIMARY[-16:]} for i in issuers)
        row = {'packet_index': index, 'subject': list(subject), **sig}
        require(subject is not None and issuers, 'signature context or issuer missing')
        if sig['class'] in {0x20, 0x28, 0x30}:
            require(subject[0] == 'uid' and sig['class'] == 0x30 and not is_self and
                    issuers == ['598F95AAF6C99C5F'] and
                    identity(body)['sha256'] == REVOCATION_SHA, 'new or self revocation requires separate review')
            revocations.append(row)
        elif is_self:
            require((subject[0], sig['class']) in {('uid', 0x13), ('sub', 0x18)}, 'self context drift')
            self_rows.append((subject[0], sig['digest_algorithm']))
            if sig['digest_algorithm'] == 8:
                selected.append(packet)
                continue
            require(sig['digest_algorithm'] == 2 and sig['declared_hashed_times'] == {
                'created_epoch': KEY_CREATED, 'signature_expiry_seconds': None,
                'key_expiry_seconds': 315360000}, 'unexpected old self certification')
        else:
            require(subject[0] == 'uid' and sig['class'] in {0x10, 0x11, 0x12, 0x13},
                    'foreign certification context drift')
        row['disposition'] = ('unverified-third-party-certification-revocation' if sig['class'] == 0x30
                              else 'excluded-old-sha1-self' if is_self else 'unused-foreign-certification')
        excluded.append(row)
    require(Counter(self_rows) == Counter([('uid', 8), ('uid', 2), ('sub', 8), ('sub', 2)]) and
            len(revocations) == 1, 'original self/revocation inventory drift')
    projection = b''.join(selected)
    inventory(projection)
    return projection, {'original': identity(raw), 'projection': identity(projection), 'excluded': excluded,
                        'revocations': revocations, 'revocation_authentication': 'not-performed',
                        'all_channel_freshness': 'unknown', 'source_acceptance': 'not-assessed'}


def filtered_material(original, filtered):
    before, after = inventory(original), inventory(filtered)
    require(before == after, 'import discarded, reassigned or changed selected strong material')
    return before


def certifications(raw, original, filtered, observed_at):
    before = filtered_material(original, filtered)
    require(type(observed_at) is int and observed_at > max(EXPIRES.values()), 'expected actual post-expiry time')
    expected = dict(before['subjects'])
    wanted = [(s, created, kind) for s, _, created, kind in before['certs']]
    seen, certs, subject, pending, trust_seen = [], [], None, None, False
    for line in keys.text_lines(raw):
        f = line.split(':')
        tag = f[0]
        if tag == 'tru':
            require(not seen and pending is None and not trust_seen and len(f) >= 8 and
                    f[1] in {'', 'o', 't'} and all(v.isdigit() for v in f[2:8]), 'unexpected trust annotation')
            trust_seen = True
        elif tag in {'pub', 'uid', 'sub'}:
            require(pending is None and len(f) >= 12 and 'D' not in f[11] and f[5].isdigit(),
                    'invalid subject record')
            require((not seen and tag == 'pub') or (seen and tag != 'pub'), 'subject order drift')
            if tag == 'uid':
                require(subject is not None and subject[0] != 'sub' and f[1] in {'e', '-', 'q'} and
                        int(f[5]) == SELF_CREATED['uid'] and f[6] in {'', str(EXPIRES['uid'])},
                        'UID time/state drift')
                subject = ('uid', mpfr.unescape_uid(f[9]).hex())
                require(subject in expected, 'UID bytes drift')
                seen.append(subject)
            else:
                require(f[1] == 'e' and f[3] == '1' and int(f[5]) == KEY_CREATED and
                        f[6] == str(EXPIRES[tag]), 'expected explicit expired key and exact expiry')
                pending = (tag, f[4])
        elif tag == 'fpr':
            require(pending is not None and len(f) >= 10, 'unpaired fingerprint')
            kind, keyid = pending
            subject = (kind, f[9])
            require(subject in expected and keyid == f[9][-16:], 'key fingerprint drift')
            seen.append(subject)
            pending = None
        elif tag == 'sig':
            require(pending is None and subject is not None and len(f) >= 16 and f[1] == '!' and
                    f[3] == '1' and f[4] == PRIMARY[-16:] and f[12] == PRIMARY and f[15] == '8' and
                    re.fullmatch('[0-9a-f]{2}x', f[10]) and f[5].isdigit() and not f[6],
                    'strong self certification not checked')
            certs.append((subject, int(f[5]), int(f[10][:2], 16)))
        else:
            raise ValueError('unexpected colon record: ' + tag)
    require(pending is None and Counter(seen) == Counter(expected.keys()) and Counter(certs) == Counter(wanted),
            'missing/duplicate/reassigned self certification')
    return {'primary': PRIMARY, 'self_certifications': 2, 'current_key_state': 'expired',
            'declared_signature_time_in_selected_interval': True, 'historical_validity': 'not-established',
            'cryptography_executed_by_parser': False, 'source_acceptance': 'not-assessed'}


def verify(result, observed_at, case='verify'):
    require(result['failure'] is None and result['stdout'] == b'' and type(result['returncode']) is int and
            type(observed_at) is int and observed_at > max(EXPIRES.values()), 'incomplete invocation or actual time')
    require(case in {'verify', 'tampered-body', 'wrong-primary', 'missing-primary'}, 'unknown case')
    positive = case == 'verify'
    require(result['returncode'] == 0 if positive else 0 < result['returncode'] < 126, 'unexpected verification exit')
    seen = Counter()
    for f in mpfr.status_fields(result['status']):
        tag, args = f[0], f[1:]
        seen[tag] += 1
        if tag == 'KEY_CONSIDERED':
            require(args == [PRIMARY, '0'] and seen[tag] <= 8, 'key considered drift')
        elif tag == 'KEYEXPIRED' and case in {'verify', 'tampered-body'}:
            require(args == [str(EXPIRES['pub'])] and seen[tag] <= 8, 'key expiry drift')
        elif positive and tag == 'SIG_ID':
            require(len(args) == 3 and re.fullmatch('[A-Za-z0-9+/=]{1,128}', args[0]) and
                    args[1:] == ['2023-07-30', str(CREATED)] and seen[tag] == 1, 'signature ID drift')
        elif positive and tag == 'EXPKEYSIG':
            require(len(args) >= 2 and args[0] == PRIMARY[-16:] and seen[tag] == 1 and not seen['VALIDSIG'],
                    'expired-key signature drift')
        elif positive and tag == 'VALIDSIG':
            require(args == [PRIMARY, '2023-07-30', str(CREATED), '0', '4', '0', '1', '10', '00', PRIMARY] and
                    seen[tag] == 1 and seen['EXPKEYSIG'] == 1, 'signature binding drift')
        elif positive and tag == 'TRUST_UNDEFINED':
            require(args == ['0', 'pgp'] and seen['VALIDSIG'] == 1 and seen[tag] == 1, 'trust drift')
        elif positive and tag == 'VERIFICATION_COMPLIANCE_MODE':
            require(seen['VALIDSIG'] == 1 and seen[tag] == 1 and args and
                    all(re.fullmatch('[0-9]{1,4}', x) for x in args), 'compliance annotation drift')
        elif case == 'tampered-body' and tag == 'BADSIG':
            require(len(args) >= 2 and args[0] == PRIMARY[-16:] and seen[tag] == 1, 'wrong bad signature')
        elif case in {'wrong-primary', 'missing-primary'} and tag == 'ERRSIG':
            require(args == [PRIMARY[-16:], '1', '10', '00', str(CREATED), '9', PRIMARY] and seen[tag] == 1,
                    'unexpected missing-key error')
        elif case in {'wrong-primary', 'missing-primary'} and tag == 'NO_PUBKEY':
            require(args == [PRIMARY[-16:]] and seen[tag] == 1 and seen['ERRSIG'] == 1, 'wrong missing key')
        elif not positive and tag == 'FAILURE':
            require(len(args) == 2 and args[0] == 'gpg-exit' and args[1].isdigit() and seen[tag] == 1,
                    'unrelated negative failure')
        else:
            raise ValueError('unexpected verification status: ' + tag)
    if positive:
        require(all(seen[k] == 1 for k in ('EXPKEYSIG', 'VALIDSIG', 'SIG_ID')) and
                seen['KEY_CONSIDERED'] and seen['KEYEXPIRED'], 'incomplete expired-key signature diagnostic')
    elif case == 'tampered-body':
        require(seen['BADSIG'] == 1 and seen['KEY_CONSIDERED'], 'tamper did not reach mismatch')
    else:
        require(seen['ERRSIG'] == seen['NO_PUBKEY'] == 1 and not seen['KEY_CONSIDERED'], 'missing key not rejected')
    return {'case': case, 'result': 'signature-relation-matched-with-expired-key' if positive
            else 'expected-verification-rejection', 'source_acceptance': 'not-assessed',
            'historical_validity': 'not-established', 'current_key_state': 'expired' if positive else 'not-assessed',
            'cryptography_executed_by_parser': False}
