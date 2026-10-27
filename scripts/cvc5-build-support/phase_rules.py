"""Private v0.2 phase declaration checks, never OS qualification or execution."""
import hashlib
import json
from pathlib import PurePosixPath
import re

FORMAT = 'radishaxiom-private-cvc5-phase-declarations'
CAPTURE_FORMAT = 'radishaxiom-private-cvc5-link-capture'
CAPTURE_EXIT = 78
JSON_LIMIT = 16 * 1024**2
ARG_LIMIT = 65536
CAPTURE_LIMIT = 1024**2
CXX = '/usr/bin/aarch64-linux-gnu-g++-12'
BUILD_ROOT = '/work/build/cvc5'
OUTPUT = BUILD_ROOT + '/bin/cvc5'
CAPTURE_PATH = '/work/evidence/cvc5-link-capture.json'
STAGES = (
    ('dependencies', ('sdk', 'sources', 'recipe'), ('dependencies', 'dependency-evidence')),
    ('main-compile', ('sdk', 'sources', 'recipe', 'dependencies'),
     ('main-tree', 'main-evidence', 'link-capture')),
    ('final-link', ('sdk', 'dependencies', 'main-tree', 'main-evidence', 'link-capture'),
     ('link-output', 'link-evidence')),
    ('postprocess', ('sdk', 'link-output', 'link-evidence'), ('candidate', 'elf-evidence')),
)


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def keys(value, fields, label):
    require(type(value) is dict and set(value) == set(fields), label + '-fields')


def sha(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'phase-sha256')
    return value


def natural(value):
    require(type(value) is int and 0 <= value < 2**64, 'phase-natural')
    return value


def binding(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def duplicates(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'phase-duplicate-json-key')
        value[key] = item
    return value


def constant(_):
    raise ValueError('phase-nonfinite-json')


def decode(raw, limit=JSON_LIMIT):
    require(type(raw) is bytes and 0 < len(raw) <= limit, 'phase-json-budget')
    depth, quoted, escaped = 0, False, False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            require(depth <= 64, 'phase-json-depth-budget')
        elif byte in (93, 125):
            depth -= 1
    try:
        return json.loads(raw, object_pairs_hook=duplicates, parse_constant=constant)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('phase-json-encoding-or-depth') from exc


def path(value):
    require(isinstance(value, str) and 0 < len(value.encode()) <= 4096,
            'phase-path-size')
    require(value.startswith('/') and '\\' not in value
            and not any(ord(c) < 32 or ord(c) == 127 for c in value), 'phase-path')
    require(str(PurePosixPath(value)) == value
            and not any(x in ('', '.', '..') for x in value.split('/')[1:]),
            'phase-path-canonical')
    return value


def beneath(value, root):
    return value == root or value.startswith(root + '/')


def plan():
    return {'version': '0.2', 'scope': 'fixed-cvc5-stage-input-sets',
            'stages': [{'id': name, 'inputs': list(inputs), 'outputs': list(outputs),
                        'after': [] if n == 0 else [STAGES[n - 1][0]],
                        'exit': 'intercepted-nonzero' if name == 'main-compile' else 'zero',
                        'freeze': 'all-descendants-exited-before-publishing-read-only-inputs'}
                       for n, (name, inputs, outputs) in enumerate(STAGES)],
            'link': {'capture_path': CAPTURE_PATH, 'launcher_exit': CAPTURE_EXIT,
                     'output_path': OUTPUT, 'map_path': '/work/evidence/cvc5.map',
                     'writable_roots': [BUILD_ROOT + '/bin', '/work/evidence', '/work/tmp'],
                     'repeat_argv': True, 'reenter_make': False},
            'qualification': 'required-not-established', 'reset_resource_budget': False}


def validate_plan(value):
    # JSON type equality matters (False must not equal 0).
    require(binding(value) == binding(plan()), 'phase-plan-drift')


def references(rows, names):
    require(type(rows) is list and len(rows) == len(names), 'phase-reference-count')
    result = {}
    for row, name in zip(rows, names):
        keys(row, ('id', 'sha256'), 'phase-reference')
        require(row['id'] == name and name not in result, 'phase-reference-order-or-id')
        result[name] = sha(row['sha256'])
    return result


def check_declarations(value, recipe, recipe_sha256):
    """Check a prefix of fixed stage declarations without authenticating them."""
    keys(value, ('format', 'version', 'scope', 'recipe_sha256', 'plan_sha256',
                 'batch_start_ns', 'external_inputs', 'stages', 'runtime_qualification'), 'phase-root')
    require(value['format'] == FORMAT and value['version'] == '0.2'
            and value['scope'] == 'offline-unverified-declarations'
            and value['runtime_qualification'] is False, 'phase-scope')
    validate_plan(recipe['phase_plan'])
    require(recipe['version'] == '0.2' and value['recipe_sha256'] == sha(recipe_sha256)
            and value['plan_sha256'] == binding(recipe['phase_plan']), 'phase-recipe-binding')
    available = references(value['external_inputs'], ('sdk', 'sources', 'recipe'))
    # The recipe input is the exact serialized recipe, not a free-form role hash.
    require(available['recipe'] == recipe_sha256, 'phase-recipe-input-binding')
    require(available['sdk'] == binding(recipe['sdk'])
            and available['sources'] == binding(recipe['source_inputs']), 'phase-external-input-binding')
    stages = value['stages']
    require(type(stages) is list and 0 < len(stages) <= len(STAGES), 'phase-stage-count')
    start = natural(value['batch_start_ns'])
    previous_end = start
    resources, limits = recipe['policy']['resources'], recipe['evidence']['log_limits']
    previous_bytes = previous_logs = 0
    previous_counters = {k: 0 for k in ('memory_peak_bytes', 'swap_peak_bytes', 'events_bytes',
                                       'inventory_bytes', 'oom_kill', 'pids_denied')}
    records = []
    for row, (name, inputs, outputs) in zip(stages, STAGES):
        keys(row, ('id', 'inputs', 'outputs', 'started_ns', 'ended_ns', 'build_exit',
                   'first_error', 'interceptions', 'streams_closed', 'descendants',
                   'writers', 'writable_aliases', 'frozen', 'control_record_sha256',
                   'usage'), 'phase-stage')
        require(row['id'] == name, 'phase-stage-order')
        declared = references(row['inputs'], inputs)
        require(all(available.get(k) == v for k, v in declared.items()), 'phase-input-origin')
        produced = references(row['outputs'], outputs)
        require(not set(produced) & set(available), 'phase-output-redefinition')
        begin, end = natural(row['started_ns']), natural(row['ended_ns'])
        require(previous_end <= begin <= end, 'phase-time-order')
        require(end - start < (resources['deadline_seconds'] - resources['termination_reserve_seconds']) * 10**9,
                'phase-batch-deadline')
        previous_end = end
        require(row['first_error'] is None, 'phase-first-error')
        require(type(row['build_exit']) is int, 'phase-build-exit-type')
        require(type(row['interceptions']) is list, 'phase-interceptions-type')
        if name == 'main-compile':
            require(1 <= row['build_exit'] <= 255 and len(row['interceptions']) == 1,
                    'phase-expected-interception')
            capture = row['interceptions'][0]
            keys(capture, ('target', 'exit_code', 'sha256', 'driver_executed', 'output_existed'),
                 'phase-interception')
            require(capture['target'] == 'cvc5-bin' and type(capture['exit_code']) is int
                    and capture['exit_code'] == CAPTURE_EXIT and capture['driver_executed'] is False
                    and capture['output_existed'] is False, 'phase-interception-boundary')
            require(sha(capture['sha256']) == produced['link-capture'], 'phase-capture-binding')
        else:
            require(row['build_exit'] == 0 and not row['interceptions'], 'phase-stage-exit')
        require(row['streams_closed'] is True and row['frozen'] is True, 'phase-not-closed-or-frozen')
        require(all(natural(row[k]) == 0 for k in ('descendants', 'writers', 'writable_aliases')),
                'phase-live-writer-or-alias')
        sha(row['control_record_sha256'])  # An unverified reference, not an authenticated receipt.
        usage = row['usage']
        keys(usage, ('total_bytes', 'log_bytes', 'memory_peak_bytes', 'swap_peak_bytes',
                     'events_bytes', 'inventory_bytes', 'oom_kill', 'pids_denied'), 'phase-usage')
        for v in usage.values():
            natural(v)
        require(all(usage[k] >= old for k, old in previous_counters.items()), 'phase-counter-rollback')
        previous_counters = {k: usage[k] for k in previous_counters}
        require(previous_bytes <= usage['total_bytes'] <= resources['writable_bytes'] - resources['finalization_reserve_bytes'],
                'phase-storage-budget-or-reset')
        require(previous_logs <= usage['log_bytes'] <= limits['all_logs_bytes'], 'phase-log-budget-or-reset')
        require(usage['memory_peak_bytes'] <= resources['memory_bytes']
                and usage['swap_peak_bytes'] <= resources['swap_bytes']
                and usage['events_bytes'] <= limits['events_jsonl_bytes']
                and usage['inventory_bytes'] <= limits['inventory_bytes']
                and usage['oom_kill'] == usage['pids_denied'] == 0, 'phase-resource-limit')
        require(usage['total_bytes'] >= usage['log_bytes'] + usage['events_bytes'] + usage['inventory_bytes'],
                'phase-storage-accounting')
        previous_bytes, previous_logs = usage['total_bytes'], usage['log_bytes']
        available.update(produced)
        records.append(name)
    return {'scope': 'offline-declaration-consistency-only', 'checked_prefix': records,
            'unverified_outputs': available, 'runtime_qualification': False,
            'execution_ready': False, 'build_ready': False, 'acceptance': 'not-accepted'}


def check_capture(value, expected_environment):
    keys(value, ('format', 'version', 'target', 'scope', 'driver_executed',
                 'exit_code', 'argv', 'cwd', 'environment'), 'capture')
    require(value['format'] == CAPTURE_FORMAT and value['version'] == '0.2'
            and value['target'] == 'cvc5-bin' and value['scope'] == 'untrusted-tool-observation'
            and value['driver_executed'] is False and type(value['exit_code']) is int
            and value['exit_code'] == CAPTURE_EXIT, 'capture-boundary')
    require(beneath(path(value['cwd']), BUILD_ROOT), 'capture-cwd')
    args = value['argv']
    require(type(args) is list and 1 <= len(args) <= ARG_LIMIT, 'capture-argv-count')
    require(all(type(a) is str and '\x00' not in a for a in args), 'capture-argv-string')
    require(args[0] == CXX, 'capture-driver')
    env = value['environment']
    extra = {'PWD', 'OLDPWD', 'SHLVL', 'MAKEFLAGS', 'MFLAGS', 'MAKELEVEL', '_'}
    require(type(env) is dict and set(expected_environment) <= set(env)
            and set(env) <= set(expected_environment) | extra, 'capture-environment-keys')
    require(all(env[k] == v for k, v in expected_environment.items()), 'capture-environment-drift')
    require(all(type(v) is str and '\x00' not in v for v in env.values()), 'capture-environment-value')
    # A build tool can chdir without updating the inherited shell PWD. Retain
    # both values; neither is rewritten to fabricate agreement with the other.
    for key in ('PWD', 'OLDPWD'):
        if key in env:
            require(beneath(path(env[key]), '/work'), 'capture-shell-directory')
    require(len(json.dumps(value, ensure_ascii=False).encode()) <= CAPTURE_LIMIT, 'capture-byte-budget')
    return args
