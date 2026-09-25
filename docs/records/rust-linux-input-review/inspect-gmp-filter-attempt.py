#!/usr/bin/env python3
"""Replay the retained first GMP filter failure offline, without relaxing the execution profile."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('collector', HERE / 'collect-gmp-verification-execution.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
run = collector.run
require, identity, read = collector.require, collector.identity, collector.read
BUNDLE_SHA = '480c6889fd21a595a0f5981c700c86439a4d71c50d0e71a39d3ea4c4de4cf336'
RESULT_SHA = 'c0ccd560880bccaaa7a565677a4ec11ef6555c1061fcbce9d33ac065b5c6d158'
FAILURE = 'unexpected auxiliary status: KEYEXPIRED'


def filter_output(status, original, exported):
    expected = (f'[GNUPG:] KEYEXPIRED {run.profile.EXPIRES["pub"]}\n'
                '[GNUPG:] IMPORT_RES 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n').encode()
    require(status == expected, 'fixed filter status drift')
    try:
        run.base.auxiliary_status(status, run.base.IMPORT_ALLOWED)
    except ValueError as error:
        require(str(error) == FAILURE, 'different original profile failure')
    else:
        raise ValueError('original profile no longer rejects this status')
    run.profile.filtered_material(original, exported)
    return {'original_profile_failure_reproduced': FAILURE, 'public_and_self_signature_bodies_equal': True,
            'packet_encoding_equal': original == exported, 'key_expiry_report_preserved': run.profile.EXPIRES['pub'],
            'self_certifications_checked': False, 'detached_signature_checked': False,
            'source_acceptance': 'not-assessed'}


def inspect(path):
    raw = read(path, collector.BUNDLE_LIMIT)
    require(identity(raw)['sha256'] == BUNDLE_SHA, 'fixed bundle drift')
    bundle = json.loads(raw)
    require(collector.replay(bundle) == bundle['replay'] and bundle['replay']['replayed_success'] is False,
            'failed bundle no longer matches')
    files = collector.unpack(bundle['files'])
    result_raw = files['result.json']
    require(identity(result_raw)['sha256'] == RESULT_SHA, 'fixed result drift')
    result = json.loads(result_raw)
    require(result['passed'] is False and result['failure'] == FAILURE and len(result['cases']) == 1 and
            result['source_acceptance'] == 'not-assessed' and result['runtime_qualification'] is False,
            'failure or trust boundary drift')
    methods = collector.unpack(bundle['methods'])
    require({name: identity(data) for name, data in methods.items()} == result['methods'] == run.methods(),
            'execution method drift')
    prepared, staged = run.inputs.prepare()
    require(result['prepared_inputs'] == prepared, 'retained source drift')
    require({name: data for name, data in files.items() if name.startswith('inputs/')} ==
            {'inputs/' + name: data for name, data in staged.items()}, 'staged source drift')
    directory = Path(bundle['original_directory'])
    require(directory == run.OUTPUT, 'original output path drift')
    records = [f'{n:03d}.json' for n in range(1, 11)]
    expected_files = set(records) | {f'{n:03d}.{channel}' for n in range(1, 11) for channel in ('stdout', 'stderr')}
    expected_files |= {'inputs/' + name for name in staged} | {'filter.status', 'result.json'}
    require(set(files) == expected_files, 'partial command/artifact set drift')
    responses = []
    for name in records:
        record = json.loads(files[name])
        streams = {channel: files[name[:-5] + '.' + channel] for channel in ('stdout', 'stderr')}
        require(all(identity(data) == record[channel] and len(data) <= record['bytes_limit']
                    for channel, data in streams.items()), 'recorded stream drift')
        responses.append({**record, **streams})
    engine = collector.Replay(responses, directory)
    run.smoke.preflight(engine)
    run.smoke.validate_image(run.smoke.inspect(engine, 'image', run.IMAGE, run.smoke.IMAGE_FIELDS), run.IMAGE)
    case, = result['cases']
    name, cid = case['name'], case['container_id']
    command = dict(run.commands())['filter']
    require(case['step'] == 'filter' and case['passed'] is False and 'assessment' not in case and
            name == 'rax-gmp-verify-' + result['run_id'] + '-filter' and case['command'] == command and
            case['status_file'] == 'filter.status' and case['expected_inputs'] == case['inputs'] == prepared['inputs'],
            'filter case scope drift')
    folder, status_path = directory / 'inputs', directory / 'filter.status'
    created = engine.call(run.base.create_args(name, result['run_id'], command, folder, status_path))
    require(run.smoke.checked(created) == (cid + '\n').encode(), 'created container identity drift')
    before = run.smoke.inspect(engine, 'container', cid, run.smoke.CONTAINER_FIELDS)
    run.base.validate_container(before, name, result['run_id'], command, folder, status_path)
    require(before['Id'] == cid and before['State.Status'] == 'created' and before['State.Running'] is False,
            'unexpected initial container state')
    require(case['start_command_number'] == engine.sequence + 1, 'start sequence drift')
    invocation = engine.call(['container', 'start', '--attach', cid], seconds=30, limit=1024**2)
    require(run.smoke.ok(invocation) and all(invocation[k] == case['invocation'][k]
            for k in ('returncode', 'failure', 'seconds')), 'filter invocation drift')
    after = run.smoke.inspect(engine, 'container', cid, run.smoke.CONTAINER_FIELDS)
    run.base.validate_container(after, name, result['run_id'], command, folder, status_path)
    run.base.exited(after, invocation['returncode'])
    require(after['Id'] == cid and {k: v for k, v in after.items() if k.startswith('State.')} == case['final_state'],
            'final container state drift')
    cleanup = run.smoke.cleanup(engine, cid, run.IMAGE, name, result['run_id'])
    require(cleanup == case['cleanup'] and cleanup['removed'] is True and
            case['status_after_confirmed_cleanup'] is True and engine.sequence == 10, 'cleanup or log count drift')
    status = files['filter.status']
    require(identity(status) == case['status'] and all(identity(invocation[k]) == case[k]
            for k in ('stdout', 'stderr')), 'case stream identity drift')
    diagnosis = filter_output(status, staged['gmp.strong.gpg'], invocation['stdout'])
    return {'kind': 'diagnostic-gmp-filter-attempt-review-v1', 'bundle': identity(raw), 'result': identity(result_raw),
            'run_id': result['run_id'], 'started_at': result['started_at'], 'finished_at': result['finished_at'],
            'command_logs_replayed': engine.sequence, 'containers_started': 1, 'cleanup': cleanup,
            'gpg_returncode': invocation['returncode'], 'stdout': identity(invocation['stdout']),
            'status_text': status.decode(), 'stderr_text': invocation['stderr'].decode(), 'diagnosis': diagnosis,
            'not_executed': ['certifications', 'verify', 'tampered-body', 'wrong-primary', 'missing-primary'],
            'source_acceptance': 'not-assessed', 'runtime_qualification': False,
            'review_method': identity(read(Path(__file__).resolve()))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=run.ROOT / '.tmp/gmp-verification-execution-20260925.json')
    args = parser.parse_args()
    print(json.dumps(inspect(args.bundle.resolve()), sort_keys=True, indent=2))
