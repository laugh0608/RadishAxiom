#!/usr/bin/env python3
"""Synthetic notice, patch observation and fixed metadata request boundaries; no network."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load('inspect-linux-headers-review.py')
route = load('fetch-linux-headers-git-metadata.py')


class NoticeTests(unittest.TestCase):
    def test_marker_beyond_old_prefix_and_literal_preservation(self):
        raw = b'x' * 5000 + b'\n/* SPDX-License-Identifier: MIT */\n'
        result = m.notices(raw)
        self.assertEqual(result['spdx_lines'], [{'line': 2, 'text': '/* SPDX-License-Identifier: MIT */'}])
        self.assertEqual(m.scope_summary([result])['literal_declaration_counts'], {'MIT': 1})

    def test_multiple_markers_do_not_multiply_file_count(self):
        result = m.notices(b'// SPDX-License-Identifier: MIT\n// SPDX-License-Identifier: GPL-2.0\n')
        summary = m.scope_summary([result])
        self.assertEqual(summary['with_spdx_marker'], 1)
        self.assertEqual(len(summary['literal_declaration_counts']), 2)

    def test_no_marker_is_only_absence_observation(self):
        result = m.notices(b'Copyright synthetic\nPermission is hereby granted\n')
        self.assertEqual(result, {'spdx_lines': [], 'copyright_line_numbers': [1]})
        self.assertEqual(m.scope_summary([result])['without_spdx_marker'], 1)

    def test_non_utf8_and_crlf_preserve_visible_bytes(self):
        result = m.notices(b'CoPyRiGhT\r\n// SPDX-License-Identifier: MIT\xff\r\n')
        self.assertEqual(result['copyright_line_numbers'], [1])
        self.assertEqual(result['spdx_lines'][0]['text'], '// SPDX-License-Identifier: MIT\\xff\r')

    def test_member_bound(self):
        with patch.object(m.previous.content.inputs, 'MAX_MEMBER', 2), self.assertRaises(ValueError):
            m.notices(b'abc')


class PatchTests(unittest.TestCase):
    def files(self, after=b'f2ba8f8'):
        return {'file.h': b'abc', 'patches/one.patch':
                b'index 0000000..' + after + b' 100644\n+++ b/file.h\n'}

    def test_blob_prefix_observation_does_not_apply_or_authenticate(self):
        row = m.patch_observations(self.files())[0]
        self.assertTrue(row['after_prefix_matches_target'])
        self.assertFalse(row['patch_applied'])
        self.assertFalse(row['patch_authenticated'])

    def test_nonmatching_prefix_is_reported(self):
        self.assertFalse(m.patch_observations(self.files(b'1111111'))[0]['after_prefix_matches_target'])

    def test_missing_and_multiple_targets_rejected(self):
        files = self.files()
        del files['file.h']
        with self.assertRaisesRegex(ValueError, 'absent'):
            m.patch_observations(files)
        files = self.files()
        files['patches/one.patch'] += b'+++ b/second.h\n'
        with self.assertRaisesRegex(ValueError, 'profile'):
            m.patch_observations(files)


class RequestTests(unittest.TestCase):
    def test_two_fixed_bounded_targets(self):
        plan = route.plan()
        self.assertEqual(set(plan['targets']), {'tag-ref', 'commit'})
        self.assertEqual(sum(row['limit'] for row in plan['targets'].values()), 327680)
        self.assertTrue(plan['targets']['commit']['url'].endswith(route.candidate.COMMIT))
        self.assertFalse(plan['executed'])
        self.assertFalse(plan['automatic_retry'])

    def test_plan_drift_stops_before_network(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(route, 'DIRECTORY', Path(directory).resolve()):
            (route.DIRECTORY / 'fetch-plan.json').write_text('{}')
            with patch.object(route.fetch, 'fetch') as fetch, self.assertRaises(ValueError):
                route.execute()
            fetch.assert_not_called()

    def test_independent_failure_is_retained_without_retry(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(route, 'DIRECTORY', Path(directory).resolve()):
            (route.DIRECTORY / 'fetch-plan.json').write_text(json.dumps(route.plan()))
            with patch.object(route.fetch, 'fetch', side_effect=[1, 0]) as fetch:
                self.assertEqual(route.execute(), 1)
            self.assertEqual([call.args for call in fetch.call_args_list], [('tag-ref', 1), ('commit', 1)])


if __name__ == '__main__':
    unittest.main()
