#!/usr/bin/env python3
"""Inspect explicit gpg package dependencies in one snapshot, without installing."""
import argparse
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('verifier_sources',
                                             HERE / 'inspect-musl-verifier-sources.py')
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)
chain = inputs.chain
NAME = r'[a-z0-9][a-z0-9+.-]+'
VERSION = r'(?:[0-9]+:)?[0-9][A-Za-z0-9.+~:-]*'


def version_parts(value):
    if not re.fullmatch(VERSION, value) or len(value) > 256:
        raise ValueError('unsupported version syntax')
    epoch, sep, rest = value.partition(':')
    epoch, rest = (int(epoch), rest) if sep else (0, value)
    upstream, dash, revision = rest.rpartition('-')
    return epoch, upstream if dash else rest, revision if dash else '0'


def character_order(char):
    if char == '~':
        return -1
    if not char or char.isdigit():
        return 0
    return ord(char) if char.isalpha() else ord(char) + 256


def compare_part(left, right):
    while left or right:
        while (left and not left[0].isdigit()) or (right and not right[0].isdigit()):
            a, b = left[:1], right[:1]
            difference = character_order(a) - character_order(b)
            if difference:
                return difference
            left, right = left[1:] if a else left, right[1:] if b else right
        a = re.match(r'[0-9]*', left)[0]
        b = re.match(r'[0-9]*', right)[0]
        number_a, number_b = int(a or '0'), int(b or '0')
        if number_a != number_b:
            return number_a - number_b
        left, right = left[len(a):], right[len(b):]
    return 0


def compare_versions(left, right):
    a, b = version_parts(left), version_parts(right)
    return a[0] - b[0] or compare_part(a[1], b[1]) or compare_part(a[2], b[2])


def dependencies(value):
    if not value:
        return []
    result = []
    for term in value.split(','):
        match = re.fullmatch(rf'\s*({NAME})(?:\s+\((=|>=)\s+({VERSION})\))?\s*', term)
        if not match:
            raise ValueError('unsupported dependency syntax: ' + term)
        result.append({'package': match[1], 'operator': match[2], 'version': match[3]})
    return result


def closure(rows):
    by_name = {}
    for row in rows:
        by_name.setdefault(row['package'], []).append(row)
    selected, edges, pending = {}, [], ['gpg']
    while pending:
        name = pending.pop(0)
        if name in selected:
            continue
        candidates = by_name.get(name, [])
        if len(candidates) != 1:
            raise ValueError('missing or ambiguous package: ' + name)
        row = candidates[0]
        if row.get('architecture') not in {'arm64', 'all'} or len(selected) >= 64:
            raise ValueError('unsupported architecture or package count')
        version_parts(row['version'])
        selected[name] = row
        for field in ('depends', 'pre-depends'):
            for dependency in dependencies(row.get(field, '')):
                edges.append({'from': name, 'field': field, **dependency})
                pending.append(dependency['package'])
    for edge in edges:
        actual = selected[edge['package']]['version']
        if edge['operator']:
            comparison = compare_versions(actual, edge['version'])
            if (edge['operator'] == '=' and comparison != 0 or
                    edge['operator'] == '>=' and comparison < 0):
                raise ValueError('unsatisfied dependency: ' + str(edge))
        edge.update(selected_version=actual, constraint_satisfied=True)
    return selected, edges


def source_identity(row):
    match = re.fullmatch(rf'({NAME})(?: \(({VERSION})\))?', row.get('source', row['package']))
    if not match:
        raise ValueError('unsupported source identity')
    return match[1], match[2] or row['version']


def bind_sources(selected, source_rows):
    required = {source_identity(row) for row in selected.values()}
    found = {}
    for row in source_rows:
        key = row['package'], row['version']
        if key in required:
            if key in found:
                raise ValueError('duplicate selected source identity')
            found[key] = row
    if set(found) != required:
        raise ValueError('missing selected source identity')
    for name, row in selected.items():
        source = found[source_identity(row)]
        if name not in [part.strip() for part in source['binary'].split(',')]:
            raise ValueError('source does not declare binary: ' + name)
        filename = row['filename']
        if (not re.fullmatch(r'pool/main/[a-z0-9+._~/-]+', filename) or
                any(part in {'', '.', '..'} for part in filename.split('/')) or
                str(Path(filename).parent) != source['directory'] or
                not filename.endswith('_' + row['architecture'] + '.deb') or
                not re.fullmatch(r'[0-9a-f]{64}', row['sha256']) or
                not row['size'].isdigit() or not 0 < int(row['size']) <= 4 * 1024**2):
            raise ValueError('invalid package artifact identity: ' + name)
    return found


def inspect(packages, sources):
    # Also binds both index identities to the retained InRelease bytes.
    inputs.inspect(sources)
    selected, edges = closure(chain.index_stanzas(packages, inputs.PACKAGES))
    found = bind_sources(selected, chain.index_stanzas(sources, inputs.SOURCES))
    artifacts = []
    for name, row in sorted(selected.items()):
        source_name, source_version = source_identity(row)
        artifacts.append({
            'package': name, 'version': row['version'], 'architecture': row['architecture'],
            'source_package': source_name, 'source_version': source_version,
            'filename': row['filename'], 'url': 'https://deb.debian.org/debian/' + row['filename'],
            'bytes': int(row['size']), 'sha256': row['sha256'],
            'declared_relationships': {key: row[key] for key in
                ('depends', 'pre-depends', 'recommends', 'suggests', 'conflicts',
                 'breaks', 'replaces', 'provides', 'essential') if key in row},
        })
    return {
        'kind': 'diagnostic-verifier-package-candidates', 'acceptance': 'not-assessed',
        'signature_reverified': False, 'package_bytes_acquired': False,
        'runtime_closure_assessed': False, 'installability_assessed': False,
        'inrelease': inputs.RELEASE, 'packages_index': inputs.PACKAGES,
        'sources_index': inputs.SOURCES,
        'methods': {str(path.relative_to(inputs.ROOT)): chain.sha256(path.read_bytes())
                    for path in (Path(__file__), HERE / 'inspect-musl-verifier-sources.py',
                                 inputs.METHOD)},
        'root': 'gpg', 'explicit_dependency_constraints_satisfied': True,
        'dependency_edges': edges, 'package_count': len(artifacts),
        'total_package_bytes': sum(row['bytes'] for row in artifacts), 'packages': artifacts,
        'source_rows': [{key: row[key] for key in
                         ('package', 'version', 'directory', 'checksums-sha256')}
                        for _, row in sorted(found.items())],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packages', type=Path)
    parser.add_argument('sources', type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.packages, args.sources), sort_keys=True, indent=2))
