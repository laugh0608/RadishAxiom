#!/usr/bin/env python3
"""Model a verifier layout and compare LLVM symbol observations; no payload execution."""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('content', HERE / 'inspect-musl-verifier-content.py')
content = importlib.util.module_from_spec(spec)
spec.loader.exec_module(content)
require, identity = content.require, content.identity


def parse_observation(text):
    """Accept the observed LLVM 21 text profile, rejecting unparsed version/symbol rows."""
    require('<stdin>:\tfile format elf64-littleaarch64' in text, 'wrong ELF format')
    require(text.count('DYNAMIC SYMBOL TABLE:\n') == 1, 'missing/duplicate symbol table')
    header, table = text.split('DYNAMIC SYMBOL TABLE:\n')
    definitions, references, state, provider = {}, {}, None, None
    for line in header.splitlines():
        if line in {'Version definitions:', 'Version References:'}:
            state = line
            continue
        if not line or state is None:
            continue
        if state == 'Version definitions:':
            if re.fullmatch(r'\t\S+', line):
                require(bool(definitions), 'version parent without definition')
                continue
            match = re.fullmatch(r'([0-9]+) (0x[0-9a-f]+) (0x[0-9a-f]+) (\S+)', line)
            require(match is not None and match[4] not in definitions, 'bad/duplicate version definition')
            definitions[match[4]] = match[3]
        else:
            match = re.fullmatch(r'  required from (\S+):', line)
            if match:
                provider = match[1]
                require(provider not in references, 'duplicate version provider')
                references[provider] = {}
                continue
            match = re.fullmatch(r'    (0x[0-9a-f]+) (0x[0-9a-f]+) ([0-9]+) (\S+)', line)
            require(match is not None and provider is not None, 'bad version reference')
            require(match[4] not in references[provider], 'duplicate version reference')
            references[provider][match[4]] = {'hash': match[1], 'flags': match[2]}
    symbols = []
    for line in table.splitlines():
        if not line:
            continue
        match = re.fullmatch(r'[0-9a-f]{16} (.{7}) (\S+)\t[0-9a-f]{16} +(.+)', line)
        require(match is not None, 'unparsed symbol row')
        flags, section, tail = match.groups()
        parts = tail.split()
        require(len(parts) in {1, 2}, 'unparsed symbol visibility/name')
        version = parts[0].strip('()') if len(parts) == 2 else None
        require(flags[0] in {' ', 'g', 'l'} and flags[1] in {' ', 'w'}, 'unknown symbol binding')
        symbols.append({'name': parts[-1], 'version': version,
                        'default_version': len(parts) == 1 or not parts[0].startswith('('),
                        'undefined': section == '*UND*', 'weak': flags[1] == 'w',
                        'exported': section != '*UND*' and (flags[0] == 'g' or flags[1] == 'w')})
    require(bool(symbols), 'empty symbol table')
    return {'definitions': definitions, 'references': references, 'symbols': symbols}


def compare_versions(observations, elf_rows):
    """Check definitions and candidate exports, not exact symbol binding or relocations."""
    checks, unresolved, unversioned, symbol_candidates = [], [], [], []
    for path, observation in sorted(observations.items()):
        providers = {}
        for library, versions in observation['references'].items():
            candidate = elf_rows[path]['library_path_candidates'].get(library)
            require(candidate is not None and candidate['status'] == 'found', 'version provider not a candidate')
            target = candidate['path']
            require(target in observations, 'version provider outside selected files')
            for version, detail in versions.items():
                available = observations[target]['definitions'].get(version) == detail['hash']
                checks.append({'from': path, 'library': library, 'provider': target,
                               'version': version, **detail, 'definition_matches': available})
                providers.setdefault(version, []).append(target)
        for symbol in observation['symbols']:
            if not symbol['undefined']:
                continue
            if symbol['version'] is None:
                candidates = [r['path'] for r in elf_rows[path]['library_path_candidates'].values()
                              if r['status'] == 'found']
                require(all(p in observations for p in candidates), 'dependency outside observations')
                matches = [p for p in candidates if any(row['exported'] and row['default_version'] and
                    row['name'] == symbol['name'] for row in observations[p]['symbols'])]
                unversioned.append({'from': path, 'matching_direct_dependency_exports': matches, **symbol})
                continue
            candidates = providers.get(symbol['version'], [])
            require(bool(candidates), 'missing symbol version provider')
            matches = [target for target in candidates if any(
                row['exported'] and row['name'] == symbol['name'] and row['version'] == symbol['version']
                for row in observations[target]['symbols'])]
            row = {'from': path, 'candidate_providers': candidates, 'matching_exports': matches, **symbol}
            symbol_candidates.append(row)
            if not matches:
                unresolved.append(row)
    return {'version_requirements': checks, 'unmatched_versioned_symbols': unresolved,
            'versioned_undefined_count': sum(s['undefined'] and s['version'] is not None
                for row in observations.values() for s in row['symbols']),
            'unversioned_undefined_symbol_candidates': unversioned,
            'versioned_symbol_candidates': symbol_candidates,
            'exact_symbol_provider_binding_assessed': False,
            'loader_resolution_assessed': False, 'relocations_assessed': False}


def model_layout(inventory):
    index = {}
    for package in inventory['packages']:
        for row in package['payload']['members']:
            index.setdefault(row['path'], {**row, 'packages': [package['package']]})
    selected = {row['path'] for row in inventory['root_static_candidates']['files']}
    rows = {path: {**index[path], 'origin': 'package'} for path in selected}
    for row in inventory['links']:
        if row['resolved']['status'] == 'found' and row['resolved']['path'] in selected:
            rows[row['path']] = {**index[row['path']], 'origin': 'package'}
    licenses = []
    owners = {p for row in inventory['root_static_candidates']['files'] for p in row['packages']}
    for package in inventory['packages']:
        if package['package'] in owners:
            copyright = package['copyright']
            path = copyright['path']
            rows[path] = {**index[path], 'origin': 'package'}
            licenses.append({'package': package['package'], 'copyright': path,
                             'common_license_references': copyright['common_license_references']})
    for path in list(rows):
        for parent in Path(path).parents:
            name = str(parent)
            require(name in index and index[name]['type'] == 'directory', 'missing package parent')
            rows.setdefault(name, {**index[name], 'origin': 'package'})
    require('lib' not in rows, 'unexpected root lib')
    rows['lib'] = {'path': 'lib', 'type': 'symlink', 'target': 'usr/lib', 'destination': 'usr/lib',
                   'mode': 0o777, 'uid': 0, 'gid': 0, 'packages': [], 'origin': 'proposed-generated'}
    resolutions = []
    for row in inventory['elf_files']:
        if row['path'] not in selected:
            continue
        for name in row['needed']:
            target = 'usr/lib/aarch64-linux-gnu/' + name
            resolutions.append({'from': row['path'], 'kind': 'needed-candidate',
                                'requested': target, **content.resolve(rows, target)})
        if row['interpreter']:
            resolutions.append({'from': row['path'], 'kind': 'interpreter',
                                'requested': row['interpreter'], **content.resolve(rows, row['interpreter'])})
    require(all(row['status'] == 'found' and row['type'] == 'file' for row in resolutions),
            'unresolved modeled layout')
    return {'kind': 'static-layout-proposal-not-assembled', 'entries': [rows[p] for p in sorted(rows)],
            'resolutions': resolutions, 'licenses': licenses,
            'common_license_files_present': False, 'configuration_and_mounts': 'see companion Markdown',
            'runtime_complete': False}


def license_candidate(directory, sources):
    packages = content.load('package_candidates', 'inspect-musl-verifier-packages.py')
    packages.inputs.inspect(sources)
    rows = [row for row in packages.chain.index_stanzas(directory / 'packages-attempt-2.xz',
            packages.inputs.PACKAGES) if row.get('package') == 'base-files']
    require(len(rows) == 1 and rows[0]['architecture'] == 'arm64', 'ambiguous base-files candidate')
    row = rows[0]
    found = packages.bind_sources({'base-files': row},
        packages.chain.index_stanzas(sources, packages.inputs.SOURCES))
    return {'package_row': row, 'source_row': found[packages.source_identity(row)],
            'url': 'https://deb.debian.org/debian/' + row['filename'],
            'bytes': int(row['size']), 'sha256': row['sha256'],
            'packages_index': packages.inputs.PACKAGES, 'sources_index': packages.inputs.SOURCES,
            'package_acquired': False, 'license_content_inspected': False,
            'methods': {str(p.relative_to(HERE.parents[2])): identity(p.read_bytes()) for p in
                        (HERE / 'inspect-musl-verifier-packages.py', HERE / 'inspect-musl-verifier-sources.py')}}


def inspect(directory, objdump, sources):
    inventory = content.inspect(directory)
    selected = {row['path'] for row in inventory['root_static_candidates']['files']}
    require(len(selected) == 14, 'root candidate count drift')
    needed_bytes = selected | {'usr/share/man/man1/gpg.1.gz', 'usr/share/man/man1/gpgconf.1.gz'}
    payloads = {}
    manifest = json.loads((HERE / 'musl-verifier-packages-2026-09-12.json').read_text())
    for package in manifest['packages']:
        name = package['package']
        attempt = 2 if name == 'gcc-14-base' else 1
        raw = content.reader.fixed(directory / f"{name.replace('.', '_')}-attempt-{attempt}.deb",
                                   package['bytes'], package['sha256'])
        _, files = content.read_tar(content.reader.ar_members(raw)['data.tar.xz'], 64 * 1024**2)
        payloads.update({path: data for path, data in files.items() if path in needed_bytes})
    require(set(payloads) == needed_bytes, 'missing selected bytes')
    tool = objdump.resolve(strict=True)
    version = subprocess.run([str(tool), '--version'], capture_output=True, timeout=20, check=True,
                             env={'LC_ALL': 'C', 'PATH': '/usr/bin:/bin'})
    require(not version.stderr and version.stdout.startswith(b'Apple LLVM version 21.0.0\n'),
            'unreviewed static tool version')
    observations, commands = {}, []
    for path in sorted(selected):
        argv = [str(tool), '--no-debuginfod', '--private-headers', '--dynamic-syms', '-']
        result = subprocess.run(argv, input=payloads[path], capture_output=True, timeout=20,
                                env={'LC_ALL': 'C', 'PATH': '/usr/bin:/bin'})
        require(result.returncode == 0 and not result.stderr and len(result.stdout) < 2 * 1024**2,
                'static tool failure or output outside profile: ' + path)
        observations[path] = parse_observation(result.stdout.decode('ascii'))
        commands.append({'input_path': path, 'input': identity(payloads[path]), 'argv': argv,
                         'exit_code': result.returncode, 'stdout': result.stdout.decode('ascii'),
                         'stderr': result.stderr.decode('ascii')})
    manuals = []
    for path in sorted(needed_bytes - selected):
        data = gzip.decompress(payloads[path])
        require(len(data) < 1024**2, 'manual size limit')
        manuals.append({'path': path, 'input': identity(payloads[path]), 'uncompressed': identity(data)})
    return {'kind': 'diagnostic-verifier-static-layout', 'acceptance': 'not-assessed',
            'candidate_manifest': inventory['candidate_manifest'], 'layout': model_layout(inventory),
            'pending_common_license_source_candidate': license_candidate(directory, sources),
            'symbol_comparison': compare_versions(observations,
                {row['path']: row for row in inventory['elf_files']}),
            'observations': observations, 'commands': commands, 'manuals': manuals,
            'tool': {'path': str(tool), **identity(tool.read_bytes()), 'version': version.stdout.decode()},
            'methods': {**inventory['methods'], str(Path(__file__).relative_to(HERE.parents[2])):
                        identity(Path(__file__).read_bytes())},
            'rootfs_assembled': False, 'payload_programs_executed': False,
            'signature_reverified': False, 'runtime_closure_assessed': False}


def summarize(result):
    raw = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode()
    comparison = result['symbol_comparison']
    return {key: value for key, value in result.items()
            if key not in {'commands', 'observations', 'symbol_comparison'}} | {
        'symbol_comparison': {k: v for k, v in comparison.items() if k != 'versioned_symbol_candidates'},
        'inventory_json': identity(raw), 'inventory_gzip': identity(gzip.compress(raw, mtime=0)),
        'elf_count': len(result['observations']),
        'version_requirement_count': len(comparison['version_requirements']),
        'unmatched_version_definition_count': sum(not r['definition_matches']
                                                 for r in comparison['version_requirements']),
        'unmatched_versioned_symbol_count': len(comparison['unmatched_versioned_symbols'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--objdump', type=Path, required=True, help='reviewed installed LLVM 21 binary')
    parser.add_argument('--summary', action='store_true')
    parser.add_argument('--sources', type=Path, required=True, help='retained fixed Sources.xz')
    args = parser.parse_args()
    result = inspect(args.directory, args.objdump, args.sources)
    print(json.dumps(summarize(result) if args.summary else result, sort_keys=True, indent=2))
