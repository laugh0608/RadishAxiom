#!/usr/bin/env bash
# Diagnostic verification only; fixed read-only keyring, ephemeral /tmp output.
set -euo pipefail
umask 077
mkdir /tmp/gnupg
export GNUPGHOME=/tmp/gnupg
verify_exit=0
gpgv --keyring /usr/share/keyrings/debian-archive-keyring.gpg \
  --status-fd 3 --output /tmp/Release /inputs/InRelease \
  3> /tmp/status > /tmp/stdout 2> /tmp/stderr || verify_exit=$?
VERIFY_EXIT="$verify_exit" python3 - <<'PY'
import base64, hashlib, json, os, pathlib, shutil, subprocess
keyring = pathlib.Path('/usr/share/keyrings/debian-archive-keyring.gpg').read_bytes()
program = pathlib.Path(shutil.which('gpgv')).resolve()
release = pathlib.Path('/tmp/Release')
print(json.dumps({
    'kind': 'diagnostic-signature-observation',
    'acceptance': 'not-assessed',
    'exit_code': int(os.environ['VERIFY_EXIT']),
    'status': pathlib.Path('/tmp/status').read_text(),
    'stdout': pathlib.Path('/tmp/stdout').read_text(),
    'stderr': pathlib.Path('/tmp/stderr').read_text(),
    'verified_text': release.read_text() if release.exists() else None,
    'inrelease_sha256': hashlib.sha256(pathlib.Path('/inputs/InRelease').read_bytes()).hexdigest(),
    'keyring': {'path': '/usr/share/keyrings/debian-archive-keyring.gpg',
                'sha256': hashlib.sha256(keyring).hexdigest(),
                'base64': base64.b64encode(keyring).decode()},
    'gpgv': {'path': str(program), 'sha256': hashlib.sha256(program.read_bytes()).hexdigest(),
             'version': subprocess.run([str(program), '--version'], check=True, capture_output=True, text=True, timeout=3).stdout},
}, sort_keys=True, indent=2))
PY
exit "$verify_exit"
