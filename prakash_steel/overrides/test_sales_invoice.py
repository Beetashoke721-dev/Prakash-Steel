# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for overrides/sales_invoice.py — no DB required.

Focuses on pure-logic methods that can be tested without ERPNext's
document lifecycle (no insert/submit/cancel, no DB).
"""

import unittest
from unittest.mock import MagicMock, patch


def _make_si_instance(**kwargs):
    """Build a minimal CustomSalesInvoice-like object without calling __init__."""
    from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
    obj = object.__new__(CustomSalesInvoice)
    for k, v in kwargs.items():
        setattr(obj, k, v)
    return obj


def _make_item(sales_order=None, so_detail=None):
    item = MagicMock()
    item.sales_order = sales_order
    item.get = lambda k, d=None: {
        "sales_order": sales_order,
        "so_detail": so_detail,
    }.get(k, d)
    return item


# ─────────────────────────────────────────────────────────────────────────────
# _extract_sales_order_serial  (static method — pure string logic)
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractSalesOrderSerial(unittest.TestCase):

    def _run(self, so_name):
        from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
        return CustomSalesInvoice._extract_sales_order_serial(so_name)

    def test_standard_format(self):
        # SO/25-26/01514 → 01514
        self.assertEqual(self._run("SO/25-26/01514"), "01514")

    def test_year_range_at_end(self):
        # SO/01007/25-26 → 01007
        self.assertEqual(self._run("SO/01007/25-26"), "01007")

    def test_hyphen_separated(self):
        # SO-0001/2025 → 0001 (4-digit year skipped)
        self.assertEqual(self._run("SO-0001/2025"), "0001")

    def test_leading_zeros_preserved(self):
        self.assertEqual(self._run("SO/25-26/00042"), "00042")

    def test_none_returns_none(self):
        self.assertIsNone(self._run(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(self._run(""))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(self._run("   "))

    def test_no_numeric_token_returns_none(self):
        self.assertIsNone(self._run("SO/ABC/XYZ"))

    def test_only_year_range_returns_none(self):
        # All tokens are 4-digit years or 2-digit year ranges → none qualify
        self.assertIsNone(self._run("SO/25-26"))

    def test_short_serial(self):
        self.assertEqual(self._run("SO/25-26/5"), "5")


# ─────────────────────────────────────────────────────────────────────────────
# _update_gross_amount_on_items
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateGrossAmountOnItems(unittest.TestCase):

    def _make_gst_item(self, taxable_value=None, net_amount=None, amount=None,
                       igst_amount=0, cgst_amount=0, sgst_amount=0):
        item = MagicMock()
        item.custom_gross_amount = None
        item.get = lambda k, d=None: {
            "taxable_value": taxable_value,
            "net_amount": net_amount,
            "amount": amount,
            "igst_amount": igst_amount,
            "cgst_amount": cgst_amount,
            "sgst_amount": sgst_amount,
        }.get(k, d)
        return item

    def _make_si(self, item):
        si = _make_si_instance()
        si.items = [item]  # guard `getattr(self, "items", None)` must be truthy
        si.get = lambda k, d=None: [item] if k == "items" else d
        return si

    def test_igst_used_when_present(self):
        from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
        item = self._make_gst_item(taxable_value=1000, igst_amount=180, cgst_amount=90, sgst_amount=90)
        CustomSalesInvoice._update_gross_amount_on_items(self._make_si(item))
        self.assertAlmostEqual(item.custom_gross_amount, 1180.0)

    def test_cgst_sgst_used_when_no_igst(self):
        from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
        item = self._make_gst_item(taxable_value=1000, igst_amount=0, cgst_amount=90, sgst_amount=90)
        CustomSalesInvoice._update_gross_amount_on_items(self._make_si(item))
        self.assertAlmostEqual(item.custom_gross_amount, 1180.0)

    def test_falls_back_to_net_amount(self):
        from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
        item = self._make_gst_item(taxable_value=None, net_amount=800, igst_amount=0)
        CustomSalesInvoice._update_gross_amount_on_items(self._make_si(item))
        self.assertAlmostEqual(item.custom_gross_amount, 800.0)

    def test_no_items_does_not_raise(self):
        from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
        si = _make_si_instance()
        si.items = None
        si.get = lambda k, d=None: None if k == "items" else d
        CustomSalesInvoice._update_gross_amount_on_items(si)  # should not raise


# ─────────────────────────────────────────────────────────────────────────────
# _get_ordered_sales_order_references  &  _build_other_references
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildOtherReferences(unittest.TestCase):

    def _make_si(self, items):
        si = _make_si_instance()
        si.get = lambda k, d=None: items if k == "items" else d
        return si

    def test_single_so_extracts_serial(self):
        from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
        si = self._make_si([_make_item(sales_order="SO/25-26/00100")])
        result = CustomSalesInvoice._build_other_references(si)
        self.assertEqual(result, "00100")

    def test_deduplicates_same_so(self):
        from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
        si = self._make_si([
            _make_item(sales_order="SO/25-26/00100"),
            _make_item(sales_order="SO/25-26/00100"),
        ])
        result = CustomSalesInvoice._build_other_references(si)
        self.assertEqual(result, "00100")

    def test_multiple_distinct_sos(self):
        from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
        si = self._make_si([
            _make_item(sales_order="SO/25-26/00100"),
            _make_item(sales_order="SO/25-26/00200"),
        ])
        result = CustomSalesInvoice._build_other_references(si)
        self.assertEqual(result, "00100, 00200")

    def test_no_items_returns_none(self):
        from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
        si = self._make_si([])
        result = CustomSalesInvoice._build_other_references(si)
        self.assertIsNone(result)

    def test_items_without_so_skipped(self):
        from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
        si = self._make_si([
            _make_item(sales_order=None),
            _make_item(sales_order="SO/25-26/00300"),
        ])
        result = CustomSalesInvoice._build_other_references(si)
        self.assertEqual(result, "00300")

    def test_order_preserved_by_first_occurrence(self):
        from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
        si = self._make_si([
            _make_item(sales_order="SO/25-26/00500"),
            _make_item(sales_order="SO/25-26/00100"),
            _make_item(sales_order="SO/25-26/00500"),  # duplicate of first
        ])
        result = CustomSalesInvoice._build_other_references(si)
        self.assertEqual(result, "00500, 00100")


# ─────────────────────────────────────────────────────────────────────────────
# before_cancel
# ─────────────────────────────────────────────────────────────────────────────

class TestBeforeCancel(unittest.TestCase):

    @patch("prakash_steel.overrides.sales_invoice.frappe")
    def test_throws_when_cancel_reason_missing(self, mock_frappe):
        from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
        si = _make_si_instance(custom_cancel_reason="")
        mock_frappe.throw.side_effect = Exception("reason required")
        with self.assertRaises(Exception):
            CustomSalesInvoice.before_cancel(si)
        mock_frappe.throw.assert_called_once()

    @patch("prakash_steel.overrides.sales_invoice.frappe")
    def test_throws_when_cancel_reason_whitespace(self, mock_frappe):
        from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
        si = _make_si_instance(custom_cancel_reason="   ")
        mock_frappe.throw.side_effect = Exception("reason required")
        with self.assertRaises(Exception):
            CustomSalesInvoice.before_cancel(si)

    @patch("prakash_steel.overrides.sales_invoice.frappe")
    def test_does_not_throw_when_reason_present(self, mock_frappe):
        from prakash_steel.overrides.sales_invoice import CustomSalesInvoice
        si = _make_si_instance(custom_cancel_reason="Rate Mistake")
        # before_cancel calls super().before_cancel() after the guard — that may raise
        # from ERPNext internals, but what we verify is that frappe.throw is NOT called
        try:
            CustomSalesInvoice.before_cancel(si)
        except Exception:
            pass
        mock_frappe.throw.assert_not_called()


if __name__ == "__main__":
    unittest.main()
