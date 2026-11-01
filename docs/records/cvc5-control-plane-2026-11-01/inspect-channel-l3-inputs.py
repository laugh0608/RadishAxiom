#!/usr/bin/env python3
"""Fixed L3 read-only observation. No downloads, extraction, install or builds.

Reuses the historical bounded target-archive reader, compares all logical
members to its retained inventory and only hashes/reads selected local metadata.
This is a diagnostic record, never a production installer or acceptance path.
"""
import gzip
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'docs/records/rust-linux-input-review'
SYSROOT = Path('/Users/luobo/.rustup/toolchains/1.97.1-aarch64-apple-darwin')
RUSTUP = Path('/Users/luobo/.cargo/bin/rustup')
TARGET = 'aarch64-unknown-linux-musl'
NAME = 'rust-std-1.97.1-'+TARGET+'.tar.xz'
ARCHIVE = ROOT / '.tmp/rust-linux-inputs-bb014fd' / NAME
SHA = '49ff0879d94e2e8e86d5e85eb15a9215943e8c78b51363d6553443598cab5d31'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fact(path, limit=256*1024**2):
    require(not path.is_symlink() and path.is_file(), 'regular-file-required')
    before = path.stat()
    require(before.st_size <= limit, 'file-size-limit')
    with path.open('rb') as f:
        sha = hashlib.file_digest(f, 'sha256').hexdigest()
    after = path.stat()
    require((before.st_size,before.st_mtime_ns,before.st_ctime_ns) ==
            (after.st_size,after.st_mtime_ns,after.st_ctime_ns), 'file-changed')
    return dict(path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                bytes=before.st_size, digest='sha256:'+sha)


def observe():
    manifest = OLD/'channel-rust-1.97.1.toml'
    require(fact(manifest)['digest'] == 'sha256:03569b1886ceb5c05276b50c8431ab111de944cd6140fe1fa7d821dd8e0f29cf', 'release-manifest')
    published = tomllib.loads(manifest.read_text())
    selected = published['pkg']['rust-std']['target'][TARGET]
    require(selected['available'] is True and selected['xz_hash'] == SHA and
            selected['xz_url'] == 'https://static.rust-lang.org/dist/2026-07-16/'+NAME, 'package-selection')
    require(fact(ARCHIVE)['digest'] == 'sha256:'+SHA, 'retained-target-package')
    # Reuse the exact old reader, selecting only musl; do not invoke its main
    # which would also rescan the unrelated GNU host archive.
    method = OLD/'inspect-archives.py'
    reader = runpy.run_path(str(method))
    fresh = reader['inspect'](ARCHIVE, SHA)
    inventory_raw = (OLD/'archive-inventory.json.gz').read_bytes()
    require(len(inventory_raw) == 3188514 and hashlib.sha256(inventory_raw).hexdigest() ==
            '53ab99369b0cc344bd732feb749873d0c2d1b2ec59a591ece983bc67f41f2a7f', 'retained-inventory-bytes')
    inventory_json = gzip.decompress(inventory_raw)
    require(len(inventory_json) == 28225710 and hashlib.sha256(inventory_json).hexdigest() ==
            'aef0833c6220ac259ee52decde39cb0590f7d2963b7f208c791c58bc6eae83da', 'retained-inventory-json')
    retained = json.loads(inventory_json)
    expected = next(x for x in retained['archives'] if x['file'] == NAME)
    require(fresh == expected, 'complete-target-inventory-drift')
    payload = []
    rows = {x['path']:x for x in fresh['members']}
    top = NAME.removesuffix('.tar.xz')
    for claim in fresh['component_claims']:
        require(claim['component'] == 'rust-std-'+TARGET and claim['kind'] == 'file', 'component-claim')
        row = rows[top+'/'+claim['component']+'/'+claim['path']]
        payload.append(dict(path=claim['path'],bytes=row['bytes'],digest='sha256:'+row['sha256'],mode=row['mode']))
    require(len(payload) == 66 and sum(x['bytes'] for x in payload) == 152642974, 'payload-total')
    rustlib = SYSROOT/'lib/rustlib'
    installed_manifest = rustlib/'multirust-channel-manifest.toml'
    installed = tomllib.loads(installed_manifest.read_text())
    projected = installed['pkg']['rust-std']['target'][TARGET]
    require(installed['date'] == published['date'] and all(projected[k] == v for k,v in selected.items()), 'installed-release-selection')
    prior = json.loads((ROOT/'docs/records/cvc5-control-plane-2026-11-01/channel-build-input-candidate.json').read_text())
    tools = []
    for old in prior['tools']:
        current = fact(Path(old['path']))
        require(current['bytes'] == old['bytes'] and current['digest'] == 'sha256:'+old['sha256'], 'host-tool-drift')
        tools.append(dict(name=old['name'],**current))
    tools.append(dict(name='rustup',**fact(RUSTUP)))
    # Read version only; pin this process without modifying the user's default.
    env = dict(RUSTUP_HOME='/Users/luobo/.rustup', RUSTUP_TOOLCHAIN='1.97.1-aarch64-apple-darwin',
               RUSTUP_AUTO_INSTALL='0', LANG='C', LC_ALL='C')
    version = subprocess.run([str(RUSTUP),'--version'],capture_output=True,timeout=8,env=env,check=True)
    require(len(version.stdout)<=4096 and len(version.stderr)<=4096, 'version-output-limit')
    first_line = version.stdout.decode('ascii').splitlines()[0]
    lld = SYSROOT/'lib/rustlib/aarch64-apple-darwin/bin/rust-lld'
    help_output = subprocess.run([str(lld),'-flavor','gnu','--help'],capture_output=True,timeout=8,env={'LANG':'C','LC_ALL':'C'},check=True)
    require(len(help_output.stdout)<=65536 and len(help_output.stderr)<=65536, 'linker-help-limit')
    require(all(flag in help_output.stdout for flag in [b'--why-extract=',b'--trace ',b'--Map=']), 'linker-trace-flags')
    require(first_line == 'rustup 1.29.0 (28d1352db 2026-03-05)', 'installer-version')
    # Reuse byte-bound selected source/license text; no 3.7 GiB source rescan.
    full_path = ROOT/'.tmp/rust-source-review-1262570/source-recipes-final-full.json'
    fact(full_path, 16*1024**2)
    full = json.loads(full_path.read_text())
    old_source = json.loads((OLD/'source-recipes-2026-09-10.json').read_text())
    require({k:v for k,v in full.items() if k!='selected_files'} ==
            {k:v for k,v in old_source.items() if k!='selected_files'}, 'source-observation-metadata')
    require([{k:v for k,v in x.items() if k!='text'} for x in full['selected_files']] == old_source['selected_files'], 'source-observation-files')
    licenses = []
    wanted = ('/LICENSE-APACHE','/LICENSE-MIT','/COPYRIGHT','/library/compiler-builtins/LICENSE.txt',
              '/src/llvm-project/compiler-rt/LICENSE.TXT','/src/llvm-project/libunwind/LICENSE.TXT')
    for row in full['selected_files']:
        raw = row['text'].encode('utf-8')
        require(len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'], 'retained-source-text')
        if row['path'].endswith(wanted):
            licenses.append(dict(path=row['path'],bytes=row['bytes'],digest='sha256:'+row['sha256']))
    require(len(licenses) == 6, 'license-selection')
    configs = []
    for ancestor in [ROOT,*ROOT.parents]:
        for name in ['config','config.toml']:
            p = ancestor/'.cargo'/name
            if p.exists(): configs.append(str(p)) # Never read config values.
    return dict(format='radishaxiom-private-linux-channel-l3-input-observation',version='0.1',
        scope='retained-target-and-installed-host-metadata-only',base_commit='5dab738',
        target=TARGET,release_date=published['date'],release_manifest=fact(manifest),
        target_package=dict(**fact(ARCHIVE),url=selected['xz_url']),
        archive_inventory=dict(files=78,directories=7,tar_bytes=fresh['tar_bytes'],
                               tar_digest='sha256:'+fresh['tar_sha256'],matches_complete_retained_inventory=True),
        target_payload=dict(files=len(payload),bytes=sum(x['bytes'] for x in payload),inventory=payload),
        target_root_present=(rustlib/TARGET).exists(),
        target_component_manifest_present=(rustlib/('manifest-rust-std-'+TARGET)).exists(),
        proposed_download_cache_present=(Path('/Users/luobo/.rustup/downloads')/SHA).exists(),
        proposed_download_partial_present=(Path('/Users/luobo/.rustup/downloads')/(SHA+'.partial')).exists(),
        installed_channel_manifest=fact(installed_manifest),
        installed_metadata=[fact(rustlib/n,2*1024**2) for n in ['components','multirust-config.toml']],
        installed_components=(rustlib/'components').read_text().splitlines(),
        tools=tools,rustup_version=first_line,ancestor_cargo_configs=configs,
        linker_help=dict(argv=[str(lld),'-flavor','gnu','--help'],exit_code=0,stdout_bytes=len(help_output.stdout),stdout_digest='sha256:'+hashlib.sha256(help_output.stdout).hexdigest(),stderr_bytes=len(help_output.stderr),supports=['--Map=','--trace','--why-extract=']),
        retained_rust_source=fact(ROOT/'.tmp/rust-source-review-1262570/rustc-1.97.1-src.tar.xz'),
        selected_source_license_metadata=licenses,
        methods=[fact(Path(__file__).resolve()),fact(method),fact(OLD/'source-recipes-2026-09-10.json')],
        target_tool_acceptance='not-established',build_ready=False,execution_ready=False,
        component_installation_performed=False,linux_artifact_built=False,collector_executed=False,
        created_or_started_environment=False,
        limitations=['logical archive comparison only; no install or archive-member link qualification',
                     'old Rust signing-key SHA-1 self-certification gap retained; no new signature verification',
                     'host dylib/system runtime closure and precise final archive-member/license association pending'])


if __name__ == '__main__':
    print(json.dumps(observe(),ensure_ascii=False,sort_keys=True,indent=2))
