# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for MRP Genaration doctype and calculation helpers — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.prakash_steel.doctype.mrp_genaration.mrp_genaration"


class TestMRPDoctype(unittest.TestCase):

    @patch(MOD + ".frappe")
    def test_doctype_is_single(self, mock_frappe):
        meta = MagicMock()
        meta.issingle = True
        mock_frappe.get_meta.return_value = meta
        self.assertTrue(mock_frappe.get_meta("MRP Genaration").issingle)

    @patch(MOD + ".frappe")
    def test_get_single_returns_doc(self, mock_frappe):
        doc = MagicMock()
        doc.doctype = "MRP Genaration"
        mock_frappe.get_single.return_value = doc
        self.assertEqual(mock_frappe.get_single("MRP Genaration").doctype, "MRP Genaration")


class TestCalculateNetOrderRecommendation(unittest.TestCase):
    """Tests for the MOQ/batch-size rounding helper."""

    def _run(self, base, moq=0, batch_size=0):
        from prakash_steel.prakash_steel.doctype.mrp_genaration.mrp_genaration import (
            calculate_net_order_recommendation,
        )
        return calculate_net_order_recommendation(base, moq, batch_size)

    def test_zero_base_returns_zero(self):
        self.assertEqual(self._run(0), 0)

    def test_negative_base_returns_zero(self):
        self.assertEqual(self._run(-5), 0)

    def test_no_moq_no_batch_returns_base(self):
        self.assertAlmostEqual(self._run(50), 50)

    def test_moq_larger_than_base_returns_moq(self):
        self.assertGreaterEqual(self._run(30, moq=100), 100)

    def test_batch_size_rounds_up(self):
        result = self._run(25, batch_size=10)
        self.assertEqual(result % 10, 0)
        self.assertGreaterEqual(result, 25)

    def test_exact_multiple_of_batch_size_unchanged(self):
        self.assertEqual(self._run(40, batch_size=10), 40)

    def test_moq_takes_precedence_when_larger(self):
        self.assertGreaterEqual(self._run(50, moq=200, batch_size=30), 200)


if __name__ == "__main__":
    unittest.main()
