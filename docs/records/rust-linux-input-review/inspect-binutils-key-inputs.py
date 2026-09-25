#!/usr/bin/env python3
"""Recheck GNU announcement/key bytes and unverified self-certification declarations."""
import argparse
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
from urllib.parse import urljoin

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('keys', HERE / 'inspect-mpc-mpfr-key-inputs.py')
keys = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keys)
require, identity, read = keys.require, keys.identity, keys.retention.read_regular
DEFAULT = HERE.parents[2] / '.tmp/binutils-key-inputs-20260925'
PRIMARY = '3A24BC1E8FB409FA9F14371813FCEF89DD9E3C4F'
TARGETS = {
    'release-243': ('https://lists.gnu.org/archive/html/info-gnu/2024-08/msg00001.html', 'html'),
    'release-244': ('https://lists.gnu.org/archive/html/info-gnu/2025-02/msg00001.html', 'html'),
    'public-key': ('https://lists.gnu.org/archive/html/info-gnu/2024-08/binqltbMeQqcS.bin', 'asc'),
}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.fragments = [], []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(value for key, value in attrs if key == 'href' and value)

    def handle_data(self, data):
        self.fragments.append(data)


def pages_link_key(old, current):
    pages = []
    for raw, version in ((old, '2.43'), (current, '2.44')):
        require(0 < len(raw) <= 262144, 'page bound')
        page = Page()
        page.feed(raw.decode('utf-8'))
        text = ''.join(page.fragments)
        require('GNU Binutils ' + version + ' Released' in text and 'Nick Clifton' in text,
                'announcement identity text missing')
        pages.append(page)
    require(TARGETS['public-key'][0] in {urljoin(TARGETS['release-243'][0], href) for href in pages[0].links},
            'key no longer linked from announcement')
    require('0cdd76777a0dfd3dd3a63f215f030208ddb91c2361d2bcc02acec0f1c16b6a2e' in
            ''.join(pages[1].fragments), '2.44 archive digest absent')


def inspect(directory=DEFAULT):
    plan = json.loads(read(directory / 'fetch-plan.json', 16384))
    targets = {name: {'url': url, 'suffix': suffix, 'limit': 262144}
               for name, (url, suffix) in TARGETS.items()}
    method = identity(read(HERE / 'fetch-mpc-mpfr-inputs.py'))
    require(plan['targets'] == targets and plan['directory'] == str(DEFAULT) and
            plan['method'] == method and plan['expected_primary'] == PRIMARY, 'fetch plan drift')
    observations, bodies = [], {}
    for name, (url, suffix) in TARGETS.items():
        stem = name + '-attempt-1'
        row = json.loads(read(directory / (stem + '.json'), 16384))
        require(row['target'] == name and row['url'] == url and row['attempt'] == 1 and row['method'] == method and
                row['body']['file'] == stem + '.' + suffix, 'fetch scope drift')
        argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--proto', '=https', '--tlsv1.2',
                '--max-time', '60', '--max-filesize', '262144', '--output', str(DEFAULT / row['body']['file']),
                '--write-out', '%{http_code}\n', url]
        require(row['argv'] == argv and row['exit_code'] == 0 and row['http_code'] == '200' and
                row['passed'] is True and row['transport_passed'] is True and row['parent_timeout'] is False,
                'unsuccessful or altered fetch')
        for channel in ('body', 'stdout', 'stderr'):
            filename = row['body']['file'] if channel == 'body' else stem + '.' + channel
            raw = read(directory / filename, 262144)
            require(identity(raw) == {k: row[channel][k] for k in ('bytes', 'sha256')}, 'fetch bytes drift')
            if channel == 'body':
                bodies[name] = raw
            else:
                require(raw.decode('utf-8') == row[channel]['text'], 'fetch stream mismatch')
                require(channel != 'stdout' or raw == b'200\n', 'HTTP output mismatch')
        observations.append(row)
    pages_link_key(bodies['release-243'], bodies['release-244'])
    inventory = keys.inventory(bodies['public-key'], PRIMARY)
    packet_list = keys.keys.packets(keys.armor(bodies['public-key']))
    uids = [body.decode('utf-8') for tag, body, _ in packet_list if tag == 13]
    return {'kind': 'diagnostic-binutils-key-inputs-v1', 'fetches': observations, 'inventory': inventory,
            'uid_text_unverified': uids, 'attachment_link_checked': True,
            'methods': {name: identity(read(HERE / name)) for name in
                        ('inspect-binutils-key-inputs.py', 'inspect-mpc-mpfr-key-inputs.py',
                         'inspect-musl-verification-keys.py', 'retain-musl-verifier-inputs.py')},
            'public_key_identity_accepted': False, 'cryptography_executed': False,
            'source_acceptance': 'not-assessed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(inspect(args.directory), sort_keys=True, indent=2))
