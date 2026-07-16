# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for rolled_bar_batch_recommendation report — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation"


class TestCeil(unittest.TestCase):
    def test_rounds_up(self):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import _ceil
        self.assertEqual(_ceil(1.1), 2)
        self.assertEqual(_ceil(2.9), 3)
        self.assertEqual(_ceil(5.0), 5)

    def test_zero_returns_zero(self):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import _ceil
        self.assertEqual(_ceil(0), 0)

    def test_none_returns_zero(self):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import _ceil
        self.assertEqual(_ceil(None), 0)

    def test_integer_unchanged(self):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import _ceil
        self.assertEqual(_ceil(10), 10)

    def test_small_fraction(self):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import _ceil
        self.assertEqual(_ceil(0.001), 1)


class TestGetColumns(unittest.TestCase):
    def test_base_columns_no_prod_cols(self):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import get_columns
        cols = get_columns(0)
        fieldnames = [c["fieldname"] for c in cols]
        for f in ("item_code", "item_name", "item_type", "sku_type",
                  "sales_qty", "consumption_qty", "total", "projected_qty",
                  "batch_size", "production_qty", "production_count"):
            self.assertIn(f, fieldnames, f"Missing base column: {f}")

    def test_prod_columns_added(self):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import get_columns
        cols = get_columns(3)
        fieldnames = [c["fieldname"] for c in cols]
        self.assertIn("prod_1", fieldnames)
        self.assertIn("prod_2", fieldnames)
        self.assertIn("prod_3", fieldnames)

    def test_no_extra_prod_cols_beyond_max(self):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import get_columns
        cols = get_columns(2)
        fieldnames = [c["fieldname"] for c in cols]
        self.assertNotIn("prod_3", fieldnames)

    def test_prod_cols_are_int_type(self):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import get_columns
        col_map = {c["fieldname"]: c for c in get_columns(2)}
        self.assertEqual(col_map["prod_1"]["fieldtype"], "Int")
        self.assertEqual(col_map["prod_2"]["fieldtype"], "Int")

    def test_item_code_links_to_item(self):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import get_columns
        col_map = {c["fieldname"]: c for c in get_columns(0)}
        self.assertEqual(col_map["item_code"]["options"], "Item")


class TestExecute(unittest.TestCase):
    @patch(MOD + ".get_period_months")
    @patch(MOD + ".period_date_range")
    @patch(MOD + ".frappe")
    def test_returns_tuple_of_lists(self, mock_frappe, mock_range, mock_period):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import execute
        from datetime import date
        mock_period.return_value = [(2026, 1), (2026, 2)]
        mock_range.return_value = (date(2026, 1, 1), date(2026, 2, 28))
        mock_frappe.db.sql.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


class TestGetData(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_empty_item_rows_returns_empty(self, mock_frappe):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import get_data
        from datetime import date
        mock_frappe.db.sql.return_value = []
        data, max_cols = get_data({}, date(2026, 1, 1), date(2026, 3, 31))
        self.assertEqual(data, [])
        self.assertEqual(max_cols, 0)

    @patch(MOD + ".frappe")
    def test_sku_type_filter_applied_on_items(self, mock_frappe):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import get_data
        from datetime import date

        item_rows = [
            MagicMock(item_code="ITEM-A", item_name="Rod A", item_type="RB", sku_type="Standard"),
            MagicMock(item_code="ITEM-B", item_name="Rod B", item_type="RB", sku_type="Custom"),
        ]
        mock_frappe.db.sql.side_effect = [item_rows, [], [], []]
        mock_frappe.db.get_single_value.return_value = 0.3

        data, _ = get_data({"sku_type": "Custom"}, date(2026, 1, 1), date(2026, 3, 31))
        # Only ITEM-B should survive the SKU type filter
        self.assertTrue(all(r["sku_type"] == "Custom" for r in data))

    @patch(MOD + ".frappe")
    def test_projected_qty_is_130_percent_of_total(self, mock_frappe):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import get_data
        from datetime import date
        import math

        item_row = MagicMock(item_code="ITEM-A", item_name="Rod A", item_type="RB", sku_type="Standard")
        sales_row = MagicMock(item_code="ITEM-A", qty=100.0)

        mock_frappe.db.sql.side_effect = [
            [item_row],  # item master
            [sales_row],  # sales
            [],  # bright bar production
            [],  # finish weight
        ]
        # FOS = 0.3 in RB Batch Planning Settings -> projection factor = 1.3
        mock_frappe.db.get_single_value.return_value = 0.3

        data, _ = get_data({}, date(2026, 1, 1), date(2026, 3, 31))
        self.assertEqual(len(data), 1)
        # sales_qty=100, consumption=0, total=100, projected=ceil(100*1.3)=130
        self.assertEqual(data[0]["projected_qty"], 130)
        self.assertEqual(data[0]["total"], 100)

    @patch(MOD + ".frappe")
    def test_projected_qty_uses_custom_fos(self, mock_frappe):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import get_data
        from datetime import date

        item_row = MagicMock(item_code="ITEM-A", item_name="Rod A", item_type="RB", sku_type="Standard")
        sales_row = MagicMock(item_code="ITEM-A", qty=100.0)

        mock_frappe.db.sql.side_effect = [
            [item_row],
            [sales_row],
            [],
            [],
        ]
        # FOS = 0.5 -> projection factor = 1.5
        mock_frappe.db.get_single_value.return_value = 0.5

        data, _ = get_data({}, date(2026, 1, 1), date(2026, 3, 31))
        # sales_qty=100, consumption=0, total=100, projected=ceil(100*1.5)=150
        self.assertEqual(data[0]["projected_qty"], 150)

    @patch(MOD + ".frappe")
    def test_projected_qty_defaults_to_total_when_fos_unset(self, mock_frappe):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import get_data
        from datetime import date

        item_row = MagicMock(item_code="ITEM-A", item_name="Rod A", item_type="RB", sku_type="Standard")
        sales_row = MagicMock(item_code="ITEM-A", qty=100.0)

        mock_frappe.db.sql.side_effect = [
            [item_row],
            [sales_row],
            [],
            [],
        ]
        # FOS not configured -> factor = 1 + 0 = 1
        mock_frappe.db.get_single_value.return_value = None

        data, _ = get_data({}, date(2026, 1, 1), date(2026, 3, 31))
        self.assertEqual(data[0]["projected_qty"], 100)

    @patch(MOD + ".frappe")
    def test_batch_size_zero_when_no_production(self, mock_frappe):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import get_data
        from datetime import date

        item_row = MagicMock(item_code="ITEM-X", item_name="Rod X", item_type="RB", sku_type="Standard")
        mock_frappe.db.sql.side_effect = [
            [item_row],
            [],  # no sales
            [],  # no consumption
            [],  # no finish weight
        ]
        mock_frappe.db.get_single_value.return_value = 0.3

        data, _ = get_data({}, date(2026, 1, 1), date(2026, 3, 31))
        self.assertEqual(data[0]["batch_size"], 0)

    @patch(MOD + ".frappe")
    def test_max_prod_cols_capped_at_10(self, mock_frappe):
        from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import get_data, MAX_PROD_COLS
        from datetime import date

        item_row = MagicMock(item_code="ITEM-Y", item_name="Rod Y", item_type="RB", sku_type="Standard")
        fw_rows = [
            MagicMock(item_name="Rod Y", finish_weight=50.0, total_count=15, total_fw=750.0)
            for _ in range(MAX_PROD_COLS)
        ]

        mock_frappe.db.sql.side_effect = [
            [item_row],
            [],
            [],
            fw_rows,
        ]
        mock_frappe.db.get_single_value.return_value = 0.3

        _, max_cols = get_data({}, date(2026, 1, 1), date(2026, 3, 31))
        self.assertLessEqual(max_cols, MAX_PROD_COLS)


if __name__ == "__main__":
    unittest.main()
