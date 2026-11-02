# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for the Actual Throughput report's Rate / TVC logic — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

import frappe

from prakash_steel.prakash_steel.report.actual_throughput import actual_throughput as MOD


def _breakdown(rate, traced_percent, rbs=(), rms=()):
	return frappe._dict(rate=rate, traced_percent=traced_percent, rbs=list(rbs), rms=list(rms))


def _lineage(results: dict):
	lineage = MagicMock()
	lineage.get_breakdown.side_effect = results.get
	return lineage


class TestSetActualRateColumns(unittest.TestCase):
	@patch.object(MOD, "load_stock_lineage")
	def test_dn_linked_row_uses_traced_end_material_rate(self, mock_load):
		mock_load.return_value = _lineage({"DN-1": _breakdown(38.5, 100.0)})
		row = {
			"item_type": "BB",
			"dn_detail": "DN-1",
			"si_detail": "SI-1",
			"update_stock": 0,
			"rate": 50.0,
			"purchase_month_taken": "6-26",
		}

		MOD.set_actual_rate_columns([row], "2026-09-30")

		self.assertEqual(row["rate"], 38.5)
		self.assertEqual(row["rate_source"], "Actual")
		self.assertEqual(row["traced_percent"], 100.0)
		self.assertIsNone(row["purchase_month_taken"])
		self.assertNotIn("dn_detail", row)
		self.assertNotIn("si_detail", row)
		self.assertNotIn("update_stock", row)

	@patch.object(MOD, "load_stock_lineage")
	def test_update_stock_invoice_uses_its_own_line(self, mock_load):
		mock_load.return_value = _lineage({"SI-1": _breakdown(40.0, 100.0)})
		row = {"item_type": "RB", "si_detail": "SI-1", "dn_detail": None, "update_stock": 1}

		MOD.set_actual_rate_columns([row], "2026-09-30")

		self.assertEqual(row["rate"], 40.0)

	@patch.object(MOD, "load_stock_lineage")
	def test_partly_traced_row_is_partial(self, mock_load):
		mock_load.return_value = _lineage({"DN-1": _breakdown(38.5, 60.0)})
		row = {"item_type": "BB", "dn_detail": "DN-1", "update_stock": 0, "rate": 50.0}

		MOD.set_actual_rate_columns([row], "2026-09-30")

		self.assertEqual(row["rate"], 38.5)
		self.assertEqual(row["rate_source"], "Partial")
		self.assertEqual(row["traced_percent"], 60.0)

	@patch.object(MOD, "load_stock_lineage")
	def test_untraceable_row_keeps_estimate(self, mock_load):
		mock_load.return_value = _lineage({})
		row = {"item_type": "BB", "dn_detail": "DN-1", "update_stock": 0, "rate": 50.0, "purchase_month_taken": "6-26"}

		MOD.set_actual_rate_columns([row], "2026-09-30")

		self.assertEqual(row["rate"], 50.0)
		self.assertEqual(row["rate_source"], "Estimated")
		self.assertIsNone(row["traced_percent"])
		self.assertEqual(row["purchase_month_taken"], "6-26")

	@patch.object(MOD, "load_stock_lineage")
	def test_no_linked_rows_skips_loading_ledger(self, mock_load):
		row = {"item_type": "Traded", "dn_detail": None, "update_stock": 0, "rate": None}

		MOD.set_actual_rate_columns([row], "2026-09-30")

		mock_load.assert_not_called()
		self.assertIsNone(row["rate_source"])

	@patch.object(MOD, "load_stock_lineage")
	def test_jw_category_never_gets_actual_rate(self, mock_load):
		row = {"item_type": "RB", "category_name": "JW", "si_detail": "SI-1", "update_stock": 1, "rate": None}

		MOD.set_actual_rate_columns([row], "2026-09-30")

		mock_load.assert_not_called()
		self.assertIsNone(row["rate"])

	@patch.object(MOD, "load_stock_lineage")
	def test_breakdown_flattens_rms_under_their_rb(self, mock_load):
		mock_load.return_value = _lineage(
			{
				"DN-1": _breakdown(
					39.6,
					100.0,
					rbs=[
						frappe._dict(rb="RB B", qty=1800.0, rate=None, rms=[("RM F", 1000.0, 40.0), ("RM E", 800.0, 38.0)]),
						frappe._dict(rb="RB C", qty=1200.0, rate=None, rms=[("RM G", 1200.0, 42.0)]),
					],
				)
			}
		)
		row = {"item_type": "BB", "item_code": "A", "dn_detail": "DN-1", "update_stock": 0}

		MOD.set_actual_rate_columns([row], "2026-09-30")

		self.assertEqual((row["rb_1"], row["rb_1_qty"], row["rb_2"], row["rb_2_qty"]), ("RB B", 1800.0, "RB C", 1200.0))
		self.assertEqual((row["rb_1_rm_2"], row["rb_1_rm_2_qty"], row["rb_1_rm_2_rate"]), ("RM E", 800.0, 38.0))
		self.assertEqual((row["rb_2_rm_1"], row["rb_2_rm_1_qty"]), ("RM G", 1200.0))
		self.assertNotIn("rb_2_rm_2", row)
		self.assertEqual(row["rm_counts"], [2, 1])

	@patch.object(MOD, "load_stock_lineage")
	def test_sold_rm_gets_rate_but_no_breakdown_columns(self, mock_load):
		mock_load.return_value = _lineage(
			{"SI-1": _breakdown(38.5, 100.0, rbs=[frappe._dict(rb=None, qty=10.0, rate=None, rms=[("RM", 10.0, 38.5)])])}
		)
		row = {"item_type": "RM", "si_detail": "SI-1", "update_stock": 1}

		MOD.set_actual_rate_columns([row], "2026-09-30")

		self.assertEqual(row["rate"], 38.5)
		self.assertNotIn("rb_1", row)


class TestBreakdownColumns(unittest.TestCase):
	def test_all_rb_sets_first_then_rm_sets_sized_per_rb_position(self):
		# RB 1 needs 4 RM slots (2nd row), RB 2 only ever has 1 - so no RB 2 RM 2..4.
		data = [{"rm_counts": [2, 1]}, {"rm_counts": [4]}, {}]

		columns = MOD.get_columns(MOD.get_rm_counts_per_rb(data))
		fieldnames = [c["fieldname"] for c in columns]

		start = fieldnames.index("traced_percent") + 1
		expected = ["rb_1", "rb_1_qty", "rb_1_rate", "rb_2", "rb_2_qty", "rb_2_rate"]
		for i, rm_count in ((1, 4), (2, 1)):
			for j in range(1, rm_count + 1):
				expected += [f"rb_{i}_rm_{j}", f"rb_{i}_rm_{j}_qty", f"rb_{i}_rm_{j}_rate"]
		self.assertEqual(fieldnames[start : start + len(expected)], expected)
		self.assertEqual(fieldnames[start + len(expected)], "purchase_month_taken")

	def test_no_breakdown_no_extra_columns(self):
		self.assertEqual(len(MOD.get_columns([])), len(MOD.get_static_columns()))


class TestGetTvc(unittest.TestCase):
	def test_bb_scales_by_qty_per_unit(self):
		self.assertAlmostEqual(MOD.get_tvc("BB", 2080, 38.5, 1.09), 2080 * 38.5 * 1.09)

	def test_traded_is_quantity_times_rate(self):
		self.assertEqual(MOD.get_tvc("Traded", 10, 5.0, None), 50.0)

	def test_scrap_is_zero(self):
		self.assertEqual(MOD.get_tvc("Scrap", 10, 5.0, None), 0)

	def test_unknown_type_is_none(self):
		self.assertIsNone(MOD.get_tvc("Other", 10, 5.0, None))


if __name__ == "__main__":
	unittest.main()
