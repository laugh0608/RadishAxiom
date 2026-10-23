#!/usr/bin/env python3
"""Explicitly authorized read-only C1 verifier preflight; never create/start/pull."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PREVIOUS = ROOT / 'docs/records/rust-linux-input-review/run-musl-verifier-smoke.py'
CLI_SHA = '4a728ee98f89005a90198a9be791e8fdaebbcb5e6af9721251efe0113df37759'
IMAGE = 'sha256:55063921d0e996f717092e07dce8041cb2376cc171a070bf9a0a38a5dd16c777'
OUTPUT = ROOT / 'artifacts/cvc5-c1-verifier-preflight-2026-10-23-attempt-2'


def main():
    spec = importlib.util.spec_from_file_location('smoke', PREVIOUS)
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    # Current-task approval accepts this exact CLI only. Historical source stays unchanged.
    smoke.DOCKER_SHA = CLI_SHA
    OUTPUT.mkdir(mode=0o700)
    report = {'format': 'radishaxiom-private-cvc5-verifier-preflight', 'version': '0.1',
              'docker_cli': {'path': smoke.DOCKER, 'sha256': CLI_SHA}, 'image': IMAGE,
              'method_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'reused_method_sha256': hashlib.sha256(PREVIOUS.read_bytes()).hexdigest(),
              'started_utc': smoke.now(), 'passed': False, 'container_created': False,
              'current_task_cli_trust_accepted': True, 'current_task_daemon_trust_accepted': True}
    try:
        rootfs, _ = smoke.verified_inputs()
        report['rootfs'] = smoke.identity(rootfs)
        engine = smoke.Docker(OUTPUT)
        version_fields = ['Server.Version', 'Server.ApiVersion', 'Server.Os', 'Server.Arch']
        version = json.loads(smoke.checked(engine.call(['version', '--format', smoke.template(version_fields)])))
        report['daemon'] = version
        smoke.require(version == {'Server.Version': '29.8.2', 'Server.ApiVersion': '1.56',
                                  'Server.Os': 'linux', 'Server.Arch': 'arm64'}, 'current-task daemon changed')
        fields = ['MemoryLimit', 'SwapLimit', 'PidsLimit', 'CpuCfsPeriod', 'CpuCfsQuota', 'CgroupVersion', 'SecurityOptions']
        info = json.loads(smoke.checked(engine.call(['info', '--format', smoke.template(fields)])))
        report['resource_capabilities'] = info
        smoke.require(all(info.get(key) is True for key in fields[:5]) and info.get('CgroupVersion') == '2' and
                      info.get('SecurityOptions') == ['name=seccomp,profile=builtin', 'name=cgroupns'], 'resource report changed')
        image = smoke.inspect(engine, 'image', IMAGE, smoke.IMAGE_FIELDS)
        smoke.validate_image(image, IMAGE)
        report.update(passed=True, image_observed=image)
    except (OSError, ValueError, KeyError, TypeError) as error:
        report['failure'] = str(error)
    report['finished_utc'] = smoke.now()
    raw = (json.dumps(report, indent=2) + '\n').encode()
    (OUTPUT / 'result.json').write_bytes(raw)
    (HERE / 'verifier-preflight.json').write_bytes(raw)
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized', action='store_true', required=True)
    parser.add_argument('--current-daemon-authorized', action='store_true', required=True)
    parser.parse_args()
    raise SystemExit(main())
