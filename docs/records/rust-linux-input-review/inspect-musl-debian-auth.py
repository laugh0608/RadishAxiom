#!/usr/bin/env python3
"""Bind trusted offline observations to this exact Debian/musl diagnostic."""
import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('debian_chain', ROOT / 'scripts/inspect-debian-source-chain.py')
chain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chain)
ARCHIVE = '04B54C3CDCA79751B16BC6B5225629DF75B188BD'
RELEASE = '41587F7DB8C774BCCF131416762F67A0B2C39DE4'
ROLES = {ARCHIVE, RELEASE}
ALLOWED = ROLES | {'B8B80B5B623EAB6AD8775C45B7C5D7D6350947F8'}
STRONG = {'8', '9', '10'}
SOURCE = {'bytes': 1080786, 'sha256': 'a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4'}
SOURCE_NAMES = {'musl_1.2.5-3.1~deb13u1.dsc', 'musl_1.2.5.orig.tar.gz',
                'musl_1.2.5.orig.tar.gz.asc', 'musl_1.2.5-3.1~deb13u1.debian.tar.xz'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def original_digest(value):
    # The historical three-package parser intentionally has a narrower path
    # alphabet. Select these four literal names, without widening its policy.
    found = {}
    original = None
    for line in value.splitlines():
        if not line:
            continue
        fields = line.split()
        require(len(fields) == 3 and re.fullmatch('[0-9a-f]{64}', fields[0])
                and fields[1].isdigit() and fields[2] in SOURCE_NAMES,
                'unexpected source checksum row')
        require(fields[2] not in found, 'duplicate source checksum row')
        found[fields[2]] = fields
        if fields[2] == 'musl_1.2.5.orig.tar.gz':
            original = line
    require(found.keys() == SOURCE_NAMES, 'missing source checksum row')
    return chain.checksums(original)['musl_1.2.5.orig.tar.gz']


def signatures(status, now):
    found = {}
    for line in status.splitlines():
        fields = line.split()
        require(len(fields) >= 2 and fields[0] == '[GNUPG:]', 'malformed status')
        require(fields[1] not in {'BADSIG', 'ERRSIG', 'EXPSIG', 'EXPKEYSIG', 'REVKEYSIG',
                                  'NO_PUBKEY', 'FAILURE', 'ERROR', 'KEYEXPIRED', 'SIGEXPIRED'},
                'GnuPG failure status')
        if fields[1] == 'VALIDSIG':
            require(len(fields) == 12 and fields[-1] in ALLOWED and fields[9] in STRONG
                    and fields[10] == '01' and re.fullmatch('[0-9A-F]{40}', fields[2]),
                    'unexpected release signature')
            require(fields[-1] not in found, 'duplicate signature role')
            require(fields[4].isdigit() and int(fields[4]) <= now and fields[5].isdigit()
                    and (int(fields[5]) == 0 or int(fields[5]) > now), 'signature time invalid')
            found[fields[-1]] = {'signer': fields[2], 'digest_algorithm': fields[9]}
    require(ROLES <= found.keys(), 'missing required trixie roles')
    return found


def certifications(key, primary, signer, now):
    for name in ('certifications', 'export', 'packets'):
        require(key[name]['exit_code'] == 0, 'key command failed: ' + name)
    subject, fingerprint, pubs, uids = None, None, 0, 0
    keys, certs = {}, []
    uid_certified, bound = False, False
    for line in key['certifications']['stdout'].splitlines():
        f = line.split(':')
        if f[0] in {'pub', 'sub', 'uid'}:
            require(len(f) >= 12 and f[1] not in {'r', 'e', 'd', 'i'}, 'invalid key/UID state')
            require(f[5].isdigit() and int(f[5]) <= now and
                    (not f[6] or f[6].isdigit() and int(f[6]) > now), 'key/UID time invalid')
            subject, fingerprint = f[0], None
            if subject == 'pub':
                pubs += 1
            if subject == 'uid':
                uids += 1
            if subject in {'pub', 'sub'}:
                require('D' not in f[11], 'disabled key')
        elif f[0] == 'fpr':
            require(subject in {'pub', 'sub'} and fingerprint is None
                    and re.fullmatch('[0-9A-F]{40}', f[9]), 'unexpected key fingerprint')
            fingerprint = f[9]
            require(fingerprint not in keys, 'duplicate key fingerprint')
            keys[fingerprint] = subject
            if subject == 'pub':
                require(fingerprint == primary, 'wrong primary key')
        elif f[0] in {'rev', 'rvs'}:
            raise ValueError('revocation record')
        elif f[0] == 'sig':
            require(len(f) >= 16 and f[1] == '!' and f[12] == primary and f[15] in STRONG,
                    'unverified, foreign or weak self-certification')
            require(f[5].isdigit() and int(f[5]) <= now and
                    (not f[6] or f[6].isdigit() and int(f[6]) > now), 'certification time invalid')
            cls = f[10][:2]
            require((subject, cls) in {('pub', '1f'), ('uid', '13'), ('sub', '18')},
                    'unexpected certification context')
            certs.append({'subject': subject, 'fingerprint': fingerprint,
                          'class': cls, 'digest_algorithm': f[15]})
            if subject == 'uid':
                uid_certified = True
            if subject == 'sub' and fingerprint == signer:
                bound = True
    require(pubs == 1 and uids == 1 and uid_certified and signer in keys,
            'missing key or UID self-certification')
    require(signer == primary or bound, 'signing subkey is not bound')
    packets = key['packets']['stdout']
    require(not re.search(r'sigclass 0x(?:20|28|30)', packets), 'revocation packet')
    digests = re.findall(r'digest algo (\d+)', packets)
    require(bool(digests) and set(digests) <= STRONG, 'weak or missing original packet digest')
    embedded = re.findall(r'subpkt 32 len \d+ \(signature: v4, class 0x19, algo \d+, digest algo (\d+)\)', packets)
    require(signer == primary or len(embedded) == 1 and embedded[0] in STRONG,
            'missing or weak subkey cross-certification')
    return {'self_certifications': certs, 'original_packet_digest_algorithms': sorted(set(digests)),
            'embedded_cross_certification_digests': embedded}


def inspect(directory, source=None):
    raw = (directory / 'offline-invocation-3.stdout').read_bytes()
    observation = json.loads(raw)
    require(observation['exit_code'] == 0 and 'error' not in observation, 'collector failed')
    require(observation['method_sha256'] == chain.sha256((HERE / 'collect-musl-debian-auth.py').read_bytes()),
            'collector method drift')
    for name in ('key_import', 'self_key_import', 'verification'):
        require(observation[name]['exit_code'] == 0, 'failed GnuPG operation')
    for name, expected in observation['inputs'].items():
        chain.hash_file(directory / name, expected)
    require(set(observation['inputs']) == {'InRelease', 'debian-archive-keyring.gpg'}, 'wrong inputs')
    require(observation['inputs']['InRelease']['sha256'] ==
            '98b25b5cd185c59d34aa6e4c3e9b5b8f01bbe9d104fe2dcfbcd30dc0a14a59ed', 'InRelease drift')
    require(observation['inputs']['debian-archive-keyring.gpg']['sha256'] ==
            '506b815cbb32d9b6066b4a2aa524071e071761e7e7f68c3ac74f3061ba852017', 'keyring drift')
    observed = datetime.fromisoformat(observation['observed_at'])
    require(observed.tzinfo is not None and observed <= datetime.now(timezone.utc), 'observation time invalid')
    signers = signatures(observation['verification']['stdout'], observed.timestamp())
    require(set(observation['keys']) == ROLES, 'wrong certification selection')
    binding = {role: certifications(observation['keys'][role], role, signers[role]['signer'], observed.timestamp())
               for role in sorted(ROLES)}
    envelope = (directory / 'InRelease').read_text()
    require(envelope.startswith('-----BEGIN PGP SIGNED MESSAGE-----\n'), 'wrong envelope')
    body = envelope.split('\n\n', 1)[1].split('-----BEGIN PGP SIGNATURE-----\n', 1)[0]
    clear = ''.join(line[2:] if line.startswith('- ') else line for line in body.splitlines(keepends=True))
    require(clear == observation['verified_text'], 'plaintext binding mismatch')
    rows = list(chain.stanzas(clear.splitlines(keepends=True)))
    require(len(rows) == 1, 'duplicate Release stanza')
    release = rows[0]
    for key, value in {'origin': 'Debian', 'label': 'Debian', 'suite': 'stable',
                       'codename': 'trixie', 'version': '13.6', 'acquire-by-hash': 'yes'}.items():
        require(release.get(key) == value, 'Release identity drift: ' + key)
    require(parsedate_to_datetime(release['date']) <= observed, 'future Release')
    if 'valid-until' in release:
        require(parsedate_to_datetime(release['valid-until']) >= observed, 'expired Release')
    index = chain.checksums(release['sha256'])['main/source/Sources.xz']
    require(index['bytes'] <= 16 * 1024**2, 'Sources download limit')
    result = {'kind': 'diagnostic-source-chain', 'acceptance': 'not-assessed',
              'observation_sha256': chain.sha256(raw), 'required_role_bindings': binding,
              'release_signatures': signers, 'release': {k: release.get(k) for k in
                  ('origin', 'suite', 'codename', 'version', 'date', 'valid-until')},
              'sources_index': index, 'sources_url':
                  'https://deb.debian.org/debian/dists/trixie/main/source/by-hash/SHA256/' + index['sha256'],
              'methods': {str(path.relative_to(ROOT)): chain.sha256(path.read_bytes()) for path in
                  [Path(__file__), ROOT / 'scripts/inspect-debian-source-chain.py']},
              'archive_diagnostic_passed': True, 'source_bytes_checked': False}
    if source is not None:
        selected = chain.unique_selection(chain.index_stanzas(directory / 'Sources.xz', index),
                                          {'musl': '1.2.5-3.1~deb13u1'}, binary=False)['musl']
        require(selected.get('directory') == 'pool/main/m/musl', 'source directory drift')
        expected = original_digest(selected['checksums-sha256'])
        require(expected == SOURCE, 'signed original source identity mismatch')
        chain.hash_file(source, SOURCE)
        result.update(source_stanza=selected, source=SOURCE, source_bytes_checked=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.directory, args.source), sort_keys=True, indent=2))
