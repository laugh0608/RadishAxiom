#!/usr/bin/env python3
"""Retained synthetic GNU inputs and adversarial pre-link checks; no SDK runs."""
import copy
import hashlib
import importlib.util
import gzip
import io
import json
from pathlib import Path
import shlex
import tempfile
import tarfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


M = load('material_test', 'scripts/cvc5-build-support/link_materials.py')
F, R = M.F, M.R
I = load('independent_material_fixture', 'scripts/check-cvc5-phases-independent.py')
C2 = load('c2_material_test', 'scripts/prepare-cvc5-offline-build.py')


class FormatTests(unittest.TestCase):
    def test_gnu_quoting_backslash_empty_and_no_shell_comments(self):
        raw = b'''one "two three" 'four five' six\\ seven "" '#literal' 'a\\b' "a\\b"\n'''
        self.assertEqual(F.response(raw), ['one', 'two three', 'four five', 'six seven', '', '#literal', 'ab', 'ab'])
        self.assertEqual(F.response(b'a\\\nb'), ['a\nb'])

    def test_response_malformed_and_budgets(self):
        for raw in (b'"unfinished', b'last\\', b'\0', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                F.response(raw)
        with patch.object(F, 'ARG_LIMIT', 2), self.assertRaisesRegex(ValueError, 'budget'):
            F.response(b'a b c')
        with patch.object(F, 'TEXT_LIMIT', 2), self.assertRaisesRegex(ValueError, 'budget'):
            F.response(b'abc')

    def test_archive_duplicate_names_keep_distinct_occurrences(self):
        payloads = [I.elf(17), I.elf(29)]
        raw = b'!<arch>\n' + b''.join(I.ar_member('same.o/', x) for x in payloads)
        members = F.archive(raw)
        self.assertEqual([(m['name'], m['index'], m['occurrence']) for m in members], [('same.o', 0, 1), ('same.o', 1, 2)])
        self.assertNotEqual(members[0]['sha256'], members[1]['sha256'])

    def test_archive_long_names_and_special_table_are_retained(self):
        raw = b'!<arch>\n' + I.ar_member('/', bytes(4)) + I.ar_member('//', b'long-object-name.o/\n')
        raw += I.ar_member('/0', I.elf(17))
        members = F.archive(raw)
        self.assertEqual([m['name'] for m in members], ['/', '//', 'long-object-name.o'])
        self.assertEqual([m['kind'] for m in members], ['table', 'table', 'object'])

    def test_archive_thin_bsd_truncation_padding_and_bad_long_offset(self):
        normal = b'!<arch>\n' + I.ar_member('a.o/', I.elf(17))
        cases = [b'!<thin>\n', normal[:-1], normal[:20], b'!<arch>\n' + I.ar_member('#1/3', b'abc'),
                 b'!<arch>\n' + I.ar_member('//', b'long-name.o/\n') + I.ar_member('/1', I.elf(17))]
        for raw in cases:
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                F.archive(raw)

    def test_object_wrong_abi_type_lto_and_section_bounds(self):
        raw = I.elf(17)
        F.object_header(raw)
        cases = []
        for pos in (4, 5, 16, 18, 40):
            damaged = bytearray(raw)
            damaged[pos] ^= 0x40
            cases.append(bytes(damaged))
        cases += [raw[:60], raw.replace(b'.data\0', b'.llvm\0')]
        for damaged in cases:
            with self.subTest(raw=damaged[:24]), self.assertRaises(ValueError):
                F.object_header(damaged)

    def test_script_subset_preserves_groups_and_paths(self):
        value = F.script(b'/* test */ GROUP ( /a.a AS_NEEDED ( "sub/b.a" -lc ) )\n')
        self.assertEqual(value['inputs'], ['/a.a', 'sub/b.a', '-lc'])
        self.assertEqual(value['tokens'][:3], ['GROUP', '(', '/a.a'])

    def test_script_unsupported_or_incomplete(self):
        for raw in (b'INCLUDE /host', b'SEARCH_DIR(/host)', b'INPUT(', b'INPUT()', b'INPUT(a.o);',
                    b'/* unfinished', b'INPUT("unfinished)', b'AS_NEEDED(a.o)', b'INPUT($SECRET)'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                F.script(raw)

    def test_generated_command_only_accepts_one_reviewed_launcher(self):
        line = (shlex.join(M.PREFIX + [R.CXX, '-static', 'x.o']) + '\n').encode()
        self.assertEqual(M.generated_command(line), [R.CXX, '-static', 'x.o'])
        for raw in (line + b'echo extra\n', line.replace(b'x.o', b'$(echo x).o'),
                    line.replace(b'x.o', b'*.o'), line.replace(b'capture_link.py', b'other.py')):
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                M.generated_command(raw)


class MaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cvc5-material-test-', dir=ROOT / '.tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'synthetic'
        self.recipe = I.fixture_recipe()
        self.sha = I.digest(I.encoded(self.recipe))
        self.phases, self.value = I.prepare(self.recipe, self.sha, self.root)
        self.phase_result = R.check_declarations(self.phases, self.recipe, self.sha)
        self.phase_result['phase_declarations_sha256'] = I.digest((self.root / 'phases.json').read_bytes())

    def check(self):
        return M.check(self.value, self.root, self.recipe, self.sha, self.phase_result, C2)

    def replace(self, logical, raw):
        row = next(r for r in self.value['files'] if r['path'] == logical)
        path = self.root / row['file']['path']
        path.write_bytes(raw)
        row['file'].update(bytes=len(raw), sha256=I.digest(raw))

    def change_command(self, change, update_generated=True, expanded=None):
        capture = json.loads((self.root / 'capture.json').read_bytes())
        change(capture)
        raw = I.encoded(capture)
        (self.root / 'capture.json').write_bytes(raw)
        self.value['capture'].update(bytes=len(raw), sha256=I.digest(raw))
        self.phase_result['unverified_outputs']['link-capture'] = I.digest(raw)
        if update_generated:
            command = (shlex.join(M.PREFIX + capture['argv']) + '\n').encode()
            (self.root / 'link.txt').write_bytes(command)
            self.value['generated_link'].update(bytes=len(command), sha256=I.digest(command))
        if expanded is not None:
            self.value['expanded_arguments'] = expanded

    def test_positive_order_alias_response_and_no_acceptance(self):
        result = self.check()
        self.assertEqual(result['input_sequence'], [I.A, I.B, I.A, I.SCRIPT, I.LIB, I.LIB, I.LIB])
        self.assertEqual(result['response_sequence'], [I.CWD + '/CMakeFiles/objects.rsp', I.CWD + '/CMakeFiles/more.rsp'])
        self.assertEqual(result['implicit_input_completeness'], 'not-established')
        self.assertFalse(result['runtime_qualification'])
        self.assertFalse(result['build_ready'])

    def test_sort_dedup_or_drop_of_arguments_and_inputs(self):
        for field in ('expanded_arguments', 'input_sequence'):
            original = self.value[field][:]
            for changed in (sorted(original), list(dict.fromkeys(original)), original[:-1]):
                if changed == original:
                    continue
                self.value[field] = changed
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'order'):
                    self.check()
            self.value[field] = original

    def test_missing_input_and_changed_bytes(self):
        self.value['files'] = [r for r in self.value['files'] if r['path'] != I.B]
        with self.assertRaisesRegex(ValueError, 'missing-input'):
            self.check()

    def test_same_size_post_capture_replacement_rejected(self):
        path = self.root / 'alpha.o'
        raw = path.read_bytes()
        path.write_bytes(raw[:-1] + b'\xff')
        with self.assertRaisesRegex(ValueError, 'byte-binding'):
            self.check()

    def test_generated_command_disagrees_with_capture(self):
        self.change_command(lambda c: c['argv'].append('-O3'), update_generated=False)
        with self.assertRaisesRegex(ValueError, 'command-drift'):
            self.check()

    def test_empty_or_non_sdk_implicit_inputs(self):
        for names in ([], [I.A], ['/usr/lib/not-retained.a']):
            self.value['implicit_inputs'] = names
            with self.subTest(names=names), self.assertRaises(ValueError):
                self.check()

    def test_new_unknown_producer_or_changed_phase_binding(self):
        row = self.value['files'][0]
        for field, value in (('producer', 'final-link'), ('producer_sha256', 'a' * 64), ('frozen_before_link', False)):
            old = row[field]
            row[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'producer|frozen'):
                self.check()
            row[field] = old

    def test_inputs_cannot_hide_in_writable_output_overlay(self):
        self.value['files'][0]['path'] = I.CWD + '/bin/alpha.o'
        with self.assertRaisesRegex(ValueError, 'hidden-by-writable'):
            self.check()

    def test_alias_cycle_escape_writable_and_directory_qualifier(self):
        alias = self.value['aliases'][0]
        for target in ('alias.o', '../../../../../../outside', 'alpha.o/.', 'alpha.o/../space name.o'):
            alias['target'] = target
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.check()
        alias.update(path='/work/tmp/alias.o', target=I.A)
        with self.assertRaisesRegex(ValueError, 'writable-alias'):
            self.check()

    def test_real_retained_symlink_and_parent_symlink_rejected(self):
        path = self.root / 'alpha.o'
        path.rename(self.root / 'original.o')
        path.symlink_to(self.root / 'original.o')
        with self.assertRaisesRegex(ValueError, 'noncanonical'):
            self.check()

    def test_unowned_virtual_alias_cannot_expand_input_namespace(self):
        self.value['aliases'].append({'path': '/host/alias.o', 'target': I.A})
        with self.assertRaisesRegex(ValueError, 'alias-origin'):
            self.check()

    def test_declared_implicit_script_must_not_hide_unknown_input(self):
        row = next(r for r in self.value['files'] if r['path'] == I.SPECS)
        row['role'] = 'script'
        self.replace(I.SPECS, b'INPUT(/host/not-retained.a)')
        with self.assertRaisesRegex(ValueError, 'missing-input'):
            self.check()

    def test_response_cycle_truncation_and_recursion_budget(self):
        name = I.CWD + '/CMakeFiles/more.rsp'
        for raw in (b'@CMakeFiles/objects.rsp', b'"truncated', b'@missing.rsp'):
            self.replace(name, raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.check()

    def test_expansion_total_byte_budget(self):
        with patch.object(M, 'EXPANDED_LIMIT', 8), self.assertRaisesRegex(ValueError, 'budget'):
            self.check()

    def test_missing_archive_member_and_ambiguous_duplicate_occurrence(self):
        row = next(r for r in self.value['files'] if r['path'] == I.LIB)
        original = copy.deepcopy(row['members'])
        for members in (original[:1], list(reversed(original)), [original[0], original[0]]):
            row['members'] = members
            with self.subTest(members=len(members)), self.assertRaisesRegex(ValueError, 'member-drift'):
                self.check()

    def test_script_cycle_escape_and_unsupported_syntax(self):
        for raw in (('INPUT(' + I.SCRIPT + ')').encode(), b'INPUT(/host/lib.a)', b'SEARCH_DIR(/host)', b'INPUT(relative.a)'):
            self.replace(I.SCRIPT, raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.check()

    def test_library_search_keeps_repetitions_and_all_L_flags(self):
        original = self.value['expanded_arguments'][:]
        # -L after -l is still used by the GNU linker for that lookup.
        expected = original[:-1] + ['-ldep', '-L/work/prefix/test/lib']
        self.change_command(lambda c: c['argv'].__setitem__(slice(-1, None), ['-ldep', '-L/work/prefix/test/lib']),
                            expanded=expected)
        self.assertEqual(self.check()['input_sequence'][-3:], [I.LIB] * 3)

    def test_unreviewed_search_root_is_rejected(self):
        expected = self.value['expanded_arguments'] + ['-L/host/lib']
        self.change_command(lambda c: c['argv'].append('-L/host/lib'), expanded=expected)
        with self.assertRaisesRegex(ValueError, 'search-root'):
            self.check()

    def test_lto_dynamic_unknown_option_and_changed_output(self):
        original = copy.deepcopy(self.value['expanded_arguments'])
        for flag in ('-flto', '-Wl,-Bdynamic', '-specs=/host/specs'):
            self.change_command(lambda c: c['argv'].append(flag), expanded=original + [flag])
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                self.check()
            # Restore the fixture's command before the next independent mutation.
            self.change_command(lambda c: c['argv'].pop(), expanded=original)
        self.change_command(lambda c: c['argv'].__setitem__(10, '/work/other'),
                            expanded=[('/work/other' if x == 'bin/cvc5' else x) for x in original])
        with self.assertRaisesRegex(ValueError, 'output-drift'):
            self.check()

    def test_required_map_trace_static_options_cannot_disappear(self):
        original = copy.deepcopy(self.value['expanded_arguments'])
        self.change_command(lambda c: c['argv'].__setitem__(6, '-Wl,-Map,/work/evidence/cvc5.map,--cref,-t'),
                            expanded=[x.replace(',--cref,-t,-t', ',--cref,-t') for x in original])
        with self.assertRaisesRegex(ValueError, 'required-options'):
            self.check()

    def test_environment_cwd_and_capture_success_tampering(self):
        for field, value in (('cwd', '/host'), ('driver_executed', True), ('exit_code', 0)):
            # Fresh byte bindings cannot turn an invalid claim into a valid capture.
            previous = json.loads((self.root / 'capture.json').read_bytes())[field]
            self.change_command(lambda c: c.update({field: value}))
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check()
            self.change_command(lambda c: c.update({field: previous}))
        self.change_command(lambda c: c['environment'].update(LD_PRELOAD='/synthetic/forbidden'))
        with self.assertRaisesRegex(ValueError, 'environment-keys'):
            self.check()

    def test_inherited_shell_pwd_is_retained_separately_from_actual_cwd(self):
        self.change_command(lambda c: c['environment'].update(PWD='/work'))
        self.assertFalse(self.check()['build_ready'])
        capture = json.loads((self.root / 'capture.json').read_bytes())
        self.assertEqual((capture['cwd'], capture['environment']['PWD']), (I.CWD, '/work'))

    def test_unknown_fields_duplicate_paths_mixed_version_and_false_actual_link(self):
        for field, value in (('extra', True), ('version', '0.1'), ('actual_link', {'success': True})):
            saved = copy.deepcopy(self.value)
            self.value[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check()
            self.value = saved
        self.value['files'].append(copy.deepcopy(self.value['files'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate-path'):
            self.check()

    def test_input_budgets_boolean_counts_and_malformed_phase_position(self):
        self.value['files'][0]['file']['bytes'] = True
        with self.assertRaisesRegex(ValueError, 'file-budget'):
            self.check()
        self.phase_result['checked_prefix'] = ['dependencies', 'main-compile', 'final-link']
        with self.assertRaisesRegex(ValueError, 'phase-position'):
            self.check()

    def test_independent_export_rejects_production_checker_disagreement(self):
        result = dict(self.phase_result, link_materials=self.check(),
                      link_declarations_sha256=I.digest((self.root / 'prelink.json').read_bytes()))
        exported = self.root / 'export.json'
        exported.write_bytes(I.encoded(result))
        self.assertEqual(I.check_export(self.root, exported)['ordered_inputs'], 7)
        for change in (lambda r: r.update(build_ready=True),
                       lambda r: r['link_materials']['input_sequence'].pop(),
                       lambda r: r['link_materials']['archive_members'][I.LIB][1].update(occurrence=1)):
            altered = copy.deepcopy(result)
            change(altered)
            exported.write_bytes(I.encoded(altered))
            with self.assertRaisesRegex(ValueError, 'independent:'):
                I.check_export(self.root, exported)


class RetainedSdkFormatTests(unittest.TestCase):
    def test_three_fixed_sdk_members_in_memory_without_materialization(self):
        content = load('retained_sdk_reader', 'scripts/inspect-cvc5-c1-sdk-content.py')
        inventory_path = ROOT / 'docs/records/solver-cvc5-c1-review-2026-10-23/content-inventory.json.gz'
        inventory = json.loads(gzip.decompress(inventory_path.read_bytes()))
        wanted = {
            'libgcc-12-dev': {'usr/lib/gcc/aarch64-linux-gnu/12/libgcc.a': 'archive'},
            'libc6-dev': {'usr/lib/aarch64-linux-gnu/libc.a': 'archive',
                         'usr/lib/aarch64-linux-gnu/libm.a': 'archive'},
        }
        matched = set()
        for package in inventory['observations']:
            if package['kind'] != 'binary' or package['package'] not in wanted:
                continue
            ref = package['input']
            raw = C2.regular(ROOT / ref['path']).read_bytes()
            self.assertEqual((len(raw), I.digest(raw)), (ref['bytes'], ref['sha256']))
            for name, data in content.ar_members(raw):
                if not name.startswith('data.tar.'):
                    continue
                blocks, total = [], 0
                for block in content.expanded_chunks(data, name):
                    total += len(block)
                    self.assertLessEqual(total, 128 * 1024**2)
                    blocks.append(block)
                expected = {r['path']: r for r in package['data']['entries']}
                with tarfile.open(fileobj=io.BytesIO(b''.join(blocks)), mode='r:') as archive:
                    for member in archive:
                        path = content.canonical(member.name)
                        if path not in wanted[package['package']]:
                            continue
                        self.assertTrue(member.isfile())
                        with archive.extractfile(member) as stream:
                            body = stream.read(64 * 1024**2 + 1)
                        self.assertLessEqual(len(body), 64 * 1024**2)
                        self.assertEqual((len(body), I.digest(body)), (expected[path]['bytes'], expected[path]['sha256']))
                        if wanted[package['package']][path] == 'archive':
                            members = F.archive(body)
                            self.assertGreater(len(members), 1)
                        else:
                            self.assertTrue(all(x.startswith('/') for x in F.script(body)['inputs']))
                        matched.add(path)
        self.assertEqual(matched, {p for paths in wanted.values() for p in paths})


if __name__ == '__main__':
    unittest.main()
