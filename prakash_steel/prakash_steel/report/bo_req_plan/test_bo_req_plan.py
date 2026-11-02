# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for bo_req_plan report — no DB required."""

import unittest
from unittest.mock import call, patch

MOD = "prakash_steel.prakash_steel.report.bo_req_plan.bo_req_plan"


class TestGetColumns(unittest.TestCase):
    def test_returns_expected_columns(self):
        from prakash_steel.prakash_steel.report.bo_req_plan.bo_req_plan import get_columns

        fieldnames = [c["fieldname"] for c in get_columns()]
        self.assertEqual(
            fieldnames,
            ["item_code", "sku_type", "on_hand_colour", "open_po", "or_with_moq_batch_size"],
        )

    def test_open_po_column_is_hidden(self):
        from prakash_steel.prakash_steel.report.bo_req_plan.bo_req_plan import get_columns

        open_po = next(c for c in get_columns() if c["fieldname"] == "open_po")
        self.assertEqual(open_po.get("hidden"), 1)


class TestGetData(unittest.TestCase):
    @patch(MOD + ".get_po_recomendation_data")
    def test_queries_both_bota_and_boto_sides(self, mock_get_data):
        """BOTA sits under buffer_flag=1 and BOTO under buffer_flag=0 in the
        underlying PSP report, so both must be queried separately."""
        from prakash_steel.prakash_steel.report.bo_req_plan.bo_req_plan import get_data

        mock_get_data.return_value = []
        get_data()
        self.assertEqual(
            mock_get_data.call_args_list,
            [
                call({"purchase": 1, "buffer_flag": 1, "sku_type": "BOTA"}),
                call({"purchase": 1, "buffer_flag": 0, "sku_type": "BOTO"}),
            ],
        )

    @patch(MOD + ".get_po_recomendation_data")
    def test_merges_rows_and_uses_priority_colour_for_boto(self, mock_get_data):
        from prakash_steel.prakash_steel.report.bo_req_plan.bo_req_plan import get_data

        mock_get_data.side_effect = [
            [{"item_code": "A", "sku_type": "BOTA", "on_hand_colour": "RED", "open_po": 5, "or_with_moq_batch_size": 100}],
            [{"item_code": "B", "sku_type": "BOTO", "on_hand_colour": None, "priority": "YELLOW", "open_po": 0, "or_with_moq_batch_size": 50}],
        ]
        self.assertEqual(
            get_data(),
            [
                {"item_code": "A", "sku_type": "BOTA", "on_hand_colour": "RED", "open_po": 5, "or_with_moq_batch_size": 100},
                {"item_code": "B", "sku_type": "BOTO", "on_hand_colour": "YELLOW", "open_po": 0, "or_with_moq_batch_size": 50},
            ],
        )

    @patch(MOD + ".get_po_recomendation_data")
    def test_bota_keeps_on_hand_colour_not_priority(self, mock_get_data):
        from prakash_steel.prakash_steel.report.bo_req_plan.bo_req_plan import get_data

        mock_get_data.side_effect = [
            [{"item_code": "A", "sku_type": "BOTA", "on_hand_colour": "GREEN", "priority": "BLACK", "or_with_moq_batch_size": 10}],
            [],
        ]
        self.assertEqual(get_data()[0]["on_hand_colour"], "GREEN")

    @patch(MOD + ".get_po_recomendation_data")
    def test_skips_zero_or_missing_recommendation(self, mock_get_data):
        from prakash_steel.prakash_steel.report.bo_req_plan.bo_req_plan import get_data

        mock_get_data.side_effect = [
            [{"item_code": "A", "sku_type": "BOTA", "or_with_moq_batch_size": 0}],
            [{"item_code": "B", "sku_type": "BOTO", "or_with_moq_batch_size": None}],
        ]
        self.assertEqual(get_data(), [])

    @patch(MOD + ".get_po_recomendation_data")
    def test_dedupes_repeated_item_code_rows(self, mock_get_data):
        from prakash_steel.prakash_steel.report.bo_req_plan.bo_req_plan import get_data

        mock_get_data.side_effect = [
            [
                {"item_code": "ITEM-1", "sku_type": "BOTA", "or_with_moq_batch_size": 100},
                {"item_code": "ITEM-1", "sku_type": "BOTA", "or_with_moq_batch_size": 100},
            ],
            [],
        ]
        self.assertEqual([row["item_code"] for row in get_data()], ["ITEM-1"])

    @patch(MOD + ".get_po_recomendation_data")
    def test_skips_rows_without_item_code(self, mock_get_data):
        from prakash_steel.prakash_steel.report.bo_req_plan.bo_req_plan import get_data

        mock_get_data.side_effect = [
            [{"item_code": None, "sku_type": "BOTA", "or_with_moq_batch_size": 100}],
            [],
        ]
        self.assertEqual(get_data(), [])


class TestExecute(unittest.TestCase):
    @patch(MOD + ".get_po_recomendation_data", return_value=[])
    def test_execute_returns_columns_and_data(self, _):
        from prakash_steel.prakash_steel.report.bo_req_plan.bo_req_plan import execute

        cols, data = execute()
        self.assertIsInstance(cols, list)
        self.assertEqual(data, [])


if __name__ == "__main__":
    unittest.main()
