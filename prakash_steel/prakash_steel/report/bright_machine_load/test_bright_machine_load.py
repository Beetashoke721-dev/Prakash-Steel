# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for bright_machine_load report — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.prakash_steel.report.bright_machine_load.bright_machine_load"


class TestBuildItemMaps(unittest.TestCase):
    def test_returns_correct_keys(self):
        from prakash_steel.prakash_steel.report.bright_machine_load.bright_machine_load import _build_item_maps
        items = [
            MagicMock(item_code="ITEM-A", buffer_flag="Buffer", item_type="BB", tog=100, moq=50, batch_size=0),
            MagicMock(item_code="ITEM-B", buffer_flag="Non-Buffer", item_type="RB", tog=0, moq=0, batch_size=25),
        ]
        item_codes, buffer_map, type_map, tog_map, moq_map, batch_map = _build_item_maps(items)
        self.assertIn("ITEM-A", item_codes)
        self.assertIn("ITEM-B", item_codes)
        self.assertEqual(buffer_map["ITEM-A"], "Buffer")
        self.assertEqual(type_map["ITEM-B"], "RB")
        self.assertEqual(moq_map["ITEM-A"], 50.0)
        self.assertEqual(batch_map["ITEM-B"], 25.0)

    def test_empty_items(self):
        from prakash_steel.prakash_steel.report.bright_machine_load.bright_machine_load import _build_item_maps
        result = _build_item_maps([])
        item_codes = result[0]
        self.assertEqual(len(item_codes), 0)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    @patch(MOD + ".require_any_permission")
    def test_returns_tuple(self, mock_perm, mock_frappe):
        from prakash_steel.prakash_steel.report.bright_machine_load.bright_machine_load import execute
        mock_frappe.db.sql.return_value = []
        mock_frappe.db.get_all.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


class TestNonBufferNetProdLoad(unittest.TestCase):
	"""Non-buffer (MTO) Net Order Rec must use all open SO (as bright_plan does),
	not just SO due till today — a future-dated SO must still create Prod Hrs."""

	def _run(self, buffer_flag, tog=0):
		from frappe import _dict

		from prakash_steel.prakash_steel.report.bright_machine_load import bright_machine_load as bml

		machine = _dict(machine_group_name="M1", no_of_machines=1, oee=80, runtime=12)
		machine_rows = [_dict(item_code="ITEM-A", machine_group_name="M1", mt_per_hour_production=500)]
		bb_items = [_dict(item_code="ITEM-A", buffer_flag=buffer_flag, item_type="BB", tog=tog, moq=0, batch_size=0)]

		with patch.object(bml, "frappe") as mock_frappe, \
			patch.object(bml, "get_planning_stock_map", return_value={"ITEM-A": 120}), \
			patch.object(bml, "get_wip_map", return_value={"ITEM-A": 1540}), \
			patch.object(bml, "get_mrq_map", return_value={}), \
			patch.object(bml, "get_qualified_demand_map", return_value=({}, {})), \
			patch.object(bml, "calculate_spike_map", return_value={}), \
			patch.object(bml, "get_sales_order_qty_map", return_value={"ITEM-A": 111340}):
			mock_frappe.get_all.side_effect = [[machine], []]  # Bright Machine, Spike Master
			mock_frappe.db.sql.side_effect = [machine_rows, bb_items]
			return bml.get_data()

	def test_mto_future_so_counts_in_net_prod_load(self):
		row = self._run("Non-Buffer")[0]
		# (111340 - 120 - 1540) / 500 = 219.36 h ; / 9.6 h effective / 1 machine = 22.8499.. (float)
		self.assertEqual(row["net_prod_load"], 22.8)
		# (111340 - 120) / 500 = 222.44 h ; / 9.6 = 23.17
		self.assertEqual(row["net_order_load"], 23.2)

	def test_buffer_without_qualified_demand_unchanged(self):
		row = self._run("Buffer", tog=0)[0]
		self.assertEqual(row["net_prod_load"], 0)
		self.assertEqual(row["net_order_load"], 0)



class TestBufferOpenSoBeforeSpikeThreshold(unittest.TestCase):
	"""Buffer Open SO (and so Order Hrs) uses qualified demand *before* the spike
	threshold, same as PO Recommendation / Manual Bright Plan. Net Order Rec (Prod
	Hrs) and the Qualified Demand column still use the thresholded value.

	TOG 12000, spike threshold 50% -> threshold qty 6000. Kg/hr 500, effective
	runtime 12h x 80% OEE = 9.6h, 1 machine, no stock / WIP / MRQ.
	"""

	def setUp(self):
		from frappe import _dict

		self.machine = _dict(machine_group_name="M1", no_of_machines=1, oee=80, runtime=12)
		self.bb_items = [_dict(item_code="ITEM-A", buffer_flag="Buffer", item_type="BB", tog=12000, moq=0, batch_size=0)]
		self.spike_master = [_dict(item_type="BB", demand_horizon=90, spike_threshold=50)]

	def _patches(self, bml, till_today):
		return (
			patch.object(bml, "get_planning_stock_map", return_value={}),
			patch.object(bml, "get_wip_map", return_value={}),
			patch.object(bml, "get_mrq_map", return_value={}),
			patch.object(bml, "get_qualified_demand_map", return_value=({"ITEM-A": till_today}, {})),
			patch.object(bml, "calculate_spike_map", return_value={}),
			patch.object(bml, "get_sales_order_qty_map", return_value={"ITEM-A": 99999}),
		)

	def _run_data(self, till_today):
		from frappe import _dict

		from prakash_steel.prakash_steel.report.bright_machine_load import bright_machine_load as bml

		machine_rows = [_dict(item_code="ITEM-A", machine_group_name="M1", mt_per_hour_production=500)]
		p1, p2, p3, p4, p5, p6 = self._patches(bml, till_today)
		with patch.object(bml, "frappe") as mock_frappe, p1, p2, p3, p4, p5, p6:
			mock_frappe.get_all.side_effect = [[self.machine], self.spike_master]
			mock_frappe.db.sql.side_effect = [machine_rows, self.bb_items]
			return bml.get_data()[0]

	def _run_breakdown(self, till_today):
		from frappe import _dict

		from prakash_steel.prakash_steel.report.bright_machine_load import bright_machine_load as bml

		machine_rows = [_dict(item_code="ITEM-A", mt_per_hour_production=500)]
		p1, p2, p3, p4, p5, p6 = self._patches(bml, till_today)
		with patch.object(bml, "frappe") as mock_frappe, patch.object(bml, "require_any_permission"), \
			p1, p2, p3, p4, p5, p6:
			mock_frappe.db.get_value.return_value = self.machine
			mock_frappe.get_all.return_value = self.spike_master
			mock_frappe.db.sql.side_effect = [machine_rows, self.bb_items]
			return bml.get_machine_breakdown("M1")

	def test_breakdown_below_threshold_shows_raw_open_so(self):
		row = self._run_breakdown(till_today=4800)["items"][0]
		self.assertEqual(row["open_so"], 4800)  # raw — was 0 when the threshold applied here
		self.assertEqual(row["qualified_demand"], 0)  # 4800 < 6000 -> thresholded
		self.assertEqual(row["net_order_rec"], 12000)  # TOG + thresholded QD
		self.assertEqual(row["order_req"], 4800)
		self.assertEqual(row["order_hours"], 9.6)  # 4800 / 500
		self.assertEqual(row["prod_hours"], 24)  # 12000 / 500

	def test_breakdown_above_threshold_unchanged(self):
		row = self._run_breakdown(till_today=7000)["items"][0]
		self.assertEqual(row["open_so"], 7000)
		self.assertEqual(row["qualified_demand"], 7000)
		self.assertEqual(row["net_order_rec"], 19000)

	def test_machine_load_below_threshold_counts_order_hours(self):
		row = self._run_data(till_today=4800)
		self.assertEqual(row["net_order_load"], 1.0)  # 9.6h / 9.6h — was 0
		self.assertEqual(row["net_prod_load"], 2.5)  # 24h / 9.6h, threshold still applies



if __name__ == "__main__":
    unittest.main()
