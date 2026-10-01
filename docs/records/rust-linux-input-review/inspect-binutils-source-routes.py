#!/usr/bin/env python3
"""Replay keyserver observations and the rejected Debian archive-equivalence route offline."""
from collections import Counter
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


streams = load('compare-binutils-streams.py')
key_review = load('inspect-binutils-key-inputs.py')
read, identity, require = key_review.read, key_review.identity, key_review.require
KEY_DIRECTORY = ROOT / '.tmp/binutils-keyservers-b1de5c8-20260925'
CHAIN_DIRECTORY = ROOT / '.tmp/binutils-content-chain-b1de5c8-20260925'
GZIP = ROOT / 'artifacts/source-inputs/binutils-inputs-8a610c7-20260925/inputs/binutils-attempt-1.tar.gz'
TARGETS = {
    'ubuntu': {'url': 'https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x' + key_review.PRIMARY,
               'suffix': 'asc', 'limit': 262144},
    'openpgp': {'url': 'https://keys.openpgp.org/vks/v1/by-fingerprint/' + key_review.PRIMARY,
                'suffix': 'asc', 'limit': 262144},
    'debian-xz': {'url': 'https://deb.debian.org/debian/pool/main/b/binutils/binutils_2.44.orig.tar.xz',
                  'suffix': 'tar.xz', 'limit': 27504768},
}


def fetch_record(directory, original_directory, name):
    target = TARGETS[name]
    stem = name + '-attempt-1'
    filename = stem + '.' + target['suffix']
    row = json.loads(read(directory / (stem + '.json'), 16384))
    argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--proto', '=https', '--tlsv1.2',
            '--max-time', '60', '--max-filesize', str(target['limit']), '--output',
            str(original_directory / filename), '--write-out', '%{http_code}\n', target['url']]
    require(row['argv'] == argv and row['target'] == name and row['url'] == target['url'] and
            row['body']['file'] == filename and row['attempt'] == 1 and
            row['method'] == identity(read(HERE / 'fetch-mpc-mpfr-inputs.py')), 'fetch scope drift')
    http = '404' if name == 'openpgp' else '200'
    require(row['exit_code'] == 0 and row['parent_timeout'] is False and row['http_code'] == http and
            row['passed'] is (http == '200') and row['transport_passed'] is (http == '200'), 'fetch outcome drift')
    body = None
    for channel in ('body', 'stdout', 'stderr'):
        raw = read(directory / (filename if channel == 'body' else stem + '.' + channel), target['limit'])
        require(identity(raw) == {k: row[channel][k] for k in ('bytes', 'sha256')}, 'fetch bytes drift')
        if channel == 'body':
            body = raw
        else:
            require(raw.decode('utf-8') == row[channel]['text'], 'fetch stream drift')
            require(channel != 'stdout' or raw == (http + '\n').encode(), 'HTTP output drift')
    return row, body


def inspect(key_directory=KEY_DIRECTORY, chain_directory=CHAIN_DIRECTORY, gzip_path=GZIP):
    fetches, bodies = {}, {}
    for directory, original, names in ((key_directory, KEY_DIRECTORY, ('ubuntu', 'openpgp')),
                                       (chain_directory, CHAIN_DIRECTORY, ('debian-xz',))):
        plan = json.loads(read(directory / 'fetch-plan.json', 16384))
        require(plan['directory'] == str(original) and plan['targets'] == {n: TARGETS[n] for n in names} and
                plan['method'] == identity(read(HERE / 'fetch-mpc-mpfr-inputs.py')), 'fetch plan drift')
        require(original != KEY_DIRECTORY or plan['expected_primary'] == key_review.PRIMARY,
                'keyserver fingerprint plan drift')
        for name in names:
            fetches[name], bodies[name] = fetch_record(directory, original, name)
    require(identity(bodies['ubuntu']) == {'bytes': 5726, 'sha256':
            '2ce8ad1dd1bf31ea10f213e3bf88d23994184124c68691f8a69c6010c3e0aab7'}, 'keyserver input drift')
    inventory = key_review.keys.inventory(bodies['ubuntu'], key_review.PRIMARY)
    require(len(inventory['blocks']) == 1, 'unexpected additional primary')
    block = inventory['blocks'][0]
    old = json.loads(read(HERE / 'binutils-key-inputs-2026-09-25.json'))['inventory']['blocks'][0]
    self_bodies = lambda b: [s['signature_body'] for s in b['signatures'] if s['declared_self_signature']]
    key_comparison = {'same_declared_self_signature_bodies': self_bodies(block) == self_bodies(old),
                      'same_key_packets': block['keys'] == old['keys'],
                      'third_party_declared_digest_counts': dict(Counter(str(s['digest_algorithm'])
                          for s in block['signatures'] if not s['declared_self_signature'])),
                      'third_party_certifications_accepted': False}
    remaining = load('inspect-musl-remaining-sources.py').inspect()
    encode = lambda value: (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    require(encode(remaining) == read(HERE / 'musl-remaining-sources-2026-09-16.json'), 'complete index replay drift')
    candidates = [c for d in remaining['dependencies'] if d['dependency'] == 'binutils'
                  for c in d['index_candidates'] if c['version'] == '2.44-3']
    require(len(candidates) == 1, 'ambiguous index candidate')
    candidate = candidates[0]
    plan = json.loads(read(chain_directory / 'fetch-plan.json', 16384))
    require(plan['index_entry'] == candidate and plan['sources'] == remaining['sources'], 'index plan drift')
    require(candidate['originals'] == {'binutils_2.44.orig.tar.xz': identity(bodies['debian-xz'])},
            'download not identical to indexed original')
    historical = load('collect-musl-verification-execution.py').collect_success()
    history_bytes = encode(historical)
    require(history_bytes == read(HERE / 'musl-verification-success-2026-09-16.json'), 'historical execution replay drift')
    gzip_raw = read(gzip_path, streams.LIMITS['compressed'])
    require(identity(gzip_raw) == streams.content.inputs.ARCHIVE, 'fixed recipe gzip drift')
    old_content, _ = streams.content.inspect(gzip_path)
    return {'kind': 'diagnostic-binutils-source-routes-v1', 'fetches': fetches,
            'keyserver_inventory': inventory, 'key_comparison': key_comparison,
            'index_candidate': candidate, 'sources': remaining['sources'],
            'historical_debian_execution': identity(history_bytes), 'historical_execution_replay_equal': True,
            'stream_comparison': streams.compare(gzip_raw, bodies['debian-xz']),
            'member_comparison': streams.compare_members(bodies['debian-xz'], old_content),
            'cryptography_reexecuted': False, 'source_acceptance': 'not-assessed',
            'methods': {name: identity(read(HERE / name)) for name in
                        ('inspect-binutils-source-routes.py', 'compare-binutils-streams.py',
                         'inspect-binutils-content.py', 'inspect-mpc-mpfr-key-inputs.py',
                         'inspect-musl-remaining-sources.py', 'collect-musl-verification-execution.py')}}


if __name__ == '__main__':
    print(json.dumps(inspect(), sort_keys=True, indent=2))
