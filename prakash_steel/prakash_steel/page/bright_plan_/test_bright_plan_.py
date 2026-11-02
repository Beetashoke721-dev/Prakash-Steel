# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for the Bright Plan page — no DB required."""

import unittest
from unittest.mock import patch

from frappe import _dict

from prakash_steel.prakash_steel.page.bright_plan_ import bright_plan_ as MOD


class TestBufferOpenSoBeforeSpikeThreshold(unittest.TestCase):
	"""Buffer Open SO (and so OP/CP) uses qualified demand *before* the spike
	threshold, same as PO Recommendation / Manual Bright Plan. The colour still
	uses the thresholded value.

	TOG 12000, spike threshold 50% -> threshold qty 6000. One pending
	Manufacture MR line of 1000, no stock / WIP / draft WO, no BOM.
	"""

	def _run(self, till_today, buffer_flag="Buffer", open_so=0):
		bb_items = [
			_dict(
				item_code="ITEM-A",
				item_name="Item A",
				buffer_flag=buffer_flag,
				item_type="BB",
				tog=12000,
				moq=0,
				batch_size=0,
			)
		]
		mr_lines = {"ITEM-A": [{"qty": 1000, "material_request": "MR-0001", "date": "2026-10-20"}]}
		spike_master = [_dict(item_type="BB", demand_horizon=90, spike_threshold=50)]

		with patch.object(MOD, "frappe") as mock_frappe, \
			patch.object(MOD, "_get_manufacture_mr_lines_map", return_value=mr_lines), \
			patch.object(MOD, "get_planning_stock_map", return_value={}), \
			patch.object(MOD, "get_wip_map", return_value={}), \
			patch.object(MOD, "_get_draft_wo_map", return_value={}), \
			patch.object(MOD, "get_open_po_map", return_value={}), \
			patch.object(MOD, "get_qualified_demand_map", return_value=({"ITEM-A": till_today}, {})), \
			patch.object(MOD, "calculate_spike_map", return_value={}), \
			patch.object(MOD, "get_sales_order_qty_map", return_value={"ITEM-A": open_so}), \
			patch.object(MOD, "get_open_so_map_for_priority", return_value={}), \
			patch.object(MOD, "_non_buffer_priority", return_value="Red"), \
			patch.object(MOD, "get_default_bom", return_value=None):
			mock_frappe.get_all.return_value = spike_master
			# bb_items, default machine rows, priority sequence, last-3-month sale
			mock_frappe.db.sql.side_effect = [bb_items, [], [], []]
			rows = MOD.get_data()

		self.assertEqual(len(rows), 1)
		return rows[0]

	def test_below_threshold_shows_raw_open_so(self):
		row = self._run(till_today=4800)
		self.assertEqual(row["open_so"], 4800)  # raw — was 0 when the threshold applied here
		self.assertEqual(row["op_cp"], "OP")  # 4800 open SO still uncovered — was CP
		self.assertEqual(row["on_hand_colour_priority"], "Black")
		self.assertEqual(row["priority_colour"], "MTAOPBLACK")
		self.assertEqual(row["or_with_moq_batch_size"], 1000)  # MR qty unaffected

	def test_above_threshold_unchanged(self):
		row = self._run(till_today=7000)
		self.assertEqual(row["open_so"], 7000)
		self.assertEqual(row["op_cp"], "OP")

	def test_non_buffer_uses_all_open_so(self):
		row = self._run(till_today=4800, buffer_flag="Non-Buffer", open_so=2500)
		self.assertEqual(row["open_so"], 2500)
		self.assertEqual(row["op_cp"], "")


if __name__ == "__main__":
	unittest.main()
