#!/usr/bin/env python3
"""Offline signature and patch diagnostic; never executes upstream source."""
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('patch_inputs', HERE / 'inspect-musl-patches.py')
patch_inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch_inputs)
FINGERPRINT = '836489290BB6B70F99FFDA0556BCDB593020450F'
PINNED = {
    'musl-1.2.5.tar.gz': 'a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4',
    'musl-1.2.5.tar.gz.asc': 'd9030116fd03e4acfa0b665a13a5de46110296b4e30bb8e67be1f08af29f6306',
    'musl.pub': 'bf6baaa63c2c4958636850a24bb9d2d514c8b6a1b3ab9c08f3b75910fb6f57be',
}
ORIGINAL = {
    'src/locale/iconv.c': '2aadd020959004608625bb6b7759d81daa5abf347643399ba887f5d11277b4c1',
    'src/stdlib/qsort.c': '3a838cc7f83f4746df6063f567be1ebb2f7d204243342122acd43f44d2434ec6',
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def run(args, cwd=None, timeout=15):
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                          env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'HOME': '/tmp'})
    return {'argv': [str(x) for x in args], 'exit_code': proc.returncode,
            'stdout': proc.stdout, 'stderr': proc.stderr}


def valid_signature(status):
    rows = [line.split()[1:] for line in status.splitlines() if line.startswith('[GNUPG:] ')]
    bad = {'BADSIG', 'ERRSIG', 'EXPSIG', 'EXPKEYSIG', 'REVKEYSIG', 'NO_PUBKEY', 'FAILURE'}
    signatures = [row for row in rows if row and row[0] == 'VALIDSIG']
    return (not any(row and row[0] in bad for row in rows)
            and len(signatures) == 1 and len(signatures[0]) == 11
            and signatures[0][-1] == FINGERPRINT and signatures[0][8] in {'8', '9', '10'})


def verify(inputs):
    with tempfile.TemporaryDirectory(prefix='musl-key-', dir='/tmp') as home:
        args = ['/usr/bin/gpg', '--batch', '--no-options', '--homedir', home,
                '--no-auto-key-retrieve', '--auto-key-locate', 'clear']
        result = {'fingerprint_from_official_page': FINGERPRINT,
                  'publisher_identity_acceptance': 'not-assessed',
                  'version': run(['/usr/bin/gpg', '--version']),
                  'gpg_sha256': sha256(Path('/usr/bin/gpg').read_bytes())}
        key = inputs / 'musl.pub'
        result['key_show'] = run(args + ['--with-colons', '--import-options', 'show-only', '--import', str(key)])
        primary = None
        count = 0
        for line in result['key_show']['stdout'].splitlines():
            fields = line.split(':')
            if fields[0] == 'pub':
                count += 1
            if fields[0] == 'fpr' and primary is None:
                primary = fields[9]
        if result['key_show']['exit_code'] or count != 1 or primary != FINGERPRINT:
            result['error'] = 'unexpected public key or primary fingerprint'
            result['pinned_signature_passed'] = False
            return result
        result['key_packets'] = run(args + ['--list-packets', str(key)])
        result['key_import'] = run(args + ['--import', str(key)])
        result['key_certifications'] = run(args + ['--with-colons', '--check-sigs', FINGERPRINT])
        result['signature_packets'] = run(args + ['--list-packets', str(inputs / 'musl-1.2.5.tar.gz.asc')])
        result['verification'] = run(args + ['--status-fd', '1', '--verify',
                                           str(inputs / 'musl-1.2.5.tar.gz.asc'),
                                           str(inputs / 'musl-1.2.5.tar.gz')])
        result['pinned_signature_passed'] = (result['key_import']['exit_code'] == 0
                                            and result['verification']['exit_code'] == 0
                                            and valid_signature(result['verification']['stdout']))
        return result


def original_files(data):
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        raw = stream.read(32 * 1024**2 + 1)
    if len(raw) > 32 * 1024**2:
        raise ValueError('source tar expansion limit')
    selected = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as tar:
        for count, member in enumerate(tar, 1):
            if count > 10000 or member.size < 0 or member.size > 8 * 1024**2:
                raise ValueError('source tar member limit')
            relative = member.name.removeprefix('musl-1.2.5/')
            if relative not in ORIGINAL:
                continue
            if not member.isfile() or relative in selected:
                raise ValueError('selected source is linked or duplicate')
            body = tar.extractfile(member).read()
            if sha256(body) != ORIGINAL[relative]:
                raise ValueError('selected source digest mismatch')
            selected[relative] = body
    if selected.keys() != ORIGINAL.keys():
        raise ValueError('missing selected source')
    return selected


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('link in patch result')
        if path.is_dir():
            continue
        relative = path.relative_to(root).as_posix()
        if relative not in patch_inputs.ALLOWED or not path.is_file():
            raise ValueError('unexpected patch result path: ' + relative)
        data = path.read_bytes()
        result[relative] = {'bytes': len(data), 'sha256': sha256(data),
                            'git_blob_sha1': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()}
    return result


def patch_check(inputs, source):
    result = {'version': run(['/usr/bin/patch', '--version']),
              'patch_sha256': sha256(Path('/usr/bin/patch').read_bytes()),
              'help': run(['/usr/bin/patch', '--help']), 'steps': []}
    originals = original_files(source)
    with tempfile.TemporaryDirectory(prefix='musl-patch-', dir='/tmp') as directory:
        root = Path(directory)
        for name, body in originals.items():
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(body)
        result['before'] = inventory(root)
        for name, expected in patch_inputs.PATCHES.items():
            patch = inputs / 'patches' / name
            data = patch.read_bytes()
            if sha256(data) != expected:
                raise ValueError('patch digest mismatch')
            step = {'file': name, 'sha256': expected, 'preflight': patch_inputs.inspect(data)}
            args = ['/usr/bin/patch', '--batch', '--forward', '--fuzz=0',
                    '--no-backup-if-mismatch', '-p1', '--input', str(patch)]
            before = inventory(root)
            step['dry_run'] = run(args + ['--dry-run'], cwd=root, timeout=10)
            if inventory(root) != before:
                raise ValueError('dry run changed source')
            if step['dry_run']['exit_code']:
                result['steps'].append(step)
                result['passed'] = False
                return result
            step['apply'] = run(args, cwd=root, timeout=10)
            result['steps'].append(step)
            try:
                step['after'] = inventory(root)
            except ValueError as error:
                step['inventory_error'] = str(error)
                result['passed'] = False
                return result
            if step['apply']['exit_code'] or 'fuzz' in (step['apply']['stdout'] + step['apply']['stderr']).lower():
                result['passed'] = False
                return result
        result['after'] = inventory(root)
        if set(result['after']) != patch_inputs.ALLOWED:
            raise ValueError('missing patch result file')
        result['passed'] = True
        result['final_text'] = {name: (root / name).read_text() for name in sorted(patch_inputs.ALLOWED)}
    return result


def main():
    inputs = Path('/inputs')
    result = {'kind': 'diagnostic-observation', 'acceptance': 'not-assessed',
              'python': platform.python_version(), 'inputs': {},
              'methods': {name: sha256((HERE / name).read_bytes())
                          for name in ('verify-musl-source.py', 'inspect-musl-patches.py')}}
    for name, expected in PINNED.items():
        data = (inputs / name).read_bytes()
        if len(data) > 4 * 1024**2 or sha256(data) != expected:
            raise ValueError('pinned input size or digest mismatch')
        result['inputs'][name] = {'bytes': len(data), 'sha256': expected}
    try:
        result['signature'] = verify(inputs)
        result['patches'] = patch_check(inputs, (inputs / 'musl-1.2.5.tar.gz').read_bytes())
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)}
        print(json.dumps(result, sort_keys=True, indent=2))
        raise
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result['signature']['pinned_signature_passed'] and result['patches']['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
