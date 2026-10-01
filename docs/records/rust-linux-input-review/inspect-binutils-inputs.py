#!/usr/bin/env python3
"""Recheck fixed Binutils download bytes and signature declarations; no cryptography or extraction."""
import argparse
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('inputs', HERE / 'inspect-mpc-mpfr-inputs.py')
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)
identity, require, read = inputs.identity, inputs.require, inputs.retention.read_regular
DEFAULT = ROOT / '.tmp/binutils-inputs-20260925'
ARCHIVE = {'bytes': 51342242, 'sha256': '0cdd76777a0dfd3dd3a63f215f030208ddb91c2361d2bcc02acec0f1c16b6a2e'}
RECIPE_SHA1 = '568ba0a286cf79520572c1597a203c1aafd462de'
TARGETS = {
    'announcement': ('https://sourceware.org/pipermail/binutils/2025-February/139195.html', 262144, 'html'),
    'signature': ('https://sourceware.org/pub/binutils/releases/binutils-2.44.tar.gz.sig', 65536, 'sig'),
    'binutils': ('https://sourceware.org/pub/binutils/releases/binutils-2.44.tar.gz', 67108864, 'tar.gz'),
}


class Announcement(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fragments = []

    def handle_data(self, data):
        self.fragments.append(data)


def announcement_digest(raw):
    require(0 < len(raw) <= TARGETS['announcement'][1], 'announcement size bound')
    page = Announcement()
    page.feed(raw.decode('utf-8'))
    matches = re.findall(r'^\s*([0-9a-f]{64})[ \t]+binutils-2\.44\.tar\.gz[ \t]*$',
                         ''.join(page.fragments), flags=re.MULTILINE)
    require(len(matches) == 1, 'missing or ambiguous exact archive announcement')
    return matches[0]


def archive_identity(raw, announcement):
    require(identity(raw) == ARCHIVE, 'fixed archive size or SHA-256 mismatch')
    require(announcement_digest(announcement) == ARCHIVE['sha256'], 'announcement SHA-256 mismatch')
    require(hashlib.sha1(raw).hexdigest() == RECIPE_SHA1, 'recipe SHA-1 mismatch')
    return identity(raw)


def inspect(directory=DEFAULT):
    plan = json.loads(read(directory / 'fetch-plan.json', 16384))
    expected_targets = {name: {'url': url, 'limit': limit, 'suffix': suffix}
                        for name, (url, limit, suffix) in TARGETS.items()}
    require(plan['targets'] == expected_targets and plan['directory'] == str(DEFAULT), 'fetch plan scope drift')
    method = identity(read(HERE / 'fetch-mpc-mpfr-inputs.py'))
    require(plan['method'] == method and plan['expected_archive_sha256'] == ARCHIVE['sha256'] and
            plan['recipe_sha1_statement_only'] == RECIPE_SHA1, 'plan identity drift')
    observations, bodies = [], {}
    for name, (url, limit, suffix) in TARGETS.items():
        stem = name + '-attempt-1'
        row = json.loads(read(directory / (stem + '.json'), 16384))
        require(row['target'] == name and row['attempt'] == 1 and row['url'] == url and
                row['method'] == method and row['body']['file'] == stem + '.' + suffix, 'fetch record scope drift')
        expected_argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--proto', '=https',
                         '--tlsv1.2', '--max-time', '60', '--max-filesize', str(limit),
                         '--output', str(DEFAULT / row['body']['file']), '--write-out', '%{http_code}\n', url]
        require(row['argv'] == expected_argv, 'fetch command drift')
        for channel in ('body', 'stdout', 'stderr'):
            filename = row['body']['file'] if channel == 'body' else stem + '.' + channel
            data = read(directory / filename, limit if channel == 'body' else 65536)
            require(identity(data) == {k: row[channel][k] for k in ('bytes', 'sha256')}, 'fetch bytes drift')
            if channel == 'body':
                require(data, 'empty fetch body')
                bodies[name] = data
            else:
                require(data.decode('utf-8') == row[channel]['text'], 'fetch stream text drift')
                if channel == 'stdout':
                    require(data == b'200\n', 'unexpected HTTP output')
        require(row['passed'] is True and row['transport_passed'] is True and row['exit_code'] == 0 and
                row['http_code'] == '200' and row['parent_timeout'] is False and
                row['index_and_recipe_bytes_match'] is None, 'unsuccessful or misclassified fetch')
        observations.append(row)
    # Read the actual fixed recipe instead of accepting a digest copied from a page.
    recipe = inputs.remaining.load('inspect-musl-cross-make.py')
    actual = recipe.inspect(ROOT / '.tmp/musl-cross-make-review-c38a1c1/musl-cross-make-3635262.tar.gz',
                            recipe.SOURCE_SHA, include_text=True)
    statement, = [row for row in actual['files'] if row['path'] == 'hashes/binutils-2.44.tar.gz.sha1']
    require(statement['text'].split() == [RECIPE_SHA1, 'binutils-2.44.tar.gz'], 'fixed recipe declaration drift')
    archive = archive_identity(bodies['binutils'], bodies['announcement'])
    signature = inputs.signature_metadata(bodies['signature'])
    return {'kind': 'diagnostic-binutils-inputs-v1', 'fetches': observations, 'archive': archive,
            'announcement_sha256_matches': True, 'recipe_sha1_matches_not_authentication': True,
            'recipe_archive': actual['archive'], 'signature': signature,
            'methods': {name: identity(read(HERE / name)) for name in
                        ('inspect-binutils-inputs.py', 'fetch-mpc-mpfr-inputs.py', 'inspect-mpc-mpfr-inputs.py',
                         'inspect-musl-cross-make.py', 'inspect-musl-verification-keys.py',
                         'inspect-musl-verification-status.py', 'retain-musl-verifier-inputs.py')},
            'archive_content_inspected': False, 'license_review_complete': False,
            'cryptography_executed': False, 'source_acceptance': 'not-assessed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT, help='original or restored input directory')
    args = parser.parse_args()
    print(json.dumps(inspect(args.directory), sort_keys=True, indent=2))
