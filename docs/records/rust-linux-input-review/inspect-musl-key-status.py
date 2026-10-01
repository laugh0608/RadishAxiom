#!/usr/bin/env python3
"""Compare fixed Debian key materials locally; no fresh signature or revocation verification."""
import argparse
import base64
from datetime import datetime, timezone
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('trust_inputs', HERE / 'inspect-musl-trust-inputs.py')
TRUST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRUST)
KEYS = {
    'archive': {
        'bytes': 11861, 'sha256': '6f1d277429dd7ffedcc6f8688a7ad9a458859b1139ffa026d1eeaadcbffb0da7',
        'primary': '04B54C3CDCA79751B16BC6B5225629DF75B188BD',
        'signer': 'B8E5F13176D2A7A75220028078DBA3BC47EF2265',
        'package_name': 'debian-archive-trixie-automatic',
        'url': 'https://ftp-master.debian.org/keys/archive-key-13.asc',
    },
    'release': {
        'bytes': 1384, 'sha256': '4d097bb93f83d731f475c5b92a0c2fcf108cfce1d4932792fca72d00b48d198b',
        'primary': '41587F7DB8C774BCCF131416762F67A0B2C39DE4',
        'signer': '41587F7DB8C774BCCF131416762F67A0B2C39DE4',
        'package_name': 'debian-archive-trixie-stable',
        'url': 'https://ftp-master.debian.org/keys/release-13.asc',
    },
}


class PreText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth, self.count, self.parts = 0, 0, []

    def handle_starttag(self, tag, attrs):
        if tag == 'pre':
            self.depth += 1
            self.count += 1

    def handle_endtag(self, tag):
        if tag == 'pre':
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def decoded_key(data):
    lines = data.decode('ascii').strip().splitlines()
    TRUST.require(lines[0] == '-----BEGIN PGP PUBLIC KEY BLOCK-----' and lines[1] == ''
                  and lines[-1] == '-----END PGP PUBLIC KEY BLOCK-----'
                  and re.fullmatch(r'=[A-Za-z0-9+/]{4}', lines[-2]), 'unexpected fixed armor layout')
    # Raw armored bytes are already pinned and compared with package bytes.
    # Decode the payload for a second byte comparison; the armor CRC is not an authentication check.
    return base64.b64decode(''.join(lines[2:-2]), validate=True)


def inspect(directory, package):
    deb = TRUST.fixed(package, 178572, TRUST.DEB_SHA)
    entries = TRUST.ar_members(deb)
    _, contents = TRUST.read_tar(entries['data.tar.xz'])
    historical_path = HERE / 'musl-debian-execution-2026-09-10.json'
    historical_bytes = historical_path.read_bytes()
    historical = json.loads(historical_bytes)['invocations'][2]['observation']
    result = {
        'kind': 'diagnostic-musl-key-status-materials', 'acceptance': 'not-assessed',
        'methods': {path.name: TRUST.identity(path.read_bytes()) for path in
                    [Path(__file__), HERE / 'inspect-musl-trust-inputs.py']},
        'keyring_package': TRUST.identity(deb),
        'historical_execution': TRUST.identity(historical_bytes),
        'historical_observed_at': historical['observed_at'],
        'keys': {}, 'signature_reverified': False, 'current_revocation_status_verified': False,
    }
    for name, expected in KEYS.items():
        raw = TRUST.fixed(directory / (name + '-attempt-2.asc'), expected['bytes'], expected['sha256'])
        asc_path = 'etc/apt/trusted.gpg.d/' + expected['package_name'] + '.asc'
        binary_path = 'usr/share/keyrings/' + expected['package_name'] + '.gpg'
        binary = decoded_key(raw)
        TRUST.require(raw == contents[asc_path], 'downloaded armor differs from package')
        TRUST.require(binary == contents[binary_path], 'decoded bytes differ from package')
        old = historical['keys'][expected['primary']]
        TRUST.require(TRUST.identity(binary)['sha256'] == old['export_sha256'], 'historical export digest differs')
        expiry = []
        for line in old['certifications']['stdout'].splitlines():
            fields = line.split(':')
            if fields[0] in {'pub', 'sub'}:
                expiry.append({'kind': fields[0], 'key_id': fields[4], 'created_epoch': int(fields[5]),
                               'expires_epoch': int(fields[6]),
                               'expires_at_utc': datetime.fromtimestamp(int(fields[6]), timezone.utc).isoformat()})
        result['keys'][name] = {
            'url': expected['url'], 'armor': TRUST.identity(raw), 'decoded': TRUST.identity(binary),
            'primary_from_historical_observation': expected['primary'],
            'signer_from_historical_observation': expected['signer'],
            'package_armor_path': asc_path, 'package_binary_path': binary_path,
            'armor_and_decoded_bytes_match_package': True, 'matches_historical_export_sha256': True,
            'expiry_from_historical_observation_only': expiry,
        }
    page = TRUST.fixed(directory / 'announcement-attempt-2.html', 29691,
                       '5384b92ed7ad6cf8ce31afff8b5edf88fc0e997ef641c7c43bffc0660d92615d')
    parser = PreText()
    parser.feed(page.decode('utf-8'))
    TRUST.require(parser.count == 1 and parser.depth == 0, 'unexpected announcement pre blocks')
    message = ''.join(parser.parts)
    summary = message.split('- -----BEGIN PGP PUBLIC KEY BLOCK-----', 1)[0]
    TRUST.require(message.startswith('-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA512\n\n')
                  and '-----BEGIN PGP SIGNATURE-----' in message, 'missing signed-message envelope')
    claims = re.findall(r'URL: (https://\S+)\s+SHA256: ([0-9a-f]{64})', summary)
    archive = KEYS['archive']
    TRUST.require(claims.count((archive['url'], archive['sha256'])) == 1
                  and archive['primary'] in summary and archive['signer'] in summary,
                  'announcement archive identity missing')
    result['announcement'] = {
        **TRUST.identity(page),
        'url': 'https://lists.debian.org/debian-devel-announce/2025/04/msg00001.html',
        'archive_primary_and_signer_present': True, 'archive_armor_sha256_claim_matches': True,
        'stable_release_fingerprint_present': KEYS['release']['primary'] in message,
        'declared_message_hash': 'SHA512', 'message_signature_verified': False,
        'third_party_certification_claims_verified': False,
    }
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--keyring-package', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.directory, args.keyring_package), sort_keys=True, indent=2))
