"""Read retained bytes and reconcile a pre-link declaration; never link/accept.

No map parser, complete implicit-input discovery or OS authenticity is claimed.
GNU syntax outside this fixed, documented subset is rejected for review.
"""
import hashlib
import importlib.util
from pathlib import Path
import re
import shlex


def load(name):
    spec = importlib.util.spec_from_file_location('cvc5_' + name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


R, F = load('phase_rules'), load('link_formats')
require, keys = R.require, R.keys
FORMAT = 'radishaxiom-private-cvc5-prelink-materials'
FILE_LIMIT, TOTAL_LIMIT, ENTRY_LIMIT = 1024**3, 4 * 1024**3, 100000
EXPANDED_LIMIT = 8 * 1024**2
PREFIX = ['/usr/bin/python3.11', '/recipe/scripts/cvc5-build-support/capture_link.py',
          '--output', R.CAPTURE_PATH, '--']
SAFE_FLAGS = {'-Werror', '-O3', '-DNDEBUG', '-static', '-pthread', '-rdynamic',
              '-static-libgcc', '-static-libstdc++', '-fPIC', '-fPIE',
              '-fvisibility=hidden', '-fvisibility-inlines-hidden', '-fno-extern-tls-init',
              '-fno-strict-aliasing', '-fno-exceptions', '-fno-rtti',
              '--sysroot=/', '-march=armv8-a', '-mtune=generic', '-fuse-ld=bfd'}


class RetainedFiles:
    """Canonical retained files and a virtual inventory; never resolve host SDK paths."""

    def __init__(self, root, c2):
        require(root.is_absolute() and root.resolve() == root and root.is_dir(), 'material-root')
        self.root, self.c2, self.total = root, c2, 0
        self.reads = {}

    def read(self, ref, limit=FILE_LIMIT):
        keys(ref, ('path', 'bytes', 'sha256'), 'material-file')
        relative = self.c2.relative_path(ref['path'])
        require(type(ref['bytes']) is int and 0 <= ref['bytes'] <= limit, 'material-file-budget')
        R.sha(ref['sha256'])
        if relative in self.reads:
            require(self.reads[relative] == ref, 'material-reference-conflict')
        self.total += ref['bytes']
        require(self.total <= TOTAL_LIMIT, 'material-total-budget')
        path = self.c2.regular(self.root / relative)
        with path.open('rb') as stream:
            raw = stream.read(ref['bytes'] + 1)
        require(len(raw) == ref['bytes'] and hashlib.sha256(raw).hexdigest() == ref['sha256'],
                'material-byte-binding')
        self.reads[relative] = dict(ref)
        return raw


def generated_command(raw):
    require(len(raw) <= R.CAPTURE_LIMIT and b'\0' not in raw, 'generated-link-budget')
    text = raw.decode('utf-8').removesuffix('\n')
    # CMake emits one command. No variable/glob/redirection/command substitution
    # interpretation is permitted here, including quoted forms we do not need.
    require(text and '\n' not in text and '\r' not in text
            and not any(x in text for x in '$`*?;|&<>'), 'generated-link-shell-syntax')
    tokens = shlex.split(text, comments=False, posix=True)
    require(tokens[:len(PREFIX)] == PREFIX and len(tokens) > len(PREFIX), 'generated-link-launcher')
    require(len(tokens) <= R.ARG_LIMIT, 'generated-link-argument-budget')
    return tokens[len(PREFIX):]


class LinkInputs:
    def __init__(self, files, aliases, retained, origins, layout):
        require(type(files) is list and 0 < len(files) <= ENTRY_LIMIT
                and type(aliases) is list and len(files) + len(aliases) <= ENTRY_LIMIT, 'material-entry-budget')
        self.index, self.files, self.uses, self.responses = {}, {}, [], []
        self.layout, self.response_bytes, self.expanded_bytes = layout, 0, 0
        for row in files:
            keys(row, ('path', 'file', 'role', 'producer', 'producer_sha256',
                       'frozen_before_link', 'members'), 'material-input')
            name = R.path(row['path'])
            require(name not in self.files and name not in self.index, 'material-duplicate-path')
            require(row['frozen_before_link'] is True, 'material-not-frozen-before-link')
            producer = row['producer']
            root_roles = {'sdk': ('sdk', ('/usr', '/lib', '/bin', '/etc')),
                          'dependencies': ('dependencies', ('/work/prefix',)),
                          'main-compile': ('main-tree', (R.BUILD_ROOT, '/work/src/cvc5'))}
            require(type(producer) is str and producer in root_roles, 'material-unknown-producer')
            origin, roots = root_roles[producer]
            require(row['producer_sha256'] == origins.get(origin), 'material-producer-binding')
            require(any(R.beneath(name, root) for root in roots), 'material-producer-path')
            require(not any(R.beneath(name, root) for root in R.plan()['link']['writable_roots']),
                    'material-hidden-by-writable-output')
            require(row['role'] in ('object', 'archive', 'response', 'script', 'configuration'), 'material-role')
            raw = retained.read(row['file'], F.TEXT_LIMIT if row['role'] in ('response', 'script', 'configuration') else FILE_LIMIT)
            if row['role'] == 'object':
                F.object_header(raw)
            if row['role'] == 'archive':
                require(R.binding(row['members']) == R.binding(F.archive(raw)), 'material-archive-member-drift')
            else:
                require(row['members'] is None, 'material-unexpected-members')
            self.files[name] = {**row, 'raw': raw if row['role'] in ('response', 'script') else None}
            self.index[name[1:]] = {'kind': 'file'}
        for row in aliases:
            keys(row, ('path', 'target'), 'material-alias')
            name = R.path(row['path'])[1:]
            require(not any(R.beneath('/' + name, p) for p in R.plan()['link']['writable_roots']),
                    'material-writable-alias')
            require(any(R.beneath('/' + name, p) for p in
                        ('/usr', '/lib', '/bin', '/etc', '/work/prefix', R.BUILD_ROOT, '/work/src/cvc5')),
                    'material-alias-origin')
            require(name not in self.index, 'material-alias-collision')
            self.index[name] = {'kind': 'symlink', 'target': row['target']}
        for name in list(self.index):
            for n in range(1, len(name.split('/'))):
                parent = '/'.join(name.split('/')[:n])
                self.index.setdefault(parent, {'kind': 'directory'})
                require(self.index[parent]['kind'] == 'directory', 'material-nondirectory-parent')
                require(len(self.index) <= ENTRY_LIMIT, 'material-inventory-budget')
        for row in aliases:
            require(self.layout.resolve(self.index, row['path'][1:])['status'] == 'resolved',
                    'material-alias-unresolved')

    def logical(self, value, cwd):
        # The shared layout reader refuses parent traversal after a named
        # component; do not lexically erase a/../ across an unknown symlink.
        name = self.layout.link_target(cwd[1:] + '/__argument__', value, False)
        return '/' + name

    def resolve(self, value, cwd):
        logical = self.logical(value, cwd)
        require(not any(R.beneath(logical, p) for p in R.plan()['link']['writable_roots']),
                'material-writable-input-path')
        result = self.layout.resolve(self.index, logical[1:])
        require(result['status'] == 'resolved' and result['kind'] == 'file', 'material-missing-input')
        name = '/' + result['path']
        require(name in self.files, 'material-outside-set')
        return name

    def expand(self, args, cwd, active=()):
        require(len(active) <= 16, 'response-recursion-budget')
        result = []
        for arg in args:
            require(type(arg) is str and '\0' not in arg, 'response-argument-type')
            if arg.startswith('@'):
                name = self.resolve(arg[1:], cwd)
                require(name not in active, 'response-cycle')
                row = self.files[name]
                require(row['role'] == 'response', 'response-role')
                self.response_bytes += len(row['raw'])
                require(self.response_bytes <= EXPANDED_LIMIT, 'response-expansion-byte-budget')
                self.responses.append(name)
                result.extend(self.expand(F.response(row['raw']), cwd, active + (name,)))
            else:
                self.expanded_bytes += len(arg.encode()) + 1
                require(self.expanded_bytes <= EXPANDED_LIMIT, 'link-argument-byte-budget')
                result.append(arg)
            require(len(result) <= R.ARG_LIMIT, 'link-argument-count-budget')
        return result

    def library(self, token, roots):
        require(token.startswith('-l') and len(token) > 2, 'link-library-token')
        suffix = token[2:]
        require(re.fullmatch(r'[A-Za-z0-9_+.-]+|:[A-Za-z0-9_+.-]+', suffix), 'link-library-name')
        filename = suffix[1:] if suffix.startswith(':') else 'lib' + suffix + '.a'
        for root in roots:
            candidate = root + '/' + filename
            result = self.layout.resolve(self.index, candidate[1:])
            if result['status'] == 'resolved':
                return self.resolve(candidate, '/')
        raise ValueError('link-library-not-in-declared-search-set')

    def consume(self, name, cwd, roots, active=()):
        require(name not in active and len(active) < 16, 'link-script-cycle-or-depth')
        row = self.files[name]
        require(row['role'] in ('object', 'archive', 'script'), 'link-input-role')
        self.uses.append(name)
        require(len(self.uses) <= R.ARG_LIMIT, 'link-input-use-budget')
        if row['role'] == 'script':
            for value in F.script(row['raw'])['inputs']:
                require(value.startswith(('/', '-l')), 'link-relative-script-input-needs-review')
                child = self.library(value, roots) if value.startswith('-l') else self.resolve(value, cwd)
                self.consume(child, cwd, roots, active + (name,))


def link_arguments(args, inputs, cwd, default_roots):
    require(type(default_roots) is list and len(default_roots) <= 128, 'link-default-search-budget')
    roots, tokens = [], []
    # First collect all -L options: GNU ld applies them to all -l occurrences,
    # irrespective of the location of -L relative to the library argument.
    n = 1
    while n < len(args):
        arg = args[n]
        if arg == '-L':
            require(n + 1 < len(args), 'link-truncated-search')
            n += 1
            roots.append(inputs.logical(args[n], cwd))
        elif arg.startswith('-L'):
            roots.append(inputs.logical(arg[2:], cwd))
        elif arg.startswith('-Wl,'):
            tokens.extend(arg[4:].split(','))
        elif arg == '-Xlinker':
            require(n + 1 < len(args), 'link-truncated-xlinker')
            n += 1
            tokens.append(args[n])
        else:
            tokens.append(arg)
        n += 1
    roots += default_roots
    require(len(roots) <= 128, 'link-search-count')
    for root in roots:
        R.path(root)
        require(any(R.beneath(root, p) for p in ('/usr/lib', '/lib', '/work/prefix', R.BUILD_ROOT))
                and not any(R.beneath(root, p) for p in R.plan()['link']['writable_roots']), 'link-search-root')
    output_count = map_count = trace_count = 0
    group_depth = 0
    whole = False
    n = 0
    while n < len(tokens):
        token = tokens[n]
        if token in ('-o', '-Map', '-T', '-l'):
            require(n + 1 < len(tokens), 'link-missing-option-value')
            n += 1
            value = tokens[n]
            if token == '-o':
                require(inputs.logical(value, cwd) == R.OUTPUT, 'link-output-drift')
                output_count += 1
            elif token == '-Map':
                require(inputs.logical(value, cwd) == '/work/evidence/cvc5.map', 'link-map-drift')
                map_count += 1
            else:
                name = inputs.library('-l' + value, roots) if token == '-l' else inputs.resolve(value, cwd)
                if token == '-T':
                    require(inputs.files[name]['role'] == 'script', 'link-script-role')
                inputs.consume(name, cwd, roots)
        elif token.startswith('-l'):
            inputs.consume(inputs.library(token, roots), cwd, roots)
        elif token == '-t':
            trace_count += 1
        elif token == '--start-group':
            group_depth += 1
            require(group_depth <= 16, 'link-group-depth')
        elif token == '--end-group':
            require(group_depth > 0, 'link-unmatched-group')
            group_depth -= 1
        elif token in ('--whole-archive', '--no-whole-archive'):
            require((token == '--whole-archive') != whole, 'link-whole-archive-state')
            whole = not whole
        elif token in ('--cref', '-Bstatic') or token in SAFE_FLAGS or re.fullmatch(r'-W(?:no-)?[A-Za-z][A-Za-z0-9-]*', token):
            pass
        elif token.startswith('-') or not token:
            raise ValueError('link-unsupported-argument')
        else:
            inputs.consume(inputs.resolve(token, cwd), cwd, roots)
        n += 1
    require(output_count == map_count == 1 and trace_count == 2 and '--cref' in tokens
            and '-static' in tokens and not group_depth and not whole, 'link-required-options-or-group')
    return roots


def check(value, root, recipe, recipe_sha256, phase_result, c2):
    keys(value, ('format', 'version', 'scope', 'recipe_sha256', 'phase_declarations_sha256',
                 'capture', 'generated_link', 'files', 'aliases', 'default_search_roots',
                 'expanded_arguments', 'input_sequence', 'implicit_inputs', 'actual_link'), 'prelink')
    require(value['format'] == FORMAT and value['version'] == '0.2'
            and value['scope'] == 'offline-retained-byte-consistency'
            and value['actual_link'] is None, 'prelink-scope')
    require(value['recipe_sha256'] == R.sha(recipe_sha256)
            and value['phase_declarations_sha256'] == phase_result['phase_declarations_sha256'], 'prelink-binding')
    require(phase_result['checked_prefix'] == ['dependencies', 'main-compile'], 'prelink-phase-position')
    retained = RetainedFiles(root, c2)
    raw = retained.read(value['capture'], R.CAPTURE_LIMIT)
    require(hashlib.sha256(raw).hexdigest() == phase_result['unverified_outputs']['link-capture'], 'prelink-capture-binding')
    capture = R.decode(raw, R.CAPTURE_LIMIT)
    args = R.check_capture(capture, recipe['policy']['environment']['values'])
    require(args == generated_command(retained.read(value['generated_link'], R.CAPTURE_LIMIT)), 'prelink-command-drift')
    layout = c2.module('cvc5_prelink_layout', 'scripts/prepare-cvc5-execution-review.py')
    inputs = LinkInputs(value['files'], value['aliases'], retained, phase_result['unverified_outputs'], layout)
    expanded = [args[0]] + inputs.expand(args[1:], capture['cwd'])
    require(expanded == value['expanded_arguments'], 'prelink-argument-order')
    roots = link_arguments(expanded, inputs, capture['cwd'], value['default_search_roots'])
    require(inputs.uses == value['input_sequence'], 'prelink-input-order')
    explicit_sequence = list(inputs.uses)
    implicit = value['implicit_inputs']
    require(type(implicit) is list and 0 < len(implicit) <= R.ARG_LIMIT, 'prelink-implicit-declarations-required')
    for name in implicit:
        resolved = inputs.resolve(name, capture['cwd'])
        require(resolved == name and inputs.files[name]['producer'] == 'sdk'
                and inputs.files[name]['role'] in ('object', 'archive', 'script', 'configuration'), 'prelink-implicit-origin')
        if inputs.files[name]['role'] == 'configuration':
            inputs.uses.append(name)
        else:
            inputs.consume(name, capture['cwd'], roots)
    implicit_sequence = inputs.uses[len(explicit_sequence):]
    require(all(inputs.files[name]['producer'] == 'sdk' for name in implicit_sequence), 'prelink-implicit-origin')
    observed = set(inputs.uses) | set(inputs.responses) | set(implicit)
    return {'scope': 'offline-prelink-byte-consistency-only', 'input_sequence': explicit_sequence,
            'response_sequence': inputs.responses, 'implicit_inputs': implicit,
            'implicit_input_sequence': implicit_sequence,
            'implicit_input_completeness': 'not-established',
            'without_use_observation': sorted(set(inputs.files) - observed),
            'archive_members': {n: x['members'] for n, x in inputs.files.items() if x['role'] == 'archive'},
            'actual_member_extraction': 'not-observed', 'bytes_checked': retained.total,
            'runtime_qualification': False, 'execution_ready': False, 'build_ready': False,
            'acceptance': 'not-accepted'}
