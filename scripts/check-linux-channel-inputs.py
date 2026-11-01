#!/usr/bin/env python3
"""Independent L1 source binding, never target build or runtime acceptance."""
import argparse
import hashlib
import json
import os
import re
import stat
import tomllib
from pathlib import Path
import runpy

BASE = runpy.run_path(str(Path(__file__).with_name('check-solver-bootstrap-inputs.py')))
ROOT = BASE['ROOT']
require = BASE['require']
read_bounded = BASE['read_bounded']
digest = BASE['digest']
canonical = BASE['canonical']
BUDGETS = dict(work_ns=18000000000, cleanup_ns=19800000000, total_ns=20000000000,
               memory_bytes=134217728, swap_bytes=0, pids=16, nofile=64,
               wire_bytes=2097152, frames=8192, chunk_bytes=4096, start_bytes=4096,
               final_bytes=32768, stdout_bytes=1572864, stderr_bytes=65536, events=64)
PROFILE = 'linux-host-observe-v0.1'
COLLECTOR = 'scripts/cvc5-build-support/inspect_linux_host.sh'
GENERATOR = 'crates/solver-bootstrap-linux/examples/export_linux_channel_inputs.rs'
EXTRA = ('Cargo.toml', 'Cargo.lock', 'rust-toolchain.toml', GENERATOR, COLLECTOR,
         'scripts/check-linux-channel-inputs.py', 'scripts/cvc5-build-support/channel_report.py',
         'scripts/test-linux-channel.py', 'scripts/build-linux-channel.py',
         'scripts/test-linux-channel-build.py', 'scripts/check-solver-bootstrap-inputs.py')
PACKAGES = ('solver-bootstrap-linux', 'solver-supervision-core', 'digest')


def parse(raw, limit=32768):
    require(0 < len(raw) <= limit, 'json-size')
    # No escapes are permitted in this closed ASCII format. Bound depth before
    # the stdlib parser so a hostile nesting never reaches Python recursion.
    depth, quoted = 0, False
    for b in raw:
        require(b != 92, 'json-escape')
        if b == 34:
            quoted = not quoted
        elif not quoted:
            if b in (91, 123):
                depth += 1
                require(depth <= 16, 'json-depth')
            elif b in (93, 125):
                depth -= 1
    value = BASE['parse_json'](raw)
    def bounded(v):
        if type(v) is dict:
            require(len(v) <= 32, 'json-object')
            for k, x in v.items(): bounded(k); bounded(x)
        elif type(v) is list:
            require(len(v) <= 64, 'json-array')
            for x in v: bounded(x)
        elif type(v) is str:
            require(len(v) <= 256 and all(32 <= ord(c) <= 126 for c in v), 'json-string')
        elif type(v) is int:
            require(0 <= v < 2**64, 'json-uint')
        else:
            require(v is None or type(v) is bool, 'json-value')
    bounded(value)
    return value


def reads():
    fixed = [('/proc/self/status',65536),('/proc/self/mountinfo',1048576),('/proc/self/cgroup',4096),
             ('/proc/self/uid_map',4096),('/proc/self/gid_map',4096),('/host-observe/boot-id',4096),
             ('/host-observe/filesystems',65536),('/host-observe/init-mountinfo',1048576),
             ('/host-observe/cgroup/cgroup.controllers',4096),('/host-observe/cgroup/cgroup.subtree_control',4096)]
    fixed += [('/host-observe/cgroup/<own-nonroot>/'+n,4096) for n in
              ('memory.max','memory.swap.max','pids.max','cpu.max','cgroup.type','cgroup.events','memory.events')]
    fixed += [('/proc/self/ns/'+n,4096) for n in ('pid','mnt','cgroup','user','ipc','uts')]
    return [dict(path=p,bytes=n) for p,n in fixed]


def source_paths(root):
    names = set(EXTRA)
    for package in PACKAGES:
        base = root / 'crates' / package
        names.add(str((base / 'Cargo.toml').relative_to(root)))
        for p in (base / 'src').rglob('*'):
            require(not p.is_symlink(), 'source-symlink')
            if p.is_file() and p.suffix == '.rs':
                names.add(str(p.relative_to(root)))
    return sorted(names)


def check(directory, root=ROOT):
    directory = Path(directory)
    require(not directory.is_symlink() and directory.is_dir(), 'export-directory')
    require({p.name for p in directory.iterdir()} == {'inputs.json', 'collector.sh', 'synthetic-report.bin'}, 'export-files')
    raw = read_bounded(directory / 'inputs.json', 1048576)
    d = parse(raw, 1048576)
    BASE['shape'](d, ('format', 'version', 'scope', 'generator', 'target', 'profile', 'budgets', 'collector',
                      'collector_reads', 'source_set_digest', 'sources', 'build_inputs', 'native_build', 'build_ready', 'execution_ready'))
    require((d['format'], d['version'], d['scope'], d['generator'], d['target'], d['profile']) ==
            ('radishaxiom-private-linux-channel-inputs', '0.1', 'offline-source-binding-only', GENERATOR,
             'aarch64-unknown-linux-musl', PROFILE), 'input-identity')
    BASE['check_fixed'](d['budgets'], BUDGETS)
    require(d['build_inputs'] is None and d['native_build'] == 'not-accepted' and
            d['build_ready'] is False and d['execution_ready'] is False, 'scope-escalation')
    body = read_bounded(directory / 'collector.sh', 32768)
    require(body and body.endswith(b'\n') and not body.startswith(b'\xef\xbb\xbf') and
            b'\0' not in body and b'\r' not in body, 'collector-encoding')
    body.decode('utf-8')
    require(body == read_bounded(root / COLLECTOR, 32768), 'collector-binding')
    require(d['collector'] == dict(path=COLLECTOR, profile=PROFILE, bytes=len(body), digest=digest(body)), 'collector-record')
    BASE['check_fixed'](d['collector_reads'], reads())
    names = source_paths(root)
    BASE['check_sources'](d['sources'], d['source_set_digest'], root, sources=names)
    return dict(scope=d['scope'], input_binding=digest(raw), collector_digest=digest(body), source_count=len(names),
                build_ready=False, execution_ready=False, target_acceptance='not-established')


def check_synthetic(directory):
    summary = check(directory)
    parser = runpy.run_path(str(ROOT / 'scripts/cvc5-build-support/channel_report.py'))
    expected = dict(run_id='07'*32, input_binding=summary['input_binding'], collector_digest=summary['collector_digest'])
    raw = read_bounded(Path(directory) / 'synthetic-report.bin', 2097152)
    for n in range(len(raw)):
        decoder = parser['Decoder'](expected)
        try:
            decoder.feed(raw[:n]); decoder.finish()
        except ValueError:
            pass
        else:
            raise ValueError('accepted-synthetic-truncation')
    sizes = [1, 7, 19, 20, 21, 4096, len(raw)]
    for size in sizes:
        decoder = parser['Decoder'](expected)
        chunks = []
        for n in range(0, len(raw), size):
            chunks += decoder.feed(raw[n:n+size])
        result = decoder.finish()
        require(chunks == [(1, b'synthetic-only\n')] and result['runtime_exit_confirmed'] is False,
                'synthetic-payload-or-scope')
    return dict(scope='source-export-and-synthetic-interop-only', inputs=summary,
                wire_bytes=len(raw), truncated_prefixes_rejected=len(raw), partition_sizes=sizes,
                runtime_exit_confirmed=False, build_ready=False, execution_ready=False)


# v0.2 has bounded external inventories; it never widens the wire parser.
SIDECARS = ('source-snapshot.json', 'target-payload.json', 'tool-inventory.json',
            'build-plan.json', 'input-review.json')
TARGET = 'aarch64-unknown-linux-musl'
TOOLCHAIN = '1.97.1-aarch64-apple-darwin'
SIDECAR_LIMIT = 4 * 1024**2
SIDECAR_ROWS = 4096
COMMIT = re.compile('[0-9a-f]{40}')
HASH = re.compile('sha256:[0-9a-f]{64}')
shape = BASE['shape']


def sidecar(raw):
    require(0 < len(raw) <= SIDECAR_LIMIT, 'sidecar-size')
    # Bound tokens/strings/depth before json.loads, independently of report limits.
    depth, quoted, start = 0, False, 0
    for i, b in enumerate(raw):
        require(32 <= b <= 126 and b != 92, 'sidecar-ascii')
        if b == 34:
            if quoted: require(i-start <= 1024, 'sidecar-string')
            quoted, start = not quoted, i+1
        elif not quoted:
            if b in (91, 123): depth += 1; require(depth <= 16, 'sidecar-depth')
            if b in (93, 125): depth -= 1; require(depth >= 0, 'sidecar-depth')
    d = BASE['parse_json'](raw)
    def visit(v):
        if type(v) is dict:
            require(len(v) <= 32, 'sidecar-object')
            for x in v.values(): visit(x)
        elif type(v) is list:
            require(len(v) <= SIDECAR_ROWS, 'sidecar-rows')
            for x in v: visit(x)
        elif type(v) is int: require(0 <= v < 2**64, 'sidecar-uint')
        else: require(v is None or type(v) in (str, bool), 'sidecar-value')
    visit(d)
    return d


def safe_path(p, absolute=False):
    require(type(p) is str and 0 < len(p) <= 1024 and '\\' not in p and
            all(32 <= ord(c) <= 126 for c in p), 'path')
    require(p.startswith('/') == absolute, 'path-kind')
    parts = p.split('/')[1:] if absolute else p.split('/')
    require(all(c not in ('', '.', '..') for c in parts), 'path-components')
    return p


def file_record(path, limit=384*1024**2):
    """Stream hashes, including empty blobs; stable regular files, no symlink components."""
    p = Path(os.path.abspath(path))
    for c in (*reversed(p.parents), p): require(not c.is_symlink(), 'file-symlink')
    fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and 0 <= before.st_size <= limit, 'file-kind-or-size')
        h = hashlib.sha256(); n = 0
        while n <= limit:
            chunk = os.read(fd, min(65536, limit+1-n))
            if not chunk: break
            h.update(chunk); n += len(chunk)
        after = os.fstat(fd)
        require(n == before.st_size and n <= limit and
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'file-changed')
        return dict(bytes=n, digest='sha256:'+h.hexdigest()), stat.S_IMODE(before.st_mode)
    finally: os.close(fd)


def reference(ref, base, maximum=SIDECAR_LIMIT, absolute=False):
    shape(ref, ('path', 'bytes', 'digest'))
    safe_path(ref['path'], absolute)
    require(type(ref['bytes']) is int and 0 < ref['bytes'] <= maximum and
            type(ref['digest']) is str and HASH.fullmatch(ref['digest']), 'reference')
    p = Path(ref['path']) if absolute else Path(base)/ref['path']
    actual, _ = file_record(p, maximum)
    require(actual == {k: ref[k] for k in ('bytes', 'digest')}, 'reference-drift')
    return p


def identity(d, name):
    require(d['format'] == 'radishaxiom-private-linux-channel-'+name and d['version'] == '0.2', 'sidecar-identity')


def regular_tree(root):
    require(root.is_dir() and not root.is_symlink(), 'tree-root')
    result = []; directories = 0
    for base, dirs, files in os.walk(root, followlinks=False):
        directories += len(dirs); require(directories <= 8192, 'tree-directories')
        for n in dirs:
            require(not (Path(base)/n).is_symlink(), 'tree-directory-symlink')
        for n in files:
            p = Path(base)/n
            rel = p.relative_to(root).as_posix(); safe_path(rel)
            require(p.is_file() and not p.is_symlink(), 'tree-special-file')
            result.append(rel); require(len(result) <= SIDECAR_ROWS, 'tree-rows')
    return sorted(result)


def check_source_snapshot(d, source, commit):
    shape(d, ('format', 'version', 'source_commit', 'files', 'compile_sources'))
    identity(d, 'source-snapshot'); require(d['source_commit'] == commit, 'snapshot-commit')
    rows = d['files']; require(type(rows) is list and 0 < len(rows) <= SIDECAR_ROWS, 'snapshot-rows')
    names = regular_tree(source)
    require([r['path'] for r in rows] == names and d['compile_sources'] == source_paths(source), 'snapshot-file-set')
    total = 0
    for r in rows:
        shape(r, ('path', 'mode', 'bytes', 'digest')); safe_path(r['path'])
        actual, mode = file_record(source/r['path'], 128*1024**2)
        require(r['mode'] in ('100644', '100755') and mode == int(r['mode'][3:], 8) and
                actual == {k:r[k] for k in ('bytes', 'digest')}, 'snapshot-file')
        total += r['bytes']; require(total <= 128*1024**2, 'snapshot-size')


def material(ref, directory):
    # Review materials are copied, never interpreted as commands or loaded as Python.
    require(ref['path'].startswith('materials/'), 'material-location')
    return reference(ref, directory)


def check_target(d, directory, source, tools, synthetic):
    shape(d, ('format', 'version', 'target', 'installed_root', 'archive', 'release_manifest', 'files', 'receipt'))
    identity(d, 'target-payload'); require(d['target'] == TARGET, 'payload-target')
    root = Path(safe_path(d['installed_root'], True))
    reference(d['archive'], directory, 64*1024**2, True)
    reference(d['release_manifest'], directory, SIDECAR_LIMIT, True)
    rows = d['files']; require(type(rows) is list and len(rows) == 66, 'payload-file-count')
    prefix = 'lib/rustlib/'+TARGET+'/'
    require([r['path'] for r in rows] == sorted(set(r['path'] for r in rows)) and
            all(r['path'].startswith(prefix) for r in rows), 'payload-path-set')
    require(regular_tree(root/prefix) == [r['path'][len(prefix):] for r in rows], 'payload-extra-or-missing')
    for r in rows:
        shape(r, ('path', 'mode', 'bytes', 'digest')); safe_path(r['path'])
        actual, mode = file_record(root/r['path'])
        require(r['mode'] in ('0644', '0755') and mode == int(r['mode'], 8) and
                actual == {k:r[k] for k in ('bytes', 'digest')}, 'installed-payload-drift')
    if not synthetic:
        observed_raw = read_bounded(source/'docs/records/cvc5-control-plane-2026-11-01/channel-l3-input-observation.json', SIDECAR_LIMIT)
        require(digest(observed_raw) == 'sha256:9c3b7f3bb3a206c3c0f8544ffe9257164f9bb773fa882080490af9e37b9d67db', 'retained-observation-drift')
        observed = json.loads(observed_raw)
        require(root == Path(tools[0]['path']).parent.parent, 'installed-toolchain-root')
        require(rows == observed['target_payload']['inventory'] and
                d['archive']['digest'] == 'sha256:49ff0879d94e2e8e86d5e85eb15a9215943e8c78b51363d6553443598cab5d31' and
                d['archive']['bytes'] == 29062284 and
                d['release_manifest']['digest'] == 'sha256:03569b1886ceb5c05276b50c8431ab111de944cd6140fe1fa7d821dd8e0f29cf',
                'retained-target-identity')
    receipt = sidecar(read_bounded(material(d['receipt'], directory), SIDECAR_LIMIT))
    shape(receipt, ('format', 'version', 'target', 'outcome', 'synthetic', 'archive_digest',
                    'files_digest', 'metadata', 'unchanged_tools', 'limitations'))
    identity(receipt, 'installation-receipt')
    require(receipt['target'] == TARGET and receipt['outcome'] == 'installed-reconciled' and
            receipt['synthetic'] is synthetic and receipt['archive_digest'] == d['archive']['digest'] and
            receipt['files_digest'] == digest(canonical(rows)), 'installation-receipt')
    require(receipt['metadata'] and receipt['limitations'] and
            receipt['unchanged_tools'] == tools[:3], 'installation-receipt-coverage')
    for ref in receipt['metadata']: reference(ref, directory, SIDECAR_LIMIT, True)
    return receipt


def check_tools(d, directory, synthetic):
    shape(d, ('format', 'version', 'toolchain', 'tools', 'dylibs', 'resolution', 'system', 'cargo_resolution'))
    identity(d, 'tool-inventory'); require(d['toolchain'] == TOOLCHAIN, 'toolchain')
    roles = ('cargo', 'rustc', 'lld', 'installer', 'python', 'git')
    require(type(d['tools']) is list and tuple(t['role'] for t in d['tools']) == roles, 'tool-roles')
    refs = []
    if not synthetic:
        prefix = Path(d['tools'][0]['file']['path']).parent.parent
        home = prefix.parents[2]
        require(prefix.name == TOOLCHAIN and str(prefix).endswith('/.rustup/toolchains/'+TOOLCHAIN) and
                [t['file']['path'] for t in d['tools'][:4]] ==
                [str(prefix/'bin/cargo'), str(prefix/'bin/rustc'),
                 str(prefix/'lib/rustlib/aarch64-apple-darwin/bin/rust-lld'), str(home/'.cargo/bin/rustup')] and
                d['tools'][5]['file']['path'] == '/usr/bin/git', 'precise-host-tools')
    for t in d['tools']:
        shape(t, ('role', 'version', 'file')); require(type(t['version']) is str and t['version'], 'tool-version')
        reference(t['file'], directory, 384*1024**2, True); refs.append(t['file'])
    require(len({r['path'] for r in refs}) == len(refs), 'duplicate-tool-path')
    for r in d['dylibs']: reference(r, directory, 384*1024**2, True)
    require(len({r['path'] for r in d['dylibs']}) == len(d['dylibs']), 'duplicate-dylib')
    resolution = sidecar(read_bounded(material(d['resolution'], directory), SIDECAR_LIMIT))
    shape(resolution, ('format', 'version', 'synthetic', 'decision', 'images_digest', 'edges', 'limitations'))
    identity(resolution, 'host-resolution')
    require(resolution['synthetic'] is synthetic and resolution['decision'] == 'reviewed-explicit-host-trust' and
            resolution['images_digest'] == digest(canonical(refs+d['dylibs'])) and
            resolution['edges'] and resolution['limitations'], 'host-resolution-review')
    paths = {r['path'] for r in refs+d['dylibs']}
    for e in resolution['edges']:
        shape(e, ('image', 'load', 'resolved', 'system'))
        require(e['image'] in paths and type(e['load']) is str and e['load'] and type(e['system']) is bool,
                'resolution-edge')
        safe_path(e['resolved'], True)
        require((e['resolved'].startswith(('/usr/lib/', '/System/Library/')) if e['system'] else
                 e['resolved'] in paths), 'resolution-closure')
    require(paths <= {e['image'] for e in resolution['edges']}, 'resolution-image-coverage')
    system = d['system']
    shape(system, ('os', 'identity', 'dyld', 'trust'))
    require(system['os'] == 'macOS-aarch64' and system['identity'] and system['dyld'] and
            system['trust'] == 'explicit-trusted-host-not-hermetic', 'system-trust')
    material(system['identity'], directory); material(system['dyld'], directory)
    return refs


RESOLVER_DESTINATIONS = (
    'registry/index/index.crates.io-1949cf8c6b5b557f/config.json',
    'registry/index/index.crates.io-1949cf8c6b5b557f/.cache/li/bc/libc',
)
LIBC_CHECKSUM = '3eaf3ede3fee6db1a4c2ee091bf8a8b4dccdc6d17f656fb07896ee72867612f2'


def check_cargo_resolution(d, directory, source, synthetic):
    shape(d, ('scope', 'package', 'version', 'checksum', 'files'))
    require(d['scope'] == 'workspace-lock-resolution-only-not-compiled' and d['package'] == 'libc' and
            d['version'] == '0.2.189' and d['checksum'] == LIBC_CHECKSUM and
            type(d['files']) is list and tuple(r['destination'] for r in d['files']) == RESOLVER_DESTINATIONS,
            'cargo-resolution-inputs')
    raw = []
    for r in d['files']:
        shape(r, ('destination', 'file'))
        p = reference(r['file'], directory, SIDECAR_LIMIT, True)
        raw.append(read_bounded(p, SIDECAR_LIMIT))
    require(json.loads(raw[0]) == dict(dl='https://static.crates.io/crates', api='https://crates.io'), 'registry-config')
    require(raw[1].startswith(b'\x03\x02\0\0\0') and raw[1].endswith(b'\0'), 'sparse-cache-version')
    parts = raw[1][5:].split(b'\0')
    require(len(parts) <= 8192 and len(parts) % 2 == 0, 'sparse-cache-records')
    entries = [json.loads(parts[i+1]) for i in range(1,len(parts)-1,2) if parts[i] == b'0.2.189']
    require(len(entries) == 1 and all(entries[0][k] == v for k,v in
            dict(name='libc',vers='0.2.189',cksum=LIBC_CHECKSUM,yanked=False).items()), 'sparse-lock-entry')
    lock = tomllib.loads(read_bounded(source/'Cargo.lock', SIDECAR_LIMIT).decode())
    package = [p for p in lock['package'] if p['name'] == 'libc']
    require(len(package) == 1 and package[0]['version'] == '0.2.189' and package[0]['checksum'] == LIBC_CHECKSUM and
            package[0]['source'] == 'registry+https://github.com/rust-lang/crates.io-index', 'locked-resolver-package')
    # No .crate, unpacked registry source, executable or additional index is seeded.
    return d['files']


def check_v02(directory, source, commit, review_digest, *, synthetic=False):
    """Independent binding review. Caller pins a real decision, not an accepted string.

    synthetic=True is test-only, always reported; production CLI/wrapper never pass it.
    Host resolution/installation statements remain explicit reviewed trust inputs.
    """
    directory, source = Path(directory), Path(source)
    require(type(commit) is str and COMMIT.fullmatch(commit) and
            type(review_digest) is str and HASH.fullmatch(review_digest), 'external-pins')
    raw = read_bounded(directory/'inputs.json', 1024**2); d = parse(raw, 1024**2)
    shape(d, ('format', 'version', 'scope', 'generator', 'target', 'profile', 'budgets', 'collector',
              'collector_reads', 'source_set_digest', 'sources', 'build_inputs', 'native_build', 'build_ready', 'execution_ready'))
    require((d['format'], d['version'], d['scope'], d['generator'], d['target'], d['profile']) ==
            ('radishaxiom-private-linux-channel-inputs', '0.2', 'target-build-input-binding', GENERATOR, TARGET, PROFILE), 'v02-identity')
    BASE['check_fixed'](d['budgets'], BUDGETS)
    require(d['native_build'] == 'not-accepted' and d['build_ready'] is False and d['execution_ready'] is False, 'readiness')
    body = read_bounded(source/COLLECTOR, 32768)
    require(d['collector'] == dict(path=COLLECTOR, profile=PROFILE, bytes=len(body), digest=digest(body)) and
            read_bounded(directory/'collector.sh', 32768) == body, 'collector-binding')
    BASE['check_fixed'](d['collector_reads'], reads())
    BASE['check_sources'](d['sources'], d['source_set_digest'], source, source_paths(source))
    build = d['build_inputs']; shape(build, ('source_commit', 'sidecars'))
    require(build['source_commit'] == commit and type(build['sidecars']) is list and
            tuple(r['path'] for r in build['sidecars']) == SIDECARS, 'v02-build-inputs')
    parts = {}
    for ref in build['sidecars']:
        p = reference(ref, directory)
        parts[ref['path']] = sidecar(read_bounded(p, SIDECAR_LIMIT))
    require(build['sidecars'][-1]['digest'] == review_digest, 'unregistered-review')
    check_source_snapshot(parts[SIDECARS[0]], source, commit)
    tools = check_tools(parts[SIDECARS[2]], directory, synthetic)
    check_target(parts[SIDECARS[1]], directory, source, tools, synthetic)
    check_cargo_resolution(parts[SIDECARS[2]]['cargo_resolution'], directory, source, synthetic)
    review = parts[SIDECARS[-1]]
    shape(review, ('format', 'version', 'scope', 'decision', 'synthetic', 'source_commit', 'objects',
                   'decisions', 'licenses', 'trust', 'limitations'))
    identity(review, 'input-review')
    require(review['scope'] == 'finite-diagnostic-build-inputs' and review['decision'] == 'accepted-for-one-diagnostic-build' and
            review['synthetic'] is synthetic and review['source_commit'] == commit and
            review['objects'] == build['sidecars'][:-1] and review['decisions'] and review['licenses'] and
            review['trust'] and review['limitations'], 'finite-review')
    for ref in review['decisions']+review['licenses']: material(ref, directory)
    # The checker owns its expected argv/flags/environment, not the producer plan.
    expected = expected_plan(parts[SIDECARS[3]]['task_root'], tools)
    BASE['check_fixed'](parts[SIDECARS[3]], expected)
    return dict(scope='synthetic-v02-binding-only' if synthetic else 'reviewed-v02-byte-binding-only',
                input_binding=digest(raw), source_commit=commit, source_count=len(d['sources']),
                synthetic=synthetic, build_ready=False, execution_ready=False, native_build='not-accepted')


def expected_launcher(task, python):
    return (f'#!{python} -ISB\nimport os, sys\nos.execve({python!r}, '
            f'[{python!r}, "-I", "-S", "-B", {task+"/source/scripts/build-linux-channel.py"!r}, "_record", '
            f'{task+"/records/build-plan.json"!r}, *sys.argv[1:]], os.environ)\n').encode('ascii')


def expected_plan(task, tools):
    # This independent literal specification deliberately does not import the wrapper.
    task = safe_path(task, True)
    require(len(task) <= 160 and re.fullmatch('[A-Za-z0-9_./-]+', task), 'task-path')
    cargo, rustc, lld, _, python, git = [r['path'] for r in tools]
    flags = ['-C', 'target-cpu=generic', '-C', 'target-feature=+crt-static', '-C', 'relocation-model=static',
             '-C', 'prefer-dynamic=no', '-C', 'link-self-contained=yes', '-C', 'linker='+lld, '-C', 'linker-flavor=ld.lld',
             '-C', 'link-arg=-static', '-C', 'link-arg=-no-pie', '-C', 'link-arg=-z', '-C', 'link-arg=noexecstack',
             '-C', 'link-arg=--trace', '-C', 'link-arg=-Map='+task+'/records/link.map',
             '-C', 'link-arg=--why-extract='+task+'/records/link-why-extract.tsv']
    return dict(format='radishaxiom-private-linux-channel-build-plan', version='0.2', task_root=task,
                cwd=task+'/source', source=task+'/source', inputs=task+'/records/inputs.json',
                argv=[cargo, 'build', '--package', 'radishaxiom-solver-bootstrap-linux', '--bin', 'axiom-linux-channel-init',
                      '--no-default-features', '--features', 'linux-channel-entry', '--target', TARGET,
                      '--profile', 'linux-channel', '--locked', '--offline', '--jobs', '1', '--verbose', '--verbose'],
                metadata_argv=[cargo, 'metadata', '--no-deps', '--format-version', '1', '--locked', '--offline',
                               '--filter-platform', TARGET],
                rustflags=flags,
                env=dict(PATH='/usr/bin:/bin', CARGO_HOME=task+'/cargo-home', CARGO_TARGET_DIR=task+'/target',
                         RUSTC=rustc, RUSTC_WRAPPER=task+'/tools/rustc-record', RUSTC_WORKSPACE_WRAPPER='',
                         CARGO_INCREMENTAL='0', CARGO_CACHE_AUTO_CLEAN_FREQUENCY='never', CARGO_NET_OFFLINE='true',
                         RADISHAXIOM_LINUX_CHANNEL_INPUTS=task+'/records/inputs.json', LANG='C', LC_ALL='C', TZ='UTC'),
                recorder=dict(source='scripts/build-linux-channel.py', python=python, git=git,
                              launcher=task+'/tools/rustc-record', policy='closed-channel-rustc-argv-v0.2', interpreter_flags=['-I','-S','-B'],
                              entry=dict(path='tools/rustc-record', bytes=len(expected_launcher(task, python)),
                                         digest=digest(expected_launcher(task, python)))),
                supervision=dict(platform='macOS-aarch64', leader_wait='waitid-WNOWAIT-before-signals-and-reap',
                                 group_query='/usr/lib/libproc.dylib:proc_listpids-PROC_PGRP_ONLY', max_group_members=64),
                limits=dict(total_seconds=600, task_bytes=536870912, source_bytes=134217728, source_files=4096,
                            elf_bytes=16777216, map_bytes=8388608, why_extract_bytes=4194304,
                            log_bytes=4194304, argv_bytes=65536, argv_records=64),
                profile=dict(inherits='release', **{'opt-level':2, 'codegen-units':1, 'lto':False, 'panic':'abort',
                            'overflow-checks':True, 'debug':1, 'strip':'none', 'incremental':False}),
                artifact=task+'/target/'+TARGET+'/linux-channel/axiom-linux-channel-init',
                run_artifact=False, implicit_retry=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    p.add_argument('--v02-source', type=Path, help='exact committed snapshot (v0.2 only)')
    p.add_argument('--source-commit')
    p.add_argument('--review-digest', help='externally registered input-review.json digest')
    p.add_argument('--synthetic', action='store_true', help='check the explicit synthetic sample, never runtime facts')
    args = p.parse_args()
    if args.v02_source is not None:
        require(not args.synthetic, 'v02-synthetic-not-a-production-cli-mode')
        result = check_v02(args.directory, args.v02_source, args.source_commit, args.review_digest)
    else:
        require(args.source_commit is None and args.review_digest is None, 'version-arguments')
        result = check_synthetic(args.directory) if args.synthetic else check(args.directory)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
