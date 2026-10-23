#!/usr/bin/env python3
"""Run one bounded, authorized GnuPG verification; stop if the positive case fails."""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OLD = ROOT / 'docs/records/rust-linux-input-review'
OUTPUT = ROOT / 'artifacts/cvc5-c1-signature-review-2026-10-23'
CLI_SHA = '4a728ee98f89005a90198a9be791e8fdaebbcb5e6af9721251efe0113df37759'
ARCHIVE = 'B8B80B5B623EAB6AD8775C45B7C5D7D6350947F8'
RELEASE = '4D64FEC119C2029067D6E791F8D2585B8783D481'


def identity(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    verifier = load('verifier', OLD / 'run-musl-verification.py')
    smoke = verifier.smoke
    smoke.DOCKER_SHA = CLI_SHA
    OUTPUT.mkdir(mode=0o700)
    (OUTPUT / 'verification-method.py').write_bytes(Path(__file__).read_bytes())
    report = {'format': 'radishaxiom-private-cvc5-snapshot-verification', 'version': '0.1',
              'started_utc': smoke.now(), 'method': identity(Path(__file__).read_bytes()),
              'image': verifier.inputs.IMAGE, 'cli_sha256': CLI_SHA,
              'required_primary_roles': [ARCHIVE, RELEASE], 'cases': [], 'passed': False,
              'input_acceptance': 'not-accepted', 'build_ready': False,
              'keyring_source': 'docs/records/linux-builder-source-chain/release-verification.json',
              'current_all_channel_revocation_checked': False, 'negative_cases_executed': False,
              'method_dependencies': {p.name: identity(p.read_bytes()) for p in OLD.glob('*.py')
                                      if p.name in {'run-musl-verification.py', 'run-musl-verifier-smoke.py',
                                                    'prepare-musl-verification-inputs.py', 'inspect-musl-verification-keys.py',
                                                    'inspect-musl-verification-status.py', 'retain-musl-verifier-inputs.py'}}}
    try:
        smoke.verified_inputs()
        engine = smoke.Docker(OUTPUT)
        version = json.loads(smoke.checked(engine.call(['version', '--format', smoke.template(
            ['Server.Version', 'Server.ApiVersion', 'Server.Os', 'Server.Arch'])])))
        smoke.require(version == {'Server.Version': '29.8.2', 'Server.ApiVersion': '1.56',
                                  'Server.Os': 'linux', 'Server.Arch': 'arm64'}, 'daemon changed')
        report['daemon'] = version
        smoke.validate_image(smoke.inspect(engine, 'image', verifier.inputs.IMAGE, smoke.IMAGE_FIELDS), verifier.inputs.IMAGE)
        historical = json.loads((ROOT / report['keyring_source']).read_bytes())
        ring = base64.b64decode(historical['keyring']['base64'], validate=True)
        smoke.require(identity(ring) == {'bytes': 55918, 'sha256': '506b815cbb32d9b6066b4a2aa524071e071761e7e7f68c3ac74f3061ba852017'}, 'keyring identity')
        envelope = (ROOT / '.tmp/cvc5-c0-sdk-metadata-2026-10-17/InRelease').read_bytes()
        smoke.require(identity(envelope) == {'bytes': 146972, 'sha256': '2814476b311085e250ddfdee295907bac45afb66f40dc7c1b35ab41a447c1d6c'}, 'InRelease identity')
        folder = OUTPUT / 'inputs'
        folder.mkdir(mode=0o755)
        for name, raw in {'InRelease': envelope, 'debian-archive-keyring.gpg': ring}.items():
            verifier.write_new(folder / name, raw)
        expected = verifier.snapshot(folder)
        report['inputs'] = expected
        command = verifier.gpg_keyring('debian-archive-keyring.gpg') + ['--proc-all-sigs', '--output', '-', '--decrypt', '/inputs/InRelease']
        case, result = verifier.run_one(engine, OUTPUT, folder, uuid.uuid4().hex, 'verify', command, expected)
        report['cases'].append(case)
        smoke.require(case['passed'], 'invocation/isolation/cleanup failure')
        report['gpg_exit_code'] = result['returncode']
        report['status_text'] = result['status'].decode('utf-8')
        report['stderr_text'] = result['stderr'].decode('utf-8')
        report['release_plaintext'] = identity(result['stdout'])
        report['plaintext_matches_fixed_release'] = result['stdout'] == (ROOT / '.tmp/cvc5-c0-sdk-metadata-2026-10-17/Release').read_bytes()
        valid = [line[9:].split()[1:] for line in report['status_text'].splitlines() if line.startswith('[GNUPG:] VALIDSIG ')]
        report['observed_validsig_primaries'] = [f[-1] for f in valid]
        report['required_roles_present'] = {ARCHIVE, RELEASE} <= set(report['observed_validsig_primaries'])
        smoke.require(result['returncode'] == 0, 'positive verification returned nonzero; stop before negatives')
        smoke.require(report['required_roles_present'], 'required bookworm roles missing; no automatic policy substitution')
        # This batch is a first-failure diagnostic, not an acceptance runner.
        report['passed'] = True
    except (OSError, ValueError, KeyError, TypeError) as error:
        report['failure'] = str(error)
    report['finished_utc'] = smoke.now()
    raw = (json.dumps(report, indent=2) + '\n').encode()
    (OUTPUT / 'result.json').write_bytes(raw)
    (HERE / 'snapshot-verification.json').write_bytes(raw)
    print(json.dumps({k: report[k] for k in ['passed', 'failure', 'negative_cases_executed', 'finished_utc'] if k in report}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized', action='store_true', required=True)
    parser.parse_args()
    raise SystemExit(main())
