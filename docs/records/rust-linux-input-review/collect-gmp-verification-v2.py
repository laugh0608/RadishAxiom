#!/usr/bin/env python3
"""Export and replay the GMP v2 run from local logs; never calls Docker or GnuPG."""
import argparse
import base64
from datetime import datetime
import re
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CACHE = ROOT / '.tmp/gmp-verification-20260925-attempt2'
BUNDLE_LIMIT = 128 * 1024**2
TOTAL_LIMIT = 64 * 1024**2
FILE_LIMIT = 16 * 1024**2
spec = importlib.util.spec_from_file_location('gmp_run', HERE / 'run-gmp-verification-v2.py')
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
read, identity, require = run.inputs.retention.read_regular, run.identity, run.require


def encoded(raw):
    try:
        return {'encoding': 'utf-8', 'data': raw.decode('utf-8', errors='strict')}
    except UnicodeDecodeError:
        return {'encoding': 'base64', 'data': base64.b64encode(raw).decode('ascii')}


def command_logs(files):
    paths = sorted(name for name in files if re.fullmatch(r'[0-9]{3}\.json', name))
    require(paths == [f'{i:03d}.json' for i in range(1, 46)], 'command log set drift')
    responses = []
    for name in paths:
        record = json.loads(files[name])
        streams = {}
        for channel in ('stdout', 'stderr'):
            data = files[name[:-5] + '.' + channel]
            require(identity(data) == record[channel] and len(data) <= record['bytes_limit'], 'command stream drift')
            streams[channel] = data
        responses.append({**record, **streams})
    return responses


class Replay:
    """Consume only retained responses for exact requested commands and capture limits."""
    def __init__(self, responses, directory=CACHE):
        self.responses, self.sequence, self.directory = responses, 0, directory

    def call(self, args, *, seconds=10, limit=262144):
        require(self.sequence < len(self.responses), 'replay exhausted')
        row = self.responses[self.sequence]
        prefix = [run.smoke.DOCKER, '--host', 'unix://' + run.smoke.SOCKET,
                  '--config', str(self.directory / 'docker-config')]
        require(row['argv'] == prefix + args and row['seconds_limit'] == seconds and row['bytes_limit'] == limit,
                'command or capture limit binding drift')
        self.sequence += 1
        return row


def replay(bundle):
    require(bundle['kind'] == 'diagnostic-gmp-verification-bundle-v2', 'bundle version drift')
    collector_source = unpack({'collector.py': bundle['collector_method']})['collector.py']
    require(collector_source == read(Path(__file__).resolve()), 'collector method drift')
    files = unpack(bundle['files'])
    result = json.loads(files['result.json'])
    require(result['kind'] == 'diagnostic-gmp-verification-run-v2' and
            result['assessment_profile'] == run.PROFILE, 'run profile version drift')
    if result['passed'] is not True:
        return {'result': 'failed-run-retained', 'replayed_success': False,
                'source_acceptance': 'not-assessed', 'failure': result.get('failure')}
    require(result['kind'] == 'diagnostic-gmp-verification-run-v2' and
            re.fullmatch('[0-9a-f]{32}', result['run_id']) and result['source_acceptance'] == 'not-assessed' and
            result['runtime_qualification'] is False and result['historical_validity'] == 'not-established' and
            result['current_all_channel_revocation_checked'] is False and result['current_key_state'] == 'expired',
            'run identity or trust boundary drift')
    require(result['image_id'] == run.IMAGE and result['rootfs']['sha256'] == run.smoke.TAR_SHA and
            result['docker_cli'] == {'path': run.smoke.DOCKER, 'sha256': run.smoke.DOCKER_SHA} and
            result['docker_socket'] == run.smoke.SOCKET, 'tool identity drift')
    methods = unpack(bundle['methods'])
    require({name: identity(raw) for name, raw in methods.items()} == result['methods'] == run.methods(),
            'execution method drift; inspect retained source rather than executing it')
    prepared = result['prepared_inputs']
    require(prepared['store']['manifest']['sha256'] == run.inputs.STORE[2] and
            prepared['source_acceptance'] == 'not-assessed', 'prepared manifest or trust drift')
    directory = Path(bundle['original_directory'])
    run.base.safe_path(directory)
    folder = directory / 'inputs'
    staged = {name[7:]: raw for name, raw in files.items() if name.startswith('inputs/')}
    final_inputs = {name: identity(raw) for name, raw in staged.items()}
    expected = dict(prepared['inputs'])
    require(len(staged) == 9 and all(len(raw) <= run.inputs.INPUT_LIMIT for raw in staged.values()) and
            sum(map(len, staged.values())) <= run.inputs.TOTAL_LIMIT, 'staged input bound')
    require(all(final_inputs.get(name) == row for name, row in expected.items()), 'staged input identity drift')
    run.inputs.source.archive_binding(staged['gmp.tar.xz'])
    require(run.profile.material.armor(staged['gmp.original.asc']) == staged['gmp.raw.gpg'], 'armor/raw mismatch')
    strong, projection = run.profile.project(staged['gmp.raw.gpg'])
    require(strong == staged['gmp.strong.gpg'] and projection == prepared['projection'], 'projection drift')
    responses = command_logs(files)
    engine = Replay(responses, directory)
    run.smoke.preflight(engine)
    run.smoke.validate_image(run.smoke.inspect(engine, 'image', run.IMAGE, run.smoke.IMAGE_FIELDS), run.IMAGE)
    steps = run.commands()
    require([c['step'] for c in result['cases']] == [name for name, _ in steps], 'case order drift')
    statuses, assessments = {}, {}
    for case, (step, command) in zip(result['cases'], steps):
        name, run_id, cid = case['name'], result['run_id'], case['container_id']
        require(name == 'rax-gmp-verify-' + run_id + '-' + step and case['command'] == command and
                case['passed'] is True and case['status_file'] == step + '.status' and
                case['expected_inputs'] == case['inputs'] == expected, 'case binding drift')
        status_path = directory / case['status_file']
        created = engine.call(run.base.create_args(name, run_id, command, folder, status_path))
        require(run.smoke.checked(created) == (cid + '\n').encode(), 'created container ID mismatch')
        before = run.smoke.inspect(engine, 'container', cid, run.smoke.CONTAINER_FIELDS)
        run.base.validate_container(before, name, run_id, command, folder, status_path)
        require(before['Id'] == cid and before['State.Status'] == 'created' and before['State.Running'] is False,
                'container already started')
        require(case['start_command_number'] == engine.sequence + 1, 'start command number drift')
        invocation = engine.call(['container', 'start', '--attach', cid], seconds=30, limit=1024**2)
        observed = case['observed_at']
        require(type(observed) is int and datetime.fromisoformat(invocation['started_at']).timestamp() - 2 <= observed <=
                datetime.fromisoformat(invocation['finished_at']).timestamp() + 2, 'observation/log time drift')
        require(all(invocation[k] == case['invocation'][k] for k in ('returncode', 'failure', 'seconds')),
                'invocation result drift')
        after = run.smoke.inspect(engine, 'container', cid, run.smoke.CONTAINER_FIELDS)
        require(after['Id'] == cid, 'final container ID drift')
        run.base.validate_container(after, name, run_id, command, folder, status_path)
        run.base.exited(after, invocation['returncode'])
        require({k: v for k, v in after.items() if k.startswith('State.')} == case['final_state'], 'final state drift')
        cleanup = run.smoke.cleanup(engine, cid, run.IMAGE, name, run_id)
        require(cleanup == case['cleanup'] and cleanup['removed'] is True and
                case['status_after_confirmed_cleanup'] is True, 'cleanup mismatch')
        status = files[case['status_file']]
        require(identity(status) == case['status'] and all(identity(invocation[k]) == case[k]
                for k in ('stdout', 'stderr')), 'case stream mismatch')
        invocation = {**invocation, 'status': status}
        assessed = run.assess_output(step, invocation, case['observed_at'], staged['gmp.strong.gpg'],
                                     staged.get('gmp.self.gpg'))
        if step == 'filter':
            require(staged['gmp.self.gpg'] == invocation['stdout'], 'derived key mismatch')
            expected['gmp.self.gpg'] = identity(invocation['stdout'])
        require(assessed == case['assessment'], 'offline assessment disagrees with run')
        statuses[step], assessments[step] = status.decode('utf-8'), assessed
    require(engine.sequence == 45 and final_inputs == expected, 'unconsumed log or final input drift')
    return {'result': 'six-case-record-replayed', 'replayed_success': True,
            'offline_assessment_replay': assessments, 'source_acceptance': 'not-assessed',
            'historical_validity': 'not-established', 'runtime_qualification': False}


def unpack(entries):
    require(isinstance(entries, dict) and len(entries) <= 256, 'bundle file count bound')
    result, total = {}, 0
    for name, item in entries.items():
        require(re.fullmatch(r'[A-Za-z0-9_./-]{1,180}', name) and
                all(part not in {'', '.', '..'} for part in name.split('/')), 'unsafe bundle path')
        require(item['encoding'] in {'utf-8', 'base64'} and len(item['data']) <= FILE_LIMIT * 2, 'encoded file bound')
        raw = item['data'].encode() if item['encoding'] == 'utf-8' else base64.b64decode(item['data'], validate=True)
        total += len(raw)
        require(len(raw) <= FILE_LIMIT and total <= TOTAL_LIMIT and identity(raw) == item['identity'], 'bundle bytes drift/bound')
        result[name] = raw
    return result


def entry(raw):
    return {**encoded(raw), 'identity': identity(raw)}


def collect(directory):
    run.base.safe_path(directory)
    files, total = {}, 0
    for path in sorted(directory.iterdir()):
        if path.name == 'methods':
            require(path.is_dir() and not path.is_symlink(), 'unsafe retained method directory')
            continue
        if path.name == 'docker-config':
            require(path.is_dir() and not path.is_symlink() and not list(path.iterdir()), 'nonempty Docker config')
            continue
        candidates = sorted(path.iterdir()) if path.name == 'inputs' and path.is_dir() and not path.is_symlink() else [path]
        for candidate in candidates:
            name = str(candidate.relative_to(directory))
            require(re.fullmatch(r'(result\.json|[0-9]{3}\.(json|stdout|stderr)|[a-z-]+\.status|inputs/[A-Za-z0-9.-]+)', name),
                    'unexpected execution artifact')
            raw = read(candidate, FILE_LIMIT)
            total += len(raw)
            require(len(files) < 256 and total <= TOTAL_LIMIT, 'run export bound')
            files[name] = entry(raw)
    result = json.loads(unpack(files)['result.json'])
    require(set(result['methods']) == set(run.methods()), 'method set drift')
    methods = {}
    for name, binding in result['methods'].items():
        raw = read(directory / 'methods' / name)
        require(identity(raw) == binding, 'retained method drift')
        methods[name] = entry(raw)
    bundle = {'kind': 'diagnostic-gmp-verification-bundle-v2', 'original_directory': str(directory),
              'files': files, 'methods': methods, 'collector_method': entry(read(Path(__file__).resolve())),
              'source_acceptance': 'not-assessed'}
    # Failed executions retain their exact partial logs. They never acquire a successful replay verdict.
    if result['passed'] is True:
        prepared, _ = run.inputs.prepare()
        require(prepared == result['prepared_inputs'], 'retained source store drift')
    bundle['replay'] = replay(bundle)
    return bundle


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=CACHE)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--replay', type=Path)
    parser.add_argument('--sha256')
    args = parser.parse_args()
    if args.replay:
        require(args.output is None and args.sha256 is not None, 'replay requires reviewed external bundle SHA-256')
        raw = read(args.replay, BUNDLE_LIMIT)
        require(identity(raw)['sha256'] == args.sha256, 'reviewed bundle digest mismatch')
        bundle = json.loads(raw)
        checked = replay(bundle)
        require(checked == bundle['replay'], 'stored replay disagrees')
        print(json.dumps(checked, sort_keys=True, indent=2))
    else:
        require(args.output is not None and args.sha256 is None, 'collection requires new output path')
        bundle = collect(args.directory)
        raw = (json.dumps(bundle, sort_keys=True, indent=2) + '\n').encode()
        require(len(raw) <= BUNDLE_LIMIT, 'encoded bundle bound')
        with args.output.open('xb') as stream:
            stream.write(raw)
        print(json.dumps({'output': str(args.output), **identity(raw), 'replay': bundle['replay']}, indent=2))
