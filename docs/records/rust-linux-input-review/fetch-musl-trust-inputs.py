"""Fetch one explicitly authorized musl trust input; never install or follow links."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

TARGETS = {
    'keys': ('https://ftp-master.debian.org/keys.html', 1048576, 'html'),
    'keyring': ('https://deb.debian.org/debian/pool/main/d/debian-archive-keyring/'
                'debian-archive-keyring_2023.3+deb12u2_all.deb', 524288, 'deb'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    name, number = sys.argv[1:]
    if name not in TARGETS or number not in {'1', '2'}:
        raise ValueError('unauthorized target or attempt')
    directory = Path(__file__).resolve().parent
    prefix = directory / (name + '-attempt-' + number)
    if number == '2':
        first = json.loads((directory / (name + '-attempt-1.json')).read_text())
        if first['exit_code'] not in {5, 6, 7, 18, 28, 35, 52, 55, 56} or first['http_code'] not in {'000', '200'}:
            raise ValueError('first attempt is not retryable transport failure')
    url, limit, suffix = TARGETS[name]
    body = prefix.with_suffix('.' + suffix)
    record = prefix.with_suffix('.json')
    with record.open('x'):
        pass
    with body.open('xb'):
        pass
    argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error',
            '--proto', '=https', '--tlsv1.2', '--max-time', '60',
            '--max-filesize', str(limit), '--output', str(body),
            '--write-out', '%{http_code}\n', url]
    started = datetime.now(timezone.utc).isoformat()
    with prefix.with_suffix('.stdout').open('xb') as stdout, prefix.with_suffix('.stderr').open('xb') as stderr:
        result = subprocess.run(argv, stdout=stdout, stderr=stderr, timeout=65)
    data = body.read_bytes()
    raw_out = prefix.with_suffix('.stdout').read_bytes()
    raw_err = prefix.with_suffix('.stderr').read_bytes()
    http_code = raw_out.decode('ascii').strip()
    observation = {
        'kind': 'diagnostic-fetch-observation', 'acceptance': 'not-assessed',
        'target': name, 'attempt': int(number), 'url': url, 'argv': argv,
        'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
        'method_sha256': digest(Path(__file__).read_bytes()),
        'curl_sha256': digest(Path('/usr/bin/curl').read_bytes()),
        'exit_code': result.returncode, 'http_code': http_code,
        'body': {'file': body.name, 'bytes': len(data), 'sha256': digest(data)},
        'stdout': {'bytes': len(raw_out), 'sha256': digest(raw_out), 'text': raw_out.decode('ascii')},
        'stderr': {'bytes': len(raw_err), 'sha256': digest(raw_err), 'text': raw_err.decode('utf-8')},
        'transport_passed': result.returncode == 0 and http_code == '200' and len(data) <= limit,
    }
    record.write_text(json.dumps(observation, sort_keys=True, indent=2) + '\n')
    print(json.dumps({k: observation[k] for k in ('target', 'attempt', 'exit_code', 'http_code', 'body', 'transport_passed')}))
    return 0 if observation['transport_passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
