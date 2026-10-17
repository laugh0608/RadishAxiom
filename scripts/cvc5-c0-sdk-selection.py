#!/usr/bin/env python3
"""Resolve the fixed C0 SDK metadata offline; selection never accepts packages."""
import argparse
import hashlib
import importlib.util
import json
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://snapshot.debian.org/archive/debian/20230612T000000Z/'
RECORDS = ROOT / 'docs/records/solver-cvc5-c0-2026-10-17'
SELECTION = RECORDS / 'sdk-selection.json'
OBSERVATIONS = RECORDS / 'metadata-observations.json'
RECORD_LIMIT = 2 * 1024 * 1024
MAX_INDEX_ROWS = 100000
MAX_SELECTED_PACKAGES = 1024
MAX_DEPENDENCY_EDGES = 8192
MAX_SOURCE_FILES = 16384


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    if len(raw) > RECORD_LIMIT:
        raise ValueError('sdk-record-size-budget')
    path.write_bytes(raw)


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate-json-key')
        result[key] = value
    return result


def read_record(path):
    with path.open('rb') as stream:
        raw = stream.read(RECORD_LIMIT + 1)
    if not 0 < len(raw) <= RECORD_LIMIT:
        raise ValueError('sdk-record-size-budget')
    return raw, json.loads(raw.decode('utf-8'), object_pairs_hook=reject_duplicates,
                           parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite-json')))


def load_metadata():
    spec = importlib.util.spec_from_file_location('c0_metadata', ROOT / 'scripts/cvc5-c0-sdk-metadata.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    observations, packages_raw, sources_raw = module.read_verified_metadata()
    return observations, deb822(packages_raw), deb822(sources_raw)


def deb822(raw):
    text = raw.decode('utf-8', errors='strict')
    if not text.strip('\n') or any(ord(char) < 32 and char not in '\n\t' or ord(char) == 127 for char in text):
        raise ValueError('invalid-control-in-deb822')
    rows = []
    for block in text.strip('\n').split('\n\n'):
        row, last, keys = {}, None, set()
        for line in block.splitlines():
            if line.startswith((' ', '\t')):
                if last is None:
                    raise ValueError('orphan-deb822-continuation')
                row[last] += '\n' + line[1:]
            else:
                key, separator, value = line.partition(':')
                if not separator or not re.fullmatch(r'[A-Za-z0-9-]+', key) or key.lower() in keys:
                    raise ValueError('malformed-or-duplicate-deb822-field')
                keys.add(key.lower())
                row[key], last = value.lstrip(' '), key
        rows.append(row)
    return rows


def version_parts(value):
    if not isinstance(value, str) or len(value) > 256 or not re.fullmatch(r'(?:[0-9]+:)?[0-9][A-Za-z0-9.+:~\-]*', value):
        raise ValueError('unsupported-debian-version: ' + value)
    epoch, separator, remainder = value.partition(':')
    has_epoch = bool(separator)
    epoch, rest = (int(epoch), remainder) if separator else (0, value)
    upstream, separator, revision = rest.rpartition('-')
    upstream = upstream if separator else rest
    revision = revision if separator else '0'
    if (not upstream or not re.fullmatch(r'[A-Za-z0-9+.~]+', revision)
            or (':' in upstream and not has_epoch)):
        raise ValueError('unsupported-debian-version: ' + value)
    return epoch, upstream, revision


def revision_compare(left, right):
    def order(char):
        if char == '~':
            return -1
        if not char or char.isdigit():
            return 0
        return ord(char) if char.isalpha() else ord(char) + 256
    li = ri = 0
    while li < len(left) or ri < len(right):
        while (li < len(left) and not left[li].isdigit()) or (ri < len(right) and not right[ri].isdigit()):
            lc, rc = left[li:li + 1], right[ri:ri + 1]
            if order(lc) != order(rc):
                return -1 if order(lc) < order(rc) else 1
            li += bool(lc)
            ri += bool(rc)
        lend, rend = li, ri
        while lend < len(left) and left[lend].isdigit():
            lend += 1
        while rend < len(right) and right[rend].isdigit():
            rend += 1
        ln, rn = left[li:lend].lstrip('0'), right[ri:rend].lstrip('0')
        if (len(ln), ln) != (len(rn), rn):
            return -1 if (len(ln), ln) < (len(rn), rn) else 1
        li, ri = lend, rend
    return 0


def version_compare(left, right):
    le, lu, lr = version_parts(left)
    re_, ru, rr = version_parts(right)
    if le != re_:
        return -1 if le < re_ else 1
    return revision_compare(lu, ru) or revision_compare(lr, rr)


ATOM = re.compile(r'([a-z0-9][a-z0-9+.-]*)(?::(any|native|arm64))?(?:\s*\((<<|<=|=|>=|>>)\s*([^()\s]+)\))?')


def relations(value):
    if not isinstance(value, str) or len(value) > 131072:
        raise ValueError('dependency-field-budget-or-type')
    if not value:
        return []
    groups = []
    if len(value.split(',')) > 2048:
        raise ValueError('dependency-relation-count-budget')
    for group in value.replace('\n', ' ').split(','):
        alternatives = []
        for option in group.split('|'):
            match = ATOM.fullmatch(option.strip())
            if not match:
                raise ValueError('unsupported-dependency-syntax: ' + option)
            name, qualifier, operator, version = match.groups()
            if version:
                version_parts(version)
            alternatives.append({'name': name, 'qualifier': qualifier, 'operator': operator, 'version': version})
        groups.append(alternatives)
    return groups


def satisfies(version, atom):
    if atom['operator'] is None:
        return True
    if version is None:
        return False
    comparison = version_compare(version, atom['version'])
    return {'<<': comparison < 0, '<=': comparison <= 0, '=': comparison == 0,
            '>=': comparison >= 0, '>>': comparison > 0}[atom['operator']]


def safe_pool_path(value):
    if (not value.startswith('pool/main/') or any(p in ('', '.', '..') for p in value.split('/'))
            or urllib.parse.quote(value, safe='/+.-_~') != value):
        raise ValueError('unsafe-or-out-of-main-pool-path: ' + value)
    return value


def eligible(row, atom):
    # This is a single native arm64 SDK, never a cross-architecture solve.
    # :any explicitly requires the package to opt into cross-architecture use.
    return atom['qualifier'] != 'any' or row.get('Multi-Arch') == 'allowed'


def index_maps(package_rows, source_rows):
    if len(package_rows) > MAX_INDEX_ROWS or len(source_rows) > MAX_INDEX_ROWS:
        raise ValueError('metadata-index-row-budget')
    packages, sources, providers = {}, {}, {}
    for row in package_rows:
        if any(not isinstance(row.get(key), str) for key in ('Package', 'Version', 'Architecture', 'Filename', 'Size', 'SHA256')):
            raise ValueError('missing-or-invalid-binary-index-field')
        if row['Architecture'] not in ('arm64', 'all'):
            raise ValueError('unexpected-package-architecture')
        name = row['Package']
        if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*', name):
            raise ValueError('invalid-package-name')
        if row.get('Essential') not in (None, 'yes', 'no'):
            raise ValueError('noncanonical-essential-value')
        if row.get('Multi-Arch') not in (None, 'no', 'same', 'foreign', 'allowed'):
            raise ValueError('unsupported-multi-arch-value')
        if name in packages:
            raise ValueError('multiple-package-candidates-require-explicit-policy: ' + name)
        packages[name] = row
        version_parts(row['Version'])
        for group in relations(row.get('Provides', '')):
            if len(group) != 1 or group[0]['operator'] not in (None, '=') or group[0]['qualifier']:
                raise ValueError('unsupported-provides')
            atom = group[0]
            providers.setdefault(atom['name'], []).append((name, atom['version']))
    for row in source_rows:
        if any(not isinstance(row.get(key), str) for key in ('Package', 'Version', 'Directory', 'Checksums-Sha256')):
            raise ValueError('missing-or-invalid-source-index-field')
        if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*', row['Package']):
            raise ValueError('invalid-source-package-name')
        version_parts(row['Version'])
        key = (row['Package'], row['Version'])
        if key in sources:
            raise ValueError('duplicate-source-candidate')
        sources[key] = row
    return packages, sources, providers


def source_record(src):
    directory = safe_pool_path(src['Directory'])
    files = []
    seen = set()
    for line in src['Checksums-Sha256'].strip().splitlines():
        sha, size, filename = line.split()
        if (filename in seen or '/' in filename or not re.fullmatch('[0-9a-f]{64}', sha)
                or not re.fullmatch(r'[1-9][0-9]{0,11}', size) or int(size) > 1024 * 1024 * 1024):
            raise ValueError('invalid-source-file-metadata')
        seen.add(filename)
        path = safe_pool_path(directory + '/' + filename)
        kind = ('dsc' if filename.endswith('.dsc') else 'orig' if '.orig' in filename
                else 'debian-patch' if '.debian.tar.' in filename or filename.endswith('.diff.gz')
                else 'native-source' if '.tar.' in filename else 'unrecognized')
        if kind == 'unrecognized':
            raise ValueError('unsupported-source-file-kind: ' + filename)
        files.append({'filename': filename, 'kind': kind, 'size': int(size), 'sha256': sha,
                      'url': BASE + path, 'bytes': None, 'raw_digest': None, 'status': 'not-obtained'})
    if not any(item['kind'] == 'dsc' for item in files) or len(files) < 2:
        raise ValueError('incomplete-source-file-set')
    return {'Package': src['Package'], 'Version': src['Version'],
                                   'Directory': directory, 'Binary': src.get('Binary'), 'Format': src.get('Format'), 'files': files,
                                   'signature_authentication': 'not-established', 'license_acceptance': 'not-accepted'}


def resolve_closure(package_rows, source_rows, roots):
    packages, sources, providers = index_maps(package_rows, source_rows)
    selected = {}
    pending = []
    edges = []
    reasons = {}

    def add(name, reason):
        if name not in packages:
            raise ValueError('missing-root-or-essential-package: ' + name)
        reasons.setdefault(name, []).append(reason)
        if name not in selected:
            if len(selected) >= MAX_SELECTED_PACKAGES:
                raise ValueError('selected-package-count-budget')
            selected[name] = packages[name]
            pending.append(name)

    for name in roots:
        add(name, {'kind': 'sdk-role-root'})
    essential = sorted(name for name, row in packages.items() if row.get('Essential') == 'yes')
    for name in essential:
        add(name, {'kind': 'essential-runtime-baseline'})
    cursor = 0
    while cursor < len(pending):
        name = pending[cursor]
        cursor += 1
        row = selected[name]
        for field in ('Pre-Depends', 'Depends'):
            for number, alternatives in enumerate(relations(row.get(field, ''))):
                chosen = None
                for atom in alternatives:
                    candidate = packages.get(atom['name'])
                    if candidate and eligible(candidate, atom) and satisfies(candidate['Version'], atom):
                        chosen = (atom['name'], atom, None, 'first-satisfiable-alternative-direct-package')
                        break
                    provider_options = sorted(providers.get(atom['name'], []), key=lambda item: (item[0] not in selected, item[0]))
                    for provider, provided_version in provider_options:
                        if eligible(packages[provider], atom) and satisfies(provided_version, atom):
                            chosen = (provider, atom, provided_version, 'first-satisfiable-alternative-provider-selected-first-then-name')
                            break
                    if chosen:
                        break
                if chosen is None:
                    raise ValueError('unsatisfied-dependency: ' + name + ' ' + field + ' ' + repr(alternatives))
                target, atom, provided_version, policy = chosen
                edge = {'from': name, 'field': field, 'group_index': number, 'alternatives': alternatives,
                        'selected_alternative': atom, 'to': target, 'target_version': packages[target]['Version'],
                        'via_provides': target != atom['name'], 'provided_version': provided_version,
                        'selection_reason': policy}
                if len(edges) >= MAX_DEPENDENCY_EDGES:
                    raise ValueError('dependency-edge-count-budget')
                edges.append(edge)
                add(target, {'kind': 'dependency', 'from': name, 'field': field, 'group_index': number})
    for name, row in selected.items():
        for field in ('Conflicts', 'Breaks'):
            for group in relations(row.get(field, '')):
                if len(group) != 1:
                    raise ValueError('unsupported-alternative-conflict')
                atom = group[0]
                for other, candidate in selected.items():
                    if other == name:
                        continue  # Debian permits a package conflicting with its own provided name.
                    direct = atom['name'] == other and satisfies(candidate['Version'], atom)
                    virtual = any(provider == other and satisfies(provided_version, atom)
                                  for provider, provided_version in providers.get(atom['name'], []))
                    if direct or virtual:
                        raise ValueError('selected-package-conflict: ' + name + ' ' + field + ' ' + other)
    binaries, source_selection = [], {}
    for name in sorted(selected):
        row = selected[name]
        source = row.get('Source', name)
        match = re.fullmatch(r'([a-z0-9][a-z0-9+.-]*)(?: \(([^() ]+)\))?', source)
        if not match:
            raise ValueError('unsupported-binary-source-field: ' + source)
        source_name, source_version = match.groups()
        source_version = source_version or row['Version']
        version_parts(source_version)
        source_key = (source_name, source_version)
        if source_key not in sources:
            raise ValueError('missing-exact-source-version: ' + repr(source_key))
        if 'Binary' in sources[source_key] and name not in [item.strip() for item in sources[source_key]['Binary'].split(',')]:
            raise ValueError('source-binary-membership-mismatch')
        binary = {key: row[key] for key in ('Package', 'Version', 'Architecture', 'Filename', 'Size', 'SHA256')}
        if not re.fullmatch(r'[1-9][0-9]{0,11}', binary['Size']):
            raise ValueError('invalid-binary-size-or-sha256')
        binary['Size'] = int(binary['Size'])
        if binary['Size'] > 512 * 1024 * 1024 or not re.fullmatch('[0-9a-f]{64}', binary['SHA256']):
            raise ValueError('invalid-binary-size-or-sha256')
        safe_pool_path(binary['Filename'])
        if not binary['Filename'].endswith('.deb'):
            raise ValueError('invalid-binary-filename-extension')
        binary.update(Source=row.get('Source'), source_package=source_name, source_version=source_version,
                      package_url=BASE + binary['Filename'], bytes=None, raw_digest=None,
                      package_status='not-obtained', license_acceptance='not-accepted', reasons=reasons[name])
        for field in ('Depends', 'Pre-Depends', 'Provides', 'Conflicts', 'Breaks', 'Essential', 'Multi-Arch', 'Replaces'):
            binary[field] = row.get(field)
        binaries.append(binary)
        correspondences = [(source_key, 'Source')]
        binary['built_using_sources'] = []
        for field in ('Built-Using', 'Static-Built-Using'):
            binary[field] = row.get(field)
            for group in relations(row.get(field, '')):
                if len(group) != 1 or group[0]['operator'] != '=' or group[0]['qualifier'] is not None:
                    raise ValueError('unsupported-built-using-source-relation')
                atom = group[0]
                correspondences.append(((atom['name'], atom['version']), field))
                binary['built_using_sources'].append({'field': field, 'source_package': atom['name'], 'source_version': atom['version']})
        for corresponding_key, field in correspondences:
            if corresponding_key not in sources:
                raise ValueError('missing-exact-corresponding-source-version: ' + repr(corresponding_key))
            if corresponding_key not in source_selection:
                source_selection[corresponding_key] = source_record(sources[corresponding_key])
                source_selection[corresponding_key]['correspondence_reasons'] = []
            source_selection[corresponding_key]['correspondence_reasons'].append({'binary_package': name, 'field': field})
    return binaries, edges, [source_selection[key] for key in sorted(source_selection)], essential


def generate():
    observations, packages, sources = load_metadata()
    spec = importlib.util.spec_from_file_location('c0_roots', ROOT / 'scripts/generate-cvc5-c0-input-selection.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    groups = [{'id': ident, 'package_names': names} for ident, names, _ in module.SDK_ITEMS]
    roots = list(dict.fromkeys(name for group in groups for name in group['package_names']))
    binaries, edges, source_selection, essential = resolve_closure(packages, sources, roots)
    binary_bytes = sum(row['Size'] for row in binaries)
    source_files = {}
    for source in source_selection:
        for file in source['files']:
            if len(source_files) >= MAX_SOURCE_FILES and file['url'] not in source_files:
                raise ValueError('source-file-count-budget')
            previous = source_files.setdefault(file['url'], (file['size'], file['sha256']))
            if previous != (file['size'], file['sha256']):
                raise ValueError('conflicting-shared-source-file')
    source_bytes = sum(row[0] for row in source_files.values())
    if binary_bytes > 512 * 1024 * 1024 or source_bytes > 1024 * 1024 * 1024:
        raise ValueError('declared-future-acquisition-budget-exceeded')
    selection = {'format': 'radishaxiom-private-cvc5-c0-sdk-selection', 'version': '0.1',
                 'generator': 'scripts/cvc5-c0-sdk-selection.py resolve', 'resolver_identity': {'path': 'scripts/cvc5-c0-sdk-selection.py', 'bytes': Path(__file__).stat().st_size, 'raw_digest': digest(Path(__file__).read_bytes())}, 'root_role_definition': {'path': 'scripts/generate-cvc5-c0-input-selection.py', 'bytes': (ROOT / 'scripts/generate-cvc5-c0-input-selection.py').stat().st_size, 'raw_digest': digest((ROOT / 'scripts/generate-cvc5-c0-input-selection.py').read_bytes())}, 'base_url': BASE,
                 'distribution': 'Debian 12 bookworm', 'architecture': 'arm64-or-all',
                 'selection': 'exact-metadata-only', 'build_ready': False, 'executable': False,
                 'tool_acceptance': 'not-accepted', 'binary_sdk_trust': 'proposed-not-accepted',
                 'metadata_authentication': 'not-established', 'signature_verified': False,
                 'metadata_record': {'path': str(OBSERVATIONS.relative_to(ROOT)), 'bytes': len((json.dumps(observations, ensure_ascii=False, indent=2) + '\n').encode()), 'raw_digest': digest((json.dumps(observations, ensure_ascii=False, indent=2) + '\n').encode())},
                 'root_groups': groups, 'essential_runtime_baseline': essential,
                 'dependency_policy': {'fields': ['Pre-Depends', 'Depends'], 'recommends': False, 'suggests': False,
                     'alternative_selection': 'left-to-right first satisfiable; direct package before providers; providers already selected first then lexicographic name',
                     'versions': 'Debian epoch/upstream/revision comparison; tilde sorts before empty; numeric digit groups ignore leading zeros',
                     'qualifiers': ':any requires Multi-Arch allowed on direct package or provider; foreign:any is conservatively unsupported; :native/:arm64 use the native arm64/all index only; unknown Multi-Arch fails closed',
                     'conflicts_breaks': 'all selected direct and provided names checked with version constraints; self conflicts ignored per Debian package semantics',
                     'source_correspondence': 'exact Source identity/version and exact = Built-Using/Static-Built-Using source references; no source or license bytes accepted',
                     'resolution_scope': 'selected 17 SDK role roots including statically identified pyparsing/m4 plus all Essential: yes packages from this index; package contents and dynamic generator/runtime filesystem behavior unverified'},
                 'packages': binaries, 'dependency_edges': edges, 'source_packages': source_selection,
                 'summary': {'root_groups': len(groups), 'root_packages': len(roots), 'packages': len(binaries), 'dependency_edges': len(edges),
                     'source_packages': len(source_selection), 'unique_source_files': len(source_files), 'binary_declared_bytes': binary_bytes,
                     'source_declared_bytes': source_bytes, 'binary_max_bytes': 512 * 1024 * 1024, 'source_max_bytes': 1024 * 1024 * 1024},
                 'resource_policy': {'record_max_bytes': RECORD_LIMIT, 'index_max_rows_each': MAX_INDEX_ROWS, 'selected_package_max_count': MAX_SELECTED_PACKAGES, 'dependency_edge_max_count': MAX_DEPENDENCY_EDGES, 'source_file_max_count': MAX_SOURCE_FILES, 'relation_max_groups_per_field': 2048, 'relation_max_bytes_per_field': 131072},
                 'tool_path_requirement': 'explicit versioned gcc-12/g++-12/cpp-12 paths and PKG_CONFIG_EXECUTABLE=pkgconf remain to be verified from package contents; unversioned compiler/pkg-config aliases or alternatives not assumed',
                 'unresolved': ['signature trust and historical validity policy', 'package/source raw bytes and licenses',
                     'unpack/install/maintainer scripts and runtime filesystem', 'dynamic generator imports/effective options',
                     'actual SDK file inventory/static link closure/link map', 'local input/tool acceptance']}
    return observations, selection


def same_typed(value, wanted):
    if type(value) is not type(wanted):
        return False
    if isinstance(wanted, dict):
        return value.keys() == wanted.keys() and all(same_typed(value[key], item) for key, item in wanted.items())
    if isinstance(wanted, list):
        return len(value) == len(wanted) and all(same_typed(left, right) for left, right in zip(value, wanted))
    return value == wanted


def verify():
    observations, selection = generate()
    _, observed = read_record(OBSERVATIONS)
    raw, recorded = read_record(SELECTION)
    if not same_typed(observed, observations) or not same_typed(recorded, selection):
        raise ValueError('sdk-record-drift-or-false-acceptance')
    return dict(selection['summary'], record_bytes=len(raw), build_ready=False, executable=False,
                signature_verified=False, check_scope='offline-regeneration-consistency-not-independent-authentication')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('resolve', 'verify'))
    args = parser.parse_args()
    if args.action == 'resolve':
        observations, selection = generate()
        write_json(OBSERVATIONS, observations)
        write_json(SELECTION, selection)
    print(json.dumps(verify(), indent=2))


if __name__ == '__main__':
    main()
