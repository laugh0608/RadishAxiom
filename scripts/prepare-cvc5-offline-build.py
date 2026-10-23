#!/usr/bin/env python3
"""Render and check a fixed C2 build recipe without executing any recipe step.

No subprocess, network, extraction, SDK assembly, configure, build or removal
entry exists. A valid recipe is still blocked on license, tool and execution
acceptance. The later manifest-binding mode also only emits command data.
"""
import argparse
from collections import defaultdict
import contextlib
import datetime
import gzip
import hashlib
import importlib.util
import io
import itertools
import json
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_RECORDS = 'docs/records/solver-cvc5-source-review-2026-10-17/'
REVIEW_RECORDS = 'docs/records/solver-cvc5-c1-review-2026-10-23/'
SELF = 'scripts/prepare-cvc5-offline-build.py'
PROBES = 'scripts/cvc5-build-support/CMakeLists.txt'
COMMIT_RECORD = '.tmp/solver-cli-licenses-2026-10-17/cvc5-commit.json'
FORMAT = 'radishaxiom-private-cvc5-offline-build-recipe'
JSON_LIMIT = 16 * 1024**2
FILE_LIMIT = 1024**3
TOTAL_LIMIT = 4 * 1024**3
CC = '/usr/bin/aarch64-linux-gnu-gcc-12'
CXX = '/usr/bin/aarch64-linux-gnu-g++-12'
CMAKE = '/usr/bin/cmake'
MAKE = '/usr/bin/make'
BINUTILS = '/usr/bin/aarch64-linux-gnu-'
FLAGS = '--sysroot=/ -march=armv8-a -mtune=generic'
BLOCKERS = [
    'C1 fixed LibPoly license and old open_memstream provenance not accepted',
    'compiler/SDK/rootfs and native Linux AArch64 execution host not accepted',
    'SDK assembly and isolated build execution not authorized',
    'actual compiler searches/specs/CRT and pkgconf static closure not observed',
    'dependency outputs, ABI/closure review and main input manifest not produced',
    'resource estimates and runtime log/input monitoring not qualified',
]


def module(name, relative=None):
    spec = importlib.util.spec_from_file_location(name, ROOT / (relative or 'scripts/' + name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


PREP = module('cvc5-build-preparation')
BUILD = module('check-cvc5-build-inputs')
PRODUCTION = module('check-cvc5-production-source-review')
PATCH = module('check-cvc5-build-patch')
SOURCES = module('cvc5-c0-source-inputs')
CONTENT = module('cvc5_content_resolver', REVIEW_RECORDS + 'derive-content-review.py')
require = PREP.require


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def regular(path):
    require(path.is_absolute() and path.resolve() == path and not path.is_symlink(), 'noncanonical-file')
    require(stat.S_ISREG(path.stat().st_mode), 'not-regular-file')
    return path


def read_json(path):
    with regular(path).open('rb') as stream:
        raw = stream.read(JSON_LIMIT + 1)
    require(0 < len(raw) <= JSON_LIMIT, 'json-size-budget')
    return raw, json.loads(raw, object_pairs_hook=PREP.CHECK.reject_duplicates,
                           parse_constant=PREP.CHECK.reject_constant)


def relative_path(value):
    return BUILD.relative_value(value)


def local(value):
    return ROOT / relative_path(value)


def identity(path):
    path = regular(path)
    size = path.stat().st_size
    require(0 <= size <= JSON_LIMIT, 'reference-size-budget')
    raw = path.read_bytes()
    require(len(raw) == size, 'reference-changed-during-read')
    return {'path': str(path.relative_to(ROOT)), 'bytes': size,
            'sha256': hashlib.sha256(raw).hexdigest()}


def check_file(row, budget):
    require(type(row['bytes']) is int and 0 <= row['bytes'] <= FILE_LIMIT, 'input-size-budget')
    BUILD.hash_value(row['sha256'])
    budget[0] += row['bytes']
    require(budget[0] <= TOTAL_LIMIT, 'total-input-byte-budget')
    path = regular(local(row['path']))
    require(path.stat().st_size == row['bytes'], 'input-size-mismatch:' + row['path'])
    h, count = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while raw := stream.read(min(1024**2, row['bytes'] - count + 1)):
            count += len(raw)
            require(count <= row['bytes'], 'input-grew-during-read')
            h.update(raw)
    require(count == row['bytes'] and h.hexdigest() == row['sha256'], 'input-digest-mismatch:' + row['path'])


def check_retained(plan, retained):
    rows = retained['inventory']
    require(len(rows) == len(plan['entries']) == 500, 'retained-count')
    require(retained['base_plan'] == identity(PREP.PLAN), 'retained-plan-binding')
    seen, budget = set(), [0]
    for n, (expected, row) in enumerate(zip(plan['entries'], rows), 1):
        require(type(row['index']) is int and row['index'] == n, 'retained-index-order')
        require(row['path'] not in seen, 'duplicate-retained-path')
        seen.add(row['path'])
        require(row['bytes'] == expected['declared_bytes']
                and row['sha256'] == expected['declared_sha256'], 'retained-selection-binding')
        check_file(row, budget)
    require(budget[0] == plan['summary']['total_bytes'] == 691605464, 'retained-total')
    return {'matched_files': len(rows), 'matched_bytes': budget[0]}


def sdk_inventory(retained, plan):
    _, derived = read_json(local(REVIEW_RECORDS + 'derived-content-review.json'))
    path = local(REVIEW_RECORDS + 'content-inventory.json.gz')
    expected = derived['inventory']
    actual = identity(path)
    require(all(actual[k] == expected[k] for k in ('bytes', 'sha256')), 'sdk-inventory-digest')
    with gzip.open(regular(path), 'rb') as stream:
        raw = stream.read(JSON_LIMIT + 1)
    require(0 < len(raw) <= JSON_LIMIT, 'sdk-expanded-budget')
    value = json.loads(raw, object_pairs_hook=PREP.CHECK.reject_duplicates,
                       parse_constant=PREP.CHECK.reject_constant)
    require(value['complete'] is True and value['installed'] is False
            and value['built'] is False and value['payload_executed'] is False, 'sdk-inventory-scope')
    for ref in value['inputs']:
        require(identity(local(ref['path'])) == ref, 'sdk-inventory-input-binding')
    observations = value['observations']
    expected_indices = {n for n, row in enumerate(plan['entries'], 1) if row['kind'] != 'orig'}
    require(len(observations) == len(expected_indices)
            and {o['index'] for o in observations} == expected_indices, 'sdk-observation-count')
    index, package_names = defaultdict(list), set()
    for obs in observations:
        n = obs['index']
        require(type(n) is int and obs['kind'] == plan['entries'][n - 1]['kind'], 'sdk-observation-kind')
        kept = retained['inventory'][n - 1]
        require(obs['input'] == {k: kept[k] for k in ('path', 'bytes', 'sha256')},
                'sdk-observation-input-binding')
        if obs['kind'] != 'binary':
            continue
        require(obs['package'] not in package_names, 'duplicate-sdk-package')
        package_names.add(obs['package'])
        for entry in obs['data']['entries']:
            SOURCES.path_name(entry['path'])
            if entry['kind'] != 'directory':
                index[entry['path']].append({**entry, 'package': obs['package'], 'version': obs['version']})
    require(len(package_names) == 172, 'sdk-package-count')
    for rows in index.values():
        require(len({(x['kind'], x.get('sha256'), x.get('target'), x['mode']) for x in rows}) == 1,
                'sdk-path-collision')
    tools = [CC, CXX, CMAKE, MAKE, '/usr/bin/python3.11', '/usr/bin/pkgconf', '/usr/bin/m4',
             '/usr/bin/gawk', '/bin/sh', '/bin/bash', '/bin/sed', '/bin/grep', '/usr/bin/env']
    tools += [BINUTILS + name for name in ('ld.bfd', 'ar', 'ranlib', 'as', 'strip', 'nm', 'readelf', 'objdump')]
    selected = {}
    for name in tools:
        resolved = CONTENT.resolve(index, name)
        require(resolved['status'] == 'resolved', 'sdk-tool-missing:' + name)
        require(all(int(row['mode'], 8) & 0o111 for row in resolved['files']), 'sdk-tool-not-executable')
        selected[name] = resolved
    require('usr/bin/git' not in index and 'bin/git' not in index, 'unexpected-git-in-sdk')
    for row in derived['pkgconfig_texts']:
        check_file({'path': row['review_text_path'], 'bytes': row['bytes'], 'sha256': row['sha256']}, [0])
    return {'inventory': actual, 'tools': selected, 'package_count': len(package_names),
            'pkgconfig_files': derived['pkgconfig_texts'], 'assembly_executed': False,
            'whole_package_inventory_is_lookup_allowlist': True}


def batch_path(batch_id):
    require(isinstance(batch_id, str) and re.fullmatch('[a-z][a-z0-9-]{0,47}', batch_id), 'unsafe-batch-id')
    parent = ROOT / 'artifacts'
    require(parent.is_dir() and parent.resolve() == parent, 'batch-parent-not-canonical')
    path = parent / ('cvc5-build-' + batch_id)
    require(not path.exists() and not path.is_symlink(), 'batch-already-occupied')
    return str(path)


def command(name, argv, cwd='/work', env=None):
    require(isinstance(argv, list) and all(isinstance(x, str) and '\x00' not in x for x in argv), 'invalid-argv')
    return {'id': name, 'operation': 'command', 'argv': argv, 'cwd': cwd,
            'environment': 'base-plus-explicit-overrides', 'overrides': env or {},
            'stdout': '/work/logs/' + name + '/stdout.bin',
            'stderr': '/work/logs/' + name + '/stderr.bin',
            'receipt': '/work/logs/' + name + '/receipt.json',
            'on_failure': 'stop-entire-batch-retain-everything-no-retry'}


def cmake_args(source, build, label):
    return [CMAKE, '--trace-expand', '--trace-format=json-v1',
            '--trace-redirect=/work/logs/' + label + '/cmake-trace.jsonl',
            '--debug-trycompile', '-S', source, '-B', build, '-G', 'Unix Makefiles',
            '-DCMAKE_MAKE_PROGRAM=' + MAKE, '-DCMAKE_C_COMPILER=' + CC, '-DCMAKE_CXX_COMPILER=' + CXX,
            '-DCMAKE_AR=' + BINUTILS + 'ar', '-DCMAKE_RANLIB=' + BINUTILS + 'ranlib',
            '-DCMAKE_LINKER=' + BINUTILS + 'ld.bfd', '-DCMAKE_STRIP=' + BINUTILS + 'strip',
            '-DCMAKE_SYSROOT=/', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
            '-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF', '-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF',
            '-DCMAKE_FIND_USE_CMAKE_ENVIRONMENT_PATH=OFF', '-DCMAKE_FIND_USE_SYSTEM_ENVIRONMENT_PATH=OFF',
            '-DCMAKE_DISABLE_FIND_PACKAGE_Git=ON', '-DCMAKE_PREFIX_PATH=',
            '-DCMAKE_C_COMPILER_LAUNCHER=', '-DCMAKE_CXX_COMPILER_LAUNCHER=',
            '-DCMAKE_C_LINKER_LAUNCHER=', '-DCMAKE_CXX_LINKER_LAUNCHER=']


def cadical_makefile(raw, unlocked, closefrom):
    require(type(unlocked) is bool and type(closefrom) is bool, 'probe-values-not-booleans')
    flags = '-fPIC -O3 -DNDEBUG -DQUIET -std=c++11 ' + FLAGS
    if not unlocked:
        flags += ' -DNUNLOCKED'
    if not closefrom:
        flags += ' -DNCLOSEFROM'
    # Same four substitutions as the pinned FindCaDiCaL; @ROOT@ is absent in
    # this template. Other unused placeholders are deliberately not invented.
    body = raw.decode('utf-8')
    for token, replacement in (('@CXX@', CXX), ('@CXXFLAGS@', flags),
                               ('@ROOT@', '/work/src/cadical'), ('@CONTRIB@', 'no')):
        body = '\n'.join(line.replace(token, replacement, 1) for line in body.split('\n'))
    return body.encode()


def poly_cmake(raw):
    # Exact equivalent of the pinned static-install sed: preserve all other bytes.
    removed, kept = [], []
    for line in raw.splitlines(keepends=True):
        (removed if re.search(rb'TARGETS (poly|polyxx|static_poly|static_polyxx) ', line) else kept).append(line)
    require(len(removed) == 6, 'poly-install-transform-source-drift')
    return b''.join(kept)


def transformations(source_records):
    roots = {row['id']: local(row['source_root']) for row in source_records['sources']}
    original = (roots['cadical'] / 'makefile.in').read_bytes()
    variants = []
    for unlocked, closefrom in itertools.product((False, True), repeat=2):
        body = cadical_makefile(original, unlocked, closefrom)
        variants.append({'when': {'unlocked_io': unlocked, 'closefrom': closefrom},
                         'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                         'generator': 'cadical_makefile(original, unlocked_io, closefrom)'})
    poly = (roots['libpoly'] / 'src/CMakeLists.txt').read_bytes()
    after = poly_cmake(poly)
    return {'cadical': {'source': identity(roots['cadical'] / 'makefile.in'),
                       'destination': '/work/src/cadical/build/makefile', 'variants': variants,
                       'retain_preimage_as': '/work/src/cadical/build/makefile.orig'},
            'libpoly': {'source': identity(roots['libpoly'] / 'src/CMakeLists.txt'),
                        'destination': '/work/src/libpoly/src/CMakeLists.txt',
                        'bytes': len(after), 'sha256': hashlib.sha256(after).hexdigest(),
                        'generator': 'poly_cmake(original)',
                        'retain_preimage_as': '/work/src/libpoly/src/CMakeLists.txt.orig',
                        'global_context_patch': False, 'windows_patch': False},
            'cvc5': {'patch': identity(local('patches/cvc5/1.3.4/explicit-inputs.patch')),
                     'review': identity(local(SOURCE_RECORDS + 'patch-review.json')),
                     'application': 'check-cvc5-build-patch.apply_exact; no offset/fuzz; writable copy only'}}


def dependency_steps():
    steps = []
    for suffix, option in [('machine', '-dumpmachine'), ('version', '-dumpfullversion'),
                           ('search', '-print-search-dirs'), ('specs', '-dumpspecs')]:
        steps.append(command('compiler-' + suffix, [CC, '--sysroot=/', option]))
    for name in ('crt1.o', 'crti.o', 'crtn.o', 'crtbeginT.o', 'crtend.o', 'libgcc.a', 'libgcc_eh.a', 'libstdc++.a'):
        steps.append(command('compiler-file-' + name.replace('.', '-'), [CC, '--sysroot=/', '-print-file-name=' + name]))
    steps.append(command('editline-static', ['/usr/bin/pkgconf', '--static', '--cflags', '--libs', 'libedit']))
    steps.append({'id': 'tool-search-review', 'operation': 'review-gate',
                  'requires': ['native aarch64-linux-gnu GCC 12.2.0', 'all search/specs/CRT paths mapped to SDK inventory',
                               'pkgconf output retained in order including repeats; resolve every header/archive to inventory'],
                  'no_automatic_pass': True})
    probe_args = cmake_args('/recipe/probes', '/work/build/probes', 'dependency-probes')
    probe_args += ['-DCMAKE_C_STANDARD=11', '-DCMAKE_CXX_STANDARD=17',
                   '-DCMAKE_C_EXTENSIONS=OFF', '-DCMAKE_CXX_EXTENSIONS=OFF',
                   '-DCMAKE_C_FLAGS=-Werror ' + FLAGS, '-DCMAKE_CXX_FLAGS=-Werror ' + FLAGS]
    steps.append(command('dependency-probes', probe_args))
    steps.append({'id': 'probe-review', 'operation': 'review-gate',
                  'requires': ['probe-results.json digest plus cache/trace and compiler diagnostics',
                               'reject infrastructure/tool errors; a false capability alone does not justify ignoring errors',
                               'select exactly one recorded macro/flag branch; never default missing results to false'],
                  'no_automatic_pass': True})
    steps += [command('gmp-configure', ['/bin/sh', '/work/src/gmp/configure', '--disable-shared',
                                     '--enable-static', '--prefix=/work/prefix/gmp', '--with-pic',
                                     '--enable-cxx', '--build=aarch64-linux-gnu'], '/work/src/gmp',
                      {'CC': CC, 'CXX': CXX, 'CC_FOR_BUILD': CC, 'CFLAGS': '-std=gnu99 ' + FLAGS,
                       'CXXFLAGS': FLAGS, 'MAKEINFO': '/bin/true'}),
              command('gmp-build', [MAKE, '-j4', 'V=1'], '/work/src/gmp'),
              command('gmp-prefix-install', [MAKE, '-j1', 'install', 'V=1'], '/work/src/gmp')]
    steps.append({'id': 'gmp-output-review', 'operation': 'review-gate',
                  'requires': ['actual gmp.h/gmpxx.h and libgmp.a/libgmpxx.a bytes, generated inputs and config.log',
                               'compiler/ABI and archive-member review before Poly uses GMP'], 'no_automatic_pass': True})
    steps.append({'id': 'cadical-prepare', 'operation': 'write-selected-transformation',
                  'from': 'transformations.cadical', 'selection': 'reviewed probe-results',
                  'require_new_destination': True, 'preserve_preimage': True})
    steps += [command('cadical-build', [MAKE, '-C', '/work/src/cadical/build', '-j4', 'libcadical.a']),
              command('cadical-library-copy', [CMAKE, '-E', 'copy', '/work/src/cadical/build/libcadical.a',
                                             '/work/prefix/cadical/lib/libcadical.a']),
              command('cadical-headers-copy', [CMAKE, '-E', 'copy', '/work/src/cadical/src/cadical.hpp',
                                             '/work/src/cadical/src/tracer.hpp', '/work/prefix/cadical/include/cadical/'])]
    steps.append({'id': 'poly-prepare', 'operation': 'apply-recorded-transformation',
                  'from': 'transformations.libpoly', 'require_preimage_match': True, 'preserve_preimage': True})
    poly = cmake_args('/work/src/libpoly', '/work/build/poly', 'poly-configure')
    poly += ['-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=/work/prefix/poly',
             '-DLIBPOLY_BUILD_PYTHON_API=OFF', '-DLIBPOLY_BUILD_STATIC=ON', '-DLIBPOLY_BUILD_STATIC_PIC=ON',
             '-DGMP_INCLUDE_DIR=/work/prefix/gmp/include', '-DGMP_LIBRARY=/work/prefix/gmp/lib/libgmp.a',
             '-DCMAKE_SKIP_INSTALL_ALL_DEPENDENCY=TRUE', '-DBUILD_TESTING=OFF', '-DCMAKE_C_FLAGS=' + FLAGS]
    steps.append({'id': 'poly-configure-choice', 'operation': 'select-command',
                  'selector': 'reviewed probe-results.deprecated_literal_flag',
                  'choices': [{'when': flag, 'step': command('poly-configure', poly + ['-DCMAKE_CXX_FLAGS=' + FLAGS +
                      (' -Wno-error=deprecated-literal-operator' if flag else '')])} for flag in (False, True)]})
    steps += [command('poly-build', [MAKE, '-C', '/work/build/poly', '-j4', 'VERBOSE=1', 'static_pic_poly', 'static_pic_polyxx']),
              command('poly-prefix-install', [MAKE, '-C', '/work/build/poly', '-j1', 'VERBOSE=1', 'install', 'static_pic_poly', 'static_pic_polyxx']),
              command('poly-library-copy', [CMAKE, '-E', 'copy', '/work/build/poly/src/libpicpoly.a',
                                          '/work/build/poly/src/libpicpolyxx.a', '/work/prefix/poly/lib/'])]
    for part in ('core', 'utils'):
        steps.append(command('symfpu-' + part, [CMAKE, '-E', 'copy_directory', '/work/src/symfpu/' + part,
                                               '/work/prefix/symfpu/include/symfpu/' + part]))
    steps.append({'id': 'dependency-manifest-review', 'operation': 'review-gate',
                  'requires': ['complete actual six-role header inventories and actual archive identities',
                               'static-closure-and-abi-reviewed record with exact Editline order',
                               'reviewed-for-configuration manifest; check-cvc5-build-inputs.py must pass'],
                  'no_automatic_pass': True})
    return steps


def cvc5_commands(config, manifest_sha256):
    BUILD.hash_value(manifest_sha256)
    args = cmake_args('/work/src/cvc5', '/work/build/cvc5', 'cvc5-configure')
    # Include only genuine CMake cache choices; descriptive review rows are not flags.
    for row in config:
        if row['candidate'] in ('ON', 'OFF', '', 'Production') or type(row['candidate']) is int:
            args.append('-D' + row['name'] + '=' + str(row['candidate']))
    args += ['-DBUILD_GMP=OFF', '-DTREAT_WARNING_AS_ERROR=ON', '-DCMAKE_C_FLAGS=-Werror ' + FLAGS,
             '-DCMAKE_CXX_FLAGS=-Werror ' + FLAGS, '-DPython_EXECUTABLE=/usr/bin/python3.11',
             '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=bfd -Wl,-Map,/work/evidence/cvc5.map,--cref,-t,-t',
             '-DCVC5_C0_INPUT_MANIFEST=/work/review/build-inputs.json',
             '-DCVC5_C0_INPUT_MANIFEST_SHA256=' + manifest_sha256]
    return [command('cvc5-configure', args),
            {'id': 'main-effective-config-review', 'operation': 'review-gate', 'no_automatic_pass': True,
             'requires': ['effective cache/trace matches frozen Production matrix and exact input manifest',
                          'native Linux aarch64 branch; GCC uses inventoried ld.bfd, no mold/gold override',
                          'no unlisted tools/search roots, download, cache, launcher or option drift',
                          'snapshot configure logs/maps before build; missing or truncated observations stop']},
            command('cvc5-build', [CMAKE, '--build', '/work/build/cvc5', '--target', 'cvc5-bin', '--parallel', '4', '--verbose']),
            command('retain-unstripped', [CMAKE, '-E', 'copy', '/work/build/cvc5/bin/cvc5', '/work/output/cvc5.unstripped']),
            command('strip-copy', [BINUTILS + 'strip', '--strip-all', '-o', '/work/output/cvc5.stripped', '/work/output/cvc5.unstripped']),
            command('elf-readelf', [BINUTILS + 'readelf', '-aW', '/work/output/cvc5.unstripped']),
            command('elf-stripped-readelf', [BINUTILS + 'readelf', '-aW', '/work/output/cvc5.stripped'])]


def evidence_policy():
    return {'per_command_receipt': ['recipe SHA256', 'step id', 'exact argv/cwd/environment', 'stdin disposition',
                                    'start/end wall and monotonic times', 'exit/signal/timeout/cancel reason',
                                    'stdout/stderr bytes and SHA256', 'truncation/overflow flags', 'resource high-water marks'],
            'log_limits': {'stdout_per_step_bytes': 256 * 1024**2, 'stderr_per_step_bytes': 64 * 1024**2,
                           'cmake_trace_per_step_bytes': 512 * 1024**2, 'all_logs_bytes': 2 * 1024**3,
                           'events_jsonl_bytes': 32 * 1024**2, 'inventory_bytes': 64 * 1024**2},
            'overflow': 'stop batch, retain partial stream and failure receipt; never truncate and report success',
            'retain': ['original inputs and frozen recipe', 'patch and transformation before/after bytes and trees',
                       'CMakeCache.txt, CMakeFiles, trace, configure output/error and try-compile directories',
                       'GMP config.log/status/h, generated headers/tables/m4/Makefiles/libtool',
                       'CaDiCaL build.hpp plus actual date/uname/compiler metadata',
                       'compile_commands, every generated Makefile/link.txt/flags.make and compiler .d/.o',
                       'archives with ordered members, duplicate-name occurrences and each member digest',
                       'complete link argv, response files, linker scripts, map, cross-reference and -t -t trace',
                       'unstripped and stripped ELF, strip argv, static review and all failure logs'],
            'link_manifest': {'path': '/work/evidence/link-inputs.json', 'generated_from': 'actual link; never planned -l list',
                              'fields': ['link argv and cwd', 'ordered expanded arguments preserving repetitions',
                                         'response/script path+bytes+sha256 and recursion order',
                                         'every object/archive and source/package ownership',
                                         'ordered archive members with occurrence index; extracted members and triggering symbols',
                                         'CRT/specs/default libraries, discarded sections and LTO observations',
                                         'actual header and generator dependencies', 'map/trace completeness and output ELF hashes'],
                              'reject': ['unmapped input', 'missing/truncated stream/map/response', 'extra library',
                                         'unreviewed search directory', 'changed patch/options', 'LTO enabled',
                                         'map vs declared manifest mismatch']},
            'assurance': 'capture and reconciliation contract only; no actual map, syscall read trace or hermeticity claim'}


def policy(batch_id, epoch):
    return {'host_batch_directory': batch_path(batch_id), 'namespace': {'sdk': '/', 'work': '/work', 'recipe': '/recipe'},
            'isolation': {'network': 'none', 'rootfs': 'only inventoried SDK payload, read-only after separately reviewed assembly',
                          'work': 'new empty unique writable batch, no previous caches', 'recipe': 'read-only self-authored files',
                          'forbidden_mounts': ['host root/usr/home', 'daemon socket', 'credentials', 'shared caches'],
                          'identity': 'unprivileged isolated uid; no capabilities; no-new-privileges',
                          'host_requirement': 'native Linux AArch64; no cross/emulated fallback',
                          'adapter': 'not selected or executed; must enforce/read back limits before any tool step'},
            'resources': {'jobs': 4, 'memory_bytes': 8 * 1024**3, 'swap_bytes': 0,
                          'writable_bytes': 20 * 1024**3, 'deadline_seconds': 5400,
                          'finalization_reserve_bytes': 128 * 1024**2, 'termination_reserve_seconds': 60,
                          'status': 'unmeasured-proposal-not-execution-authorization'},
            'environment': {'inherit': False, 'umask': '022', 'stdin': 'closed',
                            'values': {'PATH': '/usr/bin:/bin', 'HOME': '/work/home', 'TMPDIR': '/work/tmp',
                                       'LANG': 'C', 'LC_ALL': 'C', 'TZ': 'UTC', 'SOURCE_DATE_EPOCH': str(epoch),
                                       'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                                       'PKG_CONFIG_LIBDIR': '/usr/lib/aarch64-linux-gnu/pkgconfig:/usr/share/pkgconfig',
                                       'PKG_CONFIG_SYSROOT_DIR': '/', 'AWK': '/usr/bin/gawk',
                                       'SHELL': '/bin/sh', 'CONFIG_SHELL': '/bin/sh',
                                       'AR': BINUTILS + 'ar', 'AS': BINUTILS + 'as', 'LD': BINUTILS + 'ld.bfd',
                                       'NM': BINUTILS + 'nm', 'RANLIB': BINUTILS + 'ranlib'},
                            'absent': ['CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH', 'LD_LIBRARY_PATH',
                                       'LD_PRELOAD', 'PYTHONPATH', 'PYTHONHOME', 'PKG_CONFIG_PATH', 'MAKEFLAGS', 'MFLAGS',
                                       'CONFIG_SITE', 'CFLAGS', 'CXXFLAGS', 'CPPFLAGS', 'LDFLAGS', 'CCACHE_DIR',
                                       'GCC_EXEC_PREFIX', 'COMPILER_PATH', 'BASH_ENV', 'ENV', 'CMAKE_PREFIX_PATH'],
                            'epoch_caveat': 'CaDiCaL date/uname and generator local-date calls may ignore epoch; preserve observed bytes'},
            'failure': {'first_failure': 'terminate entire isolated process group/cgroup; no next stage, retry, network or budget increase',
                        'infrastructure_probe_error': 'stop; do not reinterpret as absent feature',
                        'on_cancel_or_supervisor_loss': 'same termination and preservation; qualify independently before execution',
                        'preserve': 'all partial inputs, sources, objects, logs and outputs; append terminal failure receipt'},
            'cleanup': {'automatic_deletion': False, 'shell_delete_commands': [],
                        'after_failure': 'only stop/remove exact ephemeral execution instance after bind-mounted records are retained',
                        'batch_data': 'retain entire resolved host_batch_directory until explicit cleanup approval',
                        'later_cleanup': 'enumerate exact owned paths with types/digests; reject symlinks/outside root; delete only approved list',
                        'never_delete': ['original source/SDK packages', 'C0/C1 evidence', 'previous failures', 'shared tools', 'repository or broad .tmp']}}



def support_files():
    """Bind the local Python import closure needed by the later read-only binder."""
    pending = [PREP, BUILD, PRODUCTION, PATCH, SOURCES, CONTENT]
    found = {SELF}
    while pending:
        value = pending.pop()
        path = Path(value.__file__).resolve()
        if not path.is_relative_to(ROOT):
            continue
        name = str(path.relative_to(ROOT))
        if name in found:
            continue
        found.add(name)
        for child in vars(value).values():
            if isinstance(child, type(PREP)) and getattr(child, '__file__', None):
                child_path = Path(child.__file__).resolve()
                if child_path.is_relative_to(ROOT):
                    pending.append(child)
    return sorted(found)


def generate(batch_id):
    plan = PREP.verify_plan()
    _, retained = read_json(local(REVIEW_RECORDS + 'retained-inventory.json'))
    matched = check_retained(plan, retained)
    sdk = sdk_inventory(retained, plan)
    # Existing bounded archive readers only read/decompress; never materialize or run payloads.
    with contextlib.redirect_stdout(io.StringIO()):
        SOURCES.verify()
    _, sources = read_json(local(SOURCE_RECORDS + 'source-inputs.json'))
    for source in sources['sources']:
        base = local(source['source_root'])
        require(base.resolve() == base and base.is_dir(), 'source-root-noncanonical')
        _, tree = read_json(local(source['tree_inventory']['path']))
        for entry in tree['entries']:
            if entry['kind'] == 'file':
                path = base.parent / entry['path']
                require(stat.S_IMODE(path.stat().st_mode) == 0o600, 'source-quarantine-mode-drift')
    _, production = read_json(local(SOURCE_RECORDS + 'production-review.json'))
    PRODUCTION.verify(production, ROOT)
    _, patch = read_json(local(SOURCE_RECORDS + 'patch-review.json'))
    cvc5 = next(x for x in sources['sources'] if x['id'] == 'cvc5')
    PATCH.inspect(local(cvc5['source_root']), local('patches/cvc5/1.3.4/explicit-inputs.patch'), patch)
    _, commit = read_json(local(COMMIT_RECORD))
    require(commit['sha'] == BUILD.COMMIT, 'epoch-source-commit')
    epoch = int(datetime.datetime.fromisoformat(commit['commit']['committer']['date'].replace('Z', '+00:00')).timestamp())
    refs = [SELF, PROBES, 'scripts/check-cvc5-build-inputs.py', 'scripts/check-cvc5-build-patch.py',
            'scripts/check-cvc5-production-source-review.py', 'scripts/cvc5-c0-source-inputs.py',
            'scripts/cvc5-build-preparation.py', REVIEW_RECORDS + 'derive-content-review.py',
            SOURCE_RECORDS + 'source-inputs.json', SOURCE_RECORDS + 'production-review.json',
            SOURCE_RECORDS + 'patch-review.json', REVIEW_RECORDS + 'retained-inventory.json',
            REVIEW_RECORDS + 'derived-content-review.json', REVIEW_RECORDS + 'historical-verification.json',
            REVIEW_RECORDS + 'libpoly-history-index.json', COMMIT_RECORD,
            'patches/cvc5/1.3.4/explicit-inputs.patch', str(PREP.PLAN.relative_to(ROOT))]
    refs = sorted(set(refs) | set(support_files()))
    recipe_files = {name: '/recipe/' + name for name in support_files()}
    recipe_files[SOURCE_RECORDS + 'production-review.json'] = '/recipe/' + SOURCE_RECORDS + 'production-review.json'
    recipe_files[PROBES] = '/recipe/probes/CMakeLists.txt'
    return {'format': FORMAT, 'version': '0.1', 'batch_id': batch_id, 'preparation_only': True,
            'execution_ready': False, 'build_ready': False, 'acceptance': 'not-accepted',
            'blocking_conditions': list(BLOCKERS), 'references': [identity(local(x)) for x in refs],
            'checked_inputs': {**matched, 'source_archives_and_trees': 5, 'patch_files': 8},
            'sdk': sdk, 'source_inputs': sources['sources'], 'policy': policy(batch_id, epoch),
            'staging': {'executed': False, 'prerequisite': 'C1 acceptance plus separate SDK assembly authorization',
                        'sdk': 'no apt/dpkg scripts; reviewed data payload assembly and full inventory/link/permission reconciliation',
                        'sources': 'copy five checked trees to /work/src/<id>; verify exact trees before transforms; never edit originals',
                        'source_modes': 'retained files are quarantined 0600; only in future copies restore 0755 when archive original_mode has execute bits, otherwise 0644; directories 0755; never restore setuid/setgid bits',
                        'source_links': 'preserve only archived verified internal symlinks; no host link resolution or new external targets',
                        'dependency_freeze': 'after prefix outputs and manifest review, freeze/remount exact prefix/header/archive inputs read-only and recheck identities before main configuration',
                        'recipe_files': recipe_files,
                        'new_directories': ['/work/home', '/work/tmp', '/work/logs', '/work/build', '/work/evidence', '/work/output',
                                            '/work/review', '/work/src/cadical/build', '/work/prefix/cadical/lib',
                                            '/work/prefix/cadical/include/cadical', '/work/prefix/poly/lib'],
                        'write_rules': 'create exclusively; original source preimages retained; output paths checked beneath fresh work root',
                        'step_log_directories': 'create exact per-step log directory before dispatch; refuse reuse'},
            'transformations': transformations(sources), 'dependency_steps': dependency_steps(),
            'main_phase': {'state': 'awaiting-real-reviewed-dependency-manifest',
                           'entry': 'bind-inputs: requires /work/review/build-inputs.json and its independently supplied SHA256',
                           'configuration': production['configuration'],
                           'argument_builder': SELF + ':cvc5_commands',
                           'pending_value': 'only actual manifest digest; no invented dependency output hashes',
                           'source_patch_gate': 'apply exact reviewed patch to independent cvc5 copy; check complete after-tree digest'},
            'evidence': evidence_policy(), 'executed_recipe_steps': []}


def write_new(path, value):
    require(path.is_absolute() and path.parent.is_dir() and path.parent.resolve() == path.parent,
            'output-parent-not-canonical')
    require(not path.exists() and not path.is_symlink(), 'output-already-exists')
    with path.open('xb') as stream:
        stream.write(encoded(value))


def checked_plan(path, sha256):
    BUILD.hash_value(sha256)
    raw, value = read_json(path)
    require(hashlib.sha256(raw).hexdigest() == sha256, 'recipe-hash-mismatch')
    require(isinstance(value, dict) and value.get('format') == FORMAT and value.get('version') == '0.1', 'recipe-format')
    require(PREP.CHECK.same_typed(value, generate(value['batch_id'])), 'recipe-drift')
    return value


def bind_inputs(plan_path, recipe_sha256, manifest_path, manifest_sha256):
    # Run in the future mounted namespace, after dependency review. This mode
    # only emits argv, and still does not authorize or execute any tool.
    BUILD.hash_value(recipe_sha256)
    raw, recipe = read_json(plan_path)
    require(hashlib.sha256(raw).hexdigest() == recipe_sha256, 'recipe-hash-mismatch')
    require(recipe['format'] == FORMAT and recipe['version'] == '0.1'
            and recipe['build_ready'] is False and recipe['execution_ready'] is False, 'recipe-boundary')
    for name in (SELF, 'scripts/check-cvc5-build-inputs.py', SOURCE_RECORDS + 'production-review.json'):
        rows = [x for x in recipe['references'] if x['path'] == name]
        require(len(rows) == 1 and identity(local(name)) == rows[0], 'recipe-entry-or-review-drift')
    _, production = read_json(local(SOURCE_RECORDS + 'production-review.json'))
    require(PREP.CHECK.same_typed(recipe['main_phase']['configuration'], production['configuration']),
            'main-configuration-drift')
    require(str(manifest_path) == '/work/review/build-inputs.json', 'manifest-namespace-path')
    result = BUILD.check(manifest_path, manifest_sha256)
    _, manifest = read_json(manifest_path)
    allowed_roots = ('/work/prefix/', '/usr/include/', '/usr/lib/')
    for row in list(manifest['header_roots'].values()) + list(manifest['archives'].values()):
        require(row['path'].startswith(allowed_roots), 'manifest-outside-build-namespace')
    require(manifest['closure_review']['path'].startswith('/work/review/'), 'closure-outside-review-namespace')
    return {'format': FORMAT + '-bound-main', 'version': '0.1', 'recipe_sha256': recipe_sha256,
            'manifest_sha256': manifest_sha256, 'byte_preflight': result,
            'steps': cvc5_commands(recipe['main_phase']['configuration'], manifest_sha256),
            'resolved_in_this_step': ['actual manifest byte and review-declaration binding only'],
            'execution_ready': False, 'build_ready': False, 'blocking_conditions': list(BLOCKERS),
            'executed_recipe_steps': []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    prepare = modes.add_parser('prepare')
    prepare.add_argument('--batch-id', required=True)
    prepare.add_argument('--output', type=Path, required=True)
    check = modes.add_parser('check')
    check.add_argument('plan', type=Path)
    check.add_argument('--sha256', required=True)
    bind = modes.add_parser('bind-inputs')
    bind.add_argument('plan', type=Path)
    bind.add_argument('--sha256', required=True)
    bind.add_argument('--manifest', type=Path, required=True)
    bind.add_argument('--manifest-sha256', required=True)
    bind.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.mode == 'prepare':
            value = generate(args.batch_id)
            write_new(args.output, value)
            print(json.dumps({'recipe_written': str(args.output), 'sha256': hashlib.sha256(encoded(value)).hexdigest(),
                              'checked_inputs': value['checked_inputs'], 'execution_ready': False, 'build_ready': False}))
            return 0
        if args.mode == 'check':
            value = checked_plan(args.plan, args.sha256)
            print(json.dumps({'preparation_check': 'passed', 'checked_inputs': value['checked_inputs'],
                              'blocking_conditions': value['blocking_conditions'], 'execution_ready': False, 'build_ready': False}))
            return 2
        result = bind_inputs(args.plan, args.sha256, args.manifest, args.manifest_sha256)
        write_new(args.output, result)
        print(json.dumps({'command_data_written': str(args.output), 'execution_ready': False, 'build_ready': False}))
        return 2
    except (ValueError, OSError, KeyError, TypeError, StopIteration) as exc:
        print(json.dumps({'preparation_check': 'failed', 'reason': str(exc), 'execution_ready': False, 'build_ready': False}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
