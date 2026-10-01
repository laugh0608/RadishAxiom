#!/usr/bin/env python3
"""Fetch the four approved GnuPG source objects once; no installation or tool execution."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fetch', HERE / 'fetch-mpc-mpfr-inputs.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)
DIRECTORY = HERE.parents[2] / '.tmp/gmp-tool-semantics-3e28608-20260929'
REVIEW = HERE / 'gmp-tool-semantics-review-2026-09-29.json'
REVIEW_SHA = 'c61683dbcd4e040c6634dd28f0733c3f7b68ea0e88779ad596ca10421e59b44e'
ORDER = ('gnupg2_2.4.7-21+deb13u1.dsc', 'gnupg2_2.4.7.orig.tar.bz2',
         'gnupg2_2.4.7.orig.tar.bz2.asc', 'gnupg2_2.4.7-21+deb13u1.debian.tar.xz')


def plan():
    raw = REVIEW.read_bytes()
    if fetch.identity(raw)['sha256'] != REVIEW_SHA:
        raise ValueError('reviewed source scope drift')
    rows = {r['name']: r for r in json.loads(raw)['supplemental_material_targets']}
    if set(rows) != set(ORDER):
        raise ValueError('source target set drift')
    return {'kind': 'diagnostic-gmp-tool-source-fetch-plan-v1', 'directory': str(DIRECTORY),
            'review': fetch.identity(raw), 'targets': [rows[n] for n in ORDER],
            'methods': {p.name: fetch.identity(p.read_bytes()) for p in (Path(__file__), Path(fetch.__file__))},
            'requests_each': 1, 'curl_seconds_each': 60, 'parent_seconds_each': 65,
            'executed': False, 'source_acceptance': 'not-assessed'}


def execute():
    selected = plan()
    if DIRECTORY.resolve() != DIRECTORY.absolute():
        raise ValueError('symlink task directory')
    DIRECTORY.mkdir(mode=0o700)  # Refuse both overwriting and resuming an old batch.
    (DIRECTORY / 'fetch-plan.json').write_text(json.dumps(selected, sort_keys=True, indent=2) + '\n')
    for p in (Path(__file__), Path(fetch.__file__)):
        (DIRECTORY / p.name).write_bytes(p.read_bytes())
    fetch.DIRECTORY = DIRECTORY
    # The existing transport's optional digest gate also requires a musl recipe SHA-1.
    # Reuse transport only and independently enforce this source index's SHA-256 below.
    fetch.TARGETS = {r['name']: {'url': r['url'], 'limit': r['bytes'], 'suffix': 'body'}
                     for r in selected['targets']}
    report = {'kind': 'diagnostic-gmp-tool-source-fetch-v1', 'plan': selected,
              'invocations': [], 'passed': False, 'source_acceptance': 'not-assessed'}
    try:
        for row in selected['targets']:
            code = fetch.fetch(row['name'], 1)
            stem = DIRECTORY / (row['name'] + '-attempt-1')
            observation = json.loads(Path(str(stem) + '.json').read_bytes())
            body = Path(str(stem) + '.body').read_bytes()
            matched = fetch.identity(body) == {k: row[k] for k in ('bytes', 'sha256')}
            report['invocations'].append({'transport': observation, 'source_index_bytes_match': matched})
            if code != 0 or not matched:
                raise ValueError('source request or index mismatch: ' + row['name'])
        if plan() != selected:
            raise ValueError('method or plan changed during requests')
        report['passed'] = True
    except (OSError, ValueError) as error:
        report['failure'] = str(error)
    finally:
        with (DIRECTORY / 'fetch-result.json').open('x') as stream:
            stream.write(json.dumps(report, sort_keys=True, indent=2) + '\n')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized', action='store_true')
    args = parser.parse_args()
    if args.execute_authorized:
        raise SystemExit(execute())
    print(json.dumps(plan(), sort_keys=True, indent=2))
