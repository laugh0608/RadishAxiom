#!/usr/bin/env python3
"""Independent L1 source binding, never target build or runtime acceptance."""
import argparse
import hashlib
import json
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
         'scripts/test-linux-channel.py')
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
    return BASE['parse_json'](raw)


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


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    p.add_argument('--synthetic', action='store_true', help='check the explicit synthetic sample, never runtime facts')
    args = p.parse_args()
    result = check_synthetic(args.directory) if args.synthetic else check(args.directory)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
