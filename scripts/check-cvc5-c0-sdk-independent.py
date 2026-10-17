#!/usr/bin/env python3
"""Independent metadata audit. Does not import C0 production modules."""
import hashlib
import json
import lzma
from pathlib import Path
import re
from urllib.parse import urlsplit
import argparse

def require(condition, reason):
    if not condition:
        raise ValueError(str(reason))
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / '.tmp/cvc5-c0-sdk-metadata-2026-10-17'
BASE = 'https://snapshot.debian.org/archive/debian/20230612T000000Z/'
TARGETS = ('Release', 'InRelease', 'main/binary-arm64/Packages.xz', 'main/source/Sources.xz')
METADATA_LIMIT = 28 * 1024**2
LINE_LIMIT = 256 * 1024
# Independently transcribed from the reviewed seventeen role groups. Never import
# the producer's root table, parser, dependency resolver, or version comparator.
REVIEWED_ROOT_NAMES = set('''
gcc-12 g++-12 cpp-12 gcc-12-base
binutils binutils-aarch64-linux-gnu binutils-common
libgcc-12-dev libstdc++-12-dev libgcc-s1 libstdc++6
libc6 libc6-dev libc-dev-bin linux-libc-dev libedit-dev libedit2
libncurses-dev libtinfo6 libbsd-dev libbsd0 libmd-dev libmd0
cmake cmake-data make python3 python3-minimal python3.11 python3.11-minimal
libpython3.11-stdlib libpython3.11-minimal python3-pyparsing m4 pkgconf pkgconf-bin libpkgconf3
dash bash coreutils sed grep gawk findutils diffutils patch tar gzip bzip2
xz-utils file libmagic1 libmagic-mgc
'''.split())

def paragraphs(path):
    opener = lzma.open if path.suffix == '.xz' else open
    with opener(path, 'rb') as stream:
        obj, previous = ({}, None)
        total = 0
        while True:
            raw_line = stream.readline(LINE_LIMIT + 1)
            if not raw_line:
                break
            require(len(raw_line) <= LINE_LIMIT, 'deb822-line-budget')
            total += len(raw_line)
            require(total <= 256 * 1024**2, 'decompressed-index-budget')
            line = raw_line.decode('utf-8')
            require('\r' not in line and '\x00' not in line, 'deb822-control-byte')
            line = line.rstrip('\n')
            if not line:
                if obj:
                    yield obj
                obj, previous = ({}, None)
            elif line[0] in ' \t':
                require(previous is not None, 'orphan continuation')
                obj[previous] += '\n' + line[1:]
            else:
                key, sep, val = line.partition(':')
                require(sep and re.fullmatch('[A-Za-z0-9-]+', key) and key not in obj, 'invalid/duplicate field')
                obj[key] = val.lstrip()
                previous = key
        if obj:
            yield obj


def read_json(path, allow_float=False):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate-json-key')
            result[key] = value
        return result

    with path.open('rb') as stream:
        raw = stream.read(2 * 1024**2 + 1)
    require(0 < len(raw) <= 2 * 1024**2, 'json-record-size')
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: require(False, 'nonfinite-json'),
                      parse_float=float if allow_float else lambda _: require(False, 'floating-number'))


def read_retained_metadata():
    fetch = read_json(RAW / 'fetch-observations.json', allow_float=True)
    require(fetch['complete'] is True and type(fetch['total_response_body_bytes']) is int
            and fetch['total_response_body_bytes'] <= METADATA_LIMIT, 'metadata-completeness-or-budget')
    require(tuple(row['relative_path'] for row in fetch['observations']) == TARGETS, 'metadata-target-set-drift')
    data, total = {}, 0
    for row in fetch['observations']:
        require(row['retained_file'] == row['relative_path'].replace('/', '__'), 'metadata-retained-path-drift')
        with (RAW / row['retained_file']).open('rb') as stream:
            raw = stream.read(METADATA_LIMIT - total + 1)
        total += len(raw)
        require(total <= METADATA_LIMIT, 'compressed-metadata-total-budget')
        require(type(row['bytes']) is int and len(raw) == row['bytes']
                and 'sha256:' + hashlib.sha256(raw).hexdigest() == row['raw_digest'], 'raw-metadata-digest-or-size')
        data[row['relative_path']] = raw
    require(total == fetch['total_response_body_bytes'], 'metadata-total-byte-count')
    return fetch, data

def compare_fragment(a, b):

    def weight(s, i):
        if i == len(s):
            return 0
        c = s[i]
        if c == '~':
            return -1
        if c.isdigit():
            return 0
        return ord(c) if c.isalpha() else ord(c) + 256
    i = j = 0
    while i < len(a) or j < len(b):
        while i < len(a) and (not a[i].isdigit()) or (j < len(b) and (not b[j].isdigit())):
            left, right = (weight(a, i), weight(b, j))
            if left != right:
                return (left > right) - (left < right)
            if i < len(a):
                i += 1
            if j < len(b):
                j += 1
        left = re.match('[0-9]*', a[i:])[0]
        right = re.match('[0-9]*', b[j:])[0]
        la, lb = (left.lstrip('0'), right.lstrip('0'))
        if len(la) != len(lb):
            return (len(la) > len(lb)) - (len(la) < len(lb))
        if la != lb:
            return (la > lb) - (la < lb)
        i += len(left)
        j += len(right)
    return 0

def version_compare(a, b):

    def parts(v):
        epoch, sep, rest = v.partition(':')
        epoch, rest = (int(epoch), rest) if sep else (0, v)
        upstream, sep, revision = rest.rpartition('-')
        return (epoch, upstream if sep else rest, revision if sep else '0')
    ea, ua, ra = parts(a)
    eb, ub, rb = parts(b)
    return (ea > eb) - (ea < eb) or compare_fragment(ua, ub) or compare_fragment(ra, rb)

def relation(atom):
    m = re.fullmatch('([a-z0-9][a-z0-9+.-]*)(?::([a-z0-9-]+))?(?:\\s*\\((<<|<=|=|>=|>>)\\s*([^()]+)\\))?', atom.strip())
    require(m, ('unsupported relationship', atom))
    return m.groups()

def satisfies(actual, op, expected):
    if not op:
        return True
    if actual is None:
        return False
    result = version_compare(actual, expected)
    return {'<<': result < 0, '<=': result <= 0, '=': result == 0, '>=': result >= 0, '>>': result > 0}[op]

def matches(atom, selected, excluded=None):
    name, arch, op, version = relation(atom)
    require(arch in (None, 'any', 'native', 'arm64', 'all'), ('foreign arch', atom))
    result = []
    for row in selected:
        if row['Package'] == excluded:
            continue
        if arch == 'any' and row.get('Multi-Arch') != 'allowed':
            continue
        if row['Package'] == name and satisfies(row['Version'], op, version):
            result.append(row['Package'])
        for provide in row.get('Provides', '').split(','):
            if not provide.strip():
                continue
            provided, pa, pop, pv = relation(provide)
            require(pop in (None, '='), ('invalid Provides', provide))
            if provided == name and satisfies(pv, op, version):
                result.append(row['Package'])
    return sorted(set(result))

def inspect(selected_names):
    candidates = list(paragraphs(RAW / 'main__binary-arm64__Packages.xz'))
    selected = [row for row in candidates if row['Package'] in selected_names]
    require(len(selected) == len(selected_names), 'selected package absent or duplicate')
    require(all((row['Architecture'] in ('all', 'arm64') for row in selected)), 'independent-condition-failed')
    require({r['Package'] for r in candidates if r.get('Essential') == 'yes'} <= selected_names, 'Essential absent')
    edges, alternatives, conflicts = ([], [], [])
    for row in selected:
        for kind in ('Depends', 'Pre-Depends'):
            for clause in row.get(kind, '').split(','):
                if not clause.strip():
                    continue
                options = [(a.strip(), matches(a, selected)) for a in clause.split('|')]
                require(any((m for _, m in options)), (row['Package'], kind, clause))
                edges.append((row['Package'], kind, clause.strip(), options))
                if len(options) > 1:
                    alternatives.append(edges[-1])
        for kind in ('Conflicts', 'Breaks'):
            for clause in row.get(kind, '').split(','):
                if not clause.strip():
                    continue
                found = matches(clause, selected, excluded=row['Package'])
                if found:
                    conflicts.append((row['Package'], kind, clause.strip(), found))
    require(not conflicts, conflicts)
    expected_sources = set()
    for row in selected:
        source = row.get('Source', row['Package'])
        m = re.fullmatch('([a-z0-9+.-]+)(?:\\s*\\(([^()]+)\\))?', source)
        require(m, source)
        expected_sources.add((m[1], m[2] or row['Version']))
        for field in ('Built-Using', 'Static-Built-Using'):
            for clause in row.get(field, '').split(','):
                if clause.strip():
                    name, arch, op, version = relation(clause)
                    require(arch is None and op == '=', 'nonexact-built-using')
                    expected_sources.add((name, version))
    selected_source_rows = [r for r in paragraphs(RAW / 'main__source__Sources.xz') if (r['Package'], r['Version']) in expected_sources]
    sources = {(r['Package'], r['Version']): r for r in selected_source_rows}
    require(len(sources) == len(selected_source_rows), 'duplicate-source-stanza')
    require(sources.keys() == expected_sources, ('source-missing', expected_sources - sources.keys()))
    for row in selected:
        m = re.fullmatch('([a-z0-9+.-]+)(?:\\s*\\(([^()]+)\\))?', row.get('Source', row['Package']))
        src = sources[m[1], m[2] or row['Version']]
        if 'Binary' in src:
            require(row['Package'] in {name.strip() for name in src['Binary'].split(',')}, ('binary not advertised by source', row['Package']))
    source_files = {}
    for identity, row in sources.items():
        for line in row['Checksums-Sha256'].splitlines():
            if line.strip():
                digest, length, name = line.split()
                require(re.fullmatch('[0-9a-f]{64}', digest) and int(length) > 0, 'independent-condition-failed')
                key = row['Directory'] + '/' + name
                require(key not in source_files or source_files[key] == (digest, int(length)), 'independent-condition-failed')
                source_files[key] = (digest, int(length))
    result = {
        'package_count': len(selected),
        'essential_count': sum(r.get('Essential') == 'yes' for r in selected),
        'dependency_clause_count': len(edges),
        'alternative_clause_count': len(alternatives),
        'alternative_clauses': alternatives,
        'source_family_versions': len(sources),
        'source_archive_file_count': len(source_files),
        'declared_deb_bytes': sum(int(r['Size']) for r in selected),
        'declared_source_bytes': sum(size for _, size in source_files.values()),
        'conflicts_or_breaks': conflicts,
    }
    return selected, sources, result

def derive_independently():
    rows = list(paragraphs(RAW / 'main__binary-arm64__Packages.xz'))
    by_name = {r['Package']: r for r in rows}
    by_capability = capability_candidates(rows)
    require(len(rows) == len(by_name), 'snapshot has multiple versions requiring policy')
    names = REVIEWED_ROOT_NAMES | {r['Package'] for r in rows if r.get('Essential') == 'yes'}
    require(names <= by_name.keys(), 'independent-condition-failed')
    while True:
        added = set()
        for name in sorted(names):
            for kind in ('Depends', 'Pre-Depends'):
                for clause in by_name[name].get(kind, '').split(','):
                    if not clause.strip():
                        continue
                    target = None
                    for atom in clause.split('|'):
                        provided_by = matches(atom, by_capability.get(relation(atom)[0], []))
                        direct = relation(atom)[0]
                        if direct in provided_by:
                            target = direct
                        elif provided_by:
                            target = min(provided_by, key=lambda n: (n not in names, n))
                        if target:
                            break
                    require(target, (name, kind, clause))
                    added.add(target)
        added -= names
        if not added:
            break
        names |= added
    _, _, result = inspect(names)
    return names, result


def capability_candidates(rows):
    result = {}
    for row in rows:
        names = {row['Package']}
        for atom in row.get('Provides', '').split(','):
            if atom.strip():
                names.add(relation(atom)[0])
        for name in names:
            result.setdefault(name, []).append(row)
    return result


def check_edges(selected, edges):
    available = list(paragraphs(RAW / 'main__binary-arm64__Packages.xz'))
    by_capability = capability_candidates(available)
    indexed = {row['Package']: row for row in selected}
    by_clause = {}
    for edge in edges:
        key = (edge['from'], edge['field'], edge['group_index'])
        require(type(edge['group_index']) is int and key not in by_clause, 'duplicate-or-invalid-edge')
        by_clause[key] = edge
    seen = set()
    for row in selected:
        for field in ('Pre-Depends', 'Depends'):
            clauses = row.get(field, '').split(',') if row.get(field) else []
            for number, clause in enumerate(clauses):
                key = (row['Package'], field, number)
                require(key in by_clause, ('missing-edge', key))
                edge = by_clause[key]
                alternatives = [relation(atom) for atom in clause.split('|')]
                normalized = [dict(name=name, qualifier=arch, operator=op, version=version)
                              for name, arch, op, version in alternatives]
                require(edge['alternatives'] == normalized, ('edge-alternatives-drift', key))
                require(edge['selected_alternative'] in normalized, ('edge-selected-option-drift', key))
                chosen = normalized.index(edge['selected_alternative'])
                require(not any(matches(atom, by_capability.get(relation(atom)[0], [])) for atom in clause.split('|')[:chosen]), ('earlier-alternative-available', key))
                atom = clause.split('|')[chosen]
                require(edge['to'] in matches(atom, selected), ('edge-target-unsatisfied', key))
                target = indexed[edge['to']]
                require(edge['target_version'] == target['Version'], ('edge-target-version', key))
                require(type(edge['via_provides']) is bool, 'via-provides-type')
                require(edge['via_provides'] == (target['Package'] != alternatives[chosen][0]), ('edge-provider-flag', key))
                if edge['via_provides']:
                    versions = [relation(value)[3] for value in target.get('Provides', '').split(',')
                                if value.strip() and relation(value)[0] == alternatives[chosen][0]]
                    require(edge['provided_version'] in versions, ('provider-version-drift', key))
                else:
                    require(edge['provided_version'] is None, ('unexpected-provider-version', key))
                seen.add(key)
    require(seen == by_clause.keys(), 'unexpected-extra-edge')

def audit(record=None):
    base = BASE
    # Establish raw compressed byte bounds and identities before parsing indexes.
    fetch, retained_bytes = read_retained_metadata()
    record = record or ROOT / 'docs/records/solver-cvc5-c0-2026-10-17/sdk-selection.json'
    chosen = read_json(record)
    require(chosen['base_url'] == BASE and chosen['build_ready'] is False and chosen['executable'] is False,
            'scope-or-acceptance-drift')
    require(chosen['tool_acceptance'] == 'not-accepted' and chosen['signature_verified'] is False,
            'false-acceptance')
    require(chosen['binary_sdk_trust'] == 'proposed-not-accepted'
            and chosen['metadata_authentication'] == 'not-established', 'sdk-trust-promotion')
    require(len(chosen['packages']) == len({row['Package'] for row in chosen['packages']}), 'duplicate-selected-package')
    selected, sources, result = inspect({row['Package'] for row in chosen['packages']})
    independently_derived, _ = derive_independently()
    require(independently_derived == {row['Package'] for row in selected}, 'independent-selected-set-differs')
    check_edges(selected, chosen['dependency_edges'])
    indexed = {r['Package']: r for r in selected}
    for row in chosen['packages']:
        original = indexed[row['Package']]
        for key in ('Package', 'Version', 'Architecture', 'Filename', 'SHA256', 'Source', 'Depends', 'Pre-Depends', 'Provides', 'Conflicts', 'Breaks', 'Essential', 'Multi-Arch', 'Replaces', 'Built-Using', 'Static-Built-Using'):
            require(row.get(key) == original.get(key), (row['Package'], key))
        require(type(row['Size']) is int and row['Size'] == int(original['Size']), 'binary-size-type-or-value')
        require(row['raw_digest'] is None and row['bytes'] is None, 'independent-condition-failed')
        require(row['package_url'] == base + original['Filename'], 'independent-condition-failed')
        identity = re.fullmatch(r'([a-z0-9+.-]+)(?:\s*\(([^()]+)\))?', original.get('Source', original['Package']))
        require((row['source_package'], row['source_version']) == (identity[1], identity[2] or original['Version']),
                ('derived-source-identity-drift', row['Package']))
        built_using = []
        for field in ('Built-Using', 'Static-Built-Using'):
            for atom in original.get(field, '').split(','):
                if atom.strip():
                    name, arch, op, version = relation(atom)
                    require(arch is None and op == '=', 'nonexact-built-using')
                    built_using.append(dict(field=field, source_package=name, source_version=version))
        require(row['built_using_sources'] == built_using, 'built-using-record-drift')
        require(row['package_status'] == 'not-obtained' and row['license_acceptance'] == 'not-accepted',
                'package-false-acceptance')
    root_names = {name for group in chosen['root_groups'] for name in group['package_names']}
    require(len(chosen['root_groups']) == 17, 'root-role-count')
    require(root_names == REVIEWED_ROOT_NAMES, 'reviewed-root-set-drift')
    require(root_names <= indexed.keys(), 'required-root-missing')
    require(chosen['essential_runtime_baseline'] == sorted((r['Package'] for r in selected if r.get('Essential') == 'yes')), 'independent-condition-failed')
    source_keys = {(row['Package'], row['Version']) for row in chosen['source_packages']}
    require(source_keys == sources.keys() and len(source_keys) == len(chosen['source_packages']), 'source-record-set-drift')
    for row in chosen['source_packages']:
        original = sources[row['Package'], row['Version']]
        require(row['Directory'] == original['Directory'] and row['Binary'] == original.get('Binary')
                and row['Format'] == original.get('Format'), 'source-field-drift')
        require(row['signature_authentication'] == 'not-established' and row['license_acceptance'] == 'not-accepted',
                'source-false-acceptance')
        expected = {}
        for line in original['Checksums-Sha256'].splitlines():
            if line.strip():
                sha, size, filename = line.split()
                expected[filename] = (sha, int(size), base + original['Directory'] + '/' + filename)
        actual = {r['filename']: (r['sha256'], r['size'], r['url']) for r in row['files']}
        require(len(actual) == len(row['files']), 'duplicate-source-file')
        require(actual == expected, (row['Package'], 'source files drift'))
        require(all((r['raw_digest'] is None and r['bytes'] is None for r in row['files'])), 'independent-condition-failed')
        require(all(r['status'] == 'not-obtained' for r in row['files']), 'source-file-false-acquisition')
    for key, own in [('packages', 'package_count'), ('dependency_edges', 'dependency_clause_count'), ('source_packages', 'source_family_versions'), ('unique_source_files', 'source_archive_file_count'), ('binary_declared_bytes', 'declared_deb_bytes'), ('source_declared_bytes', 'declared_source_bytes')]:
        require(chosen['summary'][key] == result[own], key)
    require(result['declared_deb_bytes'] <= 512 * 1024 ** 2, 'independent-condition-failed')
    require(result['declared_source_bytes'] <= 1024 ** 3, 'independent-condition-failed')
    require(len(chosen['source_packages']) == len(sources), 'source-record-set-incomplete')
    release_stanzas = list(paragraphs(RAW / 'Release'))
    require(len(release_stanzas) == 1, 'release-stanza-count')
    release = release_stanzas[0]
    released_hashes = {}
    for line in release['SHA256'].splitlines():
        if line.strip():
            sha, size, path = line.split()
            released_hashes[path] = (sha, int(size))
    total, files, redirect_count = (0, {}, 0)
    metadata_inputs = []
    for row in fetch['observations']:
        require(row['retained_file'] == row['relative_path'].replace('/', '__'), 'metadata-retained-path-drift')
        require(row['status'] == 'obtained', 'metadata-not-obtained')
        raw = retained_bytes[row['relative_path']]
        require(len(raw) == row['bytes'] and 'sha256:' + hashlib.sha256(raw).hexdigest() == row['raw_digest'], 'independent-condition-failed')
        require(row['http_status'] == 200, 'independent-condition-failed')
        require(row['requested_url'] == base + 'dists/bookworm/' + row['relative_path'], 'independent-condition-failed')
        current = row['requested_url']
        require(len(row['redirects']) <= 5, 'independent-condition-failed')
        for redirect in row['redirects']:
            require(redirect['from_url'] == current, 'independent-condition-failed')
            current = redirect['to_url']
            u = urlsplit(current)
            require(u.scheme == 'https' and u.netloc == 'snapshot.debian.org' and (not u.query) and (not u.fragment), 'independent-condition-failed')
            content = re.fullmatch('/file/([0-9a-f]{40})/([^/]+)', u.path)
            archival = re.fullmatch('/archive/debian/([0-9]{8}T[0-9]{6}Z)/dists/bookworm/' + re.escape(row['relative_path']), u.path)
            require(content or (archival and archival[1] <= '20230612T000000Z'), 'independent-condition-failed')
            if content:
                require(content[2] == row['relative_path'].split('/')[-1] or (row['relative_path'] in released_hashes and content[2] == released_hashes[row['relative_path']][0]), 'file basename neither exact original nor Release SHA256')
                require(hashlib.sha1(raw).hexdigest() == content[1], 'file locator sha1 differs')
            redirect_count += 1
        require(current == row['final_url'], 'independent-condition-failed')
        headers = {key.lower(): value for key, value in row['response_headers'].items()}
        if 'content-length' in headers:
            require(int(headers['content-length']) == len(raw), 'http-content-length')
        require(headers.get('content-encoding', 'identity') == 'identity', 'http-content-encoding')
        files[row['relative_path']] = raw
        metadata_inputs.append(dict(path=str((RAW / row['retained_file']).relative_to(ROOT)),
                                    bytes=len(raw), raw_digest='sha256:' + hashlib.sha256(raw).hexdigest()))
        total += len(raw)
    require(total == fetch['total_response_body_bytes'], 'independent-condition-failed')
    require(release['Codename'] == 'bookworm' and release['Origin'] == 'Debian', 'independent-condition-failed')
    require('arm64' in release['Architectures'].split() and 'main' in release['Components'].split(), 'independent-condition-failed')
    for name in ('main/binary-arm64/Packages.xz', 'main/source/Sources.xz'):
        raw = files[name]
        require(released_hashes[name] == (hashlib.sha256(raw).hexdigest(), len(raw)), 'independent-condition-failed')
    require(files['InRelease'].startswith(b'-----BEGIN PGP SIGNED MESSAGE-----\n'), 'inrelease-envelope')
    require(files['InRelease'].endswith(b'-----END PGP SIGNATURE-----\n'), 'inrelease-envelope')
    text = files['InRelease'].split(b'\n\n', 1)[1].split(b'-----BEGIN PGP SIGNATURE-----', 1)[0]
    clear = b'\n'.join((line[2:] if line.startswith(b'- ') else line for line in text.split(b'\n')))
    require(clear == files['Release'], 'cleartext mismatch')
    result.pop('alternative_clauses')
    checker_raw = Path(__file__).read_bytes()
    record_raw = record.read_bytes()
    result.update(format='radishaxiom-private-c0-independent-sdk-check', version='0.1',
                  checker=dict(path=str(Path(__file__).relative_to(ROOT)), raw_digest='sha256:' + hashlib.sha256(checker_raw).hexdigest()),
                  selection_input=dict(path=str(record.relative_to(ROOT)), bytes=len(record_raw), raw_digest='sha256:' + hashlib.sha256(record_raw).hexdigest()),
                  metadata_inputs=metadata_inputs, independently_derived_set_matches=True,
                  metadata_body_bytes=total, redirects_checked=redirect_count, release_date=release.get('Date'),
                  signature_verified=False, build_ready=False, executable=False,
                  independent_scope='selected dependency clauses/edges, root+Essential set, architecture/Provides/alternatives, version comparisons, Conflicts/Breaks, Source and exact Built-Using associations, source/binary declared byte sums, raw metadata/hash/Release links, HTTP locator chain',
                  unverified=['signature authentication and historical validity policy', 'binary/source package raw bytes and licenses',
                              'package file contents, maintainer scripts, ELF/dlopen/runtime filesystem',
                              'dynamic generator imports/effective options, SDK static link closure/map', 'compiler/SDK/tool acceptance'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.record)
    raw = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(raw)
    print(raw, end='')


if __name__ == '__main__':
    main()
