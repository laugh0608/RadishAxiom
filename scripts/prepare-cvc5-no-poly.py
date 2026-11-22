#!/usr/bin/env python3
"""Prepare and verify the fixed AX-B01 Poly-disabled candidate offline."""

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
SELF = 'scripts/prepare-cvc5-no-poly.py'
spec = importlib.util.spec_from_file_location('cvc5_offline', ROOT / 'scripts/prepare-cvc5-offline-build.py')
C2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C2)
BUILD, PATCH, require = C2.BUILD, C2.PATCH, C2.require
PHASES = C2.module('cvc5_phase_recipe', 'scripts/cvc5-build-support/phase_recipe.py')
RULES = PHASES.RULES

CANDIDATE = 'ax-b01-cvc5-1.3.4-linux-aarch64-no-poly'
BATCH = 'ax-b01-no-poly-2026-11-22'
VERSION = '0.1'
PREFIX = 'radishaxiom-private-cvc5-no-poly-'
MANIFEST_FORMAT = 'radishaxiom-cvc5-no-poly-build-inputs'
RECORDS = 'docs/records/solver-cvc5-no-poly-2026-11-22/'
INPUTS = RECORDS + 'candidate-inputs.json'
RECIPE = RECORDS + 'offline-build-recipe.json'
BASELINE = 'docs/records/solver-cvc5-phases-2026-10-27/offline-build-recipe.json'
BASELINE_SHA = '0b6e31f762fd351063d4e656c1bf299c80c28269b370ad6f355c7674b2e4edee'
SHARED_PATCH = 'patches/cvc5/1.3.4/explicit-inputs.patch'
DELTA = 'patches/cvc5/1.3.4/no-poly-inputs.patch'
DELTA_SHA = 'ef595643e8858609521ca743b869c8fa440f73b7b9021e9afb81b80d5ae3b1e1'
PROBES = 'scripts/cvc5-build-support/no-poly-probes.cmake'
PROBES_SHA = 'a5c27a0319a8c2971b82a49f0d95fd2e9eb5127a2b960fde1cfdcaac22d733ab'
CAPTURE = PHASES.PATCH_PATH
SOURCES = ('cvc5', 'cadical', 'symfpu', 'gmp')
PROBE_KEYS = ('unlocked_io', 'closefrom')
CORE_ARCHIVES = {
    'gmp': '/work/prefix/gmp/lib/libgmp.a',
    'gmpxx': '/work/prefix/gmp/lib/libgmpxx.a',
    'cadical': '/work/prefix/cadical/lib/libcadical.a',
}
TERMINAL_ARCHIVES = {role: '/usr/lib/aarch64-linux-gnu/' + name for role, name in (
    ('editline', 'libedit.a'), ('tinfo', 'libtinfo.a'), ('bsd', 'libbsd.a'), ('md', 'libmd.a'))}
TERMINAL_REQUIRED = {'editline', 'tinfo', 'bsd'}
EDITLINE_HEADERS = {
    'editline/readline.h': {'bytes': 9195, 'sha256': 'bd234c53bbe46a2f0fa9b523dfc46fc2a9527affe5377fdba81b00e104c8a507'},
    'histedit.h': {'bytes': 9587, 'sha256': 'bbeef8fefdd8b5ba97e0df100550eeb6ef994a2861e685b5bbe72010a7d5fd39'},
}
MANIFEST_PATH = '/work/review/build-inputs.json'
CLOSURE_PATH = '/work/review/static-closure-review.json'
MANIFEST_ARG = '-DCVC5_C0_INPUT_MANIFEST_SHA256='
PENDING_MANIFEST_ARG = MANIFEST_ARG + '<reviewed-manifest-sha256>'
BINDINGS = ('candidate_id', *BUILD.BINDINGS)
POLY_STEPS = {'poly-prepare', 'poly-configure-choice', 'poly-build', 'poly-prefix-install', 'poly-library-copy'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, digest, limit=RULES.JSON_LIMIT):
    RULES.sha(digest)
    with C2.regular(path).open('rb') as stream:
        raw = stream.read(limit + 1)
    require(0 < len(raw) <= limit, 'candidate-json-budget')
    require(sha(raw) == digest, 'candidate-json-digest-mismatch')
    value = RULES.decode(raw, limit)
    require(type(value) is dict, 'candidate-json-object-required')
    return value


def historical():
    return read(C2.local(BASELINE), BASELINE_SHA)


def source_inventory(source):
    for role in ('archive', 'tree_inventory', 'license_inventory'):
        ref = source[role]
        actual = C2.identity(C2.local(ref['path']))
        require(actual['bytes'] == ref['bytes'] and 'sha256:' + actual['sha256'] == ref['raw_digest'],
                'candidate-source-reference-drift:' + source['id'])
    source_id = source['id']
    tree_path = C2.local(source['tree_inventory']['path'])
    tree = read(tree_path, source['tree_inventory']['raw_digest'].removeprefix('sha256:'))
    fresh = C2.SOURCES.audit(C2.local(source['archive']['path']))
    require(all(BUILD.CHECK.same_typed(tree[key], val) for key, val in fresh.items()),
            'candidate-source-inventory-drift:' + source_id)
    base = C2.local(source['source_root'])
    require(base.is_dir() and base.resolve() == base and base.name == tree['top'], 'candidate-source-root')
    top = base.parent
    entries = {row['path']: row for row in tree['entries']}
    require({p.relative_to(top).as_posix() for p in top.rglob('*')} == set(entries),
            'candidate-extra-or-missing-source-member:' + source_id)
    for name, row in entries.items():
        path = top / name
        mode = path.lstat().st_mode
        if row['kind'] == 'directory':
            require(stat.S_ISDIR(mode), 'candidate-source-directory-drift')
        elif row['kind'] == 'symlink':
            require(stat.S_ISLNK(mode) and path.readlink().as_posix() == row['target'],
                    'candidate-source-symlink-drift')
        else:
            require(stat.S_ISREG(mode) and stat.S_IMODE(mode) == 0o600, 'candidate-source-quarantine-drift')
            require(path.stat().st_size == row['bytes'] and sha(path.read_bytes()) == row['sha256'],
                    'candidate-source-bytes-drift:' + source_id)
    return tree


def patch_chain(old_refs):
    original_patch = C2.local(SHARED_PATCH).read_bytes()
    require(sha(original_patch) == old_refs[SHARED_PATCH]['sha256'], 'candidate-shared-patch-drift')
    # Project precisely the seven shared sections before applying any changes.
    sections = re.split(rb'(?m)(?=^diff --git )', original_patch)
    skipped = b'diff --git a/cmake/FindPoly.cmake b/cmake/FindPoly.cmake\n'
    require(sum(s.startswith(skipped) for s in sections) == 1, 'candidate-patch-projection')
    shared = b''.join(section for section in sections if not section.startswith(skipped))
    delta = C2.local(DELTA).read_bytes()
    capture = C2.local(CAPTURE).read_bytes()
    require(sha(delta) == DELTA_SHA and sha(capture) == old_refs[CAPTURE]['sha256'],
            'candidate-patch-drift')
    helper, main = 'cmake/cvc5-c0-inputs.cmake', 'src/main/CMakeLists.txt'
    return (
        (shared, PATCH.FILES - {'cmake/FindPoly.cmake'}, C2.identity(C2.local(SHARED_PATCH))),
        (delta, {helper}, C2.identity(C2.local(DELTA))),
        (capture, {main}, C2.identity(C2.local(CAPTURE))),
    )


def patch_review(source, old_refs):
    base = C2.local(source['source_root'])
    rows = {r['path']: r for r in PATCH.inventory(base)}
    changed, transforms = {}, []
    for raw, files, ref in patch_chain(old_refs):
        before = PATCH.digest(PATCH.canonical([rows[n] for n in sorted(rows)]))
        originals = {n: changed[n] if n in changed else (base / n).read_bytes()
                     for n in files if n in rows}
        edits = PATCH.apply_exact(raw, originals, files)
        for name, body in edits.items():
            rows[name] = {'path': name, 'bytes': len(body), 'raw_digest': PATCH.digest(body),
                          'executable': rows.get(name, {}).get('executable', False)}
        changed.update(edits)
        transforms.append({
            'reference': ref, 'applied_bytes': len(raw), 'applied_sha256': sha(raw),
            'files': sorted(files), 'before_tree': before,
            'after_tree': PATCH.digest(PATCH.canonical([rows[n] for n in sorted(rows)])),
        })
    PATCH.check_no_fallback(changed)
    return transforms


def read_baseline_ref(ref):
    value = read(C2.local(ref['path']), ref['sha256'])
    require(C2.identity(C2.local(ref['path'])) == ref, 'candidate-baseline-reference-drift')
    return value


def input_plan(base):
    refs = {ref['path']: ref for ref in base['references']}
    sources = [source for source in base['source_inputs'] if source['id'] in SOURCES]
    require([s['id'] for s in sources] == list(SOURCES), 'candidate-source-set')
    trees = {s['id']: source_inventory(s) for s in sources}

    plan_path = C2.PREP.PLAN.relative_to(ROOT).as_posix()
    retained_path = C2.REVIEW_RECORDS + 'retained-inventory.json'
    derived_path = C2.REVIEW_RECORDS + 'derived-content-review.json'
    plan, retained, derived = (read_baseline_ref(refs[name]) for name in (plan_path, retained_path, derived_path))
    checked = C2.check_retained(plan, retained)
    require(BUILD.CHECK.same_typed(C2.sdk_inventory(retained, plan), base['sdk']), 'candidate-sdk-inventory-drift')
    sdk_rows = {row['requested_path']: row for row in derived['selected_paths']}
    archives = {}
    for role, path in TERMINAL_ARCHIVES.items():
        selected = sdk_rows[path.removeprefix('/')]
        file, = selected['files']
        require(selected['resolved_path'] == path.removeprefix('/') and not selected['links'],
                'candidate-sdk-archive-path-drift')
        archives[role] = {'path': path, 'bytes': file['bytes'], 'sha256': file['sha256']}
    symfpu = trees['symfpu']
    headers = {'symfpu/' + row['path'].removeprefix(symfpu['top'] + '/'):
               {'bytes': row['bytes'], 'sha256': row['sha256']}
               for row in symfpu['entries'] if row['kind'] == 'file'
               and row['path'].split('/')[1] in ('core', 'utils')}
    cadical = trees['cadical']
    by_path = {row['path']: row for row in cadical['entries']}
    cadical_headers = {}
    for name in ('cadical.hpp', 'tracer.hpp'):
        row = by_path[cadical['top'] + '/src/' + name]
        cadical_headers['cadical/' + name] = {'bytes': row['bytes'], 'sha256': row['sha256']}
    gmp_headers = {'path': '/work/prefix/gmp/include', 'files': {'gmp.h': None, 'gmpxx.h': None}}
    return {
        'format': PREFIX + 'candidate-inputs', 'version': VERSION, 'candidate_id': CANDIDATE,
        'upstream_commit': BUILD.COMMIT, 'target_abi': BUILD.TARGET,
        'acceptance': 'not-accepted', 'build_ready': False, 'execution_ready': False,
        'baseline_review': C2.identity(C2.local(BASELINE)), 'sources': sources,
        'sdk': {'retention': refs[retained_path], 'acquisition': refs[plan_path],
                'content': base['sdk']['inventory'], 'derived_content': refs[derived_path],
                'historical_trust': refs[C2.REVIEW_RECORDS + 'historical-verification.json'], **checked},
        'patch_chain': patch_review(sources[0], refs),
        'dependency_manifest': {
            'format': MANIFEST_FORMAT, 'version': VERSION, 'path': MANIFEST_PATH, 'closure_path': CLOSURE_PATH,
            'versions': {k: BUILD.VERSIONS[k] for k in ('gmp', 'cadical', 'symfpu')},
            'headers': {
                'gmp': gmp_headers, 'gmpxx': gmp_headers,
                'cadical': {'path': '/work/prefix/cadical/include', 'files': cadical_headers},
                'symfpu': {'path': '/work/prefix/symfpu/include', 'files': headers},
                'editline': {'path': '/work/prefix/editline/include', 'files': EDITLINE_HEADERS},
            },
            'generated_archives': CORE_ARCHIVES, 'sdk_archives': archives,
            'required_editline_roles': sorted(TERMINAL_REQUIRED),
            'pending': 'actual-generated-bytes-and-independently-reviewed-order-abi-and-closure',
        },
    }


def recipe(base, inputs):
    config = copy.deepcopy(base['main_phase']['configuration'])
    poly, = (row for row in config if row['name'] == 'USE_POLY')
    poly.update(candidate='OFF', assessment='candidate-difference', reason='AX-B01 fixed Poly-disabled candidate')
    for row in config:
        row['evidence'] = [path for path in row['evidence'] if not path.startswith('libpoly/')]
        require(row['evidence'], 'candidate-configuration-evidence-missing:' + row['name'])
    # Render the argv from the frozen matrix. The placeholder is not a valid SHA-256.
    steps = PHASES.bound_steps(C2.cvc5_commands(config, '0' * 64))
    argv = steps[0]['argv']
    argv[argv.index(MANIFEST_ARG + '0' * 64)] = PENDING_MANIFEST_ARG
    steps[1]['requires'].append('verify effective USE_POLY=OFF, disabled Poly lookup and no Poly input in generated rules')
    stages = copy.deepcopy(base['dependency_steps'])
    require(POLY_STEPS <= {step['id'] for step in stages}, 'candidate-legacy-step-drift')
    stages = [step for step in stages if step['id'] not in POLY_STEPS]
    by_id = {step['id']: step for step in stages}
    probe_argv = by_id['dependency-probes']['argv']
    probe_argv[probe_argv.index('-DCMAKE_CXX_STANDARD=17')] = '-DCMAKE_CXX_STANDARD=11'
    by_id['gmp-output-review']['requires'][1] = 'compiler/ABI and archive-member review before cvc5 uses GMP'
    by_id['probe-review']['requires'][-1] = 'require the two typed CaDiCaL results; no other capability keys'
    gate = stages.pop()
    require(gate['id'] == 'dependency-manifest-review', 'candidate-dependency-gate-position')
    gate['requires'] = [
        'check-manifest passes for exact five header roles, archives and independently supplied SHA256',
        'retain actual pkgconf output and independently reviewed ordered Editline closure, ABI and license evidence',
        'verify exact virtual paths and frozen actual input bytes',
    ]
    for rel in EDITLINE_HEADERS:
        stages.append(C2.command('editline-stage-' + Path(rel).stem,
                                 [C2.CMAKE, '-E', 'copy', '/usr/include/' + rel,
                                  '/work/prefix/editline/include/' + rel]))
    stages.append(gate)
    staging = copy.deepcopy(base['staging'])
    staging['sources'] = 'copy four checked trees under /work/src by source id; verify before transforms; retain originals'
    staging['new_directories'].remove('/work/prefix/poly/lib')
    staging['new_directories'].append('/work/prefix/editline/include/editline')
    staging['recipe_files'] = {
        PROBES: '/recipe/probes/CMakeLists.txt',
        **{p: '/recipe/' + p for p in ('scripts/cvc5-build-support/capture_link.py',
                                       'scripts/cvc5-build-support/phase_rules.py')},
    }
    policy = copy.deepcopy(base['policy'])
    policy['host_batch_directory'] = Path(C2.batch_path(BATCH)).relative_to(ROOT).as_posix()
    old_refs = {r['path']: r for r in base['references']}
    shared = set(C2.support_files()) | set(PHASES.FILES)
    refs = {name: C2.identity(C2.local(name))
            for name in shared | {SELF, PROBES, BASELINE, INPUTS, SHARED_PATCH, DELTA}}
    require(all(refs[name] == old_refs.get(name) for name in shared), 'candidate-shared-method-drift')
    require(refs[PROBES]['sha256'] == PROBES_SHA, 'candidate-probes-drift')
    blockers = base['blocking_conditions'][1:]
    blockers.insert(0, 'C1 retained input/license and candidate host acceptance pending')
    return {
        'format': PREFIX + 'offline-recipe', 'version': VERSION, 'candidate_id': CANDIDATE,
        'batch_id': BATCH, 'preparation_only': True,
        'execution_ready': False, 'build_ready': False, 'acceptance': 'not-accepted',
        'blocking_conditions': blockers, 'references': [refs[n] for n in sorted(refs)],
        'candidate_inputs': C2.identity(C2.local(INPUTS)), 'source_inputs': inputs['sources'],
        'sdk': base['sdk'], 'policy': policy, 'staging': staging,
        'transformations': {'cadical': base['transformations']['cadical'], 'patch_chain': inputs['patch_chain']},
        'dependency_steps': stages, 'probe_output': {'format': PREFIX + 'dependency-probes', 'version': VERSION,
                                                    'boolean_keys': list(PROBE_KEYS)},
        'main_phase': {
            'configuration': config, 'steps': steps,
            'pending_bindings': ['actual dependency manifest SHA256', 'actual cache/trace and final-link capture'],
        },
        'phase_plan': base['phase_plan'], 'evidence': base['evidence'], 'executed_recipe_steps': [],
    }


def checked_inputs(base):
    path = C2.local(INPUTS)
    value = read(path, C2.identity(path)['sha256'])
    require(BUILD.CHECK.same_typed(value, input_plan(base)), 'candidate-input-set-drift')
    return value


def checked_recipe(path, digest):
    candidate = read(path, digest)
    require(candidate.get('format') == PREFIX + 'offline-recipe'
            and candidate.get('version') == VERSION and candidate.get('candidate_id') == CANDIDATE,
            'candidate-recipe-identity')
    base = historical()
    expected = recipe(base, checked_inputs(base))
    BUILD.keys(candidate, set(expected), 'candidate-recipe-fields')
    for key, wanted in expected.items():
        require(BUILD.CHECK.same_typed(candidate[key], wanted), 'candidate-recipe-drift:' + key)
    return candidate


def check_manifest(root, digest, plan):
    root = BUILD.path_value(str(root), directory=True)
    path = C2.regular(root / MANIFEST_PATH.lstrip('/'))
    value = read(path, digest, BUILD.JSON_LIMIT)
    BUILD.keys(value, set(BINDINGS) | {'format', 'version', 'review_state', 'closure_review'},
               'candidate-manifest-fields')
    contract = plan['dependency_manifest']
    require(value['format'] == MANIFEST_FORMAT and value['version'] == VERSION
            and value['candidate_id'] == plan['candidate_id'] and value['upstream_commit'] == plan['upstream_commit']
            and value['target_abi'] == plan['target_abi'] and value['review_state'] == 'reviewed-for-configuration'
            and BUILD.CHECK.same_typed(value['versions'], contract['versions']), 'candidate-manifest-identity-or-versions')
    budget = {'files': 0, 'bytes': 0, 'entries': 0}
    closure = value['closure_review']
    BUILD.keys(closure, {'path', 'bytes', 'sha256'}, 'candidate-closure-fields')
    require(closure['path'] == CLOSURE_PATH, 'candidate-closure-path')
    target = C2.regular(root / CLOSURE_PATH.lstrip('/'))
    BUILD.verify_file(target, closure, budget)
    review = read(target, closure['sha256'], BUILD.JSON_LIMIT)
    BUILD.keys(review, set(BINDINGS) | {'review_state'}, 'candidate-closure-review-fields')
    require(review['review_state'] == 'static-closure-and-abi-reviewed'
            and all(BUILD.CHECK.same_typed(review[k], value[k]) for k in BINDINGS),
            'candidate-closure-binding')

    headers = value['header_roots']
    BUILD.keys(headers, set(contract['headers']), 'candidate-header-role-set')
    for role, allowed in contract['headers'].items():
        item = headers[role]
        BUILD.keys(item, {'path', 'files'}, 'candidate-header-fields')
        require(item['path'] == allowed['path'], 'candidate-header-root')
        directory = BUILD.path_value(str(root / item['path'].lstrip('/')), directory=True)
        rows = item['files']
        names = allowed['files']
        require(type(rows) is list and len(rows) == len(names), 'candidate-header-file-set:' + role)
        seen = set()
        for row in rows:
            BUILD.keys(row, {'path', 'bytes', 'sha256'}, 'candidate-header-file-fields')
            name = BUILD.relative_value(row['path'])
            require(name in names and name not in seen, 'candidate-header-file-set:' + role)
            pin = names[name]
            require(pin is None or BUILD.CHECK.same_typed(pin, {k: row[k] for k in ('bytes', 'sha256')}),
                    'candidate-pinned-header-drift:' + role)
            BUILD.verify_file(directory / name, row, budget)
            seen.add(name)
        require(BUILD.header_inventory(directory, budget) == seen, 'candidate-staged-header-set:' + role)

    archives = value['archives']
    required = set(CORE_ARCHIVES) | set(contract['required_editline_roles'])
    require(type(archives) is dict and required <= set(archives) <= required | {'md'}, 'candidate-archive-role-set')
    for role, row in archives.items():
        BUILD.keys(row, {'path', 'bytes', 'sha256'}, 'candidate-archive-fields')
        pin = contract['sdk_archives'].get(role)
        if pin is None:
            require(row['path'] == contract['generated_archives'][role], 'candidate-generated-archive-path')
        else:
            require(BUILD.CHECK.same_typed(row, pin), 'candidate-sdk-archive-drift:' + role)
        BUILD.verify_file(root / row['path'].lstrip('/'), row, budget)
    order = value['editline_link_order']
    require(type(order) is list and 0 < len(order) <= 32 and order[0] == 'editline'
            and all(type(r) is str for r in order) and set(order) == set(archives) - set(CORE_ARCHIVES),
            'candidate-editline-order-roles')
    return {'candidate_id': CANDIDATE, 'scope': 'byte-and-declared-review-binding-only', 'passed': True,
            'checked_file_references': budget['files'], 'editline_link_order': order,
            'build_ready': False, 'execution_ready': False, 'acceptance': 'not-accepted'}


def bound_main(candidate, recipe_digest, root, manifest_digest, inputs):
    verified = check_manifest(root, manifest_digest, inputs)
    steps = copy.deepcopy(candidate['main_phase']['steps'])
    argv = steps[0]['argv']
    require(argv.count(PENDING_MANIFEST_ARG) == 1, 'candidate-manifest-binding-position')
    argv[argv.index(PENDING_MANIFEST_ARG)] = MANIFEST_ARG + manifest_digest
    return {
        'format': PREFIX + 'bound-main', 'version': VERSION, 'candidate_id': CANDIDATE,
        'recipe_sha256': recipe_digest, 'manifest_sha256': manifest_digest, 'byte_preflight': verified,
        'steps': steps, 'execution_ready': False, 'build_ready': False, 'acceptance': 'not-accepted',
        'executed_recipe_steps': [], 'blocking_conditions': candidate['blocking_conditions'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    for mode in ('prepare-inputs', 'prepare'):
        modes.add_parser(mode).add_argument('--output', required=True, type=Path)
    bind = modes.add_parser('bind-inputs')
    for action in (modes.add_parser('check'), bind):
        action.add_argument('recipe', type=Path)
        action.add_argument('--sha256', required=True, help='Independently supplied recipe SHA-256')
    bind.add_argument('--material-root', type=Path, required=True)
    bind.add_argument('--manifest-sha256', required=True)
    bind.add_argument('--output', type=Path, required=True)
    manifest = modes.add_parser('check-manifest')
    manifest.add_argument('--material-root', type=Path, required=True)
    manifest.add_argument('--sha256', required=True, help='Independently supplied manifest SHA-256')
    args = parser.parse_args()
    try:
        if args.mode in ('check', 'bind-inputs'):
            candidate = checked_recipe(args.recipe.absolute(), args.sha256)
            result = {'preparation_check': 'passed', 'candidate_id': CANDIDATE}
            if args.mode == 'bind-inputs':
                inputs = read(C2.local(INPUTS), candidate['candidate_inputs']['sha256'])
                bound = bound_main(candidate, args.sha256, args.material_root, args.manifest_sha256, inputs)
                C2.write_new(args.output.absolute(), bound)
                result.update(written=str(args.output), sha256=sha(C2.encoded(bound)))
        else:
            base = historical()
            if args.mode == 'check-manifest':
                result = check_manifest(args.material_root, args.sha256, checked_inputs(base))
            else:
                value = input_plan(base) if args.mode == 'prepare-inputs' else recipe(base, checked_inputs(base))
                C2.write_new(args.output.absolute(), value)
                result = {'written': str(args.output), 'sha256': sha(C2.encoded(value))}
        print(json.dumps({**result, 'acceptance': 'not-accepted', 'build_ready': False, 'execution_ready': False}))
        return 0 if args.mode.startswith('prepare') else 2
    except (ValueError, KeyError, OSError, TypeError, StopIteration) as exc:
        print('candidate-offline-check-rejected: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
