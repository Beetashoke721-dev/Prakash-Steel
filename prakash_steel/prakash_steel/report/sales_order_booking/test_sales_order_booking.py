# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for sales_order_booking report — no DB required."""

import unittest
from datetime import date
from unittest.mock import patch

from prakash_steel.prakash_steel.report.sales_order_booking import sales_order_booking as mod

MOD = "prakash_steel.prakash_steel.report.sales_order_booking.sales_order_booking"


class TestGetColumns(unittest.TestCase):
    def test_column_order(self):
        expected = [
            "date", "customer", "customer_group_name", "item_code", "description",
            "qty", "rate", "payment_terms_template", "lead_time", "special_condition",
            "status", "sales_order", "delivered_qty", "loading_and_cutting", "delivery_date",
        ]
        self.assertEqual([c["fieldname"] for c in mod.get_columns()], expected)

    def test_links_and_types(self):
        col_map = {c["fieldname"]: c for c in mod.get_columns()}
        self.assertEqual(col_map["sales_order"]["options"], "Sales Order")
        self.assertEqual(col_map["item_code"]["options"], "Item")
        self.assertEqual(col_map["customer"]["options"], "Customer")
        self.assertEqual(col_map["payment_terms_template"]["options"], "Payment Terms Template")
        self.assertEqual(col_map["rate"]["fieldtype"], "Currency")
        for f in ("qty", "delivered_qty", "lead_time"):
            self.assertEqual(col_map[f]["fieldtype"], "Int")
        for f in ("date", "delivery_date"):
            self.assertEqual(col_map[f]["fieldtype"], "Date")


class TestExecute(unittest.TestCase):
    def test_no_filters_returns_empty(self):
        self.assertEqual(mod.execute(None), ([], []))
        self.assertEqual(mod.execute({}), ([], []))

    @patch(MOD + ".frappe")
    def test_returns_columns_and_data(self, mock_frappe):
        mock_frappe.db.sql.return_value = []
        cols, data = mod.execute({"from_date": "2025-04-01", "to_date": "2025-04-30"})
        self.assertEqual(len(cols), 15)
        self.assertEqual(data, [])


class TestValidateFilters(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_to_date_before_from_date_throws(self, mock_frappe):
        mod.validate_filters({"from_date": "2025-04-10", "to_date": "2025-04-01"})
        mock_frappe.throw.assert_called_once()

    @patch(MOD + ".frappe")
    def test_valid_range_does_not_throw(self, mock_frappe):
        mod.validate_filters({"from_date": "2025-04-01", "to_date": "2025-04-10"})
        mock_frappe.throw.assert_not_called()


class TestGetConditions(unittest.TestCase):
    def test_no_filters_gives_empty_string(self):
        self.assertEqual(mod.get_conditions({}), "")

    def test_date_range_needs_both_dates(self):
        self.assertEqual(mod.get_conditions({"from_date": "2025-04-01"}), "")
        self.assertIn(
            "so.transaction_date between %(from_date)s and %(to_date)s",
            mod.get_conditions({"from_date": "2025-04-01", "to_date": "2025-04-30"}),
        )

    def test_optional_filters_appended(self):
        cases = {
            "company": "so.company = %(company)s",
            "sales_order": "so.name in %(sales_order)s",
            "status": "so.status in %(status)s",
            "customer": "so.customer = %(customer)s",
            "item_code": "soi.item_code = %(item_code)s",
        }
        for key, clause in cases.items():
            with self.subTest(filter=key):
                self.assertIn(clause, mod.get_conditions({key: "x"}))


class TestGetData(unittest.TestCase):
    def _query(self, mock_frappe, conditions="", filters=None):
        mock_frappe.db.sql.return_value = []
        mod.get_data(conditions, filters or {})
        return mock_frappe.db.sql.call_args[0][0]

    @patch(MOD + ".frappe")
    def test_mandatory_conditions(self, mock_frappe):
        query = self._query(mock_frappe)
        self.assertIn("so.docstatus = 1", query)
        self.assertIn("so.status not in ('Stopped', 'On Hold')", query)
        self.assertIn("IFNULL(soi.custom_closed, 0) = 0", query)

    @patch(MOD + ".frappe")
    def test_conditions_injected_and_filters_passed(self, mock_frappe):
        filters = {"company": "X"}
        query = self._query(mock_frappe, " and so.company = %(company)s", filters)
        self.assertIn("and so.company = %(company)s", query)
        self.assertEqual(mock_frappe.db.sql.call_args[0][1], filters)

    @patch(MOD + ".frappe")
    def test_qty_cast_to_int_and_lead_time_computed(self, mock_frappe):
        mock_frappe.db.sql.return_value = [
            {"qty": 10.0, "delivered_qty": 4.0, "date": date(2025, 4, 1), "delivery_date": date(2025, 4, 8)}
        ]
        row = mod.get_data("", {})[0]
        self.assertEqual(row["qty"], 10)
        self.assertEqual(row["delivered_qty"], 4)
        self.assertEqual(row["lead_time"], 7)

    @patch(MOD + ".frappe")
    def test_lead_time_none_without_dates(self, mock_frappe):
        mock_frappe.db.sql.return_value = [{"qty": None, "delivered_qty": None}]
        row = mod.get_data("", {})[0]
        self.assertEqual(row["qty"], 0)
        self.assertEqual(row["delivered_qty"], 0)
        self.assertIsNone(row["lead_time"])


if __name__ == "__main__":
    unittest.main()
