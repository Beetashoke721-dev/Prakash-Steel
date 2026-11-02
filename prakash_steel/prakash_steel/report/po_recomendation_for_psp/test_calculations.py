# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
Unit tests for calculations.py — all pure functions, no DB required.
Run with: python -m pytest test_calculations.py  OR  bench run-tests --module test_calculations
"""

import math
import unittest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import():
	from prakash_steel.prakash_steel.report.po_recomendation_for_psp import calculations

	return calculations


# ---------------------------------------------------------------------------
# _non_buffer_priority
# ---------------------------------------------------------------------------


class TestNonBufferPriority(unittest.TestCase):
	def setUp(self):
		self._fn = _import()._non_buffer_priority

	def test_no_open_sos_returns_empty(self):
		self.assertEqual(self._fn("ITEM-001", 100.0, {}), "")

	def test_item_not_in_map_returns_empty(self):
		self.assertEqual(self._fn("ITEM-001", 100.0, {"OTHER": []}), "")

	def test_sufficient_stock_returns_worst_no_shortage_colour(self):
		so_map = {
			"ITEM": [
				{"pending_qty": 10, "order_status": "GREEN"},
				{"pending_qty": 20, "order_status": "RED"},
			]
		}
		# level 100 covers all → no shortage, worst is RED
		self.assertEqual(self._fn("ITEM", 100.0, so_map), "RED")

	def test_shortage_returns_worst_shortage_colour(self):
		so_map = {
			"ITEM": [
				{"pending_qty": 80, "order_status": "GREEN"},
				{"pending_qty": 40, "order_status": "RED"},  # shortage of 20
			]
		}
		# level 100: first SO uses 80, 20 left; second SO needs 40 → shortage 20 (RED)
		self.assertEqual(self._fn("ITEM", 100.0, so_map), "RED")

	def test_shortage_takes_priority_over_no_shortage(self):
		so_map = {
			"ITEM": [
				{"pending_qty": 200, "order_status": "BLACK"},  # shortage
				{"pending_qty": 10, "order_status": "WHITE"},
			]
		}
		# level 50: BLACK SO has shortage; WHITE has no shortage; result = BLACK
		self.assertEqual(self._fn("ITEM", 50.0, so_map), "BLACK")

	def test_fifo_allocation_picks_correct_worst_shortage(self):
		so_map = {
			"ITEM": [
				{"pending_qty": 30, "order_status": "GREEN"},
				{"pending_qty": 30, "order_status": "YELLOW"},  # partial shortage (10 short)
				{"pending_qty": 30, "order_status": "RED"},  # full shortage (30 short)
			]
		}
		# level 50: SO1 GREEN(30) uses 30→20 left, SO2 YELLOW(30) short 10, SO3 RED(30) short 30
		# worst shortage = RED (priority 4 > YELLOW 3)
		self.assertEqual(self._fn("ITEM", 50.0, so_map), "RED")

	def test_zero_level_all_shortage(self):
		so_map = {
			"ITEM": [
				{"pending_qty": 10, "order_status": "GREEN"},
			]
		}
		self.assertEqual(self._fn("ITEM", 0.0, so_map), "GREEN")

	def test_unknown_order_status_ignored(self):
		so_map = {
			"ITEM": [
				{"pending_qty": 200, "order_status": "PURPLE"},  # unknown, priority 0
			]
		}
		# shortage but no recognised status → no worst_shortage > 0, no worst_no_shortage > 0
		self.assertEqual(self._fn("ITEM", 0.0, so_map), "")


# ---------------------------------------------------------------------------
# get_qualified_demand_for_item
# ---------------------------------------------------------------------------


class TestGetQualifiedDemandForItem(unittest.TestCase):
	def setUp(self):
		self._fn = _import().get_qualified_demand_for_item

	def test_non_buffer_spike_always_zero(self):
		qd, till_today, spike = self._fn(
			"ITEM",
			{"ITEM": 50.0},
			{"ITEM": 99.0},  # spike present but should be ignored
			{"ITEM": "Non-Buffer"},
		)
		self.assertEqual(spike, 0.0)
		self.assertEqual(till_today, 50.0)
		self.assertEqual(qd, 50.0)

	def test_buffer_spike_is_added(self):
		qd, till_today, spike = self._fn(
			"ITEM",
			{"ITEM": 50.0},
			{"ITEM": 20.0},
			{"ITEM": "Buffer"},
		)
		self.assertEqual(spike, 20.0)
		self.assertEqual(till_today, 50.0)
		self.assertEqual(qd, 70.0)

	def test_buffer_no_threshold_applied_here_anymore(self):
		# get_qualified_demand_for_item always returns the RAW till_today+spike —
		# the spike threshold is applied downstream (once parent_demand is known)
		# via apply_spike_threshold / calculate_total_demand, not here.
		qd, _, _ = self._fn(
			"ITEM",
			{"ITEM": 10.0},
			{"ITEM": 0.0},
			{"ITEM": "Buffer"},
		)
		self.assertEqual(qd, 10.0)

	def test_missing_item_defaults_to_zero(self):
		qd, till_today, spike = self._fn(
			"MISSING",
			{},
			{},
			{},
		)
		self.assertEqual(qd, 0.0)
		self.assertEqual(till_today, 0.0)
		self.assertEqual(spike, 0.0)


# ---------------------------------------------------------------------------
# buffer_order_recommendation_colour
# ---------------------------------------------------------------------------


class TestBufferOrderRecommendationColour(unittest.TestCase):
	def setUp(self):
		self._fn = _import().buffer_order_recommendation_colour

	def test_level_zero_is_black(self):
		self.assertEqual(self._fn(0, 150), "Black")

	def test_total_non_positive_is_blank(self):
		self.assertEqual(self._fn(10, 0), "")
		self.assertEqual(self._fn(10, -5), "")

	def test_up_to_one_third_is_red(self):
		self.assertEqual(self._fn(50, 150), "Red")  # exactly total/3

	def test_up_to_two_thirds_is_yellow(self):
		self.assertEqual(self._fn(100, 150), "Yellow")  # exactly 2*total/3

	def test_up_to_total_is_green(self):
		self.assertEqual(self._fn(150, 150), "Green")  # exactly total

	def test_above_total_is_white(self):
		self.assertEqual(self._fn(151, 150), "White")


# ---------------------------------------------------------------------------
# apply_spike_threshold
# ---------------------------------------------------------------------------


class TestApplySpikeThreshold(unittest.TestCase):
	def setUp(self):
		self._fn = _import().apply_spike_threshold

	def test_below_threshold_zeroed(self):
		# tog=100, threshold=50% → threshold_qty=50; total=40 < 50 → zeroed
		result = self._fn(40.0, 100.0, "RM", {"RM": {"spike_threshold": 50.0}})
		self.assertEqual(result, 0.0)

	def test_above_threshold_unchanged(self):
		# tog=100, threshold=50% → threshold_qty=50; total=60 >= 50 → unchanged
		result = self._fn(60.0, 100.0, "RM", {"RM": {"spike_threshold": 50.0}})
		self.assertEqual(result, 60.0)

	def test_no_spike_master_map_no_threshold(self):
		self.assertEqual(self._fn(10.0, 100.0, "RM", None), 10.0)

	def test_no_item_type_no_threshold(self):
		self.assertEqual(self._fn(10.0, 100.0, None, {"RM": {"spike_threshold": 50.0}}), 10.0)

	def test_zero_tog_no_threshold(self):
		self.assertEqual(self._fn(10.0, 0.0, "RM", {"RM": {"spike_threshold": 50.0}}), 10.0)

	def test_no_matching_spike_config_no_threshold(self):
		self.assertEqual(self._fn(10.0, 100.0, "BB", {"RM": {"spike_threshold": 50.0}}), 10.0)


# ---------------------------------------------------------------------------
# calculate_total_demand
# ---------------------------------------------------------------------------


class TestCalculateTotalDemand(unittest.TestCase):
	def setUp(self):
		self._fn = _import().calculate_total_demand

	def test_combines_qualified_and_parent_demand(self):
		result = self._fn(
			"ITEM", True, {"ITEM": 30.0}, {"ITEM": 20.0},
		)
		self.assertEqual(result, 50.0)

	def test_threshold_uses_combined_total_not_qualified_demand_alone(self):
		# Own qualified demand (30) alone would be below a 50 threshold_qty,
		# but qualified_demand + parent_demand (30 + 20 = 50) clears it.
		result = self._fn(
			"ITEM", True, {"ITEM": 30.0}, {"ITEM": 20.0},
			item_tog_map={"ITEM": 100.0},
			item_type_map={"ITEM": "RM"},
			spike_master_map={"RM": {"spike_threshold": 50.0}},
		)
		self.assertEqual(result, 50.0)

	def test_combined_total_still_below_threshold_zeroed(self):
		# qualified_demand(30) + parent_demand(20) = 50 < threshold_qty(80)
		result = self._fn(
			"ITEM", True, {"ITEM": 30.0}, {"ITEM": 20.0},
			item_tog_map={"ITEM": 100.0},
			item_type_map={"ITEM": "RM"},
			spike_master_map={"RM": {"spike_threshold": 80.0}},
		)
		self.assertEqual(result, 0.0)

	def test_non_buffer_never_thresholded(self):
		# Even with a spike_master_map/tog that would zero a buffer item,
		# non-buffer items are never subject to the threshold.
		result = self._fn(
			"ITEM", False, {"ITEM": 5.0}, {"ITEM": 5.0},
			item_tog_map={"ITEM": 100.0},
			item_type_map={"ITEM": "RM"},
			spike_master_map={"RM": {"spike_threshold": 80.0}},
		)
		self.assertEqual(result, 10.0)


# ---------------------------------------------------------------------------
# calculate_final_order_recommendation
# ---------------------------------------------------------------------------


class TestCalculateFinalOrderRecommendation(unittest.TestCase):
	def setUp(self):
		self._fn = _import().calculate_final_order_recommendation

	def _call(
		self,
		item="ITEM",
		is_buffer=True,
		sku_type="BBMTA",
		tog=100,
		stock=20,
		wip=5,
		qd=30,
		open_so=30,
		open_po=0,
		mrq=0,
		parent_demand=0,
		item_type=None,
		spike_master_map=None,
	):
		return self._fn(
			item_code=item,
			item_buffer_map={item: "Buffer" if is_buffer else "Non-Buffer"},
			item_tog_map={item: tog},
			item_sku_type_map={item: sku_type},
			stock_map={item: stock},
			wip_map={item: wip},
			open_so_map={item: open_so},
			qualified_demand_map={item: qd},
			open_po_map={item: open_po},
			mrq_map={item: mrq},
			parent_demand_map={item: parent_demand},
			item_type_map={item: item_type},
			spike_master_map=spike_master_map,
		)

	# Buffer paths
	def test_buffer_bbmta_includes_open_po(self):
		# "else" sku types combine open_po with wip: 100 + 30 - 20 - 5 - 10 = 95
		self.assertEqual(self._call(open_po=10), 95.0)

	def test_buffer_bota_includes_open_po(self):
		# 100 + 30 - 20 - 5 - 10 = 95
		self.assertEqual(self._call(sku_type="BOTA", open_po=10), 95.0)

	def test_buffer_pta_includes_open_po(self):
		self.assertEqual(self._call(sku_type="PTA", open_po=10), 95.0)

	def test_buffer_mrq_reduces(self):
		# 100 + 30 - 20 - 5 = 105, mrq=10 → 95
		self.assertEqual(self._call(mrq=10), 95.0)

	def test_buffer_parent_demand_added(self):
		# 100 + (30 + 20) - 20 - 5 = 125
		self.assertEqual(self._call(parent_demand=20), 125.0)

	def test_buffer_threshold_uses_qualified_demand_plus_parent_demand(self):
		# qd(30) alone is below threshold_qty(40), but qd + parent_demand(20) = 50 clears it
		# → 100 + 50 - 20 - 5 = 125 (not zeroed)
		result = self._call(
			parent_demand=20,
			item_type="RM",
			spike_master_map={"RM": {"spike_threshold": 40.0}},  # threshold_qty = 100*40/100 = 40
		)
		self.assertEqual(result, 125.0)

	def test_buffer_threshold_zeroes_combined_total(self):
		# qd(30) + parent_demand(20) = 50 < threshold_qty(60) → total_demand zeroed
		# → 100 + 0 - 20 - 5 = 75
		result = self._call(
			parent_demand=20,
			item_type="RM",
			spike_master_map={"RM": {"spike_threshold": 60.0}},  # threshold_qty = 100*60/100 = 60
		)
		self.assertEqual(result, 75.0)

	def test_buffer_negative_clamped_to_zero(self):
		self.assertEqual(self._call(stock=500), 0.0)

	def test_buffer_mrq_cannot_go_negative(self):
		# base = 0 (stock covers everything), mrq=100 → still 0
		self.assertEqual(self._call(stock=300, mrq=100), 0.0)

	# Non-buffer paths
	def test_non_buffer_bbmto_includes_open_po(self):
		# "else" sku types combine open_po with wip: 50 - 10 - 5 - 10 = 25
		self.assertEqual(
			self._call(is_buffer=False, sku_type="BBMTO", open_so=50, stock=10, wip=5, open_po=10), 25.0
		)

	def test_non_buffer_trmto_includes_open_po(self):
		# TRMTO now grouped with PTO/BOTO: 50 - 10 - 5 - 10 = 25
		self.assertEqual(
			self._call(is_buffer=False, sku_type="TRMTO", open_so=50, stock=10, wip=5, open_po=10), 25.0
		)

	def test_non_buffer_boto_includes_open_po(self):
		# open_so - stock - wip - open_po = 50 - 10 - 5 - 10 = 25
		self.assertEqual(
			self._call(is_buffer=False, sku_type="BOTO", open_so=50, stock=10, wip=5, open_po=10), 25.0
		)

	def test_non_buffer_pto_includes_open_po(self):
		self.assertEqual(
			self._call(is_buffer=False, sku_type="PTO", open_so=50, stock=10, wip=5, open_po=10), 25.0
		)

	def test_non_buffer_parent_demand_added(self):
		# (open_so + parent) - stock - wip = (30 + 20) - 20 - 5 = 25
		self.assertEqual(self._call(is_buffer=False, sku_type="BBMTO", parent_demand=20), 25.0)

	def test_non_buffer_clamped_to_zero(self):
		self.assertEqual(self._call(is_buffer=False, sku_type="BBMTO", stock=500), 0.0)

	def test_missing_item_defaults(self):
		# Item not in any map → all zeros → max(0, 0) = 0
		result = self._fn(
			item_code="GHOST",
			item_buffer_map={},
			item_tog_map={},
			item_sku_type_map={},
			stock_map={},
			wip_map={},
			open_so_map={},
			qualified_demand_map={},
			open_po_map={},
			mrq_map={},
			parent_demand_map={},
		)
		self.assertEqual(result, 0.0)


# ---------------------------------------------------------------------------
# build_calculation_breakdown_po_report
# ---------------------------------------------------------------------------


class TestBuildCalculationBreakdown(unittest.TestCase):
	def setUp(self):
		self._fn = _import().build_calculation_breakdown_po_report

	def _call_buffer(self, **overrides):
		kwargs = dict(
			item_code="ITEM-001",
			buffer_flag="Buffer",
			is_buffer=True,
			sku_type="BBMTA",
			tog=100,
			qualified_demand=30,
			open_so=30,
			stock=20,
			wip=5,
			open_po=0,
			mrq=0,
			moq=0,
			batch_size=0,
			total_parent_demand=0,
			final_order_rec=105,
			net_order_rec=105,
			parent_demand_details_list=[],
		)
		kwargs.update(overrides)
		return self._fn(**kwargs)

	def test_buffer_contains_item_code(self):
		self.assertIn("ITEM-001", self._call_buffer())

	def test_buffer_contains_tog(self):
		self.assertIn("TOG", self._call_buffer())

	def test_buffer_contains_stock(self):
		self.assertIn("Stock", self._call_buffer())

	def test_buffer_bota_shows_open_po(self):
		self.assertIn("Open PO", self._call_buffer(sku_type="BOTA", open_po=10))

	def test_moq_applied_shown(self):
		result = self._call_buffer(moq=200, final_order_rec=105, net_order_rec=200)
		self.assertIn("MOQ", result)
		self.assertIn("MOQ >= Order Rec", result)

	def test_moq_not_applied_when_base_zero(self):
		result = self._call_buffer(moq=200, final_order_rec=0, net_order_rec=0)
		self.assertIn("Not applied", result)

	def test_batch_size_shown(self):
		result = self._call_buffer(batch_size=50, final_order_rec=105, net_order_rec=150)
		self.assertIn("Batch Size", result)
		self.assertIn("ceil(", result)

	def test_parent_demand_details_included(self):
		details = [
			{
				"parent_item": "PARENT-001",
				"bom_name": "BOM-001",
				"demand_qty": 20,
				"applied": True,
				"reason": "test",
			}
		]
		result = self._call_buffer(total_parent_demand=20, parent_demand_details_list=details)
		self.assertIn("PARENT-001", result)
		self.assertIn("BOM-001", result)

	def test_unapplied_parent_demand_labelled(self):
		details = [
			{
				"parent_item": "PARENT-002",
				"bom_name": "BOM-002",
				"demand_qty": 10,
				"applied": False,
				"reason": "skipped",
			}
		]
		result = self._call_buffer(total_parent_demand=10, parent_demand_details_list=details)
		self.assertIn("IGNORED", result)

	def test_till_today_and_spike_shown(self):
		result = self._call_buffer(till_today=25, spike=5)
		self.assertIn("Till Today", result)
		self.assertIn("Spike", result)

	def test_non_buffer_shows_open_so(self):
		result = self._fn(
			item_code="ITEM-002",
			buffer_flag="Non-Buffer",
			is_buffer=False,
			sku_type="BBMTO",
			tog=0,
			qualified_demand=50,
			open_so=50,
			stock=10,
			wip=5,
			open_po=0,
			mrq=0,
			moq=0,
			batch_size=0,
			total_parent_demand=0,
			final_order_rec=35,
			net_order_rec=35,
			parent_demand_details_list=[],
		)
		self.assertIn("Open SO", result)
		self.assertNotIn("TOG", result)

	def test_returns_string(self):
		result = self._call_buffer()
		self.assertIsInstance(result, str)
		self.assertTrue(len(result) > 0)


# ---------------------------------------------------------------------------
# generate_detailed_log_po_report
# ---------------------------------------------------------------------------


class TestGenerateDetailedLog(unittest.TestCase):
	def setUp(self):
		self._fn = _import().generate_detailed_log_po_report

	def test_empty_data(self):
		result = self._fn([], {})
		self.assertIn("PO RECOMMENDATION", result)
		self.assertIn("Total Items Processed: 0", result)

	def test_item_appears_in_output(self):
		data = [
			{
				"item_code": "ITEM-001",
				"buffer_flag": "Buffer",
				"order_recommendation": 50,
				"calculation_breakdown": "",
				"moq": 0,
				"batch_size": 0,
			}
		]
		result = self._fn(data, {"ITEM-001": 50.0})
		self.assertIn("ITEM-001", result)
		self.assertIn("Total Items Processed: 1", result)

	def test_item_with_net_rec_appears_in_summary(self):
		data = [
			{
				"item_code": "ITEM-001",
				"buffer_flag": "Buffer",
				"order_recommendation": 50,
				"calculation_breakdown": "",
				"moq": 0,
				"batch_size": 0,
			}
		]
		result = self._fn(data, {"ITEM-001": 50.0})
		# Summary section lists items with net_rec > 0
		summary_idx = result.index("SUMMARY")
		detail_idx = result.index("DETAILED BREAKDOWN FOR ALL ITEMS")
		self.assertIn("ITEM-001", result[summary_idx:detail_idx])

	def test_item_with_zero_rec_not_in_summary(self):
		data = [
			{
				"item_code": "ITEM-ZERO",
				"buffer_flag": "Non-Buffer",
				"order_recommendation": 0,
				"calculation_breakdown": "",
				"moq": 0,
				"batch_size": 0,
			}
		]
		result = self._fn(data, {"ITEM-ZERO": 0.0})
		summary_idx = result.index("SUMMARY")
		detail_idx = result.index("DETAILED BREAKDOWN")
		# Not in summary section
		self.assertNotIn("ITEM-ZERO", result[summary_idx:detail_idx])
		# But IS in the detailed section
		self.assertIn("ITEM-ZERO", result[detail_idx:])

	def test_calculation_breakdown_included_when_present(self):
		data = [
			{
				"item_code": "ITEM-001",
				"buffer_flag": "Buffer",
				"order_recommendation": 10,
				"calculation_breakdown": "  Item: ITEM-001\n  Custom breakdown text",
				"moq": 0,
				"batch_size": 0,
			}
		]
		result = self._fn(data, {"ITEM-001": 10.0})
		self.assertIn("Custom breakdown text", result)

	def test_multiple_items_processed(self):
		data = [
			{"item_code": "A", "buffer_flag": "Buffer", "order_recommendation": 10, "calculation_breakdown": "", "moq": 0, "batch_size": 0},
			{"item_code": "B", "buffer_flag": "Non-Buffer", "order_recommendation": 5, "calculation_breakdown": "", "moq": 0, "batch_size": 0},
		]
		result = self._fn(data, {"A": 10.0, "B": 5.0})
		self.assertIn("Total Items Processed: 2", result)
		self.assertIn("A", result)
		self.assertIn("B", result)

	def test_returns_string(self):
		self.assertIsInstance(self._fn([], {}), str)


if __name__ == "__main__":
	unittest.main()
