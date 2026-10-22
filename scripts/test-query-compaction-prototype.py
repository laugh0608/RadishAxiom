#!/usr/bin/env python3
"""独立手算恒等式、负向规则和离线语法拒绝测试。"""
from dataclasses import replace
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location(
    "query_compaction_prototype", Path(__file__).with_name("query_compaction_prototype.py"))
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
Budgets = MODULE.Budgets
PrototypeError = MODULE.PrototypeError
transform = MODULE.transform
PREAMBLE = '(set-logic QF_UFLIA)\n(declare-sort Text 0)\n'


def query(lines, root='goal'):
    return (PREAMBLE + '\n'.join(lines) + f'\n(assert {root})\n(check-sat)\n').encode('ascii')


def forms(data):
    """独立测试读取器，接纳紧凑 SMT 中的嵌套项。"""
    import re
    tokens = re.findall(r'\(|\)|[^\s()]+', data.decode('ascii'))
    stack = []
    result = []
    for token in tokens:
        if token == '(':
            stack.append([])
        elif token == ')':
            node = stack.pop()
            (stack[-1] if stack else result).append(node)
        else:
            stack[-1].append(token)
    return result


def evaluate(data, free):
    """独立解释 SMT 全函数操作，核验有限组测试赋值。"""
    environment = dict(free)

    def value(expression):
        if isinstance(expression, str):
            if expression == 'true':
                return True
            if expression == 'false':
                return False
            if expression.isdigit():
                return int(expression)
            return environment[expression]
        operator = expression[0]
        args = [value(arg) for arg in expression[1:]]
        if operator == 'not':
            return not args[0]
        if operator == 'and':
            return all(args)
        if operator == 'or':
            return any(args)
        if operator == '=':
            return args[0] == args[1]
        if operator == '+':
            return args[0] + args[1]
        if operator == '-':
            return -args[0] if len(args) == 1 else args[0] - args[1]
        if operator == '<':
            return args[0] < args[1]
        if operator == '<=':
            return args[0] <= args[1]
        if operator == '>':
            return args[0] > args[1]
        if operator == '>=':
            return args[0] >= args[1]
        if operator == 'ite':
            return args[1] if args[0] else args[2]
        raise AssertionError(operator)

    for command in forms(data):
        if command[0] == 'define-fun':
            environment[command[1]] = value(command[4])
        if command[0] == 'assert':
            return value(command[1])
    raise AssertionError('missing assertion')


def representation_variants():
    # 首版128/8预算保持不变；这两个参数可独立恢复首版表示。
    return (
        ('legacy', replace(Budgets(), min_free_name_digits=6, inline_multiuse_bytes=0)),
        ('short', replace(Budgets(), inline_multiuse_bytes=0)),
        ('multiuse', replace(Budgets(), min_free_name_digits=6)),
        ('combined', Budgets()),
    )


class CompactionTests(unittest.TestCase):
    def assert_truth(self, lines, expected):
        artifact = transform(query(lines))
        self.assertIn(f'(assert {str(expected).lower()})'.encode(), artifact.smt_bytes)
        self.assertEqual(evaluate(artifact.smt_bytes, {}), expected)
        return artifact

    def test_hand_calculated_constants(self):
        self.assert_truth([
            '(define-fun a () Int (- 7))', '(define-fun b () Int 2)',
            '(define-fun c () Int (+ a b))', '(define-fun d () Int (- c b))',
            '(define-fun goal () Bool (= d a))'], True)
        self.assert_truth([
            '(define-fun f () Bool false)', '(define-fun t () Bool true)',
            '(define-fun a () Bool (not t))', '(define-fun b () Bool (or f a))',
            '(define-fun goal () Bool (and t b))'], False)
        for op, expected in [('<', False), ('<=', True), ('>', False), ('>=', True)]:
            self.assert_truth(['(declare-const x Int)',
                               f'(define-fun goal () Bool ({op} x x))'], expected)
        for op, expected in [('<', True), ('<=', True), ('>', False), ('>=', False)]:
            self.assert_truth(['(define-fun x () Int (- 4))', '(define-fun y () Int 3)',
                               f'(define-fun goal () Bool ({op} x y))'], expected)

    def test_more_hand_calculated_identity_rules(self):
        self.assert_truth([
            '(define-fun t () Bool true)', '(define-fun f () Bool false)',
            '(define-fun goal () Bool (= t f))'], False)
        for op, constant, expected in [('and', 'false', False), ('or', 'true', True)]:
            self.assert_truth(['(declare-const p Bool)', f'(define-fun c () Bool {constant})',
                               f'(define-fun goal () Bool ({op} p c))'], expected)
        data = query(['(declare-const p Bool)', '(declare-const x Int)',
                      '(define-fun zero () Int 0)', '(define-fun a () Int (+ zero x))',
                      '(define-fun b () Int (- a zero))',
                      '(define-fun same () Bool (= b x))',
                      '(define-fun t () Bool true)', '(define-fun f () Bool false)',
                      '(define-fun flag () Bool (ite p t f))',
                      '(define-fun goal () Bool (and same flag))'])
        self.assertIn(b'(assert s0)', transform(data).smt_bytes)

    def test_symbol_identities_and_free_bijection(self):
        data = query([
            '(declare-const z Text)', '(declare-const beta Bool)', '(declare-const alpha Int)',
            '(declare-const text_literal_A Text)', '(declare-const text_literal_B Text)',
            '(define-fun zero () Int 0)', '(define-fun a () Int (+ alpha zero))',
            '(define-fun b () Int (- a alpha))', '(define-fun goal () Bool (= b zero))'])
        artifact = transform(data)
        self.assertEqual([s.old for s in artifact.free_symbols],
                         ['alpha', 'beta', 'text_literal_A', 'text_literal_B', 'z'])
        self.assertEqual([s.new for s in artifact.free_symbols],
                         ['s0', 's1', 's2', 's3', 's4'])
        self.assertEqual(artifact.stats['output_definitions'], 0)
        self.assertIn(b'(assert true)', artifact.smt_bytes)
        self.assertEqual(artifact.smt_bytes.count(b'declare-const'), 5)

    def test_free_text_values_not_assumed_distinct(self):
        data = query(['(declare-const literal_A Text)', '(declare-const literal_B Text)',
                      '(declare-const inactive Text)',
                      '(define-fun goal () Bool (= literal_A literal_B))'])
        artifact = transform(data)
        self.assertEqual(len(artifact.free_symbols), 3)
        mapping = {s.old: s.new for s in artifact.free_symbols}
        for a, b, expected in [('same', 'same', True), ('A', 'B', False)]:
            assignment = {'literal_A': a, 'literal_B': b, 'inactive': 'unused'}
            self.assertEqual(evaluate(artifact.smt_bytes,
                                     {mapping[k]: v for k, v in assignment.items()}), expected)

    def test_exact_sharing_and_symmetric_equality(self):
        artifact = transform(query([
            '(declare-const a Text)', '(declare-const b Text)',
            '(define-fun x () Bool (= a b))', '(define-fun y () Bool (= b a))',
            '(define-fun goal () Bool (and x y x))']))
        self.assertIn(b'(assert (= s0 s1))', artifact.smt_bytes)
        self.assertGreater(artifact.stats['shared_terms'], 0)

    def test_ite_and_double_not(self):
        data = query([
            '(declare-const p Bool)', '(define-fun t () Bool true)',
            '(define-fun f () Bool false)', '(define-fun a () Bool (ite p f t))',
            '(define-fun b () Bool (not a))', '(define-fun goal () Bool (ite t b f))'])
        artifact = transform(data)
        self.assertIn(b'(assert s0)', artifact.smt_bytes)
        for p in (False, True):
            self.assertEqual(evaluate(artifact.smt_bytes, {'s0': p}), p)
        self.assert_truth(['(declare-const p Bool)', '(define-fun n () Int 6)',
                           '(define-fun a () Int (ite p n n))',
                           '(define-fun goal () Bool (= a n))'], True)

    def test_rules_do_not_assume_wf_or_fault_or_int_bounds(self):
        data = query([
            '(declare-const fault Bool)', '(declare-const x Int)', '(declare-const y Int)',
            '(define-fun a () Int (- x y))', '(define-fun b () Bool (< x y))',
            '(define-fun c () Bool (= a x))', '(define-fun goal () Bool (ite fault b c))'])
        artifact = transform(data)
        mapping = {s.old: s.new for s in artifact.free_symbols}
        for fault in (False, True):
            for x in (-10**30, -1, 0, 10**30):
                for y in (-3, 0, 5):
                    assignment = {'fault': fault, 'x': x, 'y': y}
                    expected = x < y if fault else x - y == x
                    self.assertEqual(evaluate(artifact.smt_bytes,
                                             {mapping[k]: v for k, v in assignment.items()}), expected)
        self.assertIn(b'declare-const s0 Bool', artifact.smt_bytes)

    def test_sort_sensitive_sharing(self):
        artifact = transform(query([
            '(declare-const b Bool)', '(declare-const i Int)', '(declare-const t Text)',
            '(define-fun x () Bool (= b b))', '(define-fun y () Bool (= i i))',
            '(define-fun z () Bool (= t t))', '(define-fun goal () Bool (and x y z))']))
        self.assertEqual([s.sort for s in artifact.free_symbols], ['Bool', 'Int', 'Text'])
        self.assertIn(b'(assert true)', artifact.smt_bytes)

    def test_deep_chain_is_iterative_and_bounded_inline(self):
        lines = ['(declare-const x Int)', '(define-fun one () Int 1)']
        previous = 'x'
        for index in range(6000):
            name = f'n{index}'
            lines.append(f'(define-fun {name} () Int (+ {previous} one))')
            previous = name
        lines.append(f'(define-fun goal () Bool (> {previous} x))')
        artifact = transform(query(lines))
        self.assertEqual(artifact.stats['input_depth'], 6002)
        self.assertLess(len(artifact.smt_bytes), 300000)
        self.assertLess(max(len(line) for line in artifact.smt_bytes.splitlines()), 200)
        with self.assertRaisesRegex(PrototypeError, 'max_depth'):
            transform(query(lines), replace(Budgets(), max_depth=6001))

    def test_high_arity_and_no_exponential_expansion(self):
        lines = ['(declare-const p Bool)', '(define-fun n0 () Bool (not p))']
        for index in range(1, 100):
            # 同一项被链后继和根各引用一次，不能按单次引用内联。
            lines.append(f'(define-fun n{index} () Bool (= n{index-1} p))')
        lines.append('(define-fun goal () Bool (and ' + ' '.join(f'n{i}' for i in range(100)) + '))')
        artifact = transform(query(lines))
        self.assertLess(artifact.stats['output_bytes'], 15000)
        data = query(['(declare-const p Bool)',
                      '(define-fun goal () Bool (and ' + ' '.join(['p'] * 20000) + '))'])
        self.assertIn(b'(assert s0)', transform(data).smt_bytes)
        with self.assertRaisesRegex(PrototypeError, 'max_edges'):
            transform(data, replace(Budgets(), max_edges=19999))

    def test_cli_origins_budget(self):
        with tempfile.TemporaryDirectory(prefix='axiom-compact-test-') as directory:
            root = Path(directory)
            source, origins = root/'input.smt2', root/'origins.json'
            output, metadata = root/'out.smt2', root/'meta.json'
            source.write_bytes(query(['(define-fun goal () Bool true)']))
            origins.write_text('{}', encoding='utf-8')
            script = Path(__file__).with_name('query_compaction_prototype.py')
            result = subprocess.run([sys.executable, str(script), str(source), '--output', str(output),
                                     '--metadata', str(metadata), '--origins', str(origins),
                                     '--max-origins-bytes', '1'], capture_output=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b'max_origins_bytes', result.stderr)
            self.assertFalse(output.exists())
            self.assertFalse(metadata.exists())

    def test_strict_rejections_even_unreachable(self):
        valid = query(['(define-fun goal () Bool true)'])
        invalid = [
            valid.replace(b'QF_UFLIA', b'ALL'),
            valid + b'(check-sat)\n',
            valid.replace(b'(check-sat)', b'(assert goal)\n(check-sat)'),
            valid.replace(b'(assert goal)', b'(assert false)'),
            valid.replace(b'(assert goal)', b'(assert (not goal))'),
            valid.replace(b'Bool true', b'Int true'),
            valid.replace(b'() Bool', b'((x Bool)) Bool'),
            valid.replace(b'Bool true', b'Real 1'),
            valid.replace(b'Bool true', b'Bool (forall () true)'),
            query(['(declare-const _ Bool)', '(define-fun goal () Bool true)']),
            query(['(define-fun n () Int 00)', '(define-fun goal () Bool true)']),
            query(['(declare-const a (Array Int Int))', '(define-fun goal () Bool true)']),
            query(['(define-fun n () Int 1)', '(define-fun goal () Bool (ite n n n))']),
            query(['(declare-const p Bool)', '(define-fun n () Int 1)',
                   '(define-fun goal () Bool (ite p p n))']),
            valid.replace(b'Bool true', b'Bool (= missing missing)'),
            query(['(define-fun goal () Bool (not later))', '(declare-const later Bool)']),
            query(['(declare-const x Int)', '(define-fun goal () Bool (and x x))']),
            query(['(declare-const x Int)', '(define-fun goal () Bool (= x x x))']),
            query(['(declare-const x Bool)', '(define-fun goal () Bool (not x x))']),
            query(['(declare-const x Int)', '(define-fun goal () Bool (< x))']),
            query(['(declare-const x Int)', '(define-fun goal () Bool (= (+ x x) x))']),
            query(['(define-fun goal () Bool true)', '(define-fun goal () Bool false)']),
            query(['(declare-const x Text)', '(define-fun goal () Bool true)',
                   '(define-fun dead () Int (+ x x))']),
            valid[:-1] + b'(', valid + b'; comment', b'\xff',
        ]
        for data in invalid:
            with self.subTest(data=data[:120]):
                with self.assertRaises(PrototypeError):
                    transform(data)

    def test_budget_boundaries(self):
        data = query(['(define-fun goal () Bool true)'])
        result = transform(data)
        self.assertEqual(transform(data, replace(Budgets(), max_input_bytes=len(data), max_terms=1,
                                                max_depth=1, max_output_bytes=len(result.smt_bytes))).smt_bytes,
                         result.smt_bytes)
        for field, limit in [('max_input_bytes', len(data) - 1),
                             ('max_output_bytes', len(result.smt_bytes) - 1),
                             ('max_syntax_depth', 1)]:
            failing_data = (query(['(define-fun i () Int (- 2))',
                                   '(define-fun goal () Bool (= i i))'])
                            if field == 'max_syntax_depth' else data)
            with self.subTest(field=field):
                with self.assertRaisesRegex(PrototypeError, field):
                    transform(failing_data, replace(Budgets(), **{field: limit}))
        with self.assertRaisesRegex(PrototypeError, 'max_terms'):
            transform(query(['(define-fun f () Bool false)', '(define-fun goal () Bool true)']),
                      replace(Budgets(), max_terms=1))
        with self.assertRaisesRegex(PrototypeError, 'max_integer_digits'):
            transform(query(['(define-fun n () Int 123)', '(define-fun goal () Bool (= n n))']),
                      replace(Budgets(), max_integer_digits=2))
        with self.assertRaisesRegex(PrototypeError, 'max_integer_digits'):
            transform(query(['(define-fun n () Int 99)', '(define-fun m () Int 1)',
                             '(define-fun a () Int (+ n m))', '(define-fun goal () Bool (= a a))']),
                      replace(Budgets(), max_integer_digits=2))

    def test_production_feasibility_is_separate_refusal(self):
        # 保留全部自由输入本身即可超出生产字节阈值。
        lines = [f'(declare-const x{i} Int)' for i in range(45000)]
        lines.append('(define-fun goal () Bool true)')
        artifact = transform(query(lines))
        self.assertGreater(artifact.stats['output_bytes'], 1024 * 1024)
        self.assertFalse(artifact.stats['within_production_byte_limit'])
        self.assertEqual(artifact.stats['production_byte_feasibility'],
                         'refused-over-production-byte-limit')

    def test_origins_and_determinism(self):
        data = query(['(declare-const x Bool)', '(define-fun goal () Bool (not x))'])
        artifact = transform(data, origins={'x': {'kind': 'synthetic'}})
        self.assertEqual(artifact.free_symbols[0].origin, {'kind': 'synthetic'})
        self.assertEqual(artifact.smt_bytes, transform(data).smt_bytes)
        self.assertNotIn(b'synthetic', artifact.smt_bytes)
        self.assertIn('research', artifact.metadata()['artifact_kind'])
        for origins in ({}, {'x': None, 'y': None}, []):
            with self.assertRaises(PrototypeError):
                transform(data, origins=origins)

    def test_cli_refusal_does_not_write_partial_artifacts(self):
        with tempfile.TemporaryDirectory(prefix='axiom-compact-test-') as directory:
            root = Path(directory)
            source, output, metadata = root/'input.smt2', root/'out.smt2', root/'meta.json'
            source.write_bytes(query(['(define-fun goal () Bool true)']))
            output.write_bytes(b'previous-output')
            metadata.write_bytes(b'previous-metadata')
            script = Path(__file__).with_name('query_compaction_prototype.py')
            result = subprocess.run([sys.executable, str(script), str(source), '--output', str(output),
                                     '--metadata', str(metadata), '--max-output-bytes', '1'],
                                    capture_output=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b'refused', result.stderr)
            self.assertEqual(output.read_bytes(), b'previous-output')
            self.assertEqual(metadata.read_bytes(), b'previous-metadata')
            result = subprocess.run([sys.executable, str(script), str(source), '--output', str(output),
                                     '--metadata', str(metadata)], capture_output=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(output.read_bytes(), b'previous-output')
            self.assertEqual(metadata.read_bytes(), b'previous-metadata')
            output.unlink()
            result = subprocess.run([sys.executable, str(script), str(source), '--output', str(output),
                                     '--metadata', str(metadata)], capture_output=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
            self.assertEqual(metadata.read_bytes(), b'previous-metadata')
            metadata.unlink()
            result = subprocess.run([sys.executable, str(script), str(source), '--output', str(output),
                                     '--metadata', str(metadata)], capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b'(assert true)', output.read_bytes())
            self.assertIn(b'not-production-request', metadata.read_bytes())


    def test_free_mapping_bijection_and_text_order(self):
        for variant, budget in representation_variants():
            for count in (1, 9, 10, 11, 100):
                lines = [f'(declare-const symbol{i} Text)' for i in range(count)]
                lines.append('(define-fun goal () Bool true)')
                artifact = transform(query(lines), budget)
                width = max(budget.min_free_name_digits, len(str(count - 1)))
                self.assertEqual(len(artifact.free_symbols), count)
                self.assertEqual([s.old for s in artifact.free_symbols],
                                 sorted(f'symbol{i}' for i in range(count)))
                self.assertEqual([s.new for s in artifact.free_symbols],
                                 [f's{i:0{width}d}' for i in range(count)])
                self.assertEqual(artifact.smt_bytes.count(b'declare-const'), count)

    def test_small_multiuse_is_semantically_identical(self):
        lines = ['(declare-const p Bool)', '(declare-const q Bool)',
                 '(define-fun n () Bool (not p))', '(define-fun a () Bool (or n q))',
                 '(define-fun b () Bool (= n q))', '(define-fun goal () Bool (and a b))']
        for variant, budget in representation_variants():
            artifact = transform(query(lines), budget)
            if budget.inline_multiuse_bytes:
                self.assertEqual(artifact.stats['output_definitions'], 0)
            else:
                self.assertEqual(artifact.stats['output_definitions'], 1)
            if variant == 'legacy':
                expected = (PREAMBLE + '(declare-const s000000 Bool)\n'
                            '(declare-const s000001 Bool)\n'
                            '(define-fun d0 () Bool (not s000000))\n'
                            '(assert (and (or d0 s000001) (= s000001 d0)))\n(check-sat)\n')
                self.assertEqual(artifact.smt_bytes, expected.encode('ascii'))
            names = {s.old: s.new for s in artifact.free_symbols}
            for p in (False, True):
                for q in (False, True):
                    self.assertEqual(evaluate(artifact.smt_bytes, {names['p']: p, names['q']: q}),
                                     ((not p) or q) and ((not p) == q))

    def test_repeated_small_term_kept_when_inline_cost_is_larger(self):
        lines = ['(declare-const p Bool)']
        lines += [f'(declare-const q{i} Bool)' for i in range(100)]
        lines += ['(define-fun n () Bool (not p))']
        lines += [f'(define-fun a{i} () Bool (= n q{i}))' for i in range(100)]
        lines += ['(define-fun goal () Bool (and ' + ' '.join(f'a{i}' for i in range(100)) + '))']
        for variant, budget in representation_variants():
            artifact = transform(query(lines), budget)
            self.assertIn(b'(define-fun d0 () Bool (not ', artifact.smt_bytes)
            self.assertLess(len(artifact.smt_bytes), 10000)

    def test_multiuse_byte_limit_and_inline_depth(self):
        lines = [f'(declare-const p{i} Bool)' for i in range(20)]
        lines += ['(define-fun n () Bool (and ' + ' '.join(f'p{i}' for i in range(20)) + '))',
                  '(define-fun a () Bool (= n p0))', '(define-fun b () Bool (= n p1))',
                  '(define-fun goal () Bool (and a b))']
        for variant, budget in representation_variants():
            artifact = transform(query(lines), budget)
            self.assertIn(b'(define-fun d0 () Bool (and ', artifact.smt_bytes)
            data = query(['(declare-const p Bool)', '(declare-const q Bool)',
                          '(define-fun n () Bool (not p))', '(define-fun a () Bool (or n q))',
                          '(define-fun b () Bool (= n q))', '(define-fun goal () Bool (and a b))'])
            artifact = transform(data, replace(budget, inline_depth=1))
            self.assertGreaterEqual(artifact.stats['output_definitions'], 2)
            for p, q in ((False, True), (True, True), (False, False)):
                names = {s.old: s.new for s in artifact.free_symbols}
                self.assertEqual(evaluate(artifact.smt_bytes, {names['p']: p, names['q']: q}),
                                 ((not p) or q) and ((not p) == q))

    def test_multitype_text_inactive_and_total_int_operations(self):
        lines = ['(declare-const b Bool)', '(declare-const x Int)', '(declare-const y Int)',
                 '(declare-const literalA Text)', '(declare-const literalB Text)',
                 '(declare-const inactive Text)', '(define-fun a () Int (- x y))',
                 '(define-fun c () Bool (< a y))', '(define-fun d () Bool (= literalA literalB))',
                 '(define-fun goal () Bool (ite b c d))']
        for variant, budget in representation_variants():
            artifact = transform(query(lines), budget)
            self.assertEqual(len(artifact.free_symbols), 6)
            names = {s.old: s.new for s in artifact.free_symbols}
            for b in (False, True):
                for x, y in ((-10**40, 1), (0, 0), (10**40, -4)):
                    for text in ('A', 'B'):
                        assignment = {'b': b, 'x': x, 'y': y, 'literalA': 'A',
                                      'literalB': text, 'inactive': 'unused'}
                        self.assertEqual(evaluate(artifact.smt_bytes,
                                                  {names[k]: v for k, v in assignment.items()}),
                                         x-y < y if b else text == 'A')

    def test_representations_have_no_deep_expansion_or_recursion(self):
        lines = ['(declare-const x Int)', '(define-fun one () Int 1)']
        previous = 'x'
        for index in range(6000):
            name = f'n{index}'
            lines.append(f'(define-fun {name} () Int (+ {previous} one))')
            previous = name
        lines.append(f'(define-fun goal () Bool (> {previous} x))')
        data = query(lines)
        for variant, budget in representation_variants():
            artifact = transform(data, budget)
            self.assertLess(len(artifact.smt_bytes), 300000)
            self.assertLess(max(len(line) for line in artifact.smt_bytes.splitlines()), 200)


if __name__ == '__main__':
    unittest.main()
