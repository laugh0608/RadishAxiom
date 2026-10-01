#!/usr/bin/env python3
"""Bounded public metadata fetch using the existing recorded fetch implementation."""
import argparse
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fetch', HERE / 'fetch-mpc-mpfr-inputs.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)
DIRECTORY = HERE.parents[2] / '.tmp/mpc-mpfr-keys-ee917c7-20260916'
PAGES = {
    'mpc-page': 'https://www.multiprecision.org/mpc/download.html',
    'mpc-fingerprint-page': 'https://www.multiprecision.org/mpfrcx/download.html',
    'mpfr-page': 'https://www.mpfr.org/mpfr-4.2.2/',
    'mpfr-key-page': 'https://www.vinc17.net/pgp.html',
}
TARGETS = {name: {'url': url, 'limit': 262144, 'suffix': 'html'} for name, url in PAGES.items()}
TARGETS['mpc-key'] = {'url': 'https://www.multiprecision.org/downloads/enge.gpg',
                      'limit': 262144, 'suffix': 'asc'}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.update(value for key, value in attrs if key == 'href' and value)


def linked_key(url):
    """Only a manually selected, actually linked HTTPS file on the maintainer host."""
    record = json.loads((DIRECTORY / 'mpfr-key-page-attempt-1.json').read_bytes())
    raw = (DIRECTORY / 'mpfr-key-page-attempt-1.html').read_bytes()
    if not record['passed'] or fetch.identity(raw) != {k: record['body'][k] for k in ('bytes', 'sha256')}:
        raise ValueError('MPFR key page is not a successful retained input')
    parser = Links()
    parser.feed(raw.decode('utf-8'))
    parsed = urlsplit(url)
    if (url not in {urljoin(PAGES['mpfr-key-page'], link) for link in parser.links}
            or parsed.scheme != 'https' or parsed.netloc != 'www.vinc17.net'
            or parsed.query or parsed.fragment or not parsed.path.endswith(('.asc', '.gpg'))):
        raise ValueError('not a linked maintainer HTTPS key file')
    return {'url': url, 'limit': 262144, 'suffix': 'asc'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=[*TARGETS, 'mpfr-key'])
    parser.add_argument('--linked-key-url')
    parser.add_argument('--attempt', type=int, choices=(1, 2), default=1)
    parser.add_argument('--execute-authorized', action='store_true')
    args = parser.parse_args()
    if not args.execute_authorized:
        print(json.dumps(TARGETS, sort_keys=True, indent=2))
    else:
        if args.target is None or (args.target == 'mpfr-key') != bool(args.linked_key_url):
            parser.error('target and linked-key-url scope mismatch')
        if args.target == 'mpfr-key':
            TARGETS['mpfr-key'] = linked_key(args.linked_key_url)
        fetch.DIRECTORY, fetch.TARGETS = DIRECTORY, TARGETS
        # Save this routing method alongside the underlying fetch method identity.
        scope = DIRECTORY / f'{args.target}-attempt-{args.attempt}.scope.json'
        with scope.open('x') as output:
            json.dump({'routing_method': fetch.identity(Path(__file__).read_bytes()),
                       'target': TARGETS[args.target]}, output, sort_keys=True, indent=2)
            output.write('\n')
        raise SystemExit(fetch.fetch(args.target, args.attempt))
