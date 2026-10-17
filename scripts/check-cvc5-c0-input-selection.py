#!/usr/bin/env python3
"""Offline consistency check for this private C0 draft; never accepts a tool."""
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


def check(raw):
    if not 0 < len(raw) <= LIMIT:
        raise ValueError('record-size-budget')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=reject_duplicates)
    # The entire reviewed draft is frozen, including its unresolved values and
    # budgets. Matching a draft is not package authentication or build readiness.
    if not same_typed(value, expected()):
        raise ValueError('selection-drift-or-false-acceptance')
    ids = [row['id'] for row in value['source_archives']]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate-component')
    if any(row['raw_digest'] is not None for row in value['source_archives']):
        raise ValueError('unobtained-archive-authentication')
    return {'draft_consistent': True, 'build_ready': False, 'c0_state': value['c0_state'], 'source_archives_selected': len(ids), 'sdk_item_groups_unresolved': len(value['sdk']['items']), 'retained_observations_rechecked': len(value['rechecked_retained_observations']), 'original_cli_acceptance': 'not-accepted', 'new_payload_acceptance': 'not-accepted'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('record', type=Path, nargs='?', default=ROOT / 'docs/records/solver-cvc5-c0-2026-10-17/input-selection.json')
    args = parser.parse_args()
    with args.record.open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    print(json.dumps(check(raw), indent=2))


if __name__ == '__main__':
    main()
