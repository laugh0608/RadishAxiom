#!/usr/bin/env python3
"""GMP v3 orchestration: fixed joint certification assessment; execution requires fresh authorization."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time
from types import ModuleType
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('gmp_certification_v3', HERE / 'inspect-gmp-certification-v3.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
prior = candidate.historical.run
base, inputs, profile = prior.base, prior.inputs, prior.profile
smoke, require, identity = prior.smoke, prior.require, prior.identity
IMAGE, BATCH_SECONDS = prior.IMAGE, prior.BATCH_SECONDS
OUTPUT = ROOT / '.tmp/gmp-verification-20260929-attempt3'
PROFILE = 'gmp-certification-expiry-v3'
commands, run_one, retain_methods = prior.commands, prior.run_one, prior.retain_methods


def assess_output(step, result, observed_at, original, filtered=None):
    if step == 'certifications':
        return candidate.assess(result, original, filtered, observed_at)
    # Filtering and the four detached-signature cases keep their reviewed v2 rules.
    return prior.assess_output(step, result, observed_at, original, filtered)


def source_basis():
    raw = inputs.retention.read_regular(HERE / 'gmp-tool-source-2026-09-29.json.gz')
    binding = identity(raw)
    require(binding['sha256'] == candidate.BASIS_SHA, 'reviewed tool source inventory drift')
    return binding


def assess(step, result, case, folder, files):
    filtered = inputs.retention.read_regular(folder / 'gmp.self.gpg', profile.keys.LIMIT) if step == 'certifications' else None
    checked = assess_output(step, result, case['observed_at'], files['gmp.strong.gpg'], filtered)
    if step == 'filter':
        inputs.write_new(folder / 'gmp.self.gpg', result['stdout'])
    return checked


def methods():
    # Historical methods are immutable. Retain the added assessor and all its
    # imported local dependencies, plus the reviewed basis and v3 export method.
    source_basis()
    paths = {Path(__file__).resolve(), HERE / 'gmp-tool-source-2026-09-29.json.gz',
             HERE / 'collect-gmp-verification-v3.py'}
    visited, pending = set(), [candidate]
    while pending:
        module = pending.pop()
        if id(module) in visited:
            continue
        visited.add(id(module))
        path = Path(module.__file__).resolve() if getattr(module, '__file__', None) else None
        if path is None or not path.is_relative_to(ROOT):
            continue
        paths.add(path)
        pending.extend(value for value in vars(module).values() if isinstance(value, ModuleType))
    return {**prior.methods(), **{str(path.relative_to(ROOT)): identity(inputs.retention.read_regular(path))
                                 for path in sorted(paths)}}


def execute(output):
    base.safe_path(output)
    require(output.parent.is_dir() and output.parent == ROOT / '.tmp', 'output must be new and directly under .tmp')
    bindings, basis = methods(), source_basis()
    output.mkdir(mode=0o700)
    report = {'kind': 'diagnostic-gmp-verification-run-v3', 'started_at': smoke.now(), 'run_id': uuid.uuid4().hex,
              'assessment_profile': PROFILE, 'certification_assessment_profile': candidate.PROFILE,
              'tool_source_inventory': basis, 'image_id': IMAGE, 'cases': [], 'passed': False, 'source_acceptance': 'not-assessed',
              'runtime_qualification': False, 'key_material_as_of': '2026-09-25',
              'current_all_channel_revocation_checked': False, 'historical_validity': 'not-established',
              'current_key_state': 'expected-expired; awaiting-tool', 'methods': bindings,
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
    return {'kind': 'diagnostic-gmp-verification-plan-v3', 'commands': dict(commands()),
            'assessment_profile': PROFILE, 'certification_assessment_profile': candidate.PROFILE,
            'tool_source_inventory': source_basis(), 'image_id': IMAGE, 'output': str(output), 'docker_socket': smoke.SOCKET,
            'run_seconds_each': 30, 'control_seconds_each': 10, 'stream_and_status_bytes_each': profile.keys.LIMIT,
            'input_bytes_each': inputs.INPUT_LIMIT, 'input_bytes_total': inputs.TOTAL_LIMIT,
            'batch_seconds_budget': BATCH_SECONDS, 'fresh_tmpfs_each_invocation': base.TMPFS,
            'actions_executed': False, 'source_acceptance': 'not-assessed', 'historical_validity': 'not-established',
            'current_key_state': 'expected-expired; awaiting-tool'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized', action='store_true', help='records current approval, does not grant it')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = execute(args.output) if args.execute_authorized else plan(args.output)
    print(json.dumps(result, sort_keys=True, indent=2))
    raise SystemExit(0 if not args.execute_authorized or result['passed'] else 1)
