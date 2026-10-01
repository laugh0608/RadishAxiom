#!/usr/bin/env python3
"""GMP auxiliary-expiry revision: default plan, fresh execution only after explicit authorization."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('gmp_v1', HERE / 'run-gmp-verification.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
base, inputs, profile = prior.base, prior.inputs, prior.profile
smoke, require, identity = prior.smoke, prior.require, prior.identity
IMAGE, BATCH_SECONDS = prior.IMAGE, prior.BATCH_SECONDS
OUTPUT = ROOT / '.tmp/gmp-verification-20260925-attempt2'
PROFILE = 'gmp-auxiliary-expiry-v2'
commands, run_one, retain_methods = prior.commands, prior.run_one, prior.retain_methods


def auxiliary_status(step, raw, original, observed_at):
    # KEYEXPIRED has no fingerprint. Bind it to the one fixed primary in the actual
    # material, then require the paired export/colon assessment before reporting success.
    profile.inventory(original)
    require(type(observed_at) is int and observed_at > max(profile.EXPIRES.values()),
            'expected actual post-expiry observation')
    require(isinstance(raw, bytes) and len(raw) <= 256, 'auxiliary status bound')
    expired = f'[GNUPG:] KEYEXPIRED {profile.EXPIRES["pub"]}\n'.encode()
    considered = f'[GNUPG:] KEY_CONSIDERED {profile.PRIMARY} 0\n'.encode()
    if step == 'filter':
        imported = b'[GNUPG:] IMPORT_RES 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n'
        require(raw == expired + imported, 'fixed expired-key import status mismatch')
    elif step == 'certifications':
        require(raw in (considered, expired + considered), 'fixed certification status mismatch')
    else:
        raise ValueError('not an auxiliary step')
    return {'primary': profile.PRIMARY, 'primary_expiry': profile.EXPIRES['pub'],
            'expiry_reported_in_status': raw.startswith(expired),
            'status_records': len(raw.splitlines()), 'source_acceptance': 'not-assessed'}


def assess_output(step, result, observed_at, original, filtered=None):
    if step not in {'filter', 'certifications'}:
        return profile.verify(result, observed_at, step)
    require(result['failure'] is None and type(result['returncode']) is int and result['returncode'] == 0,
            'incomplete or failed auxiliary invocation')
    auxiliary = auxiliary_status(step, result['status'], original, observed_at)
    if step == 'filter':
        profile.filtered_material(original, result['stdout'])
        return {'result': 'all-selected-strong-self-material-retained', 'current_key_state': 'expired',
                'self_certifications_checked': False, 'historical_validity': 'not-established',
                'source_acceptance': 'not-assessed', 'auxiliary_status': auxiliary}
    checked = profile.certifications(result['stdout'], original, filtered, observed_at)
    return {**checked, 'auxiliary_status': auxiliary}


def assess(step, result, case, folder, files):
    filtered = inputs.retention.read_regular(folder / 'gmp.self.gpg', profile.keys.LIMIT) if step == 'certifications' else None
    checked = assess_output(step, result, case['observed_at'], files['gmp.strong.gpg'], filtered)
    if step == 'filter':
        inputs.write_new(folder / 'gmp.self.gpg', result['stdout'])
    return checked


def methods():
    # Retain the exact historical lifecycle and its transitive dependencies, plus this revision.
    return {**prior.methods(), str(Path(__file__).resolve().relative_to(ROOT)):
            identity(inputs.retention.read_regular(Path(__file__).resolve()))}


def execute(output):
    base.safe_path(output)
    require(output.parent.is_dir() and output.parent == ROOT / '.tmp', 'output must be new and directly under .tmp')
    output.mkdir(mode=0o700)
    report = {'kind': 'diagnostic-gmp-verification-run-v2', 'started_at': smoke.now(), 'run_id': uuid.uuid4().hex,
              'assessment_profile': PROFILE, 'image_id': IMAGE, 'cases': [], 'passed': False, 'source_acceptance': 'not-assessed',
              'runtime_qualification': False, 'key_material_as_of': '2026-09-25',
              'current_all_channel_revocation_checked': False, 'historical_validity': 'not-established',
              'current_key_state': 'expected-expired; awaiting-tool', 'methods': methods(),
              'docker_cli': {'path': smoke.DOCKER, 'sha256': smoke.DOCKER_SHA}, 'docker_socket': smoke.SOCKET}
    started = time.monotonic()
    try:
        retain_methods(output, report['methods'])
        prepared, files = inputs.prepare()
        tar, _ = smoke.verified_inputs()
        report.update(prepared_inputs=prepared, rootfs=identity(tar),
                      python={'version': sys.version, 'executable': sys.executable,
                              **identity(Path(sys.executable).read_bytes())})
        folder = inputs.stage(output, files)
        expected = inputs.snapshot(folder)
        engine = smoke.Docker(output)
        smoke.preflight(engine)
        smoke.validate_image(smoke.inspect(engine, 'image', IMAGE, smoke.IMAGE_FIELDS), IMAGE)
        for step, command in commands():
            require(time.monotonic() - started < BATCH_SECONDS - 150, 'batch launch deadline')
            case, result = run_one(engine, output, folder, report['run_id'], step, command, expected)
            report['cases'].append(case)
            require(case['passed'], 'execution or cleanup failed: ' + step)
            case['passed'] = False
            case['assessment'] = assess(step, result, case, folder, files)
            if step == 'filter':
                expected['gmp.self.gpg'] = identity(result['stdout'])
            case['passed'] = True
        after, after_files = inputs.prepare()
        require(after == prepared and after_files == files and methods() == report['methods'],
                'retained inputs or methods changed during execution')
        report.update(passed=True, source_bytes_rechecked=True, current_key_state='expired',
                      cryptography='performed-by-fixed-GnuPG; host-and-tools-remain-trusted')
    except (OSError, ValueError, KeyError, TypeError) as error:
        report['failure'] = str(error)
    finally:
        report['finished_at'] = smoke.now()
        with (output / 'result.json').open('x') as stream:
            json.dump(report, stream, sort_keys=True, indent=2)
            stream.write('\n')
    return report


def plan(output=OUTPUT):
    return {'kind': 'diagnostic-gmp-verification-plan-v2', 'commands': dict(commands()),
            'assessment_profile': PROFILE, 'image_id': IMAGE, 'output': str(output), 'docker_socket': smoke.SOCKET,
            'run_seconds_each': 30, 'control_seconds_each': 10, 'stream_and_status_bytes_each': profile.keys.LIMIT,
            'input_bytes_each': inputs.INPUT_LIMIT, 'input_bytes_total': inputs.TOTAL_LIMIT,
            'batch_seconds_budget': BATCH_SECONDS, 'fresh_tmpfs_each_invocation': base.TMPFS,
            'actions_executed': False, 'source_acceptance': 'not-assessed', 'historical_validity': 'not-established',
            'current_key_state': 'expected-expired; awaiting-tool'}


def review_retained_filter():
    # Consume the fixed failed attempt offline; never overwrite its result or execute saved source.
    review = prior.load('inspect-gmp-filter-attempt.py')
    path = ROOT / '.tmp/gmp-verification-execution-20260925.json'
    historical = review.inspect(path)
    bundle = json.loads(review.read(path, review.collector.BUNDLE_LIMIT))
    files = review.collector.unpack(bundle['files'])
    result = json.loads(files['result.json'])
    case, = result['cases']
    number = case['start_command_number']
    invocation = {**case['invocation'], 'status': files['filter.status'],
                  'stdout': files[f'{number:03d}.stdout'], 'stderr': files[f'{number:03d}.stderr']}
    candidate = assess_output('filter', invocation, case['observed_at'], files['inputs/gmp.strong.gpg'])
    return {'kind': 'diagnostic-gmp-auxiliary-expiry-review-v2', 'assessment_profile': PROFILE,
            'historical_bundle': historical['bundle'], 'historical_result': historical['result'],
            'historical_failure': historical['diagnosis']['original_profile_failure_reproduced'],
            'candidate_filter_assessment': candidate, 'methods': methods(),
            'historical_reviewer': identity(inputs.retention.read_regular(Path(review.__file__).resolve())),
            'actions_executed': False, 'new_cryptography_executed': False,
            'self_certifications_checked': False, 'detached_signature_checked': False,
            'source_acceptance': 'not-assessed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--execute-authorized', action='store_true', help='records current approval, does not grant it')
    mode.add_argument('--review-retained-filter', action='store_true', help='offline comparison only; no execution')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = (execute(args.output) if args.execute_authorized else review_retained_filter()
              if args.review_retained_filter else plan(args.output))
    print(json.dumps(result, sort_keys=True, indent=2))
    raise SystemExit(0 if not args.execute_authorized or result['passed'] else 1)
