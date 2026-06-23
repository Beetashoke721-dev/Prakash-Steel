# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for utils/payment_entry.py — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.utils.payment_entry"


def _make_ref_row(doctype, name, custom_invoice_date=None):
    row = MagicMock()
    row.reference_doctype = doctype
    row.reference_name = name
    row.custom_invoice_date = custom_invoice_date
    return row


class TestSetInvoiceDateOnReferences(unittest.TestCase):

    @patch(MOD + ".frappe")
    def test_sets_invoice_date_for_sales_invoice(self, mock_frappe):
        from prakash_steel.utils.payment_entry import set_invoice_date_on_references
        mock_frappe.db.has_column.return_value = True
        mock_frappe.db.get_value.return_value = "2026-01-15"

        row = _make_ref_row("Sales Invoice", "SI-0001")
        doc = MagicMock()
        doc.get = lambda k, d=None: [row] if k == "references" else d

        set_invoice_date_on_references(doc)
        self.assertEqual(row.custom_invoice_date, "2026-01-15")

    @patch(MOD + ".frappe")
    def test_sets_invoice_date_for_purchase_invoice(self, mock_frappe):
        from prakash_steel.utils.payment_entry import set_invoice_date_on_references
        mock_frappe.db.has_column.return_value = True
        mock_frappe.db.get_value.return_value = "2026-02-20"

        row = _make_ref_row("Purchase Invoice", "PI-0001")
        doc = MagicMock()
        doc.get = lambda k, d=None: [row] if k == "references" else d

        set_invoice_date_on_references(doc)
        self.assertEqual(row.custom_invoice_date, "2026-02-20")

    @patch(MOD + ".frappe")
    def test_clears_date_for_non_invoice_doctype(self, mock_frappe):
        from prakash_steel.utils.payment_entry import set_invoice_date_on_references
        mock_frappe.db.has_column.return_value = True

        row = _make_ref_row("Journal Entry", "JV-0001")
        doc = MagicMock()
        doc.get = lambda k, d=None: [row] if k == "references" else d

        set_invoice_date_on_references(doc)
        self.assertIsNone(row.custom_invoice_date)

    @patch(MOD + ".frappe")
    def test_clears_date_when_missing_reference_name(self, mock_frappe):
        from prakash_steel.utils.payment_entry import set_invoice_date_on_references
        mock_frappe.db.has_column.return_value = True

        row = _make_ref_row("Sales Invoice", None)
        doc = MagicMock()
        doc.get = lambda k, d=None: [row] if k == "references" else d

        set_invoice_date_on_references(doc)
        self.assertIsNone(row.custom_invoice_date)

    @patch(MOD + ".frappe")
    def test_skips_when_column_missing(self, mock_frappe):
        from prakash_steel.utils.payment_entry import set_invoice_date_on_references
        mock_frappe.db.has_column.return_value = False

        row = _make_ref_row("Sales Invoice", "SI-0001")
        doc = MagicMock()
        doc.get = lambda k, d=None: [row] if k == "references" else d

        set_invoice_date_on_references(doc)
        mock_frappe.db.get_value.assert_not_called()

    @patch(MOD + ".frappe")
    def test_caches_lookup_for_same_invoice(self, mock_frappe):
        from prakash_steel.utils.payment_entry import set_invoice_date_on_references
        mock_frappe.db.has_column.return_value = True
        mock_frappe.db.get_value.return_value = "2026-01-15"

        row1 = _make_ref_row("Sales Invoice", "SI-0001")
        row2 = _make_ref_row("Sales Invoice", "SI-0001")  # same invoice
        doc = MagicMock()
        doc.get = lambda k, d=None: [row1, row2] if k == "references" else d

        set_invoice_date_on_references(doc)
        # DB should be hit only once due to caching
        mock_frappe.db.get_value.assert_called_once()
        self.assertEqual(row1.custom_invoice_date, "2026-01-15")
        self.assertEqual(row2.custom_invoice_date, "2026-01-15")

    @patch(MOD + ".frappe")
    def test_handles_empty_references(self, mock_frappe):
        from prakash_steel.utils.payment_entry import set_invoice_date_on_references
        mock_frappe.db.has_column.return_value = True
        doc = MagicMock()
        doc.get = lambda k, d=None: [] if k == "references" else d
        set_invoice_date_on_references(doc)
        mock_frappe.db.get_value.assert_not_called()


class TestSetSubmittedTime(unittest.TestCase):

    @patch(MOD + ".frappe")
    @patch(MOD + ".now_datetime", return_value="2026-01-15 10:00:00")
    def test_sets_submitted_time(self, mock_now, mock_frappe):
        from prakash_steel.utils.payment_entry import set_submitted_time
        mock_frappe.db.has_column.return_value = True
        doc = MagicMock()
        doc.get = lambda k, d=None: None if k == "custom_submitted_time" else d
        doc.doctype = "Payment Entry"
        set_submitted_time(doc)
        doc.db_set.assert_called_once_with(
            "custom_submitted_time", "2026-01-15 10:00:00", update_modified=False
        )

    @patch(MOD + ".frappe")
    @patch(MOD + ".now_datetime")
    def test_skips_if_already_set(self, mock_now, mock_frappe):
        from prakash_steel.utils.payment_entry import set_submitted_time
        doc = MagicMock()
        doc.get = lambda k, d=None: "2026-01-01 08:00:00" if k == "custom_submitted_time" else d
        set_submitted_time(doc)
        doc.db_set.assert_not_called()

    @patch(MOD + ".frappe")
    @patch(MOD + ".now_datetime")
    def test_skips_if_column_missing(self, mock_now, mock_frappe):
        from prakash_steel.utils.payment_entry import set_submitted_time
        mock_frappe.db.has_column.return_value = False
        doc = MagicMock()
        doc.get = lambda k, d=None: None
        doc.doctype = "Payment Entry"
        set_submitted_time(doc)
        doc.db_set.assert_not_called()


if __name__ == "__main__":
    unittest.main()
