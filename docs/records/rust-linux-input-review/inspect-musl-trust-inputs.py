#!/usr/bin/env python3
"""Read this fixed web page and Debian keyring package; never extract or verify signatures."""
import argparse
import base64
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
import lzma
from pathlib import Path
import re
import tarfile
from urllib.parse import urljoin

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SPEC = importlib.util.spec_from_file_location('chain', ROOT / 'scripts/inspect-debian-source-chain.py')
CHAIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHAIN)
PAGE_SHA = 'b271f4c351a3b54f6a6be9667bb834809d12ee514055b903ccb06839d274e3e0'
DEB_SHA = 'f699e2f88dca05212f2a452b58475f2993cb6993dfbafb1d0205a3291eb8b4b8'
KEY_SHA = '506b815cbb32d9b6066b4a2aa524071e071761e7e7f68c3ac74f3061ba852017'
ROLES = ['04B54C3CDCA79751B16BC6B5225629DF75B188BD',
         '41587F7DB8C774BCCF131416762F67A0B2C39DE4']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def fixed(path, length, digest):
    require(path.stat().st_size == length, 'fixed input size mismatch')
    data = path.read_bytes()
    require(identity(data) == {'bytes': length, 'sha256': digest}, 'fixed input digest mismatch')
    return data


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for name, value in attrs:
                if name == 'href' and value is not None:
                    self.targets.append(urljoin('https://ftp-master.debian.org/keys.html', value))


def ar_members(data):
    # Same fixed Debian layout as inspect-controls.py; stricter count and padding bounds.
    require(data[:8] == b'!<arch>\n', 'invalid ar envelope')
    offset, entries = 8, {}
    while offset < len(data):
        header = data[offset:offset + 60]
        require(len(entries) < 3 and len(header) == 60 and header[58:] == b'`\n', 'invalid ar header')
        require(re.fullmatch(rb' *[0-9]+ *', header[48:58]) is not None, 'invalid ar size')
        size = int(header[48:58])
        name = header[:16].decode('ascii').strip().removesuffix('/')
        end = offset + 60 + size
        require(name not in entries and end <= len(data), 'duplicate or truncated ar member')
        entries[name] = data[offset + 60:end]
        require(size % 2 == 0 or data[end:end + 1] == b'\n', 'invalid ar padding')
        offset = end + size % 2
    require(offset == len(data) and set(entries) == {'debian-binary', 'control.tar.xz', 'data.tar.xz'}
            and entries['debian-binary'] == b'2.0\n', 'unexpected Debian layout')
    return entries


def read_tar(data):
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=128 * 1024**2)
    raw = decoder.decompress(data, max_length=4 * 1024**2 + 1)
    require(len(raw) <= 4 * 1024**2 and decoder.eof and not decoder.unused_data,
            'oversized, truncated or concatenated XZ')
    inventory, contents, seen = [], {}, set()
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            name = member.name.removeprefix('./')
            require(len(seen) < 512 and len(name) <= 256 and name not in seen
                    and not member.pax_headers, 'unexpected or duplicate tar member')
            require(name == '.' and member.isdir() or name and not name.startswith('/')
                    and all(part not in {'', '.', '..'} for part in name.split('/')), 'invalid tar path')
            require(member.isdir() or member.isfile(), 'unsupported tar member type')
            require(0 <= member.size <= 1024**2, 'tar file size limit')
            seen.add(name)
            row = {'path': name, 'type': 'directory' if member.isdir() else 'file', 'mode': member.mode}
            if member.isfile():
                stream = archive.extractfile(member)
                content = stream.read(1024**2 + 1)
                require(len(content) == member.size, 'tar file length mismatch')
                contents[name] = content
                row.update(identity(content))
            inventory.append(row)
    return inventory, contents


def inspect(directory):
    page = fixed(directory / 'keys-attempt-2.html', 10718, PAGE_SHA).decode('utf-8')
    fingerprints = [value.replace(' ', '') for value in re.findall(r'<tt>([0-9A-F ]+)</tt>', page)]
    require(all(fingerprints.count(role) == 1 for role in ROLES), 'missing or duplicated page fingerprint')
    links = Links()
    links.feed(page)
    selected_links = [
        'https://ftp-master.debian.org/keys/archive-key-13.asc',
        'https://ftp-master.debian.org/keys/release-13.asc',
        'https://lists.debian.org/debian-devel-announce/2025/04/msg00001.html',
    ]
    require(all(links.targets.count(url) == 1 for url in selected_links), 'selected page link missing or duplicated')
    data = fixed(directory / 'keyring-attempt-2.deb', 178572, DEB_SHA)
    entries = ar_members(data)
    control_inventory, controls = read_tar(entries['control.tar.xz'])
    rows = list(CHAIN.stanzas(controls['control'].decode().splitlines(keepends=True)))
    require(len(rows) == 1, 'invalid control record')
    fields = rows[0]
    for key, value in {'package': 'debian-archive-keyring', 'version': '2023.3+deb12u2', 'architecture': 'all'}.items():
        require(fields.get(key) == value, 'control identity mismatch')
    inventory, contents = read_tar(entries['data.tar.xz'])
    key_path = 'usr/share/keyrings/debian-archive-keyring.gpg'
    keyring = contents[key_path]
    old = ROOT / 'docs/records/linux-builder-source-chain/release-verification.json'
    old_data = old.read_bytes()
    original = base64.b64decode(json.loads(old_data)['keyring']['base64'], validate=True)
    require(identity(original) == {'bytes': 55918, 'sha256': KEY_SHA}, 'historical keyring drift')
    require(keyring == original, 'package keyring differs from diagnostic keyring')
    copyright_path = 'usr/share/doc/debian-archive-keyring/copyright'
    require(copyright_path in contents, 'missing copyright metadata')
    return {
        'kind': 'diagnostic-musl-trust-input-review', 'acceptance': 'not-assessed',
        'methods': {str(path.relative_to(ROOT)): identity(path.read_bytes()) for path in
                    [Path(__file__), ROOT / 'scripts/inspect-debian-source-chain.py']},
        'page': {'bytes': 10718, 'sha256': PAGE_SHA, 'required_fingerprints_present': ROLES,
                 'linked_but_not_fetched': selected_links},
        'package': {'bytes': 178572, 'sha256': DEB_SHA, 'control': fields,
                    'ar': {name: identity(content) for name, content in entries.items()},
                    'control_inventory': control_inventory, 'data_inventory': inventory},
        'keyring': {'path': key_path, **identity(keyring), 'matches_historical_bytes': True,
                    'historical_record': identity(old_data)},
        'copyright': {'path': copyright_path, **identity(contents[copyright_path])},
        'signature_reverified': False, 'tools_provenance_accepted': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.directory), sort_keys=True, indent=2))
