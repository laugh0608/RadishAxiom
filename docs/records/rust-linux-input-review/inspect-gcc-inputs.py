#!/usr/bin/env python3
"""Recheck fixed GCC 9.4.0 bytes, checksum bindings and signature declarations offline."""
import argparse
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
from urllib.parse import urljoin

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('inputs', HERE / 'inspect-mpc-mpfr-inputs.py')
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)
require, identity, read = inputs.require, inputs.identity, inputs.retention.read_regular
DEFAULT = ROOT / '.tmp/gcc-inputs-dac0405-20260925'
BASE = 'https://gcc.gnu.org/pub/gcc/releases/gcc-9.4.0/'
ARCHIVE_NAME = 'gcc-9.4.0.tar.xz'
RECIPE_SHA1 = 'bf6d6480fb32e5a28dac849449f533a84d4e6547'
TARGETS = {'directory': {'url': BASE, 'suffix': 'html', 'limit': 262144},
           'checksums': {'url': BASE + 'sha512.sum', 'suffix': 'txt', 'limit': 65536},
           'signature': {'url': BASE + ARCHIVE_NAME + '.sig', 'suffix': 'sig', 'limit': 65536},
           'gcc': {'url': BASE + ARCHIVE_NAME, 'suffix': 'tar.xz', 'limit': 100663296}}


def checksum_entries(raw):
    require(0 < len(raw) <= 65536, 'checksum list size bound')
    entries = {}
    expected = {'gcc-9.4.0.tar.' + suffix for suffix in ('gz', 'gz.sig', 'xz', 'xz.sig')}
    for line in raw.decode('ascii').splitlines():
        match = re.fullmatch(r'([0-9a-f]{128})  (gcc-9\.4\.0\.tar\.(?:gz|xz)(?:\.sig)?)', line)
        require(match is not None, 'invalid checksum line')
        digest, name = match.groups()
        require(name not in entries, 'duplicate checksum filename')
        entries[name] = digest
    require(entries.keys() == expected, 'missing exact release checksum entries')
    return entries


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.update(urljoin(BASE, value) for key, value in attrs if key == 'href' and value)


def directory_links(raw):
    require(0 < len(raw) <= 262144, 'directory page bound')
    page = Links()
    page.feed(raw.decode('utf-8'))
    require({TARGETS[n]['url'] for n in ('checksums', 'signature', 'gcc')} <= page.links,
            'exact release links missing')


def verify_bindings(archive, signature, checksums):
    entries = checksum_entries(checksums)
    require(hashlib.sha512(archive).hexdigest() == entries[ARCHIVE_NAME], 'archive SHA-512 mismatch')
    require(hashlib.sha512(signature).hexdigest() == entries[ARCHIVE_NAME + '.sig'], 'signature SHA-512 mismatch')
    require(hashlib.sha1(archive).hexdigest() == RECIPE_SHA1, 'recipe SHA-1 mismatch')
    return {'archive': identity(archive), 'archive_sha512': entries[ARCHIVE_NAME],
            'signature_sha512': entries[ARCHIVE_NAME + '.sig'], 'checksum_entries': entries,
            'recipe_sha1_matches_not_authentication': True}


def inspect(directory=DEFAULT):
    plan = json.loads(read(directory / 'fetch-plan.json', 16384))
    method = identity(read(HERE / 'fetch-mpc-mpfr-inputs.py'))
    require(plan['directory'] == str(DEFAULT) and plan['targets'] == TARGETS and
            plan['method'] == method and plan['recipe_sha1_statement_only'] == RECIPE_SHA1, 'fetch plan drift')
    recovery_method = identity(read(HERE / 'fetch-gcc-archive-recovery.py'))
    recovery_plan = json.loads(read(directory / 'recovery-plan.json', 16384))
    require(recovery_plan == {'target': TARGETS['gcc'], 'directory': str(DEFAULT), 'request_timeout': 180,
                             'parent_timeout': 185, 'executed': False}, 'recovery plan drift')
    observations, bodies = [], {}
    for name, attempt in [('directory', 1), ('checksums', 1), ('signature', 1), ('gcc', 1), ('gcc', 2)]:
        target, stem = TARGETS[name], name + '-attempt-' + str(attempt)
        filename = stem + '.' + target['suffix']
        row = json.loads(read(directory / (stem + '.json'), 16384))
        recovery = attempt == 2
        failed = name == 'gcc' and not recovery
        argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--proto', '=https', '--tlsv1.2',
                '--max-time', '180' if recovery else '60', '--max-filesize', str(target['limit']),
                '--output', str(DEFAULT / filename), '--write-out', '%{http_code}\n', target['url']]
        require(row['argv'] == argv and row['target'] == name and row['url'] == target['url'] and
                row['attempt'] == attempt and row['body']['file'] == filename and
                row['method'] == (recovery_method if recovery else method), 'fetch scope drift')
        require(row['exit_code'] == (28 if failed else 0) and row['http_code'] == '200' and
                row['parent_timeout'] is False and row['passed'] is (not failed) and
                row['transport_passed'] is (not failed), 'fetch outcome drift')
        if recovery:
            require(row['first_timeout_record'] == identity(read(directory / 'gcc-attempt-1.json')),
                    'recovery failure binding drift')
        for channel in ('body', 'stdout', 'stderr'):
            raw = read(directory / (filename if channel == 'body' else stem + '.' + channel),
                       target['limit'] if channel == 'body' else 65536)
            require(identity(raw) == {k: row[channel][k] for k in ('bytes', 'sha256')}, 'fetch bytes drift')
            if channel == 'body' and not failed:
                bodies[name] = raw
            elif channel != 'body':
                require(raw.decode('utf-8') == row[channel]['text'], 'fetch stream drift')
                require(channel != 'stdout' or raw == b'200\n', 'HTTP output drift')
        observations.append(row)
    directory_links(bodies['directory'])
    recipe = inputs.remaining.load('inspect-musl-cross-make.py')
    actual = recipe.inspect(ROOT / '.tmp/musl-cross-make-review-c38a1c1/musl-cross-make-3635262.tar.gz',
                            recipe.SOURCE_SHA, include_text=True)
    statement, = [r for r in actual['files'] if r['path'] == 'hashes/' + ARCHIVE_NAME + '.sha1']
    require(statement['text'].split() == [RECIPE_SHA1, ARCHIVE_NAME], 'fixed recipe declaration drift')
    return {'kind': 'diagnostic-gcc-inputs-v1', 'fetches': observations,
            'bindings': verify_bindings(bodies['gcc'], bodies['signature'], bodies['checksums']),
            'signature': inputs.signature_metadata(bodies['signature']), 'recipe_archive': actual['archive'],
            'exact_directory_links_checked': True, 'archive_content_inspected': False,
            'license_review_complete': False, 'cryptography_executed': False, 'source_acceptance': 'not-assessed',
            'methods': {name: identity(read(HERE / name)) for name in
                        ('inspect-gcc-inputs.py', 'fetch-gcc-archive-recovery.py', 'fetch-mpc-mpfr-inputs.py',
                         'inspect-mpc-mpfr-inputs.py', 'inspect-musl-cross-make.py',
                         'inspect-musl-verification-keys.py', 'retain-musl-verifier-inputs.py')}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(inspect(args.directory), sort_keys=True, indent=2))
