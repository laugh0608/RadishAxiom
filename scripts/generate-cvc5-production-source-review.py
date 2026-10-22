#!/usr/bin/env python3
"""Assemble manually reviewed C0 facts and source-byte bindings; execute no upstream code."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD_DIR = ROOT / 'docs/records/solver-cvc5-source-review-2026-10-17'
INPUTS = RECORD_DIR / 'source-inputs.json'
OUTPUT = RECORD_DIR / 'production-review.json'

# Human-selected evidence ranges; these are not a CMake evaluator.
FILES = {
    'cvc5/configure.sh': [(129, 180), (322, 324), (420, 518)],
    'cvc5/CMakeLists.txt': [(87, 181), (253, 349), (496, 674), (687, 706)],
    'cvc5/cmake/ConfigProduction.cmake': [(12, 26)],
    'cvc5/cmake/Helpers.cmake': [(26, 48), (180, 197), (277, 313)],
    'cvc5/cmake/ConfigureCvc5.cmake': [(22, 109)],
    'cvc5/cmake/deps-helper.cmake': [(16, 64), (92, 105)],
    'cvc5/cmake/FindGMP.cmake': [(104, 166), (175, 196)],
    'cvc5/cmake/FindCaDiCaL.cmake': [(99, 165)],
    'cvc5/cmake/FindPoly.cmake': [(57, 85), (140, 230)],
    'cvc5/cmake/FindEditline.cmake': [],
    'cvc5/cmake/FindSymFPU.cmake': [(35, 58)],
    'cvc5/cmake/version.cmake': [(24, 34), (71, 129)],
    'cvc5/cmake/version-base.cmake': [(1, 18)],
    'cvc5/cmake/IWYU.cmake': [(16, 34)],
    'cvc5/cmake/fuzzing-murxla.cmake': [(16, 48)],
    'cvc5/src/CMakeLists.txt': [(1351, 1353), (1410, 1437), (1502, 1510), (1582, 1610)],
    'cvc5/src/main/CMakeLists.txt': [(36, 57), (75, 108)],
    'cvc5/src/main/gen-token-header.sh': [(11, 13)],
    'cvc5/src/parser/CMakeLists.txt': [(27, 57), (61, 89)],
    'cvc5/src/base/CMakeLists.txt': [(43, 68)],
    'cvc5/src/base/cvc5config.h.in': [],
    'cvc5/src/expr/CMakeLists.txt': [(149, 179), (237, 259)],
    'cvc5/src/theory/CMakeLists.txt': [(22, 60)],
    'cvc5/src/rewriter/CMakeLists.txt': [(13, 14), (63, 89)],
    'cvc5/src/util/CMakeLists.txt': [(13, 15)],
    'cvc5/src/api/java/CMakeLists.txt': [(18, 35), (101, 104), (190, 210), (295, 308), (368, 400)],
    'cvc5/src/api/java/genenums.py.in': [],
    'cvc5/src/api/parseenums.py': [],
    'cvc5/test/CMakeLists.txt': [(32, 54)],
    'cvc5/test/api/CMakeLists.txt': [(13, 27)],
    'cvc5/.github/workflows/ci.yml': [(97, 107)],
    'cvc5/.github/actions/configure-and-build/action.yml': [(28, 68)],
    'gmp/configure': [(3709, 3726), (4411, 4417), (25599, 25655)],
    'gmp/Makefile.in': [(797, 824), (1455, 1497)],
    'gmp/mpn/Makefile.in': [(742, 768)],
    'gmp/demos/Makefile.am': [(42, 50)],
    'gmp/demos/calc/Makefile.in': [(173, 185), (384, 394), (549, 550)],
    'gmp/demos/calc/calc.c': [],
    'gmp/demos/calc/calc.h': [],
    'gmp/demos/calc/calclex.c': [],
    'gmp/ltmain.sh': [],
    'gmp/aclocal.m4': [],
    'gmp/config.in': [],
    'cadical/makefile.in': [(37, 78)],
    'cadical/scripts/make-build-header.sh': [(28, 95)],
    'cadical/scripts/get-git-id.sh': [(1, 3)],
    'libpoly/CMakeLists.txt': [(11, 17), (35, 83)],
    'libpoly/src/CMakeLists.txt': [(70, 93), (129, 144)],
    'libpoly/include/CMakeLists.txt': [(1, 10)],
}

GENERATOR_MODULES = [
    'src/base/collect_tags.py', 'src/expr/mkexpr.py', 'src/expr/mkkind.py',
    'src/expr/mkmetakind.py', 'src/expr/theory_validator.py', 'src/options/mkoptions.py',
    'src/rewriter/mkrewrites.py', 'src/rewriter/node.py', 'src/rewriter/rule.py',
    'src/rewriter/rw_parser.py', 'src/rewriter/util.py',
    'src/theory/mkrewriter.py', 'src/theory/mktheorytraits.py',
]


def binding(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw),
            'raw_digest': 'sha256:' + hashlib.sha256(raw).hexdigest()}


def generate():
    inputs = json.loads(INPUTS.read_text())
    roots = {row['id']: ROOT / row['source_root'] for row in inputs['sources']}
    files = {}
    selections = dict(FILES)
    for name in GENERATOR_MODULES:
        selections['cvc5/' + name] = []
    for name, ranges in selections.items():
        component, relative = name.split('/', 1)
        path = roots[component] / relative
        evidence = binding(path)
        evidence['retained_path'] = evidence.pop('path')
        lines = path.read_text().splitlines()
        evidence['excerpts'] = [
            {'start': start, 'end': end, 'text': '\n'.join(lines[start - 1:end])}
            for start, end in ranges]
        if any(end > len(lines) for _, end in ranges):
            raise ValueError('invalid manually selected evidence range: ' + name)
        files[name] = evidence

    config = []

    def add(name, baseline, candidate, note, evidence, assessment='static-determined'):
        config.append({'name': name, 'baseline_static': baseline, 'candidate': candidate,
                       'assessment': assessment, 'reason': note, 'evidence': evidence})

    common = ['cvc5/CMakeLists.txt', 'cvc5/configure.sh', 'cvc5/cmake/ConfigProduction.cmake',
              'cvc5/cmake/Helpers.cmake']
    add('CMAKE_BUILD_TYPE', 'Production', 'Production', 'production wrapper maps to Production', common)
    add('OPTIMIZATION_LEVEL', 3, 3, '-O3 addition depends on compiler flag check', common,
        'conditional-unverified')
    for name, value in [('ENABLE_ASSERTIONS', 'OFF'), ('ENABLE_DEBUG_SYMBOLS', 'OFF'),
                        ('ENABLE_STATISTICS', 'ON'), ('ENABLE_TRACING', 'OFF'),
                        ('ENABLE_MUZZLE', 'OFF'), ('ENABLE_UNIT_TESTING', 'OFF')]:
        add(name, value, value, 'Production cvc5_set_option; explicit user overrides must be excluded', common)
    for name in ('ENABLE_ASAN', 'ENABLE_UBSAN', 'ENABLE_TSAN', 'ENABLE_SAFE_MODE',
                 'ENABLE_STABLE_MODE', 'ENABLE_VALGRIND', 'ENABLE_IPO'):
        add(name, 'IGNORE (false in if)', 'OFF',
            'No Production setter or baseline argv enables it; explicit OFF freezes false branch', common)
    for name in ('ENABLE_CLANG_TIDY', 'ENABLE_COVERAGE', 'ENABLE_PROFILING',
                 'ENABLE_DEBUG_CONTEXT_MM', 'ENABLE_GPL', 'USE_CLN', 'USE_GLPK',
                 'USE_COCOA', 'USE_CRYPTOMINISAT', 'USE_KISSAT', 'USE_MPFR',
                 'NO_GLOBAL_POLY_CTX', 'BUILD_DOCS', 'BUILD_DOCS_GA', 'ONLY_PYTHON_EXT_SRC'):
        add(name, 'OFF', 'OFF', 'Two-valued option default; baseline does not override', common)
    for name in ('BUILD_CLN', 'SKIP_COMPRESS_DEBUG', 'SKIP_SET_RPATH', 'USE_DEFAULT_LINKER'):
        add(name, 'OFF', 'OFF', 'Preserve declared default; inactive branch is not deleted', common)
    for name in ('GLPK_DIR', 'PYTHONIC_PATH', 'PROGRAM_PREFIX', 'WASM_FLAGS'):
        add(name, '', '', 'No baseline override; no extra path/prefix/wasm flags', common)
    add('WASM', 'OFF', 'OFF', 'Linux native candidate; no emscripten wrapper', common)
    add('CMAKE_LANGUAGE_STANDARDS', 'C11/C++17; extensions OFF', 'C11/C++17; extensions OFF',
        'Do not silently change dialects; dependent sources retain their own dialects',
        ['cvc5/CMakeLists.txt', 'cvc5/cmake/FindGMP.cmake', 'cvc5/cmake/FindCaDiCaL.cmake',
         'libpoly/src/CMakeLists.txt'])
    add('ENABLE_PROOFS', 'Production setter present; option undeclared/unconsumed',
        'no new proof compile flag', 'Do not infer effective ON or a proof macro from stale setter',
        common + ['cvc5/src/CMakeLists.txt'])
    add('BUILD_SHARED_LIBS', 'OFF', 'OFF', '--static', common)
    add('STATIC_BINARY', 'ON (non-Darwin static default)', 'ON',
        'CLI static link flags; ELF outcome remains unverified', common + ['cvc5/src/main/CMakeLists.txt'])
    add('USE_EDITLINE', 'ON', 'ON', '--editline', common)
    add('USE_POLY', 'ON', 'ON', 'wrapper poly=ON, not bare CMake default', common)
    add('CaDiCaL', 'required', 'required', 'unconditional find/target dependency',
        ['cvc5/CMakeLists.txt', 'cvc5/src/CMakeLists.txt', 'cvc5/cmake/FindCaDiCaL.cmake'])
    add('SymFPU', 'required', 'required', 'unconditional even if MPFR used',
        ['cvc5/CMakeLists.txt', 'cvc5/src/CMakeLists.txt', 'cvc5/cmake/FindSymFPU.cmake'])
    add('BUILD_BINDINGS_PYTHON', 'ON requested then OFF for static', 'OFF',
        'CLI generators still need Python', common)
    add('BUILD_BINDINGS_JAVA', 'ON', 'OFF', 'separate forward-only JNI/JAR subgraph',
        ['cvc5/CMakeLists.txt', 'cvc5/src/api/java/CMakeLists.txt', 'cvc5/src/main/CMakeLists.txt'],
        'candidate-difference')
    add('ENABLE_AUTO_DOWNLOAD', 'ON', 'OFF', 'no build-time download/pip', common,
        'candidate-difference')
    add('USE_PYTHON_VENV', 'ON', 'OFF', 'fixed interpreter/modules replace auto venv', common,
        'candidate-difference')
    add('BUILD_GMP', '1', 'OFF; independently built same fixed GMP/GMPXX imported',
        'preserve original configure options and ABI; no outputs yet',
        ['cvc5/configure.sh', 'cvc5/cmake/FindGMP.cmake'], 'candidate-difference')
    add('TREAT_WARNING_AS_ERROR', 'ON plus exported CFLAGS/CXXFLAGS=-Werror',
        'ON plus explicit -Werror compile flags', 'wrapper semantics must be preserved', common)
    add('COMPILER_FLAGS', 'checked flags; actual unknown', 'same checked flag proposals',
        'flags and platform feature macros require compiler checks',
        ['cvc5/CMakeLists.txt', 'cvc5/cmake/Helpers.cmake', 'cvc5/cmake/ConfigureCvc5.cmake'],
        'conditional-unverified')
    add('CPU_ISA', 'GMP build triplet aarch64-linux-gnu; no cvc5 march=native',
        'fixed aarch64 toolchain; no native tuning', 'GMP ABI/assembly selection unverified',
        ['cvc5/cmake/Helpers.cmake', 'gmp/configure'], 'conditional-unverified')
    add('LINKER', 'aarch64 bypasses mold/gold detection', 'fixed linker/SDK tools',
        'actual command and implicit inputs still unknown', ['cvc5/CMakeLists.txt'],
        'conditional-unverified')
    add('CCACHE_LAUNCHER', 'ccache injected by CI action', 'empty launchers; clean build tree',
        'new bytes; no restored cache', ['cvc5/.github/actions/configure-and-build/action.yml'],
        'candidate-difference')
    add('GIT_VERSION', 'optional find_package Git and ancestor lookup', 'patch disables Git lookup',
        'preserve base 1.3.4; do not embed RadishAxiom identity',
        ['cvc5/cmake/version.cmake', 'cvc5/cmake/version-base.cmake'], 'candidate-difference')
    add('BUILD_TARGET', 'CI all/install/test/SDK package', 'cvc5-bin and required dependency targets',
        'no tests/examples/Murxla/JNI/JAR build',
        ['cvc5/src/main/CMakeLists.txt', 'cvc5/test/CMakeLists.txt', 'cvc5/cmake/fuzzing-murxla.cmake'],
        'candidate-difference')

    imports = []
    for relative in GENERATOR_MODULES:
        path = roots['cvc5'] / relative
        source = path.read_text()
        nodes = ast.walk(ast.parse(source))
        rows = [{'line': node.lineno, 'statement': ast.get_source_segment(source, node)}
                for node in nodes if isinstance(node, (ast.Import, ast.ImportFrom))]
        imports.append({'source': 'cvc5/' + relative, 'imports': sorted(rows, key=lambda row: row['line']),
                        'external_required': ['pyparsing'] if relative.endswith('rw_parser.py') else [],
                        'conditional_external': ['tomli if Python <3.11']
                        if 'import tomli as tomllib' in source else []})
    result = {
        'format': 'radishaxiom-private-cvc5-production-source-review', 'version': '0.1',
        'generator': 'scripts/generate-cvc5-production-source-review.py',
        'status': 'static-reviewed-not-configured-not-accepted',
        **{name: False for name in ('build_ready', 'configuration_executed', 'build_executed',
                                   'probe_executed', 'solver_executed', 'tool_accepted')},
        'assurance': 'manual static source review; hashes/excerpts are byte bindings, not independent semantic verification',
        'source_input_record': binding(INPUTS),
        'source_identities': [{'id': row['id'], 'source_root': row['source_root'],
                               'archive': row['archive'], 'tree_inventory': row['tree_inventory']}
                              for row in inputs['sources']],
        'source_files': files, 'configuration': config, 'python_generators': imports,
        'new_required_sdk_roots': ['python3-pyparsing', 'm4'],
        'not_required_new_roots': ['python3-tomli', 'autoconf', 'automake', 'libtool',
                                   'perl', 'bison', 'flex', 'texinfo', 'default-jdk',
                                   'python3-pip', 'python3-venv', 'clang-format', 'git'],
        'remaining_conditions': [
            'compiler flags, generated config headers and all configure feature checks unexecuted',
            'GMP ABI/assembler selection, m4 checks and compiled generation programs unexecuted',
            'CaDiCaL getc_unlocked/closefrom conditionals and build.hpp generation unexecuted',
            'Poly warning-flag/open_memstream checks and writable worktree generation unexecuted',
            'fixed SDK contents/signature/license/trust and generator API compatibility not accepted',
            'Editline pkg-config --static closure/order and actual archives remain missing',
            'patch is separately reviewed; future compiler/linker/ELF/map composition not established',
            'original resources/runtime arguments unchanged; E0/E4/E5 remain separate gates',
        ],
    }
    return result


if __name__ == '__main__':
    OUTPUT.write_text(json.dumps(generate(), ensure_ascii=False, indent=2) + '\n')
    print('generated static source review; no upstream execution or acceptance')
