# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for overrides/payment_reconciliation.py — no DB required."""

import unittest
from unittest.mock import MagicMock, patch


def _entry(voucher_type, voucher_no, outstanding=1000.0, bill_no=None):
    return {
        "voucher_type": voucher_type,
        "voucher_no": voucher_no,
        "posting_date": "2026-01-15",
        "invoice_amount": 5000.0,
        "outstanding_amount": outstanding,
        "currency": "INR",
        "bill_no": bill_no,
    }


class TestAddInvoiceEntries(unittest.TestCase):

    @patch("prakash_steel.overrides.payment_reconciliation.frappe")
    def test_sets_bill_no_for_purchase_invoice(self, mock_frappe):
        from prakash_steel.overrides.payment_reconciliation import CustomPaymentReconciliation
        mock_frappe.db.get_all.return_value = [("PI-0001", "SUPP-INV-001")]

        pr = object.__new__(CustomPaymentReconciliation)
        appended = []

        def fake_append(table, data=None):
            row = MagicMock()
            row.custom_supplier_invoice_no = None
            if data:
                for k, v in data.items():
                    setattr(row, k, v)
            appended.append(row)
            return row

        pr.append = fake_append
        pr.set = MagicMock()

        entries = [_entry("Purchase Invoice", "PI-0001")]
        pr.add_invoice_entries(entries)

        self.assertEqual(len(appended), 1)
        self.assertEqual(appended[0].custom_supplier_invoice_no, "SUPP-INV-001")

    @patch("prakash_steel.overrides.payment_reconciliation.frappe")
    def test_bill_no_not_set_for_journal_entry(self, mock_frappe):
        from prakash_steel.overrides.payment_reconciliation import CustomPaymentReconciliation
        mock_frappe.db.get_all.return_value = []

        pr = object.__new__(CustomPaymentReconciliation)
        appended = []

        def fake_append(table, data=None):
            row = MagicMock()
            row.custom_supplier_invoice_no = None
            appended.append(row)
            return row

        pr.append = fake_append
        pr.set = MagicMock()

        entries = [_entry("Journal Entry", "JV-0001")]
        pr.add_invoice_entries(entries)

        self.assertEqual(len(appended), 1)
        self.assertIsNone(appended[0].custom_supplier_invoice_no)

    @patch("prakash_steel.overrides.payment_reconciliation.frappe")
    def test_bill_no_fetched_in_single_batch_query(self, mock_frappe):
        """All PI names should be fetched in one query, not per-row."""
        from prakash_steel.overrides.payment_reconciliation import CustomPaymentReconciliation
        mock_frappe.db.get_all.return_value = [
            ("PI-0001", "INV-A"),
            ("PI-0002", "INV-B"),
        ]

        pr = object.__new__(CustomPaymentReconciliation)
        pr.append = lambda t, d=None: MagicMock()
        pr.set = MagicMock()

        entries = [
            _entry("Purchase Invoice", "PI-0001"),
            _entry("Purchase Invoice", "PI-0002"),
        ]
        pr.add_invoice_entries(entries)
        mock_frappe.db.get_all.assert_called_once()

    @patch("prakash_steel.overrides.payment_reconciliation.frappe")
    def test_handles_empty_entries(self, mock_frappe):
        from prakash_steel.overrides.payment_reconciliation import CustomPaymentReconciliation
        pr = object.__new__(CustomPaymentReconciliation)
        pr.set = MagicMock()
        pr.append = MagicMock()
        pr.add_invoice_entries([])
        pr.set.assert_called_once_with("invoices", [])
        pr.append.assert_not_called()

    @patch("prakash_steel.overrides.payment_reconciliation.frappe")
    def test_mixed_entries_correct_bill_no_mapping(self, mock_frappe):
        from prakash_steel.overrides.payment_reconciliation import CustomPaymentReconciliation
        mock_frappe.db.get_all.return_value = [("PI-0001", "EXT-99")]

        pr = object.__new__(CustomPaymentReconciliation)
        appended = []

        def fake_append(table, data=None):
            row = MagicMock()
            row.custom_supplier_invoice_no = None
            appended.append(row)
            return row

        pr.append = fake_append
        pr.set = MagicMock()

        entries = [
            _entry("Journal Entry", "JV-0001"),
            _entry("Purchase Invoice", "PI-0001"),
        ]
        pr.add_invoice_entries(entries)

        self.assertIsNone(appended[0].custom_supplier_invoice_no)  # JV
        self.assertEqual(appended[1].custom_supplier_invoice_no, "EXT-99")  # PI


if __name__ == "__main__":
    unittest.main()
