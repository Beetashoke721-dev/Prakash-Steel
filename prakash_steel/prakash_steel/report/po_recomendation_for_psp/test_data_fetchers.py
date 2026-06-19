# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
Unit tests for data_fetchers.py — all frappe DB calls are mocked.
"""

import unittest
from unittest.mock import MagicMock, patch


MODULE = "prakash_steel.prakash_steel.report.po_recomendation_for_psp.data_fetchers"


# ---------------------------------------------------------------------------
# Helper: build a mock row with attributes
# ---------------------------------------------------------------------------


def _row(**kwargs):
	obj = MagicMock()
	for k, v in kwargs.items():
		setattr(obj, k, v)
	return obj


# ---------------------------------------------------------------------------
# get_stock_map
# ---------------------------------------------------------------------------


class TestGetStockMap(unittest.TestCase):
	def setUp(self):
		from prakash_steel.prakash_steel.report.po_recomendation_for_psp.data_fetchers import get_stock_map
		self._fn = get_stock_map

	def test_empty_item_codes_returns_empty(self):
		with patch(MODULE + ".frappe") as mf:
			result = self._fn([])
			mf.db.sql.assert_not_called()
		self.assertEqual(result, {})

	def test_maps_items_to_stock(self):
		rows = [_row(item_code="A", stock=100.0), _row(item_code="B", stock=50.0)]
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.return_value = rows
			result = self._fn(["A", "B"])
		self.assertEqual(result["A"], 100.0)
		self.assertEqual(result["B"], 50.0)

	def test_zero_stock_included(self):
		rows = [_row(item_code="A", stock=0.0)]
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.return_value = rows
			result = self._fn(["A"])
		self.assertEqual(result["A"], 0.0)

	def test_item_with_no_bin_row_absent_from_map(self):
		rows = [_row(item_code="A", stock=10.0)]
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.return_value = rows
			result = self._fn(["A", "MISSING"])
		self.assertNotIn("MISSING", result)

	def test_no_db_rows_returns_empty(self):
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.return_value = []
			result = self._fn(["A"])
		self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# get_sales_order_qty_map
# ---------------------------------------------------------------------------


class TestGetSalesOrderQtyMap(unittest.TestCase):
	def setUp(self):
		from prakash_steel.prakash_steel.report.po_recomendation_for_psp.data_fetchers import get_sales_order_qty_map
		self._fn = get_sales_order_qty_map

	def test_maps_items_to_so_qty(self):
		rows = [_row(item_code="ITEM-A", so_qty=200.0), _row(item_code="ITEM-B", so_qty=50.0)]
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.return_value = rows
			result = self._fn({})
		self.assertEqual(result["ITEM-A"], 200.0)
		self.assertEqual(result["ITEM-B"], 50.0)

	def test_empty_result_returns_empty_dict(self):
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.return_value = []
			result = self._fn({})
		self.assertEqual(result, {})

	def test_returns_dict(self):
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.return_value = []
			result = self._fn({})
		self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# get_qualified_demand_map
# ---------------------------------------------------------------------------


class TestGetQualifiedDemandMap(unittest.TestCase):
	def setUp(self):
		from prakash_steel.prakash_steel.report.po_recomendation_for_psp.data_fetchers import get_qualified_demand_map
		self._fn = get_qualified_demand_map

	def test_returns_two_element_tuple(self):
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".today", return_value="2026-01-01"):
			mf.db.sql.return_value = []
			result = self._fn()
		self.assertIsInstance(result, tuple)
		self.assertEqual(len(result), 2)

	def test_till_today_map_populated(self):
		rows = [_row(item_code="ITEM-A", so_qty=50.0)]
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".today", return_value="2026-01-01"):
			mf.db.sql.return_value = rows
			till_today_map, _ = self._fn()
		self.assertEqual(till_today_map["ITEM-A"], 50.0)

	def test_spike_map_all_zeros(self):
		rows = [_row(item_code="ITEM-A", so_qty=50.0), _row(item_code="ITEM-B", so_qty=20.0)]
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".today", return_value="2026-01-01"):
			mf.db.sql.return_value = rows
			_, spike_map = self._fn()
		self.assertEqual(spike_map["ITEM-A"], 0.0)
		self.assertEqual(spike_map["ITEM-B"], 0.0)

	def test_spike_map_keys_match_till_today_keys(self):
		rows = [_row(item_code="X", so_qty=10.0), _row(item_code="Y", so_qty=5.0)]
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".today", return_value="2026-01-01"):
			mf.db.sql.return_value = rows
			till_today_map, spike_map = self._fn()
		self.assertEqual(set(till_today_map.keys()), set(spike_map.keys()))

	def test_empty_result(self):
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".today", return_value="2026-01-01"):
			mf.db.sql.return_value = []
			till_today_map, spike_map = self._fn()
		self.assertEqual(till_today_map, {})
		self.assertEqual(spike_map, {})


# ---------------------------------------------------------------------------
# get_mrq_map
# ---------------------------------------------------------------------------


class TestGetMrqMap(unittest.TestCase):
	def setUp(self):
		from prakash_steel.prakash_steel.report.po_recomendation_for_psp.data_fetchers import get_mrq_map
		self._fn = get_mrq_map

	def test_mr_and_draft_wo_summed(self):
		mr_rows = [_row(item_code="ITEM-A", mrq_qty=20.0)]
		wo_rows = [_row(item_code="ITEM-A", wo_qty=10.0)]
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.side_effect = [mr_rows, wo_rows]
			result = self._fn()
		self.assertEqual(result["ITEM-A"], 30.0)

	def test_mr_only_when_no_draft_wo(self):
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.side_effect = [[_row(item_code="ITEM-B", mrq_qty=15.0)], []]
			result = self._fn()
		self.assertEqual(result["ITEM-B"], 15.0)

	def test_draft_wo_only_when_no_mr(self):
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.side_effect = [[], [_row(item_code="ITEM-C", wo_qty=25.0)]]
			result = self._fn()
		self.assertEqual(result["ITEM-C"], 25.0)

	def test_different_items_in_mr_and_wo(self):
		mr_rows = [_row(item_code="ITEM-A", mrq_qty=10.0)]
		wo_rows = [_row(item_code="ITEM-B", wo_qty=5.0)]
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.side_effect = [mr_rows, wo_rows]
			result = self._fn()
		self.assertEqual(result["ITEM-A"], 10.0)
		self.assertEqual(result["ITEM-B"], 5.0)

	def test_empty_returns_empty(self):
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.side_effect = [[], []]
			result = self._fn()
		self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# get_open_po_map
# ---------------------------------------------------------------------------


class TestGetOpenPoMap(unittest.TestCase):
	def setUp(self):
		from prakash_steel.prakash_steel.report.po_recomendation_for_psp.data_fetchers import get_open_po_map
		self._fn = get_open_po_map

	def test_calculates_open_qty(self):
		rows = [_row(item_code="ITEM-A", qty=100.0, received_qty=30.0)]
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.return_value = rows
			result = self._fn()
		self.assertEqual(result["ITEM-A"], 70.0)

	def test_accumulates_multiple_rows_same_item(self):
		rows = [
			_row(item_code="ITEM-A", qty=100.0, received_qty=30.0),
			_row(item_code="ITEM-A", qty=50.0, received_qty=10.0),
		]
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.return_value = rows
			result = self._fn()
		self.assertEqual(result["ITEM-A"], 110.0)  # 70 + 40

	def test_fully_received_gives_zero(self):
		rows = [_row(item_code="ITEM-A", qty=50.0, received_qty=50.0)]
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.return_value = rows
			result = self._fn()
		self.assertEqual(result["ITEM-A"], 0.0)

	def test_over_received_clamped_to_zero(self):
		# received > ordered → max(0, ...) clamps to 0
		rows = [_row(item_code="ITEM-A", qty=50.0, received_qty=70.0)]
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.return_value = rows
			result = self._fn()
		self.assertEqual(result["ITEM-A"], 0.0)

	def test_empty_returns_empty(self):
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.return_value = []
			result = self._fn()
		self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# get_open_so_map_for_priority
# ---------------------------------------------------------------------------


class TestGetOpenSoMapForPriority(unittest.TestCase):
	def setUp(self):
		from prakash_steel.prakash_steel.report.po_recomendation_for_psp.data_fetchers import get_open_so_map_for_priority
		self._fn = get_open_so_map_for_priority

	def test_empty_item_codes_returns_empty(self):
		with patch(MODULE + ".frappe") as mf:
			result = self._fn([])
			mf.db.sql.assert_not_called()
		self.assertEqual(result, {})

	def test_groups_so_rows_by_item_code(self):
		rows = [
			_row(item_code="A", pending_qty=10.0, delivery_date="2026-02-01", transaction_date="2026-01-01"),
			_row(item_code="A", pending_qty=20.0, delivery_date="2026-03-01", transaction_date="2026-01-01"),
			_row(item_code="B", pending_qty=5.0, delivery_date="2026-02-15", transaction_date="2026-01-01"),
		]
		with patch(MODULE + ".frappe") as mf, patch(MODULE + "._compute_order_status", return_value="GREEN"):
			mf.db.sql.return_value = rows
			result = self._fn(["A", "B"])
		self.assertEqual(len(result["A"]), 2)
		self.assertEqual(len(result["B"]), 1)

	def test_each_entry_has_pending_qty_and_order_status(self):
		rows = [_row(item_code="A", pending_qty=10.0, delivery_date="2026-02-01", transaction_date="2026-01-01")]
		with patch(MODULE + ".frappe") as mf, patch(MODULE + "._compute_order_status", return_value="RED"):
			mf.db.sql.return_value = rows
			result = self._fn(["A"])
		entry = result["A"][0]
		self.assertIn("pending_qty", entry)
		self.assertIn("order_status", entry)
		self.assertEqual(entry["order_status"], "RED")
		self.assertEqual(entry["pending_qty"], 10.0)

	def test_no_so_rows_returns_empty_map(self):
		with patch(MODULE + ".frappe") as mf:
			mf.db.sql.return_value = []
			result = self._fn(["A", "B"])
		self.assertEqual(dict(result), {})

	def test_order_status_computed_per_row(self):
		rows = [
			_row(item_code="A", pending_qty=5.0, delivery_date="2026-01-05", transaction_date="2025-12-01"),
			_row(item_code="A", pending_qty=8.0, delivery_date="2026-06-01", transaction_date="2025-12-01"),
		]
		statuses = ["BLACK", "WHITE"]
		with patch(MODULE + ".frappe") as mf, patch(MODULE + "._compute_order_status", side_effect=statuses):
			mf.db.sql.return_value = rows
			result = self._fn(["A"])
		self.assertEqual(result["A"][0]["order_status"], "BLACK")
		self.assertEqual(result["A"][1]["order_status"], "WHITE")


# ---------------------------------------------------------------------------
# calculate_spike_map
# ---------------------------------------------------------------------------


class TestCalculateSpikeMap(unittest.TestCase):
	def setUp(self):
		from prakash_steel.prakash_steel.report.po_recomendation_for_psp.data_fetchers import calculate_spike_map
		self._fn = calculate_spike_map

	def test_non_buffer_items_always_zero(self):
		# When all items are Non-Buffer, function returns early with {} (no DB call)
		# Callers use spike_map.get(item_code, 0.0) so absence is equivalent to 0
		spike_master = {"RM": {"demand_horizon": 30, "spike_threshold": 50}}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".today", return_value="2026-01-01"), \
			 patch(MODULE + ".add_days", return_value="2026-01-31"):
			mf.db.sql.return_value = []
			result = self._fn(
				["ITEM-A", "ITEM-B"],
				{"ITEM-A": "Non-Buffer", "ITEM-B": "Non-Buffer"},
				{"ITEM-A": "RM", "ITEM-B": "RM"},
				{"ITEM-A": 100, "ITEM-B": 100},
				spike_master,
			)
		# Result is {} or items have 0.0 — either way spike is falsy/zero
		self.assertFalse(result.get("ITEM-A", 0.0))
		self.assertFalse(result.get("ITEM-B", 0.0))

	def test_no_buffer_items_returns_empty(self):
		# All Non-Buffer → early return with {}, no DB query
		with patch(MODULE + ".frappe") as mf:
			result = self._fn(
				["ITEM-A"],
				{"ITEM-A": "Non-Buffer"},
				{"ITEM-A": "RM"},
				{"ITEM-A": 100},
				{},
			)
			mf.db.sql.assert_not_called()
		self.assertFalse(result.get("ITEM-A", 0.0))

	def test_buffer_item_no_spike_master_spike_zero(self):
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".today", return_value="2026-01-01"), \
			 patch(MODULE + ".add_days", return_value="2026-01-31"):
			mf.db.sql.return_value = []
			result = self._fn(
				["ITEM-A"],
				{"ITEM-A": "Buffer"},
				{"ITEM-A": "UNKNOWN_TYPE"},
				{"ITEM-A": 100},
				{},  # empty spike_master → no config
			)
		self.assertEqual(result.get("ITEM-A"), 0.0)

	def test_buffer_item_zero_demand_horizon_spike_zero(self):
		spike_master = {"RM": {"demand_horizon": 0, "spike_threshold": 50}}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".today", return_value="2026-01-01"):
			mf.db.sql.return_value = []
			result = self._fn(
				["ITEM-A"],
				{"ITEM-A": "Buffer"},
				{"ITEM-A": "RM"},
				{"ITEM-A": 100},
				spike_master,
			)
		self.assertEqual(result.get("ITEM-A"), 0.0)

	def test_buffer_item_future_so_creates_spike(self):
		spike_master = {"RM": {"demand_horizon": 30, "spike_threshold": 0}}
		so_rows = [_row(item_code="ITEM-A", so_qty=50.0, delivery_date="2026-01-15", sales_order_name="SO-001")]
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".today", return_value="2026-01-01"), \
			 patch(MODULE + ".add_days", return_value="2026-01-31"):
			mf.db.sql.return_value = so_rows
			result = self._fn(
				["ITEM-A"],
				{"ITEM-A": "Buffer"},
				{"ITEM-A": "RM"},
				{"ITEM-A": 100},
				spike_master,
			)
		self.assertEqual(result.get("ITEM-A"), 50.0)

	def test_buffer_item_no_tog_excluded_from_details(self):
		# tog=0 → item skipped in buffer_items_with_details → no spike entry
		spike_master = {"RM": {"demand_horizon": 30, "spike_threshold": 50}}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".today", return_value="2026-01-01"), \
			 patch(MODULE + ".add_days", return_value="2026-01-31"):
			mf.db.sql.return_value = []
			result = self._fn(
				["ITEM-A"],
				{"ITEM-A": "Buffer"},
				{"ITEM-A": "RM"},
				{"ITEM-A": 0},  # tog = 0
				spike_master,
			)
		# Buffer item with no TOG: spike_map entry absent or 0
		self.assertFalse(result.get("ITEM-A", 0.0))

	def test_multiple_items_same_type_one_query(self):
		# Two buffer items of same type → only one SQL call for that type
		spike_master = {"RM": {"demand_horizon": 30, "spike_threshold": 0}}
		so_rows = [
			_row(item_code="ITEM-A", so_qty=30.0, delivery_date="2026-01-15", sales_order_name="SO-001"),
			_row(item_code="ITEM-B", so_qty=20.0, delivery_date="2026-01-20", sales_order_name="SO-002"),
		]
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".today", return_value="2026-01-01"), \
			 patch(MODULE + ".add_days", return_value="2026-01-31"):
			mf.db.sql.return_value = so_rows
			result = self._fn(
				["ITEM-A", "ITEM-B"],
				{"ITEM-A": "Buffer", "ITEM-B": "Buffer"},
				{"ITEM-A": "RM", "ITEM-B": "RM"},
				{"ITEM-A": 100, "ITEM-B": 100},
				spike_master,
			)
		# Both items get spike from their respective SO rows
		self.assertEqual(result.get("ITEM-A"), 30.0)
		self.assertEqual(result.get("ITEM-B"), 20.0)
		# Only one SQL call for the single type group
		self.assertEqual(mf.db.sql.call_count, 1)

	def test_spike_master_fetched_from_db_when_not_provided(self):
		# When spike_master_map=None, should call frappe.get_all to fetch it
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".today", return_value="2026-01-01"), \
			 patch(MODULE + ".add_days", return_value="2026-01-31"):
			mf.get_all.return_value = []
			mf.db.sql.return_value = []
			self._fn(
				["ITEM-A"],
				{"ITEM-A": "Buffer"},
				{"ITEM-A": "RM"},
				{"ITEM-A": 100},
				None,  # trigger DB fetch
			)
		mf.get_all.assert_called_once()


if __name__ == "__main__":
	unittest.main()
