# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for billets_req_plan report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.billets_req_plan.billets_req_plan"


class TestGetColumns(unittest.TestCase):
    def test_returns_exactly_the_four_requested_columns(self):
        from prakash_steel.prakash_steel.report.billets_req_plan.billets_req_plan import get_columns

        cols = get_columns()
        self.assertIsInstance(cols, list)
        fieldnames = [c["fieldname"] for c in cols]
        self.assertEqual(
            fieldnames,
            ["item_code", "sku_type", "on_hand_colour", "or_with_moq_batch_size"],
        )


class TestGetData(unittest.TestCase):
    @patch(MOD + ".get_po_recomendation_data")
    def test_queries_purchase_buffer_pta_only(self, mock_get_data):
        from prakash_steel.prakash_steel.report.billets_req_plan.billets_req_plan import get_data

        mock_get_data.return_value = []
        get_data()
        mock_get_data.assert_called_once_with(
            {"purchase": 1, "buffer_flag": 1, "sku_type": "PTA"}
        )

    @patch(MOD + ".get_po_recomendation_data")
    def test_projects_only_the_four_fields(self, mock_get_data):
        from prakash_steel.prakash_steel.report.billets_req_plan.billets_req_plan import get_data

        mock_get_data.return_value = [
            {
                "item_code": "ITEM-1",
                "sku_type": "PTA",
                "on_hand_colour": "RED",
                "or_with_moq_batch_size": 100,
                "child_item_code": "CHILD-1",
                "calculation_breakdown": "noise",
            }
        ]
        data = get_data()
        self.assertEqual(
            data,
            [
                {
                    "item_code": "ITEM-1",
                    "sku_type": "PTA",
                    "on_hand_colour": "RED",
                    "or_with_moq_batch_size": 100,
                }
            ],
        )

    @patch(MOD + ".get_po_recomendation_data")
    def test_dedupes_repeated_item_code_rows(self, mock_get_data):
        """The underlying PSP report emits one row per BOM child item, so the
        same item_code can repeat; only the first occurrence should survive."""
        from prakash_steel.prakash_steel.report.billets_req_plan.billets_req_plan import get_data

        mock_get_data.return_value = [
            {"item_code": "ITEM-1", "sku_type": "PTA", "on_hand_colour": "RED", "or_with_moq_batch_size": 100},
            {"item_code": "ITEM-1", "sku_type": "PTA", "on_hand_colour": "RED", "or_with_moq_batch_size": 100},
            {"item_code": "ITEM-2", "sku_type": "PTA", "on_hand_colour": "GREEN", "or_with_moq_batch_size": 0},
        ]
        data = get_data()
        self.assertEqual([row["item_code"] for row in data], ["ITEM-1", "ITEM-2"])

    @patch(MOD + ".get_po_recomendation_data")
    def test_skips_rows_without_item_code(self, mock_get_data):
        from prakash_steel.prakash_steel.report.billets_req_plan.billets_req_plan import get_data

        mock_get_data.return_value = [
            {"item_code": None, "sku_type": "PTA", "on_hand_colour": "RED", "or_with_moq_batch_size": 100},
        ]
        data = get_data()
        self.assertEqual(data, [])


class TestExecute(unittest.TestCase):
    @patch(MOD + ".get_po_recomendation_data", return_value=[])
    def test_execute_returns_columns_and_data(self, _):
        from prakash_steel.prakash_steel.report.billets_req_plan.billets_req_plan import execute

        cols, data = execute()
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
