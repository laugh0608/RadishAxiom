import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / '.tmp/cvc5-c1-acquisition-2026-10-22'
NEW = BASE / 'continuation-2'
plan = json.loads((NEW / 'acquisition-plan.json').read_bytes())
proposal = json.loads((NEW / 'continuation-plan.json').read_bytes())
result = json.loads((NEW / 'result.json').read_bytes())
def identity(path):
    digest, count = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            count += len(chunk)
    return {'path': str(path.relative_to(ROOT)), 'bytes': count, 'sha256': digest.hexdigest()}
for old in proposal['prior_records'] + proposal['retained_complete_files'] + [proposal['retained_partial']]:
    actual = identity(ROOT / old['path'])
    assert all(actual[key] == old[key] for key in ('path', 'bytes', 'sha256')), old['path']
assert identity(NEW / 'fetch-helper.py') == result['fetch_method']
assert identity(NEW / 'events.jsonl') == result['journal']
assert identity(NEW / 'continuation-plan.json') == result['proposal']
assert identity(NEW / 'acquisition-plan.json')['sha256'] == proposal['base_plan']['sha256']
matched, partial, missing = [], [], []
for index, row in enumerate(plan['entries'], 1):
    path = (BASE if index <= 40 else NEW) / row['relative_path']
    if not path.exists():
        missing.append(index)
        continue
    assert path.resolve() == path and path.is_file() and not path.is_symlink()
    actual = {'index': index, **identity(path)}
    if actual['bytes'] == row['declared_bytes'] and actual['sha256'] == row['declared_sha256']:
        matched.append(actual)
    else:
        partial.append(actual)
for observed in result['observations']:
    actual = next(item for item in matched + partial if item['index'] == observed['index'])
    assert actual['bytes'] == observed['bytes'] and actual['sha256'] == observed['sha256']
    if observed['status'] == 'obtained-byte-matched':
        assert actual in matched
journal = [json.loads(line) for line in (NEW / 'events.jsonl').read_text().splitlines()]
starts = [item for item in journal if item['event'] == 'request-start']
assert [item['index'] for item in starts] == list(range(41, 48))
assert starts[0]['request_headers']['Range'] == 'bytes=12582912-16306651'
assert sum(item['network_bytes'] for item in result['observations']) == result['response_body_bytes']
assert result['observations'][0]['http_status'] == 206
assert result['observations'][0]['network_bytes'] == 3723740
assert result['transport_route']['https_proxy'] == 'http://127.0.0.1:10808'
assert result['failure'] == {'index': 47, 'type': 'InterruptedError', 'reason': 'acquisition-interrupted'}
summary = {'format': 'radishaxiom-private-cvc5-c1-proxy-acquisition-readback', 'version': '0.1',
    'scope': 'independent-local-raw-byte-readback-no-network', 'method': identity(Path(__file__)),
    'result': identity(NEW / 'result.json'), 'old_materials_unchanged': True,
    'matched_files': len(matched), 'matched_bytes': sum(item['bytes'] for item in matched),
    'new_matched_indices': [item['index'] for item in matched if item['index'] > 40],
    'partial_files': partial, 'missing_indices': missing,
    'request_start_indices': [item['index'] for item in starts],
    'followed_redirects': sum(item['event'] == 'redirect' for item in journal),
    'network_body_bytes': result['response_body_bytes'],
    'first_tail_bytes_per_second': result['observations'][0]['network_bytes'] / result['observations'][0]['elapsed_seconds'],
    'stop_reason': 'operator-stop-after-slow-proxy-sample-per-owner-instruction',
    'all_raw_bytes_complete': len(matched) == 500,
    'unpacked': False, 'installed': False, 'built': False, 'payload_executed': False,
    'input_acceptance': 'not-accepted', 'build_ready': False}
with (NEW / 'readback.json').open('x') as stream:
    json.dump(summary, stream, ensure_ascii=True, indent=2)
    stream.write('\n')
print(json.dumps({key:summary[key] for key in ('matched_files','matched_bytes','new_matched_indices','partial_files','network_body_bytes','first_tail_bytes_per_second')}))
