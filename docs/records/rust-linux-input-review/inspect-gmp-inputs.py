#!/usr/bin/env python3
"""Offline GMP bytes, logical contents and key declarations; no cryptographic acceptance."""
import argparse
import gzip
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
from urllib.parse import urljoin

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


route = load('fetch-gmp-inputs.py')
inputs = load('inspect-mpc-mpfr-inputs.py')
refresh = load('inspect-binutils-key-refresh.py')
declarations = refresh.prior.keys
require, identity, read = refresh.require, refresh.identity, refresh.read
RECIPE = ROOT / '.tmp/musl-cross-make-review-c38a1c1/musl-cross-make-3635262.tar.gz'
RECIPE_SHA1 = 'b4043dd2964ab1a858109da85c44de224384f352'
ARCHIVE = {'bytes': 2094196, 'sha256': 'a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898'}
SELECTED = {'README', 'COPYING', 'COPYING.LESSERv3', 'COPYINGv2', 'COPYINGv3', 'gmp-h.in', 'doc/gmp.texi'}


class Page(HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.base, self.links, self.text = base, set(), []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.update(urljoin(self.base, v) for k, v in attrs if k == 'href' and v)

    def handle_data(self, data):
        self.text.append(data)


def pages(home, announcement):
    result = {}
    for name, raw in (('identity', home), ('announcement', announcement)):
        require(0 < len(raw) <= 262144, 'page bound')
        page = Page(route.TARGETS[name]['url'])
        page.feed(raw.decode('utf-8'))
        require(route.TARGETS['gmp']['url'] in page.links, 'exact archive link missing')
        if name == 'announcement':
            require(route.TARGETS['signature']['url'] in page.links, 'exact signature link missing')
        else:
            text = ' '.join(' '.join(page.text).split())
            require('Fingerprint: 343C 2FF0 FBEE 5EC2 EDBE F399 F359 9FF8 28C6 7298' in text,
                    'official key fingerprint declaration missing')
            require('2094196 bytes' in text, 'archive size declaration missing')
        result[name] = {'input': identity(raw), 'exact_links_checked': True}
    return result


def archive_binding(raw):
    require(identity(raw) == ARCHIVE, 'fixed observed archive changed')
    require(hashlib.sha1(raw).hexdigest() == RECIPE_SHA1, 'recipe SHA-1 mismatch')
    return {'observed_archive': identity(raw), 'recipe_sha1': RECIPE_SHA1,
            'strong_digest_is_local_observation_not_authentication': True}


def key_material(raw, ring):
    require(identity(ring) == refresh.RING, 'previous GNU keyring drift')
    current = declarations.armor(raw)
    require(set(declarations.keys.key_blocks(current)) == {route.PRIMARY}, 'unexpected primary set')
    report = declarations.inventory(raw, route.PRIMARY)
    selected, selection = refresh.select(ring, route.PRIMARY)
    old_packets = declarations.keys.packets(selected)
    old_bodies = {identity(body)['sha256'] for tag, body, _ in old_packets if tag == 2}
    old_signatures = [declarations.signature_fields(body) for tag, body, _ in old_packets if tag == 2]
    new_self = [s for s in report['blocks'][0]['signatures'] if s['declared_self_signature'] and
                s['signature_body']['sha256'] not in old_bodies]
    return {'current': report, 'gnu_keyring': refresh.RING, 'gnu_selection': selection,
            'gnu_signature_declarations': old_signatures, 'additional_self_declarations': new_self,
            'additional_declarations_authenticated': False}


def inspect(directory=route.DIRECTORY, recipe_path=RECIPE,
            ring_path=refresh.DEFAULT / 'gnu-keyring-attempt-1.gpg'):
    require(json.loads(read(directory / 'fetch-plan.json')) == route.plan(), 'fetch plan drift')
    bodies, fetches = {}, []
    for name, target in route.TARGETS.items():
        stem = name + '-attempt-1'
        filename = stem + '.' + target['suffix']
        row = json.loads(read(directory / (stem + '.json')))
        argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--proto', '=https', '--tlsv1.2',
                '--max-time', '60', '--max-filesize', str(target['limit']), '--output',
                str(route.DIRECTORY / filename), '--write-out', '%{http_code}\n', target['url']]
        require(row['argv'] == argv and row['target'] == name and row['url'] == target['url'] and
                row['attempt'] == 1 and row['body']['file'] == filename and row['method'] == route.plan()['method'],
                'fetch scope drift')
        require(row['exit_code'] == 0 and row['http_code'] == '200' and not row['parent_timeout'] and
                row['passed'] is True and row['transport_passed'] is True, 'fetch outcome drift')
        for channel in ('body', 'stdout', 'stderr'):
            raw = read(directory / (filename if channel == 'body' else stem + '.' + channel), target['limit'])
            require(identity(raw) == {k: row[channel][k] for k in ('bytes', 'sha256')}, 'fetch bytes drift')
            if channel == 'body':
                bodies[name] = raw
            else:
                require(raw.decode('utf-8') == row[channel]['text'] and
                        raw == (b'200\n' if channel == 'stdout' else b''), 'fetch stream drift')
        fetches.append(row)
    recipe = load('inspect-musl-cross-make.py')
    actual_recipe = recipe.inspect(recipe_path, recipe.SOURCE_SHA, include_text=True)
    declaration, = [r for r in actual_recipe['files'] if r['path'] == 'hashes/gmp-6.3.0.tar.xz.sha1']
    require(declaration['text'].split() == [RECIPE_SHA1, 'gmp-6.3.0.tar.xz'], 'fixed recipe declaration drift')
    binding = archive_binding(bodies['gmp'])
    signature = inputs.signature_metadata(bodies['signature'])
    require(signature['declared_issuer'] == route.PRIMARY, 'signature issuer differs from official identity')
    content, texts = inputs.inventory(inputs.unpack(bodies['gmp'], 'xz'), 'gmp-6.3.0', SELECTED)
    header_lines = {' '.join(line.split()) for line in texts['gmp-h.in'].splitlines()}
    require({'#define __GNU_MP_VERSION 6', '#define __GNU_MP_VERSION_MINOR 3',
             '#define __GNU_MP_VERSION_PATCHLEVEL 0'} <= header_lines, 'header version declaration drift')
    report = {'kind': 'diagnostic-gmp-inputs-v1', 'fetches': fetches, 'bindings': binding,
              'official_pages': pages(bodies['identity'], bodies['announcement']), 'signature': signature,
              'recipe_archive': actual_recipe['archive'], 'content': content,
              'header_version_declaration': '6.3.0',
              'keys': key_material(bodies['public-key'], read(ring_path)),
              'license_review_complete': False, 'upstream_programs_executed': False,
              'cryptography_executed': False, 'source_acceptance': 'not-assessed',
              'methods': {name: identity(read(HERE / name)) for name in
                          ('inspect-gmp-inputs.py', 'fetch-gmp-inputs.py', 'fetch-mpc-mpfr-inputs.py',
                           'inspect-mpc-mpfr-inputs.py', 'inspect-musl-remaining-sources.py',
                           'inspect-musl-cross-make.py', 'inspect-archives.py',
                           'inspect-binutils-key-refresh.py', 'inspect-binutils-key-inputs.py',
                           'inspect-mpc-mpfr-key-inputs.py', 'fetch-mpc-mpfr-key-inputs.py',
                           'inspect-musl-verification-keys.py', 'inspect-musl-verification-status.py',
                           'retain-musl-verifier-inputs.py')}}
    return report, texts


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=route.DIRECTORY)
    parser.add_argument('--recipe', type=Path, default=RECIPE)
    parser.add_argument('--ring', type=Path, default=refresh.DEFAULT / 'gnu-keyring-attempt-1.gpg')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report, _ = inspect(args.directory, args.recipe, args.ring)
    with args.output.open('xb') as stream:
        stream.write(gzip.compress((json.dumps(report, sort_keys=True, indent=2) + '\n').encode(), mtime=0))
    print(json.dumps({'archive': report['bindings'], 'members': report['content']['member_count'],
                      'files': report['content']['file_count'], 'output': identity(args.output.read_bytes())}, indent=2))
