#!/usr/bin/env python3
"""Bounded, offline C1 package-content inventory; never install or execute payloads."""
import argparse
import bz2
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import lzma
from pathlib import Path
import posixpath
import re
import signal
import struct
import tarfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / 'docs/records/solver-cvc5-c1-review-2026-10-23'
RETAINED = RECORDS / 'retained-inventory.json'
PLAN = ROOT / 'docs/records/solver-cvc5-c1-2026-10-22/acquisition-plan.json'
SDK = ROOT / 'docs/records/solver-cvc5-c0-2026-10-17/sdk-selection.json'
OUTPUT = ROOT / 'artifacts/cvc5-c1-content-review-2026-10-23'
SPEC = importlib.util.spec_from_file_location('debian_chain', ROOT / 'scripts/inspect-debian-source-chain.py')
CHAIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHAIN)
LIMITS = {'total_expanded_bytes': 4 * 1024**3, 'archive_expanded_bytes': 1024**3,
          'entries_per_archive': 100000, 'regular_file_bytes': 128 * 1024**2,
          'selected_text_bytes': 32 * 1024**2, 'total_selected_bytes': 64 * 1024**2,
          'seconds': 600, 'path_bytes': 4096}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw), 'sha256': sha(raw)}


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + '\n').encode()


def ar_members(raw):
    require(raw.startswith(b'!<arch>\n'), 'ar-magic')
    offset = 8
    while offset < len(raw):
        header = raw[offset:offset + 60]
        require(len(header) == 60 and header[58:60] == b'`\n', 'ar-header')
        require(header[48:58].strip().isdigit(), 'ar-size')
        size = int(header[48:58])
        end = offset + 60 + size
        require(end <= len(raw), 'ar-truncated')
        name = header[:16].decode('ascii').strip()
        yield name, raw[offset + 60:end]
        require(not size % 2 or raw[end:end + 1] == b'\n', 'ar-padding')
        offset = end + size % 2
    require(offset == len(raw), 'ar-trailer')


def canonical(name):
    require(len(name.encode()) <= LIMITS['path_bytes'] and '\x00' not in name and '\\' not in name,
            'member-path-size-or-character')
    while name.startswith('./'):
        name = name[2:]
    name = name.removesuffix('/')
    if name in ('', '.'):
        return ''
    require(not name.startswith('/') and all(part not in ('', '.', '..') for part in name.split('/')),
            'member-path-escape-or-alias')
    return name


def expanded_chunks(raw, filename):
    is_gzip = filename.endswith('.gz')
    if filename.endswith('.xz'):
        decoder = lzma.LZMADecompressor(memlimit=128 * 1024**2)
    elif filename.endswith('.gz'):
        decoder = zlib.decompressobj(31)
    elif filename.endswith('.bz2'):
        decoder = bz2.BZ2Decompressor()
    else:
        require(filename.endswith('.tar'), 'unsupported-compression')
        for offset in range(0, len(raw), 65536):
            yield raw[offset:offset + 65536]
        return
    offset, pending = 0, b''
    while not decoder.eof:
        if is_gzip:
            take_input = not pending
        else:
            take_input = decoder.needs_input
        if take_input:
            require(offset < len(raw), 'compressed-truncated')
            pending = raw[offset:offset + 65536]
            offset += len(pending)
        out = decoder.decompress(pending, 65536)
        pending = decoder.unconsumed_tail if is_gzip else b''
        if out:
            yield out
    require(not decoder.unused_data and offset == len(raw), 'compressed-trailing-or-concatenated-data')


class ExpandedReader:
    def __init__(self, chunks, budget):
        self.chunks, self.budget = iter(chunks), budget
        self.buffer, self.count = b'', 0

    def read(self, size):
        require(0 <= size <= 1024**2, 'unbounded-expanded-read')
        result = bytearray()
        while len(result) < size:
            if not self.buffer:
                self.buffer = next(self.chunks, b'')
                self.count += len(self.buffer)
                self.budget['expanded'] += len(self.buffer)
                require(self.count <= LIMITS['archive_expanded_bytes']
                        and self.budget['expanded'] <= LIMITS['total_expanded_bytes'], 'expanded-byte-budget')
                if not self.buffer:
                    break
            take = min(size - len(result), len(self.buffer))
            result.extend(self.buffer[:take])
            self.buffer = self.buffer[take:]
        return bytes(result)


def elf_header(raw):
    if not raw.startswith(b'\x7fELF'):
        return None
    require(len(raw) >= 20 and raw[4] in (1, 2) and raw[5] in (1, 2), 'elf-header')
    kind, machine = struct.unpack(('<' if raw[5] == 1 else '>') + 'HH', raw[16:20])
    return {'class': 32 if raw[4] == 1 else 64, 'endianness': 'little' if raw[5] == 1 else 'big',
            'type': kind, 'machine': machine, 'scope': 'header-only-not-load-or-runtime-acceptance'}


def static_members(raw):
    header = elf_header(raw)
    if header is not None:
        require(header['type'] == 1, 'a-suffix-non-relocatable-elf')
        return {'container': 'elf-relocatable-with-a-suffix', 'elf_objects': 1,
                'elf_header_counts': {f"{header['class']}:{header['endianness']}:{header['machine']}:{header['type']}": 1},
                'non_elf_members': []}
    counts, other, objects = Counter(), [], 0
    for name, content in ar_members(raw):
        if name in ('/', '//', '/SYM64/') or name.startswith('__.SYMDEF'):
            continue
        if name.startswith('#1/'):
            length = int(name[3:])
            require(length <= len(content), 'bsd-ar-name-size')
            content = content[length:]
        header = elf_header(content)
        if header is None:
            other.append(name)
        else:
            counts[f"{header['class']}:{header['endianness']}:{header['machine']}:{header['type']}"] += 1
            objects += 1
    return {'container': 'ar', 'elf_objects': objects, 'elf_header_counts': dict(counts), 'non_elf_members': other}


def want_text(name, control, source):
    if control:
        return name in {'control', 'preinst', 'postinst', 'prerm', 'postrm', 'triggers', 'conffiles'}
    base = name.rsplit('/', 1)[-1].lower()
    if source:
        return '/debian/' + base in '/' + name and base in {'copyright', 'rules', 'control'} or '/debian/patches/' in '/' + name
    return base == 'copyright' or name.startswith('usr/share/common-licenses/') or name.endswith('.pc')


def scan_tar(raw, filename, label, budget, output, control=False, source=False):
    reader = ExpandedReader(expanded_chunks(raw, filename), budget)
    entries, names = [], set()
    with tarfile.open(fileobj=reader, mode='r|', bufsize=65536) as archive:
        for member in archive:
            name = canonical(member.name)
            if not name:
                require(member.isdir(), 'non-directory-root')
                continue
            require(name not in names and len(names) < LIMITS['entries_per_archive'], 'duplicate-or-entry-budget')
            names.add(name)
            kind = 'file' if member.isfile() else 'directory' if member.isdir() else 'symlink' if member.issym() else 'hardlink' if member.islnk() else 'unsupported'
            require(kind != 'unsupported' and not member.issparse(), 'device-fifo-sparse-or-unknown-entry')
            require(0 <= member.size <= LIMITS['regular_file_bytes'], 'member-byte-budget')
            row = {'path': name, 'kind': kind, 'bytes': member.size, 'mode': format(member.mode, '04o')}
            if kind in ('symlink', 'hardlink'):
                require(len(member.linkname.encode()) <= LIMITS['path_bytes'] and '\x00' not in member.linkname,
                        'link-target-size-or-nul')
                row['target'] = member.linkname
            if kind == 'file':
                selected = want_text(name, control, source)
                static = not control and not source and name.endswith('.a')
                require(not selected or member.size <= LIMITS['selected_text_bytes'], 'selected-text-budget')
                digest, count, head, chunks = hashlib.sha256(), 0, b'', []
                stream = archive.extractfile(member)
                require(stream is not None, 'missing-regular-stream')
                while chunk := stream.read(65536):
                    count += len(chunk)
                    require(count <= member.size, 'regular-file-overflow')
                    digest.update(chunk)
                    if len(head) < 64:
                        head += chunk[:64 - len(head)]
                    if selected or static:
                        chunks.append(chunk)
                require(count == member.size, 'regular-file-truncated')
                row['sha256'] = digest.hexdigest()
                header = elf_header(head)
                if header:
                    row['elf'] = header
                if static:
                    row['static_archive'] = static_members(b''.join(chunks))
                if selected:
                    budget['selected'] += count
                    require(budget['selected'] <= LIMITS['total_selected_bytes'], 'total-selected-budget')
                    # No archive path is materialized: regular text only, keyed
                    # by immutable bytes. No links, modes or ownership restored.
                    target = output / 'text' / (row['sha256'] + '.txt')
                    data = b''.join(chunks)
                    if target.exists():
                        require(target.read_bytes() == data, 'text-store-drift')
                    else:
                        with target.open('xb') as stream:
                            stream.write(data)
                    row['review_text_path'] = str(target.relative_to(ROOT))
            else:
                require(member.size == 0, 'non-file-payload')
            entries.append(row)
    # Consume the remaining compressed stream to enforce decompression limits
    # and trailer checks even when tarfile stops at the tar terminator.
    while reader.read(65536):
        pass
    return {'label': label, 'expanded_bytes': reader.count, 'entries': entries}


def deb(raw, expected, budget, output):
    members = {}
    for name, content in ar_members(raw):
        name = name.removesuffix('/')
        require(name not in members, 'duplicate-deb-member')
        members[name] = content
    require(members.get('debian-binary') == b'2.0\n' and len(members) == 3, 'deb-layout')
    controls = [name for name in members if re.fullmatch(r'control\.tar\.(xz|gz|bz2)', name)]
    payloads = [name for name in members if re.fullmatch(r'data\.tar\.(xz|gz|bz2)', name)]
    require(len(controls) == len(payloads) == 1, 'deb-compression-layout')
    control = scan_tar(members[controls[0]], controls[0], 'control', budget, output, control=True)
    data = scan_tar(members[payloads[0]], payloads[0], 'data', budget, output)
    item = next((row for row in control['entries'] if row['path'] == 'control'), None)
    require(item is not None and item['kind'] == 'file', 'deb-control-missing')
    fields = list(CHAIN.stanzas((ROOT / item['review_text_path']).read_text().splitlines(keepends=True)))
    require(len(fields) == 1, 'deb-control-count')
    fields = fields[0]
    for key in ('Package', 'Version', 'Architecture', 'Source', 'Depends', 'Pre-Depends', 'Provides',
                'Conflicts', 'Breaks', 'Replaces', 'Essential', 'Multi-Arch', 'Built-Using', 'Static-Built-Using'):
        require(fields.get(key.lower()) == expected.get(key), 'control-index-mismatch:' + key)
    return {'package': expected['Package'], 'version': expected['Version'], 'architecture': expected['Architecture'],
            'source_package': expected['source_package'], 'source_version': expected['source_version'],
            'control_fields_match_index': True, 'control': control, 'data': data}


def timeout(signum, frame):
    raise TimeoutError('content-review-batch-deadline')


def scan_diff(raw, filename, budget, output):
    reader = ExpandedReader(expanded_chunks(raw, filename), budget)
    content = bytearray()
    while chunk := reader.read(65536):
        content.extend(chunk)
        require(len(content) <= LIMITS['selected_text_bytes'], 'selected-text-budget')
    content = bytes(content)
    require(content.startswith(b'--- ') and b'\n+++ ' in content and b'\n@@ ' in content,
            'source-diff-format')
    content.decode('utf-8')
    budget['selected'] += len(content)
    require(budget['selected'] <= LIMITS['total_selected_bytes'], 'total-selected-budget')
    target = output / 'text' / (sha(content) + '.txt')
    with target.open('xb') as stream:
        stream.write(content)
    return {'format': 'debian-1.0-unified-diff', 'expanded_bytes': reader.count,
            'sha256': sha(content), 'review_text_path': str(target.relative_to(ROOT)),
            'patch_applied': False}


def inspect(output=OUTPUT):
    require(sha(PLAN.read_bytes()) == '165672c67dcaea6963f00dc13e2128a3563fc8a59b58e27326ae58e47f1749cc', 'base-plan-drift')
    plan, retained, sdk = (json.loads(path.read_bytes()) for path in (PLAN, RETAINED, SDK))
    require(not output.exists() and not output.is_symlink(), 'review-output-already-exists')
    packages = {row['Filename']: row for row in sdk['packages']}
    output.mkdir(parents=True)
    (output / 'text').mkdir()
    with (output / 'inspection-method.py').open('xb') as stream:
        stream.write(Path(__file__).read_bytes())
    budget, observations = {'expanded': 0, 'selected': 0}, []
    result = {'format': 'radishaxiom-private-cvc5-c1-content-review', 'version': '0.1',
              'method': identity(Path(__file__)), 'inputs': [identity(path) for path in (PLAN, RETAINED, SDK)],
              'started_utc': datetime.now(timezone.utc).isoformat(), 'limits': LIMITS,
              'scope': 'offline-archive-streams-and-review-text-only', 'complete': False,
              'installed': False, 'built': False, 'payload_executed': False,
              'input_acceptance': 'not-accepted', 'build_ready': False, 'observations': observations}
    old_alarm = signal.signal(signal.SIGALRM, timeout)
    signal.alarm(LIMITS['seconds'])
    try:
        for index, row in enumerate(plan['entries'], 1):
            if row['kind'] not in {'binary', 'debian-patch', 'native-source', 'dsc'}:
                continue
            path = ROOT / retained['inventory'][index - 1]['path']
            require(path.resolve() == path and path.is_file() and not path.is_symlink(), 'input-path')
            raw = path.read_bytes()
            require(len(raw) == row['declared_bytes'] and sha(raw) == row['declared_sha256'], 'input-digest-or-size')
            observation = {'index': index, 'kind': row['kind'], 'input': identity(path), 'owners': row['owners']}
            observations.append(observation)
            if row['kind'] == 'binary':
                observation.update(deb(raw, packages[row['relative_path'].removeprefix('inputs/')], budget, output))
            elif row['kind'] == 'dsc':
                # The raw envelope is recorded; maintainer signatures are not
                # claimed verified by archive-index byte correspondence.
                observation.update(text_encoding='utf-8', maintainer_signature_verified=False)
                raw.decode('utf-8')
            elif row['kind'] == 'debian-patch' and path.name.endswith('.diff.gz'):
                observation['source_diff'] = scan_diff(raw, path.name, budget, output)
            else:
                observation['source'] = scan_tar(raw, path.name, row['kind'], budget, output, source=True)
            observation['status'] = 'inspected'
            if len(observations) % 25 == 0:
                print(json.dumps({'inspected': len(observations), 'budget': budget}), flush=True)
        require(len(observations) == 374, 'inspection-count')
        result['complete'] = True
    except Exception as error:
        result['failure'] = {'type': type(error).__name__, 'reason': str(error),
                             'index': observations[-1]['index'] if observations else None}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_alarm)
        result.update(finished_utc=datetime.now(timezone.utc).isoformat(), consumed=budget)
        raw = encoded(result)
        with (output / 'content-inventory.json.gz').open('xb') as stream:
            stream.write(gzip.compress(raw, mtime=0))
        print(json.dumps({key: result.get(key) for key in ('complete', 'consumed', 'failure')}), flush=True)
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect-authorized', action='store_true', required=True)
    parser.add_argument('--attempt', type=int, default=1, choices=range(1, 10))
    args = parser.parse_args()
    output = OUTPUT if args.attempt == 1 else OUTPUT.with_name(OUTPUT.name + f'-attempt-{args.attempt}')
    raise SystemExit(inspect(output))
