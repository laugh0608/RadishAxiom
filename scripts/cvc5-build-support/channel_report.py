"""Independent bounded private report parser. No OS/runtime acceptance or execution."""
import hashlib
from pathlib import Path
import re
import runpy
import struct

INPUTS = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'check-linux-channel-inputs.py'))
require, parse, canonical = INPUTS['require'], INPUTS['parse'], INPUTS['canonical']
BUDGETS, PROFILE = INPUTS['BUDGETS'], INPUTS['PROFILE']


def shape(d, keys):
    require(type(d) is dict and tuple(d) == tuple(keys), 'report-shape')


def uint(n, maximum=2**64-1):
    require(type(n) is int and 0 <= n <= maximum, 'report-uint')
    return n


def boolean(b):
    require(type(b) is bool, 'report-bool')
    return b


def binding(d):
    shape(d, ('run_id', 'input_binding', 'collector_digest'))
    require(type(d['run_id']) is str and re.fullmatch('[0-9a-f]{64}', d['run_id']), 'run-id')
    for k in ('input_binding', 'collector_digest'):
        require(type(d[k]) is str and re.fullmatch('sha256:[0-9a-f]{64}', d[k]), 'binding-digest')


def fault(d):
    shape(d, ('operation', 'kind', 'detail'))
    require(type(d['operation']) is str and re.fullmatch('[a-z0-9-]{1,64}', d['operation']), 'operation')
    require(d['kind'] in ('errno', 'invalid-input', 'invalid-return', 'layout', 'ownership'), 'error-kind')
    uint(d['detail'], 4095)
    require(d['detail'] > 0 if d['kind'] == 'errno' else d['detail'] == 0, 'error-detail')


def reason(d):
    if d is None:
        return
    shape(d, ('kind', 'signal', 'error'))
    k = d['kind']
    require(k in ('kernel', 'deadline', 'cancelled', 'signal', 'orphan', 'budget', 'capture', 'transport'), 'reason-kind')
    if k == 'kernel':
        fault(d['error'])
    else:
        require(d['error'] is None, 'reason-error')
    if k in ('cancelled', 'signal'):
        uint(d['signal'], 64)
        require(d['signal'] in (1, 2, 3, 15) if k == 'cancelled' else
                d['signal'] > 0 and d['signal'] not in (9, 17, 19), 'reason-signal')
    else:
        require(d['signal'] is None, 'reason-signal')


def child_exit(e):
    shape(e, ('pid', 'uid', 'code', 'status'))
    require(1 < uint(e['pid'], 2**31-1), 'child-pid')
    uint(e['uid'], 2**32-1)
    require(uint(e['code'], 3) > 0, 'child-code')
    uint(e['status'], 255)
    require(e['code'] == 1 or 1 <= e['status'] <= 64, 'child-signal')


def selected(f):
    c = f['cause']
    if c is not None:
        return 124 if c['kind'] == 'deadline' else 128+c['signal'] if c['kind'] == 'cancelled' else 125
    if (not f['no_children'] or f['errors'] or f['observations_overflowed'] or f['capture_failed'] or
            f['transport_failed'] or any(f[s]['prefix_only'] or not f[s]['eof'] for s in ('stdout', 'stderr'))):
        return 125
    e = f['main_exit']
    return 125 if e is None else e['status'] if e['code'] == 1 else 128+e['status']


def check_final(f, expected, counts, hashes):
    shape(f, ('binding', 'cause', 'child_pid', 'main_exit', 'exits', 'signals', 'errors', 'clone_attempted',
              'no_children', 'observations_overflowed', 'stdout', 'stderr', 'clock', 'capture_failed',
              'transport_failed', 'selected_exit_code'))
    binding(f['binding'])
    require(f['binding'] == expected, 'final-binding')
    reason(f['cause'])
    for k in ('clone_attempted', 'no_children', 'observations_overflowed', 'capture_failed', 'transport_failed'):
        boolean(f[k])
    for k in ('exits', 'signals', 'errors'):
        require(type(f[k]) is list and len(f[k]) <= 64, 'event-budget')
    for e in f['exits']:
        child_exit(e)
    for e in f['errors']:
        fault(e)
    for e in f['signals']:
        shape(e, ('pid', 'error'))
        require(1 < uint(e['pid'], 2**31-1), 'signal-pid')
        if e['error'] is not None:
            fault(e['error'])
    pid = f['child_pid']
    if pid is None:
        require(f['main_exit'] is None and not f['exits'] and not f['signals'], 'missing-child')
    else:
        require(1 < uint(pid, 2**31-1) and f['clone_attempted'], 'child-creation')
    e = f['main_exit']
    if e is not None:
        child_exit(e)
        require(e['pid'] == pid and next((x for x in f['exits'] if x['pid'] == pid), None) == e, 'main-exit-binding')
    require(not (f['no_children'] and pid is not None) or e is not None, 'missing-main-reap')
    if f['cause'] is None:
        require(len(f['exits']) <= 1 and all(e['pid'] == pid for e in f['exits']) and not f['signals'], 'hidden-orphan-or-signal')
    for i, k in enumerate(('stdout', 'stderr')):
        st = f[k]
        shape(st, ('seen_bytes', 'exported_bytes', 'sha256', 'prefix_only', 'eof'))
        boolean(st['prefix_only']); boolean(st['eof'])
        require(uint(st['exported_bytes'], 2**32-1) == counts[i] and uint(st['seen_bytes']) >= counts[i], 'stream-count')
        require(st['sha256'] == 'sha256:'+hashes[i].hexdigest(), 'stream-digest')
        require(st['prefix_only'] or st['seen_bytes'] == counts[i], 'hidden-prefix')
    c = f['clock']
    shape(c, ('first_ns', 'work_ns', 'cleanup_ns', 'final_ns', 'last_ns'))
    for n in c.values():
        uint(n)
    t = c['first_ns']
    require(c['work_ns'] == t+18000000000 and c['cleanup_ns'] == t+19800000000 and
            c['final_ns'] == t+20000000000 and t <= c['last_ns'] < c['final_ns'], 'clock-budget')
    require(uint(f['selected_exit_code'], 255) == selected(f), 'selected-exit')


class Decoder:
    def __init__(self, expected):
        binding(expected)
        self.expected = dict(expected)
        self.buffer = bytearray()
        self.need = 20
        self.seq = self.wire = self.received = 0
        self.started = self.failed = False
        self.final = None
        self.counts = [0, 0]
        self.hashes = [hashlib.sha256(), hashlib.sha256()]

    def feed(self, raw):
        require(not self.failed, 'terminal')
        chunks = []
        try:
            for b in raw:
                require(self.final is None, 'after-final')
                self.received += 1
                require(self.received <= 2097152, 'wire-budget')
                self.buffer.append(b)
                if len(self.buffer) == 20:
                    magic, seq, kind, stream, reserved, size = struct.unpack('>8sIBBHI', self.buffer)
                    require(magic == b'AXCHN001' and reserved == 0 and seq == self.seq and seq < 8192, 'header')
                    cap = {(1, 0): 4096, (2, 1): 4096, (2, 2): 4096, (3, 0): 32768}.get((kind, stream), 0)
                    require(0 < size <= cap, 'payload-budget')
                    self.need = 20+size
                if len(self.buffer) == self.need:
                    _, seq, kind, stream, _, _ = struct.unpack('>8sIBBHI', self.buffer[:20])
                    payload = bytes(self.buffer[20:])
                    if kind == 1:
                        require(not self.started, 'duplicate-start')
                        expected = dict(format='radishaxiom-private-linux-channel-report', version='0.1',
                                        binding=self.expected, profile=PROFILE, budgets=BUDGETS)
                        require(payload == canonical(expected), 'start-binding')
                        self.started = True
                    elif kind == 2:
                        require(self.started and seq < 8191 and self.wire+len(self.buffer)+20+32768 <= 2097152, 'chunk-order-or-reserve')
                        i = stream-1
                        self.counts[i] += len(payload)
                        require(self.counts[i] <= (1572864 if i == 0 else 65536), 'stream-budget')
                        self.hashes[i].update(payload)
                        chunks.append((stream, payload))
                    else:
                        require(self.started, 'final-before-start')
                        f = parse(payload)
                        check_final(f, self.expected, self.counts, self.hashes)
                        self.final = f
                    self.seq += 1
                    self.wire += len(self.buffer)
                    self.buffer.clear()
                    self.need = 20
        except (ValueError, TypeError, KeyError, OverflowError, struct.error):
            self.failed = True
            raise ValueError('invalid-channel-report') from None
        return chunks

    def finish(self):
        if self.failed or self.buffer or self.final is None:
            self.failed = True
            raise ValueError('missing-final')
        return dict(scope='diagnostic-observation-only', final=self.final,
                    collection_succeeded=self.final['selected_exit_code'] == 0,
                    runtime_exit_confirmed=False, qualification='not-established')
