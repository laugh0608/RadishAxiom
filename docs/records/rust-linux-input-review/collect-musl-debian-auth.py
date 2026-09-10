#!/usr/bin/env python3
"""Collect offline GnuPG observations, not a source acceptance decision."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

KEYRING_SHA256 = '506b815cbb32d9b6066b4a2aa524071e071761e7e7f68c3ac74f3061ba852017'
INRELEASE_SHA256 = '98b25b5cd185c59d34aa6e4c3e9b5b8f01bbe9d104fe2dcfbcd30dc0a14a59ed'
ROLES = ['04B54C3CDCA79751B16BC6B5225629DF75B188BD',
         '41587F7DB8C774BCCF131416762F67A0B2C39DE4']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=25,
                            env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'HOME': '/tmp'})
    return {'argv': [str(x) for x in args], 'exit_code': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr}


def collect(result):
    inputs = Path('/inputs')
    for name, limit, expected in [('InRelease', 512 * 1024, INRELEASE_SHA256),
                                  ('debian-archive-keyring.gpg', 64 * 1024, KEYRING_SHA256)]:
        path = inputs / name
        if path.stat().st_size > limit:
            raise ValueError('input size limit')
        data = path.read_bytes()
        if digest(data) != expected:
            raise ValueError('input digest mismatch: ' + name)
        result['inputs'][name] = {'bytes': len(data), 'sha256': expected}
    result['gpg'] = {'sha256': digest(Path('/usr/bin/gpg').read_bytes()),
                     'version': run(['/usr/bin/gpg', '--version'])}
    with tempfile.TemporaryDirectory(prefix='musl-debian-', dir='/tmp') as directory:
        home = Path(directory)
        args = ['/usr/bin/gpg', '--batch', '--no-options', '--homedir', str(home),
                '--no-auto-key-retrieve', '--auto-key-locate', 'clear',
                '--no-sig-cache', '--require-cross-certification']
        result['key_import'] = run(args + ['--import', str(inputs / 'debian-archive-keyring.gpg')])
        # Only self-certification is assessed here. Keep the full imported keyring
        # for InRelease verification and original packet observations below.
        self_home = home / 'self-certifications'
        self_home.mkdir(mode=0o700)
        self_args = args.copy()
        self_args[self_args.index('--homedir') + 1] = str(self_home)
        result['self_key_import'] = run(self_args + ['--import-options', 'self-sigs-only',
                                                    '--import', str(inputs / 'debian-archive-keyring.gpg')])
        result['keys'] = {}
        for role in ROLES:
            key = result['keys'][role] = {}
            key['certifications'] = run(self_args + ['--with-colons', '--fixed-list-mode',
                                               '--with-fingerprint', '--with-subkey-fingerprint',
                                               '--check-sigs', role])
            export = home / (role + '.gpg')
            key['export'] = run(args + ['--output', str(export), '--export', role])
            if export.exists():
                key['export_sha256'] = digest(export.read_bytes())
                key['packets'] = run(args + ['--list-packets', str(export)])
        plaintext = home / 'Release'
        result['verification'] = run(args + ['--status-fd', '1', '--output', str(plaintext),
                                             '--decrypt', str(inputs / 'InRelease')])
        result['verified_text'] = plaintext.read_text() if plaintext.exists() else None
    commands = [result['key_import'], result['self_key_import'], result['verification']]
    commands += [key[name] for key in result['keys'].values()
                 for name in ('certifications', 'export', 'packets')]
    return 0 if all(command['exit_code'] == 0 for command in commands) else 1


def main():
    result = {'kind': 'diagnostic-gnupg-observation', 'acceptance': 'not-assessed',
              'observed_at': datetime.now(timezone.utc).isoformat(),
              'python': platform.python_version(), 'inputs': {},
              'method_sha256': digest(Path(__file__).read_bytes())}
    try:
        code = collect(result)
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)}
        code = 1
    result['exit_code'] = code
    print(json.dumps(result, sort_keys=True, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
