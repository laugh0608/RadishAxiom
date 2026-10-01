#!/usr/bin/env python3
"""Read selected Docker version/resource fields through an existing Unix socket only."""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import socket
import stat

VERSION_FIELDS = {'Version': str, 'ApiVersion': str, 'MinAPIVersion': str,
                  'GitCommit': str, 'GoVersion': str, 'Os': str, 'Arch': str, 'KernelVersion': str}
INFO_FIELDS = {'ServerVersion': str, 'KernelVersion': str, 'OSType': str, 'Architecture': str,
               'CgroupDriver': str, 'CgroupVersion': str, 'Driver': str,
               'MemoryLimit': bool, 'SwapLimit': bool, 'PidsLimit': bool,
               'CpuCfsPeriod': bool, 'CpuCfsQuota': bool, 'CPUShares': bool, 'CPUSet': bool,
               'NCPU': int, 'MemTotal': int, 'SecurityOptions': list}


def identity(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def select_fields(value, fields):
    if not isinstance(value, dict):
        raise ValueError('response is not an object')
    selected, absent = {}, []
    for key, kind in fields.items():
        if key not in value or value[key] is None:
            absent.append(key)
            continue
        entry = value[key]
        if type(entry) is not kind:
            raise ValueError('wrong selected field type: ' + key)
        if isinstance(entry, str) and (len(entry) > 512 or any(ord(c) < 32 for c in entry)):
            raise ValueError('selected string outside profile: ' + key)
        if kind is list and (len(entry) > 32 or any(type(x) is not str or len(x) > 256 or
                                any(ord(c) < 32 for c in x) for x in entry)):
            raise ValueError('selected list outside profile: ' + key)
        selected[key] = entry
    return {'selected_fields': selected, 'absent_fields': absent}


def query(endpoint, path, fields):
    if path not in {'/version', '/v1.54/info'}:
        raise ValueError('request outside read-only allowlist')
    connection = http.client.HTTPConnection('localhost', timeout=5)
    transport = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    transport.settimeout(5)
    connection.sock = transport
    try:
        transport.connect(str(endpoint))
        connection.request('GET', path)
        response = connection.getresponse()
        raw = response.read(256 * 1024 + 1)
        if response.status != 200 or len(raw) > 256 * 1024:
            raise ValueError('HTTP status or response size outside profile')
        return {'method': 'GET', 'path': path, 'status': response.status,
                'response_identity_only': identity(raw), 'raw_response_retained': False,
                **select_fields(json.loads(raw), fields)}
    finally:
        connection.close()


def inspect(endpoint):
    if not stat.S_ISSOCK(endpoint.stat().st_mode):
        raise ValueError('endpoint is not an existing Unix socket')
    version = query(endpoint, '/version', VERSION_FIELDS)
    current = version['selected_fields']
    if current.get('ApiVersion') != '1.54' or current.get('Os') != 'linux' or current.get('Arch') != 'arm64':
        return {'requests': [version], 'resource_query_skipped': 'reviewed API/platform changed'}
    info = query(endpoint, '/v1.54/info', INFO_FIELDS)
    return {'requests': [version, info], 'resource_query_skipped': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new JSON file, never overwritten')
    args = parser.parse_args()
    with args.output.open('x') as output:
        result = {'kind': 'diagnostic-verifier-daemon-capabilities',
                  'started_at': datetime.now(timezone.utc).isoformat(), 'socket': str(args.socket),
                  'method': identity(Path(__file__).read_bytes()), 'runtime_limits_verified': False,
                  'containers_started': False, 'applications_started': False,
                  'tool_trust_accepted': False, 'raw_response_policy': 'hash only; whitelist fields retained'}
        code = 0
        try:
            result.update(inspect(args.socket))
        except (OSError, ValueError, http.client.HTTPException) as error:
            result['failure'] = {'type': type(error).__name__, 'errno': getattr(error, 'errno', None)}
            code = 1
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        output.write(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True, indent=2))
    raise SystemExit(code)
