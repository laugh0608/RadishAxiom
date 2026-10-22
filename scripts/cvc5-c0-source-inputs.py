#!/usr/bin/env python3
"""Acquire and statically inspect the five C0 source inputs; never execute them.

fetch is network-only acquisition with no retry. inspect audits the entire tar
before creating a new review tree. verify is read-only and rehashes retained
archives and every materialized entry. These observations are not authentication,
license acceptance, build readiness, or solver/tool acceptance.
"""
from __future__ import annotations

import argparse
import bz2
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import tarfile
import time
import unicodedata
import urllib.parse
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[1]
SELECTION = ROOT / 'docs/records/solver-cvc5-c0-2026-10-17/input-selection.json'
RETAINED = ROOT / '.tmp/cvc5-c0-acquisition-2026-10-17'
RECORDS = ROOT / 'docs/records/solver-cvc5-source-review-2026-10-17'
IDS = ('cvc5', 'cadical', 'symfpu', 'libpoly', 'gmp')
TIMEOUT = 180
TOTAL = 192 * 1024 * 1024
LIMITS = {'entries': 100000, 'file_bytes': 128 * 1024 * 1024,
          'expanded_tar_bytes': 1024 * 1024 * 1024, 'path_bytes': 4096,
          'extension_bytes': 16384, 'link_hops': 40}
BLOCK = 1024 * 1024


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_new(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)


def write_equal_or_new(path, raw):
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError('existing-record-differs-refuse-overwrite: ' + str(path))
    else:
        write_new(path, raw)


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + '\n').encode()


def now():
    return datetime.now(timezone.utc).isoformat()


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw), 'raw_digest': 'sha256:' + sha(raw)}


def inputs(path=SELECTION):
    value = json.loads(path.read_bytes())
    rows = {row['id']: row for row in value['source_archives']}
    if set(rows) != set(IDS):
        raise ValueError('source-target-set-drift')
    for name, row in rows.items():
        if row['max_download_bytes'] != (64 if name == 'cvc5' else 32) * 1024 * 1024:
            raise ValueError('download-budget-drift')
        expected = row['expected_archive_sha256']
        if (expected is None) != (name == 'cvc5') or expected is not None and not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError('expected-archive-hash-drift')
        allowed_urls(row, row['url'])
    return [rows[name] for name in IDS]


def allowed_urls(row, url):
    original = urllib.parse.urlsplit(row['url'])
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or parts.username or parts.password or parts.port or parts.fragment:
        raise ValueError('source-url-not-plain-https: ' + url)
    if row['id'] == 'gmp':
        if row['url'] != 'https://github.com/cvc5/cvc5-deps/blob/main/gmp-6.3.0.tar.bz2?raw=true':
            raise ValueError('gmp-initial-target-drift')
        allowed = {row['url'], 'https://github.com/cvc5/cvc5-deps/raw/main/gmp-6.3.0.tar.bz2',
                   'https://github.com/cvc5/cvc5-deps/raw/refs/heads/main/gmp-6.3.0.tar.bz2',
                   'https://raw.githubusercontent.com/cvc5/cvc5-deps/main/gmp-6.3.0.tar.bz2',
                   'https://raw.githubusercontent.com/cvc5/cvc5-deps/refs/heads/main/gmp-6.3.0.tar.bz2'}
    else:
        repos = {'cvc5': 'cvc5/cvc5', 'cadical': 'arminbiere/cadical', 'symfpu': 'cvc5/symfpu', 'libpoly': 'SRI-CSL/libpoly'}
        repo = repos[row['id']]
        prefix = '/' + repo + '/archive/'
        if original.netloc != 'github.com' or not original.path.startswith(prefix) or not original.path.endswith('.tar.gz') or original.query:
            raise ValueError('github-initial-target-drift')
        ref = original.path[len(prefix):-7]
        if not ref or '..' in ref or '?' in ref:
            raise ValueError('invalid-source-ref')
        allowed = {row['url'], f'https://codeload.github.com/{repo}/tar.gz/{ref}'}
        if row['id'] == 'cadical' and ref == 'rel-2.1.3-elevate':
            allowed.add('https://codeload.github.com/arminbiere/cadical/tar.gz/refs/heads/rel-2.1.3-elevate')
    if url not in allowed:
        raise ValueError('source-redirect-outside-exact-target: ' + url)


class Redirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, row, chain):
        self.row, self.chain = row, chain

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        allowed_urls(self.row, newurl)
        if len(self.chain) >= 5 or newurl in [hop['from_url'] for hop in self.chain]:
            raise ValueError('source-redirect-cycle-or-count')
        self.chain.append({'from_url': req.full_url, 'to_url': newurl, 'http_status': code})
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def deadline(signum, frame):
    raise TimeoutError('source-item-total-deadline')


def fetch(continuation=False):
    if continuation:
        manifest, rows, resumed_url = prepare_continuation()
        fetch_rows(rows[1:], manifest, resumed_url)
        return
    rows = inputs()
    RETAINED.mkdir(parents=True, exist_ok=False)
    write_new(RETAINED / 'fetch-helper.py', Path(__file__).read_bytes())
    write_new(RETAINED / 'input-selection.json', SELECTION.read_bytes())
    manifest = {'format': 'radishaxiom-private-cvc5-c0-source-acquisition', 'version': '0.1',
                'scope': 'retained-source-bytes-only-no-authentication-or-acceptance',
                'complete': False, 'signature_authentication': 'not-established',
                'timeout_seconds_per_item': TIMEOUT, 'retries': 0, 'fallback_sources': 0,
                'max_total_bytes': TOTAL, 'total_response_body_bytes': 0,
                'fetch_helper': identity(RETAINED / 'fetch-helper.py'),
                'selection_input': identity(RETAINED / 'input-selection.json'), 'observations': []}
    fetch_rows(rows, manifest)


def prepare_continuation():
    raw = (RETAINED / 'fetch-observations.json').read_bytes()
    manifest = json.loads(raw)
    rows = inputs(RETAINED / 'input-selection.json')
    url = 'https://codeload.github.com/arminbiere/cadical/tar.gz/refs/heads/rel-2.1.3-elevate'
    observations = manifest.get('observations', [])
    if (manifest.get('complete') is not False or len(observations) != 2
            or observations[0].get('id') != 'cvc5' or observations[0].get('status') != 'obtained'
            or observations[1].get('id') != 'cadical' or observations[1].get('status') != 'failed'
            or observations[1].get('bytes_received') != 0
            or observations[1].get('error') != 'source-redirect-outside-exact-target: ' + url
            or (RETAINED / 'cadical.source-archive').exists()):
        raise ValueError('continuation-not-exact-zero-body-cadical-redirect-guard-failure')
    for key in ('fetch_helper', 'selection_input'):
        if identity(ROOT / manifest[key]['path']) != manifest[key]:
            raise ValueError('continuation-frozen-input-drift')
    cvc5 = observations[0]
    actual = identity(RETAINED / 'cvc5.source-archive')
    if actual['raw_digest'] != cvc5['raw_digest'] or actual['bytes'] != cvc5['bytes'] or manifest['total_response_body_bytes'] != cvc5['bytes']:
        raise ValueError('continuation-completed-cvc5-drift')
    write_new(RETAINED / 'fetch-before-redirect-continuation.json', raw)
    write_new(RETAINED / 'continuation-helper.py', Path(__file__).read_bytes())
    manifest['prior_redirect_guard_failure'] = observations[1]
    manifest['prior_fetch_manifest'] = identity(RETAINED / 'fetch-before-redirect-continuation.json')
    manifest['continuation_helper'] = identity(RETAINED / 'continuation-helper.py')
    manifest['continuation_scope'] = 'captured-CaDiCaL-Location-only-no-repeated-initial-GET;three-other-original-source-URLs-first-request'
    manifest['observations'] = observations[:1]
    return manifest, rows, url


def fetch_rows(rows, manifest, resumed_url=None):
    signal.signal(signal.SIGALRM, deadline)
    for selected in rows:
        row = {'id': selected['id'], 'requested_url': selected['url'], 'redirects': [],
               'retained_file': selected['id'] + '.source-archive', 'started_utc': now(),
               'expected_archive_sha256': selected['expected_archive_sha256'], 'status': 'started'}
        manifest['observations'].append(row)
        start, count, digest = time.monotonic(), 0, hashlib.sha256()
        try:
            signal.alarm(TIMEOUT)
            opener = urllib.request.build_opener(Redirect(selected, row['redirects']))
            actual_url = selected['url']
            if resumed_url and selected['id'] == 'cadical':
                actual_url = resumed_url
                allowed_urls(selected, actual_url)
                row['redirects'].append({'from_url': selected['url'], 'to_url': actual_url, 'http_status': 302,
                                         'observation': 'captured-before-guard-rejection;initial-GET-not-repeated'})
            request = urllib.request.Request(actual_url, headers={'Accept-Encoding': 'identity', 'User-Agent': 'RadishAxiom-C0-source/0.1'})
            with opener.open(request, timeout=TIMEOUT) as response, (RETAINED / row['retained_file']).open('xb') as stream:
                allowed_urls(selected, response.url)
                row.update(final_url=response.url, http_status=response.status,
                           response_headers={key.lower(): val for key, val in response.headers.items()
                                             if key.lower() in {'content-type', 'content-length', 'content-encoding', 'etag', 'last-modified'}})
                if response.status != 200 or response.headers.get('Content-Encoding', 'identity') != 'identity':
                    raise ValueError('unexpected-source-http-status-or-encoding')
                cap = min(selected['max_download_bytes'], TOTAL - manifest['total_response_body_bytes'])
                length = response.headers.get('Content-Length')
                if length is not None and (not length.isdigit() or int(length) > cap):
                    raise ValueError('source-declared-length-over-budget')
                while True:
                    chunk = response.read(min(65536, cap - count + 1))
                    if not chunk:
                        break
                    count += len(chunk)
                    manifest['total_response_body_bytes'] += len(chunk)
                    digest.update(chunk)
                    stream.write(chunk)
                    if count > cap:
                        raise ValueError('source-byte-budget-exceeded')
                if not count or length is not None and int(length) != count:
                    raise ValueError('source-empty-or-content-length-mismatch')
            row.update(bytes=count, raw_digest='sha256:' + digest.hexdigest())
            if selected['expected_archive_sha256'] is not None and selected['expected_archive_sha256'] != digest.hexdigest():
                raise ValueError('expected-source-hash-mismatch-stop-no-alternate')
            row['status'] = 'obtained'
        except Exception as error:
            row.update(status='failed', bytes_received=count, partial_raw_digest='sha256:' + digest.hexdigest(),
                       error_type=type(error).__name__, error=str(error))
            raise
        finally:
            signal.alarm(0)
            row.update(finished_utc=now(), elapsed_seconds=round(time.monotonic() - start, 3))
            (RETAINED / 'fetch-observations.json').write_bytes(encoded(manifest))
        print(row['id'], count, row['raw_digest'], flush=True)
    manifest['complete'] = True
    (RETAINED / 'fetch-observations.json').write_bytes(encoded(manifest))
    print('five-source-only fetch complete', manifest['total_response_body_bytes'], flush=True)


# The physical tar parser is deliberately separate from filesystem writes.
class Reader:
    def __init__(self, chunks):
        self.chunks, self.buffer, self.count = iter(chunks), b'', 0
        self.hash = hashlib.sha256()

    def read(self, size):
        if not 0 <= size <= BLOCK:
            raise ValueError('unbounded-tar-read')
        result = bytearray()
        while len(result) < size:
            if not self.buffer:
                self.buffer = next(self.chunks, b'')
                self.count += len(self.buffer)
                if self.count > LIMITS['expanded_tar_bytes']:
                    raise ValueError('expanded-tar-byte-budget')
                self.hash.update(self.buffer)
                if not self.buffer:
                    break
            take = min(size - len(result), len(self.buffer))
            result.extend(self.buffer[:take])
            self.buffer = self.buffer[take:]
        return bytes(result)

    def exact(self, size):
        result = bytearray()
        while size:
            part = self.read(min(size, BLOCK))
            if not part:
                raise ValueError('truncated-tar')
            result.extend(part)
            size -= len(part)
        return bytes(result)

    def padding(self, size):
        if any(self.exact((-size) % 512)):
            raise ValueError('nonzero-tar-member-padding')


def decompress(path):
    with path.open('rb') as stream:
        magic = stream.read(3)
        stream.seek(0)
        decoder = bz2.BZ2Decompressor() if magic == b'BZh' else zlib.decompressobj(31)
        if magic != b'BZh' and magic[:2] != b'\x1f\x8b':
            raise ValueError('unsupported-source-compression')
        pending = b''
        while not decoder.eof:
            if isinstance(decoder, bz2.BZ2Decompressor):
                data = stream.read(65536) if decoder.needs_input else b''
                if decoder.needs_input and not data:
                    raise ValueError('truncated-bzip2')
                output = decoder.decompress(data, max_length=BLOCK)
            else:
                data = pending or stream.read(65536)
                if not data:
                    raise ValueError('truncated-gzip')
                output = decoder.decompress(data, BLOCK)
                pending = decoder.unconsumed_tail
            if output:
                yield output
        if decoder.unused_data or stream.read(1):
            raise ValueError('trailing-or-concatenated-compressed-stream')


def path_name(name):
    if (not name or len(name.encode('utf-8')) > LIMITS['path_bytes'] or name.startswith('/')
            or '\\' in name or any(ord(char) < 32 or ord(char) == 127 for char in name)
            or any(part in {'', '.', '..'} for part in name.split('/'))):
        raise ValueError('unsafe-or-noncanonical-tar-path: ' + repr(name))
    return name


def pax(data):
    fields = {}
    while data:
        prefix, sep, _ = data.partition(b' ')
        if not sep or not re.fullmatch(rb'[1-9][0-9]*', prefix):
            raise ValueError('invalid-pax-length')
        length = int(prefix)
        if length > len(data) or length <= len(prefix) + 2 or data[length - 1:length] != b'\n':
            raise ValueError('invalid-pax-boundary')
        key, sep, val = data[len(prefix) + 1:length - 1].partition(b'=')
        key = key.decode('ascii')
        if not sep or key in fields:
            raise ValueError('invalid-or-duplicate-pax-field')
        fields[key] = val.decode('utf-8')
        data = data[length:]
    return fields


def resolve_links(rows, top):
    nodes = {row['path']: row for row in rows}
    if nodes.get(top, {}).get('kind') != 'directory':
        raise ValueError('single-explicit-top-directory-required')
    for name in nodes:
        parts = name.split('/')
        for end in range(1, len(parts)):
            if nodes.get('/'.join(parts[:end]), {}).get('kind') != 'directory':
                raise ValueError('missing-or-nondirectory-ancestor: ' + name)
    for row in rows:
        if row['kind'] not in {'symlink', 'hardlink'}:
            continue
        target = row['target']
        if not target or target.startswith('/') or '\\' in target or len(target.encode()) > LIMITS['path_bytes'] or any(ord(c) < 32 or ord(c) == 127 for c in target):
            raise ValueError('unsafe-link-target')
        if row['kind'] == 'hardlink':
            resolved = path_name(target)
            if nodes.get(resolved, {}).get('kind') != 'file':
                raise ValueError('hardlink-must-target-explicit-regular-file')
        else:
            parts, pending, hops = row['path'].split('/')[:-1], target.split('/'), 0
            while pending:
                part = pending.pop(0)
                if part in {'', '.'}:
                    continue
                if part == '..':
                    if len(parts) <= 1:
                        raise ValueError('symlink-escapes-top')
                    parts.pop()
                    continue
                name = '/'.join(parts + [part])
                node = nodes.get(name)
                if node is None:
                    raise ValueError('dangling-link: ' + name)
                if node['kind'] == 'symlink':
                    hops += 1
                    if hops > LIMITS['link_hops']:
                        raise ValueError('symlink-cycle-or-hop-budget')
                    nested = node['target']
                    if nested.startswith('/'):
                        raise ValueError('absolute-nested-link')
                    pending = nested.split('/') + pending
                else:
                    if pending and node['kind'] != 'directory':
                        raise ValueError('link-traverses-nondirectory')
                    parts.append(part)
            resolved = '/'.join(parts)
        row['resolved_path'] = resolved


def audit_tar(reader, consume=None):
    rows, names, aliases, local, global_fields = [], set(), set(), {}, {}
    extensions, payload = 0, 0
    while True:
        header = reader.exact(512)
        if header == bytes(512):
            if local or reader.exact(512) != bytes(512):
                raise ValueError('missing-tar-end-or-orphan-extension')
            while tail := reader.read(BLOCK):
                if any(tail):
                    raise ValueError('nonzero-tar-trailer')
            if reader.count % 512:
                raise ValueError('unaligned-tar-trailer')
            break
        member = tarfile.TarInfo.frombuf(header, 'utf-8', 'strict')
        if member.size < 0:
            raise ValueError('negative-member-size')
        if member.type in {tarfile.XHDTYPE, tarfile.XGLTYPE, tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK}:
            extensions += 1
            if extensions > LIMITS['entries'] or member.size > LIMITS['extension_bytes']:
                raise ValueError('tar-extension-budget')
            raw = reader.exact(member.size)
            reader.padding(member.size)
            if member.type in {tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK}:
                key = 'path' if member.type == tarfile.GNUTYPE_LONGNAME else 'linkpath'
                if key in local or not raw.endswith(b'\0') or b'\0' in raw[:-1]:
                    raise ValueError('invalid-or-stacked-gnu-extension')
                local[key] = raw[:-1].decode('utf-8')
            else:
                fields = pax(raw)
                if member.type == tarfile.XGLTYPE:
                    if global_fields or rows or local or set(fields) != {'comment'} or not re.fullmatch('[0-9a-f]{40}', fields['comment']):
                        raise ValueError('unsupported-global-pax')
                    global_fields = fields
                else:
                    if set(fields) - {'path', 'linkpath', 'mtime', 'atime', 'ctime'} or set(fields) & set(local):
                        raise ValueError('unsupported-or-stacked-local-pax')
                    local.update(fields)
            continue
        if len(rows) >= LIMITS['entries'] or member.size > LIMITS['file_bytes']:
            raise ValueError('source-member-count-or-byte-budget')
        kind = {tarfile.REGTYPE: 'file', tarfile.AREGTYPE: 'file', tarfile.DIRTYPE: 'directory',
                tarfile.SYMTYPE: 'symlink', tarfile.LNKTYPE: 'hardlink'}.get(member.type)
        if kind is None:
            raise ValueError('unsupported-device-fifo-or-other-tar-type')
        raw_name = header[:100].split(b'\0', 1)[0].decode('utf-8')
        if header[257:265] == b'ustar\x0000':
            prefix = header[345:500].split(b'\0', 1)[0].decode('utf-8')
            if prefix:
                raw_name = prefix + '/' + raw_name
        name = local.get('path', raw_name)
        if kind == 'directory':
            name = name.removesuffix('/')
        name = path_name(name)
        folded = unicodedata.normalize('NFC', name).casefold()
        if name in names or folded in aliases:
            raise ValueError('duplicate-casefold-or-unicode-path-collision: ' + name)
        names.add(name)
        aliases.add(folded)
        if kind != 'file' and member.size or kind not in {'symlink', 'hardlink'} and ('linkpath' in local or member.linkname):
            raise ValueError('unexpected-nonfile-payload-or-nonlink-target')
        row = {'path': name, 'kind': kind, 'bytes': member.size, 'original_mode': format(member.mode, '04o'),
               'uid': member.uid, 'gid': member.gid, 'uname': member.uname, 'gname': member.gname,
               'mtime': member.mtime, 'tar_type_hex': member.type.hex()}
        if kind in {'symlink', 'hardlink'}:
            row['target'] = local.get('linkpath', member.linkname)
            row['target_bytes'] = len(row['target'].encode())
        local = {}
        if kind == 'file':
            data = reader.exact(member.size)
            payload += len(data)
            if payload > LIMITS['expanded_tar_bytes']:
                raise ValueError('expanded-file-payload-budget')
            reader.padding(member.size)
            row.update(sha256=sha(data), git_blob_sha1=hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest())
            if consume:
                consume(row, data)
        rows.append(row)
    tops = {row['path'].split('/')[0] for row in rows}
    if len(tops) != 1:
        raise ValueError('multiple-source-roots')
    top = tops.pop()
    resolve_links(rows, top)
    return {'top': top, 'limits': LIMITS, 'tar_bytes': reader.count, 'tar_sha256': reader.hash.hexdigest(),
            'payload_bytes': payload, 'extensions': extensions, 'global_pax': global_fields,
            'type_counts': dict(Counter(row['kind'] for row in rows)), 'entries': sorted(rows, key=lambda row: row['path'])}


def audit(path, consume=None):
    return audit_tar(Reader(decompress(path)), consume)


def retained_inputs(partial_cvc5=False):
    manifest = json.loads((RETAINED / 'fetch-observations.json').read_bytes())
    if (not manifest.get('complete') and not partial_cvc5) or manifest.get('signature_authentication') != 'not-established':
        raise ValueError('incomplete-source-acquisition')
    for key in ('fetch_helper', 'selection_input', 'continuation_helper', 'prior_fetch_manifest'):
        if key not in manifest:
            continue
        saved = manifest[key]
        if identity(ROOT / saved['path']) != saved:
            raise ValueError('frozen-acquisition-input-bytes-changed')
    rows = inputs(RETAINED / 'input-selection.json')
    if partial_cvc5:
        rows = rows[:1]
    elif len(manifest['observations']) != len(rows):
        raise ValueError('source-observation-count')
    total = 0
    for selected, observed in zip(rows, manifest['observations']):
        if selected['id'] != observed['id'] or observed['status'] != 'obtained' or observed['http_status'] != 200 or observed['requested_url'] != selected['url']:
            raise ValueError('source-observation-identity-status')
        previous = selected['url']
        for hop in observed['redirects']:
            if hop['from_url'] != previous or hop['http_status'] not in {301, 302, 303, 307, 308}:
                raise ValueError('source-redirect-chain-disconnected')
            allowed_urls(selected, hop['to_url'])
            previous = hop['to_url']
        if previous != observed['final_url'] or len(observed['redirects']) > 5:
            raise ValueError('source-redirect-chain-end-or-count')
        path = RETAINED / (selected['id'] + '.source-archive')
        ident = identity(path)
        total += ident['bytes']
        if ident['raw_digest'] != observed['raw_digest'] or ident['bytes'] != observed['bytes'] or ident['bytes'] > selected['max_download_bytes']:
            raise ValueError('retained-source-byte-mismatch')
        if selected['expected_archive_sha256'] is not None and ident['raw_digest'] != 'sha256:' + selected['expected_archive_sha256']:
            raise ValueError('retained-expected-source-hash-mismatch')
    if (not partial_cvc5 and total != manifest['total_response_body_bytes']) or total > TOTAL:
        raise ValueError('retained-source-total-mismatch')
    return manifest, rows


def materialize(path, inventory, destination):
    destination.mkdir(parents=True, exist_ok=False)
    top = inventory['top']
    for row in inventory['entries']:
        if row['kind'] == 'directory':
            (destination / row['path']).mkdir(mode=0o700, exist_ok=False)
    def save(row, data):
        target = destination / row['path']
        # Ancestors were audited as explicit directories and no links exist yet.
        with target.open('xb') as output:
            output.write(data)
        target.chmod(0o600)
    second = audit(path, save)
    if second != inventory:
        raise ValueError('archive-changed-between-audit-and-materialization')
    for row in inventory['entries']:
        target = destination / row['path']
        if row['kind'] == 'symlink':
            os.symlink(row['target'], target)
        elif row['kind'] == 'hardlink':
            os.link(destination / row['resolved_path'], target, follow_symlinks=False)
    return destination / top


def license_observation(row, data):
    base = row['path'].rsplit('/', 1)[-1]
    named = bool(re.match(r'(?i)^(copying|licen[cs]e|copyright|notice|authors|patents)([._-]|$)', base))
    matches = []
    for line in data.splitlines():
        if re.search(rb'(?i)copyright|SPDX-License-Identifier:|permission is hereby granted|GNU (?:General|Lesser)|license exception|licensing exception|all rights reserved', line):
            matches.append(line.decode('utf-8', 'backslashreplace').strip()[:220])
    if not named and not matches:
        return None
    return {'archive_path': row['path'], 'bytes': row['bytes'], 'sha256': row['sha256'],
            'named_license_material': named, 'matched_line_count': len(matches),
            'short_declarations': matches[:2], 'classification': 'requires-contextual-component-review'}


def cvc5_tree_check(inventory):
    retained = ROOT / '.tmp/solver-cli-licenses-2026-10-17/cvc5-tree.json'
    original = json.loads(retained.read_bytes())
    if original.get('truncated'):
        raise ValueError('retained-publisher-git-tree-truncated')
    if inventory['global_pax'].get('comment') != 'f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341':
        raise ValueError('cvc5-archive-commit-comment-mismatch')
    expected = {entry['path']: entry for entry in original['tree'] if entry['type'] == 'blob'}
    actual = {}
    prefix = inventory['top'] + '/'
    for row in inventory['entries']:
        if row['kind'] in {'file', 'symlink'}:
            relative = row['path'][len(prefix):]
            blob = row.get('git_blob_sha1')
            if row['kind'] == 'symlink':
                raw = row['target'].encode()
                blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            actual[relative] = blob
    missing, extra = sorted(set(expected) - set(actual)), sorted(set(actual) - set(expected))
    mismatch = sorted(name for name in set(expected) & set(actual) if expected[name]['sha'] != actual[name])
    if missing or extra or mismatch:
        raise ValueError('cvc5-publisher-tree-blob-difference: ' + str({'missing': missing[:15], 'extra': extra[:15], 'mismatch': mismatch[:15]}))
    return {'retained_git_tree': identity(retained), 'blob_count': len(actual),
            'all_retained_git_blob_sha1_equal': True, 'scope': 'consistency-with-retained-unsigned-publisher-tree-not-signature-authentication'}


def inspect(partial_cvc5=False, refresh_summary=False):
    manifest, selected = retained_inputs(partial_cvc5)
    RECORDS.mkdir(parents=True, exist_ok=True)
    summaries = []
    for row in selected:
        name, licenses = row['id'], []
        archive = RETAINED / (row['id'] + '.source-archive')
        def scan(entry, data):
            observation = license_observation(entry, data)
            if observation:
                licenses.append(observation)
        inventory = audit(archive, scan)
        if row['commit'] is not None and inventory['global_pax'].get('comment') != row['commit']:
            raise ValueError('archive-pax-comment-does-not-match-selected-commit: ' + name)
        destination = RETAINED / 'sources' / name
        if destination.exists():
            source_root = destination / inventory['top']
        else:
            source_root = materialize(archive, inventory, destination)
        git_check = cvc5_tree_check(inventory) if name == 'cvc5' else None
        tree_path = RECORDS / (name + '-tree.json')
        write_equal_or_new(tree_path, encoded({'format': 'radishaxiom-private-cvc5-source-tree', 'version': '0.1',
                                     'source_id': name, 'archive': identity(archive), **inventory}))
        lic_path = RECORDS / (name + '-license-inventory.json')
        write_equal_or_new(lic_path, encoded({'format': 'radishaxiom-private-cvc5-source-license-inventory', 'version': '0.1',
                                    'source_id': name, 'scope': 'full-regular-file-byte-scan-plus-license-filenames; contextual-review-required; no-license-or-distribution-acceptance',
                                    'scan_pattern': 'copyright|SPDX-License-Identifier|permission-is-hereby-granted|GNU-General/Lesser|license/licensing-exception|all-rights-reserved',
                                    'materials': licenses}))
        summaries.append({'id': name, 'archive': identity(archive), 'source_root': str(source_root.relative_to(ROOT)),
                          'tree_inventory': identity(tree_path), 'license_inventory': identity(lic_path),
                          'entries': len(inventory['entries']), 'payload_bytes': inventory['payload_bytes'],
                          'tar_bytes': inventory['tar_bytes'], 'type_counts': inventory['type_counts'],
                          'selected_commit': row['commit'],
                          'archive_commit_comment': inventory['global_pax'].get('comment'),
                          'archive_commit_comment_matches_selected': True if row['commit'] is not None else None,
                          'cvc5_retained_git_blob_check': git_check})
        print(name, 'static review tree ready:', source_root, flush=True)
    if partial_cvc5:
        print('partial cvc5-only inspection; five-source completion not claimed', flush=True)
        return
    inspector = Path(__file__).resolve()
    snapshot = RETAINED / ('inspection-helper-' + sha(inspector.read_bytes()) + '.py')
    write_equal_or_new(snapshot, inspector.read_bytes())
    result = {'format': 'radishaxiom-private-cvc5-c0-source-inputs', 'version': '0.1',
              'scope': 'source-byte-static-review-only', 'signature_authentication': 'not-established',
              'license_acceptance': 'not-accepted', 'build_ready': False, 'tool_acceptance': 'not-accepted',
              'acquisition_manifest': identity(RETAINED / 'fetch-observations.json'),
              'fetch_helper': manifest['fetch_helper'], 'inspection_helper': identity(inspector), 'retained_inspection_helper': identity(snapshot),
              'download_selection': manifest['selection_input'],
              'sources': summaries, 'executed_upstream_programs': False,
              'materialization_policy': '0700 directories;0600 regular files;no owner/original executable/setuid application;contained audited links only'}
    if refresh_summary:
        (RECORDS / 'source-inputs.json').write_bytes(encoded(result))
    else:
        write_new(RECORDS / 'source-inputs.json', encoded(result))


def verify():
    retained_inputs()
    summary = json.loads((RECORDS / 'source-inputs.json').read_bytes())
    for key in ('inspection_helper', 'retained_inspection_helper', 'download_selection'):
        if identity(ROOT / summary[key]['path']) != summary[key]:
            raise ValueError('inspection-helper-or-frozen-selection-drift;explicit-summary-refresh-required')
    for source in summary['sources']:
        for key in ('archive', 'tree_inventory', 'license_inventory'):
            if identity(ROOT / source[key]['path']) != source[key]:
                raise ValueError('record-or-archive-byte-mismatch')
        tree = json.loads((ROOT / source['tree_inventory']['path']).read_bytes())
        fresh = audit(ROOT / source['archive']['path'])
        if source['selected_commit'] is not None and fresh['global_pax'].get('comment') != source['selected_commit']:
            raise ValueError('verified-pax-comment-selected-commit-mismatch')
        if any(tree[key] != val for key, val in fresh.items()):
            raise ValueError('independent-reparse-inventory-mismatch')
        base = ROOT / source['source_root']
        root = base.parent
        expected = {entry['path']: entry for entry in tree['entries']}
        actual = {str(path.relative_to(root)) for path in root.rglob('*')}
        if actual != set(expected):
            raise ValueError('review-tree-member-set-drift')
        for name, entry in expected.items():
            path = root / name
            mode = path.lstat().st_mode
            if entry['kind'] == 'directory':
                if not stat.S_ISDIR(mode):
                    raise ValueError('review-tree-directory-drift')
            elif entry['kind'] == 'symlink':
                if not stat.S_ISLNK(mode) or os.readlink(path) != entry['target']:
                    raise ValueError('review-tree-link-drift')
            else:
                if not stat.S_ISREG(mode):
                    raise ValueError('review-tree-file-type-drift')
                target = expected[entry['resolved_path']] if entry['kind'] == 'hardlink' else entry
                if path.stat().st_size != target['bytes'] or sha(path.read_bytes()) != target['sha256']:
                    raise ValueError('review-tree-file-content-drift')
        if source['id'] == 'cvc5':
            cvc5_tree_check(fresh)
    print('five retained archives, physical tar inventories, and all materialized entries verified; no authentication/acceptance', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('fetch', 'continue-cadical-redirect', 'inspect-cvc5', 'inspect', 'refresh-summary', 'verify'))
    args = parser.parse_args()
    if args.action == 'continue-cadical-redirect':
        fetch(continuation=True)
    elif args.action == 'refresh-summary':
        inspect(refresh_summary=True)
    elif args.action == 'inspect-cvc5':
        inspect(partial_cvc5=True)
    else:
        globals()[args.action]()


if __name__ == '__main__':
    main()
