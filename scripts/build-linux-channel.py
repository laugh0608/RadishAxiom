#!/usr/bin/env python3
"""Private one-shot Linux channel build. Plan is pure; build needs separately reviewed inputs.

Never installs a target, runs an ELF, retries or cleans up failed tasks. Internal
recorder is not a general command runner. All child groups belong to this call.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import selectors
import signal
import stat
import subprocess
import sys
import time
import tomllib

TARGET = 'aarch64-unknown-linux-musl'
TOOLCHAIN = '1.97.1-aarch64-apple-darwin'
PACKAGES = ('digest', 'solver-supervision-core', 'solver-bootstrap-linux')
SIDECARS = ('source-snapshot.json', 'target-payload.json', 'tool-inventory.json', 'build-plan.json', 'input-review.json')
LIMITS = dict(total_seconds=600, task_bytes=536870912, source_bytes=134217728, source_files=4096,
              elf_bytes=16777216, map_bytes=8388608, why_extract_bytes=4194304,
              log_bytes=4194304, argv_bytes=65536, argv_records=64)


def require(ok, why):
    if not ok: raise ValueError(why)


def canonical(d):
    return json.dumps(d, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def digest(b): return 'sha256:'+hashlib.sha256(b).hexdigest()


def path_text(p):
    require(type(p) is str and re.fullmatch('/[A-Za-z0-9_./-]+', p) and
            all(c not in ('', '.', '..') for c in p.split('/')[1:]), 'absolute-path')
    return p


def launcher(task, python):
    return (f'#!{python} -ISB\nimport os, sys\nos.execve({python!r}, '
            f'[{python!r}, "-I", "-S", "-B", {task+"/source/scripts/build-linux-channel.py"!r}, "_record", '
            f'{task+"/records/build-plan.json"!r}, *sys.argv[1:]], os.environ)\n').encode('ascii')


def make_plan(task, tools):
    task = path_text(task); require(len(task) <= 160, 'task-path-length')
    require(tuple(t['role'] for t in tools) == ('cargo', 'rustc', 'lld', 'installer', 'python', 'git'), 'tool-roles')
    cargo, rustc, lld, _, python, git = [path_text(t['file']['path']) for t in tools]
    flags = []
    for v in ('target-cpu=generic', 'target-feature=+crt-static', 'relocation-model=static',
              'prefer-dynamic=no', 'link-self-contained=yes', 'linker='+lld, 'linker-flavor=ld.lld',
              'link-arg=-static', 'link-arg=-no-pie', 'link-arg=-z', 'link-arg=noexecstack',
              'link-arg=--trace', 'link-arg=-Map='+task+'/records/link.map',
              'link-arg=--why-extract='+task+'/records/link-why-extract.tsv'):
        flags.extend(('-C', v))
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
                              entry=dict(path='tools/rustc-record', bytes=len(launcher(task, python)), digest=digest(launcher(task, python)))),
                supervision=dict(platform='macOS-aarch64', leader_wait='waitid-WNOWAIT-before-signals-and-reap',
                                 group_query='/usr/lib/libproc.dylib:proc_listpids-PROC_PGRP_ONLY', max_group_members=64),
                limits=dict(LIMITS),
                profile=dict(inherits='release', **{'opt-level':2, 'codegen-units':1, 'lto':False, 'panic':'abort',
                            'overflow-checks':True, 'debug':1, 'strip':'none', 'incremental':False}),
                artifact=task+'/target/'+TARGET+'/linux-channel/axiom-linux-channel-init',
                run_artifact=False, implicit_retry=False)


def new_file(p, data, mode=0o644):
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        view = memoryview(data)
        while view:
            n = os.write(fd, view); require(n > 0, 'short-write'); view = view[n:]
        os.fchmod(fd, mode)
    finally: os.close(fd)


def no_links(p):
    for c in (*reversed(p.parents), p): require(not c.is_symlink(), 'path-symlink')


def cargo_configs(cwd, cargo_home):
    # Presence only: do not read private user configuration.
    for base in (cwd, *cwd.parents, cargo_home.parent):
        directory = cargo_home if base == cargo_home.parent else base/'.cargo'
        no_links(directory)
        for name in ('config', 'config.toml'):
            require(not os.path.lexists(directory/name), 'unbound-cargo-config')


def graph(source):
    root = tomllib.loads((source/'Cargo.toml').read_text())
    require(root['profile']['linux-channel'] == make_plan('/tmp/a', [dict(role=r, file=dict(path='/tmp/'+r))
            for r in ('cargo','rustc','lld','installer','python','git')])['profile'], 'profile-drift')
    require(set(root['workspace']['members']) == {'crates/'+n for n in
            ('axiom-ir','checker-runtime','checker-runtime-darwin-store','digest','solver-diagnostic-host',
             'solver-supervision-core','solver-bootstrap-linux')}, 'workspace-members')
    for package in PACKAGES:
        base = source/'crates'/package; d = tomllib.loads((base/'Cargo.toml').read_text())
        require(d['package'].get('build', False) is False and not (base/'build.rs').exists(), 'build-script')
        require(d['package']['name'] == 'radishaxiom-'+package and d['package']['edition'] == '2024', 'package-identity')
        require(not d.get('build-dependencies') and not d.get('target'), 'conditional-or-build-dependency')
        require(not d.get('lib', {}).get('proc-macro', False), 'proc-macro')
        wanted = {} if package == 'digest' else {'radishaxiom-solver-supervision-core': '../solver-supervision-core',
                 'radishaxiom-digest': '../digest'} if package == 'solver-bootstrap-linux' else {'radishaxiom-digest': '../digest'}
        require(d.get('dependencies', {}) == {n:dict(path=p) for n,p in wanted.items()}, 'normal-dependency-closure')
    leaf = tomllib.loads((source/'crates/solver-bootstrap-linux/Cargo.toml').read_text())
    require(leaf['features'] == {'default':[], 'linux-channel-entry':[]} and
            leaf['bin'] == [dict(name='axiom-linux-channel-init', path='src/bin/linux_channel_init.rs',
                                **{'required-features':['linux-channel-entry'], 'test':False, 'bench':False})], 'leaf-target')


class Session:
    """Single monotonic deadline. Disk counting is an observation, not a hard quota."""
    def __init__(self, root, *, seconds=600, task_bytes=536870912, log_bytes=4194304):
        require(sys.platform == 'darwin' and hasattr(os,'waitid') and hasattr(os,'WNOWAIT'), 'unsupported-supervision-host')
        require(signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL, 'child-wait-owner-not-established')
        self.start = time.monotonic(); self.end = self.start+seconds
        self.root, self.task_limit, self.log_limit = Path(root), task_bytes, log_bytes
        self.owns_timer = False; self.cancelled = False; self.log_count = 0; self.peak_bytes = 0; self.children = []

    def checkpoint(self):
        require(not self.cancelled, 'cancelled')
        require(time.monotonic() < self.end, 'total-deadline')

    def measure(self):
        self.checkpoint(); total = 0; count = 0
        if self.root.exists():
            for base, dirs, files in os.walk(self.root, followlinks=False):
                for n in dirs: require(not (Path(base)/n).is_symlink(), 'task-symlink')
                for n in files:
                    st = (Path(base)/n).lstat()
                    require(stat.S_ISREG(st.st_mode), 'task-special-file')
                    total += st.st_size; count += 1
                    require(count <= 32768 and total <= self.task_limit, 'task-size-limit')
                self.checkpoint()
        for name, limit in (('records/link.map', LIMITS['map_bytes']),
                            ('records/link-why-extract.tsv', LIMITS['why_extract_bytes']),
                            ('target/'+TARGET+'/linux-channel/axiom-linux-channel-init', LIMITS['elf_bytes'])):
            p = self.root/name
            if os.path.lexists(p):
                st = p.lstat(); require(stat.S_ISREG(st.st_mode) and st.st_size <= limit, 'artifact-growth-limit')
        self.peak_bytes = max(self.peak_bytes, total)

    @staticmethod
    def group_present(pid):
        try: os.killpg(pid, 0); return True
        except ProcessLookupError: return False

    @staticmethod
    def exited_unreaped(p):
        require(p.returncode is None, 'leader-reaped-before-group-check')
        event = os.waitid(os.P_PID, p.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        require(event is None or event.si_pid == p.pid, 'leader-wait-identity')
        return event is not None

    @staticmethod
    def group_members(pid):
        # macOS libproc.h / sys/proc_info.h: PROC_PGRP_ONLY=2. The leader
        # remains unreaped while querying/signalling, pinning its numeric ID.
        lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        query = lib.proc_listpids
        query.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_int]
        query.restype = ctypes.c_int
        buffer = (ctypes.c_int * 65)()
        ctypes.set_errno(0)
        size = query(2, pid, buffer, ctypes.sizeof(buffer))
        require(0 <= size <= 64*ctypes.sizeof(ctypes.c_int) and size % ctypes.sizeof(ctypes.c_int) == 0 and
                not (size == 0 and ctypes.get_errno()), 'group-query-unconfirmed-or-limit')
        values = list(buffer)[:size//ctypes.sizeof(ctypes.c_int)]
        require(all(v > 0 for v in values) and len(values) == len(set(values)), 'group-query-layout')
        return values

    def stop(self, p):
        stop_end = time.monotonic()+1
        try: self.stop_pinned(p, stop_end)
        except BaseException as primary:
            # A failed group confirmation still must reap our known leader;
            # never signal the group again after releasing that identity pin.
            try:
                if p.returncode is None: p.wait(timeout=max(0.001,stop_end-time.monotonic()))
            except BaseException as reap:
                raise ValueError(str(primary)+'; reap: '+str(reap)) from primary
            raise

    def stop_pinned(self, p, stop_end):
        require(p.returncode is None, 'leader-reaped-before-stop')
        self.exited_unreaped(p)  # ECHILD/unknown ownership forbids any group signal.
        try: os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        except PermissionError:
            # Darwin can return EPERM when only the unreaped zombie remains.
            # Accept this only after both identity and membership checks.
            require(self.exited_unreaped(p) and set(self.group_members(p.pid)) <= {p.pid}, 'group-signal-unconfirmed')
        while True:
            exited = self.exited_unreaped(p)
            members = self.group_members(p.pid)
            if exited and set(members) <= {p.pid}:
                p.wait(timeout=max(0.001,stop_end-time.monotonic())); return
            if time.monotonic() >= stop_end:
                if exited: p.wait(timeout=0.001)
                raise ValueError('descendant-stop-unconfirmed' if exited else 'child-stop-unconfirmed')
            time.sleep(0.005)

    def run(self, argv, cwd, env, *, output_limit=4194304, logs=None):
        self.measure()
        p = None
        sel = selectors.DefaultSelector(); chunks = [bytearray(), bytearray()]; count = 0
        try:
            # Do not raise our timer exception in the Popen ownership handoff.
            # Spawn itself relies on the trusted host OS; check the same deadline
            # immediately after a PID is registered, never renew it.
            if self.owns_timer: signal.setitimer(signal.ITIMER_REAL, 0)
            p = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, start_new_session=True, close_fds=True)
            self.children.append(p.pid)
            if self.owns_timer: signal.setitimer(signal.ITIMER_REAL, 0.05, 0.05)
            self.checkpoint()
            for i, stream in enumerate((p.stdout, p.stderr)):
                os.set_blocking(stream.fileno(), False); sel.register(stream, selectors.EVENT_READ, i)
            while sel.get_map() or not self.exited_unreaped(p):
                self.measure()
                for key, _ in sel.select(min(0.05, max(0, self.end-time.monotonic()))):
                    b = os.read(key.fileobj.fileno(), 65536)
                    if not b: sel.unregister(key.fileobj); continue
                    count += len(b); require(count <= output_limit, 'command-output-limit')
                    if logs is not None:
                        self.log_count += len(b); require(self.log_count <= self.log_limit, 'combined-log-limit')
                        # Unbuffered writes, no silently discarded short writes.
                        require(logs[key.data].write(b) == len(b), 'log-short-write')
                    else: chunks[key.data].extend(b)
            require(set(self.group_members(p.pid)) <= {p.pid}, 'unexpected-live-descendant')
            code = p.wait(timeout=max(0.001, self.end-time.monotonic()))
            self.measure(); require(code == 0, 'command-failed-'+str(code))
            return bytes(chunks[0]), bytes(chunks[1])
        except BaseException as primary:
            if self.owns_timer: signal.setitimer(signal.ITIMER_REAL, 0)
            try:
                if p is not None and p.returncode is None: self.stop(p)
            except BaseException as cleanup:
                raise ValueError(str(primary)+'; cleanup: '+str(cleanup)) from primary
            raise
        finally:
            sel.close()
            if p is not None: p.stdout.close(); p.stderr.close()


def snapshot(repo, commit, git, session):
    require(re.fullmatch('[0-9a-f]{40}', commit), 'commit')
    env = dict(PATH='/usr/bin:/bin', LANG='C', LC_ALL='C', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
               GIT_OPTIONAL_LOCKS='0', GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0', GIT_ATTR_NOSYSTEM='1')
    def call(args, limit=4194304):
        out, err = session.run([git, '-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false',
                                '-c', 'core.hooksPath=/dev/null', '-C', str(repo), *args], repo, env, output_limit=limit)
        require(not err, 'git-stderr'); return out
    require(call(['rev-parse','HEAD']).decode().strip() == commit and
            not call(['status','--porcelain=v1','--untracked-files=normal']), 'source-not-final-clean-commit')
    entries = call(['ls-tree','-rlz',commit]).split(b'\0'); rows = []; total = 0
    for item in entries:
        if not item: continue
        header, raw_path = item.split(b'\t', 1); mode, kind, blob, size = header.split()
        name = raw_path.decode('ascii')
        require(kind == b'blob' and mode in (b'100644', b'100755') and
                re.fullmatch('[0-9a-f]{40}', blob.decode()) and name and not name.startswith('/') and
                all(c not in ('', '.', '..', '.git') for c in name.split('/')) and
                all(32 <= ord(c) <= 126 and c != '\\' for c in name), 'git-tree-entry')
        total += int(size); require(total <= LIMITS['source_bytes'] and len(rows) < LIMITS['source_files'], 'source-budget')
        rows.append((name, mode.decode(), blob.decode(), int(size)))
    out = session.root/'source'; out.mkdir()
    for name, mode, blob, size in rows:
        session.checkpoint(); b = call(['cat-file','blob',blob], LIMITS['source_bytes'])
        require(len(b) == size, 'git-blob-size')
        # Git verifies the object too; this independent check binds the exact blob.
        require(hashlib.sha1(b'blob '+str(size).encode()+b'\0'+b).hexdigest() == blob, 'git-blob-identity')
        p = out/name; p.parent.mkdir(parents=True, exist_ok=True); new_file(p, b, int(mode[3:], 8))
    session.measure(); return out


HOST_PROBE = ['-', '--crate-name', '___', '--print=file-names', '--crate-type', 'bin', '--crate-type', 'rlib',
              '--crate-type', 'dylib', '--crate-type', 'cdylib', '--crate-type', 'staticlib', '--crate-type', 'proc-macro',
              '--print=sysroot', '--print=split-debuginfo', '--print=crate-name', '--print=cfg', '-Wwarnings']
RESOLVER_DESTINATIONS = (
    'registry/index/index.crates.io-1949cf8c6b5b557f/config.json',
    'registry/index/index.crates.io-1949cf8c6b5b557f/.cache/li/bc/libc',
)


def seed_resolution(home, spec):
    require(tuple(r['destination'] for r in spec['files']) == RESOLVER_DESTINATIONS, 'resolver-destinations')
    for r in spec['files']:
        p=Path(r['file']['path']); no_links(p)
        require(p.is_file() and p.stat().st_size <= 4194304, 'resolver-file')
        with p.open('rb') as f: raw=f.read(4194305)
        require(len(raw) == r['file']['bytes'] and digest(raw) == r['file']['digest'], 'resolver-drift')
        dest=home/r['destination']; dest.parent.mkdir(parents=True, exist_ok=True); new_file(dest,raw)


def rustc_argv(plan, args):
    """Validate actual Cargo argv, including read-only probes. Unknown forms fail closed."""
    require(args and args[0] == plan['env']['RUSTC'], 'rustc-executable')
    a = args[1:]; require(len(canonical(a)) <= LIMITS['argv_bytes'] and
                             all(type(v) is str and '\0' not in v for v in a), 'rustc-argv-budget')
    if a == ['-vV']: return 'version-probe'
    if a == HOST_PROBE: return 'host-probe'
    flags = plan['rustflags']
    at = [i for i in range(len(a)-len(flags)+1) if a[i:i+len(flags)] == flags]
    require(len(at) == 1, 'rustc-flags-order')
    i = at[0]; a = a[:i]+a[i+len(flags):]
    pairs = {}; positional = []
    multi = {'--crate-type', '--print', '-L', '--extern', '--cfg', '--check-cfg', '-C'}
    allowed = multi | {'--crate-name','--edition','--error-format','--json','--emit','--out-dir','--target','-W'}
    i = 0
    while i < len(a):
        v = a[i]
        if not v.startswith('-') or v == '-': positional.append(v); i += 1; continue
        if '=' in v: k, val = v.split('=',1)
        elif v.startswith(('-C','-L','-W')) and len(v) > 2: k, val = v[:2], v[2:]
        else:
            k = v; i += 1; require(i < len(a), 'rustc-option-value'); val = a[i]
        require(k in allowed and (k in multi or k not in pairs), 'rustc-option')
        pairs.setdefault(k, []).append(val); i += 1
    require(pairs.get('--target') == [TARGET], 'rustc-target')
    if positional == ['-']:
        require(pairs.get('--crate-name') == ['___'] and set(pairs) <= {'--crate-name','--print','--target','--crate-type','-W'}, 'rustc-probe')
        require(set(pairs.get('--print', [])) <= {'file-names','sysroot','split-debuginfo','crate-name','cfg'} and
                set(pairs.get('--crate-type', [])) <= {'bin','rlib','dylib','cdylib','staticlib','proc-macro'}, 'rustc-probe-options')
        require(pairs.get('-W', ['warnings']) == ['warnings'], 'rustc-probe-warning')
        return 'target-probe'
    require(len(positional) == 1 and len(pairs.get('--crate-name', [])) == 1, 'rustc-unit')
    crate = pairs['--crate-name'][0]
    package = {'radishaxiom_digest':'digest', 'radishaxiom_solver_supervision_core':'solver-supervision-core',
               'radishaxiom_solver_bootstrap_linux':'solver-bootstrap-linux', 'axiom_linux_channel_init':'solver-bootstrap-linux'}.get(crate)
    require(package is not None, 'rustc-unregistered-unit')
    suffix = 'src/bin/linux_channel_init.rs' if crate == 'axiom_linux_channel_init' else 'src/lib.rs'
    source = Path(plan['source']); wanted = source/'crates'/package/suffix
    got = Path(positional[0]); got = got if got.is_absolute() else source/got
    require(got == wanted, 'rustc-unit-source')
    require('-W' not in pairs, 'rustc-unit-warning-override')
    require(pairs.get('--edition') == ['2024'] and pairs.get('--crate-type') == (['bin'] if crate == 'axiom_linux_channel_init' else ['lib']) and
            pairs.get('--emit') == ['dep-info,metadata,link'], 'rustc-unit-options')
    out = plan['task_root']+'/target/'+TARGET+'/linux-channel/deps'
    require(pairs.get('--out-dir') == [out] and all(v.startswith('dependency='+plan['task_root']+'/target/') and
            '..' not in v.split('/') for v in pairs.get('-L', [])), 'rustc-output-paths')
    for v in pairs.get('--extern', []):
        name, sep, p = v.partition('=')
        require(sep and name in {'radishaxiom_digest','radishaxiom_solver_supervision_core','radishaxiom_solver_bootstrap_linux'} and
                p.startswith(out+'/lib'+name+'-') and '/' not in p[len(out)+1:] and p.endswith('.rlib'), 'rustc-extern')
    require(set(pairs.get('--cfg', [])) <= ({'feature="linux-channel-entry"'} if package == 'solver-bootstrap-linux' else set()), 'rustc-cfg')
    require(set(pairs.get('--check-cfg', [])) <= {'cfg(docsrs,test)', 'cfg(feature, values())',
            'cfg(feature, values("default", "linux-channel-entry"))'}, 'rustc-check-cfg')
    for v in pairs.get('-C', []):
        require(v in {'opt-level=2','panic=abort','embed-bitcode=no','codegen-units=1','debuginfo=1',
                      'overflow-checks=on','debug-assertions=off','strip=none','split-debuginfo=off'} or
                re.fullmatch('metadata=[0-9a-f]{1,32}|extra-filename=-[0-9a-f]{1,32}', v), 'rustc-codegen')
    require(pairs.get('--error-format', ['json']) == ['json'] and
            pairs.get('--json', ['diagnostic-rendered-ansi,artifacts,future-incompat']) ==
            ['diagnostic-rendered-ansi,artifacts,future-incompat'], 'rustc-diagnostic')
    return crate


def record(plan_path, args):
    # This entry cannot select arbitrary commands or reconfigure a plan.
    p = Path(plan_path); no_links(p)
    require(p.name == 'build-plan.json' and p.parent.name == 'records', 'recorder-plan-location')
    require(p.stat().st_size <= 4*1024**2, 'recorder-plan-size')
    with p.open('rb') as f: raw = f.read(4*1024**2+1)
    require(len(raw) <= 4*1024**2, 'recorder-plan-size')
    plan = json.loads(raw); require(canonical(plan) == raw, 'recorder-plan-canonical')
    require(str(p) == plan['task_root']+'/records/build-plan.json' and
            Path(__file__).absolute() == Path(plan['source'])/'scripts/build-linux-channel.py', 'recorder-entry-location')
    checker = runpy.run_path(str(Path(__file__).with_name('check-linux-channel-inputs.py')))
    inventory = checker['sidecar'](checker['read_bounded'](p.parent/'tool-inventory.json', 4194304))
    expected = make_plan(plan['task_root'], inventory['tools'])
    require(canonical(expected) == raw, 'recorder-plan-drift')
    root_raw = checker['read_bounded'](Path(plan['inputs']), 1048576)
    root = checker['parse'](root_raw, 1048576)
    require(root['version'] == '0.2' and root['scope'] == 'target-build-input-binding', 'recorder-input-version')
    checker['reference'](root['build_inputs']['sidecars'][3], p.parent)
    checker['reference'](inventory['tools'][1]['file'], p.parent, 384*1024**2, True)
    require((Path(plan['recorder']['launcher'])).read_bytes() == launcher(plan['task_root'], plan['recorder']['python']),
            'recorder-launcher-drift')
    kind = rustc_argv(plan, args)
    # The independent checker validated the plan precompile; check immutable
    # record locations and executable again immediately before exec.
    require(os.environ.get('RUSTC_WRAPPER') == plan['recorder']['launcher'] and
            os.environ.get('RADISHAXIOM_LINUX_CHANNEL_INPUTS') == plan['inputs'], 'recorder-environment')
    item = canonical(dict(format='radishaxiom-private-linux-channel-rustc-argv', version='0.2', kind=kind, argv=args))
    require(len(item) <= LIMITS['argv_bytes'], 'rustc-record-size')
    for i in range(LIMITS['argv_records']):
        try: new_file(p.parent/f'argv-{i:04}.json', item); break
        except FileExistsError: continue
    else: raise ValueError('rustc-record-count')
    env = dict(plan['env']); env.pop('RUSTC_WRAPPER'); env.pop('RUSTC_WORKSPACE_WRAPPER')
    env['CARGO_ENCODED_RUSTFLAGS'] = '\x1f'.join(plan['rustflags'])
    os.execve(plan['env']['RUSTC'], args, env)


def build(repo, bundle, commit, review_digest, task):
    session = Session(task)  # t0 precedes parsing, preflight and snapshot.
    require(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'preexisting-process-timer')
    previous = {}
    def cancel(_sig, _frame): session.cancelled = True
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): previous[sig] = signal.signal(sig, cancel)
    previous_alarm = signal.signal(signal.SIGALRM, lambda _sig, _frame: session.checkpoint())
    signal.setitimer(signal.ITIMER_REAL, 0.05, 0.05)
    session.owns_timer = True
    created = False
    try:
        repo, bundle, task = Path(repo), Path(bundle), Path(task)
        require(repo.is_absolute() and bundle.is_absolute() and task.is_absolute(), 'absolute-build-paths')
        no_links(repo); no_links(bundle); no_links(task)
        require(task.parent == repo/'.tmp' and re.fullmatch('linux-channel-build-[A-Za-z0-9-]+', task.name) and
                not os.path.lexists(task), 'fresh-task-root')
        require(re.fullmatch('[0-9a-f]{40}', commit) and re.fullmatch('sha256:[0-9a-f]{64}', review_digest), 'external-pins')
        check = runpy.run_path(str(Path(__file__).with_name('check-linux-channel-inputs.py')))
        def load(name, maximum=4194304):
            return check['read_bounded'](bundle/name, maximum)
        input_raw = load('inputs.json', 1048576)
        root = check['parse'](input_raw, 1048576)
        require(root['version'] == '0.2' and root['scope'] == 'target-build-input-binding', 'native-input-version')
        binding = root['build_inputs']; check['shape'](binding, ('source_commit','sidecars'))
        require(binding['source_commit'] == commit and
                tuple(r['path'] for r in binding['sidecars']) == SIDECARS, 'input-sidecars')
        for ref in binding['sidecars']: check['reference'](ref, bundle)
        review = check['sidecar'](load('input-review.json'))
        require(binding['sidecars'][-1]['digest'] == review_digest and review['source_commit'] == commit and
                review['decision'] == 'accepted-for-one-diagnostic-build' and review['synthetic'] is False and
                review['objects'] == binding['sidecars'][:-1] and review['decisions'] and review['licenses'] and
                review['trust'] and review['limitations'], 'input-review-not-accepted')
        for ref in review['decisions']+review['licenses']: check['material'](ref, bundle)
        inventory = check['sidecar'](load('tool-inventory.json'))
        check['check_tools'](inventory, bundle, False)
        tools = inventory['tools']
        plan = make_plan(str(task), tools)
        require(load('build-plan.json') == canonical(plan) and digest(load('input-review.json')) == review_digest,
                'plan-or-review-drift')
        # Never start Cargo to find out whether target components are present.
        payload = json.loads(load('target-payload.json'))
        target_root = Path(payload['installed_root'])/'lib/rustlib'/TARGET
        require(target_root.is_dir() and not target_root.is_symlink(), 'target-component-absent')
        cargo_configs(task/'source', task/'cargo-home')
        task.parent.mkdir(exist_ok=True); task.mkdir(); created = True
        for name in ('records','cargo-home','target','tools'): (task/name).mkdir()
        source = snapshot(repo, commit, plan['recorder']['git'], session)
        graph(source); cargo_configs(source, task/'cargo-home')
        check['check_cargo_resolution'](inventory['cargo_resolution'], bundle, source, False)
        # Copy only inventoried bundle materials to the owned records directory.
        # Extra files (e.g. synthetic report) are ignored, never executed/delivered.
        for name in ('inputs.json','collector.sh',*SIDECARS): new_file(task/'records'/name, load(name))
        material_names = set()
        for name in ('target-payload.json','tool-inventory.json','input-review.json'):
            def refs(v):
                if type(v) is dict:
                    if tuple(v) == ('path','bytes','digest') and v['path'].startswith('materials/'):
                        material_names.add(v['path'])
                    else:
                        for x in v.values(): refs(x)
                elif type(v) is list:
                    for x in v: refs(x)
            refs(json.loads(load(name)))
        require(len(material_names) <= 4096, 'material-count')
        for name in sorted(material_names):
            require(all(c not in ('','.','..') for c in name.split('/')), 'material-path')
            p = task/'records'/name; p.parent.mkdir(parents=True, exist_ok=True); new_file(p, load(name))
        entry = launcher(str(task), plan['recorder']['python'])
        new_file(task/'tools/rustc-record', entry, 0o755)
        env = dict(plan['env']); env['CARGO_ENCODED_RUSTFLAGS'] = '\x1f'.join(plan['rustflags'])
        checker = [plan['recorder']['python'], '-I', '-S', '-B', str(source/'scripts/check-linux-channel-inputs.py'),
                   str(task/'records'), '--v02-source', str(source), '--source-commit', commit, '--review-digest', review_digest]
        session.run(checker, source, dict(PATH='/usr/bin:/bin', LANG='C', LC_ALL='C', PYTHONDONTWRITEBYTECODE='1'))
        seed_resolution(task/'cargo-home', inventory['cargo_resolution'])
        metadata_raw, metadata_err = session.run(plan['metadata_argv'], source, env)
        require(not metadata_err, 'cargo-metadata-stderr')
        metadata = json.loads(metadata_raw)
        packages = {p['name']: p for p in metadata['packages']}
        require(len(packages) == 7 and set(metadata['workspace_members']) == set(p['id'] for p in packages.values()), 'cargo-workspace')
        for name in PACKAGES:
            package = packages['radishaxiom-'+name]
            require(package['source'] is None and all(t['kind'] != ['custom-build'] and 'proc-macro' not in t['kind']
                    for t in package['targets']) and all(dep['kind'] in (None, 'dev') and dep['source'] is None
                    for dep in package['dependencies']), 'cargo-native-graph')
        new_file(task/'records/cargo-metadata.json', metadata_raw)
        require((task/'records/inputs.json').read_bytes() == input_raw, 'inputs-drift')
        with (task/'records/stdout.log').open('xb', buffering=0) as out, (task/'records/stderr.log').open('xb', buffering=0) as err:
            session.run(plan['argv'], source, env, logs=(out,err))
        # Recheck all inputs/tools/target/source after the sole compile, never rebuild.
        session.run(checker, source, dict(PATH='/usr/bin:/bin', LANG='C', LC_ALL='C', PYTHONDONTWRITEBYTECODE='1'))
        require((task/'records/inputs.json').read_bytes() == input_raw, 'inputs-postbuild-drift')
        for item in inventory['cargo_resolution']['files']:
            p=task/'cargo-home'/item['destination']; no_links(p)
            require(p.is_file() and p.stat().st_size == item['file']['bytes'] and
                    digest(p.read_bytes()) == item['file']['digest'], 'resolver-postbuild-drift')
        records = sorted((task/'records').glob('argv-*.json')); kinds = []
        require(len(records) <= LIMITS['argv_records'], 'argv-record-count')
        for p in records:
            no_links(p); require(p.stat().st_size <= LIMITS['argv_bytes'], 'argv-record-size')
            raw = p.read_bytes(); require(len(raw) <= LIMITS['argv_bytes'], 'argv-record-size')
            d = json.loads(raw); require(canonical(d) == raw and rustc_argv(plan, d['argv']) == d['kind'], 'argv-record')
            kinds.append(d['kind'])
        units = [k for k in kinds if not k.endswith('-probe')]
        require(sorted(units) == sorted(('radishaxiom_digest','radishaxiom_solver_supervision_core',
                'radishaxiom_solver_bootstrap_linux','axiom_linux_channel_init')), 'compiled-unit-set')
        artifacts = []
        for name, limit in ((plan['artifact'], LIMITS['elf_bytes']), (str(task/'records/link.map'), LIMITS['map_bytes']),
                            (str(task/'records/link-why-extract.tsv'), LIMITS['why_extract_bytes'])):
            p = Path(name); no_links(p); st = p.stat()
            require(stat.S_ISREG(st.st_mode) and 0 < st.st_size <= limit, 'artifact-size')
            raw = p.read_bytes(); require(len(raw) == st.st_size, 'artifact-changed')
            artifacts.append(dict(path=name, bytes=len(raw), digest=digest(raw)))
        session.measure()
        result = dict(format='radishaxiom-private-linux-channel-build-manifest', version='0.2',
                      outcome='built-not-accepted', source_commit=commit, input_binding=digest(input_raw),
                      review_digest=review_digest, artifacts=artifacts, argv_records=len(records),
                      elapsed_seconds=int(time.monotonic()-session.start), peak_observed_bytes=session.peak_bytes,
                      native_build='not-accepted', build_ready=False, execution_ready=False, artifact_executed=False)
        new_file(task/'records/build-manifest.json', canonical(result)); session.measure()
        return result
    except BaseException as e:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if created:
            failure = dict(format='radishaxiom-private-linux-channel-build-failure', version='0.2',
                           outcome='failed', reason=str(e)[:256], child_group_ids_diagnostic_only=session.children,
                           late_process_identity='not-established-do-not-reuse-numeric-ids',
                           native_build='not-accepted', build_ready=False, execution_ready=False, artifact_executed=False)
            try: new_file(Path(task)/'records/failure.json', canonical(failure))
            except OSError: pass  # Original failure remains nonzero, including ENOSPC.
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_alarm)
        for sig, handler in previous.items(): signal.signal(sig, handler)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '_record':
        require(len(sys.argv) >= 4, 'recorder-arguments'); record(sys.argv[2], sys.argv[3:]); return
    p = argparse.ArgumentParser(description=__doc__); commands = p.add_subparsers(dest='mode', required=True)
    plan = commands.add_parser('plan', help='pure output; creates no task/environment')
    plan.add_argument('--task-root', required=True)
    plan.add_argument('--tool-inventory', required=True, type=Path)
    b = commands.add_parser('build', help='one build only, after separate explicit execution authorization')
    for name in ('repo','bundle','source-commit','review-digest','task-root'): b.add_argument('--'+name, required=True)
    args = p.parse_args()
    if args.mode == 'plan':
        check = runpy.run_path(str(Path(__file__).with_name('check-linux-channel-inputs.py')))
        inventory = check['sidecar'](check['read_bounded'](args.tool_inventory,4194304))
        result = make_plan(args.task_root, inventory['tools'])
    else: result = build(args.repo, args.bundle, args.source_commit, args.review_digest, args.task_root)
    sys.stdout.buffer.write(canonical(result)+b'\n')


if __name__ == '__main__': main()
