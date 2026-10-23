"""Retain the owner-provided item 48 without changing historical evidence."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path('/tmp/cvc5-proxy-test.nLZRSY/libhwasan0.deb')
DESTINATION = ROOT / 'artifacts/cvc5-c1-retained-2026-10-23/inputs/pool/main/g/gcc-12/libhwasan0_12.2.0-14_arm64.deb'
RECORDS = Path(__file__).resolve().parent
PLAN = ROOT / 'docs/records/solver-cvc5-c1-2026-10-22/acquisition-plan.json'
PREVIOUS = ROOT / 'docs/records/solver-cvc5-c1-2026-10-22/continuation-3-readback.json'


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


assert identity(PLAN)['sha256'] == '165672c67dcaea6963f00dc13e2128a3563fc8a59b58e27326ae58e47f1749cc'
row = json.loads(PLAN.read_bytes())['entries'][47]
assert SOURCE.is_file() and not SOURCE.is_symlink()
before = identity(SOURCE.resolve())
assert before['bytes'] == row['declared_bytes'] and before['sha256'] == row['declared_sha256']
assert not DESTINATION.exists() and not DESTINATION.is_symlink()
DESTINATION.parent.mkdir(parents=True, exist_ok=True)
assert DESTINATION.parent.resolve() == DESTINATION.parent
with DESTINATION.open('xb') as stream:
    stream.write(SOURCE.read_bytes())
after = identity(DESTINATION)
assert after['bytes'] == before['bytes'] and after['sha256'] == before['sha256']
assert identity(SOURCE.resolve()) == before
previous = json.loads(PREVIOUS.read_bytes())
inventory = [dict(item) for item in previous['matched_inventory']]
assert len(inventory) == 500 and inventory[47]['index'] == 48
inventory[47] = {'index': 48, **after}
for item in inventory:
    actual = identity(ROOT / item['path'])
    assert all(actual[key] == item[key] for key in ('path', 'bytes', 'sha256'))
record = {'format': 'radishaxiom-private-cvc5-c1-retained-inventory', 'version': '0.1',
          'observed_utc': datetime.now(timezone.utc).isoformat(), 'method': identity(Path(__file__)),
          'base_plan': identity(PLAN), 'previous_readback': identity(PREVIOUS),
          'copied_index': 48, 'source': before, 'destination': after, 'original_unchanged': True,
          'matched_files': 500, 'matched_bytes': sum(item['bytes'] for item in inventory),
          'inventory': inventory, 'retention': 'local-ignored-artifact; no system-temp dependency for item 48',
          'unpacked': False, 'installed': False, 'built': False, 'payload_executed': False,
          'input_acceptance': 'not-accepted', 'build_ready': False}
with (RECORDS / 'retained-inventory.json').open('x') as stream:
    json.dump(record, stream, ensure_ascii=True, indent=2)
    stream.write('\n')
print(json.dumps({'retained': after, 'all_500_rechecked': True, 'original_unchanged': True}))
