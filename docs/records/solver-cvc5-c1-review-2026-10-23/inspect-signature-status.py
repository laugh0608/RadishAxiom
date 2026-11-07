#!/usr/bin/env python3
"""Check the explicitly accepted three-role 2023 Debian snapshot profile in bounded GnuPG status output; does not verify cryptography."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

LEGACY = '80D15823B7FD1561F9F7BCDDDC30D7C23CBBABEE'
ARCHIVE = '1F89983E0081FDE018F3CC9673A4F27B8DD47936'
RELEASE = '4D64FEC119C2029067D6E791F8D2585B8783D481'
REQUIRED = {LEGACY, ARCHIVE, RELEASE}
SIGNERS = {
    LEGACY: ('0146DC6D4A0B2914BDED34DB648ACFD622F3D138', '1'),
    ARCHIVE: ('A7236886F3CCCAAD148A27F80E98404D386FA1D9', '1'),
    RELEASE: (RELEASE, '22'),
}
FAILURES = {'BADSIG', 'ERRSIG', 'EXPSIG', 'EXPKEYSIG', 'REVKEYSIG', 'NO_PUBKEY', 'FAILURE', 'ERROR',
            'KEYEXPIRED', 'SIGEXPIRED', 'KEYREVOKED', 'NODATA', 'BADARMOR', 'TRUST_NEVER',
            'DECRYPTION_FAILED', 'UNEXPECTED'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def timestamp(value):
    require(re.fullmatch(r'[0-9]{1,10}', value) is not None, 'timestamp outside decimal profile')
    return int(value)


def signature(fields, observed_at):
    require(len(fields) == 10, 'invalid VALIDSIG field count')
    signer, date, created, expires, version, reserved, public, digest, kind, primary = fields
    require(primary in SIGNERS and (signer, public) == SIGNERS[primary], 'wrong primary/signer/algorithm binding')
    require(version == '4' and reserved == '0' and kind == '01' and digest in {'8', '9', '10'},
            'unsupported signature version, class or digest')
    created, expires = timestamp(created), timestamp(expires)
    require(0 < created <= observed_at and (expires == 0 or created < expires and observed_at < expires),
            'signature time invalid')
    require(datetime.fromtimestamp(created, timezone.utc).strftime('%Y-%m-%d') == date,
            'signature date disagrees with timestamp')
    return {'primary': primary, 'signer': signer, 'public_key_algorithm': public,
            'digest_algorithm': digest, 'created_at': created, 'expires_at': expires, 'date': date}


def verify(raw, *, exit_code, observed_at, failure=None):
    require(type(exit_code) is int and exit_code == 0 and failure is None,
            'failed, interrupted or incomplete invocation')
    require(type(observed_at) is int and 0 < observed_at <= 9999999999, 'invalid observation timestamp')
    require(isinstance(raw, bytes) and 0 < len(raw) <= 1024**2 and raw.endswith(b'\n'),
            'empty, oversized or unterminated status stream')
    text = raw.decode('utf-8', errors='strict')
    require(all(ord(c) >= 32 and ord(c) != 127 or c == '\n' for c in text), 'control character in status')
    require(not any(c in text for c in '\u0085\u2028\u2029'), 'non-LF record separator in status')
    lines = text.split('\n')[:-1]
    require(len(lines) <= 4096, 'too many status lines')
    groups, current, plaintext_seen = [], None, False
    for number, line in enumerate(lines, 1):
        require(len(line.encode()) <= 8192 and line.startswith('[GNUPG:] '),
                f'malformed status line {number}')
        keyword, _, value = line[9:].partition(' ')
        fields = value.split()
        require(keyword not in FAILURES, 'GnuPG failure status: ' + keyword)
        if keyword == 'PLAINTEXT':
            require(not groups and current is None and not plaintext_seen and value in {'74 0', '74 0 '},
                    'unexpected plaintext status')
            plaintext_seen = True
        elif keyword == 'NEWSIG':
            require(value in {'', 'debian-release@lists.debian.org'}, 'unexpected signature UID annotation')
            if current is not None:
                groups.append(current)
            require(len(groups) < 3, 'too many signatures')
            current = {'good': None, 'valid': None, 'sig_id': None, 'keys': [], 'trust': False}
        else:
            require(current is not None, 'signature status without NEWSIG')
            if keyword == 'KEY_CONSIDERED':
                require(len(fields) == 2 and fields[0] in SIGNERS and fields[1] == '0',
                        'unexpected key considered or invalid key flags')
                current['keys'].append(fields[0])
            elif keyword == 'SIG_ID':
                require(len(fields) == 3 and current['sig_id'] is None and
                        re.fullmatch(r'[A-Za-z0-9+/=]{1,128}', fields[0]) is not None,
                        'malformed or duplicate SIG_ID')
                current['sig_id'] = {'date': fields[1], 'created_at': timestamp(fields[2])}
            elif keyword == 'GOODSIG':
                key_id, _, user_id = value.partition(' ')
                require(current['good'] is None and current['valid'] is None and user_id and
                        re.fullmatch(r'(?:[0-9A-F]{16}|[0-9A-F]{40})', key_id) is not None,
                        'malformed, duplicate or reordered GOODSIG')
                current['good'] = key_id
            elif keyword == 'VALIDSIG':
                require(current['valid'] is None and current['good'] is not None, 'unpaired or duplicate VALIDSIG')
                current['valid'] = signature(fields, observed_at)
            elif keyword == 'TRUST_UNDEFINED':
                require(current['valid'] is not None and not current['trust'] and (fields == ['0', 'pgp'] or fields == ['0', 'pgp', 'debian-release@lists.debian.org'] and current['valid']['primary'] == RELEASE),
                        'unexpected trust record')
                current['trust'] = True
            elif keyword == 'VERIFICATION_COMPLIANCE_MODE':
                require(current['valid'] is not None and fields and all(re.fullmatch('[0-9]{1,4}', f) for f in fields),
                        'invalid compliance annotation')
            else:
                raise ValueError('unrecognized status: ' + keyword)
    if current is not None:
        groups.append(current)
    found = {}
    for group in groups:
        valid = group['valid']
        require(valid is not None and group['good'] in {valid['signer'], valid['signer'][-16:]},
                'incomplete or inconsistent signature group')
        primary = valid['primary']
        require(primary not in found and group['keys'] and set(group['keys']) == {primary},
                'duplicate role or inconsistent considered key')
        require(group['sig_id'] == {k: valid[k] for k in ['date', 'created_at']}, 'SIG_ID disagrees with VALIDSIG')
        found[primary] = valid
    require(REQUIRED == found.keys(), 'missing or unexpected historical snapshot role')
    return {'kind': 'diagnostic-cvc5-historical-signature-status-v1', 'result': 'required-role-statuses-matched',
            'observed_at': observed_at, 'signatures': found,
            'status': {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()},
            'source_acceptance': 'not-assessed', 'cryptography_executed_by_parser': False,
            'self_certifications_assessed': False, 'cross_certification_assessed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status', type=Path, required=True)
    parser.add_argument('--exit-code', type=int, required=True)
    parser.add_argument('--observed-at', type=int, required=True, help='actual invocation UTC Unix timestamp')
    parser.add_argument('--failure', help='collector failure, timeout or limit reason; any supplied value rejects')
    args = parser.parse_args()
    with args.status.open('rb') as stream:
        raw = stream.read(1024**2 + 1)
    print(json.dumps(verify(raw, exit_code=args.exit_code, observed_at=args.observed_at,
                            failure=args.failure), sort_keys=True, indent=2))
