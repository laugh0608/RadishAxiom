#!/usr/bin/env python3
"""Independent finite review of exported E3 cBPF and bootstrap wire bytes.

No Rust library, kernel call, container, payload execution, or qualification.
All bytes are synthetic exports. This is not a general cBPF verifier.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

KILL, ALLOW, NOTIFY = 0x80000000, 0x7FFF0000, 0x7FC00000
ARCH = 0xC00000B7
if not __debug__:
    raise RuntimeError('offline verifier requires Python assertions enabled')


def read_file(path):
    assert path.is_file() and not path.is_symlink()
    assert path.stat().st_size <= 8 * 1024 * 1024
    return path.read_bytes()


def evaluate(program, nr, args=(), arch=ARCH):
    """Small independent interpreter for the emitted acyclic cBPF subset."""
    assert len(program) % 8 == 0 and 0 < len(program) <= 4096 * 8
    data = struct.pack('<IIQ6Q', nr & 0xFFFFFFFF, arch, 0,
                       *(list(args) + [0] * (6 - len(args))))
    instructions = list(struct.iter_unpack('<HBBI', program))
    pc, accumulator = 0, 0
    for _ in range(len(instructions) + 1):
        assert 0 <= pc < len(instructions), 'jump outside program'
        op, jt, jf, operand = instructions[pc]
        pc += 1
        if op == 0x20:  # BPF_LD|BPF_W|BPF_ABS
            assert jt == jf == 0 and operand % 4 == 0 and operand <= 60
            accumulator = struct.unpack_from('<I', data, operand)[0]
        elif op == 0x15:  # BPF_JMP|BPF_JEQ|BPF_K
            pc += jt if accumulator == operand else jf
        elif op == 0x45:  # BPF_JMP|BPF_JSET|BPF_K
            pc += jt if accumulator & operand else jf
        elif op == 0x05:  # BPF_JMP|BPF_JA
            assert jt == jf == 0
            pc += operand
        elif op == 0x06:  # BPF_RET|BPF_K
            assert jt == jf == 0 and operand in (KILL, ALLOW, NOTIFY)
            return operand
        else:
            raise AssertionError(f'unknown instruction {op:x}')
    raise AssertionError('program did not return')


def check_worker(program):
    cases = 0

    def check(nr, args, wanted, arch=ARCH):
        nonlocal cases
        actual = evaluate(program, nr, args, arch)
        assert actual == wanted, (nr, args, hex(arch), hex(actual), hex(wanted))
        cases += 1

    allowed_numbers = {25, 29, 57, 63, 64, 65, 66, 80, 93, 94, 96, 98,
                       99, 113, 114, 124, 132, 134, 135, 139, 165, 172,
                       178, 211, 214, 215, 216, 222, 226, 233, 261, 281, 293}
    for nr in range(512):
        if nr not in allowed_numbers:
            check(nr, (), KILL)
            check(nr, [2**64-1] * 6, KILL)
        for arch in (0, 0x40000028, 0xC000003E, 0x800000B7):
            check(nr, (), KILL, arch)
    for nr in (63, 65):
        check(nr, (0,), ALLOW)
        for fd in (1, 2, 3, 2**32, 2**64-1):
            check(nr, (fd,), KILL)
    for nr in (64, 66):
        for fd in (1, 2):
            check(nr, (fd,), ALLOW)
            check(nr, (fd + 2**32,), KILL)
        for fd in (0, 3, 4, 2**64-1):
            check(nr, (fd,), KILL)
    for fd in range(8):
        check(57, (fd,), ALLOW if fd <= 5 else KILL)
        check(57, (fd + 2**32,), KILL)
        check(80, (fd,), ALLOW if fd <= 2 else KILL)
        check(25, (fd, 3), ALLOW if fd <= 2 else KILL)
        check(29, (fd, 0x5401), ALLOW if fd <= 2 else KILL)
    for nr, base, idx in ((25, [0, 3], 1), (29, [0, 0x5401], 1),
                          (281, [3, 0x1000, 0x2000, 0x3000, 0x1000], 4),
                          (211, [4, 0x1000, 0x4000], 2)):
        wanted = NOTIFY if nr == 281 else ALLOW
        check(nr, base, wanted)
        high = base.copy(); high[idx] += 2**32
        check(nr, high, KILL)
    # Nonempty pathname pointer cannot be inspected by cBPF: still NOTIFY,
    # never ALLOW. Trusted-first-exec state must reject all later requests.
    check(281, (3, 0xDEADBEEF, 0x2000, 0x3000, 0x1000), NOTIFY)
    for nr in (221, 56, 220, 435, 277, 167, 198, 199, 212, 280, 425):
        check(nr, (), KILL)
    for prot in (0, 1, 2, 3):
        check(222, (0, 4096, prot, 0x22, 2**64-1, 0), ALLOW)
        check(226, (0x1000, 4096, prot), ALLOW)
    for prot in (4, 5, 7, 2**32+1):
        check(222, (0, 4096, prot, 0x22, 2**64-1, 0), KILL)
        check(226, (0x1000, 4096, prot), KILL)
    for flags in (0, 2, 0x20, 0x23, 0x32, 0x22+2**32):
        check(222, (0, 4096, 3, flags, 2**64-1, 0), KILL)
    for fd in (0, 3, 0xFFFFFFFF):
        check(222, (0, 4096, 3, 0x22, fd, 0), KILL)
    for nr in (113, 114):
        for clock in range(12):
            check(nr, (clock,), ALLOW if clock in (1, 2, 3, 7) else KILL)
    for op in (128, 129, 137, 138):
        check(98, (0x1000, op), ALLOW)
        check(98, (0x1000, op+2**32), KILL)
    for op in (0, 1, 6, 9, 10, 256+128, 134):
        check(98, (0x1000, op), KILL)
    for who in (0, 1):
        check(165, (who,), ALLOW)
    for who in (2, 2**32, 2**32+1, 0xFFFFFFFF, 2**64-1):
        check(165, (who,), KILL)
    for resource in (2, 3, 9):
        check(261, (0, resource, 0, 0x1000), ALLOW)
        check(261, (0, resource, 0x1000, 0), KILL)
        check(261, (1, resource, 0, 0x1000), KILL)
    for nr in (0x40000000+63, 0xFFFFFFFF):
        check(nr, (), KILL)
    return cases


def check_supervisor(program):
    """Hand-specified cases for the fixed exported S FD map, no Rust oracle."""
    cases = 0

    def check(nr, args, wanted, arch=ARCH):
        nonlocal cases
        assert evaluate(program, nr, args, arch) == wanted, (nr, args, wanted)
        cases += 1

    allowed = {29, 57, 63, 64, 62, 73, 93, 94, 95, 113, 114,
               214, 215, 216, 222, 226, 233, 424}
    for nr in range(512):
        if nr not in allowed:
            check(nr, (), KILL)
        check(nr, (), KILL, 0xC000003E)
    read_fds = {0, 11, 12, 13, *range(20, 32)}
    write_fds = {1, 2, 10}
    owned = {0, 1, 2, *range(10, 16), *range(20, 32)}
    for fd in range(42):
        for nr, fds in ((63, read_fds), (64, write_fds), (57, owned),
                        (62, set(range(20, 32)))):
            check(nr, (fd,), ALLOW if fd in fds else KILL)
            check(nr, (fd + 2**32,), KILL)
    good = [(73, [0x1000, 21, 0x2000, 0, 8], (1, 3, 4)),
            (424, [14, 9, 0, 0], (0, 1, 2, 3)),
            (95, [3, 14, 0x1000, 5, 0], (0, 1, 3, 4)),
            (62, [20, 0, 0], (0, 1, 2)),
            (222, [0, 4096, 3, 0x22, 2**64-1, 0], (2, 3, 4, 5)),
            (226, [0x1000, 4096, 3], (2,)),
            (216, [0x1000, 4096, 8192, 1], (3,)),
            (233, [0x1000, 4096, 4], (2,))]
    for nr, args, indices in good:
        check(nr, args, ALLOW)
        for index in indices:
            bad = args.copy(); bad[index] ^= 2**32
            check(nr, bad, KILL)
    for count in range(24):
        check(73, (0x1000, count, 0x2000, 0, 8), ALLOW if 1 <= count <= 21 else KILL)
    for nr in (113, 114):
        for clock in range(12):
            check(nr, (clock,), ALLOW if clock == 7 else KILL)
    for cmd in (0xC0502100, 0xC0182101, 0x40082102):
        check(29, (15, cmd, 0x1000), ALLOW)
        check(29, (14, cmd, 0x1000), KILL)
        check(29, (15, cmd + 2**32, 0x1000), KILL)
    for cmd in (0x40182103, 0x5401, 0):
        check(29, (15, cmd, 0x1000), KILL)
    for nr in (93, 94, 214, 215):
        check(nr, (), ALLOW)
    for prot in range(8):
        check(226, (0x1000, 4096, prot), ALLOW if prot <= 3 else KILL)
    for args in ((13, 9, 0, 0), (14, 15, 0, 0), (14, 9, 1, 0), (14, 9, 0, 1)):
        check(424, args, KILL)
    for args in ((1, 14, 0x1000, 5, 0), (3, 14, 0x1000, 4, 0), (3, 14, 0x1000, 5, 1)):
        check(95, args, KILL)
    return cases


def read_frames(raw, direction, binding):
    position = control = sequence = 0
    frames = []
    totals = {3: 0, 5: 0, 7: 0}
    closed, singleton = set(), set()
    terminal = False
    while position < len(raw):
        assert not terminal and position + 24 <= len(raw)
        magic, major, minor, observed_direction, kind, reserved, seq, length = struct.unpack_from('>4sBBBB4sQI', raw, position)
        assert magic == b'RAXB' and (major, minor) == (0, 1)
        assert observed_direction == direction and reserved == bytes(4)
        assert seq == sequence and 160 <= length <= 65536
        assert (kind in (2, 3, 4)) if direction == 1 else (kind in (1, 5, 6, 7, 8, 9, 10, 11))
        position += 24
        assert position + length <= len(raw)
        payload = raw[position:position+length]; position += length
        assert payload[:160] == binding
        body = payload[160:]
        sequence += 1
        control += 184 + (0 if kind in totals else len(body))
        assert control <= 32768
        if kind in totals:
            assert body and kind not in closed
            totals[kind] += len(body)
            assert totals[kind] <= {3: 1048576, 5: 4194304, 7: 65536}[kind]
        else:
            assert kind not in singleton; singleton.add(kind)
            assert len(body) == {1:112, 2:44, 4:0, 6:0, 8:0, 9:2, 10:2, 11:1}[kind]
        if kind in (4, 6, 8):
            closed.add({4:3, 6:5, 8:7}[kind])
        if kind == 10:
            assert body == bytes([1, 1])
            terminal = True
        if kind == 11:
            assert 1 <= body[0] <= 9
            terminal = True
        frames.append((kind, body))
    return frames, control


def check_exports(root):
    program = read_file(root/'worker.cbpf.bin')
    cases = check_worker(program)
    supervisor_program = read_file(root/'supervisor.cbpf.bin')
    supervisor_cases = check_supervisor(supervisor_program)
    binding = read_file(root/'binding.bin')
    assert len(binding) == 160
    outbound, c1 = read_frames(read_file(root/'mac.wire'), 1, binding)
    inbound, c2 = read_frames(read_file(root/'supervisor.wire'), 2, binding)
    assert c1+c2 <= 65536
    assert [k for k, _ in outbound if k != 3] == [2, 4]
    assert [k for k, _ in inbound if k not in (5,7)] == [1, 6, 8, 9, 10]
    query = b''.join(b for k,b in outbound if k == 3)
    stdout = b''.join(b for k,b in inbound if k == 5)
    stderr = b''.join(b for k,b in inbound if k == 7)
    assert query == read_file(root/'query.smt2')
    assert stdout == read_file(root/'stdout.bin')
    assert stderr == read_file(root/'stderr.bin')
    arm = outbound[0][1]
    assert struct.unpack_from('>I', arm, 8)[0] == len(query)
    assert arm[12:] == hashlib.sha256(query).digest()
    assert len(query) == 962642
    assert hashlib.sha256(query).hexdigest() == '5ba58e0d9754c3448f299ce4d9be2060c2d91d829253ec3e4a170e0d4d07a85a'
    world_bytes = read_file(root/'world.json')
    world = json.loads(world_bytes)
    assert len(world) == 1 and world[0]['interface'] == 'orders' and len(world[0]['rows']) == 3
    values = [{f['name']: f['value'] for f in row['fields']} for row in world[0]['rows']]
    assert len({v['order_id']['value'] for v in values}) == 3
    assert all(0 <= int(v['discount_cents']['value']) <= int(v['subtotal_cents']['value']) for v in values)
    settled = [v for v in values if v['state']['member'] == 'settled']
    assert len(settled) == 2
    assert any(int(v['subtotal_cents']['value']) + int(v['discount_cents']['value']) != int(v['subtotal_cents']['value']) - int(v['discount_cents']['value']) for v in settled)
    replay = json.loads(read_file(root/'replay.json'))
    assert replay['result']['kind'] == 'target-violated'
    assert replay['binding']['obligation'] == 'sha256:4916b2ef17b43cab21bff8ae87433922c60fbf86fb72fc52972e06964584476e'
    assert replay['world_raw_digest'] == 'sha256:' + hashlib.sha256(world_bytes).hexdigest()
    for kind in ('request', 'response', 'candidate'):
        assert replay['source'][kind] == 'sha256:' + hashlib.sha256(read_file(root/(kind+'.json'))).hexdigest()
    assert binding[32:64] == hashlib.sha256(read_file(root/'request.json')).digest()
    assert binding[64:96] == hashlib.sha256(program).digest()
    return {'scope':'offline-simulation-only', 'policy_cases':cases,
            'supervisor_policy_cases':supervisor_cases,
            'supervisor_instructions':len(supervisor_program)//8,
            'supervisor_sha256':hashlib.sha256(supervisor_program).hexdigest(),
            'worker_instructions':len(program)//8,
            'worker_sha256':hashlib.sha256(program).hexdigest(),
            'mac_frames':len(outbound), 'supervisor_frames':len(inbound),
            'control_bytes':c1+c2, 'query_bytes':len(query),
            'query_sha256':hashlib.sha256(query).hexdigest(),
            'stdout_sha256':hashlib.sha256(stdout).hexdigest(),
            'stderr_sha256':hashlib.sha256(stderr).hexdigest(),
            'real_execution':'blocked-E0-and-runtime-qualification'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(check_exports(args.directory), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
