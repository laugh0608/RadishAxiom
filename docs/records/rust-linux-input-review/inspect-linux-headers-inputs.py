#!/usr/bin/env python3
"""Bind fixed headers fetches, source comparison and build-recipe observations; never authenticate or execute."""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


route = load('fetch-linux-headers-inputs.py')
candidate = load('fetch-linux-headers-candidate.py')
content = load('inspect-linux-headers-content.py')
retention = load('retain-musl-verifier-inputs.py')
require, identity, read = retention.require, retention.identity, retention.read_regular
RECIPE = ROOT / '.tmp/musl-cross-make-review-c38a1c1/musl-cross-make-3635262.tar.gz'
SHA1 = 'de12b9c8ae2de9e85056a36be9f0fcc0a1e4abe9'
MIRROR = {'bytes': 1052880, 'sha256': 'd3f3acf6d16bdb005d3f2589ade1df8eff2e1c537f92e6cd9222218ead882feb'}
CANDIDATE = {'bytes': 1415704, 'sha256': 'e875ffc69332bb4a8776e29ba15659be3e27785762fc8c769d9d2f4cf002ff87'}
RUST_SCRIPT = {'bytes': 2668, 'sha256': 'faae0de27e4ca1661a030ce3623e4959f34f5d1b6f795ea9b5b84c10c2086b2e'}


def tag_declaration(raw):
    require(0 < len(raw) <= 262144, 'tags input bound')
    rows = json.loads(raw)
    require(isinstance(rows, list) and 0 < len(rows) <= 100, 'tags page bound')
    seen = set()
    for row in rows:
        name, sha = row['name'], row['commit']['sha']
        require(isinstance(name, str) and name not in seen and
                re.fullmatch(r'[0-9a-f]{40}', sha) is not None, 'duplicate tag or invalid commit')
        seen.add(name)
    exact = [r for r in rows if r['name'] == 'v4.19.88']
    require(len(exact) == 1 and exact[0]['commit']['sha'] == candidate.COMMIT, 'exact tag declaration drift')
    return {'observed_page_count': len(rows), 'selected_tag': 'v4.19.88', 'commit': candidate.COMMIT,
            'entire_tag_history_inspected': False, 'tag_signature_verified': False}


def recipe_context(recipe_path, script_path):
    recipe = load('inspect-musl-cross-make.py')
    actual = recipe.inspect(recipe_path, recipe.SOURCE_SHA, include_text=True)
    texts = {row['path']: row['text'] for row in actual['files']}
    require(texts['hashes/linux-headers-4.19.88.tar.xz.sha1'].split() ==
            [SHA1, 'linux-headers-4.19.88.tar.xz'], 'fixed recipe SHA-1 declaration drift')
    raw = read(script_path, 16384)
    require(identity(raw) == RUST_SCRIPT, 'previously bound Rust script drift')
    script = raw.decode('utf-8')
    require('LINUX_VER=headers-4.19.88\n' in script and
            'LINUX_HEADERS_SITE=https://ci-mirrors.rust-lang.org/rustc/sabotage-linux-tarballs\n' in script and
            'LINUX_HEADERS_SITE=$LINUX_HEADERS_SITE LINUX_VER=$LINUX_VER' in script,
            'Rust recipe override drift')
    lite = texts['litecross/Makefile']
    for fragment in ('$(patsubst aarch64%,arm64%,$(TARGET_ARCH))', '$(wildcard $(LINUX_SRCDIR)/arch/*)',
                     'ARCH=$(LINUX_ARCH)', 'headers_install'):
        require(fragment in lite, 'headers installation recipe drift')
    return {'musl_cross_make_archive': actual['archive'], 'recipe_sha1_statement': SHA1,
            'rust_script': RUST_SCRIPT, 'rust_script_origin': 'previously bound source-recipes-2026-09-10.json',
            'rust_source_rescanned_this_batch': False,
            'selected_recipe_files': [{k: row[k] for k in ('path', 'bytes', 'sha256')} for row in actual['files']
                                      if row['path'] in ('Makefile', 'litecross/Makefile',
                                                        'hashes/linux-headers-4.19.88.tar.xz.sha1')],
            'aarch64_to_arm64_mapping_observed': True, 'actual_published_build_verified': False}


def inspect(directory=route.DIRECTORY, recipe_path=RECIPE):
    require(json.loads(read(directory / 'fetch-plan.json')) == route.plan(), 'initial fetch plan drift')
    require(json.loads(read(directory / 'candidate-plan.json')) == candidate.plan(), 'candidate plan drift')
    fetches, bodies = [], {}
    for name, target in {**route.TARGETS, 'candidate': candidate.TARGET}.items():
        stem, filename = name + '-attempt-1', name + '-attempt-1.' + target['suffix']
        row = json.loads(read(directory / (stem + '.json')))
        argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--proto', '=https', '--tlsv1.2',
                '--max-time', '60', '--max-filesize', str(target['limit']), '--output',
                str(route.DIRECTORY / filename), '--write-out', '%{http_code}\n', target['url']]
        require(row['argv'] == argv and row['target'] == name and row['url'] == target['url'] and
                row['attempt'] == 1 and row['method'] == route.plan()['method'] and row['body']['file'] == filename,
                'fetch scope drift')
        require(row['exit_code'] == 0 and row['http_code'] == '200' and row['parent_timeout'] is False and
                row['passed'] is True and row['transport_passed'] is True, 'fetch outcome drift')
        for channel in ('body', 'stdout', 'stderr'):
            raw = read(directory / (filename if channel == 'body' else stem + '.' + channel), target['limit'])
            require(identity(raw) == {k: row[channel][k] for k in ('bytes', 'sha256')}, 'fetch bytes drift')
            if channel == 'body':
                bodies[name] = raw
            else:
                require(raw.decode('utf-8') == row[channel]['text'] and
                        raw == (b'200\n' if channel == 'stdout' else b''), 'fetch streams drift')
        fetches.append(row)
    require(identity(bodies['headers']) == MIRROR and identity(bodies['candidate']) == CANDIDATE and
            identity(bodies['tags']) == candidate.TAGS, 'observed input identity drift')
    require(hashlib.sha1(bodies['headers']).hexdigest() == SHA1, 'archive recipe SHA-1 mismatch')
    inventories, texts = {}, {}
    for name, compression, top in (('headers', 'xz', 'linux-headers-4.19.88'),
                                   ('candidate', 'gz', 'kernel-headers-' + candidate.COMMIT)):
        inventories[name], texts[name] = content.inventory(content.inputs.unpack(bodies[name], compression), top)
    require(inventories['candidate']['pax_comment'] == candidate.COMMIT, 'candidate PAX commit declaration drift')
    require(content.SELECTED - {'UPDATE.sh', 'create-dist.sh', 'test.sh'} <= texts['headers'].keys() and
            content.SELECTED <= texts['candidate'].keys(), 'selected review files missing')
    require('#define LINUX_VERSION_CODE 267096\n' in texts['headers']['generic/include/linux/version.h'],
            'kernel version declaration drift')
    for phrase in ('LEVELS = * */* */*/* */*/*/* */*/*/*/*', 'headers_install: install', '-D -m 644 $< $@'):
        require(phrase in texts['headers']['Makefile'], 'header install selection rule drift')
    rows = {row['path']: row for row in inventories['headers']['members']}
    require(content.resolve(rows, 'linux-headers-4.19.88/arch/arm64', 'linux-headers-4.19.88') ==
            'linux-headers-4.19.88/arm64', 'arm64 architecture mapping drift')
    projections = {name: content.include_projection(report) for name, report in inventories.items()}
    report = {'kind': 'diagnostic-linux-headers-inputs-v1', 'fetches': fetches,
              'tag_declaration': tag_declaration(bodies['tags']), 'inventories': inventories,
              'comparison': content.compare(inventories['headers'], inventories['candidate']),
              'include_projections': projections, 'arm64_projections_equal': projections['headers'] == projections['candidate'],
              'recipe_context': recipe_context(recipe_path, directory / 'rust-musl-toolchain.sh'),
              'source_acceptance': 'not-assessed', 'cryptography_executed': False,
              'upstream_programs_executed': False, 'license_review_complete': False,
              'methods': {name: identity(read(HERE / name)) for name in
                          ('inspect-linux-headers-inputs.py', 'inspect-linux-headers-content.py',
                           'fetch-linux-headers-inputs.py', 'fetch-linux-headers-candidate.py',
                           'fetch-mpc-mpfr-inputs.py', 'inspect-mpc-mpfr-inputs.py',
                           'inspect-musl-remaining-sources.py', 'inspect-musl-cross-make.py',
                           'inspect-archives.py', 'inspect-musl-verification-keys.py',
                           'inspect-musl-verification-status.py', 'retain-musl-verifier-inputs.py')}}
    return report, texts


def summarize(report):
    comparison = report['comparison']
    return {'kind': 'diagnostic-linux-headers-summary-v1',
            'inputs': {r['target']: {k: r['body'][k] for k in ('bytes', 'sha256')} for r in report['fetches']},
            'inventories': {name: {'tar': r['tar'], 'member_count': len(r['members']), 'type_counts': r['type_counts'],
                                  'selected_review_files': r['selected_review_files'],
                                  'spdx_literal_counts_not_license_coverage': dict(Counter(
                                      d for row in r['members'] for d in row.get('spdx_declarations', []))),
                                  'license_named_paths': [row['path'] for row in r['members'] if
                                      any(w in row['path'].rsplit('/', 1)[-1].upper() for w in ('COPYING', 'LICENSE', 'LICENCE'))]}
                            for name, r in report['inventories'].items()},
            'comparison': {k: len(v) if k in ('mode_differences', 'owner_or_mtime_differences') else v
                           for k, v in comparison.items()},
            'arm64_header_count': len(report['include_projections']['headers']['headers']),
            'arm64_projections_equal': report['arm64_projections_equal'],
            'tag_declaration': report['tag_declaration'], 'recipe_context': report['recipe_context'],
            'source_acceptance': 'not-assessed', 'upstream_programs_executed': False,
            'license_review_complete': False, 'methods': report['methods']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=route.DIRECTORY)
    parser.add_argument('--recipe', type=Path, default=RECIPE)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary', type=Path)
    args = parser.parse_args()
    report, _ = inspect(args.directory, args.recipe)
    with args.output.open('xb') as stream:
        stream.write(gzip.compress((json.dumps(report, sort_keys=True, indent=2) + '\n').encode(), mtime=0))
    if args.summary is not None:
        with args.summary.open('x') as stream:
            stream.write(json.dumps(summarize(report), sort_keys=True, indent=2) + '\n')
    print(json.dumps({'arm64_headers': len(report['include_projections']['headers']['headers']),
                      'arm64_projections_equal': report['arm64_projections_equal'],
                      'output': identity(args.output.read_bytes())}, indent=2))
