#!/usr/bin/env python3
"""Bind the private C0 static review to retained source bytes; never execute them."""

import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'docs/records/solver-cvc5-source-review-2026-10-17/production-review.json'
INPUTS = 'docs/records/solver-cvc5-source-review-2026-10-17/source-inputs.json'
COMMIT = 'f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341'
BASE = '.tmp/cvc5-c0-acquisition-2026-10-17/sources/'
IDENTITIES = {
    'cvc5': ('cvc5/cvc5-' + COMMIT, 'cbaa927c4d8085e38e7a097191bb9dd3a6780cc17fcde65cb156c9583e597760'),
    'cadical': ('cadical/cadical-rel-2.1.3-elevate', '15e1e82f7f9a9da0e97070cb8ac41d5b32139f65d54f72d2ff84849b0466ef92'),
    'symfpu': ('symfpu/symfpu-227a7246b8ce513b393cc2645d6d65d3490ea1de', 'ff22e37dbc133120ada5760878974811737bec65b12a8883f92b1ed9e3f96e99'),
    'libpoly': ('libpoly/libpoly-0.2.1', 'f9920afc876f998633348b9cbfcf180757ada48cc872040256c60ad0707b5a0f'),
    'gmp': ('gmp/gmp-6.3.0', 'ac28211a7cfb609bae2e2c8d6058d66c8fe96434f740cf6fe2e47b000d1c20cb'),
}
REQUIRED_CONFIG = set('''CMAKE_BUILD_TYPE OPTIMIZATION_LEVEL ENABLE_ASSERTIONS ENABLE_DEBUG_SYMBOLS
ENABLE_STATISTICS ENABLE_TRACING ENABLE_MUZZLE ENABLE_UNIT_TESTING ENABLE_ASAN ENABLE_UBSAN
ENABLE_TSAN ENABLE_SAFE_MODE ENABLE_STABLE_MODE ENABLE_VALGRIND ENABLE_IPO ENABLE_CLANG_TIDY
ENABLE_COVERAGE ENABLE_PROFILING ENABLE_DEBUG_CONTEXT_MM ENABLE_GPL USE_CLN USE_GLPK USE_COCOA
USE_CRYPTOMINISAT USE_KISSAT USE_MPFR NO_GLOBAL_POLY_CTX BUILD_DOCS BUILD_DOCS_GA ONLY_PYTHON_EXT_SRC
ENABLE_PROOFS BUILD_SHARED_LIBS STATIC_BINARY USE_EDITLINE USE_POLY CaDiCaL SymFPU
BUILD_CLN SKIP_COMPRESS_DEBUG SKIP_SET_RPATH USE_DEFAULT_LINKER GLPK_DIR PYTHONIC_PATH
PROGRAM_PREFIX WASM_FLAGS WASM CMAKE_LANGUAGE_STANDARDS
BUILD_BINDINGS_PYTHON BUILD_BINDINGS_JAVA ENABLE_AUTO_DOWNLOAD USE_PYTHON_VENV BUILD_GMP
TREAT_WARNING_AS_ERROR COMPILER_FLAGS CPU_ISA LINKER CCACHE_LAUNCHER GIT_VERSION BUILD_TARGET'''.split())
REQUIRED_MODULES = set('''src/base/collect_tags.py src/expr/mkexpr.py src/expr/mkkind.py
src/expr/mkmetakind.py src/expr/theory_validator.py src/options/mkoptions.py src/rewriter/mkrewrites.py
src/rewriter/node.py src/rewriter/rule.py src/rewriter/rw_parser.py src/rewriter/util.py
src/theory/mkrewriter.py src/theory/mktheorytraits.py'''.split())
REQUIRED_SOURCES = {'cvc5/' + name for name in REQUIRED_MODULES} | set('''
cvc5/configure.sh cvc5/CMakeLists.txt cvc5/cmake/ConfigProduction.cmake cvc5/cmake/Helpers.cmake
cvc5/cmake/ConfigureCvc5.cmake cvc5/cmake/deps-helper.cmake cvc5/cmake/FindGMP.cmake
cvc5/cmake/FindCaDiCaL.cmake cvc5/cmake/FindPoly.cmake cvc5/cmake/FindEditline.cmake
cvc5/cmake/FindSymFPU.cmake cvc5/cmake/version.cmake cvc5/cmake/version-base.cmake
cvc5/cmake/IWYU.cmake cvc5/cmake/fuzzing-murxla.cmake cvc5/src/CMakeLists.txt
cvc5/src/main/CMakeLists.txt cvc5/src/main/gen-token-header.sh cvc5/src/parser/CMakeLists.txt
cvc5/src/base/CMakeLists.txt cvc5/src/base/cvc5config.h.in cvc5/src/expr/CMakeLists.txt
cvc5/src/theory/CMakeLists.txt cvc5/src/rewriter/CMakeLists.txt cvc5/src/util/CMakeLists.txt
cvc5/src/api/java/CMakeLists.txt cvc5/src/api/java/genenums.py.in cvc5/src/api/parseenums.py
cvc5/test/CMakeLists.txt cvc5/test/api/CMakeLists.txt cvc5/.github/workflows/ci.yml
cvc5/.github/actions/configure-and-build/action.yml gmp/configure gmp/Makefile.in
gmp/mpn/Makefile.in gmp/demos/Makefile.am gmp/demos/calc/Makefile.in gmp/demos/calc/calc.c
gmp/demos/calc/calc.h gmp/demos/calc/calclex.c gmp/ltmain.sh gmp/aclocal.m4 gmp/config.in
cadical/makefile.in cadical/scripts/make-build-header.sh cadical/scripts/get-git-id.sh
libpoly/CMakeLists.txt libpoly/src/CMakeLists.txt libpoly/include/CMakeLists.txt'''.split())


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def checked_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or '.' in path.parts:
        raise ValueError('unsafe retained path: ' + relative)
    result = root
    for part in path.parts:
        result = result / part
        if result.is_symlink():
            raise ValueError('symlink source path: ' + relative)
    if not result.is_file():
        raise ValueError('source evidence is not a regular file: ' + relative)
    return result


def check_binding(root, row):
    path = checked_path(root, row['path'])
    raw = path.read_bytes()
    if len(raw) != row['bytes'] or digest(raw) != row['raw_digest']:
        raise ValueError('input binding differs: ' + row['path'])
    return raw


def verify(record, root):
    required = {'format', 'version', 'generator', 'status', 'build_ready', 'configuration_executed',
                'build_executed', 'probe_executed', 'solver_executed', 'tool_accepted', 'assurance',
                'source_input_record', 'source_identities', 'source_files', 'configuration',
                'python_generators', 'new_required_sdk_roots', 'not_required_new_roots',
                'remaining_conditions'}
    if set(record) != required:
        raise ValueError('missing or unknown review section')
    if record.get('format') != 'radishaxiom-private-cvc5-production-source-review':
        raise ValueError('unexpected review format')
    if record.get('version') != '0.1':
        raise ValueError('unsupported review version')
    for name in ('build_ready', 'configuration_executed', 'build_executed',
                 'probe_executed', 'solver_executed', 'tool_accepted'):
        if record.get(name) is not False:
            raise ValueError('static-only boundary violated: ' + name)
    if record.get('status') != 'static-reviewed-not-configured-not-accepted':
        raise ValueError('unexpected review status')
    if record['source_input_record']['path'] != INPUTS:
        raise ValueError('unexpected source-input record')
    input_raw = check_binding(root, record['source_input_record'])
    inputs = json.loads(input_raw, object_pairs_hook=reject_duplicates)
    identities = record['source_identities']
    if len(identities) != len(IDENTITIES) or {row['id'] for row in identities} != set(IDENTITIES):
        raise ValueError('source identity set differs')
    inventory_files = {}
    for row in identities:
        component = row['id']
        expected_root, expected_digest = IDENTITIES[component]
        if row['source_root'] != BASE + expected_root:
            raise ValueError('unexpected source root')
        if row['archive']['raw_digest'] != 'sha256:' + expected_digest:
            raise ValueError('unexpected fixed archive identity')
        selected = next((item for item in inputs['sources'] if item['id'] == component), None)
        if selected is None or any(row[key] != selected[key]
                                   for key in ('source_root', 'archive', 'tree_inventory')):
            raise ValueError('source identity differs from acquisition record')
        check_binding(root, row['archive'])
        inventory = json.loads(check_binding(root, row['tree_inventory']), object_pairs_hook=reject_duplicates)
        if inventory['source_id'] != component or inventory['archive'] != row['archive']:
            raise ValueError('tree inventory identity differs')
        inventory_files[component] = {entry['path']: entry for entry in inventory['entries']
                                      if entry['kind'] == 'file'}
    sources = record['source_files']
    if not isinstance(sources, dict) or set(sources) != REQUIRED_SOURCES:
        raise ValueError('source evidence set differs')
    for name, row in sources.items():
        component, suffix = name.split('/', 1)
        wanted = BASE + IDENTITIES[component][0] + '/' + suffix
        if row['retained_path'] != wanted:
            raise ValueError('source path is not bound to selected root: ' + name)
        path = checked_path(root, row['retained_path'])
        raw = path.read_bytes()
        if len(raw) != row['bytes'] or digest(raw) != row['raw_digest']:
            raise ValueError('source bytes differ: ' + name)
        member = IDENTITIES[component][0].split('/', 1)[1] + '/' + suffix
        archived = inventory_files[component].get(member)
        if archived is None or archived['bytes'] != row['bytes'] or 'sha256:' + archived['sha256'] != row['raw_digest']:
            raise ValueError('review evidence differs from archive inventory: ' + name)
        lines = raw.decode('utf-8').splitlines()
        for excerpt in row.get('excerpts', []):
            start, end = excerpt['start'], excerpt['end']
            if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
                raise ValueError('invalid evidence lines: ' + name)
            if '\n'.join(lines[start - 1:end]) != excerpt['text']:
                raise ValueError('source excerpt differs: ' + name)
    configuration = record['configuration']
    if len(configuration) != len(REQUIRED_CONFIG) or {row['name'] for row in configuration} != REQUIRED_CONFIG:
        raise ValueError('configuration matrix is incomplete or duplicated')
    for row in configuration:
        if not row.get('evidence') or any(name not in sources for name in row['evidence']):
            raise ValueError('configuration lacks source evidence: ' + row.get('name', '?'))
        if row.get('assessment') not in ('static-determined', 'conditional-unverified', 'candidate-difference'):
            raise ValueError('invalid static assessment')
    modules = record['python_generators']
    if len(modules) != len(REQUIRED_MODULES) or {row['source'] for row in modules} != {
            'cvc5/' + name for name in REQUIRED_MODULES}:
        raise ValueError('generator module set differs')
    for row in modules:
        path = checked_path(root, sources[row['source']]['retained_path'])
        source = path.read_text()
        actual = [{'line': node.lineno, 'statement': ast.get_source_segment(source, node)}
                  for node in ast.walk(ast.parse(source))
                  if isinstance(node, (ast.Import, ast.ImportFrom))]
        if row['imports'] != sorted(actual, key=lambda item: item['line']):
            raise ValueError('generator imports differ')
    if record['new_required_sdk_roots'] != ['python3-pyparsing', 'm4']:
        raise ValueError('required tool roots differ')
    if not isinstance(record['remaining_conditions'], list) or len(record['remaining_conditions']) != 8:
        raise ValueError('missing future configure/build conditions')
    return len(sources)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, default=RECORD)
    args = parser.parse_args()
    record = json.loads(args.record.read_text(), object_pairs_hook=reject_duplicates)
    count = verify(record, ROOT)
    print(f'checked {count} retained source files; static review only, no configure/build/acceptance')


if __name__ == '__main__':
    main()
