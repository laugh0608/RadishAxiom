#!/usr/bin/env python3
"""L1 synthetic/static checks only. Never invokes the collector shell or Linux."""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
I = runpy.run_path(str(ROOT / 'scripts/check-linux-channel-inputs.py'))
M = runpy.run_path(str(ROOT / 'scripts/cvc5-build-support/channel_report.py'))
canonical, digest = I['canonical'], I['digest']
B = dict(run_id='01'*32, input_binding='sha256:'+'02'*32, collector_digest='sha256:'+'03'*32)


def frame(seq, kind, stream, raw):
    return struct.pack('>8sIBBHI', b'AXCHN001', seq, kind, stream, 0, len(raw))+raw


def fixture():
    start = dict(format='radishaxiom-private-linux-channel-report', version='0.1', binding=B,
                 profile=I['PROFILE'], budgets=I['BUDGETS'])
    e = dict(pid=42, uid=65532, code=1, status=0)
    def stats(raw):
        return dict(seen_bytes=len(raw), exported_bytes=len(raw), sha256=digest(raw), prefix_only=False, eof=True)
    f = dict(binding=B, cause=None, child_pid=42, main_exit=e, exits=[e], signals=[], errors=[],
             clone_attempted=True, no_children=True, observations_overflowed=False,
             stdout=stats(b'abc'), stderr=stats(b''),
             clock=dict(first_ns=1, work_ns=18000000001, cleanup_ns=19800000001, final_ns=20000000001, last_ns=2),
             capture_failed=False, transport_failed=False, selected_exit_code=0)
    return start, f


def wire(final=None):
    start, f = fixture()
    return frame(0, 1, 0, canonical(start))+frame(1, 2, 1, b'abc')+frame(2, 3, 0, canonical(final or f))


def decode(raw, expected=B):
    d = M['Decoder'](expected)
    d.feed(raw)
    return d.finish()


class Reports(unittest.TestCase):
    def test_every_truncation_and_partition(self):
        raw = wire()
        for n in range(len(raw)):
            with self.assertRaises(ValueError):
                decode(raw[:n])
        for n in range(0, len(raw)+1, 13):
            d = M['Decoder'](B)
            chunks = d.feed(raw[:n])+d.feed(raw[n:])
            r = d.finish()
            self.assertEqual(chunks, [(1, b'abc')])
            self.assertTrue(r['collection_succeeded'])
            self.assertFalse(r['runtime_exit_confirmed'])
            self.assertEqual(r['qualification'], 'not-established')

    def test_headers_wrong_binding_and_after_final(self):
        for offset in [0, 8, 11, 12, 13, 14, 15, 16, 17, 18, 19]:
            raw = bytearray(wire()); raw[offset] ^= 128
            d = M['Decoder'](B)
            with self.assertRaises(ValueError): d.feed(raw)
            with self.assertRaises(ValueError): d.feed(wire())
        for key in B:
            b = dict(B); b[key] = b[key][:-1]+'f'
            with self.assertRaises(ValueError): decode(wire(), b)
        with self.assertRaises(ValueError): decode(wire()+b'x')

    def test_duplicate_start_final_order_and_streams(self):
        a, f = fixture()
        for raw in [frame(0, 3, 0, canonical(f)), frame(0, 2, 1, b'x'),
                    frame(0, 1, 0, canonical(a))*2,
                    frame(0, 1, 0, canonical(a))+frame(1, 2, 3, b'x')]:
            with self.assertRaises(ValueError): decode(raw)

    def test_final_tampering_cannot_be_success(self):
        _, original = fixture()
        mutations = [lambda f: f['stdout'].update(sha256='sha256:'+'00'*32),
                     lambda f: f['stdout'].update(exported_bytes=2),
                     lambda f: f['stdout'].update(seen_bytes=4),
                     lambda f: f.update(clone_attempted=False), lambda f: f.update(exits=[]),
                     lambda f: f['clock'].update(work_ns=4), lambda f: f.update(accepted=True),
                     lambda f: f['exits'].append(dict(f['main_exit'])),
                     lambda f: f.update(selected_exit_code=False), lambda f: f.update(no_children=1)]
        for mutate in mutations:
            f = copy.deepcopy(original); mutate(f)
            with self.assertRaises(ValueError): decode(wire(f))

    def test_prefix_eof_reap_are_not_interchangeable(self):
        _, f = fixture()
        for key in ('no_children', 'stdout', 'capture_failed', 'transport_failed', 'observations_overflowed'):
            g = copy.deepcopy(f)
            if key == 'stdout': g[key]['eof'] = False
            else: g[key] = key != 'no_children'
            with self.assertRaises(ValueError): decode(wire(g))
            g['selected_exit_code'] = 125
            self.assertFalse(decode(wire(g))['collection_succeeded'])
        g = copy.deepcopy(f); g['stdout'].update(prefix_only=True, seen_bytes=4); g['selected_exit_code'] = 125
        self.assertTrue(decode(wire(g))['final']['stdout']['prefix_only'])

    def test_canonical_controls_and_budgets(self):
        a, f = fixture()
        for raw in [b'{"a":1,"a":2}', b'{"a":1.0}', b'{"a":NaN}', b'['*18+b'0'+b']'*18,
                    canonical(f)+b'\n', b'{"a":"\\u0061"}']:
            with self.assertRaises(ValueError): I['parse'](raw)
        for size in (0, 4097):
            with self.assertRaises(ValueError): decode(frame(0, 1, 0, canonical(a))+frame(1, 2, 1, b'x'*size))
        raw = frame(0, 1, 0, canonical(a))+b''.join(frame(i, 2, 2, b'x'*4096) for i in range(1, 18))
        with self.assertRaises(ValueError): decode(raw)

    def test_actual_selected_code_and_siginfo(self):
        _, f = fixture()
        for code in (2, 3):
            g = copy.deepcopy(f); g['main_exit'].update(code=code, status=9); g['selected_exit_code'] = 137
            self.assertEqual(decode(wire(g))['final']['main_exit']['code'], code)
        for kind, sig, result in [('deadline', None, 124), ('cancelled', 15, 143), ('orphan', None, 125)]:
            g = copy.deepcopy(f); g['cause'] = dict(kind=kind, signal=sig, error=None); g['selected_exit_code'] = result
            self.assertEqual(decode(wire(g))['final']['main_exit']['status'], 0)


BODY = (ROOT / I['COLLECTOR']).read_text()
AWK = BODY.split('# AXIOM_FILTER_BEGIN\n', 1)[1].split('# AXIOM_FILTER_END', 1)[0]


def filt(mode, raw, cap=65536):
    # Execute only the exact embedded pure AWK transformation on synthetic decimal
    # byte records. No collector shell, head/stat/proc/cgroup or host read occurs.
    data = raw+b'\x1c'
    encoded = '\n'.join(' '.join(str(b) for b in data[i:i+16]) for i in range(0, len(data), 16))+'\n'
    return subprocess.run(['/usr/bin/awk', '-v', 'mode='+mode, '-v', 'cap='+str(cap), AWK],
                          input=encoded.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=3, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})


class Collector(unittest.TestCase):
    def good(self, mode, raw, cap=65536):
        r = filt(mode, raw, cap); self.assertEqual(r.returncode, 0, r.stderr); return r.stdout
    def bad(self, mode, raw, cap=65536):
        r = filt(mode, raw, cap); self.assertNotEqual(r.returncode, 0); self.assertEqual(r.stdout, b'')
    def test_shell_syntax_only_and_applets(self):
        subprocess.run(['/bin/sh', '-n', str(ROOT / I['COLLECTOR'])], check=True, capture_output=True)
        self.assertLessEqual(len(BODY.encode()), 32768)
        self.assertNotIn('system(', AWK); self.assertNotIn('getline', AWK)
        calls = set(__import__('re').findall(r'/bin/busybox ([a-z]+)', BODY))
        self.assertEqual(calls, {'awk', 'head', 'od', 'readlink', 'stat', 'uname'})
    def test_uuid_exact_bytes_no_nul_cr_or_truncation(self):
        raw = b'12345678-1234-1234-1234-123456789abc\n'
        self.assertIn(raw.rstrip(), self.good('boot', raw, len(raw)))
        for b in [raw[:-1], raw+b'x\n', raw.replace(b'\n', b'\0\n'), raw.replace(b'\n', b'\r\n'), raw+b'\x1c']:
            self.bad('boot', b)
        self.bad('boot', raw, len(raw)-1)
    def test_empty_controller_list_is_an_explicit_observation(self):
        self.assertEqual(self.good('subtree_control', b'\n'), b'AXHC01\tsubtree_control\tempty\n')
        self.bad('controllers', b'cpu\nmemory\n')

    def test_path_and_mapping(self):
        out = self.good('cgroup_path', b'0::/system.slice/docker-abc.scope\n')
        self.assertEqual(out, b'/system.slice/docker-abc.scope\n')
        for p in [b'/', b'/a/../b', b'/a//b', b'/a;touch-x', b'/a/']:
            self.bad('cgroup_path', b'0::'+p+b'\n')
        self.good('uid_map', b'0 0 4294967295\n')
        self.bad('gid_map', b'0 0 65532\n')
        self.bad('uid_map', b'0 0 4294967296\n')
    def test_limits_events_status(self):
        for mode, raw in [('memory_max', b'134217728\n'), ('swap_max', b'0\n'), ('pids_max', b'16\n'),
                          ('cpu_max', b'50000 100000\n'), ('events', b'populated 1\nfrozen 0\n')]:
            self.good(mode, raw); self.bad(mode, b'max\n')
        self.bad('cpu_max', b'100000 100000\n')
        self.bad('events', b'populated 1\n')
        raw = b'Uid:\t65532\t65532\t65532\t65532\nGid:\t65532\t65532\t65532\t65532\nGroups:\t\nNoNewPrivs:\t1\n'
        raw += b''.join(k+b':\t0000000000000000\n' for k in (b'CapInh', b'CapPrm', b'CapEff', b'CapBnd', b'CapAmb'))
        self.good('status', raw); self.bad('status', raw.replace(b'65532', b'0', 1))
    def test_mount_filter_never_exports_private_source_or_super_options(self):
        raw = b'1 1 0:1 / / ro - overlay secret-token super-secret\n2 1 0:2 / /sys/fs/cgroup ro - cgroup2 secret secret\n3 1 0:3 /private-user /private-path rw - ext4 credential=secret password=secret\n'
        out = self.good('mount_host', raw)
        self.assertNotIn(b'secret', out); self.assertNotIn(b'private', out)
        self.bad('mount_host', raw+raw[:raw.index(b'\n')+1])
        self.bad('mount_host', raw.replace(b'/ / ro', b'/private / ro', 1))
    def test_self_mount_requirements_and_readonly(self):
        paths = [(b'/', b'/', b'overlay'), (b'/', b'/sys/fs/cgroup', b'cgroup2'),
                 (b'/private-artifact', b'/mnt', b'virtiofs'), (b'/sys/kernel/random/boot_id', b'/host-observe/boot-id', b'proc'),
                 (b'/filesystems', b'/host-observe/filesystems', b'proc'), (b'/1/mountinfo', b'/host-observe/init-mountinfo', b'proc'),
                 (b'/', b'/host-observe/cgroup', b'cgroup2')]
        raw = b''.join(str(i+1).encode()+b' 1 0:1 '+r+b' '+p+b' ro - '+f+b' secret secret\n' for i, (r, p, f) in enumerate(paths))
        self.assertNotIn(b'private', self.good('mount_self', raw))
        self.bad('mount_self', raw.replace(b'/mnt ro', b'/mnt rw'))
        self.bad('mount_self', raw.replace(b'/mnt ro -', b'/mnt ro shared:2 -'))


class Inputs(unittest.TestCase):
    def test_real_source_export_and_recomputed_tampering(self):
        with tempfile.TemporaryDirectory(prefix='axiom-channel-l1-') as td:
            base = Path(td).resolve(); root = base/'root'; out = base/'out'; out.mkdir()
            names = I['source_paths'](ROOT)
            for name in names:
                p = root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes((ROOT/name).read_bytes())
            body = (root/I['COLLECTOR']).read_bytes()
            rows = [dict(path=n, bytes=(root/n).stat().st_size, digest=digest((root/n).read_bytes())) for n in names]
            d = dict(format='radishaxiom-private-linux-channel-inputs', version='0.1', scope='offline-source-binding-only',
                     generator=I['GENERATOR'], target='aarch64-unknown-linux-musl', profile=I['PROFILE'], budgets=I['BUDGETS'],
                     collector=dict(path=I['COLLECTOR'], profile=I['PROFILE'], bytes=len(body), digest=digest(body)),
                     collector_reads=I['reads'](), source_set_digest=digest(canonical(rows)), sources=rows, build_inputs=None,
                     native_build='not-accepted', build_ready=False, execution_ready=False)
            (out/'collector.sh').write_bytes(body); (out/'synthetic-report.bin').write_bytes(b'')
            def save(value): (out/'inputs.json').write_bytes(canonical(value))
            save(d); self.assertFalse(I['check'](out, root)['execution_ready'])
            for mutate in [lambda x: x.update(build_ready=True), lambda x: x.update(build_inputs={}),
                           lambda x: x['budgets'].update(pids=32), lambda x: x['sources'].pop()]:
                v = copy.deepcopy(d); mutate(v); v['source_set_digest'] = digest(canonical(v['sources'])); save(v)
                with self.assertRaises(ValueError): I['check'](out, root)
            save(d); (root/names[0]).write_bytes(b'changed')
            with self.assertRaises(ValueError): I['check'](out, root)
            (root/names[0]).unlink(); (root/names[0]).symlink_to(out/'collector.sh')
            with self.assertRaises(ValueError): I['check'](out, root)


if __name__ == '__main__':
    unittest.main()
