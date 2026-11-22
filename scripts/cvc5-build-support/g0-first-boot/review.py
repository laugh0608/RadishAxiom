#!/usr/bin/env python3
"""Review an existing G0 bundle without creating or starting a VM."""

import gzip
import hashlib
import json
from pathlib import Path
import plistlib
import stat
import struct
import subprocess
import sys
import tempfile


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def invoke(argv):
    return subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
                          env={'PATH': '/usr/bin:/bin'})


def checked(result):
    require(result.returncode == 0, result.stderr.decode(errors='replace'))
    return result.stdout


def check_initramfs(path, expected_init):
    with gzip.open(path, 'rb') as stream:
        data = stream.read(8 * 1024 * 1024 + 1)
    require(len(data) <= 8 * 1024 * 1024, 'initramfs expanded limit')
    entries = {}
    offset = 0
    while offset < len(data):
        require(data[offset:offset + 6] == b'070701', 'newc magic')
        fields = [int(data[index:index + 8], 16) for index in range(offset + 6, offset + 110, 8)]
        _, mode, uid, gid, links, mtime, size, devmajor, devminor, major, minor, length, checksum = fields
        require((uid, gid, mtime, devmajor, devminor, checksum) == (0, 0, 0, 0, 0, 0), 'newc identity')
        require(links == (2 if stat.S_ISDIR(mode) else 1), 'newc link count')
        key = data[offset + 110:offset + 110 + length]
        require(len(key) == length and key.endswith(b'\0') and b'\0' not in key[:-1], 'newc name')
        name = key[:-1].decode('ascii')
        offset = (offset + 110 + length + 3) & ~3
        payload = data[offset:offset + size]
        require(len(payload) == size and name not in entries, 'newc duplicate or truncated entry')
        offset = (offset + size + 3) & ~3
        entries[name] = (mode, major, minor, payload)
        if name == 'TRAILER!!!':
            break
    require(offset == len(data) and list(entries) == [
        'dev', 'dev/console', 'dev/null', 'init', 'proc', 'sys', 'virtio_mmio.ko', 'TRAILER!!!',
    ], 'initramfs entry inventory or trailing content')
    require(entries['TRAILER!!!'] == (0, 0, 0, b''), 'newc trailer')
    for name, mode in (('dev', 0o755), ('proc', 0o555), ('sys', 0o555)):
        require(entries[name] == (stat.S_IFDIR | mode, 0, 0, b''), 'initramfs mountpoint identity')
    require(entries['dev/console'] == (stat.S_IFCHR | 0o600, 5, 1, b'') and
            entries['dev/null'] == (stat.S_IFCHR | 0o666, 1, 3, b''), 'initramfs device inventory')
    mode, major, minor, init = entries['init']
    require((mode, major, minor) == (stat.S_IFREG | 0o555, 0, 0), 'PID 1 executable properties')
    require({'bytes': len(init), 'sha256': digest(init)} == expected_init, 'PID 1 executable binding')
    require(init[:7] == b'\x7fELF\x02\x01\x01' and struct.unpack_from('<HH', init, 16) == (2, 183),
            'PID 1 is not AArch64 LE ET_EXEC')
    offset = struct.unpack_from('<Q', init, 32)[0]
    size, count = struct.unpack_from('<HH', init, 54)
    require(size == 56 and 0 < count < 64 and 64 <= offset <= offset + size * count <= len(init), 'ELF PHDRs')
    headers = {struct.unpack_from('<I', init, offset + i * size)[0] for i in range(count)}
    require(1 in headers and not {2, 3} & headers, 'PID 1 contains interpreter or dynamic linkage')
    mode, major, minor, module = entries['virtio_mmio.ko']
    require((mode, major, minor) == (stat.S_IFREG | 0o444, 0, 0) and
            digest(module) == '97c9144f7c1c4e8d38a4cef9b83fec13214b4eb90bb49b438f546a1711279b26', 'transport module')
    return list(entries)[:-1]


def review(bundle):
    build = json.loads((bundle / 'build.json').read_bytes())
    launch = bundle / 'g0-first-boot'
    image, ram = bundle / 'Image', bundle / 'initramfs.cpio.gz'
    for path, mode in ((launch, 0o555), (image, 0o444), (ram, 0o444)):
        require(not path.is_symlink() and stat.S_IMODE(path.stat().st_mode) == mode and
                {'bytes': path.stat().st_size, 'sha256': digest(path.read_bytes())} == build['boot_files'][path.name],
                'boot bundle file identity')
    sources = Path(__file__).resolve().parent
    for name, metadata in build['materials'].items():
        raw = (sources / name).read_bytes()
        require({'bytes': len(raw), 'sha256': digest(raw)} == metadata, 'boot build source drift')
    inventory = check_initramfs(ram, build['guest_init'])
    checked(invoke(['/usr/bin/codesign', '--verify', '--strict', launch]))
    entitlement = plistlib.loads(checked(invoke(['/usr/bin/codesign', '--display', '--entitlements', '-', '--xml', launch])))
    require(entitlement == {'com.apple.security.virtualization': True}, 'unexpected effective entitlement')
    display = invoke(['/usr/bin/codesign', '--display', '--verbose=4', launch])
    require(display.returncode == 0 and b'Signature=adhoc' in display.stderr and
            b'runtime' in display.stderr, 'launcher signature flags')

    report = {'format': 'radishaxiom-private-ax-b01-g0-boot-v1', 'arch': 'aarch64', 'kernel': '6.18.60-0-virt',
              'boot_id': '00000000-0000-4000-8000-000000000001', 'port': 'org.radishaxiom.ax-b01.g0',
              'device': 'vport0p0', 'device_id': '240:0', 'controllers': ['cpu', 'memory', 'pids'],
              'mounts': ['/proc:proc:ro', '/sys:sysfs:ro', '/dev:devtmpfs:ro', '/sys/fs/cgroup:cgroup2:ro']}

    def wire(value):
        return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')

    original = wire(report)
    bad_frames = {
        'missing-terminator': original[:-1], 'duplicate-frame': original * 2,
        'duplicate-key': b'{"arch":"aarch64",' + original[1:], 'oversize': b'x' * (64 * 1024 + 1),
        'wrong-port': wire({**report, 'port': 'another-port'}),
        'wrong-kernel': wire({**report, 'kernel': '6.18.64-0-virt'}),
        'zero-boot-id': wire({**report, 'boot_id': '00000000-0000-0000-0000-000000000000'}),
        'writable-proc': original.replace(b'/proc:proc:ro', b'/proc:proc:rw'),
        'missing-memory-controller': wire({**report, 'controllers': ['pids']}),
    }
    with tempfile.TemporaryDirectory(dir=bundle) as scratch:
        root = Path(scratch)
        candidate = root / 'report'
        for name, content in {'valid': original, **bad_frames}.items():
            candidate.write_bytes(content)
            result = invoke([launch, '--check-report', candidate])
            require(result.returncode == (0 if name == 'valid' else 2), f'report case: {name}')
        wrong_ram = root / 'changed-initramfs'
        content = bytearray(ram.read_bytes())
        content[-1] ^= 1
        wrong_ram.write_bytes(content)
        link = root / 'Image-symlink'
        link.symlink_to(image)
        for kernel, initrd, expected in ((image, wrong_ram, b'pinned input identity mismatch'),
                                         (link, ram, b'pinned input length or type mismatch')):
            result = invoke([launch, '--offline', kernel, initrd])
            require(result.returncode == 1 and expected in result.stderr, 'changed bytes or symlink guard')

    configuration = invoke([launch, '--offline', image, ram])
    require(configuration.returncode in (0, 1) and configuration.stdout, 'configuration readback unavailable')
    plan = json.loads(configuration.stdout)
    expected = {'start_count': 1, 'vcpu': 1, 'guest_mib': 512, 'work_seconds': 65, 'cleanup_seconds': 25,
                'overall_seconds': 90, 'report_bytes': 65536, 'receipt_bytes': 262144, 'data_disks': 0,
                'network_devices': 0, 'directory_shares': 0, 'socket_devices': 0, 'mac_to_guest': False,
                'appkit_or_console_tty': False, 'configuration_validated': configuration.returncode == 0,
                'port': report['port'], 'command_line': 'rdinit=/init panic=0 quiet',
                'effective_account': '_raxcg0', 'protected_root': '/private/var/db/radishaxiom/ax-b01-g0'}
    require(all(plan.get(key) == value for key, value in expected.items()), 'configuration values differ')
    require(plan.get('machine_id') and plan['kernel_sha256'] == build['boot_files'][image.name]['sha256'] and
            plan['initramfs_sha256'] == build['boot_files'][ram.name]['sha256'], 'configuration byte binding')
    path_check = invoke([launch, '--preflight-paths'])
    return {'scope': 'offline-no-vm', 'configuration': plan,
            'framework_validation': {'exit': configuration.returncode, 'stderr': configuration.stderr.decode().strip()},
            'entitlements': entitlement,
            'initramfs_members': inventory, 'report_rejections': list(bad_frames),
            'input_rejections': ['changed-initramfs', 'symlink-kernel'],
            'protected_paths': {'exit': path_check.returncode, 'stderr': path_check.stderr.decode().strip()},
            'runtime_qualification': False, 'vm_started': False}


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: review.py BUILT_G0_BUNDLE')
    print(json.dumps(review(Path(sys.argv[1]).resolve()), indent=2, sort_keys=True))
