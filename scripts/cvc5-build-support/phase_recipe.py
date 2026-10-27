"""Explicit v0.2 transformation of the existing C2 preparation recipe."""
import copy
import hashlib
import importlib.util
from pathlib import Path

SUPPORT = 'scripts/cvc5-build-support/'
PATCH_PATH = 'patches/cvc5/1.3.4/capture-final-link.patch'
RULE_PATH = 'docs/query/solver-local-cvc5-offline-v0.2.md'
FILES = (SUPPORT + 'phase_recipe.py', SUPPORT + 'phase_rules.py',
         SUPPORT + 'link_materials.py', SUPPORT + 'link_formats.py', SUPPORT + 'capture_link.py', PATCH_PATH, RULE_PATH,
         'scripts/prepare-cvc5-execution-review.py', SUPPORT + 'event_rules.py',
         'docs/adr/0031-local-cvc5-build-provenance-boundary.md')
spec = importlib.util.spec_from_file_location('cvc5_phase_rules', Path(__file__).with_name('phase_rules.py'))
RULES = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RULES)
require = RULES.require
ANCHOR = b'target_compile_definitions(cvc5-bin PRIVATE -D__BUILDING_CVC5DRIVER -Dcvc5_obj_EXPORTS)\n'
ADDITION = (b'# Local provenance boundary: capture only; the controller links frozen inputs.\n'
            b'set_property(TARGET cvc5-bin PROPERTY CXX_LINKER_LAUNCHER\n'
            b'  "/usr/bin/python3.11;/recipe/scripts/cvc5-build-support/capture_link.py;'
            b'--output;/work/evidence/cvc5-link-capture.json;--")\n')


def patch_review(base, root, identity, patch):
    source = next(x for x in base['source_inputs'] if x['id'] == 'cvc5')
    source_root = root / source['source_root']
    name = 'src/main/CMakeLists.txt'
    original = (source_root / name).read_bytes()
    require(original.count(ANCHOR) == 1, 'phase-patch-anchor')
    changed = patch.apply_exact((root / PATCH_PATH).read_bytes(), {name: original}, {name})
    require(changed[name] == original.replace(ANCHOR, ANCHOR + ADDITION), 'phase-patch-scope')
    # Compute the combined after-tree without materializing or configuring it.
    rows = {r['path']: r for r in patch.inventory(source_root)}
    base_patch = root / 'patches/cvc5/1.3.4/explicit-inputs.patch'
    originals = {n: (source_root / n).read_bytes() for n in patch.FILES if (source_root / n).exists()}
    first = patch.apply_exact(base_patch.read_bytes(), originals, patch.FILES)
    for n, raw in first.items():
        rows[n] = {'path': n, 'bytes': len(raw), 'raw_digest': patch.digest(raw),
                   'executable': rows.get(n, {}).get('executable', False)}
    before_tree = patch.digest(patch.canonical([rows[n] for n in sorted(rows)]))
    rows[name] = {**rows[name], 'bytes': len(changed[name]), 'raw_digest': patch.digest(changed[name])}
    return {'patch': identity(root / PATCH_PATH), 'changed_files': [name],
            'order': 'after-explicit-inputs-patch', 'scope': 'static-text-only',
            'before_file_sha256': hashlib.sha256(original).hexdigest(),
            'after_file_sha256': hashlib.sha256(changed[name]).hexdigest(),
            'before_tree_digest': before_tree,
            'after_tree_digest': patch.digest(patch.canonical([rows[n] for n in sorted(rows)])),
            'files': len(rows), 'materialized': False, 'configured': False}


def upgrade(base, root, identity, patch):
    require(base['version'] == '0.1' and base['build_ready'] is False, 'phase-base-version')
    result = copy.deepcopy(base)
    result['version'] = '0.2'
    result['phase_plan'] = RULES.plan()
    refs = {r['path']: r for r in result['references']}
    refs.update({name: identity(root / name) for name in FILES})
    result['references'] = [refs[name] for name in sorted(refs)]
    result['transformations']['cvc5_final_link'] = patch_review(base, root, identity, patch)
    result['checked_inputs']['patch_files'] += 1
    result['staging']['recipe_files'].update({p: '/recipe/' + p for p in FILES})
    result['main_phase']['argument_builder'] = SUPPORT + 'phase_recipe.py:bound_steps'
    result['main_phase']['source_patch_gate'] += '; then exact capture-final-link.patch and combined tree check'
    result['main_phase']['link_state'] = 'awaiting-one-interception-and-real-freeze-qualification'
    result['policy']['provenance'] = {
        'rule_version': '0.2', 'scope': 'local-fixed-cvc5-only',
        'classes': ['accessible-input-set', 'stage-production-relations', 'tool-use-observations'],
        'complete_read_history': False, 'immutable_link_inputs_required': True,
        'protected_control_records_required': True, 'runtime_qualification': False}
    result['policy']['failure']['interception_exception'] = (
        'only cvc5-bin launcher exit 78 may declare link-intercepted after independent review; '
        'retain actual nonzero make/cmake exit; never build success or automatic next-stage execution')
    result['evidence']['assurance'] = 'ADR0031 input-set/stage/link reconciliation; no complete read history or OS qualification'
    result['evidence']['retain'] += ['one capture observation and actual failed build exit',
                                    'stage manifests, frozen-root identities and independent control-plane records']
    result['blocking_conditions'] += ['A3/A4/A7/A8 real closed-input/freeze/control/termination qualification absent',
                                      'final linker argv, implicit inputs and frozen-input replay unverified']
    return result


def bound_steps(steps):
    result = copy.deepcopy(steps)
    require([r['id'] for r in result] == ['cvc5-configure', 'main-effective-config-review', 'cvc5-build',
            'retain-unstripped', 'strip-copy', 'elf-readelf', 'elf-stripped-readelf'], 'phase-main-step-drift')
    gate = result[1]['requires']
    old = 'no unlisted tools/search roots, download, cache, launcher or option drift'
    require(gate.count(old) == 1, 'phase-main-review-drift')
    gate[gate.index(old)] = ('no unlisted tools/search roots, download, cache or option drift; '
                            'only exact reviewed cvc5-bin CXX_LINKER_LAUNCHER allowed')
    result[2]['expected_exit'] = 'nonzero-with-one-cvc5-bin-capture-78; never successful-build'
    result[2]['on_failure'] = 'retain-real-exit; interception-needs-independent-review; all-other-failures-stop'
    boundary = [
        {'id': 'link-interception-review', 'operation': 'review-gate', 'no_automatic_pass': True,
         'requires': ['one capture and matching generated command; no driver execution or fake CLI',
                      'no earlier error; actual make/cmake nonzero exit and all logs retained',
                      'all descendants exited and streams closed; exact required materials retained']},
        {'id': 'freeze-main-inputs', 'operation': 'freeze-stage', 'executed': False,
         'requires': ['qualified control plane; no writable aliases, writers or inherited write handles',
                      'SDK, dependency prefixes and entire main source/build trees bound read-only',
                      'response/scripts/objects/archives stable before consumption',
                      'empty output mounts do not shadow inputs; no undeclared workspace carry-over']},
        {'id': 'cvc5-final-link', 'operation': 'dispatch-reviewed-captured-driver', 'executed': False,
         'requires': ['separate execution authorization and qualified instance',
                      'exact ordered argv/cwd/environment; preserved repetitions and output path',
                      'immutable input roots and independent writable outputs; no reentry into Make'],
         'capture_path': RULES.CAPTURE_PATH, 'capture_missing': 'stop-no-command-data',
         'on_failure': 'stop-entire-batch-retain-everything-no-retry'},
        {'id': 'final-link-review', 'operation': 'review-gate', 'no_automatic_pass': True,
         'requires': ['full descendant closure; freeze unstripped output before postprocess',
                      'actual map/trace/ELF/member/implicit-input reconciliation; no generated unstable link input']},
    ]
    return result[:3] + boundary + result[3:]


def check_bound_structure(recipe):
    # The full offline checker must run first. The later namespace binder also
    # checks its closed envelope and refuses silent v0.1/v0.2 field mixing.
    RULES.keys(recipe, ('format', 'version', 'batch_id', 'preparation_only', 'execution_ready',
                       'build_ready', 'acceptance', 'blocking_conditions', 'references',
                       'checked_inputs', 'sdk', 'source_inputs', 'policy', 'staging',
                       'transformations', 'dependency_steps', 'main_phase', 'evidence',
                       'executed_recipe_steps', 'phase_plan'), 'bound-recipe')
    require(recipe['preparation_only'] is True and recipe['acceptance'] == 'not-accepted'
            and recipe['executed_recipe_steps'] == [], 'bound-recipe-overclaim')
    RULES.validate_plan(recipe['phase_plan'])
    RULES.keys(recipe['main_phase'], ('state', 'entry', 'configuration', 'argument_builder',
                                     'pending_value', 'source_patch_gate', 'link_state'), 'bound-main')
    require(recipe['main_phase']['argument_builder'] == SUPPORT + 'phase_recipe.py:bound_steps'
            and recipe['main_phase']['link_state'] == 'awaiting-one-interception-and-real-freeze-qualification',
            'bound-main-state')
    refs = recipe['references']
    require(type(refs) is list and 0 < len(refs) <= 1000, 'bound-reference-budget')
    seen = set()
    for ref in refs:
        RULES.keys(ref, ('path', 'bytes', 'sha256'), 'bound-reference')
        require(type(ref['path']) is str and ref['path'] not in seen, 'bound-reference-duplicate')
        seen.add(ref['path'])
        RULES.natural(ref['bytes'])
        RULES.sha(ref['sha256'])


def execution_review(base):
    result = copy.deepcopy(base)
    result['version'] = '0.2'
    result['pending_decisions'] = [x.replace('read observer', 'input-set/freeze/control-record boundary')
                                   for x in result['pending_decisions']]
    result['phase_plan'] = RULES.plan()
    result['supervision']['phase_rules'] = SUPPORT + 'phase_rules.py'
    result['supervision']['scope'] = 'offline phase declarations; dependency v0.1 event checks remain unchanged'
    result['supervision']['schedule'] = 'fixed four-phase plan; no execution adapter or qualification'
    return result
