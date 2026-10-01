#!/usr/bin/env python3
"""Replay the four retained request logs and report GitHub declarations, never authentication."""
import argparse
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


route = load('fetch-linux-headers-git-metadata.py')
retention = load('retain-musl-verifier-inputs.py')
read, identity, require = retention.read_regular, retention.identity, retention.require
BODIES = {
    'tag-ref': {'bytes': 410, 'sha256': 'e03c1e27b167f7756eee46934dbd44fced50b8e9a078a1ea0cf1c1fd08a4950a'},
    'commit': {'bytes': 1346, 'sha256': '7618b00fef4319d0b3fbff278352109c98a4fb0f6d64e0e3bc461bd42a5960ff'},
}


def declarations(ref, commit):
    expected = route.candidate.COMMIT
    require(ref['ref'] == 'refs/tags/v4.19.88' and ref['object']['type'] == 'commit' and
            ref['object']['sha'] == commit['sha'] == expected, 'fixed ref/commit declaration drift')
    require(re.fullmatch('[0-9a-f]{40}', commit['tree']['sha']) is not None and
            len(commit['parents']) == 1 and
            re.fullmatch('[0-9a-f]{40}', commit['parents'][0]['sha']) is not None, 'tree/parent profile drift')
    verification = commit['verification']
    require(verification == {'verified': False, 'reason': 'unsigned', 'signature': None,
                            'payload': None, 'verified_at': None}, 'observed unsigned profile drift')
    return {'ref': ref['ref'], 'ref_object_type': ref['object']['type'], 'commit': expected,
            'tree': commit['tree']['sha'], 'parents': [p['sha'] for p in commit['parents']],
            'message': commit['message'], 'author_date_declaration': commit['author']['date'],
            'committer_date_declaration': commit['committer']['date'],
            'github_verification_declaration': verification,
            'annotated_tag_object_supplied': False, 'original_git_objects_reconstructed': False,
            'signature_material_available': False, 'signature_verified': False,
            'source_acceptance': 'not-assessed'}


def inspect(directory=route.DIRECTORY):
    plan = json.loads(read(directory / 'fetch-plan.json', 16384))
    require(plan == route.plan(), 'reviewed request plan drift')
    logs, bodies = [], {}
    for name, target in route.TARGETS.items():
        for attempt in (1, 2):
            stem = f'{name}-attempt-{attempt}'
            filename = stem + '.' + target['suffix']
            row = json.loads(read(directory / (stem + '.json'), 16384))
            argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--proto', '=https',
                    '--tlsv1.2', '--max-time', '60', '--max-filesize', str(target['limit']),
                    '--output', str(route.DIRECTORY / filename), '--write-out', '%{http_code}\n', target['url']]
            require(row['argv'] == argv and row['target'] == name and row['attempt'] == attempt and
                    row['url'] == target['url'] and row['method'] == plan['method'] and
                    row['body']['file'] == filename and row['parent_timeout'] is False, 'request scope drift')
            streams = {}
            for channel in ('body', 'stdout', 'stderr'):
                raw = read(directory / (filename if channel == 'body' else stem + '.' + channel), target['limit'])
                require(identity(raw) == {k: row[channel][k] for k in ('bytes', 'sha256')}, 'stream identity drift')
                if channel != 'body':
                    require(raw.decode('utf-8') == row[channel]['text'], 'stream text drift')
                streams[channel] = raw
            if attempt == 1:
                require(row['exit_code'] == 7 and row['http_code'] == '000' and streams['body'] == b'' and
                        streams['stdout'] == b'000\n' and b'127.0.0.1 port 10808' in streams['stderr'] and
                        row['passed'] is False and row['transport_passed'] is False, 'initial failure drift')
            else:
                require(row['exit_code'] == 0 and row['http_code'] == '200' and streams['stdout'] == b'200\n' and
                        streams['stderr'] == b'' and row['passed'] is True and row['transport_passed'] is True,
                        'successful request drift')
                require(identity(streams['body']) == BODIES[name], 'fixed metadata body drift')
                bodies[name] = json.loads(streams['body'])
            logs.append(row)
    require(len({r['curl']['sha256'] for r in logs}) == 1, 'curl identity changed between attempts')
    return {'kind': 'diagnostic-linux-headers-git-metadata-v1', 'plan': plan, 'invocations': logs,
            'declarations': declarations(bodies['tag-ref'], bodies['commit']),
            'method': identity(read(Path(__file__))), 'cryptography_executed': False,
            'additional_urls_followed': False, 'source_acceptance': 'not-assessed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=route.DIRECTORY)
    args = parser.parse_args()
    print(json.dumps(inspect(args.directory), sort_keys=True, indent=2))
