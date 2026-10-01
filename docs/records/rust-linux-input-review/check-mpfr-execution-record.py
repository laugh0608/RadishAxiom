#!/usr/bin/env python3
"""Synthetic replay binding and encoding checks; no external processes."""
import base64
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('collector', HERE / 'collect-mpfr-verification-execution.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def row():
    return {'argv': [collector.run.smoke.DOCKER, '--host', 'unix://' + collector.run.smoke.SOCKET,
                     '--config', str(collector.CACHE / 'docker-config'), 'container', 'rm', 'synthetic'],
            'seconds_limit': 10, 'bytes_limit': 262144, 'returncode': 0, 'failure': None,
            'stdout': b'synthetic\n', 'stderr': b''}


class ReplayChecks(unittest.TestCase):
    def test_exact_call_consumes_one_record(self):
        engine = collector.Replay([row()])
        self.assertEqual(engine.call(['container', 'rm', 'synthetic']), row())
        self.assertEqual(engine.sequence, 1)

    def test_wrong_target_or_operation_does_not_consume(self):
        for args in [['container', 'rm', 'other'], ['container', 'start', 'synthetic']]:
            engine = collector.Replay([row()])
            with self.assertRaises(ValueError):
                engine.call(args)
            self.assertEqual(engine.sequence, 0)

    def test_different_socket_or_config_is_rejected(self):
        for index in (0, 2, 4):
            changed = row()
            changed['argv'][index] = '/synthetic/other'
            with self.assertRaises(ValueError):
                collector.Replay([changed]).call(['container', 'rm', 'synthetic'])

    def test_capture_limit_drift_is_rejected(self):
        for kwargs in [{'seconds': 30}, {'limit': 1048576}]:
            with self.assertRaises(ValueError):
                collector.Replay([row()]).call(['container', 'rm', 'synthetic'], **kwargs)

    def test_exhaustion_never_falls_back_to_execution(self):
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            collector.Replay([]).call(['container', 'rm', 'synthetic'])

    def test_failed_record_remains_failed(self):
        changed = {**row(), 'returncode': 1, 'failure': 'deadline'}
        result = collector.Replay([changed]).call(['container', 'rm', 'synthetic'])
        with self.assertRaises(ValueError):
            collector.run.smoke.checked(result)

    def test_binary_and_unicode_streams_round_trip(self):
        for raw in [b'', b'\xff\x00\x80', '合成记录\n'.encode()]:
            encoded = collector.encoded(raw)
            restored = (encoded['data'].encode() if encoded['encoding'] == 'utf-8'
                        else base64.b64decode(encoded['data'], validate=True))
            self.assertEqual(restored, raw)


if __name__ == '__main__':
    unittest.main()
