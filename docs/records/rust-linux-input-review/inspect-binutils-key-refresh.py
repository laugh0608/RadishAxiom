#!/usr/bin/env python3
"""Select one v4 public key from a bounded GNU keyring; no trust import or cryptography."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('prior', HERE / 'inspect-binutils-key-inputs.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
keys = prior.keys.keys
require, identity, read = prior.require, prior.identity, prior.read
DEFAULT = HERE.parents[2] / '.tmp/binutils-key-refresh-383b570-20260925'
TARGETS = {
    'savannah-release': {'url': 'https://savannah.gnu.org/project/release-gpgkeys.php?group=binutils&download=1',
                         'suffix': 'asc', 'limit': 262144},
    'gnu-keyring': {'url': 'https://ftp.gnu.org/gnu/gnu-keyring.gpg', 'suffix': 'gpg', 'limit': 8388608},
}
RING = {'bytes': 3687794, 'sha256': 'b136fbe57ade4ee5270ca66c402cae7b50349fd07646b5b3de7962d58d4df608'}
LIMIT, PACKETS = 8388608, 50000


def select(raw, expected):
    require(0 < len(raw) <= LIMIT, 'keyring size bound')
    offset, current, starts = 0, None, 0
    counts, selected, selected_rows = Counter(), [], []
    primary_count = 0
    while offset < len(raw):
        start = offset
        header, offset = keys.take(raw, offset, 1)
        header = header[0]
        require(header & 128, 'invalid keyring packet header')
        if header & 64:
            tag = header & 63
            size, offset = keys.length(raw, offset)
        else:
            tag, encoding = (header >> 2) & 15, header & 3
            require(encoding != 3, 'indeterminate packet length')
            field, offset = keys.take(raw, offset, 1 << encoding)
            size = int.from_bytes(field, 'big')
        body, offset = keys.take(raw, offset, size)
        require(tag in {2, 6, 12, 13, 14, 17} and body, 'unexpected or secret keyring packet')
        counts[tag] += 1
        require(sum(counts.values()) <= PACKETS, 'keyring packet count bound')
        if tag == 6:
            # Legacy/non-v4 blocks are framed only, never treated as the target.
            current = keys.fingerprint(body) if body[0] == 4 else 'non-v4'
            primary_count += 1
            if current == expected:
                starts += 1
                require(starts == 1, 'duplicate target primary')
        require(current is not None, 'material before primary')
        if current == expected:
            selected_rows.append({'tag': tag, 'offset': start, 'bytes': offset - start,
                                  'packet': identity(raw[start:offset]), 'excluded_local_trust': tag == 12})
            if tag != 12:
                selected.append(raw[start:offset])
    require(starts == 1, 'target primary absent')
    public = b''.join(selected)
    # Existing narrow parser still validates selected public packets and its bounds.
    require(set(keys.key_blocks(public)) == {expected}, 'selected key profile mismatch')
    return public, {'packet_counts': {str(k): v for k, v in sorted(counts.items())},
                    'primary_count': primary_count, 'selected_packets': selected_rows,
                    'selected_public': identity(public), 'unrelated_key_semantics_checked': False}


def compare_public_material(current, previous):
    # Old/new OpenPGP packet headers may differ while carrying identical bodies.
    # Compare ordered tags and complete bodies, never only fingerprints or issuers.
    current_packets, previous_packets = keys.packets(current), keys.packets(previous)
    require([(tag, body) for tag, body, _ in current_packets] ==
            [(tag, body) for tag, body, _ in previous_packets],
            'selected public packet bodies differ: new review required')
    return {'public_packet_bodies_equal_to_previous': True,
            'public_packet_encoding_equal_to_previous': current == previous,
            'ordered_public_packets': [{'tag': tag, 'body': identity(body)} for tag, body, _ in current_packets]}


def inspect(directory=DEFAULT, previous=prior.DEFAULT):
    plan = json.loads(read(directory / 'fetch-plan.json', 16384))
    method = identity(read(HERE / 'fetch-mpc-mpfr-inputs.py'))
    require(plan['targets'] == TARGETS and plan['directory'] == str(DEFAULT) and
            plan['expected_primary'] == prior.PRIMARY and plan['method'] == method, 'fetch plan drift')
    fetches, bodies = [], {}
    for name, target in TARGETS.items():
        stem = name + '-attempt-1'
        row = json.loads(read(directory / (stem + '.json'), 16384))
        filename = stem + '.' + target['suffix']
        argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--proto', '=https', '--tlsv1.2',
                '--max-time', '60', '--max-filesize', str(target['limit']), '--output', str(DEFAULT / filename),
                '--write-out', '%{http_code}\n', target['url']]
        require(row['target'] == name and row['url'] == target['url'] and row['attempt'] == 1 and
                row['argv'] == argv and row['body']['file'] == filename and row['method'] == method,
                'fetch scope drift')
        expected_http = '404' if name == 'savannah-release' else '200'
        passed = expected_http == '200'
        require(row['exit_code'] == 0 and row['http_code'] == expected_http and
                row['parent_timeout'] is False and row['passed'] is passed and
                row['transport_passed'] is passed, 'recorded fetch outcome changed')
        for channel in ('body', 'stdout', 'stderr'):
            raw = read(directory / (filename if channel == 'body' else stem + '.' + channel), target['limit'])
            require(identity(raw) == {k: row[channel][k] for k in ('bytes', 'sha256')}, 'fetch bytes drift')
            if channel == 'body':
                bodies[name] = raw
            else:
                require(raw.decode('utf-8') == row[channel]['text'], 'fetch stream drift')
                require(channel != 'stdout' or raw == (expected_http + '\n').encode(), 'HTTP stream drift')
        fetches.append(row)
    require(identity(bodies['gnu-keyring']) == RING, 'fixed keyring identity mismatch')
    public, selected = select(bodies['gnu-keyring'], prior.PRIMARY)
    old = read(previous / 'public-key-attempt-1.asc', 262144)
    require(identity(old) == {'bytes': 3106, 'sha256':
            '2cad260c1b933559858ef82943b72049af96426138a99c299f63fabda2a305b4'}, 'previous attachment drift')
    comparison = compare_public_material(public, prior.keys.armor(old))
    return {'kind': 'diagnostic-binutils-key-refresh-v1', 'fetches': fetches, 'selection': selected,
            'previous_attachment': identity(old), 'comparison': comparison,
            'previous_inventory': prior.keys.inventory(old, prior.PRIMARY),
            'new_strong_self_certification_found': False, 'savannah_key_obtained': False,
            'public_key_identity_accepted': False, 'cryptography_executed': False,
            'source_acceptance': 'not-assessed',
            'methods': {name: identity(read(HERE / name)) for name in
                        ('inspect-binutils-key-refresh.py', 'inspect-binutils-key-inputs.py',
                         'inspect-mpc-mpfr-key-inputs.py', 'inspect-musl-verification-keys.py',
                         'inspect-musl-verification-status.py', 'retain-musl-verifier-inputs.py')}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT)
    parser.add_argument('--previous', type=Path, default=prior.DEFAULT)
    args = parser.parse_args()
    print(json.dumps(inspect(args.directory, args.previous), sort_keys=True, indent=2))
