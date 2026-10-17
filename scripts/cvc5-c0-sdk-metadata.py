#!/usr/bin/env python3
"""Fetch and check only pinned C0 metadata; never install, build, or run SDK tools."""
import argparse
import hashlib
import json
import lzma
import re
import signal
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://snapshot.debian.org/archive/debian/20230612T000000Z/'
RETAINED = ROOT / '.tmp/cvc5-c0-sdk-metadata-2026-10-17'
RECORDS = ROOT / 'docs/records/solver-cvc5-c0-2026-10-17'
TARGETS = ('Release', 'InRelease', 'main/binary-arm64/Packages.xz', 'main/source/Sources.xz')
MAX_BYTES = 28 * 1024 * 1024
TIMEOUT = 180
MAX_DECOMPRESSED = 256 * 1024 * 1024
OBSERVATIONS = RECORDS / 'metadata-observations.json'
HEADERS = frozenset(('location', 'date', 'last-modified', 'content-type', 'content-length',
                     'content-encoding', 'etag'))


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


class MetadataRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, relative, redirects, expected_digest=None):
        self.relative, self.redirects, self.expected_digest = relative, redirects, expected_digest

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_redirect(self.relative, newurl, self.expected_digest)
        if newurl == req.full_url or any(newurl == item['from_url'] for item in self.redirects):
            raise ValueError('metadata-redirect-loop')
        if len(self.redirects) >= 5:
            raise ValueError('metadata-redirect-limit')
        self.redirects.append({'status': code, 'from_url': req.full_url, 'to_url': newurl})
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_redirect(relative, newurl, expected_digest=None):
    if relative not in TARGETS:
        raise ValueError('metadata-relative-path-not-allowed')
    parts = urllib.parse.urlsplit(newurl)
    prefix = '/archive/debian/'
    tail = '/dists/bookworm/' + relative
    middle = parts.path[len(prefix):-len(tail)]
    basenames = [relative.rsplit('/', 1)[-1]]
    if expected_digest is not None:
        if relative not in TARGETS[2:] or not re.fullmatch('[0-9a-f]{64}', expected_digest):
            raise ValueError('invalid-release-declared-redirect-digest')
        basenames.append(expected_digest)
    content_path = any(re.fullmatch(r'/file/[0-9a-f]{40}/' + re.escape(name), parts.path) for name in basenames)
    archive_path = (parts.path.startswith(prefix) and parts.path.endswith(tail) and len(middle) == 16
                    and re.fullmatch(r'[0-9]{8}T[0-9]{6}Z', middle) and middle <= '20230612T000000Z')
    if (parts.scheme != 'https' or parts.netloc != 'snapshot.debian.org'
            or parts.query or parts.fragment or not (content_path or archive_path)):
        raise ValueError('redirect-outside-pinned-metadata-path: ' + newurl)


def relevant_headers(headers):
    return {key.lower(): value for key, value in headers.items() if key.lower() in HEADERS}


def sanitize_headers(value):
    if isinstance(value, dict):
        return {key: relevant_headers(item) if key == 'response_headers' else sanitize_headers(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_headers(item) for item in value]
    return value


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate-json-key')
        result[key] = value
    return result


def read_manifest():
    with (RETAINED / 'fetch-observations.json').open('rb') as stream:
        raw = stream.read(1024 * 1024 + 1)
    if not 0 < len(raw) <= 1024 * 1024:
        raise ValueError('fetch-manifest-size-budget')
    value = json.loads(raw.decode(), object_pairs_hook=reject_duplicates, parse_constant=reject_json_constant)
    if not isinstance(value, dict):
        raise ValueError('fetch-manifest-object-required')
    return value, raw


def reject_json_constant(value):
    raise ValueError('nonfinite-json-number: ' + value)


def validate_manifest_policy(manifest, complete):
    if (manifest.get('format') != 'radishaxiom-private-cvc5-c0-sdk-metadata'
            or manifest.get('version') != '0.1' or manifest.get('complete') is not complete
            or manifest.get('base_url') != BASE or manifest.get('signature_authentication') != 'not-established'):
        raise ValueError('metadata-not-complete-or-policy-drift')
    for key, wanted in (('max_total_bytes', MAX_BYTES), ('timeout_seconds_per_item', TIMEOUT),
                        ('retries', 0), ('fallback_sources', 0)):
        if type(manifest.get(key)) is not int or manifest[key] != wanted:
            raise ValueError('metadata-numeric-policy-drift: ' + key)
    total = manifest.get('total_response_body_bytes')
    if type(total) is not int or not 0 <= total <= MAX_BYTES:
        raise ValueError('metadata-total-byte-count-or-budget')


def deadline(signum, frame):
    raise TimeoutError('metadata-item-total-deadline')


def deb822(raw):
    text = raw.decode('utf-8', errors='strict')
    if '\r' in text or '\x00' in text:
        raise ValueError('invalid-control-in-deb822')
    rows = []
    for block in text.strip('\n').split('\n\n'):
        row, last = {}, None
        for line in block.splitlines():
            if line.startswith((' ', '\t')):
                if last is None:
                    raise ValueError('orphan-deb822-continuation')
                row[last] += '\n' + line[1:]
            else:
                key, separator, value = line.partition(':')
                if not separator or not re.fullmatch(r'[A-Za-z0-9-]+', key) or key in row:
                    raise ValueError('malformed-or-duplicate-deb822-field')
                row[key], last = value.lstrip(' '), key
        rows.append(row)
    return rows


def decompress(raw):
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=128 * 1024 * 1024)
    try:
        decoded = decoder.decompress(raw, max_length=MAX_DECOMPRESSED + 1)
    except lzma.LZMAError as error:
        raise ValueError('invalid-xz') from error
    if len(decoded) > MAX_DECOMPRESSED:
        raise ValueError('decompressed-index-budget')
    if not decoder.eof or decoder.unused_data:
        raise ValueError('truncated-or-multiple-xz-streams-or-trailing-data')
    return decoded


def signed_release_body(raw):
    marker = b'\n\n'
    if not raw.startswith(b'-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA256\n'):
        raise ValueError('unsupported-inrelease-cleartext-header')
    body = raw.split(marker, 1)[1].split(b'-----BEGIN PGP SIGNATURE-----\n', 1)
    if len(body) != 2 or not body[1].endswith(b'-----END PGP SIGNATURE-----\n'):
        raise ValueError('incomplete-inrelease-signature-envelope')
    return b'\n'.join(line[2:] if line.startswith(b'- ') else line for line in body[0].split(b'\n'))


def release_hashes(raw):
    rows = deb822(raw)
    if len(rows) != 1:
        raise ValueError('release-multiple-stanzas')
    release = rows[0]
    if release.get('Codename') != 'bookworm' or 'arm64' not in release.get('Architectures', '').split() or 'main' not in release.get('Components', '').split():
        raise ValueError('release-distribution-identity-drift')
    hashes = {}
    for line in release['SHA256'].strip().splitlines():
        sha, size, path = line.split()
        if path in hashes or not re.fullmatch('[0-9a-f]{64}', sha) or not size.isdigit():
            raise ValueError('invalid-or-duplicate-release-sha256-path')
        hashes[path] = (sha, int(size))
    return release, hashes


def validate_observation(relative, row, expected_digest=None):
    if (row.get('relative_path') != relative or row.get('requested_url') != BASE + 'dists/bookworm/' + relative
            or row.get('retained_file') != relative.replace('/', '__') or row.get('status') != 'obtained'
            or type(row.get('http_status')) is not int or row['http_status'] != 200
            or type(row.get('bytes')) is not int or row['bytes'] <= 0):
        raise ValueError('metadata-origin-target-status-or-size-drift')
    redirects = row.get('redirects')
    if not isinstance(redirects, list) or len(redirects) > 5:
        raise ValueError('metadata-redirect-list-or-limit')
    previous = row['requested_url']
    seen = {previous}
    for redirect in redirects:
        if (redirect.get('from_url') != previous or type(redirect.get('status')) is not int
                or redirect['status'] not in (301, 302, 303, 307, 308)):
            raise ValueError('metadata-redirect-chain-disconnected-or-status')
        target = redirect['to_url']
        validate_redirect(relative, target, expected_digest)
        if target in seen:
            raise ValueError('metadata-redirect-loop')
        seen.add(target)
        previous = target
    if row.get('final_url') != previous:
        raise ValueError('metadata-final-url-not-redirect-chain-end')
    headers = relevant_headers(row.get('response_headers', {}))
    length = headers.get('content-length')
    if length is not None and (not length.isdigit() or int(length) != row['bytes']):
        raise ValueError('metadata-content-length-mismatch')
    if headers.get('content-encoding', 'identity') != 'identity':
        raise ValueError('unexpected-metadata-content-encoding')
    elapsed = row.get('elapsed_seconds')
    if type(elapsed) not in (int, float) or not 0 <= elapsed <= TIMEOUT + 1:
        raise ValueError('invalid-metadata-elapsed-time')


def read_verified_metadata():
    manifest, manifest_raw = read_manifest()
    validate_manifest_policy(manifest, complete=True)
    data, total, hashes = {}, 0, {}
    if len(manifest['observations']) != len(TARGETS):
        raise ValueError('metadata-target-count')
    for relative, row in zip(TARGETS, manifest['observations']):
        validate_observation(relative, row, hashes.get(relative, (None,))[0])
        path = RETAINED / row['retained_file']
        with path.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        total += len(raw)
        if len(raw) != row['bytes'] or digest(raw) != row['raw_digest'] or total > MAX_BYTES:
            raise ValueError('retained-metadata-bytes-mismatch')
        data[relative] = raw
        if relative == 'Release':
            release, hashes = release_hashes(raw)
    if total != manifest['total_response_body_bytes']:
        raise ValueError('metadata-total-byte-count-drift')
    if signed_release_body(data['InRelease']) != data['Release']:
        raise ValueError('inrelease-body-release-mismatch')
    for relative in TARGETS[2:]:
        if hashes.get(relative) != (hashlib.sha256(data[relative]).hexdigest(), len(data[relative])):
            raise ValueError('release-index-hash-or-size-mismatch: ' + relative)
    observations = sanitize_headers(manifest)
    verifier_path = Path(__file__).resolve()
    verifier_raw = verifier_path.read_bytes()
    observations['metadata_verifier'] = {'path': 'scripts/cvc5-c0-sdk-metadata.py',
                                         'bytes': len(verifier_raw), 'raw_digest': digest(verifier_raw)}
    observations['retention_directory'] = str(RETAINED.relative_to(ROOT))
    observations['validation_scope'] = 'retained-byte integrity and metadata internal consistency; not signature verification, independent authentication, package acquisition, SDK acceptance, or runtime filesystem closure'
    observations['retained_fetch_manifest'] = {'path': str((RETAINED / 'fetch-observations.json').relative_to(ROOT)), 'bytes': len(manifest_raw), 'raw_digest': digest(manifest_raw)}
    observations['release_fields'] = {key: release.get(key) for key in ('Origin', 'Label', 'Suite', 'Version', 'Codename', 'Date', 'Valid-Until', 'Architectures', 'Components')}
    observations['release_index_checks'] = [{'relative_path': rel, 'declared_sha256': hashes[rel][0], 'declared_bytes': hashes[rel][1], 'bytes_match': True} for rel in TARGETS[2:]]
    observations['inrelease_body_equals_release'] = True
    observations['signature_verified'] = False
    observations['signature_trust_and_time_policy'] = 'not-accepted; historical snapshot expiry and trusted keyring require separate review'
    return observations, decompress(data[TARGETS[2]]), decompress(data[TARGETS[3]])


def fetch(resume=False, resume_index=False):
    # Exclusive directory creation prevents overwriting evidence or implicit retry.
    sandbox_failure = None
    guard_failure = None
    resumed_manifest = None
    if RETAINED.exists():
        prior, prior_raw = read_manifest()
        rows = prior.get('observations', [])
        if resume_index:
            validate_manifest_policy(prior, complete=False)
            expected_files = {'fetch-observations.json', 'Release', 'InRelease'}
            expected_error = ('redirect-outside-pinned-metadata-path: https://snapshot.debian.org/file/'
                              'b600d57187e0bdcc4680509f02595d3e5055935a/'
                              '4926bbf128b8e497cb83c59c8212fd2ef4df5b2c30e9140a688198cd2cd55471')
            if (set(p.name for p in RETAINED.iterdir()) != expected_files or len(rows) != 3
                    or rows[2].get('status') != 'failed' or rows[2].get('bytes_received') != 0
                    or rows[2].get('error') != expected_error or prior.get('complete') is not False):
                raise ValueError('index-resume-state-not-exact-observed-redirect')
            for relative, row in zip(TARGETS[:2], rows[:2]):
                validate_observation(relative, row)
                raw = (RETAINED / relative).read_bytes()
                if len(raw) != row['bytes'] or digest(raw) != row['raw_digest']:
                    raise ValueError('index-resume-retained-release-mismatch')
            if prior['total_response_body_bytes'] != sum(row['bytes'] for row in rows[:2]):
                raise ValueError('index-resume-partial-byte-count-mismatch')
            if signed_release_body((RETAINED / 'InRelease').read_bytes()) != (RETAINED / 'Release').read_bytes():
                raise ValueError('index-resume-signed-body-mismatch')
            _, hashes = release_hashes((RETAINED / 'Release').read_bytes())
            if hashes[TARGETS[2]][0] != expected_error.rsplit('/', 1)[-1]:
                raise ValueError('index-resume-location-not-release-declared-hash')
            with (RETAINED / 'fetch-before-index-resume.json').open('xb') as stream:
                stream.write(prior_raw)
            resumed_manifest = dict(prior)
            resumed_manifest['prior_index_redirect_guard_failure'] = rows[2]
            resumed_manifest['observations'] = rows[:2]
            resumed_manifest['resume_index_action'] = 'continue-only-observed-Packages-302-location; initial-Packages-request-not-repeated; Sources-first-request'
        elif (set(p.name for p in RETAINED.iterdir()) != {'fetch-observations.json'}
                or prior.get('total_response_body_bytes') != 0 or len(rows) != 1):
            raise ValueError('retention-directory-exists-no-retry')
        elif rows[0].get('error') == '<urlopen error [Errno 1] Operation not permitted>' and not resume:
            sandbox_failure = prior
        elif (resume and rows[0].get('error') == 'redirect-outside-pinned-metadata-path: https://snapshot.debian.org/file/4c57abe878336c7806099d53d10dde2a6d0a4540/Release'):
            guard_failure = prior
        else:
            raise ValueError('retention-directory-exists-no-retry')
    else:
        RETAINED.mkdir(parents=True, exist_ok=False)
    manifest = {'format': 'radishaxiom-private-cvc5-c0-sdk-metadata', 'version': '0.1',
                'base_url': BASE, 'max_total_bytes': MAX_BYTES, 'timeout_seconds_per_item': TIMEOUT,
                'retries': 0, 'fallback_sources': 0, 'signature_authentication': 'not-established',
                'observations': [], 'total_response_body_bytes': 0, 'complete': False}
    if resumed_manifest:
        manifest = resumed_manifest
    if sandbox_failure:
        manifest['prior_sandbox_network_failure'] = sandbox_failure
    if guard_failure:
        manifest['prior_redirect_guard_failure'] = guard_failure
        manifest['resume_action'] = 'continue-only-observed-302-location; initial-Release-request-not-repeated'
    signal.signal(signal.SIGALRM, deadline)
    for relative in TARGETS[2:] if resume_index else TARGETS:
        name = relative.replace('/', '__')
        url = BASE + 'dists/bookworm/' + relative
        row = {'requested_url': url, 'relative_path': relative, 'retained_file': name,
               'started_utc': now(), 'redirects': [], 'status': 'started'}
        manifest['observations'].append(row)
        start = time.monotonic()
        count = 0
        sha = hashlib.sha256()
        try:
            signal.alarm(TIMEOUT)
            expected_digest = None
            if relative in TARGETS[2:]:
                _, hashes = release_hashes((RETAINED / 'Release').read_bytes())
                expected_digest = hashes[relative][0]
            opener = urllib.request.build_opener(MetadataRedirect(relative, row['redirects'], expected_digest))
            actual_url = url
            if guard_failure and relative == 'Release':
                actual_url = 'https://snapshot.debian.org/file/4c57abe878336c7806099d53d10dde2a6d0a4540/Release'
                validate_redirect(relative, actual_url)
                row['redirects'].append({'status': 302, 'from_url': url, 'to_url': actual_url,
                                         'observation': 'captured in prior redirect guard failure; resumed without repeating initial GET'})
            if resume_index and relative == TARGETS[2]:
                actual_url = manifest['prior_index_redirect_guard_failure']['error'].split(': ', 1)[1]
                validate_redirect(relative, actual_url, expected_digest)
                row['redirects'].append({'status': 302, 'from_url': url, 'to_url': actual_url,
                                         'observation': 'captured in prior index redirect guard failure; resumed without repeating initial GET'})
            req = urllib.request.Request(actual_url, headers={'Accept-Encoding': 'identity', 'User-Agent': 'RadishAxiom-C0-metadata/0.1'})
            with opener.open(req, timeout=TIMEOUT) as response, (RETAINED / name).open('xb') as stream:
                row.update(final_url=response.url, http_status=response.status,
                           response_headers=relevant_headers(response.headers))
                if response.status != 200 or response.headers.get('Content-Encoding', 'identity') != 'identity':
                    raise ValueError('unexpected-metadata-http-status-or-encoding')
                length = response.headers.get('Content-Length')
                if length is None or not length.isdigit():
                    raise ValueError('bounded-metadata-fetch-requires-content-length')
                declared_length = int(length)
                if declared_length > MAX_BYTES - manifest['total_response_body_bytes']:
                    raise ValueError('metadata-content-length-exceeds-total-budget')
                while count < declared_length:
                    remaining = MAX_BYTES - manifest['total_response_body_bytes']
                    chunk = response.read(min(65536, remaining, declared_length - count))
                    if not chunk:
                        break
                    count += len(chunk)
                    manifest['total_response_body_bytes'] += len(chunk)
                    if manifest['total_response_body_bytes'] > MAX_BYTES:
                        raise ValueError('metadata-total-byte-budget-exceeded')
                    sha.update(chunk)
                    stream.write(chunk)
                if count != declared_length:
                    raise ValueError('metadata-content-length-mismatch')
            row.update(status='obtained', bytes=count, raw_digest='sha256:' + sha.hexdigest())
        except (OSError, ValueError, urllib.error.URLError) as error:
            row.update(status='failed', bytes_received=count, error_type=type(error).__name__, error=str(error))
            raise
        finally:
            signal.alarm(0)
            row.update(finished_utc=now(), elapsed_seconds=round(time.monotonic() - start, 3))
            write_json(RETAINED / 'fetch-observations.json', manifest)
        print(relative, row['bytes'], row['raw_digest'], flush=True)
    manifest['complete'] = True
    write_json(RETAINED / 'fetch-observations.json', manifest)
    print('metadata-only fetch complete:', manifest['total_response_body_bytes'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('fetch', 'resume-redirect', 'resume-index-redirect', 'metadata-verify'))
    args = parser.parse_args()
    if args.action == 'fetch':
        fetch()
    elif args.action == 'resume-redirect':
        fetch(resume=True)
    elif args.action == 'resume-index-redirect':
        fetch(resume_index=True)
    else:
        observations, packages, sources = read_verified_metadata()
        print(json.dumps({'metadata_bytes': observations['total_response_body_bytes'],
                          'packages_uncompressed_bytes': len(packages),
                          'sources_uncompressed_bytes': len(sources),
                          'signature_verified': False}, indent=2))


if __name__ == '__main__':
    main()
