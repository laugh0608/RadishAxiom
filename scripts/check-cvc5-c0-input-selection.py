#!/usr/bin/env python3
"""Offline consistency and boundary checks for private C0 v0.2; never accepts a tool."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 131072


def reject_duplicates(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate-json-key')
        value[key] = item
    return value


def expected():
    spec = importlib.util.spec_from_file_location('cvc5_c0_generator', ROOT / 'scripts/generate-cvc5-c0-input-selection.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.generate()


def same_typed(value, wanted):
    if type(value) is not type(wanted):
        return False
    if isinstance(wanted, dict):
        return value.keys() == wanted.keys() and all(same_typed(value[key], item) for key, item in wanted.items())
    if isinstance(wanted, list):
        return len(value) == len(wanted) and all(same_typed(left, right) for left, right in zip(value, wanted))
    return value == wanted


def reject_constant(value):
    raise ValueError('nonfinite-json')


def verify_sdk():
    spec = importlib.util.spec_from_file_location('c0_sdk_selection_check', ROOT / 'scripts/cvc5-c0-sdk-selection.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify()


def check(raw):
    if not 0 < len(raw) <= LIMIT:
        raise ValueError('record-size-budget')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=reject_duplicates, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError('selection-must-be-object')
    if value.get('format') != 'radishaxiom-private-cvc5-c0-input-selection':
        raise ValueError('unsupported-selection-format')
    if value.get('version') == '0.1':
        raise ValueError('legacy-selection-version-requires-regeneration')
    if value.get('version') != '0.2':
        raise ValueError('unsupported-selection-version')
    if any(value.get(key) is not False for key in ('executable', 'build_ready')):
        raise ValueError('false-execution-or-build-acceptance')
    if any(value.get(key) != 'not-accepted' for key in ('original_cli_acceptance', 'new_payload_acceptance')):
        raise ValueError('false-payload-acceptance')
    # Independent boundary assertions do not treat the shared reviewed decision
    # data as source authentication, nor turn metadata hashes into package hashes.
    archives = value.get('source_archives', [])
    if not isinstance(archives, list) or any(not isinstance(row, dict) for row in archives):
        raise ValueError('invalid-source-archives-shape')
    if ([row.get('id') for row in archives] != ['cvc5', 'cadical', 'gmp', 'libpoly', 'symfpu']
            or any(row.get('raw_digest') is not None or row.get('bytes') is not None
                   or row.get('status') != 'not-obtained' or row.get('license_acceptance') != 'not-accepted'
                   for row in archives)):
        raise ValueError('source-selection-or-unobtained-archive-authentication')
    sdk = value.get('sdk', {})
    if not isinstance(sdk, dict):
        raise ValueError('invalid-sdk-shape')
    if (sdk.get('selection') != 'exact-metadata-only' or sdk.get('metadata_authentication') != 'not-established'
            or sdk.get('package_contents_acceptance') != 'not-accepted'
            or sdk.get('binary_sdk_trust') != 'proposed-not-accepted'):
        raise ValueError('false-sdk-authentication-or-content-acceptance')
    observations = value.get('rechecked_retained_observations', [])
    if (not isinstance(observations, list) or any(not isinstance(row, dict)
            or not isinstance(row.get('file'), str) for row in observations)):
        raise ValueError('invalid-retained-observations-shape')
    if len(observations) != 29 or len({row['file'] for row in observations}) != 29:
        raise ValueError('retained-observation-set-drift')
    # Regeneration also rehashes the retained observations and SDK record bytes.
    # This is consistency checking, not an independent dependency resolver.
    if not same_typed(value, expected()):
        raise ValueError('selection-drift-or-false-acceptance')
    sdk_result = verify_sdk()
    if (sdk_result.get('build_ready') is not False or sdk_result.get('executable') is not False
            or sdk_result.get('signature_verified') is not False):
        raise ValueError('sdk-check-result-false-acceptance')
    return {'selection_consistent': True, 'build_ready': False, 'c0_state': value['c0_state'],
            'source_archives_selected': len(archives), 'sdk_role_groups_selected': len(sdk['items']),
            'sdk_packages_selected': sdk_result['packages'], 'sdk_source_packages_selected': sdk_result['source_packages'],
            'sdk_metadata_dependency_closure': sdk['package_dependency_closure'],
            'retained_observations_rechecked': len(observations), 'original_cli_acceptance': 'not-accepted',
            'new_payload_acceptance': 'not-accepted', 'metadata_authentication': 'not-established',
            'verification_scope': 'reviewed-selection-and-offline-sdk-regeneration-consistency; independent-source-authentication-not-established'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('record', type=Path, nargs='?', default=ROOT / 'docs/records/solver-cvc5-c0-2026-10-17/input-selection.json')
    args = parser.parse_args()
    with args.record.open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    print(json.dumps(check(raw), indent=2))


if __name__ == '__main__':
    main()
