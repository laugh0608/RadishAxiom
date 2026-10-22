#!/usr/bin/env python3
"""One authorized C1 raw-byte acquisition; stop at the first error, never resume.

No archive contents are inspected or executed. The offline preparation entry
remains separate and unchanged; this consumer freezes its approved plan bytes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import signal
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cvc5_prep', ROOT / 'scripts/cvc5-build-preparation.py')
PREP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PREP)
APPROVED_PLAN_SHA256 = '165672c67dcaea6963f00dc13e2128a3563fc8a59b58e27326ae58e47f1749cc'
HEADER_NAMES = frozenset(('content-length', 'content-encoding', 'content-type',
                         'date', 'last-modified', 'etag'))
REQUEST_HEADERS = {'User-Agent': 'RadishAxiom-C1-byte-acquisition/0.1', 'Accept-Encoding': 'identity'}
BLOCK = 1024 * 1024


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + '\n').encode()


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def headers(value):
    result = {}
    for key in HEADER_NAMES:
        entries = value.get_all(key, [])
        require(len(entries) <= 1, 'duplicate-response-header:' + key)
        if entries:
            require(len(entries[0]) <= 4096, 'response-header-size')
            result[key] = entries[0]
    return result


def allowed_redirect(url):
    require(isinstance(url, str) and len(url) <= 4096, 'redirect-url-size')
    parts = urllib.parse.urlsplit(url)
    require(parts.scheme == 'https' and parts.netloc == 'snapshot.debian.org'
            and not parts.query and not parts.fragment
            and re.fullmatch(r'/file/[0-9a-f]{40}/(?:[A-Za-z0-9_+~.=-]|%2[Bb])+', parts.path),
            'redirect-outside-approved-content-address-path')
    # Snapshot percent-encodes literal '+' in package revisions. Permit only
    # this observed equivalent spelling; encoded slash/dot/% remain rejected.
    name = urllib.parse.unquote(parts.path.rsplit('/', 1)[1])
    require(name not in ('.', '..'), 'redirect-dot-segment')


class Redirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, observation, event):
        self.observation, self.event = observation, event

    def http_error_302(self, req, fp, code, msg, response_headers):
        # urllib's default redirect handler reads an unbounded redirect body.
        # Close it instead: the authorized payload is the final pinned object.
        try:
            locations = response_headers.get_all('location', [])
            require(len(locations) == 1 and len(locations[0]) <= 4096, 'redirect-location-count-or-size')
            target = urllib.parse.urljoin(req.full_url, locations[0])
            allowed_redirect(target)
            chain = self.observation['redirects']
            require(len(chain) < 5, 'redirect-count-limit')
            seen = {self.observation['requested_url']} | {hop['to_url'] for hop in chain}
            require(target not in seen, 'redirect-loop')
            hop = {'status': code, 'from_url': req.full_url, 'to_url': target}
            chain.append(hop)
            self.event({'event': 'redirect', **hop})
        except Exception:
            self.observation['rejected_redirect'] = {
                'status': code, 'from_url': req.full_url,
                'location': response_headers.get('location', '')[:4096]}
            raise
        finally:
            fp.close()
        return self.parent.open(urllib.request.Request(target, headers=REQUEST_HEADERS), timeout=req.timeout)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


class Journal:
    def __init__(self, path, limit):
        self.stream = path.open('xb')
        self.limit, self.bytes = limit, 0

    def append(self, value):
        raw = (json.dumps(dict(utc=now(), **value), ensure_ascii=True, separators=(',', ':')) + '\n').encode()
        require(self.bytes + len(raw) <= self.limit, 'journal-byte-budget')
        self.stream.write(raw)
        self.stream.flush()
        self.bytes += len(raw)

    def close(self):
        self.stream.close()


def timeout(signum, frame):
    raise TimeoutError('item-or-batch-deadline')


def interrupted(signum, frame):
    raise InterruptedError('acquisition-interrupted')


def error_info(error):
    # Never record arbitrary environment/proxy exception strings or credentials.
    result = {'type': type(error).__name__}
    if isinstance(error, urllib.error.HTTPError):
        result['http_status'] = error.code
        try:
            result['response_headers'] = headers(error.headers)
        except ValueError as header_error:
            result['response_header_error'] = str(header_error)
    elif isinstance(error, urllib.error.URLError):
        result['reason_type'] = type(error.reason).__name__
        result['errno'] = getattr(error.reason, 'errno', None)
    elif isinstance(error, (ValueError, TimeoutError, InterruptedError)):
        result['reason'] = str(error)[:512]
    elif isinstance(error, OSError):
        result['errno'] = error.errno
    return result


def fetch_one(row, directory, observation, budget, event, seconds):
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    opener = urllib.request.build_opener(Redirect(observation, event), urllib.request.HTTPSHandler(context=context))
    path = directory / row['relative_path']
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists() and not path.is_symlink(), 'input-already-exists')
    require(path.parent.resolve() == path.parent, 'input-parent-symlink')
    request = urllib.request.Request(row['url'], headers=REQUEST_HEADERS)
    with opener.open(request, timeout=seconds) as response:
        observation['http_status'] = response.status
        observation['final_url'] = response.geturl()
        observation['response_headers'] = headers(response.headers)
        require(response.status == 200, 'non-200-response')
        expected_url = observation['redirects'][-1]['to_url'] if observation['redirects'] else row['url']
        require(response.geturl() == expected_url, 'unobserved-final-url')
        length = observation['response_headers'].get('content-length')
        require(length is None or length.isdigit() and int(length) == row['declared_bytes'],
                'content-length-mismatch')
        require(observation['response_headers'].get('content-encoding', 'identity') == 'identity',
                'unexpected-content-encoding')
        with path.open('xb') as stream:
            hasher = hashlib.sha256()
            while True:
                # At most one overflow byte is read to detect a false length.
                capacity = min(BLOCK, row['declared_bytes'] - observation['bytes'] + 1,
                               budget['limit'] - budget['received'])
                if capacity == 0:
                    # At the total ceiling, a matching HTTP Content-Length is
                    # needed to establish completion without reading beyond it.
                    require(length is not None and observation['bytes'] == int(length),
                            'body-budget-before-established-eof')
                    break
                data = response.read(capacity)
                if not data:
                    break
                observation['bytes'] += len(data)
                budget['received'] += len(data)
                stream.write(data)
                hasher.update(data)
                observation['sha256'] = hasher.hexdigest()
                require(observation['bytes'] <= row['declared_bytes'], 'payload-size-overflow')
                require(budget['received'] <= budget['limit'], 'batch-body-budget')
            observation['sha256'] = hasher.hexdigest()
        require(observation['bytes'] == row['declared_bytes'], 'payload-size-mismatch')
        require(observation['sha256'] == row['declared_sha256'], 'payload-sha256-mismatch')


def fetch_rows(plan, directory, journal, result):
    policy = plan['transport_policy']
    deadline = time.monotonic() + policy['batch_deadline_seconds']
    budget = {'received': 0, 'limit': policy['response_body_byte_limit']}
    for index, row in enumerate(plan['entries'], 1):
        observation = {'index': index, 'requested_url': row['url'], 'relative_path': row['relative_path'],
                       'started_utc': now(), 'redirects': [], 'bytes': 0, 'status': 'started'}
        result['observations'].append(observation)
        started = time.monotonic()
        try:
            seconds = min(policy['per_item_deadline_seconds'], deadline - started)
            require(seconds > 0, 'batch-deadline-before-next-request')
            journal.append({'event': 'request-start', **observation})
            signal.setitimer(signal.ITIMER_REAL, seconds)
            try:
                fetch_one(row, directory, observation, budget, journal.append, seconds)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            require(time.monotonic() <= deadline, 'batch-deadline-after-response')
            observation['status'] = 'obtained-byte-matched'
            observation['finished_utc'] = now()
            observation['elapsed_seconds'] = round(time.monotonic() - started, 6)
            journal.append({'event': 'request-finished', **observation})
            result['matched_files'] += 1
            result['matched_bytes'] += observation['bytes']
            if index == 1 or index % 10 == 0 or index == len(plan['entries']):
                print(json.dumps({'matched_files': result['matched_files'], 'total_files': len(plan['entries']),
                                  'matched_bytes': result['matched_bytes']}), flush=True)
        except (Exception, KeyboardInterrupt) as error:
            signal.setitimer(signal.ITIMER_REAL, 0)
            observation.update(status='failed', finished_utc=now(), error=error_info(error),
                               elapsed_seconds=round(time.monotonic() - started, 6))
            result['failure'] = {'index': index, 'relative_path': row['relative_path'], **observation['error']}
            result['response_body_bytes'] = budget['received']
            # Reserve space separately from the journal for this final result.
            if journal.bytes < journal.limit - 16384:
                journal.append({'event': 'stopped-at-first-error', **observation})
            print(json.dumps({'stopped': True, 'failure': result['failure'],
                              'matched_files': result['matched_files']}), flush=True)
            return
    result['response_body_bytes'] = budget['received']
    result['download_complete'] = True


def fetch():
    raw = PREP.PLAN.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == APPROVED_PLAN_SHA256, 'approved-plan-sha256-drift')
    plan = PREP.verify_plan()
    require(plan['summary']['total_files'] == 500 and plan['summary']['total_bytes'] == 691605464,
            'approved-count-or-bytes-drift')
    directory = ROOT / plan['retention_directory']
    require(directory == ROOT / '.tmp/cvc5-c1-acquisition-2026-10-22', 'retention-target-drift')
    require(directory.parent.resolve() == directory.parent, 'retention-parent-noncanonical')
    require(not directory.exists() and not directory.is_symlink(), 'batch-exists-refuse-resume')
    free = shutil.disk_usage(directory.parent).free
    require(free >= plan['transport_policy']['minimum_free_bytes'], 'insufficient-free-space')
    directory.mkdir(mode=0o700)
    for name, data in (('acquisition-plan.json', raw), ('fetch-helper.py', Path(__file__).read_bytes())):
        with (directory / name).open('xb') as stream:
            stream.write(data)
    # The approved plan stays immutable and records its preparation-time state;
    # current authorization is recorded separately, never forged into C0 data.
    result = {'format': 'radishaxiom-private-cvc5-c1-acquisition', 'version': '0.1',
              'scope': 'authorized-raw-download-and-byte-check-only',
              'authorization': 'owner-confirmed-500-files-stop-first-error-no-unpack-install-build-or-payload-execution',
              'started_utc': now(), 'initial_free_bytes': free,
              'plan': identity(directory / 'acquisition-plan.json'),
              'fetch_method': identity(directory / 'fetch-helper.py'),
              'download_complete': False, 'readback_complete': False,
              'matched_files': 0, 'matched_bytes': 0, 'response_body_bytes': 0,
              'failure': None, 'observations': [], 'signature_verified': False,
              'input_acceptance': 'not-accepted', 'build_ready': False,
              'unpacked': False, 'installed': False, 'built': False, 'payload_executed': False}
    # Physical journal+result budgets total at most the authorized 8 MiB.
    journal = Journal(directory / 'events.jsonl', 6 * 1024 * 1024)
    old_alarm = signal.signal(signal.SIGALRM, timeout)
    old_term = signal.signal(signal.SIGTERM, interrupted)
    try:
        fetch_rows(plan, directory, journal, result)
        if result['download_complete']:
            audit = PREP.audit_archives(plan, directory)
            require(audit['archive_bytes_complete'], 'final-readback-incomplete')
            result['readback_complete'] = True
            result['readback'] = audit
    except (Exception, KeyboardInterrupt) as error:
        result['failure'] = {'stage': 'batch-or-final-readback', **error_info(error)}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_alarm)
        signal.signal(signal.SIGTERM, old_term)
        journal.close()
        result['finished_utc'] = now()
        result['journal'] = identity(directory / 'events.jsonl')
        data = encoded(result)
        require(len(data) <= 2 * 1024 * 1024, 'result-byte-budget')
        with (directory / 'result.json').open('xb') as stream:
            stream.write(data)
    print(json.dumps({key: result[key] for key in ('download_complete', 'readback_complete',
        'matched_files', 'matched_bytes', 'response_body_bytes', 'failure', 'build_ready')}), flush=True)
    return 0 if result['download_complete'] and result['readback_complete'] and result['failure'] is None else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirmed-plan-sha256', required=True)
    args = parser.parse_args()
    require(args.confirmed_plan_sha256 == APPROVED_PLAN_SHA256, 'explicit-approved-plan-hash-required')
    raise SystemExit(fetch())
