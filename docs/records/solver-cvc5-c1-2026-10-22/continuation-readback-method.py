import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
base = ROOT / '.tmp/cvc5-c1-acquisition-2026-10-22'
logs = base / 'continuation-1'
plan = json.loads((base / 'acquisition-plan.json').read_bytes())
prior = json.loads((base / 'result.json').read_bytes())
result = json.loads((logs / 'result.json').read_bytes())
def ident(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
for name, expected in result['continuation']['original_records'].items():
    assert ident(base / name) == expected, name
for field, path in [('plan', logs / 'acquisition-plan.json'), ('fetch_method', logs / 'fetch-helper.py'), ('journal', logs / 'events.jsonl')]:
    assert ident(path) == result[field], field
assert ident(logs / 'fetch-helper.py')['sha256'] == ident(ROOT / 'scripts/fetch-cvc5-c1-inputs.py')['sha256']
matched, missing, partial = [], [], []
for i, row in enumerate(plan['entries'], 1):
    path = base / row['relative_path']
    if not path.exists():
        missing.append(i)
        continue
    assert path.is_file() and not path.is_symlink()
    h, n = hashlib.sha256(), 0
    with path.open('rb') as f:
        while data := f.read(1024 * 1024):
            h.update(data)
            n += len(data)
    observation = {'index': i, 'relative_path': row['relative_path'], 'bytes': n, 'sha256': h.hexdigest()}
    if n == row['declared_bytes'] and h.hexdigest() == row['declared_sha256']:
        matched.append(observation)
    else:
        partial.append(observation)
for old in prior['observations'][:6]:
    row = matched[old['index'] - 1]
    assert row['index'] == old['index'] and row['bytes'] == old['bytes'] and row['sha256'] == old['sha256']
for obs in result['observations']:
    if obs['status'] == 'obtained-byte-matched':
        got = next(x for x in matched if x['index'] == obs['index'])
        assert got['bytes'] == obs['bytes'] and got['sha256'] == obs['sha256']
events = [json.loads(x) for x in (logs / 'events.jsonl').read_text().splitlines()]
starts = [x['index'] for x in events if x['event'] == 'request-start']
assert starts == list(range(7, 7 + len(starts)))
assert starts == [x['index'] for x in result['observations']]
assert not result['unpacked'] and not result['installed'] and not result['built'] and not result['payload_executed']
record = {'format': 'radishaxiom-private-cvc5-c1-continuation-readback', 'version': '0.1',
    'scope': 'independent-raw-byte-readback-no-network-or-payload-execution',
    'method': ident(Path(__file__)), 'result': ident(logs / 'result.json'),
    'original_records_unchanged': True, 'original_six_matched': True,
    'fetch_method_matches_current_script': True, 'matched_files': len(matched),
    'matched_bytes': sum(x['bytes'] for x in matched), 'missing_indices': missing,
    'partial_files': partial, 'request_start_indices': starts,
    'followed_redirects': sum(x['event'] == 'redirect' for x in events),
    'failure': result['failure'], 'all_raw_bytes_complete': len(matched) == 500,
    'unpacked': False, 'payload_executed': False, 'input_acceptance': 'not-accepted', 'build_ready': False}
with (logs / 'readback.json').open('x') as f:
    json.dump(record, f, ensure_ascii=True, indent=2)
    f.write('\n')
print(json.dumps({k:record[k] for k in ['matched_files', 'matched_bytes', 'partial_files', 'failure', 'all_raw_bytes_complete']}))
