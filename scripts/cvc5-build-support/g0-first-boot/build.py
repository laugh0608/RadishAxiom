#!/usr/bin/env python3
"""Build the fixed AX-B01 diskless diagnostic from retained local inputs."""

import gzip
import hashlib
import json
import os
from pathlib import Path
import plistlib
import stat
import struct
import subprocess
import sys
import tempfile
import zlib


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
GO = Path('/Users/luobo/.local/share/mise/installs/go/1.26.7')
XCODE = Path('/Applications/Xcode.app/Contents/Developer')
SDK = XCODE / 'Platforms/MacOSX.platform/Developer/SDKs/MacOSX27.2.sdk'
TOOLS = XCODE / 'Toolchains/XcodeDefault.xctoolchain/usr/bin'
ISO = 'alpine-virt-3.24.4-aarch64.iso'
ISO_SHA = 'cf88d8ba67389d20d9ed307366b52e487c15d7d3ee3233b62b95f709daa1d430'
RELEASE = '6.18.60-0-virt'
IMAGE_SHA = 'a2cecb9b6fdbd83e87bd43c8040de67300d5b8dde1fc50c34714faa272888f17'
MODULE = 'usr/lib/modules/' + RELEASE + '/kernel/drivers/virtio/virtio_mmio.ko'
MODULE_SHA = '97c9144f7c1c4e8d38a4cef9b83fec13214b4eb90bb49b438f546a1711279b26'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    with path.open('rb') as stream:
        return {'bytes': path.stat().st_size, 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}


def capture(arguments, *, data=None):
    return subprocess.run(arguments, input=data, check=True, stdout=subprocess.PIPE,
                          timeout=10, env={'PATH': '/usr/bin:/bin'}).stdout


def kernel_inputs(source):
    iso = source / ISO
    require(iso.is_file() and not iso.is_symlink() and identity(iso) == {
        'bytes': 93464576, 'sha256': ISO_SHA,
    }, 'virtual ISO identity')
    config = (source / ('config-' + RELEASE)).read_bytes()
    require(sha(config) == 'b7643cddcd3ba109183a2aaafa3c911d91e7d89485fd7b2caf5ede9396bf78ca', 'kernel config')
    require({b'CONFIG_INITRAMFS_SOURCE=""', b'CONFIG_VIRTIO_CONSOLE=y', b'CONFIG_VIRTIO_MMIO=m',
             b'CONFIG_VIRTIO_PCI=y', b'CONFIG_RD_GZIP=y'} <= set(config.splitlines()), 'kernel config values')
    zboot = capture(['/usr/bin/bsdtar', '-xOf', iso, 'boot/vmlinuz-virt'])
    require(sha(zboot) == 'cd05fed9e617b5df93dc62ece9b78c422fd94e9b432a2f7c092714b139d5eef4', 'zboot identity')
    start, size = struct.unpack_from('<II', zboot, 8)
    require(zboot[:8] == b'MZ\0\0zimg' and zboot[24:29] == b'gzip\0' and 64 <= start < start + size <= len(zboot),
            'zboot header')
    gunzip = zlib.decompressobj(wbits=31)
    kernel = gunzip.decompress(zboot[start:start + size], 64 * 1024 * 1024)
    require(gunzip.eof and not gunzip.unused_data and not gunzip.unconsumed_tail and sha(kernel) == IMAGE_SHA and
            kernel[56:60] == b'ARM\x64' and not kernel[24] & 1, 'AArch64 image identity')
    alpine_initramfs = capture(['/usr/bin/bsdtar', '-xOf', iso, 'boot/initramfs-virt'])
    require(sha(alpine_initramfs) == 'a0aca3b06df6b029711099e78cf01635f53331754d14af608f87bf9254630bac',
            'Alpine initramfs identity')
    module = capture(['/usr/bin/bsdtar', '-xOf', '-', MODULE], data=alpine_initramfs)
    require(sha(module) == MODULE_SHA and (b'\0vermagic=' + RELEASE.encode() + b' ') in module and
            b'\0depends=\0' in module, 'virtio transport module identity')
    return kernel, module


def initramfs_archive(init, module):
    entries = (
        ('dev', stat.S_IFDIR | 0o755, b'', 0, 0),
        ('dev/console', stat.S_IFCHR | 0o600, b'', 5, 1),
        ('dev/null', stat.S_IFCHR | 0o666, b'', 1, 3),
        ('init', stat.S_IFREG | 0o555, init, 0, 0),
        ('proc', stat.S_IFDIR | 0o555, b'', 0, 0),
        ('sys', stat.S_IFDIR | 0o555, b'', 0, 0),
        ('virtio_mmio.ko', stat.S_IFREG | 0o444, module, 0, 0),
        ('TRAILER!!!', 0, b'', 0, 0),
    )
    raw = bytearray()
    for inode, (name, mode, data, major, minor) in enumerate(entries, 1):
        key = name.encode('ascii') + b'\0'
        values = (inode, mode, 0, 0, 2 if stat.S_ISDIR(mode) else 1, 0, len(data), 0, 0,
                  major, minor, len(key), 0)
        raw.extend(b'070701' + ''.join(f'{value:08x}' for value in values).encode('ascii') + key)
        raw.extend(b'\0' * (-len(raw) % 4))
        raw.extend(data)
        raw.extend(b'\0' * (-len(raw) % 4))
    return gzip.compress(bytes(raw), mtime=0)


def build(source, output):
    require(plistlib.loads((XCODE.parent / 'version.plist').read_bytes())['ProductBuildVersion'] == '27B52',
            'Xcode build mismatch')
    kernel, module = kernel_inputs(source)
    output.mkdir(mode=0o700)
    image, ram = output / 'Image', output / 'initramfs.cpio.gz'
    image.write_bytes(kernel)
    with tempfile.TemporaryDirectory(dir=output) as scratch_name:
        scratch = Path(scratch_name)
        (scratch / 'tmp').mkdir()
        go_env = {
            'PATH': '/usr/bin:/bin', 'GOROOT': str(GO), 'GOTOOLCHAIN': 'local', 'GOENV': 'off',
            'GOWORK': 'off', 'GO111MODULE': 'off', 'GOPROXY': 'off', 'GOSUMDB': 'off',
            'GOOS': 'linux', 'GOARCH': 'arm64', 'GOARM64': 'v8.0', 'CGO_ENABLED': '0',
            'GOPATH': str(scratch / 'gopath'), 'GOCACHE': str(scratch / 'cache'),
            'GOTMPDIR': str(scratch / 'tmp'),
        }
        guest = scratch / 'init'
        subprocess.run([GO / 'bin/go', 'build', '-trimpath', '-buildvcs=false', '-ldflags=-buildid=',
                        '-o', guest, HERE / 'guest.go'], check=True, env=go_env, timeout=180)
        init = guest.read_bytes()
        ram.write_bytes(initramfs_archive(init, module))
    header = output / 'boot-pins.h'
    header.write_text(f'#define KERNEL_BYTES {len(kernel)}\n#define KERNEL_SHA256 "{sha(kernel)}"\n'
                      f'#define INITRAMFS_BYTES {ram.stat().st_size}\n#define INITRAMFS_SHA256 "{identity(ram)["sha256"]}"\n')
    launcher = output / 'g0-first-boot'
    subprocess.run([TOOLS / 'clang', '-B' + str(TOOLS), '-isysroot', SDK, '-target', 'arm64-apple-macos27.0',
                    '-fobjc-arc', '-O2', '-Wall', '-Wextra', '-Werror', '-I', output,
                    '-framework', 'Foundation', '-framework', 'Security', '-framework', 'Virtualization',
                    HERE / 'host.m', '-o', launcher], check=True, timeout=60, env={'PATH': '/usr/bin:/bin'})
    subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', '--timestamp=none', '--options', 'runtime',
                    '--identifier', 'org.radishaxiom.ax-b01.g0-first-boot', '--entitlements',
                    HERE / 'entitlements.plist', launcher], check=True, timeout=10)
    subprocess.run(['/usr/bin/codesign', '--verify', '--strict', launcher], check=True, timeout=10)
    for path in (image, ram):
        path.chmod(0o444)
    launcher.chmod(0o555)
    receipt = {
        'scope': 'offline-diskless-g0-build-no-vm', 'ready': False,
        'materials': {name: identity(HERE / name) for name in ('build.py', 'guest.go', 'host.m', 'entitlements.plist')},
        'boot_files': {path.name: identity(path) for path in (image, ram, launcher)},
        'guest_init': {'bytes': len(init), 'sha256': sha(init)},
        'source': {'alpine_virtual_iso_sha256': ISO_SHA, 'virtio_mmio_sha256': MODULE_SHA},
        'go': '1.26.7', 'sdk': '27.2', 'xcode_build': '27B52',
    }
    (output / 'build.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: build.py RETAINED_RELEASE_DIRECTORY NEW_REPO_TMP_OUTPUT_DIRECTORY')
    os.umask(0o077)
    destination = Path(sys.argv[2]).resolve()
    require(destination.parent == REPO / '.tmp', 'output must be a new direct child of the repository .tmp directory')
    build(Path(sys.argv[1]).resolve(), destination)
