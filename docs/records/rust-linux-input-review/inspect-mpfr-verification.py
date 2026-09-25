#!/usr/bin/env python3
"""Fixed MPFR key-material and GnuPG output checks; this parser performs no cryptography."""
from collections import Counter
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


material = load('inspect-mpc-mpfr-key-inputs.py')
keys, require = material.keys, material.require
PRIMARY = 'A534BE3F83E241D918280AEB5831D11A0D4DB02A'
SUBKEY = '8AD026996B3D556D551A5F9E4E2735E8983DE1A8'
OLD = '07F3DBBECC1A39605078094D980C197698C3739D'
CREATED = 1742462545


def inventory(raw):
    require(set(keys.key_blocks(raw)) == {PRIMARY}, 'wrong selected primary')
    subjects, certs, foreign, subject = [], [], [], None
    for tag, body, _ in keys.packets(raw):
        if tag in {6, 14}:
            subject = ('pub' if tag == 6 else 'sub', keys.fingerprint(body))
            require((tag, subject[1], body[5]) in {(6, PRIMARY, 22), (14, SUBKEY, 18)},
                    'unexpected selected key or algorithm')
            subjects.append((subject, body))
        elif tag == 13:
            require(subject is not None and subject[0] != 'sub', 'UID after subkey')
            body.decode('utf-8', errors='strict')
            subject = ('uid', body.hex())
            subjects.append((subject, body))
        else:
            sig = material.signature_fields(body)
            require(subject is not None and (subject[0], sig['class']) in {('uid', 0x13), ('uid', 0x10), ('sub', 0x18)},
                    'revocation or signature outside selected context')
            issuers = sig['declared_issuers']
            require(issuers and all(i in {PRIMARY, PRIMARY[-16:], OLD, OLD[-16:]} for i in issuers),
                    'unexpected certification issuer')
            if PRIMARY in issuers or PRIMARY[-16:] in issuers:
                parsed = keys.signature(body)
                times = sig['declared_hashed_times']
                require(sig['public_key_algorithm'] == 22 and parsed['digest'] == 8 and not parsed['embedded'] and
                        sig['class'] == (0x13 if subject[0] == 'uid' else 0x18), 'unsupported self certification')
                require(times['created_epoch'] is not None and times['signature_expiry_seconds'] is None and
                        times['key_expiry_seconds'] is None, 'self certification time profile drift')
                certs.append((subject, body, times['created_epoch'], sig['class']))
            else:
                # The fixed snapshot contains old-key SHA-1 certifications. Preserve and account for them,
                # but do not use them as identity, self-certification or source-acceptance evidence.
                require(subject[0] == 'uid' and sig['class'] == 0x10 and
                        sig['public_key_algorithm'] == 17 and sig['digest_algorithm'] == 2,
                        'unexpected foreign certification')
                foreign.append((subject, body))
    ids = [s for s, _ in subjects]
    require(len(ids) == len(set(ids)) == 5 and ids[0] == ('pub', PRIMARY) and ids[-1] == ('sub', SUBKEY) and
            all(s[0] == 'uid' for s in ids[1:4]), 'selected subject inventory drift')
    require(Counter(c[0] for c in certs) == Counter(ids[1:]), 'missing or duplicate original self certification')
    require(not foreign or Counter(s for s, _ in foreign) == Counter(ids[1:4]), 'foreign certification set drift')
    return {'subjects': subjects, 'certs': certs, 'foreign': foreign}


def filtered_material(original, filtered):
    before, after = inventory(original), inventory(filtered)
    require(Counter(before['subjects']) == Counter(after['subjects']) and
            Counter(before['certs']) == Counter(after['certs']) and not after['foreign'],
            'import discarded, reassigned or changed original self material')
    return before


def unescape_uid(value):
    # GnuPG colon field 10 uses C escapes; compare decoded UTF-8 bytes, not UID counts or display names.
    out, pos = bytearray(), 0
    escapes = {'n': b'\n', 'r': b'\r', 't': b'\t', 'b': b'\b', 'f': b'\f', 'v': b'\v', '\\': b'\\', '"': b'"'}
    while pos < len(value):
        if value[pos] != '\\':
            out.extend(value[pos].encode('utf-8'))
            pos += 1
            continue
        require(pos + 1 < len(value), 'truncated UID escape')
        code = value[pos + 1]
        if code == 'x':
            token = value[pos + 2:pos + 4]
            require(re.fullmatch('[0-9a-fA-F]{2}', token) is not None, 'invalid UID hex escape')
            out.append(int(token, 16))
            pos += 4
        else:
            require(code in escapes, 'unsupported UID escape')
            out.extend(escapes[code])
            pos += 2
    return bytes(out)


def certifications(raw, original, filtered, observed_at):
    before = filtered_material(original, filtered)
    require(type(observed_at) is int and observed_at > 0, 'invalid observation time')
    expected_subjects = dict(before['subjects'])
    expected_certs = Counter((s, created, kind) for s, _, created, kind in before['certs'])
    seen, certs, subject, pending, trust_seen = [], [], None, None, False
    for line in keys.text_lines(raw):
        f = line.split(':')
        tag = f[0]
        if tag == 'tru':
            require(not seen and pending is None and not trust_seen and len(f) >= 8 and
                    f[1] in {'', 'o', 't'} and all(v.isdigit() for v in f[2:8]), 'unexpected trust annotation')
            trust_seen = True
        elif tag in {'pub', 'sub', 'uid'}:
            require(pending is None and len(f) >= 12 and f[1] in {'-', 'o', 'q', 'm', 'f', 'u'} and
                    'D' not in f[11] and f[5].isdigit() and 0 < int(f[5]) <= observed_at and not f[6],
                    'invalid/revoked/expired subject or time')
            require((not seen and tag == 'pub') or (seen and tag != 'pub'), 'subject order drift')
            if tag == 'uid':
                require(subject is not None and subject[0] != 'sub', 'UID after subkey listing')
                subject = ('uid', unescape_uid(f[9]).hex())
                require(subject in expected_subjects and
                        (subject, int(f[5]), 0x13) in expected_certs, 'UID or self-signature date drift')
                seen.append(subject)
            else:
                pending = (tag, f[4], f[3], int(f[5]))
        elif tag == 'fpr':
            require(pending is not None and len(f) >= 10, 'unpaired fingerprint')
            kind, keyid, algorithm, created = pending
            subject = (kind, f[9])
            require(subject in expected_subjects and keyid == f[9][-16:], 'fingerprint/key ID drift')
            body = expected_subjects[subject]
            require(str(body[5]) == algorithm and int.from_bytes(body[1:5], 'big') == created,
                    'key algorithm or creation time drift')
            seen.append(subject)
            pending = None
        elif tag == 'sig':
            require(pending is None and subject is not None and len(f) >= 16 and f[1] == '!' and
                    f[3] == '22' and f[4] == PRIMARY[-16:] and f[12] == PRIMARY and f[15] == '8' and
                    re.fullmatch('[0-9a-f]{2}x', f[10]) and f[5].isdigit() and
                    0 < int(f[5]) <= observed_at and not f[6], 'invalid self certification result')
            certs.append((subject, int(f[5]), int(f[10][:2], 16)))
        else:
            raise ValueError('unexpected colon record: ' + tag)
    require(pending is None and Counter(seen) == Counter(expected_subjects.keys()) and
            Counter(certs) == expected_certs, 'GnuPG did not check every original self certification in context')
    return {'primary': PRIMARY, 'uid_count': 3, 'self_certifications': 4,
            'excluded_foreign_certifications': len(before['foreign']), 'cryptography_executed_by_parser': False}


def status_fields(raw):
    fields = []
    for line in keys.text_lines(raw):
        require(line.startswith('[GNUPG:] '), 'malformed status prefix')
        f = line[9:].split()
        require(f, 'empty status record')
        fields.append(f)
    require(fields[0] == ['NEWSIG'] and sum(f[0] == 'NEWSIG' for f in fields) == 1,
            'expected exactly one signature group')
    return fields[1:]


def verify(result, observed_at, case='verify'):
    require(result['failure'] is None and result['stdout'] == b'' and type(result['returncode']) is int and
            type(observed_at) is int and observed_at >= CREATED, 'incomplete invocation or observation')
    require(case in {'verify', 'tampered-body', 'wrong-primary', 'missing-primary'}, 'unknown case')
    positive = case == 'verify'
    require(result['returncode'] == 0 if positive else 0 < result['returncode'] < 126,
            'unexpected verification exit')
    rows = status_fields(result['status'])
    seen = Counter()
    date = datetime.fromtimestamp(CREATED, timezone.utc).strftime('%Y-%m-%d')
    for f in rows:
        tag, args = f[0], f[1:]
        seen[tag] += 1
        if tag == 'KEY_CONSIDERED':
            require(args == [PRIMARY, '0'], 'wrong key considered or invalid flags')
        elif positive and tag == 'SIG_ID':
            require(len(args) == 3 and re.fullmatch('[A-Za-z0-9+/=]{1,128}', args[0]) and
                    args[1:] == [date, str(CREATED)] and seen[tag] == 1, 'signature ID mismatch')
        elif positive and tag == 'GOODSIG':
            require(len(args) >= 2 and args[0] == PRIMARY[-16:] and seen[tag] == 1 and not seen['VALIDSIG'],
                    'wrong or duplicate good signature')
        elif positive and tag == 'VALIDSIG':
            require(args == [PRIMARY, date, str(CREATED), '0', '4', '0', '22', '8', '00', PRIMARY] and
                    seen[tag] == 1 and seen['GOODSIG'] == 1, 'detached signature binding mismatch')
        elif positive and tag == 'TRUST_UNDEFINED':
            require(args == ['0', 'pgp'] and seen['VALIDSIG'] == 1 and seen[tag] == 1, 'unexpected trust')
        elif positive and tag == 'VERIFICATION_COMPLIANCE_MODE':
            require(seen['VALIDSIG'] == 1 and seen[tag] == 1 and args and
                    all(re.fullmatch('[0-9]{1,4}', x) for x in args), 'invalid compliance annotation')
        elif case == 'tampered-body' and tag == 'BADSIG':
            require(len(args) >= 2 and args[0] == PRIMARY[-16:] and seen[tag] == 1, 'wrong bad signature')
        elif case in {'wrong-primary', 'missing-primary'} and tag == 'ERRSIG':
            require(args == [PRIMARY[-16:], '22', '8', '00', str(CREATED), '9', PRIMARY] and seen[tag] == 1,
                    'missing key did not reach expected signature error')
        elif case in {'wrong-primary', 'missing-primary'} and tag == 'NO_PUBKEY':
            require(args == [PRIMARY[-16:]] and seen[tag] == 1 and seen['ERRSIG'] == 1,
                    'wrong missing key')
        elif not positive and tag == 'FAILURE':
            require(len(args) == 2 and args[0] == 'gpg-exit' and args[1].isdigit() and seen[tag] == 1,
                    'unrelated negative failure')
        else:
            raise ValueError('unexpected verification status: ' + tag)
    if positive:
        require(all(seen[k] == 1 for k in ('GOODSIG', 'VALIDSIG', 'SIG_ID')) and seen['KEY_CONSIDERED'],
                'incomplete positive signature')
    elif case == 'tampered-body':
        require(seen['BADSIG'] == 1 and seen['KEY_CONSIDERED'], 'tamper did not reach signature mismatch')
    else:
        require(seen['ERRSIG'] == seen['NO_PUBKEY'] == 1 and not seen['KEY_CONSIDERED'],
                'missing primary did not reach expected rejection')
    return {'case': case, 'result': 'signature-status-matched' if positive else 'expected-verification-rejection',
            'source_acceptance': 'not-assessed', 'cryptography_executed_by_parser': False}
