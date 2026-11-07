"""Independent raw-byte audit after continuation 3; no network or unpacking."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / '.tmp/cvc5-c1-acquisition-2026-10-22'
NEW = BASE / 'continuation-3'


def identity(path):
    digest, count = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            count += len(chunk)
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': count, 'sha256': digest.hexdigest()}


def check(expected):
    path = ROOT / expected['path']
    assert path.resolve() == path and path.is_file() and not path.is_symlink(), path
    actual = identity(path)
    assert all(actual[key] == expected[key] for key in ('path', 'bytes', 'sha256')), path
    return actual


plan = json.loads((NEW / 'acquisition-plan.json').read_bytes())
proposal = json.loads((NEW / 'continuation-plan.json').read_bytes())
result = json.loads((NEW / 'result.json').read_bytes())
previous = json.loads((BASE / 'continuation-2/continuation-plan.json').read_bytes())
assert identity(NEW / 'acquisition-plan.json')['sha256'] == '165672c67dcaea6963f00dc13e2128a3563fc8a59b58e27326ae58e47f1749cc'
assert identity(NEW / 'continuation-plan.json')['sha256'] == '061d506821b5e7b22aed9766188d041d2de400c6fbc99a50052bc9bade1a4c45'
for expected in proposal['prior_records'] + proposal['retained_complete_files'] + [proposal['retained_partial'], previous['retained_partial']]:
    check(expected)
for field in ('fetch_method', 'journal', 'proposal'):
    check(result[field])
paths = {row['index']: row['path'] for row in proposal['retained_complete_files']}
paths.update({row['index']: row['output_path'] for row in proposal['requests_detail']})
assert sorted(paths) == list(range(1, 501))
matched, partial, missing = [], [], []
for index, row in enumerate(plan['entries'], 1):
    path = ROOT / paths[index]
    if not path.exists():
        missing.append(index)
        continue
    assert path.resolve() == path and path.is_file() and not path.is_symlink(), path
    actual = {'index': index, **identity(path)}
    if actual['bytes'] == row['declared_bytes'] and actual['sha256'] == row['declared_sha256']:
        matched.append(actual)
    else:
        partial.append(actual)
expected_indices = [47] + list(range(49, 501))
observed_indices = [row['index'] for row in result['observations']]
assert observed_indices == expected_indices[:len(observed_indices)]
for observed in result['observations']:
    actual = next(item for item in matched + partial if item['index'] == observed['index'])
    assert actual['bytes'] == observed['bytes'], observed['index']
    if 'sha256' in observed:
        assert actual['sha256'] == observed['sha256'], observed['index']
    if observed['status'] == 'obtained-byte-matched':
        assert actual in matched
events = [json.loads(line) for line in (NEW / 'events.jsonl').read_text().splitlines()]
starts = [row for row in events if row['event'] == 'request-start']
assert [row['index'] for row in starts] == observed_indices[:len(starts)]
assert starts[0]['request_headers']['Range'] == 'bytes=79180-103991'
assert starts[0]['request_headers']['If-Range'] == '"19638-5f1e07a37d140"'
assert all(row['index'] != 48 for row in starts)
assert result['observations'][0]['http_status'] == 206
assert result['observations'][0]['network_bytes'] == 24812
assert sum(row['network_bytes'] for row in result['observations']) == result['response_body_bytes']
assert result['response_body_bytes'] <= 628212768
assert result['transport_route']['https_proxy'] == 'http://127.0.0.1:10808'
assert result['matched_files'] == len(matched)
assert not partial or len(partial) == 1 and partial[0]['index'] == result['failure']['index']
if result['download_complete']:
    assert len(matched) == 500 and not partial and not missing
    assert result['response_body_bytes'] == 628212768
    assert result['readback_complete'] and result['failure'] is None
summary = {'format': 'radishaxiom-private-cvc5-c1-continuation-3-readback', 'version': '0.1',
           'scope': 'independent-local-raw-byte-readback-no-network',
           'method': identity(Path(__file__)), 'result': identity(NEW / 'result.json'),
           'old_materials_unchanged': True, 'user_file_48_reused_without_request': True,
           'matched_files': len(matched), 'matched_bytes': sum(row['bytes'] for row in matched),
           'matched_inventory': matched, 'partial_files': partial, 'missing_indices': missing,
           'request_start_indices': [row['index'] for row in starts],
           'followed_redirects': sum(row['event'] == 'redirect' for row in events),
           'network_body_bytes': result['response_body_bytes'], 'failure': result['failure'],
           'all_raw_bytes_complete': len(matched) == 500,
           'unpacked': False, 'installed': False, 'built': False, 'payload_executed': False,
           'input_acceptance': 'not-accepted', 'build_ready': False}
with (NEW / 'readback.json').open('x') as stream:
    json.dump(summary, stream, ensure_ascii=True, indent=2)
    stream.write('\n')
print(json.dumps({key: summary[key] for key in ('matched_files', 'matched_bytes', 'partial_files',
                 'network_body_bytes', 'all_raw_bytes_complete', 'failure')}))
