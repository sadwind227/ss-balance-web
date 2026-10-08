"""跨模块行为测试：判定依据、规则差异、见证正确性与长串构造。"""

from __future__ import annotations

import unittest

from engine.data import PublishedData
from engine.solve import generate, known_existence, validate_number
from engine.verify import InvalidEquation, verify_equation


class DataTests(unittest.TestCase):
    def test_published_snapshot(self):
        data = PublishedData()
        self.assertEqual(len(data.non_single), 19515)
        self.assertIn("9989858", data.strong)
        self.assertIn("222", data.weak)


class ValidationTests(unittest.TestCase):
    def test_input_boundaries(self):
        self.assertEqual(validate_number(" 1234 "), "1234")
        for invalid in ("", "00123", "-123", "1e10", "12 34", "1" * 257):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_number(invalid)

    def test_independent_equation_rules(self):
        self.assertEqual(verify_equation("1234", "12=3*4", "strict", False)["common_value"], "12")
        self.assertEqual(verify_equation("1433", "(-1)+4=3=3", "segment", True)["common_value"], "3")
        for number, expression, mode, multi in (
            ("1433", "(-1)+4=3=3", "strict", True),
            ("1433", "1+(-4)=3=3", "segment", True),
            ("1234", "12=3*5", "strict", False),
            ("1234", "12=3*4/0", "strict", False),
            ("1234", "12=3**4", "strict", False),
            ("1234", "1=2=3=4", "strict", False),
        ):
            with self.subTest(expression=expression), self.assertRaises(InvalidEquation):
                verify_equation(number, expression, mode, multi)


class BalanceTests(unittest.TestCase):
    def collect(self, number, mode="segment", multiple=False, target=5):
        records = []
        reason = generate(number, mode, multiple, target, records.append)
        for record in records:
            verified = verify_equation(number, record["expression"], mode, multiple)
            self.assertEqual(record, verified)
        self.assertEqual(len(records), len({r["expression"] for r in records}))
        return reason, records

    def test_known_boundaries(self):
        self.assertEqual(known_existence("9989858", "segment", True)[0], "no")
        self.assertEqual(known_existence("9989859", "strict", False)[0], "yes")
        self.assertEqual(known_existence("222", "strict", True)[0], "unknown")
        self.assertEqual(known_existence("7", "segment", False)[0], "no")

    def test_short_examples_and_multiple_solutions(self):
        _, records = self.collect("1234", target=5)
        self.assertGreaterEqual(len(records), 2)
        self.assertIn("12=3 * 4", [r["expression"] for r in records])
        _, records = self.collect("1919810", target=3)
        self.assertGreaterEqual(len(records), 2)
        _, records = self.collect("222", multiple=True)
        self.assertEqual([r["expression"] for r in records], ["2=2=2"])
        _, records = self.collect("113", multiple=True)
        self.assertEqual(records, [])
        _, records = self.collect("9989858", multiple=True)
        self.assertEqual(records, [])
        _, records = self.collect("1433", mode="strict", multiple=True)
        self.assertEqual(records, [])

    def test_long_construction_strict(self):
        for number in ("1234567890123456", "8985898985898985", "1" + "0" * 63):
            with self.subTest(number=number):
                _, records = self.collect(number, mode="strict", target=1)
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["common_value"], "0")


if __name__ == "__main__":
    unittest.main()
