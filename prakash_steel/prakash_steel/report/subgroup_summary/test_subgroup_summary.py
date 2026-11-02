# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for subgroup_summary report — no DB required.

subgroup_summary is a thin aggregation over rolled_plan.get_data(), so these
tests mock that dependency directly rather than the whole frappe DB layer.
"""

import unittest
from unittest.mock import patch

from prakash_steel.prakash_steel.report.subgroup_summary.subgroup_summary import (
    execute,
    get_columns,
    get_data,
)

MOD = "prakash_steel.prakash_steel.report.subgroup_summary.subgroup_summary"


class TestGetColumns(unittest.TestCase):
    def test_returns_expected_fieldnames(self):
        cols = get_columns()
        self.assertEqual(
            [c["fieldname"] for c in cols],
            [
                "subgrp_shape",
                "sum_of_order_recommendation",
                "sum_of_net_qty",
                "actual_planned_qty_pct",
            ],
        )

    def test_every_column_has_a_label(self):
        for col in get_columns():
            self.assertIn("label", col)
            self.assertTrue(col["label"])


class TestGetData(unittest.TestCase):
    @patch(MOD + ".get_rolled_plan_data")
    def test_empty_rolled_plan_gives_empty_result(self, mock_get_rolled_plan_data):
        mock_get_rolled_plan_data.return_value = []
        self.assertEqual(get_data(), [])

    @patch(MOD + ".get_rolled_plan_data")
    def test_sums_net_order_recommendation_and_net_qty_within_a_group(self, mock_get_rolled_plan_data):
        mock_get_rolled_plan_data.return_value = [
            {
                "subgrp_shape": "SG1 Round",
                "net_order_recommendation": 100,
                "net_qty": 120,
                "actual_planned_qty_pct": 83.33,
            },
            {
                "subgrp_shape": "SG1 Round",
                "net_order_recommendation": 50,
                "net_qty": 60,
                "actual_planned_qty_pct": 83.33,
            },
        ]
        rows = get_data()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["subgrp_shape"], "SG1 Round")
        self.assertEqual(row["sum_of_order_recommendation"], 150)
        self.assertEqual(row["sum_of_net_qty"], 180)
        self.assertEqual(row["actual_planned_qty_pct"], 83.33)

    @patch(MOD + ".get_rolled_plan_data")
    def test_keeps_distinct_subgrp_shape_groups_separate(self, mock_get_rolled_plan_data):
        mock_get_rolled_plan_data.return_value = [
            {"subgrp_shape": "SG1 Round", "net_order_recommendation": 100, "net_qty": 120},
            {"subgrp_shape": "SG2 Hex", "net_order_recommendation": 10, "net_qty": 15},
        ]
        rows = get_data()
        by_group = {r["subgrp_shape"]: r for r in rows}
        self.assertEqual(set(by_group), {"SG1 Round", "SG2 Hex"})
        self.assertEqual(by_group["SG1 Round"]["sum_of_order_recommendation"], 100)
        self.assertEqual(by_group["SG2 Hex"]["sum_of_order_recommendation"], 10)

    @patch(MOD + ".get_rolled_plan_data")
    def test_preserves_first_seen_group_order(self, mock_get_rolled_plan_data):
        mock_get_rolled_plan_data.return_value = [
            {"subgrp_shape": "SG2 Hex", "net_order_recommendation": 1, "net_qty": 1},
            {"subgrp_shape": "SG1 Round", "net_order_recommendation": 1, "net_qty": 1},
            {"subgrp_shape": "SG2 Hex", "net_order_recommendation": 1, "net_qty": 1},
        ]
        rows = get_data()
        self.assertEqual([r["subgrp_shape"] for r in rows], ["SG2 Hex", "SG1 Round"])

    @patch(MOD + ".get_rolled_plan_data")
    def test_none_values_treated_as_zero(self, mock_get_rolled_plan_data):
        mock_get_rolled_plan_data.return_value = [
            {"subgrp_shape": "SG1 Round", "net_order_recommendation": None, "net_qty": None},
        ]
        rows = get_data()
        self.assertEqual(rows[0]["sum_of_order_recommendation"], 0)
        self.assertEqual(rows[0]["sum_of_net_qty"], 0)

    @patch(MOD + ".get_rolled_plan_data")
    def test_missing_subgrp_shape_falls_back_to_empty_string(self, mock_get_rolled_plan_data):
        mock_get_rolled_plan_data.return_value = [
            {"net_order_recommendation": 5, "net_qty": 5},
        ]
        rows = get_data()
        self.assertEqual(rows[0]["subgrp_shape"], "")

    @patch(MOD + ".get_rolled_plan_data")
    def test_forwards_filters_to_rolled_plan(self, mock_get_rolled_plan_data):
        mock_get_rolled_plan_data.return_value = []
        filters = {"company": "Prakash Steel"}
        get_data(filters)
        mock_get_rolled_plan_data.assert_called_once_with(filters)

    @patch(MOD + ".get_rolled_plan_data")
    def test_actual_planned_qty_pct_taken_from_first_row_of_group_not_recomputed(
        self, mock_get_rolled_plan_data
    ):
        # Second row in the group carries a different (stale/inconsistent) value —
        # subgroup_summary must not recompute this itself, only pass through what
        # rolled_plan already decided for the group.
        mock_get_rolled_plan_data.return_value = [
            {"subgrp_shape": "SG1 Round", "net_order_recommendation": 10, "net_qty": 10, "actual_planned_qty_pct": 42},
            {"subgrp_shape": "SG1 Round", "net_order_recommendation": 10, "net_qty": 10, "actual_planned_qty_pct": 999},
        ]
        rows = get_data()
        self.assertEqual(rows[0]["actual_planned_qty_pct"], 42)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".get_rolled_plan_data")
    def test_returns_columns_and_data_tuple(self, mock_get_rolled_plan_data):
        mock_get_rolled_plan_data.return_value = [
            {"subgrp_shape": "SG1 Round", "net_order_recommendation": 10, "net_qty": 10, "actual_planned_qty_pct": 100},
        ]
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)


if __name__ == "__main__":
    unittest.main()
