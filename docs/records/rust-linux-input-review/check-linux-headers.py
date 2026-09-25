#!/usr/bin/env python3
"""Synthetic headers/link, comparison and request-scope boundaries; no network or extraction."""
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('m', HERE / 'inspect-linux-headers-inputs.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
c = m.content
TOP = 'synthetic'


def archive(entries, tail=b''):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as t:
        for path, kind, value in [('', 'd', b''), *entries]:
            row = tarfile.TarInfo(TOP + ('/' + path if path else ''))
            row.type = {'d': tarfile.DIRTYPE, 'f': tarfile.REGTYPE, 's': tarfile.SYMTYPE,
                        'h': tarfile.LNKTYPE, 'p': tarfile.FIFOTYPE}[kind]
            if kind in ('s', 'h'):
                row.linkname = value
                value = b''
            row.size = len(value)
            t.addfile(row, io.BytesIO(value))
    return output.getvalue() + tail


class LinkTests(unittest.TestCase):
    def inspect(self, rows):
        return c.inventory(archive(rows), TOP)[0]

    def test_relative_directory_and_alias_links(self):
        report = self.inspect([('generic', 'd', b''), ('generic/a.h', 'f', b'a'),
                               ('arm64', 'd', b''), ('arm64/include', 's', '../generic'),
                               ('aarch64', 's', 'arm64')])
        self.assertEqual(report['type_counts'], {'directory': 3, 'file': 1, 'symlink': 2})
        projected = c.include_projection(report, 'aarch64')
        self.assertEqual(projected['headers'][0]['source_path'], 'generic/a.h')
        self.assertFalse(projected['actual_installation_verified'])

    def test_link_component_is_resolved_before_parent(self):
        rows = [('a', 'd', b''), ('b', 'd', b''), ('b/deep', 'd', b''), ('b/x.h', 'f', b'x'),
                ('a/jump', 's', '../b/deep'), ('a/final', 's', 'jump/../x.h')]
        report = self.inspect(rows)
        final = next(r for r in report['members'] if r['path'] == TOP + '/a/final')
        self.assertEqual(final['resolved_target'], TOP + '/b/x.h')

    def test_absolute_control_backslash_and_empty_targets(self):
        for value in ('/outside', 'a\\b', '', 'a//b', 'bad\nname', 'a' * 4097):
            with self.subTest(value=value[:20]), self.assertRaises(ValueError):
                self.inspect([('bad', 's', value)])

    def test_root_escape_and_dangling(self):
        for target in ('..', '../outside', 'absent'):
            with self.assertRaises(ValueError):
                self.inspect([('bad', 's', target)])

    def test_self_and_mutual_cycles(self):
        for rows in ([('a', 's', 'a')], [('a', 's', 'b'), ('b', 's', 'a')]):
            with self.assertRaisesRegex(ValueError, 'cycle'):
                self.inspect(rows)

    def test_link_hop_bound(self):
        rows = [('a', 's', 'b'), ('b', 's', 'c'), ('c', 'f', b'x')]
        with patch.object(c, 'LINK_HOPS', 1), self.assertRaisesRegex(ValueError, 'hop bound'):
            self.inspect(rows)

    def test_file_traversal_rejected(self):
        with self.assertRaisesRegex(ValueError, 'file traversed'):
            self.inspect([('file', 'f', b'x'), ('link', 's', 'file/../file')])

    def test_linked_or_missing_physical_ancestor(self):
        for rows in ([('file/sub', 'f', b'x')],
                     [('dir', 'd', b''), ('link', 's', 'dir'), ('link/sub', 'f', b'x')]):
            with self.assertRaisesRegex(ValueError, 'ancestor'):
                self.inspect(rows)

    def test_projection_cycle_is_separate_from_link_resolution(self):
        report = self.inspect([('arm64', 'd', b''), ('arm64/include', 'd', b''),
                               ('arm64/include/back', 's', '.')])
        with self.assertRaisesRegex(ValueError, 'projection cycle'):
            c.include_projection(report)

    def test_projection_glob_depth_and_hidden_names(self):
        rows = [('arm64', 'd', b''), ('arm64/include', 'd', b''), ('arm64/include/.hidden.h', 'f', b'x')]
        current = 'arm64/include'
        for i in range(6):
            rows.append((current + '/a.h', 'f', b'x'))
            current += '/sub'
            rows.append((current, 'd', b''))
        report = self.inspect(rows)
        self.assertEqual(len(c.include_projection(report)['headers']), 5)


class ArchiveTests(unittest.TestCase):
    def test_paths_duplicate_and_nonfile_payload(self):
        for rows in ([('../bad', 'f', b'x')], [('a', 'f', b'x'), ('a', 'f', b'x')], [('d', 'd', b'x')]):
            with self.assertRaises(ValueError):
                c.inventory(archive(rows), TOP)

    def test_hardlink_and_special_rejected(self):
        for kind, value in (('h', TOP), ('p', b'')):
            with self.assertRaisesRegex(ValueError, 'special member'):
                c.inventory(archive([('bad', kind, value)]), TOP)

    def test_member_and_tar_limits(self):
        raw = archive([('file', 'f', b'abc')])
        for name, bound in (('MAX_TAR', 512), ('MAX_MEMBER', 2), ('MAX_MEMBERS', 1)):
            with patch.object(c.inputs, name, bound), self.assertRaises(ValueError):
                c.inventory(raw, TOP)

    def test_nonzero_tail(self):
        with self.assertRaisesRegex(ValueError, 'nonzero tar tail'):
            c.inventory(archive([], b'X'), TOP)

    def test_comparison_separates_content_modes_and_metadata(self):
        left, _ = c.inventory(archive([('file', 'f', b'a')]), TOP)
        right = json.loads(json.dumps(left))
        right['members'][1]['mode'] += 1
        right['members'][1]['uid'] += 1
        result = c.compare(left, right)
        self.assertEqual(result['content_link_or_type_differences'], [])
        self.assertEqual(result['mode_differences'], ['file'])
        self.assertEqual(result['owner_or_mtime_differences'], ['file'])
        self.assertFalse(result['normalized_all_members_equal'])
        right['members'][1]['sha256'] = '0' * 64
        self.assertEqual(c.compare(left, right)['content_link_or_type_differences'], ['file'])

    def test_missing_file_not_equivalent(self):
        left, _ = c.inventory(archive([]), TOP)
        right, _ = c.inventory(archive([('extra', 'f', b'x')]), TOP)
        result = c.compare(left, right)
        self.assertEqual(result['only_in_candidate'], ['extra'])
        self.assertFalse(result['normalized_all_members_equal'])


class InputTests(unittest.TestCase):
    def test_exact_tag_declaration_remains_unauthenticated(self):
        raw = json.dumps([{'name': 'v4.19.88', 'commit': {'sha': m.candidate.COMMIT}}]).encode()
        self.assertFalse(m.tag_declaration(raw)['tag_signature_verified'])
        row = json.loads(raw)[0]
        for value in ([], [row, row], [{'name': 'v4.19.88-2', 'commit': row['commit']}],
                      [{'name': 'v4.19.88', 'commit': {'sha': '0' * 40}}], [row] * 101):
            with self.assertRaises(ValueError):
                m.tag_declaration(json.dumps(value).encode())

    def test_independent_requests_preserve_failure_without_retry(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(m.route, 'DIRECTORY', Path(temporary)):
            (Path(temporary) / 'fetch-plan.json').write_text(json.dumps(m.route.plan()))
            with patch.object(m.route.fetch, 'fetch', side_effect=[1, 0]) as fetch:
                self.assertEqual(m.route.execute(), 1)
            self.assertEqual([r.args for r in fetch.call_args_list], [('headers', 1), ('tags', 1)])

    def test_plan_drift_stops_before_network(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(m.route, 'DIRECTORY', Path(temporary)):
            (Path(temporary) / 'fetch-plan.json').write_text('{}')
            with patch.object(m.route.fetch, 'fetch') as fetch, self.assertRaises(ValueError):
                m.route.execute()
            fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
