# Copyright (c) 2026, beetashoke chakraborty and Contributors
# See license.txt

import math
import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

import pytest
from frappe.utils import add_days, nowdate

from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
	_compute_order_status,
	_non_buffer_priority,
	calculate_final_order_recommendation,
	calculate_initial_order_recommendation,
	calculate_net_order_recommendation,
	calculate_sku_type,
	execute,
)


# ---------------------------------------------------------------------------
# Pure unit tests (no DB required)
# ---------------------------------------------------------------------------


class TestCalculateSkuType(unittest.TestCase):
	"""Tests for calculate_sku_type() - pure function, no DB."""

	def test_bb_buffer(self):
		self.assertEqual(calculate_sku_type("Buffer", "BB"), "BBMTA")

	def test_bb_non_buffer(self):
		self.assertEqual(calculate_sku_type("Non-Buffer", "BB"), "BBMTO")

	def test_rb_buffer(self):
		self.assertEqual(calculate_sku_type("Buffer", "RB"), "RBMTA")

	def test_rb_non_buffer(self):
		self.assertEqual(calculate_sku_type("Non-Buffer", "RB"), "RBMTO")

	def test_bo_buffer(self):
		self.assertEqual(calculate_sku_type("Buffer", "BO"), "BOTA")

	def test_bo_non_buffer(self):
		self.assertEqual(calculate_sku_type("Non-Buffer", "BO"), "BOTO")

	def test_rm_buffer(self):
		self.assertEqual(calculate_sku_type("Buffer", "RM"), "PTA")

	def test_rm_non_buffer(self):
		self.assertEqual(calculate_sku_type("Non-Buffer", "RM"), "PTO")

	def test_traded_buffer(self):
		self.assertEqual(calculate_sku_type("Buffer", "Traded"), "TRMTA")

	def test_traded_non_buffer(self):
		self.assertEqual(calculate_sku_type("Non-Buffer", "Traded"), "TRMTO")

	def test_none_item_type_returns_none(self):
		self.assertIsNone(calculate_sku_type("Buffer", None))

	def test_unknown_item_type_returns_none(self):
		self.assertIsNone(calculate_sku_type("Buffer", "UNKNOWN"))


class TestComputeOrderStatus(unittest.TestCase):
	"""Tests for _compute_order_status() - pure function, no DB."""

	def test_no_delivery_date_returns_none(self):
		self.assertIsNone(_compute_order_status(None, nowdate()))

	def test_overdue_returns_black(self):
		# delivery_date in the past → remaining_days < 0
		past_date = add_days(nowdate(), -5)
		self.assertEqual(_compute_order_status(past_date, add_days(past_date, -10)), "BLACK")

	def test_buffer_pct_within_34_returns_red(self):
		# lead_time=100 days, remaining=20 → 20% → RED
		transaction_date = add_days(nowdate(), -80)
		delivery_date = add_days(nowdate(), 20)
		status = _compute_order_status(delivery_date, transaction_date)
		self.assertEqual(status, "RED")

	def test_buffer_pct_within_67_returns_yellow(self):
		# lead_time=100 days, remaining=50 → 50% → YELLOW
		transaction_date = add_days(nowdate(), -50)
		delivery_date = add_days(nowdate(), 50)
		status = _compute_order_status(delivery_date, transaction_date)
		self.assertEqual(status, "YELLOW")

	def test_buffer_pct_within_100_returns_green(self):
		# lead_time=100 days, remaining=80 → 80% → GREEN
		transaction_date = add_days(nowdate(), -20)
		delivery_date = add_days(nowdate(), 80)
		status = _compute_order_status(delivery_date, transaction_date)
		self.assertEqual(status, "GREEN")

	def test_buffer_pct_above_100_returns_white(self):
		# For WHITE: buffer_pct > 100% → remaining_days > lead_time
		# lead_time = date_diff(delivery_date, transaction_date)
		# remaining  = date_diff(delivery_date, today)
		# remaining > lead_time  ⟺  transaction_date > today
		# Example: delivery in 100 days, transaction_date 10 days in the future
		#   → lead_time = 90, remaining = 100 → 100/90*100 = 111% → WHITE
		transaction_date = add_days(nowdate(), 10)
		delivery_date = add_days(nowdate(), 100)
		status = _compute_order_status(delivery_date, transaction_date)
		self.assertEqual(status, "WHITE")

	def test_no_transaction_date_uses_remaining_days(self):
		# No transaction_date → lead_time = None → buffer_pct = remaining_days * 100
		delivery_date = add_days(nowdate(), 1)
		# remaining=1, buffer_pct = 1*100 = 100 → ceil(100) = 100 → GREEN
		status = _compute_order_status(delivery_date, None)
		self.assertEqual(status, "GREEN")


class TestCalculateNetOrderRecommendation(unittest.TestCase):
	"""Tests for calculate_net_order_recommendation() - pure function, no DB."""

	def test_zero_base_returns_zero(self):
		self.assertEqual(calculate_net_order_recommendation(0, 0, 0), 0)

	def test_negative_base_returns_zero(self):
		self.assertEqual(calculate_net_order_recommendation(-10, 0, 0), 0)

	def test_no_moq_no_batch_size(self):
		self.assertEqual(calculate_net_order_recommendation(50, 0, 0), 50)

	def test_moq_less_than_order_rec_uses_order_rec(self):
		# moq=20 < base=50 → use base=50
		self.assertEqual(calculate_net_order_recommendation(50, 20, 0), 50)

	def test_moq_greater_than_order_rec_uses_moq(self):
		# moq=100 >= base=50 → use moq=100
		self.assertEqual(calculate_net_order_recommendation(50, 100, 0), 100)

	def test_moq_equal_to_order_rec_uses_moq(self):
		# moq=50 == base=50 → use moq=50
		self.assertEqual(calculate_net_order_recommendation(50, 50, 0), 50)

	def test_batch_size_rounds_up(self):
		# base=55, batch=25 → ceil(55/25)*25 = 3*25 = 75
		self.assertEqual(calculate_net_order_recommendation(55, 0, 25), 75)

	def test_batch_size_exact_multiple(self):
		# base=50, batch=25 → ceil(50/25)*25 = 2*25 = 50
		self.assertEqual(calculate_net_order_recommendation(50, 0, 25), 50)

	def test_moq_takes_priority_over_batch_size(self):
		# Both MOQ and batch_size set → MOQ takes priority
		self.assertEqual(calculate_net_order_recommendation(30, 100, 25), 100)


class TestCalculateInitialOrderRecommendation(unittest.TestCase):
	"""Tests for calculate_initial_order_recommendation() - pure maps, no DB."""

	def _make_maps(self, item_code, buffer_flag, item_type, tog=0, stock=0, wip=0, open_so=0, qualified_demand=0, open_po=0):
		from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
			calculate_sku_type,
		)

		return {
			"item_buffer_map": {item_code: buffer_flag},
			"item_tog_map": {item_code: tog},
			"item_sku_type_map": {item_code: calculate_sku_type(buffer_flag, item_type)},
			"stock_map": {item_code: stock},
			"wip_map": {item_code: wip},
			"open_so_map": {item_code: open_so},
			"qualified_demand_map": {item_code: qualified_demand},
			"open_po_map": {item_code: open_po},
		}

	def test_buffer_pta_includes_open_po(self):
		# RM + Buffer → PTA → order_rec = tog + qualified_demand - stock - wip - open_po
		m = self._make_maps("ITEM-001", "Buffer", "RM", tog=100, qualified_demand=50, stock=30, wip=10, open_po=20)
		result = calculate_initial_order_recommendation("ITEM-001", **m)
		# 100 + 50 - 30 - 10 - 20 = 90
		self.assertEqual(result, 90)

	def test_buffer_bbmta_excludes_open_po(self):
		# BB + Buffer → BBMTA → order_rec = tog + qualified_demand - stock - wip
		m = self._make_maps("ITEM-001", "Buffer", "BB", tog=100, qualified_demand=50, stock=30, wip=10, open_po=20)
		result = calculate_initial_order_recommendation("ITEM-001", **m)
		# 100 + 50 - 30 - 10 = 110
		self.assertEqual(result, 110)

	def test_buffer_result_floored_at_zero(self):
		# stock > tog + demand
		m = self._make_maps("ITEM-001", "Buffer", "BB", tog=50, qualified_demand=10, stock=200, wip=0)
		result = calculate_initial_order_recommendation("ITEM-001", **m)
		self.assertEqual(result, 0)

	def test_non_buffer_pto_includes_open_po(self):
		# RM + Non-Buffer → PTO → order_rec = open_so - stock - wip - open_po
		m = self._make_maps("ITEM-001", "Non-Buffer", "RM", open_so=100, stock=30, wip=10, open_po=20)
		result = calculate_initial_order_recommendation("ITEM-001", **m)
		# 100 - 30 - 10 - 20 = 40
		self.assertEqual(result, 40)

	def test_non_buffer_bbmto_excludes_open_po(self):
		# BB + Non-Buffer → BBMTO → order_rec = open_so - stock - wip
		m = self._make_maps("ITEM-001", "Non-Buffer", "BB", open_so=100, stock=30, wip=10, open_po=20)
		result = calculate_initial_order_recommendation("ITEM-001", **m)
		# 100 - 30 - 10 = 60
		self.assertEqual(result, 60)

	def test_non_buffer_result_floored_at_zero(self):
		m = self._make_maps("ITEM-001", "Non-Buffer", "BB", open_so=10, stock=200)
		result = calculate_initial_order_recommendation("ITEM-001", **m)
		self.assertEqual(result, 0)


class TestCalculateFinalOrderRecommendation(unittest.TestCase):
	"""Tests for calculate_final_order_recommendation() - pure maps, no DB."""

	def _make_maps(self, item_code, buffer_flag, item_type, tog=0, stock=0, wip=0,
				   open_so=0, qualified_demand=0, open_po=0, mrq=0, parent_demand=0):
		from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
			calculate_sku_type,
		)

		return {
			"item_buffer_map": {item_code: buffer_flag},
			"item_tog_map": {item_code: tog},
			"item_sku_type_map": {item_code: calculate_sku_type(buffer_flag, item_type)},
			"stock_map": {item_code: stock},
			"wip_map": {item_code: wip},
			"open_so_map": {item_code: open_so},
			"qualified_demand_map": {item_code: qualified_demand},
			"open_po_map": {item_code: open_po},
			"mrq_map": {item_code: mrq},
			"parent_demand_map": {item_code: parent_demand},
		}

	def test_buffer_pta_with_mrq_and_parent_demand(self):
		# RM + Buffer → PTA
		# order_rec = (tog + qualified_demand + parent_demand - stock - wip - open_po) - mrq
		# = (100 + 50 + 20 - 30 - 10 - 15) - 5 = 115 - 5 = 110
		m = self._make_maps("ITEM-001", "Buffer", "RM",
							tog=100, qualified_demand=50, parent_demand=20,
							stock=30, wip=10, open_po=15, mrq=5)
		result = calculate_final_order_recommendation("ITEM-001", **m)
		self.assertEqual(result, 110)

	def test_buffer_mrq_reduces_order_rec(self):
		# BBMTA (BB + Buffer): order_rec = tog + total_demand - stock - wip - mrq
		# = 100 + 50 - 30 - 10 - 25 = 85
		m = self._make_maps("ITEM-001", "Buffer", "BB",
							tog=100, qualified_demand=50, stock=30, wip=10, mrq=25)
		result = calculate_final_order_recommendation("ITEM-001", **m)
		self.assertEqual(result, 85)

	def test_mrq_greater_than_base_returns_zero(self):
		# base = 10, mrq = 50 → max(0, 10 - 50) = 0
		m = self._make_maps("ITEM-001", "Buffer", "BB",
							tog=50, qualified_demand=10, stock=30, wip=10, mrq=50)
		result = calculate_final_order_recommendation("ITEM-001", **m)
		self.assertEqual(result, 0)

	def test_non_buffer_pto_with_parent_demand_and_mrq(self):
		# RM + Non-Buffer → PTO
		# base = (open_so + parent_demand) - stock - wip - open_po - mrq
		# = (100 + 20) - 30 - 10 - 15 - 5 = 60
		m = self._make_maps("ITEM-001", "Non-Buffer", "RM",
							open_so=100, parent_demand=20, stock=30, wip=10, open_po=15, mrq=5)
		result = calculate_final_order_recommendation("ITEM-001", **m)
		self.assertEqual(result, 60)

	def test_non_buffer_bbmto_excludes_open_po(self):
		# BB + Non-Buffer → BBMTO: base = open_so - stock - wip - mrq (no open_po)
		# = 100 - 30 - 10 - 5 = 55
		m = self._make_maps("ITEM-001", "Non-Buffer", "BB",
							open_so=100, stock=30, wip=10, mrq=5, open_po=100)
		result = calculate_final_order_recommendation("ITEM-001", **m)
		self.assertEqual(result, 55)


class TestNonBufferPriority(unittest.TestCase):
	"""Tests for _non_buffer_priority() - pure function, no DB."""

	def test_no_open_sos_returns_empty_string(self):
		result = _non_buffer_priority("ITEM-001", 100, {})
		self.assertEqual(result, "")

	def test_sufficient_stock_returns_best_colour(self):
		# level=200, SO requires 100 → no shortage → return colour of that SO
		so_map = {
			"ITEM-001": [
				{"pending_qty": 100, "order_status": "GREEN", "delivery_date": add_days(nowdate(), 10)}
			]
		}
		result = _non_buffer_priority("ITEM-001", 200, so_map)
		self.assertEqual(result, "Green")

	def test_shortage_returns_worst_shortage_colour(self):
		# level=0, SO needs 100 → shortage → colour based on order_status
		so_map = {
			"ITEM-001": [
				{"pending_qty": 100, "order_status": "RED", "delivery_date": add_days(nowdate(), 5)}
			]
		}
		result = _non_buffer_priority("ITEM-001", 0, so_map)
		self.assertEqual(result, "Red")

	def test_multiple_sos_fifo_allocation_worst_shortage(self):
		# level=50, SO1=60 (RED-shortage), SO2=40 (GREEN-no-shortage after SO1)
		so_map = {
			"ITEM-001": [
				{"pending_qty": 60, "order_status": "RED", "delivery_date": add_days(nowdate(), 5)},
				{"pending_qty": 40, "order_status": "GREEN", "delivery_date": add_days(nowdate(), 15)},
			]
		}
		result = _non_buffer_priority("ITEM-001", 50, so_map)
		# SO1: needs 60, available 50 → shortage 10 → RED
		# SO2: available 0, needs 40 → shortage 40 → GREEN (priority 2 < RED priority 4)
		# worst shortage = RED
		self.assertEqual(result, "Red")

	def test_black_is_highest_priority(self):
		so_map = {
			"ITEM-001": [
				{"pending_qty": 10, "order_status": "BLACK", "delivery_date": add_days(nowdate(), -1)},
				{"pending_qty": 10, "order_status": "RED", "delivery_date": add_days(nowdate(), 5)},
			]
		}
		result = _non_buffer_priority("ITEM-001", 0, so_map)
		self.assertEqual(result, "Black")


# ---------------------------------------------------------------------------
# Integration tests (require DB / Frappe context)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="integration test — requires bench run-tests with a live Frappe site")
class TestPOReportExecute(FrappeTestCase):
	"""Integration tests for execute() function."""

	def test_execute_returns_two_elements(self):
		columns, data = execute({"purchase": 1})
		self.assertIsInstance(columns, list)
		self.assertIsInstance(data, list)

	def test_execute_no_filters_returns_empty_data(self):
		# Neither purchase nor sell set → must return empty data
		columns, data = execute({})
		self.assertEqual(data, [])

	def test_execute_purchase_buffer_returns_columns(self):
		columns, data = execute({"purchase": 1, "buffer_flag": 1})
		self.assertIsInstance(columns, list)
		self.assertTrue(len(columns) > 0)
		# Buffer-specific columns must be present
		fieldnames = [c["fieldname"] for c in columns]
		self.assertIn("tog", fieldnames)
		self.assertIn("on_hand_colour", fieldnames)

	def test_execute_purchase_non_buffer_returns_columns(self):
		columns, data = execute({"purchase": 1, "buffer_flag": 0})
		fieldnames = [c["fieldname"] for c in columns]
		self.assertIn("priority", fieldnames)
		self.assertIn("requirement", fieldnames)
		self.assertNotIn("tog", fieldnames)

	def test_execute_sell_returns_child_columns(self):
		columns, data = execute({"sell": 1})
		fieldnames = [c["fieldname"] for c in columns]
		self.assertIn("child_item_code", fieldnames)
		self.assertIn("child_stock", fieldnames)

	def test_execute_data_rows_have_required_fields(self):
		columns, data = execute({"purchase": 1})
		for row in data:
			self.assertIn("item_code", row)
			self.assertIn("or_with_moq_batch_size", row)

	def test_execute_net_order_rec_never_negative(self):
		_, data = execute({"purchase": 1})
		for row in data:
			net_rec = row.get("or_with_moq_batch_size", 0) or 0
			self.assertGreaterEqual(net_rec, 0, f"Negative net order rec for {row.get('item_code')}")

	def test_execute_string_filters_parsed_correctly(self):
		# Filters passed as strings (as they come from the JS front-end)
		columns1, data1 = execute({"purchase": "1", "buffer_flag": "1"})
		columns2, data2 = execute({"purchase": 1, "buffer_flag": 1})
		# Column structure must be identical
		self.assertEqual(
			[c["fieldname"] for c in columns1],
			[c["fieldname"] for c in columns2],
		)
