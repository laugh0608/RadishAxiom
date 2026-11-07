#!/usr/bin/env python3
"""Explicitly accepted historical three-signature diagnostics; no installation/build."""
import argparse
import base64
import json
from pathlib import Path
import time
import uuid

import importlib.util

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OLD = ROOT / 'docs/records/rust-linux-input-review'
OUTPUT = ROOT / 'artifacts/cvc5-c1-historical-verification-2026-10-23-attempt-2'


def load(path):
    spec = importlib.util.spec_from_file_location(path.name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v = load(OLD / 'run-musl-verification.py')
profile = load(HERE / 'inspect-signature-status.py')
v.status = profile
v.keys.status = profile
v.key_material.KEYS = {role: {'primary': primary} for role, primary in
                       [('legacy', profile.LEGACY), ('archive', profile.ARCHIVE), ('release', profile.RELEASE)]}
v.smoke.DOCKER_SHA = '4a728ee98f89005a90198a9be791e8fdaebbcb5e6af9721251efe0113df37759'
require, identity = v.require, v.identity


def commands():
    result = []
    for role, key in v.key_material.KEYS.items():
        result.append((role + '-filter', v.GPG + ['--import-options', 'import-export,self-sigs-only',
                       '--output', '-', '--import', '/inputs/' + role + '.raw.gpg']))
        result.append((role + '-certifications', v.gpg_keyring(role + '.self.gpg') + v.COLONS + ['--check-sigs', key['primary']]))
    result.append(('verify', v.gpg_keyring('debian-archive-keyring.gpg') + ['--proc-all-sigs', '--output', '-', '--decrypt', '/inputs/InRelease']))
    result.append(('tampered-text', v.gpg_keyring('debian-archive-keyring.gpg') + ['--proc-all-sigs', '--output', '-', '--decrypt', '/inputs/InRelease.tampered']))
    for missing in v.key_material.KEYS:
        retained = [r for r in v.key_material.KEYS if r != missing]
        command = v.gpg_keyring(retained[0] + '.raw.gpg') + ['--keyring', '/inputs/' + retained[1] + '.raw.gpg']
        result.append(('missing-' + missing, command + ['--proc-all-sigs', '--output', '-', '--decrypt', '/inputs/InRelease']))
    result.append(('bad-cross-certification', v.gpg_keyring('keyring.bad-cross.gpg') + ['--proc-all-sigs', '--output', '-', '--decrypt', '/inputs/InRelease']))
    return result


def stage():
    trust = load(OLD / 'inspect-musl-trust-inputs.py')
    raw = (ROOT / 'artifacts/source-inputs/musl-verifier-2fb2e70-20260912/objects' / trust.DEB_SHA).read_bytes()
    require(identity(raw) == {'bytes': 178572, 'sha256': trust.DEB_SHA}, 'keyring package changed')
    _, payload = trust.read_tar(trust.ar_members(raw)['data.tar.xz'])
    removed = payload['usr/share/keyrings/debian-archive-removed-keys.gpg']
    require(identity(removed) == {'bytes': 72636, 'sha256': '0ff45da93c7fd62cc3f10b4c5019985caf49e5959bb3bf992f558d11963870fa'}, 'removed keyring changed')
    old = json.loads((ROOT / 'docs/records/linux-builder-source-chain/release-verification.json').read_bytes())
    ring = base64.b64decode(old['keyring']['base64'], validate=True)
    require(identity(ring) == {'bytes': 55918, 'sha256': '506b815cbb32d9b6066b4a2aa524071e071761e7e7f68c3ac74f3061ba852017'}, 'original ring changed')
    legacy = v.keys.key_blocks(removed)[profile.LEGACY]
    require(identity(legacy) == {'bytes': 8132, 'sha256': '89d89bcedee9ed88b25eabb5be786fbca6259f121e6ad6ebf5651f852f5227cf'}, 'legacy key changed')
    ring += legacy
    blocks = v.keys.key_blocks(ring)
    originals = {role: blocks[key['primary']] for role, key in v.key_material.KEYS.items()}
    for role, raw in originals.items():
        v.keys.inventory(raw, v.key_material.KEYS[role]['primary'])
    envelope = (ROOT / '.tmp/cvc5-c0-sdk-metadata-2026-10-17/InRelease').read_bytes()
    require(identity(envelope) == {'bytes': 146972, 'sha256': '2814476b311085e250ddfdee295907bac45afb66f40dc7c1b35ab41a447c1d6c'}, 'InRelease changed')
    require(envelope.count(b'Origin: Debian\n') == 1, 'tamper target')
    corrupted = v.keys.corrupt_backsignature(originals['archive'], profile.ARCHIVE)
    require(ring.count(originals['archive']) == 1, 'archive mutation target')
    files = {'InRelease': envelope, 'debian-archive-keyring.gpg': ring,
             'InRelease.tampered': envelope.replace(b'Origin: Debian\n', b'Origin: DebiaX\n', 1),
             'keyring.bad-cross.gpg': ring.replace(originals['archive'], corrupted, 1),
             **{role + '.raw.gpg': data for role, data in originals.items()}}
    folder = OUTPUT / 'inputs'
    folder.mkdir(mode=0o755)
    for name, data in files.items():
        v.write_new(folder / name, data)
    return folder, originals, files


def missing_role(result, role):
    require(result['failure'] is None and result['returncode'] == 2, 'missing-key case invocation failure')
    lines = v.keys.text_lines(result['status'])
    require(all(line.startswith('[GNUPG:] ') for line in lines), 'malformed missing-role status')
    fields = [line[9:].split() for line in lines]
    allowed = {'NEWSIG', 'KEY_CONSIDERED', 'SIG_ID', 'GOODSIG', 'VALIDSIG', 'PLAINTEXT',
               'TRUST_UNDEFINED', 'VERIFICATION_COMPLIANCE_MODE', 'ERRSIG', 'NO_PUBKEY', 'FAILURE'}
    require(all(f and f[0] in allowed for f in fields), 'unexpected missing-role status')
    primary = v.key_material.KEYS[role]['primary']
    signer = profile.SIGNERS[primary][0]
    require([f for f in fields if f[0] == 'NO_PUBKEY'] == [['NO_PUBKEY', signer[-16:]]], 'wrong missing key')
    require({f[-1] for f in fields if f[0] == 'VALIDSIG'} == profile.REQUIRED - {primary}, 'other roles did not verify')
    require(not any(f[0] in {'GOODSIG', 'VALIDSIG'} and f[1] in {signer, signer[-16:]} for f in fields), 'missing role accepted')
    return {'result': 'expected-verification-rejection', 'missing_primary': primary}


def main():
    OUTPUT.mkdir(mode=0o700)
    (OUTPUT / 'verification-method.py').write_bytes(Path(__file__).read_bytes())
    report = {'format': 'radishaxiom-private-cvc5-historical-verification', 'version': '0.1',
              'started_utc': v.smoke.now(), 'current_task_profile_accepted': True,
              'required_signatures': profile.SIGNERS, 'passed': False, 'cases': [],
              'method': identity(Path(__file__).read_bytes()), 'profile': identity((HERE / 'inspect-signature-status.py').read_bytes()),
              'candidate': identity((HERE / 'historical-key-candidate.json').read_bytes()),
              'key_material_as_of': 'retained-debian-archive-keyring-2025.1; identity-pages-reviewed-2026-10-23',
              'current_all_channel_revocation_checked': False,
              'input_acceptance': 'not-accepted', 'build_ready': False,
              'image': v.inputs.IMAGE, 'cli_sha256': v.smoke.DOCKER_SHA}
    start = time.monotonic()
    try:
        v.smoke.verified_inputs()
        engine = v.smoke.Docker(OUTPUT)
        version = json.loads(v.smoke.checked(engine.call(['version', '--format', v.smoke.template(['Server.Version', 'Server.ApiVersion', 'Server.Os', 'Server.Arch'])])))
        require(version == {'Server.Version': '29.8.2', 'Server.ApiVersion': '1.56', 'Server.Os': 'linux', 'Server.Arch': 'arm64'}, 'daemon changed')
        report['daemon'] = version
        v.smoke.validate_image(v.smoke.inspect(engine, 'image', v.inputs.IMAGE, v.smoke.IMAGE_FIELDS), v.inputs.IMAGE)
        folder, originals, files = stage()
        for filename in ['main__binary-arm64__Packages.xz', 'main__source__Sources.xz']:
            require((ROOT / '.tmp/cvc5-c0-sdk-metadata-2026-10-17' / filename).is_file(), 'missing host metadata: ' + filename)
        expected = v.snapshot(folder)
        report['initial_inputs'] = expected.copy()
        run_id = uuid.uuid4().hex
        for step, command in commands():
            require(time.monotonic() - start < 150, 'five-minute batch launch deadline')
            case, result = v.run_one(engine, OUTPUT, folder, run_id, step, command, expected)
            report['cases'].append(case)
            require(case['passed'], 'isolation/invocation/cleanup failure: ' + step)
            case['passed'] = False
            if step.endswith(('-filter', '-certifications')):
                case['assessment'] = v.assess(step, result, case, folder, originals, files, {})
                if step.endswith('-filter'):
                    expected[step.removesuffix('-filter') + '.self.gpg'] = identity(result['stdout'])
            elif step == 'verify':
                case['assessment'] = profile.verify(result['status'], exit_code=result['returncode'], observed_at=case['observed_at'], failure=result['failure'])
                release = (ROOT / '.tmp/cvc5-c0-sdk-metadata-2026-10-17/Release').read_bytes()
                require(result['stdout'] == release == v.release_body(files['InRelease']), 'Release plaintext mismatch')
                fields = list(v.inputs.auth.chain.stanzas(release.decode().splitlines(keepends=True)))
                require(len(fields) == 1 and fields[0]['codename'] == 'bookworm' and fields[0]['version'] == '12.0', 'unexpected release identity')
                digests = v.inputs.auth.chain.checksums(fields[0]['sha256'])
                report['metadata_chain'] = {}
                for name, indexed in [('main__binary-arm64__Packages.xz', 'main/binary-arm64/Packages.xz'), ('main__source__Sources.xz', 'main/source/Sources.xz')]:
                    raw = (ROOT / '.tmp/cvc5-c0-sdk-metadata-2026-10-17' / name).read_bytes()
                    require(identity(raw) == digests[indexed], 'authenticated metadata mismatch: ' + name)
                    report['metadata_chain'][indexed] = identity(raw)
                report['release'] = {'identity': identity(release), 'date': fields[0]['date'], 'valid_until': fields[0].get('valid-until')}
                report['positive_status'] = result['status'].decode('utf-8')
            elif step.startswith('missing-'):
                case['assessment'] = missing_role(result, step.removeprefix('missing-'))
            else:
                case['assessment'] = v.negative(result, step)
            case['passed'] = True
        require(v.snapshot(folder) == expected, 'final input drift')
        report.update(passed=True, all_new_containers_removed=all(c['cleanup']['removed'] for c in report['cases']),
                      signature_scope='three-fixed-2023-signatures-with-retained-key-material-and-explicit-identity-trust')
    except (OSError, ValueError, KeyError, TypeError) as error:
        report['failure'] = str(error)
    report['all_new_containers_removed'] = bool(report['cases']) and all(c.get('cleanup', {}).get('removed') for c in report['cases'])
    report.update(finished_utc=v.smoke.now(), elapsed_seconds=time.monotonic()-start)
    raw = (json.dumps(report, indent=2) + '\n').encode()
    (OUTPUT / 'result.json').write_bytes(raw)
    (HERE / 'historical-verification.json').write_bytes(raw)
    print(json.dumps({k: report.get(k) for k in ['passed','failure','elapsed_seconds','all_new_containers_removed']}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized', action='store_true', required=True)
    parser.parse_args()
    raise SystemExit(main())
