#!/usr/bin/env python3
"""Offline full-file notice census and patch blob observations for the retained headers batch."""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import tarfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('previous', HERE / 'inspect-linux-headers-inputs.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
store = previous.load('prepare-mpfr-verification.py')
require, identity = previous.require, previous.identity
PREFIX = '.tmp/linux-headers-inputs-38edae0-20260925/'
RECORD = 'docs/records/rust-linux-input-review/'


def notices(raw):
    """Record literal lines, not parsed SPDX expressions or a license conclusion."""
    require(len(raw) <= previous.content.inputs.MAX_MEMBER, 'notice file size bound')
    declarations, copyrights = [], []
    for number, line in enumerate(raw.split(b'\n'), 1):
        if b'SPDX-License-Identifier:' in line:
            declarations.append({'line': number, 'text': line.decode('utf-8', errors='backslashreplace')})
        if re.search(rb'copyright', line, re.IGNORECASE):
            copyrights.append(number)
    return {'spdx_lines': declarations, 'copyright_line_numbers': copyrights}


def scope_summary(rows):
    expressions = Counter()
    for row in rows:
        for declaration in row['spdx_lines']:
            literal = declaration['text'].split('SPDX-License-Identifier:', 1)[1]
            expressions[literal.strip().removesuffix('*/').strip()] += 1
    return {'files': len(rows), 'with_spdx_marker': sum(bool(r['spdx_lines']) for r in rows),
            'without_spdx_marker': sum(not r['spdx_lines'] for r in rows),
            'with_copyright_word': sum(bool(r['copyright_line_numbers']) for r in rows),
            'literal_declaration_counts': dict(sorted(expressions.items()))}


def patch_observations(files):
    output = []
    for path in sorted(p for p in files if p.startswith('patches/') and p.endswith('.patch')):
        raw = files[path]
        targets = re.findall(rb'^\+\+\+ b/([^\r\n]+)$', raw, re.MULTILINE)
        indices = re.findall(rb'^index ([0-9a-f]{7})\.\.([0-9a-f]{7}) 100644$', raw, re.MULTILINE)
        require(len(targets) == len(indices) == 1, 'patch observation profile drift')
        target = targets[0].decode('ascii')
        require(target in files, 'patch target absent')
        body = files[target]
        blob = hashlib.sha1(b'blob ' + str(len(body)).encode('ascii') + b'\0' + body).hexdigest()
        output.append({'path': path, 'patch': identity(raw), 'target': target,
                       'declared_before_blob_prefix': indices[0][0].decode('ascii'),
                       'declared_after_blob_prefix': indices[0][1].decode('ascii'),
                       'actual_target_git_blob_sha1': blob,
                       'after_prefix_matches_target': blob.startswith(indices[0][1].decode('ascii')),
                       'patch_applied': False, 'patch_authenticated': False})
    return output


def review(root=previous.ROOT):
    retained, checked = store.read_store(root, 'linux-headers-inputs-38edae0-20260925',
        'linux-headers-retention-manifest-2026-09-25.json',
        '961ba896f42f9324e8349def7c50663efbbca325fe764f20eb734169b9aca8b3')
    for path, raw in retained.items():
        if path.startswith(RECORD) and path.endswith('.py'):
            require(previous.read(root / path) == raw, 'retained method drift')
    old = json.loads(gzip.decompress(retained[RECORD + 'linux-headers-inputs-2026-09-25.json.gz']))
    inventories, files, entries = {}, {}, {}
    for name, suffix, compression, top, expected in (
        ('headers', 'tar.xz', 'xz', 'linux-headers-4.19.88', previous.MIRROR),
        ('candidate', 'tar.gz', 'gz', 'kernel-headers-' + previous.candidate.COMMIT, previous.CANDIDATE),
    ):
        compressed = retained[PREFIX + name + '-attempt-1.' + suffix]
        require(identity(compressed) == expected, 'archive identity drift')
        raw = previous.content.inputs.unpack(compressed, compression)
        inventory, _ = previous.content.inventory(raw, top)
        require(inventory == old['inventories'][name], 'historical inventory replay drift')
        inventories[name], files[name] = inventory, {}
        # Read only regular members after the existing bounded logical archive validation.
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
            for member in archive:
                if member.isfile():
                    body = archive.extractfile(member).read(previous.content.inputs.MAX_MEMBER + 1)
                    require(len(body) == member.size, 'regular member size drift')
                    files[name][member.name[len(top) + 1:]] = body
        entries[name] = [{'path': path, **identity(body), **notices(body)}
                         for path, body in sorted(files[name].items())]
    projection = previous.content.include_projection(inventories['headers'])['headers']
    require(projection == previous.content.include_projection(inventories['candidate'])['headers'],
            'projection comparison drift')
    index = {row['path']: row for row in entries['headers']}
    projected = []
    for row in projection:
        source = index[row['source_path']]
        require(all(source[k] == row[k] for k in ('bytes', 'sha256')), 'projected identity drift')
        projected.append({**row, **{k: source[k] for k in ('spdx_lines', 'copyright_line_numbers')}})
    comparison = previous.content.compare(inventories['headers'], inventories['candidate'])
    require(comparison == old['comparison'], 'historical comparison replay drift')
    patches = patch_observations(files['headers'])
    require(len(patches) == 5 and patches == patch_observations(files['candidate']), 'patch set drift')
    return {'kind': 'diagnostic-linux-headers-notice-and-production-review-v1',
            'method': identity(previous.read(Path(__file__))), 'store': checked,
            'historical_inventory_and_comparison_replay_equal': True,
            'archives': {'headers': previous.MIRROR, 'candidate': previous.CANDIDATE},
            'notice_scan': 'entire regular file; literal UTF-8/backslashreplace lines, not license parsing',
            'summaries': {**{k: scope_summary(v) for k, v in entries.items()},
                          'arm64_include_paths': scope_summary(projected)},
            'regular_files': entries, 'arm64_include_paths': projected,
            'arm64_unique_source_files': len({r['source_path'] for r in projected}),
            'patch_blob_observations': patches,
            'candidate_production_scripts': {p: identity(files['candidate'][p])
                for p in ('UPDATE.sh', 'create-dist.sh', 'Makefile', 'tools/install.sh', 'test.sh')},
            'source_acceptance': 'not-assessed', 'license_review_complete': False,
            'upstream_programs_executed': False, 'original_kernel_derivation_verified': False,
            'actual_installation_verified': False, 'cryptography_executed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new deterministic gzip JSON report')
    args = parser.parse_args()
    result = review()
    raw = json.dumps(result, sort_keys=True, indent=2).encode() + b'\n'
    with args.output.open('xb') as stream:
        stream.write(gzip.compress(raw, mtime=0))
    print(json.dumps(result['summaries'], sort_keys=True, indent=2))
