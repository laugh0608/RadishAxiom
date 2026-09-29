#!/usr/bin/env python3
"""Offline v3 candidate for fixed expired GMP certifications; no execution entry point."""
from collections import Counter
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('historical', HERE / 'inspect-gmp-certification-attempt.py')
historical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(historical)
p = historical.run.profile
require = p.require
PROFILE = 'gmp-certification-expiry-v3-offline-candidate'
BASIS_SHA = '4353f860d766b28fc353020672a40c6869df4a4142d48b837eef57e189ca3cf9'


def certifications(raw, original, filtered, observed_at):
    # Keep packet declarations unchanged; only the *reported effective* subkey
    # expiry follows getkey.c's already-expired-primary branch. Frozen v1/v2 stay intact.
    before = p.filtered_material(original, filtered)
    require(type(observed_at) is int and observed_at > max(p.EXPIRES.values()), 'expected actual post-expiry time')
    effective = {'pub': p.EXPIRES['pub'], 'sub': min(p.EXPIRES['pub'], p.EXPIRES['sub'])}
    expected = dict(before['subjects'])
    wanted = [(s, created, kind) for s, _, created, kind in before['certs']]
    seen, certs, subject, pending, trust_seen = [], [], None, None, False
    for line in p.keys.text_lines(raw):
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
                        int(f[5]) == p.SELF_CREATED['uid'] and f[6] in {'', str(p.EXPIRES['uid'])},
                        'UID time/state drift')
                subject = ('uid', p.mpfr.unescape_uid(f[9]).hex())
                require(subject in expected, 'UID bytes drift')
                seen.append(subject)
            else:
                require(f[1] == 'e' and f[3] == '1' and int(f[5]) == p.KEY_CREATED and
                        f[6] == str(effective[tag]), 'expected expired key and exact effective expiry')
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
                    f[3] == '1' and f[4] == p.PRIMARY[-16:] and f[12] == p.PRIMARY and f[15] == '8' and
                    re.fullmatch('[0-9a-f]{2}x', f[10]) and f[5].isdigit() and not f[6],
                    'strong self certification not checked')
            certs.append((subject, int(f[5]), int(f[10][:2], 16)))
        else:
            raise ValueError('unexpected colon record: ' + tag)
    require(pending is None and Counter(seen) == Counter(expected.keys()) and Counter(certs) == Counter(wanted),
            'missing/duplicate/reassigned self certification')
    return {'primary': p.PRIMARY, 'self_certifications': 2, 'current_key_state': 'expired',
            'packet_declared_expiry': dict(p.EXPIRES), 'listed_effective_expiry': effective,
            'declared_signature_time_in_selected_interval': True, 'historical_validity': 'not-established',
            'cryptography_executed_by_parser': False, 'source_acceptance': 'not-assessed'}


def assess(result, original, filtered, observed_at):
    require(result['failure'] is None and type(result['returncode']) is int and result['returncode'] == 0,
            'incomplete or failed certification invocation')
    require(all(isinstance(result[k], bytes) and len(result[k]) <= p.keys.LIMIT
                for k in ('stdout', 'stderr', 'status')), 'capture bound or type')
    require(len(result['status']) <= 256, 'auxiliary status bound')
    p.inventory(original)
    expired = f'[GNUPG:] KEYEXPIRED {p.EXPIRES["pub"]}\n'.encode()
    considered = f'[GNUPG:] KEY_CONSIDERED {p.PRIMARY} 0\n'.encode()
    # This exact sequence is a narrow observed profile, not a general GnuPG guarantee.
    # No deduplication, arbitrary repetition, discarded failures, or alternate ordering.
    require(result['status'] == expired + considered + expired * 2, 'fixed v3 certification status mismatch')
    checked = certifications(result['stdout'], original, filtered, observed_at)
    return {**checked, 'assessment_profile': PROFILE, 'status_records': 4,
            'key_expiry_status_records': 3, 'detached_signature_checked': False,
            'result': 'fixed-certification-output-matches-offline-candidate'}


def review():
    basis = p.identity((HERE / 'gmp-tool-source-2026-09-29.json.gz').read_bytes())
    require(basis['sha256'] == BASIS_SHA, 'reviewed tool source inventory drift')
    path = historical.run.ROOT / '.tmp/gmp-verification-execution-20260925-attempt2.json'
    old = historical.inspect(path)  # Recheck the old failure and all 17 original command logs first.
    bundle = json.loads(historical.read(path, historical.collector.BUNDLE_LIMIT))
    files = historical.collector.unpack(bundle['files'])
    result = json.loads(files['result.json'])
    case = result['cases'][1]
    number = case['start_command_number']
    invocation = {**case['invocation'], 'status': files['certifications.status'],
                  'stdout': files[f'{number:03d}.stdout'], 'stderr': files[f'{number:03d}.stderr']}
    candidate = assess(invocation, files['inputs/gmp.strong.gpg'], files['inputs/gmp.self.gpg'], case['observed_at'])
    return {'kind': 'diagnostic-gmp-certification-v3-offline-review', 'historical_bundle': old['bundle'],
            'historical_result': old['result'], 'historical_assessment_passed': False,
            'historical_rejections': old['cases'][1]['assessment'], 'candidate_assessment': candidate,
            'tool_source_inventory': basis,
            'candidate_method': p.identity(Path(__file__).read_bytes()),
            'new_cryptography_executed': False, 'execution_entry_prepared': False,
            'source_acceptance': 'not-assessed', 'historical_validity': 'not-established'}


if __name__ == '__main__':
    print(json.dumps(review(), sort_keys=True, indent=2))
