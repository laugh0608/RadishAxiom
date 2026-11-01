#!/usr/bin/env python3
"""Synthetic v0.2/runner tests. No target installation, Linux build or collector execution."""
import copy
import hashlib
import json
import os
from pathlib import Path
import runpy
import signal
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
I = runpy.run_path(str(ROOT/'scripts/check-linux-channel-inputs.py'))
W = runpy.run_path(str(ROOT/'scripts/build-linux-channel.py'))
canonical, digest = I['canonical'], I['digest']
COMMIT = '01'*20


def row(p, name=None):
    raw = p.read_bytes()
    return dict(path=str(p) if name is None else name, bytes=len(raw), digest=digest(raw))


def put(p, value):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(canonical(value)); return row(p)


def fixture(base):
    """Deliberately false installation/review; reachable only with synthetic=True."""
    source, bundle, host = base/'source', base/'bundle', base/'host'
    bundle.mkdir(); host.mkdir()
    for name in I['source_paths'](ROOT):
        p = source/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes((ROOT/name).read_bytes()); p.chmod(0o644)
    for n in ('axiom-ir','checker-runtime','checker-runtime-darwin-store','solver-diagnostic-host'):
        p = source/'crates'/n/'Cargo.toml'; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes((ROOT/p.relative_to(source)).read_bytes()); p.chmod(0o644)
    def mat(name, value):
        p = bundle/'materials'/name
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(value)
        return row(p, 'materials/'+name)
    tools = []
    for role in ('cargo','rustc','lld','installer','python','git'):
        p = host/role; p.write_bytes(('synthetic '+role).encode()); tools.append(dict(role=role, version='synthetic-only', file=row(p)))
    refs = [t['file'] for t in tools]
    resolution = dict(format='radishaxiom-private-linux-channel-host-resolution', version='0.2', synthetic=True,
                      decision='reviewed-explicit-host-trust', images_digest=digest(canonical(refs)),
                      edges=[dict(image=r['path'], load='/usr/lib/libSystem.B.dylib', resolved='/usr/lib/libSystem.B.dylib', system=True) for r in refs],
                      limitations=['synthetic, no host resolution occurred'])
    tool_inventory = dict(format='radishaxiom-private-linux-channel-tool-inventory', version='0.2', toolchain=I['TOOLCHAIN'],
                          tools=tools, dylibs=[], resolution=mat('resolution.json', canonical(resolution)),
                          system=dict(os='macOS-aarch64', identity=mat('os.json', b'synthetic OS'), dyld=mat('dyld.json', b'synthetic dyld'),
                                      trust='explicit-trusted-host-not-hermetic'))
    registry=host/'registry-config'; registry.write_bytes(canonical(dict(dl='https://static.crates.io/crates',api='https://crates.io')))
    index=host/'libc-index'
    index.write_bytes(b'\x03\x02\0\0\0etag: synthetic\0' + b'0.2.189\0' + canonical(dict(name='libc',vers='0.2.189',
                      cksum=I['LIBC_CHECKSUM'],yanked=False)) + b'\0')
    tool_inventory['cargo_resolution']=dict(scope='workspace-lock-resolution-only-not-compiled',package='libc',version='0.2.189',
                    checksum=I['LIBC_CHECKSUM'],files=[dict(destination=dest,file=row(p)) for dest,p in
                    zip(I['RESOLVER_DESTINATIONS'],(registry,index))])
    prefix = 'lib/rustlib/'+I['TARGET']+'/'
    files = []
    for i in range(66):
        p = host/(prefix+f'lib/file-{i:02}.a'); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'not an archive\n'); p.chmod(0o644)
        r = row(p, str(p.relative_to(host))); files.append(dict(path=r['path'], mode='0644', bytes=r['bytes'], digest=r['digest']))
    archive, release, metadata = host/'archive', host/'release', host/'components'
    for p in (archive, release, metadata): p.write_bytes(b'synthetic-only\n')
    receipt = dict(format='radishaxiom-private-linux-channel-installation-receipt', version='0.2', target=I['TARGET'],
                   outcome='installed-reconciled', synthetic=True, archive_digest=row(archive)['digest'],
                   files_digest=digest(canonical(files)), metadata=[row(metadata)], unchanged_tools=refs[:3], limitations=['synthetic'])
    target = dict(format='radishaxiom-private-linux-channel-target-payload', version='0.2', target=I['TARGET'], installed_root=str(host),
                  archive=row(archive), release_manifest=row(release), files=files, receipt=mat('installation.json', canonical(receipt)))
    source_rows = []
    for name in I['regular_tree'](source):
        r = row(source/name, name); source_rows.append(dict(path=name, mode='100644', bytes=r['bytes'], digest=r['digest']))
    snapshot = dict(format='radishaxiom-private-linux-channel-source-snapshot', version='0.2', source_commit=COMMIT,
                    files=source_rows, compile_sources=I['source_paths'](source))
    plan = W['make_plan'](str(base/'linux-channel-build-synthetic'), tools)
    parts = (snapshot, target, tool_inventory, plan)
    side_refs = []
    for name, d in zip(I['SIDECARS'], parts):
        put(bundle/name, d); side_refs.append(row(bundle/name, name))
    review = dict(format='radishaxiom-private-linux-channel-input-review', version='0.2', scope='finite-diagnostic-build-inputs',
                  decision='accepted-for-one-diagnostic-build', synthetic=True, source_commit=COMMIT, objects=side_refs.copy(),
                  decisions=[mat('decision.txt', b'SYNTHETIC ONLY. No object was accepted.')],
                  licenses=[mat('license.txt', b'SYNTHETIC ONLY. No license review occurred.')],
                  trust=['synthetic-only'], limitations=['not a real build input'])
    put(bundle/'input-review.json', review); side_refs.append(row(bundle/'input-review.json', 'input-review.json'))
    request = dict(source_commit=COMMIT, sidecars=side_refs)
    (bundle/'request.json').write_bytes(canonical(request))
    body = (source/I['COLLECTOR']).read_bytes(); (bundle/'collector.sh').write_bytes(body)
    srcs = [row(source/n,n) for n in I['source_paths'](source)]
    root = dict(format='radishaxiom-private-linux-channel-inputs', version='0.2', scope='target-build-input-binding',
                generator=I['GENERATOR'], target=I['TARGET'], profile=I['PROFILE'], budgets=I['BUDGETS'],
                collector=dict(path=I['COLLECTOR'], profile=I['PROFILE'], bytes=len(body), digest=digest(body)),
                collector_reads=I['reads'](), source_set_digest=digest(canonical(srcs)), sources=srcs, build_inputs=request,
                native_build='not-accepted', build_ready=False, execution_ready=False)
    (bundle/'inputs.json').write_bytes(canonical(root))
    return source, bundle, root


class Binding(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='axiom-channel-v02-'); self.base = Path(self.temp.name).resolve()
        self.source, self.bundle, self.root = fixture(self.base)
    def tearDown(self): self.temp.cleanup()
    def check(self, synthetic=True, review_digest=None):
        return I['check_v02'](self.bundle, self.source, COMMIT,
                              review_digest or row(self.bundle/'input-review.json')['digest'], synthetic=synthetic)
    def save(self): (self.bundle/'inputs.json').write_bytes(canonical(self.root))
    def rebind(self, name, value, update_review=False):
        put(self.bundle/name, value)
        refs = self.root['build_inputs']['sidecars']; idx = I['SIDECARS'].index(name); refs[idx] = row(self.bundle/name, name)
        if update_review and name != 'input-review.json':
            review = json.loads((self.bundle/'input-review.json').read_bytes()); review['objects'] = refs[:-1]
            put(self.bundle/'input-review.json', review); refs[-1] = row(self.bundle/'input-review.json', 'input-review.json')
        self.save()
    def test_synthetic_full_binding_and_production_refusal(self):
        result = self.check(); self.assertEqual(result['scope'], 'synthetic-v02-binding-only')
        self.assertFalse(result['build_ready']); self.assertGreater(len(json.loads((self.bundle/'target-payload.json').read_bytes())['files']),64)
        with self.assertRaises(ValueError): self.check(False)
    def test_legacy_null_missing_scope_and_readiness(self):
        original = copy.deepcopy(self.root)
        for change in (dict(version='0.1'), dict(scope='offline-source-binding-only'), dict(build_inputs=None), dict(build_inputs={}),
                       dict(build_ready=True), dict(execution_ready=True), dict(native_build='accepted')):
            self.root = copy.deepcopy(original); self.root.update(change); self.save()
            with self.assertRaises((ValueError, TypeError)): self.check()
    def test_raw_sidecar_tampering_and_external_review_pin(self):
        for name in I['SIDECARS']:
            p = self.bundle/name; raw = p.read_bytes(); p.write_bytes(raw+b' ')
            with self.assertRaises(ValueError): self.check()
            p.write_bytes(raw)
        with self.assertRaises(ValueError): self.check(review_digest='sha256:'+'00'*32)
    def test_rehashed_false_review_and_unregistered_objects(self):
        review = json.loads((self.bundle/'input-review.json').read_bytes())
        for key, val in (('decision','not-assessed'),('objects',[]),('decisions',[]),('licenses',[]),('trust',[]),('synthetic',False)):
            bad = copy.deepcopy(review); bad[key] = val; self.rebind('input-review.json',bad)
            with self.assertRaises(ValueError): self.check()
    def test_missing_installed_file_extra_file_and_receipt_drift(self):
        d = json.loads((self.bundle/'target-payload.json').read_bytes()); p = Path(d['installed_root'])/d['files'][0]['path']
        raw = p.read_bytes(); p.unlink()
        with self.assertRaises(ValueError): self.check()
        p.write_bytes(raw); extra = p.parent/'extra.a'; extra.write_bytes(b'extra')
        with self.assertRaises(ValueError): self.check()
        extra.unlink(); p.write_bytes(b'drift')
        with self.assertRaises(ValueError): self.check()
    def test_argv_config_and_budget_drift_even_rehashed(self):
        original = json.loads((self.bundle/'build-plan.json').read_bytes())
        for mutation in (lambda x:x['argv'].append('--release'), lambda x:x['rustflags'].append('-Cpanic=unwind'),
                         lambda x:x['env'].update(RUSTFLAGS='-Cpanic=unwind'), lambda x:x['limits'].update(total_seconds=601),
                         lambda x:x['profile'].update(lto=True), lambda x:x['recorder']['entry'].update(digest='sha256:'+'00'*32)):
            bad=copy.deepcopy(original); mutation(bad); self.rebind('build-plan.json', bad, True)
            with self.assertRaises(ValueError): self.check()
    def test_source_digest_rehashed_still_rejected(self):
        p = self.source/self.root['sources'][0]['path']; p.write_bytes(b'changed')
        for r in self.root['sources']:
            if r['path'] == str(p.relative_to(self.source)): r.update(row(p,r['path']))
        self.root['source_set_digest'] = digest(canonical(self.root['sources'])); self.save()
        with self.assertRaises(ValueError): self.check()
    def test_symlink_paths_and_large_sidecar_parser_boundaries(self):
        p = self.bundle/'collector.sh'; p.unlink(); p.symlink_to(self.source/I['COLLECTOR'])
        with self.assertRaises(ValueError): self.check()
        for value in (b'['*17+b'0'+b']'*17, b'['+b','.join([b'0']*4097)+b']', b'{"x":0,"x":0}', b'{"x":-1}', b'{"x":1.0}', b'"'+b'a'*1025+b'"'):
            with self.assertRaises(ValueError): I['sidecar'](value)
        self.assertEqual(len(I['sidecar'](canonical(list(range(4096))))),4096)
        with self.assertRaises(ValueError): I['parse'](canonical(list(range(65))))
    def test_fixed_plan_independent_agreement_and_graph(self):
        tools = json.loads((self.bundle/'tool-inventory.json').read_bytes())['tools']
        plan = W['make_plan'](str(self.base/'linux-channel-build-synthetic'), tools)
        self.assertEqual(plan, I['expected_plan'](plan['task_root'],[x['file'] for x in tools]))
        self.assertEqual(W['launcher'](plan['task_root'],plan['recorder']['python']),I['expected_launcher'](plan['task_root'],plan['recorder']['python']))
        W['graph'](self.source)
        p=self.source/'crates/digest/Cargo.toml'; original=p.read_text(); p.write_text(original+'\n[build-dependencies]\nx = "1"\n')
        with self.assertRaises(ValueError): W['graph'](self.source)
    def test_receipt_metadata_and_host_closure_refusal(self):
        d = json.loads((self.bundle/'tool-inventory.json').read_bytes())
        p = Path(d['tools'][0]['file']['path']); p.write_bytes(b'changed tool')
        with self.assertRaises(ValueError): self.check()
    def test_config_presence_without_reading_contents(self):
        task=self.base/'task'; task.mkdir(); cargo=self.base/'cargo-home'; cargo.mkdir()
        W['cargo_configs'](task,cargo)
        config=task/'.cargo/config.toml'; config.parent.mkdir(); config.write_bytes(b'do not read me')
        with self.assertRaisesRegex(ValueError,'unbound-cargo-config'): W['cargo_configs'](task,cargo)

    def test_resolver_metadata_binding_and_closed_copy(self):
        d=json.loads((self.bundle/'tool-inventory.json').read_bytes())
        I['check_cargo_resolution'](d['cargo_resolution'],self.bundle,self.source,True)
        home=self.base/'new-cargo-home'; home.mkdir()
        W['seed_resolution'](home,d['cargo_resolution'])
        self.assertEqual(I['regular_tree'](home),sorted(I['RESOLVER_DESTINATIONS']))
        with self.assertRaises(FileExistsError): W['seed_resolution'](home,d['cargo_resolution'])
        for mutate in (lambda x:x['files'][0].update(destination='../escape'), lambda x:x.update(version='0.2.188'),
                       lambda x:x.update(scope='compiled-dependency'), lambda x:x['files'].pop()):
            bad=copy.deepcopy(d['cargo_resolution']); mutate(bad)
            with self.assertRaises(ValueError):I['check_cargo_resolution'](bad,self.bundle,self.source,True)
        p=Path(d['cargo_resolution']['files'][1]['file']['path']); p.write_bytes(b'wrong index')
        with self.assertRaises(ValueError):self.check()

    @unittest.skipUnless(sys.platform == 'darwin','Mac host supervision only')
    def test_generated_recorder_executes_only_bound_version_probe(self):
        # The real OS runs only this synthetic Python script, never rustc/Linux.
        tools=json.loads((self.bundle/'tool-inventory.json').read_bytes())['tools']
        rustc=Path(tools[1]['file']['path'])
        rustc.write_text(f'#!{Path(sys.executable).resolve()} -ISB\nprint("synthetic-rustc-version")\n'); rustc.chmod(0o755)
        tools[1]['file']=row(rustc)
        tools[4]['file']=row(Path(sys.executable).resolve())
        inventory=json.loads((self.bundle/'tool-inventory.json').read_bytes()); inventory['tools']=tools
        put(self.bundle/'tool-inventory.json',inventory)
        plan=W['make_plan'](str(self.base),tools)
        put(self.bundle/'build-plan.json',plan)
        self.root['build_inputs']['sidecars'][2]=row(self.bundle/'tool-inventory.json','tool-inventory.json')
        self.root['build_inputs']['sidecars'][3]=row(self.bundle/'build-plan.json','build-plan.json')
        self.save()
        records=self.base/'records'; records.mkdir()
        for name in ('inputs.json','build-plan.json','tool-inventory.json'):
            (records/name).write_bytes((self.bundle/name).read_bytes())
        entry=self.base/'tools/rustc-record'; entry.parent.mkdir()
        entry.write_bytes(W['launcher'](str(self.base),plan['recorder']['python'])); entry.chmod(0o755)
        env=dict(plan['env']); env['CARGO_ENCODED_RUSTFLAGS']='\x1f'.join(plan['rustflags'])
        s=W['Session'](self.base,seconds=3)
        out,_=s.run([str(entry),str(rustc),'-vV'],self.source,env)
        self.assertEqual(out,b'synthetic-rustc-version\n')
        record=json.loads((records/'argv-0000.json').read_bytes())
        self.assertEqual(record['kind'],'version-probe'); self.assertEqual(record['argv'],[str(rustc),'-vV'])
        with self.assertRaisesRegex(ValueError,'command-failed'):
            s.run([str(entry),'/unregistered/executable','-vV'],self.source,env)
        self.assertFalse((records/'argv-0001.json').exists())
        for i in range(1,64):(records/f'argv-{i:04}.json').write_bytes(b'occupied')
        with self.assertRaisesRegex(ValueError,'command-failed'):
            s.run([str(entry),str(rustc),'-vV'],self.source,env)
        self.assertEqual(len(list(records.glob('argv-*.json'))),64)



@unittest.skipUnless(sys.platform == 'darwin','Mac host supervision only')
class Runner(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='axiom-channel-runner-'); self.root=Path(self.temp.name).resolve()
        self.env=dict(PATH='/usr/bin:/bin',LANG='C',LC_ALL='C')
    def tearDown(self): self.temp.cleanup()
    def command(self, body): return [str(Path(sys.executable).resolve()),'-c',body]
    def test_success_failure_and_no_inherited_env(self):
        s=W['Session'](self.root,seconds=2)
        out,err=s.run(self.command('import os; print(os.environ.get("AXIOM_SYNTHETIC_SECRET","absent"))'),self.root,self.env)
        self.assertEqual(out,b'absent\n'); self.assertEqual(err,b'')
        with self.assertRaisesRegex(ValueError,'command-failed-7'):
            s.run(self.command('raise SystemExit(7)'),self.root,self.env)
    def test_deadline_shared_without_renewal(self):
        s=W['Session'](self.root,seconds=0.25)
        s.run(self.command('import time; time.sleep(0.12)'),self.root,self.env)
        with self.assertRaisesRegex(ValueError,'total-deadline'):
            s.run(self.command('import time; time.sleep(0.3)'),self.root,self.env)
        self.assertTrue(all(not s.group_present(pid) for pid in s.children))
    def test_cancellation_reaps_owned_group(self):
        s=W['Session'](self.root,seconds=2)
        t=threading.Timer(0.1,lambda:setattr(s,'cancelled',True)); t.start()
        try:
            with self.assertRaisesRegex(ValueError,'cancelled'):
                s.run(self.command('import time; time.sleep(1)'),self.root,self.env)
        finally:t.cancel(); t.join()
        self.assertTrue(all(not s.group_present(pid) for pid in s.children))
    def test_output_and_combined_log_limits(self):
        s=W['Session'](self.root,seconds=2)
        with self.assertRaisesRegex(ValueError,'command-output-limit'):
            s.run(self.command('print("x"*2048)'),self.root,self.env,output_limit=1024)
        s=W['Session'](self.root,seconds=2,log_bytes=1024)
        with (self.root/'stdout').open('xb',buffering=0) as out,(self.root/'stderr').open('xb',buffering=0) as err:
            with self.assertRaisesRegex(ValueError,'combined-log-limit'):
                s.run(self.command('import sys; print("x"*600); print("y"*600,file=sys.stderr)'),self.root,self.env,logs=(out,err))
    def test_task_growth_and_map_limit(self):
        s=W['Session'](self.root,seconds=2,task_bytes=1024)
        with self.assertRaisesRegex(ValueError,'task-size-limit'):
            s.run(self.command('from pathlib import Path; Path("large").write_bytes(b"x"*2048)'),self.root,self.env)
        (self.root/'large').unlink(); (self.root/'records').mkdir()
        with (self.root/'records/link.map').open('wb') as f: f.truncate(8388609)
        with self.assertRaisesRegex(ValueError,'artifact-growth-limit'): W['Session'](self.root).measure()
    def test_special_files_and_short_write(self):
        with patch.object(W['signal'],'getsignal',return_value=signal.SIG_IGN):
            with self.assertRaisesRegex(ValueError,'child-wait-owner-not-established'):W['Session'](self.root)
        p=self.root/'pipe'; os.mkfifo(p)
        with self.assertRaisesRegex(ValueError,'task-special-file'): W['Session'](self.root).measure()
        p.unlink()
        class Short:
            def write(self,_b): return 0
        with self.assertRaisesRegex(ValueError,'log-short-write'):
            W['Session'](self.root).run(self.command('print("test")'),self.root,self.env,logs=(Short(),Short()))
    def test_enospc_and_zero_write_remain_failures(self):
        with patch.object(W['os'],'write',side_effect=OSError(28,'synthetic ENOSPC')):
            with self.assertRaises(OSError):W['new_file'](self.root/'enospc',b'owned')
        with patch.object(W['os'],'write',return_value=0):
            with self.assertRaisesRegex(ValueError,'short-write'):W['new_file'](self.root/'zero-write',b'owned')
    def test_unknown_descendant_never_becomes_success_and_preserves_both_errors(self):
        s=W['Session'](self.root,seconds=2)
        with patch.object(s,'group_members',side_effect=lambda pid:[pid,pid+1]):
            with self.assertRaisesRegex(ValueError,'unexpected-live-descendant; cleanup: (group-signal|descendant-stop)-unconfirmed'):
                s.run(self.command('pass'),self.root,self.env)

    def test_fresh_task_rejects_before_creation(self):
        bundle=self.root/'bundle'; bundle.mkdir(); task=self.root/'.tmp/linux-channel-build-synthetic'
        with self.assertRaises((ValueError, FileNotFoundError)):
            W['build'](str(self.root),str(bundle),COMMIT,'sha256:'+'00'*32,str(task))
        self.assertFalse(task.exists())
    def test_real_closed_stdio_descendant_is_rejected_before_leader_reap(self):
        s=W['Session'](self.root,seconds=3)
        code='import os,time; p=os.fork(); '\
             'os._exit(0) if p else None; os.close(1); os.close(2); time.sleep(2)'
        with self.assertRaisesRegex(ValueError,'unexpected-live-descendant'):
            s.run(self.command(code),self.root,self.env)
        self.assertTrue(all(not s.group_present(pid) for pid in s.children))

    def test_snapshot_from_exact_scripted_git_blobs(self):
        data=b'synthetic\n'; blob=hashlib.sha1(b'blob 10\0'+data).hexdigest()
        class Git:
            root=self.root
            def run(_self,argv,*_args,**_kwargs):
                op=argv[argv.index('-C')+2:]
                if op==['rev-parse','HEAD']:return (COMMIT+'\n').encode(),b''
                if op[0]=='status':return b'',b''
                if op[0]=='ls-tree':return f'100644 blob {blob}      10\tfile\0'.encode(),b''
                if op[0]=='cat-file':return data,b''
                raise AssertionError(op)
            def checkpoint(_self):pass
            def measure(_self):pass
        source=W['snapshot'](self.root,COMMIT,'/synthetic/git',Git())
        self.assertEqual((source/'file').read_bytes(),data)


class Argv(unittest.TestCase):
    def setUp(self):
        self.plan=W['make_plan']('/tmp/linux-channel-build-synthetic',[dict(role=r,file=dict(path='/tmp/'+r)) for r in
                      ('cargo','rustc','lld','installer','python','git')])
    def unit(self):
        p=self.plan; out=p['task_root']+'/target/'+I['TARGET']+'/linux-channel/deps'
        return [p['env']['RUSTC'],'--crate-name','radishaxiom_digest','--edition=2024','crates/digest/src/lib.rs',
                '--error-format=json','--json=diagnostic-rendered-ansi,artifacts,future-incompat','--crate-type','lib',
                '--emit=dep-info,metadata,link','-C','opt-level=2','-C','panic=abort','--out-dir',out,'--target',I['TARGET'],
                '-L','dependency='+out,*p['rustflags']]
    def test_registered_unit_and_version_probe(self):
        self.assertEqual(W['rustc_argv'](self.plan,self.unit()),'radishaxiom_digest')
        self.assertEqual(W['rustc_argv'](self.plan,['/tmp/rustc','-vV']),'version-probe')
        self.assertEqual(W['rustc_argv'](self.plan,['/tmp/rustc',*W['HOST_PROBE']]),'host-probe')
    def test_unknown_executable_units_injections_and_order(self):
        a=self.unit()
        for bad in ([a[0]+'-other',*a[1:]], [a[0],a[1],'libc',*a[3:]], [*a,'@response'], [*a[:-2]],
                    [*a[:-28],'--cfg','test',*a[-28:]],
                    [*a[:-28],'-C','opt-level=3',*a[-28:]],
                    [*a[:-28],'--sysroot','/unreviewed',*a[-28:]]):
            with self.assertRaises(ValueError):W['rustc_argv'](self.plan,bad)
    def test_target_probe_is_closed(self):
        a=['/tmp/rustc','-','--crate-name','___','--print=sysroot','--target',I['TARGET'],'--crate-type','bin',*self.plan['rustflags']]
        self.assertEqual(W['rustc_argv'](self.plan,a),'target-probe')
        # Cargo puts the same encoded flags before its target probe options.
        middle=a[:4]+self.plan['rustflags']+a[4:-28]+['-Wwarnings']
        self.assertEqual(W['rustc_argv'](self.plan,middle),'target-probe')
        a[4]='--print=arbitrary'
        with self.assertRaises(ValueError):W['rustc_argv'](self.plan,a)


if __name__=='__main__':unittest.main()
