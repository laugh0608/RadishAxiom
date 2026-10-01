#!/usr/bin/env python3
"""Replay the fixed second GMP failure from retained bytes; never runs Docker/GnuPG."""
import argparse
from datetime import datetime
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('collector', HERE / 'collect-gmp-verification-v2.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
run = collector.run
require, identity, read = collector.require, collector.identity, collector.read
BUNDLE_SHA = '495ce3fb361747d09626f1eb0c55f0386a4a0e08f53a6901ecdd08d410e794a7'
RESULT_SHA = '1e3a403d764bd5390d31d1fb8d1370de62c73c4f14c047b2daf7f8a28d74c92a'
FAILURE = 'fixed certification status mismatch'
COLON_FAILURE = 'expected explicit expired key and exact expiry'


def rejected(call, expected):
    try:
        call()
    except ValueError as error:
        require(str(error) == expected, 'different failure: ' + str(error))
    else:
        raise ValueError('historical profile no longer rejects this response')


def diagnose(invocation, original, filtered, observed):
    expired = f'[GNUPG:] KEYEXPIRED {run.profile.EXPIRES["pub"]}\n'.encode()
    considered = f'[GNUPG:] KEY_CONSIDERED {run.profile.PRIMARY} 0\n'.encode()
    require(invocation['status'] == expired + considered + expired * 2, 'fixed status sequence drift')
    require(invocation['failure'] is None and type(invocation['returncode']) is int and
            invocation['returncode'] == 0, 'incomplete certification invocation')
    rejected(lambda: run.assess_output('certifications', invocation, observed, original, filtered), FAILURE)
    # Exercise the unchanged colon parser separately. This is a second rejection,
    # not permission to discard status lines or normalize a tool expiry field.
    rejected(lambda: run.profile.certifications(invocation['stdout'], original, filtered, observed), COLON_FAILURE)
    rows = [line.split(':') for line in run.profile.keys.text_lines(invocation['stdout'])]
    sub = [row for row in rows if row[0] == 'sub']
    require(len(sub) == 1 and sub[0][1] == 'e' and sub[0][4] == run.profile.SUBKEY[-16:] and
            sub[0][6] == str(run.profile.EXPIRES['pub']), 'fixed observed subkey expiry drift')
    return {'profile_failure_reproduced': FAILURE, 'separate_colon_failure_reproduced': COLON_FAILURE,
            'key_expiry_status_records': 3, 'listed_subkey_expiry': int(sub[0][6]),
            'binding_declared_subkey_expiry': run.profile.EXPIRES['sub'],
            'expiry_difference_seconds': run.profile.EXPIRES['sub'] - int(sub[0][6]),
            'tool_sig_bang_records_observed': sum(row[:2] == ['sig', '!'] for row in rows),
            'complete_certification_assessment_passed': False, 'detached_signature_checked': False,
            'expiry_listing_semantics': 'requires-separate-tool-semantics-review',
            'historical_validity': 'not-established', 'source_acceptance': 'not-assessed'}


def inspect(path):
    raw = read(path, collector.BUNDLE_LIMIT)
    require(identity(raw)['sha256'] == BUNDLE_SHA, 'fixed bundle drift')
    bundle = json.loads(raw)
    require(collector.replay(bundle) == bundle['replay'] and bundle['replay']['replayed_success'] is False,
            'failed bundle replay drift')
    files = collector.unpack(bundle['files'])
    require(identity(files['result.json'])['sha256'] == RESULT_SHA, 'fixed result drift')
    result = json.loads(files['result.json'])
    require(result['passed'] is False and result['failure'] == FAILURE and
            [c['step'] for c in result['cases']] == ['filter', 'certifications'] and
            result['source_acceptance'] == 'not-assessed' and result['runtime_qualification'] is False and
            result['historical_validity'] == 'not-established' and
            result['current_all_channel_revocation_checked'] is False, 'failure or trust boundary drift')
    methods = collector.unpack(bundle['methods'])
    require({name: identity(data) for name, data in methods.items()} == result['methods'] == run.methods(),
            'execution method drift')
    require(result['image_id'] == run.IMAGE and result['rootfs']['sha256'] == run.smoke.TAR_SHA and
            result['docker_cli'] == {'path': run.smoke.DOCKER, 'sha256': run.smoke.DOCKER_SHA} and
            result['docker_socket'] == run.smoke.SOCKET, 'tool binding drift')
    prepared, staged = run.inputs.prepare()
    require(result['prepared_inputs'] == prepared, 'retained source drift')
    filtered = files['inputs/gmp.self.gpg']
    expected = dict(prepared['inputs'])
    require({name: data for name, data in files.items() if name.startswith('inputs/')} ==
            {'inputs/' + name: data for name, data in {**staged, 'gmp.self.gpg': filtered}.items()},
            'staged input drift')
    directory = Path(bundle['original_directory'])
    require(directory == run.OUTPUT, 'original output path drift')
    records = [f'{n:03d}.json' for n in range(1, 18)]
    expected_files = set(records) | {f'{n:03d}.{channel}' for n in range(1, 18)
                                   for channel in ('stdout', 'stderr')}
    expected_files |= {'inputs/' + name for name in staged} | {
        'inputs/gmp.self.gpg', 'filter.status', 'certifications.status', 'result.json'}
    require(set(files) == expected_files, 'partial artifact set drift')
    responses = []
    for name in records:
        row = json.loads(files[name])
        streams = {channel: files[name[:-5] + '.' + channel] for channel in ('stdout', 'stderr')}
        require(all(identity(data) == row[channel] and len(data) <= row['bytes_limit']
                    for channel, data in streams.items()), 'command stream drift')
        responses.append({**row, **streams})
    engine = collector.Replay(responses, directory)
    run.smoke.preflight(engine)
    run.smoke.validate_image(run.smoke.inspect(engine, 'image', run.IMAGE, run.smoke.IMAGE_FIELDS), run.IMAGE)
    summaries = []
    for case, (step, command) in zip(result['cases'], run.commands()[:2]):
        name, cid = case['name'], case['container_id']
        require(name == 'rax-gmp-verify-' + result['run_id'] + '-' + step and case['command'] == command and
                case['passed'] is (step == 'filter') and case['status_file'] == step + '.status' and
                case['expected_inputs'] == case['inputs'] == expected, 'case binding drift')
        folder, status_path = directory / 'inputs', directory / case['status_file']
        created = engine.call(run.base.create_args(name, result['run_id'], command, folder, status_path))
        require(run.smoke.checked(created) == (cid + '\n').encode(), 'created container identity drift')
        before = run.smoke.inspect(engine, 'container', cid, run.smoke.CONTAINER_FIELDS)
        run.base.validate_container(before, name, result['run_id'], command, folder, status_path)
        require(before['Id'] == cid and before['State.Status'] == 'created' and before['State.Running'] is False,
                'unexpected initial container state')
        require(case['start_command_number'] == engine.sequence + 1, 'start sequence drift')
        invocation = engine.call(['container', 'start', '--attach', cid], seconds=30, limit=1024**2)
        observed = case['observed_at']
        require(type(observed) is int and datetime.fromisoformat(invocation['started_at']).timestamp() - 2 <= observed <=
                datetime.fromisoformat(invocation['finished_at']).timestamp() + 2, 'observation time drift')
        require(run.smoke.ok(invocation) and all(invocation[k] == case['invocation'][k]
                for k in ('returncode', 'failure', 'seconds')), 'invocation drift')
        after = run.smoke.inspect(engine, 'container', cid, run.smoke.CONTAINER_FIELDS)
        run.base.validate_container(after, name, result['run_id'], command, folder, status_path)
        run.base.exited(after, invocation['returncode'])
        require(after['Id'] == cid and {k: v for k, v in after.items() if k.startswith('State.')} == case['final_state'],
                'final state drift')
        cleanup = run.smoke.cleanup(engine, cid, run.IMAGE, name, result['run_id'])
        require(cleanup == case['cleanup'] and cleanup['removed'] is True and
                case['status_after_confirmed_cleanup'] is True, 'cleanup drift')
        status = files[case['status_file']]
        require(identity(status) == case['status'] and all(identity(invocation[k]) == case[k]
                for k in ('stdout', 'stderr')), 'case stream drift')
        invocation = {**invocation, 'status': status}
        if step == 'filter':
            assessment = run.assess_output(step, invocation, observed, staged['gmp.strong.gpg'])
            require(case['assessment'] == assessment and filtered == invocation['stdout'], 'filter assessment drift')
            expected['gmp.self.gpg'] = identity(filtered)
        else:
            require('assessment' not in case, 'failed case gained assessment')
            assessment = diagnose(invocation, staged['gmp.strong.gpg'], filtered, observed)
        summaries.append({'step': step, 'gpg_returncode': invocation['returncode'], 'cleanup': cleanup,
                          'assessment': assessment, 'status_text': status.decode(),
                          'stdout': identity(invocation['stdout']), 'stderr_text': invocation['stderr'].decode()})
    require(engine.sequence == 17, 'unconsumed commands')
    return {'kind': 'diagnostic-gmp-certification-attempt-review-v1', 'bundle': identity(raw),
            'result': identity(files['result.json']), 'run_id': result['run_id'],
            'started_at': result['started_at'], 'finished_at': result['finished_at'],
            'command_logs_replayed': engine.sequence, 'containers_started': 2, 'cases': summaries,
            'not_executed': ['verify', 'tampered-body', 'wrong-primary', 'missing-primary'],
            'source_acceptance': 'not-assessed', 'historical_validity': 'not-established',
            'runtime_qualification': False, 'new_cryptography_executed_by_review': False,
            'review_method': identity(read(Path(__file__).resolve()))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path,
                        default=run.ROOT / '.tmp/gmp-verification-execution-20260925-attempt2.json')
    args = parser.parse_args()
    print(json.dumps(inspect(args.bundle.resolve()), sort_keys=True, indent=2))
