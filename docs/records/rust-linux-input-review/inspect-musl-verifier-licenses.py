#!/usr/bin/env python3
"""Inspect the fixed base-files archive in memory; never install or execute it."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('content', HERE / 'inspect-musl-verifier-content.py')
content = importlib.util.module_from_spec(spec)
spec.loader.exec_module(content)
require, identity = content.require, content.identity
EXPECTED = {'bytes': 73276, 'sha256':
            '5f5a571ec846d7db05d9f825f0388a37bc033267b33cbf85b4eaa838dffcc41b'}
PREFIX = 'usr/share/common-licenses/'


def reference_observations(copyrights, index, files):
    rows = []
    for owner in copyrights:
        for reference in owner['common_license_references']:
            target = content.resolve(index, reference)
            row = {'package': owner['package'], 'reference': reference, 'literal_resolution': target}
            if reference == '/' + PREFIX + 'GPL-2.0' and owner['package'] in {'gpg', 'gpgconf'}:
                # Retain the missing literal path, and bind a separately reviewed text candidate.
                require(target['status'] == 'missing', 'GPL-2.0 literal path changed')
                require('complete text of the GPL license, version 2.0,' in owner['text'],
                        'copyright version wording changed')
                alternative = content.resolve(index, PREFIX + 'GPL-2')
                require(alternative['status'] == 'found' and alternative['type'] == 'file',
                        'GPL-2 text missing')
                require(b'Version 2, June 1991' in files[alternative['path']][:160], 'GPL-2 heading changed')
                row['reviewed_text_candidate'] = alternative
                row['literal_path_repaired'] = False
            if reference == '/' + PREFIX + 'LGPL' and owner['package'] == 'libgcrypt20':
                require('version 2.1' in owner['text'], 'libgcrypt license wording changed')
                alternative = content.resolve(index, PREFIX + 'LGPL-2.1')
                require(alternative['status'] == 'found' and alternative['type'] == 'file',
                        'LGPL-2.1 text missing')
                require(b'Version 2.1, February 1999' in files[alternative['path']][:160],
                        'LGPL-2.1 heading changed')
                row['library_declaration_text_candidate'] = alternative
                row['literal_alias_determines_component_license'] = False
            rows.append(row)
    return rows


def inspect(directory, attempt):
    previous_path = HERE / 'musl-verifier-layout-summary-2026-09-12.json'
    previous_raw = previous_path.read_bytes()
    previous = json.loads(previous_raw)
    candidate = previous['pending_common_license_source_candidate']
    require({key: candidate[key] for key in EXPECTED} == EXPECTED, 'candidate digest drift')
    raw = content.reader.fixed(directory / f'base-files-attempt-{attempt}.deb',
                               EXPECTED['bytes'], EXPECTED['sha256'])
    members = content.reader.ar_members(raw)
    control, controls = content.read_tar(members['control.tar.xz'], 4 * 1024**2)
    payload, files = content.read_tar(members['data.tar.xz'], 64 * 1024**2)
    fields = list(content.reader.CHAIN.stanzas(controls['control'].decode().splitlines(keepends=True)))
    require(len(fields) == 1, 'unexpected control record count')
    fields = fields[0]
    for key in ('package', 'version', 'architecture', 'pre-depends', 'breaks', 'replaces', 'provides', 'essential'):
        require(fields.get(key) == candidate['package_row'].get(key), 'control drift: ' + key)
    require(fields.get('source', fields['package']) == candidate['source_row']['package'] and
            fields['version'] == candidate['source_row']['version'], 'source identity drift')
    index = {row['path']: {**row, 'packages': ['base-files']} for row in payload['members']}
    require(not any(data.startswith(b'\x7fELF') for data in files.values()), 'unexpected base-files ELF')
    original = content.inspect(directory, include_text=True)
    owners = {row['package'] for row in previous['layout']['licenses']}
    copyrights = [{'package': p['package'], **p['copyright']}
                  for p in original['packages'] if p['package'] in owners]
    require(len(copyrights) == 12, 'selected copyright owners drift')
    copyright_path = 'usr/share/doc/base-files/copyright'
    copyrights.append({'package': 'base-files', 'text': files[copyright_path].decode(),
                       'common_license_references': ['/' + PREFIX + 'GPL']})
    references = reference_observations(copyrights, index, files)
    selected = {copyright_path}
    for row in references:
        if row['literal_resolution']['status'] == 'found':
            selected.add(row['reference'].lstrip('/'))
            selected.add(row['literal_resolution']['path'])
        for key in ('reviewed_text_candidate', 'library_declaration_text_candidate'):
            if key in row:
                selected.add(row[key]['path'])
    for path in list(selected):
        for parent in Path(path).parents:
            if str(parent) not in {r['path'] for r in previous['layout']['entries']}:
                selected.add(str(parent))
    require(all(path in index for path in selected), 'supplemental path absent from package')
    return {'kind': 'diagnostic-verifier-license-materials', 'acceptance': 'not-assessed',
            'input': identity(raw), 'previous_layout_summary': identity(previous_raw),
            'control': control, 'control_fields': fields, 'payload': payload,
            'copyright': {'path': copyright_path, **identity(files[copyright_path])},
            'installation_metadata': {path: identity(data) for path, data in controls.items()
                                      if path in {'preinst', 'postinst', 'postrm', 'triggers', 'conffiles'}},
            'common_license_entries': [row for path, row in sorted(index.items()) if path.startswith(PREFIX)],
            'reference_observations': references,
            'supplemental_layout_entries': [{**index[path], 'origin': 'package'} for path in sorted(selected)],
            'root_lib_observation': index['lib'], 'root_lib_applied': False,
            'literal_missing_references': [row for row in references if row['literal_resolution']['status'] != 'found'],
            'license_acceptance_assessed': False, 'rootfs_assembled': False,
            'payload_programs_executed': False, 'signature_reverified': False,
            'methods': {**original['methods'], str(Path(__file__).relative_to(HERE.parents[2])):
                        identity(Path(__file__).read_bytes())}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--attempt', choices=(1, 2), type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.directory, args.attempt), sort_keys=True, indent=2))
