# Copyright (c) 2026, beetashoke chakraborty and Contributors
# See license.txt

import math
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

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

MODULE = "prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp"


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

	def test_buffer_bbmta_includes_open_po(self):
		# BB + Buffer → BBMTA → "else" sku types combine open_po with wip
		m = self._make_maps("ITEM-001", "Buffer", "BB", tog=100, qualified_demand=50, stock=30, wip=10, open_po=20)
		result = calculate_initial_order_recommendation("ITEM-001", **m)
		# 100 + 50 - 30 - 10 - 20 = 90
		self.assertEqual(result, 90)

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

	def test_non_buffer_bbmto_includes_open_po(self):
		# BB + Non-Buffer → BBMTO → "else" sku types combine open_po with wip
		m = self._make_maps("ITEM-001", "Non-Buffer", "BB", open_so=100, stock=30, wip=10, open_po=20)
		result = calculate_initial_order_recommendation("ITEM-001", **m)
		# 100 - 30 - 10 - 20 = 40
		self.assertEqual(result, 40)

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

	def test_non_buffer_bbmto_includes_open_po(self):
		# BB + Non-Buffer → BBMTO: "else" sku types combine open_po with wip
		# base = 100 - 30 - 10 - 100 = -40 -> clamped to 0, mrq can't push below 0
		m = self._make_maps("ITEM-001", "Non-Buffer", "BB",
							open_so=100, stock=30, wip=10, mrq=5, open_po=100)
		result = calculate_final_order_recommendation("ITEM-001", **m)
		self.assertEqual(result, 0)


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


# ---------------------------------------------------------------------------
# Characterization tests for get_data() — fully mocked, no DB required
# ---------------------------------------------------------------------------
#
# get_data() is being split into calculations.py / data_fetchers.py /
# bom_traversal.py / columns.py. The app's CI is currently disabled and the
# real DB-integration tier above (TestPOReportExecute) cannot run in this
# environment (a documented, pre-existing, out-of-scope india_compliance
# test-record bug). These tests are the only safety net for that refactor:
# they pin today's row-level numeric output of get_data() — including the
# just-fixed formula where open_po is now subtracted (together with wip) for
# *every* SKU type, not just PTO/BOTO/TRMTO/BOTA/PTA — so a regression back
# to the old "else" branch (which forgot to subtract open_po) gets caught.
#
# Mocking follows the same style as test_bom_traversal.py: frappe itself is
# replaced with a MagicMock and frappe.db.sql is given a side-effect
# dispatcher that matches queries by distinctive substrings/table names and
# returns small canned frappe._dict rows. Functions get_data imports by name
# from .calculations / .data_fetchers / .bom_traversal / lead_time are
# patched directly on MODULE (they are just names bound in get_data's own
# module namespace via the re-export shim at the top of
# po_recomendation_for_psp.py). Pure functions (calculate_sku_type,
# calculate_initial_order_recommendation, calculate_final_order_recommendation,
# calculate_net_order_recommendation, get_qualified_demand_for_item,
# build_calculation_breakdown_po_report, _non_buffer_priority) are left real
# so the arithmetic under test is the genuine, unmocked formula.


def _row(**kwargs):
	return frappe._dict(kwargs)


def _bom_item(item_code, qty):
	obj = MagicMock()
	obj.item_code = item_code
	obj.qty = qty
	return obj


def _bom_doc(name, quantity, items):
	doc = MagicMock()
	doc.name = name
	doc.quantity = quantity
	doc.items = items
	return doc


def _item_doc(item_type, buffer_flag):
	doc = MagicMock()

	def _get(key):
		if key == "custom_item_type":
			return item_type
		if key == "custom_buffer_flag":
			return buffer_flag
		return None

	doc.get = _get
	return doc


def _make_sql_dispatcher(item_rows, bin_stock):
	"""
	Builds a frappe.db.sql side-effect that recognizes the handful of raw
	SQL shapes get_data() issues directly (as opposed to the ones hidden
	behind the mocked data_fetchers.* functions) and answers them from the
	small `item_rows` / `bin_stock` fixtures. Anything not recognized
	(bulk BOM pre-fetch, BOM-ancestor BFS, non-buffer preseed SO rows, ...)
	returns an empty list, which is a safe "nothing found" default for the
	single/few-item scenarios exercised here.

	item_rows: {item_code: {buffer_flag, item_type, tog, moq, batch_size,
	                         item_name, toy, tor}}
	bin_stock: {item_code: stock_qty} — used for every `tabBin` query,
	           whether it's an `IN %s` list lookup or a single `= %s` lookup.
	"""

	def _dispatch(query, params=None, as_dict=None, **kwargs):
		q = " ".join(str(query).split())

		if "tabBin" in q:
			if params and isinstance(params[0], (tuple, list)):
				codes = list(params[0])
			elif params:
				codes = [params[0]]
			else:
				codes = list(bin_stock.keys())
			return [_row(item_code=c, stock=bin_stock[c]) for c in codes if c in bin_stock]

		# Plain "SELECT name as item_code FROM tabItem WHERE custom_buffer_flag ..."
		# (no IN-clause, no extra columns) — the top-of-function item universe query.
		if "tabItem" in q and "IN %s" not in q and "min_order_qty" not in q:
			if "!= 'Buffer'" in q:
				codes = [c for c, r in item_rows.items() if r.get("buffer_flag") != "Buffer"]
			else:
				codes = [c for c, r in item_rows.items() if r.get("buffer_flag") == "Buffer"]
			return [_row(item_code=c) for c in codes]

		# Preseed block for buffer items (_buf_rows): "safety_stock AS tog" + "min_order_qty"
		if "tabItem" in q and "IN %s" not in q and "safety_stock AS tog" in q and "min_order_qty" in q:
			rows = []
			for c, r in item_rows.items():
				if r.get("buffer_flag") == "Buffer":
					rows.append(
						_row(
							item_code=c,
							tog=r.get("tog", 0),
							item_type=r.get("item_type"),
							buffer_flag=r.get("buffer_flag"),
							moq=r.get("moq", 0),
							batch_size=r.get("batch_size", 0),
						)
					)
			return rows

		# Preseed block for non-buffer items (_nonbuf_rows): no "safety_stock", has "min_order_qty"
		if (
			"tabItem" in q
			and "IN %s" not in q
			and "custom_item_type AS item_type" in q
			and "safety_stock" not in q
			and "min_order_qty" in q
		):
			rows = []
			for c, r in item_rows.items():
				if r.get("buffer_flag") != "Buffer":
					rows.append(
						_row(
							item_code=c,
							item_type=r.get("item_type"),
							moq=r.get("moq", 0),
							batch_size=r.get("batch_size", 0),
						)
					)
			return rows

		# Bulk item-detail lookups keyed by "i.name IN %s" — items_details_all
		# and items_data (buffer/non-buffer variants) both match this shape.
		if "tabItem" in q and "IN %s" in q:
			codes = params[0] if params else ()
			rows = []
			for c in codes:
				r = item_rows.get(c)
				if not r:
					continue
				rows.append(
					_row(
						item_code=c,
						buffer_flag=r.get("buffer_flag"),
						custom_buffer_flag=r.get("buffer_flag"),
						item_type=r.get("item_type"),
						custom_item_type=r.get("item_type"),
						tog=r.get("tog", 0),
						moq=r.get("moq", 0),
						batch_size=r.get("batch_size", 0),
						item_name=r.get("item_name", ""),
						toy=r.get("toy", 0),
						tor=r.get("tor", 0),
					)
				)
			return rows

		# BOM bulk pre-fetch, BOM-ancestor BFS, non-buffer preseed SO totals, etc.
		# Not exercised by these scenarios — "no rows found" is the correct answer.
		return []

	return _dispatch


class TestGetDataCharacterization(unittest.TestCase):
	"""
	Characterization tests that pin down get_data()'s current row-level
	output before the upcoming extraction of its inline logic into
	calculations.py / data_fetchers.py / bom_traversal.py / columns.py.

	The app's CI is currently disabled and the DB-integration tier
	(TestPOReportExecute above) cannot run in this environment, so these
	fully-mocked tests are the only regression guard the refactor gets.
	Everything is deterministic: frappe.db.sql/get_doc/get_all are mocked
	with a small dispatcher, and every DB-backed helper get_data() imports
	from the sibling modules is patched by name with a fixed return value.
	"""

	def _run_get_data(
		self,
		filters,
		item_rows,
		bin_stock=None,
		so_qty_map=None,
		wip_map=None,
		open_po_map=None,
		mrq_map=None,
		till_today_map=None,
		so_priority_map=None,
		get_default_bom_map=None,
		bom_docs=None,
		item_docs=None,
	):
		bin_stock = bin_stock or {}
		so_qty_map = so_qty_map or {}
		wip_map = wip_map or {}
		open_po_map = open_po_map or {}
		mrq_map = mrq_map or {}
		till_today_map = till_today_map or {}
		so_priority_map = so_priority_map or {}
		get_default_bom_map = get_default_bom_map or {}
		bom_docs = bom_docs or {}
		item_docs = item_docs or {}

		sql_dispatch = _make_sql_dispatcher(item_rows, bin_stock)

		def _get_doc(doctype, name=None):
			if doctype == "BOM":
				return bom_docs[name]
			if doctype == "Item":
				return item_docs[name]
			return MagicMock()

		with ExitStack() as stack:
			mock_frappe = stack.enter_context(patch(MODULE + ".frappe"))
			mock_frappe.db.sql.side_effect = sql_dispatch
			mock_frappe.get_all.return_value = []
			mock_frappe.get_doc.side_effect = _get_doc

			stack.enter_context(
				patch(MODULE + ".get_default_bom", side_effect=lambda ic: get_default_bom_map.get(ic))
			)
			stack.enter_context(patch(MODULE + ".get_stock_map", return_value=dict(bin_stock)))
			stack.enter_context(patch(MODULE + ".get_sales_order_qty_map", return_value=dict(so_qty_map)))
			stack.enter_context(
				patch(MODULE + ".get_qualified_demand_map", return_value=(dict(till_today_map), {}))
			)
			stack.enter_context(patch(MODULE + ".get_wip_map", return_value=dict(wip_map)))
			stack.enter_context(patch(MODULE + ".get_mrq_map", return_value=dict(mrq_map)))
			stack.enter_context(patch(MODULE + ".get_open_po_map", return_value=dict(open_po_map)))
			stack.enter_context(
				patch(MODULE + ".get_open_so_map_for_priority", return_value=dict(so_priority_map))
			)
			stack.enter_context(patch(MODULE + ".calculate_spike_map", return_value={}))
			stack.enter_context(patch(MODULE + ".traverse_bom_for_parent_demand_simple", return_value=None))
			stack.enter_context(patch(MODULE + ".traverse_bom_for_parent_demand", return_value=None))
			stack.enter_context(patch(MODULE + ".traverse_bom_for_po", return_value=None))
			stack.enter_context(patch(MODULE + ".propagate_priority_through_bom_tree", return_value=None))

			from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
				get_data,
			)

			return get_data(filters)

	def test_non_buffer_pto_order_rec_matches_open_so_minus_stock_wip_open_po(self):
		"""
		Scenario 1: single non-buffer RM (PTO) item, no BOM children.
		open_so=100, stock=30, wip=10, open_po=20 →
		order_recommendation = ceil(max(0, 100 - 30 - 10 - 20)) = 40.
		"""
		data = self._run_get_data(
			filters={"purchase": 1, "buffer_flag": 0},
			item_rows={
				"ITEM-001": {
					"buffer_flag": "Non-Buffer",
					"item_type": "RM",
					"tog": 0,
					"moq": 0,
					"batch_size": 0,
					"item_name": "Item 001",
					"toy": 0,
					"tor": 0,
				}
			},
			bin_stock={"ITEM-001": 30},
			so_qty_map={"ITEM-001": 100},
			wip_map={"ITEM-001": 10},
			open_po_map={"ITEM-001": 20},
		)

		self.assertEqual(len(data), 1)
		row = data[0]
		self.assertEqual(row["item_code"], "ITEM-001")
		self.assertEqual(row["sku_type"], "PTO")
		self.assertEqual(row["order_recommendation"], 40)
		self.assertEqual(row["net_po_recommendation"], 40)
		self.assertEqual(row["or_with_moq_batch_size"], 40)
		self.assertEqual(row["on_hand_stock"], 30)
		self.assertEqual(row["wip"], 10)
		self.assertEqual(row["open_po"], 20)
		self.assertEqual(row["priority"], "")

	def test_non_buffer_formerly_else_sku_type_now_subtracts_open_po(self):
		"""
		Scenario 2: RBMTO (item_type RB, Non-Buffer) — a "formerly-else" SKU
		type that, before the fix, did NOT subtract open_po in this formula
		(only wip was subtracted). With a nonzero open_po this proves the
		fix is captured: open_so=100, stock=20, wip=0, open_po=30 →
		order_recommendation = ceil(max(0, 100 - 20 - 0 - 30)) = 50.
		Pre-fix this would have been ceil(max(0, 100 - 20 - 0)) = 80, since
		open_po would not have been subtracted for RBMTO.
		"""
		data = self._run_get_data(
			filters={"sell": 1, "buffer_flag": 0},
			item_rows={
				"ITEM-RB": {
					"buffer_flag": "Non-Buffer",
					"item_type": "RB",
					"tog": 0,
					"moq": 0,
					"batch_size": 0,
					"item_name": "Item RB",
					"toy": 0,
					"tor": 0,
				}
			},
			bin_stock={"ITEM-RB": 20},
			so_qty_map={"ITEM-RB": 100},
			wip_map={},
			open_po_map={"ITEM-RB": 30},
		)

		self.assertEqual(len(data), 1)
		row = data[0]
		self.assertEqual(row["item_code"], "ITEM-RB")
		self.assertEqual(row["sku_type"], "RBMTO")
		self.assertEqual(row["order_recommendation"], 50)
		self.assertEqual(row["net_po_recommendation"], 50)
		self.assertEqual(row["or_with_moq_batch_size"], 50)

	def test_buffer_item_with_bom_child_populates_child_kit_fields(self):
		"""
		Scenario 3: single buffer RM (PTA) item, TOG=50, qualified demand
		(till_today)=80, stock=10 → order_recommendation =
		ceil(max(0, 50 + 80 - 10 - 0 - 0)) = 120.
		It has one BOM child (CHILD-001, bom_qty=2 per 1 parent unit,
		stock=100, no wip/open_po) → child_requirement =
		ceil(120 * 2/1) = 240; stock covers 100 of that (shortage 140,
		partially allocated) so child_full_kit_status is "Partial" and,
		since child has no WIP/open PO at all, child_wip_open_po_full_kit_status
		is "Pending".
		"""
		data = self._run_get_data(
			filters={"purchase": 1, "buffer_flag": 1},
			item_rows={
				"ITEM-PARENT": {
					"buffer_flag": "Buffer",
					"item_type": "RM",
					"tog": 50,
					"moq": 0,
					"batch_size": 0,
					"item_name": "Parent Item",
					"toy": 20,
					"tor": 10,
				}
			},
			bin_stock={"ITEM-PARENT": 10, "CHILD-001": 100},
			till_today_map={"ITEM-PARENT": 80},
			get_default_bom_map={"ITEM-PARENT": "BOM-PARENT"},
			bom_docs={"BOM-PARENT": _bom_doc("BOM-PARENT", 1, [_bom_item("CHILD-001", 2)])},
			item_docs={"CHILD-001": _item_doc("RM", "Non-Buffer")},
		)

		self.assertEqual(len(data), 1)
		row = data[0]
		self.assertEqual(row["item_code"], "ITEM-PARENT")
		self.assertEqual(row["sku_type"], "PTA")
		self.assertEqual(row["order_recommendation"], 120)
		self.assertEqual(row["net_po_recommendation"], 120)
		self.assertEqual(row["or_with_moq_batch_size"], 120)
		self.assertEqual(row["child_item_code"], "CHILD-001")
		self.assertEqual(row["child_sku_type"], "PTO")
		self.assertEqual(row["child_requirement"], 240)
		self.assertEqual(row["child_stock"], 100)
		self.assertEqual(row["child_stock_shortage"], 140)
		self.assertEqual(row["child_full_kit_status"], "Partial")
		self.assertEqual(row["child_wip_open_po_full_kit_status"], "Pending")


if __name__ == "__main__":
	unittest.main()
