#!/usr/bin/env python3
"""Bounded v4 public-key structure and GnuPG colon checks for two fixed roles; no cryptography."""
from collections import Counter
import hashlib
import importlib.util
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('signature_status', HERE / 'inspect-musl-verification-status.py')
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)
require = status.require
LIMIT = 1024**2


def take(raw, offset, size):
    require(0 <= size and offset + size <= len(raw), 'truncated public-key material')
    return raw[offset:offset + size], offset + size


def length(raw, offset):
    first, offset = take(raw, offset, 1)
    if first[0] < 192:
        return first[0], offset
    if first[0] < 224:
        second, offset = take(raw, offset, 1)
        return (first[0] - 192) * 256 + second[0] + 192, offset
    require(first[0] == 255, 'partial packet length outside fixed profile')
    size, offset = take(raw, offset, 4)
    return int.from_bytes(size, 'big'), offset


def packets(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= LIMIT, 'public-key input bound')
    offset, found = 0, []
    while offset < len(raw):
        start = offset
        header, offset = take(raw, offset, 1)
        header = header[0]
        require(header & 128, 'invalid packet header')
        if header & 64:
            tag = header & 63
            size, offset = length(raw, offset)
        else:
            tag, encoding = (header >> 2) & 15, header & 3
            require(encoding != 3, 'indeterminate packet length')
            field, offset = take(raw, offset, 1 << encoding)
            size = int.from_bytes(field, 'big')
        body, offset = take(raw, offset, size)
        require(tag in {2, 6, 13, 14} and body, 'unexpected or secret key packet')
        found.append((tag, body, raw[start:offset]))
        require(len(found) <= 512, 'too many public-key packets')
    return found


def fingerprint(body):
    require(6 <= len(body) <= 65535 and body[0] == 4, 'only bounded v4 public keys supported')
    # RFC 4880 v4 key identity only; this does not accept SHA-1 signatures.
    return hashlib.sha1(b'\x99' + len(body).to_bytes(2, 'big') + body).hexdigest().upper()


def key_blocks(raw):
    blocks, current = {}, None
    for tag, body, packet in packets(raw):
        if tag == 6:
            current = fingerprint(body)
            require(current not in blocks, 'duplicate primary key')
            blocks[current] = b''
        require(current is not None, 'material before primary key')
        blocks[current] += packet
    return blocks


def subpackets(raw):
    offset, found = 0, []
    while offset < len(raw):
        size, offset = length(raw, offset)
        require(size > 0, 'empty signature subpacket')
        body, offset = take(raw, offset, size)
        found.append((body[0] & 127, body[1:]))
        require(len(found) <= 128, 'too many signature subpackets')
    return found


def signature(body):
    require(len(body) >= 10 and body[0] == 4, 'unsupported signature packet')
    require(body[1] not in {0x20, 0x28, 0x30}, 'revocation in original material')
    require(body[3] in {8, 9, 10}, 'weak signature digest in original material')
    offset, parts = 4, []
    for _ in range(2):
        size, offset = take(body, offset, 2)
        data, offset = take(body, offset, int.from_bytes(size, 'big'))
        parts.extend(subpackets(data))
    require(len(body) - offset >= 4, 'missing signature hash or MPI material')
    issuers = [value.hex().upper() for kind, value in parts if kind == 16 and len(value) == 8]
    fprs = [value[1:].hex().upper() for kind, value in parts if kind == 33 and len(value) == 21 and value[0] == 4]
    require(len(issuers) <= 1 and len(fprs) <= 1 and (issuers or fprs), 'ambiguous or missing signature issuer')
    require(all((kind != 16 or len(value) == 8) and
                (kind != 33 or len(value) == 21 and value[0] == 4) for kind, value in parts),
            'malformed signature issuer')
    require(not issuers or not fprs or issuers[0] == fprs[0][-16:], 'issuer identity disagreement')
    return {'class': body[1], 'digest': body[3], 'issuer': fprs[0] if fprs else issuers[0],
            'embedded': [value for kind, value in parts if kind == 32]}


def inventory(raw, primary):
    require(set(key_blocks(raw)) == {primary}, 'wrong raw primary key')
    signer = status.SIGNERS[primary][0]
    subject, keys, uids, certs, self_bodies, embedded_count = None, [], [], [], [], 0
    revokers = []
    for tag, body, _ in packets(raw):
        if tag in {6, 14}:
            subject = ('pub' if tag == 6 else 'sub', fingerprint(body))
            keys.append((tag, body))
        elif tag == 13:
            require(subject is not None and subject[0] != 'sub', 'UID after subkey')
            subject = ('uid', body.hex())
            uids.append(body)
        else:
            sig = signature(body)
            require(subject is not None and (subject[0], sig['class']) in
                    {('pub', 0x1f), ('uid', 0x10), ('uid', 0x11), ('uid', 0x12), ('uid', 0x13), ('sub', 0x18)},
                    'signature in wrong original context')
            if sig['issuer'] in {primary, primary[-16:]}:
                certs.append((subject[0], sig['class']))
                self_bodies.append(body)
                # Revocation-key designations are not revocations. Bind colon rvk rows to raw subpackets.
                offset = 4
                size, offset = take(body, offset, 2)
                hashed, _ = take(body, offset, int.from_bytes(size, 'big'))
                for kind, value in subpackets(hashed):
                    if kind == 12:
                        require(len(value) == 22 and value[0] == 0x80, 'unsupported designated revoker')
                        revokers.append((str(value[1]), value[2:].hex().upper(), '80'))
            for embedded in sig['embedded']:
                require(subject == ('sub', signer) and sig['class'] == 0x18 and
                        sig['issuer'] in {primary, primary[-16:]}, 'unexpected cross-certification context')
                back = signature(embedded)
                require(back['class'] == 0x19 and not back['embedded'] and
                        back['issuer'] in {signer, signer[-16:]}, 'invalid back-signature structure')
                embedded_count += 1
    expected = [primary] if signer == primary else [primary, signer]
    require([fingerprint(body) for _, body in keys] == expected and len(uids) == 1,
            'unexpected key/subkey/UID inventory')
    require(('uid', 0x13) in certs and (signer == primary or ('sub', 0x18) in certs),
            'missing original self-certification or subkey binding')
    require(embedded_count == (0 if signer == primary else 1), 'missing or duplicate cross-certification')
    return {'keys': keys, 'uids': uids, 'self_bodies': self_bodies, 'certs': certs, 'revokers': revokers}


def filtered_material(original, filtered, primary):
    before, after = inventory(original, primary), inventory(filtered, primary)
    require(before['keys'] == after['keys'] and before['uids'] == after['uids'] and
            Counter(before['self_bodies']) == Counter(after['self_bodies']),
            'import discarded or changed original self-certifications')
    require(sum(tag == 2 for tag, _, _ in packets(filtered)) == len(after['self_bodies']),
            'foreign signature remains in self-only material')
    return before


def corrupt_backsignature(raw, primary):
    """Mutate one signature-value byte in the unhashed back-signature, preserving the binding's signed data."""
    inventory(raw, primary)
    candidates = []
    for tag, body, _ in packets(raw):
        if tag != 2 or body[1] != 0x18:
            continue
        size, offset = take(body, 4, 2)
        hashed, offset = take(body, offset, int.from_bytes(size, 'big'))
        require(not any(kind == 32 for kind, _ in subpackets(hashed)), 'back-signature unexpectedly hashed')
        size, offset = take(body, offset, 2)
        unhashed, _ = take(body, offset, int.from_bytes(size, 'big'))
        candidates.extend(value for kind, value in subpackets(unhashed) if kind == 32)
    require(len(candidates) == 1 and raw.count(candidates[0]) == 1, 'back-signature mutation target not unique')
    target = raw.index(candidates[0]) + len(candidates[0]) - 1
    mutated = raw[:target] + bytes([raw[target] ^ 1]) + raw[target + 1:]
    inventory(mutated, primary)
    return mutated


def text_lines(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= LIMIT and raw.endswith(b'\n'), 'colon stream bound')
    text = raw.decode('utf-8', errors='strict')
    require(all(c == '\n' or ord(c) >= 32 and ord(c) != 127 for c in text) and
            not any(c in text for c in '\u0085\u2028\u2029'), 'invalid colon record separator')
    lines = text.split('\n')[:-1]
    require(len(lines) <= 4096 and all(len(line.encode()) <= 8192 for line in lines), 'colon record bound')
    return lines


def certifications(raw, original, filtered, primary, observed_at):
    material = filtered_material(original, filtered, primary)
    require(type(observed_at) is int and observed_at > 0, 'invalid key observation time')
    subject, pending_id, keys, uids, certs = None, None, [], 0, []
    revokers, trust_seen = [], False
    for line in text_lines(raw):
        f = line.split(':')
        tag = f[0]
        if tag == 'tru':
            require(subject is None and not trust_seen and len(f) >= 8 and f[1] in {'', 'o', 't'} and
                    all(v.isdigit() for v in f[2:8]), 'unexpected trust database annotation')
            trust_seen = True
        elif tag == 'rvk':
            require(subject == 'pub' and len(f) >= 11, 'revoker outside primary key')
            revokers.append((f[3], f[9], f[10]))
        elif tag in {'pub', 'sub', 'uid'}:
            require(pending_id is None and len(f) >= 12 and f[1] in {'-', 'o', 'q', 'm', 'f', 'u'},
                    'invalid/revoked/expired key or UID')
            require(f[5].isdigit() and 0 < int(f[5]) <= observed_at and
                    (not f[6] or f[6].isdigit() and observed_at < int(f[6])), 'invalid key or UID time')
            require('D' not in f[11], 'disabled key')
            subject = tag
            if tag == 'uid':
                uids += 1
            else:
                pending_id = f[4]
        elif tag == 'fpr':
            require(pending_id is not None and len(f) >= 10 and re.fullmatch('[0-9A-F]{40}', f[9]) and
                    pending_id == f[9][-16:], 'unpaired or inconsistent fingerprint')
            keys.append((subject, f[9]))
            pending_id = None
        elif tag == 'sig':
            require(pending_id is None and len(f) >= 16 and f[1] == '!' and f[12] == primary and
                    f[4] == primary[-16:] and f[15] in {'8', '9', '10'}, 'invalid self-certification result')
            require(f[5].isdigit() and 0 < int(f[5]) <= observed_at and
                    (not f[6] or f[6].isdigit() and observed_at < int(f[6])), 'invalid certification time')
            require(re.fullmatch('[0-9a-f]{2}[xl]', f[10]), 'invalid certification class')
            certs.append((subject, int(f[10][:2], 16)))
        else:
            raise ValueError('unexpected colon record: ' + tag)
    expected = [('pub' if tag == 6 else 'sub', fingerprint(body)) for tag, body in material['keys']]
    require(pending_id is None and keys == expected and uids == 1 and Counter(certs) == Counter(material['certs']) and
            Counter(revokers) == Counter(material['revokers']),
            'GnuPG did not check every original self-certification in its context')
    return {'primary': primary, 'signer': status.SIGNERS[primary][0], 'self_certifications': len(certs),
            'original_material_examined': True, 'cryptography_executed_by_parser': False}
