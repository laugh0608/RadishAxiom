#!/usr/bin/env python3
"""Independent finite byte/patch/export review. No production checker imports.

prepare writes synthetic inputs; check compares a production review export to
those hand-specified inputs. Neither mode runs an SDK, compiler or solver.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shlex
import stat
import struct

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'docs/records/solver-cvc5-c2-2026-10-23/offline-build-recipe.json'
OLD_SHA = '2ee5ae5e9c437036c6b0cc6ec8c4324b875b0376dcd91c9aa3d5dca29d01f4dd'
CWD = '/work/build/cvc5'
LIB = '/work/prefix/test/lib/libdep.a'
SCRIPT = '/work/prefix/test/lib/libroute.a'
A, B = CWD + '/CMakeFiles/alpha.o', CWD + '/CMakeFiles/space name.o'
CRT = '/usr/lib/aarch64-linux-gnu/crt1.o'
SPECS = '/usr/lib/gcc/aarch64-linux-gnu/12/specs'
STAGES = [
    ('dependencies', ['sdk', 'sources', 'recipe'], ['dependencies', 'dependency-evidence']),
    ('main-compile', ['sdk', 'sources', 'recipe', 'dependencies'], ['main-tree', 'main-evidence', 'link-capture']),
    ('final-link', ['sdk', 'dependencies', 'main-tree', 'main-evidence', 'link-capture'], ['link-output', 'link-evidence']),
    ('postprocess', ['sdk', 'link-output', 'link-evidence'], ['candidate', 'elf-evidence']),
]


def demand(ok, reason):
    if not ok:
        raise ValueError('independent:' + reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def read(path):
    demand(path.resolve() == path and path.is_file() and not path.is_symlink(), 'regular-retained-path')
    demand(path.stat().st_size <= 16 * 1024**2, 'read-budget')
    return path.read_bytes()


def unique(pairs):
    value = {}
    for key, item in pairs:
        demand(key not in value, 'duplicate-json-key')
        value[key] = item
    return value


def parse(raw):
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: demand(False, 'nonfinite'))


def phase_plan():
    return {'version': '0.2', 'scope': 'fixed-cvc5-stage-input-sets',
            'stages': [{'id': name, 'inputs': inputs, 'outputs': outputs,
                        'after': [] if i == 0 else [STAGES[i - 1][0]],
                        'exit': 'intercepted-nonzero' if name == 'main-compile' else 'zero',
                        'freeze': 'all-descendants-exited-before-publishing-read-only-inputs'}
                       for i, (name, inputs, outputs) in enumerate(STAGES)],
            'link': {'capture_path': '/work/evidence/cvc5-link-capture.json', 'launcher_exit': 78,
                     'output_path': CWD + '/bin/cvc5', 'map_path': '/work/evidence/cvc5.map',
                     'writable_roots': [CWD + '/bin', '/work/evidence', '/work/tmp'],
                     'repeat_argv': True, 'reenter_make': False},
            'qualification': 'required-not-established', 'reset_resource_budget': False}


def fixture_recipe():
    value = copy.deepcopy(parse(read(OLD)))
    value['version'], value['phase_plan'] = '0.2', phase_plan()
    return value


def elf(marker):
    # Three sections: NULL, .shstrtab, .data. No code, symbol or relocation;
    # this is a structural AArch64 fixture, not an executable payload.
    strings = b'\0.shstrtab\0.data\0'
    header = struct.pack('<16sHHIQQQIHHHHHH', b'\x7fELF\x02\x01\x01' + bytes(9),
                         1, 183, 1, 0, 0, 64, 0, 64, 0, 0, 64, 3, 1)
    table = bytes(64) + struct.pack('<IIQQQQIIQQ', 1, 3, 0, 0, 256, len(strings), 0, 0, 1, 0)
    table += struct.pack('<IIQQQQIIQQ', 11, 1, 0, 0, 256 + len(strings), 1, 0, 0, 1, 0)
    return header + table + strings + bytes([marker])


def ar_member(name, raw):
    fields = [name.ljust(16), '0'.ljust(12), '0'.ljust(6), '0'.ljust(6), '644'.ljust(8), str(len(raw)).ljust(10)]
    return ''.join(fields).encode() + b'`\n' + raw + (b'\n' if len(raw) % 2 else b'')


def write(root, name, raw):
    path = root / name
    with path.open('xb') as stream:
        stream.write(raw)
    return {'path': name, 'bytes': len(raw), 'sha256': digest(raw)}


def prepare(recipe, recipe_digest, directory):
    demand(directory.is_absolute() and directory.parent.resolve() == directory.parent
           and not directory.exists() and not directory.is_symlink(), 'new-synthetic-directory')
    directory.mkdir()
    args = ['/usr/bin/aarch64-linux-gnu-g++-12', '-Werror', '--sysroot=/', '-O3', '-DNDEBUG',
            '-fuse-ld=bfd', '-Wl,-Map,/work/evidence/cvc5.map,--cref,-t,-t', '-static',
            '@CMakeFiles/objects.rsp', '-o', 'bin/cvc5', SCRIPT, LIB]
    capture = {'format': 'radishaxiom-private-cvc5-link-capture', 'version': '0.2',
               'target': 'cvc5-bin', 'scope': 'untrusted-tool-observation', 'driver_executed': False,
               'exit_code': 78, 'argv': args, 'cwd': CWD,
               'environment': dict(recipe['policy']['environment']['values'], PWD=CWD)}
    capture_ref = write(directory, 'capture.json', encoded(capture))
    launcher = ['/usr/bin/python3.11', '/recipe/scripts/cvc5-build-support/capture_link.py',
                '--output', '/work/evidence/cvc5-link-capture.json', '--']
    link_ref = write(directory, 'link.txt', (shlex.join(launcher + args) + '\n').encode())
    available = {'sdk': digest(canonical(recipe['sdk'])), 'sources': digest(canonical(recipe['source_inputs'])),
                 'recipe': recipe_digest}
    stages = []
    external = [{'id': k, 'sha256': available[k]} for k in ('sdk', 'sources', 'recipe')]
    for i, (name, ins, outs) in enumerate(STAGES[:2]):
        inputs = [{'id': k, 'sha256': available[k]} for k in ins]
        for k in outs:
            available[k] = capture_ref['sha256'] if k == 'link-capture' else digest(('synthetic:' + k).encode())
        stages.append({'id': name, 'inputs': inputs,
                       'outputs': [{'id': k, 'sha256': available[k]} for k in outs],
                       'started_ns': i * 100 + 1, 'ended_ns': i * 100 + 2, 'build_exit': 0 if i == 0 else 2,
                       'first_error': None, 'interceptions': [] if i == 0 else [{
                           'target': 'cvc5-bin', 'exit_code': 78, 'sha256': capture_ref['sha256'],
                           'driver_executed': False, 'output_existed': False}],
                       'streams_closed': True, 'descendants': 0, 'writers': 0, 'writable_aliases': 0,
                       'frozen': True, 'control_record_sha256': digest(('synthetic-control:' + name).encode()),
                       'usage': {'total_bytes': 100000 * (i + 1), 'log_bytes': 100 * (i + 1),
                                 'memory_peak_bytes': 100, 'swap_peak_bytes': 0, 'events_bytes': 100,
                                 'inventory_bytes': 100, 'oom_kill': 0, 'pids_denied': 0}})
    phases = {'format': 'radishaxiom-private-cvc5-phase-declarations', 'version': '0.2',
              'scope': 'offline-unverified-declarations', 'recipe_sha256': recipe_digest,
              'plan_sha256': digest(canonical(recipe['phase_plan'])), 'batch_start_ns': 0,
              'external_inputs': external, 'stages': stages, 'runtime_qualification': False}
    phase_ref = write(directory, 'phases.json', encoded(phases))
    objects = [elf(17), elf(29)]
    archive = b'!<arch>\n' + b''.join(ar_member('duplicate.o/', x) for x in objects)
    members = [{'index': n, 'name': 'duplicate.o', 'occurrence': n + 1, 'kind': 'object',
                'bytes': len(raw), 'sha256': digest(raw)} for n, raw in enumerate(objects)]
    specs = [(A, 'alpha.o', objects[0], 'object', 'main-compile', None),
             (B, 'space.o', objects[1], 'object', 'main-compile', None),
             (LIB, 'libdep.a', archive, 'archive', 'dependencies', members),
             (SCRIPT, 'libroute.a', ('GROUP ( ' + LIB + ' AS_NEEDED ( ' + LIB + ' ) )\n').encode(),
              'script', 'dependencies', None),
             (CWD + '/CMakeFiles/objects.rsp', 'objects.rsp',
              b'CMakeFiles/alpha.o "CMakeFiles/space name.o" @CMakeFiles/more.rsp\n', 'response', 'main-compile', None),
             (CWD + '/CMakeFiles/more.rsp', 'more.rsp', b'CMakeFiles/alias.o\n', 'response', 'main-compile', None),
             (CRT, 'crt1.o', elf(43), 'object', 'sdk', None),
             (SPECS, 'specs.txt', b'synthetic specs observation only\n', 'configuration', 'sdk', None)]
    files = []
    for name, file, raw, role, producer, member_rows in specs:
        key = 'main-tree' if producer == 'main-compile' else producer
        files.append({'path': name, 'file': write(directory, file, raw), 'role': role, 'producer': producer,
                      'producer_sha256': available[key], 'frozen_before_link': True, 'members': member_rows})
    expanded = args[:8] + ['CMakeFiles/alpha.o', 'CMakeFiles/space name.o', 'CMakeFiles/alias.o'] + args[9:]
    inputs = [A, B, A, SCRIPT, LIB, LIB, LIB]
    prelink = {'format': 'radishaxiom-private-cvc5-prelink-materials', 'version': '0.2',
               'scope': 'offline-retained-byte-consistency', 'recipe_sha256': recipe_digest,
               'phase_declarations_sha256': phase_ref['sha256'], 'capture': capture_ref, 'generated_link': link_ref,
               'files': files, 'aliases': [{'path': CWD + '/CMakeFiles/alias.o', 'target': 'alpha.o'}],
               'default_search_roots': ['/usr/lib/aarch64-linux-gnu'], 'expanded_arguments': expanded,
               'input_sequence': inputs, 'implicit_inputs': [CRT, SPECS], 'actual_link': None}
    write(directory, 'prelink.json', encoded(prelink))
    return phases, prelink


def verify_recipe(recipe):
    demand(digest(read(OLD)) == OLD_SHA, 'old-recipe-byte-drift')
    old = parse(read(OLD))
    demand(recipe['version'] == '0.2' and recipe['build_ready'] is False
           and recipe['execution_ready'] is False and recipe['acceptance'] == 'not-accepted'
           and recipe['executed_recipe_steps'] == [], 'recipe-overclaim')
    demand(recipe['phase_plan'] == phase_plan(), 'phase-plan')
    demand(recipe['dependency_steps'] == old['dependency_steps'], 'dependency-command-drift')
    demand(recipe['policy']['resources'] == old['policy']['resources'], 'resource-drift')
    demand(recipe['main_phase']['configuration'] == old['main_phase']['configuration'], 'configuration-drift')
    for ref in recipe['references']:
        raw = read(ROOT / ref['path'])
        demand(len(raw) == ref['bytes'] and digest(raw) == ref['sha256'], 'method-reference')
    record = parse(read(ROOT / 'docs/records/solver-cvc5-source-review-2026-10-17/patch-review.json'))
    # Use the already retained, statically prepared C0 review tree as an
    # independent before image, rather than the new production patch applier.
    base = ROOT / record['derived_review_root']
    rows = []
    for path in sorted(base.rglob('*')):
        mode = path.lstat().st_mode
        demand(not stat.S_ISLNK(mode), 'review-tree-symlink')
        if stat.S_ISDIR(mode):
            continue
        demand(stat.S_ISREG(mode), 'review-tree-special-file')
        raw = read(path)
        rows.append({'path': path.relative_to(base).as_posix(), 'bytes': len(raw),
                     'raw_digest': 'sha256:' + digest(raw), 'executable': bool(mode & 0o111)})
    rows.sort(key=lambda r: r['path'])
    before = 'sha256:' + digest(canonical(rows))
    demand(before == record['after']['inventory_digest'], 'old-review-tree-drift')
    transform = recipe['transformations']['cvc5_final_link']
    demand(transform['before_tree_digest'] == before, 'new-patch-before-tree')
    name = 'src/main/CMakeLists.txt'
    original = read(base / name)
    lines = original.splitlines(keepends=True)
    demand(lines[58].startswith(b'target_compile_definitions(cvc5-bin '), 'fixed-main-line')
    addition = (b'# Local provenance boundary: capture only; the controller links frozen inputs.\n'
                b'set_property(TARGET cvc5-bin PROPERTY CXX_LINKER_LAUNCHER\n'
                b'  "/usr/bin/python3.11;/recipe/scripts/cvc5-build-support/capture_link.py;--output;'
                b'/work/evidence/cvc5-link-capture.json;--")\n')
    expected = b''.join(lines[:59]) + addition + b''.join(lines[59:])
    for row in rows:
        if row['path'] == name:
            row.update(bytes=len(expected), raw_digest='sha256:' + digest(expected))
    demand(transform['changed_files'] == [name] and transform['after_file_sha256'] == digest(expected)
           and transform['before_file_sha256'] == digest(original)
           and transform['after_tree_digest'] == 'sha256:' + digest(canonical(rows)), 'new-patch-after-tree')
    return {'old_recipe_unchanged': True, 'dependency_steps': len(old['dependency_steps']),
            'combined_tree_files': len(rows), 'scope': 'independent-static-text-and-byte-review'}


def check_export(directory, export):
    phases = parse(read(directory / 'phases.json'))
    inputs = parse(read(directory / 'prelink.json'))
    result = parse(read(export))
    demand(result['scope'] == 'offline-declaration-consistency-only'
           and result['checked_prefix'] == ['dependencies', 'main-compile'], 'export-scope')
    demand(result['phase_declarations_sha256'] == digest(read(directory / 'phases.json'))
           and result['link_declarations_sha256'] == digest(read(directory / 'prelink.json')), 'export-input-binding')
    for value in (result, result['link_materials']):
        demand(value['build_ready'] is False and value['execution_ready'] is False
               and value['runtime_qualification'] is False and value['acceptance'] == 'not-accepted', 'export-overclaim')
    available = {r['id']: r['sha256'] for r in phases['external_inputs']}
    for stage in phases['stages']:
        available.update({r['id']: r['sha256'] for r in stage['outputs']})
    demand(result['unverified_outputs'] == available, 'export-stage-outputs')
    link = result['link_materials']
    demand(link['scope'] == 'offline-prelink-byte-consistency-only'
           and link['input_sequence'] == [A, B, A, SCRIPT, LIB, LIB, LIB]
           and link['response_sequence'] == [CWD + '/CMakeFiles/objects.rsp', CWD + '/CMakeFiles/more.rsp'], 'export-order')
    demand(link['implicit_inputs'] == link['implicit_input_sequence'] == [CRT, SPECS]
           and link['implicit_input_completeness'] == 'not-established'
           and link['actual_member_extraction'] == 'not-observed' and link['without_use_observation'] == [], 'export-use-overclaim')
    library = next(r for r in inputs['files'] if r['path'] == LIB)
    raw = read(directory / library['file']['path'])
    expected_archive = b'!<arch>\n' + ar_member('duplicate.o/', elf(17)) + ar_member('duplicate.o/', elf(29))
    demand(raw == expected_archive, 'synthetic-archive-bytes')
    expected_members = [{'index': i, 'name': 'duplicate.o', 'occurrence': i + 1, 'kind': 'object',
                         'bytes': len(elf(n)), 'sha256': digest(elf(n))} for i, n in enumerate((17, 29))]
    demand(link['archive_members'] == {LIB: expected_members}, 'export-repeated-members')
    for item in [inputs['capture'], inputs['generated_link']] + [r['file'] for r in inputs['files']]:
        body = read(directory / item['path'])
        demand(len(body) == item['bytes'] and digest(body) == item['sha256'], 'retained-byte-drift')
    return {'scope': 'independent-synthetic-export-review', 'ordered_inputs': 7,
            'repeated_archive_members': 2, 'runtime_qualification': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--recipe', required=True, type=Path)
    prep.add_argument('--sha256', required=True)
    prep.add_argument('--directory', required=True, type=Path)
    check = sub.add_parser('check')
    check.add_argument('--recipe', required=True, type=Path)
    check.add_argument('--sha256', required=True)
    check.add_argument('--directory', required=True, type=Path)
    check.add_argument('--export', required=True, type=Path)
    args = parser.parse_args()
    raw = read(args.recipe)
    demand(digest(raw) == args.sha256, 'recipe-hash')
    recipe = parse(raw)
    summary = verify_recipe(recipe)
    if args.mode == 'prepare':
        prepare(recipe, args.sha256, args.directory)
        summary['synthetic_inputs_written'] = str(args.directory)
    else:
        summary['export_review'] = check_export(args.directory, args.export)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
