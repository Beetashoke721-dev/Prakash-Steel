# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for traded_req_plan report — no DB required."""

import unittest
from unittest.mock import call, patch

MOD = "prakash_steel.prakash_steel.report.traded_req_plan.traded_req_plan"


class TestGetColumns(unittest.TestCase):
    def test_returns_expected_columns(self):
        from prakash_steel.prakash_steel.report.traded_req_plan.traded_req_plan import get_columns

        fieldnames = [c["fieldname"] for c in get_columns()]
        self.assertEqual(
            fieldnames,
            ["item_code", "sku_type", "on_hand_colour", "open_po", "or_with_moq_batch_size"],
        )


class TestGetData(unittest.TestCase):
    @patch(MOD + ".get_po_recomendation_data")
    def test_queries_both_trmta_and_trmto_sides(self, mock_get_data):
        """TRMTA sits under buffer_flag=1 and TRMTO under buffer_flag=0 in the
        underlying PSP report, so both must be queried separately."""
        from prakash_steel.prakash_steel.report.traded_req_plan.traded_req_plan import get_data

        mock_get_data.return_value = []
        get_data()
        self.assertEqual(
            mock_get_data.call_args_list,
            [
                call({"purchase": 1, "buffer_flag": 1, "sku_type": "TRMTA"}),
                call({"purchase": 1, "buffer_flag": 0, "sku_type": "TRMTO"}),
            ],
        )

    @patch(MOD + ".get_po_recomendation_data")
    def test_merges_rows_and_uses_priority_colour_for_trmto(self, mock_get_data):
        from prakash_steel.prakash_steel.report.traded_req_plan.traded_req_plan import get_data

        mock_get_data.side_effect = [
            [{"item_code": "A", "sku_type": "TRMTA", "on_hand_colour": "RED", "open_po": 5, "or_with_moq_batch_size": 100}],
            [{"item_code": "B", "sku_type": "TRMTO", "on_hand_colour": None, "priority": "YELLOW", "open_po": 0, "or_with_moq_batch_size": 50}],
        ]
        self.assertEqual(
            get_data(),
            [
                {"item_code": "A", "sku_type": "TRMTA", "on_hand_colour": "RED", "open_po": 5, "or_with_moq_batch_size": 100},
                {"item_code": "B", "sku_type": "TRMTO", "on_hand_colour": "YELLOW", "open_po": 0, "or_with_moq_batch_size": 50},
            ],
        )

    @patch(MOD + ".get_po_recomendation_data")
    def test_skips_zero_recommendation_missing_item_and_duplicates(self, mock_get_data):
        from prakash_steel.prakash_steel.report.traded_req_plan.traded_req_plan import get_data

        mock_get_data.side_effect = [
            [
                {"item_code": "A", "sku_type": "TRMTA", "or_with_moq_batch_size": 10},
                {"item_code": "A", "sku_type": "TRMTA", "or_with_moq_batch_size": 10},
                {"item_code": None, "sku_type": "TRMTA", "or_with_moq_batch_size": 10},
            ],
            [{"item_code": "B", "sku_type": "TRMTO", "or_with_moq_batch_size": 0}],
        ]
        self.assertEqual([r["item_code"] for r in get_data()], ["A"])


class TestExecute(unittest.TestCase):
    @patch(MOD + ".get_po_recomendation_data", return_value=[])
    def test_execute_returns_columns_and_data(self, _):
        from prakash_steel.prakash_steel.report.traded_req_plan.traded_req_plan import execute

        cols, data = execute()
        self.assertIsInstance(cols, list)
        self.assertEqual(data, [])


if __name__ == "__main__":
    unittest.main()
