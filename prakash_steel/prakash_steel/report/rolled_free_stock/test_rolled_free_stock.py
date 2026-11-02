# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
Unit tests for rolled_free_stock.py.

Mocking style matches bright_free_stock/test_bright_free_stock.py and
po_recomendation_for_psp/test_po_recomendation_for_psp.py: frappe is replaced
with a MagicMock on the module and the module's own DB-backed helpers are
patched by name so only the orchestration/formula logic under test runs for
real.

NOTE (2026-08-13): Bright Requirement is now sourced from the Bright Plan
report (prakash_steel.prakash_steel.report.bright_plan.bright_plan.get_data),
summing each row's child_stock_shortage for rows whose child_item_code
matches the Rolled Bar item. _get_bright_plan_rows() is the seam patched in
tests below — it's a one-line wrapper around bright_plan.get_data(), so
tests don't need to mock that report's own heavy internals (stock/WIP/BOM/
FIFO allocation) to exercise rolled_free_stock's own summing logic.

No live site/DB connection is required.
"""

import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe

MODULE = "prakash_steel.prakash_steel.report.rolled_free_stock.rolled_free_stock"


def _item_row(item_code, item_name="Item Name", item_group="Rolled Bars", category_name=None, sku_type=None):
	return frappe._dict(
		item_code=item_code,
		item_name=item_name,
		item_group=item_group,
		category_name=category_name,
		sku_type=sku_type,
	)


# ---------------------------------------------------------------------------
# get_columns() — pure, no DB
# ---------------------------------------------------------------------------


class TestGetColumns(unittest.TestCase):
	def setUp(self):
		from prakash_steel.prakash_steel.report.rolled_free_stock.rolled_free_stock import get_columns

		self.columns = get_columns()

	def test_fieldnames_in_order(self):
		fieldnames = [c["fieldname"] for c in self.columns]
		self.assertEqual(
			fieldnames,
			[
				"item_code",
				"item_name",
				"sku_type",
				"on_hand_stock",
				"bright_requirement",
				"qty_available_to_sell",
				"open_so",
				"free_stock",
			],
		)

	def test_item_code_is_link_to_item(self):
		col = next(c for c in self.columns if c["fieldname"] == "item_code")
		self.assertEqual(col["fieldtype"], "Link")
		self.assertEqual(col["options"], "Item")

	def test_numeric_columns_are_int(self):
		for fieldname in (
			"on_hand_stock",
			"bright_requirement",
			"qty_available_to_sell",
			"open_so",
			"free_stock",
		):
			col = next(c for c in self.columns if c["fieldname"] == fieldname)
			self.assertEqual(col["fieldtype"], "Int", f"{fieldname} should be Int")


# ---------------------------------------------------------------------------
# _get_planning_engine_warehouses() / _get_stock_map() / _get_open_so_map()
# ---------------------------------------------------------------------------
# Same shape as bright_free_stock's copies — verified independently since
# rolled_free_stock.py is a fully standalone file (no shared import between
# the two reports for these helpers).


class TestGetPlanningEngineWarehouses(unittest.TestCase):
	def test_returns_only_truthy_warehouses(self):
		doc = MagicMock()
		doc.table_cmgr = [frappe._dict(warehouse="WH-1"), frappe._dict(warehouse=None)]
		with patch(MODULE + ".frappe") as mock_frappe:
			mock_frappe.get_single.return_value = doc
			from prakash_steel.prakash_steel.report.rolled_free_stock.rolled_free_stock import (
				_get_planning_engine_warehouses,
			)

			result = _get_planning_engine_warehouses()
		self.assertEqual(result, ["WH-1"])


class TestGetStockMap(unittest.TestCase):
	def test_empty_item_codes_returns_empty_without_query(self):
		with patch(MODULE + ".frappe") as mock_frappe:
			from prakash_steel.prakash_steel.report.rolled_free_stock.rolled_free_stock import (
				_get_stock_map,
			)

			result = _get_stock_map([], ["WH-1"])
		self.assertEqual(result, {})
		mock_frappe.db.sql.assert_not_called()

	def test_maps_rows_to_dict(self):
		with patch(MODULE + ".frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = [frappe._dict(item_code="RB-1", stock=42.0)]
			from prakash_steel.prakash_steel.report.rolled_free_stock.rolled_free_stock import (
				_get_stock_map,
			)

			result = _get_stock_map(["RB-1"], ["WH-1"])
		self.assertEqual(result, {"RB-1": 42.0})


class TestGetOpenSoMap(unittest.TestCase):
	def test_maps_rows_to_dict(self):
		with patch(MODULE + ".frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = [frappe._dict(item_code="RB-1", open_qty=5.0)]
			from prakash_steel.prakash_steel.report.rolled_free_stock.rolled_free_stock import (
				_get_open_so_map,
			)

			result = _get_open_so_map()
		self.assertEqual(result, {"RB-1": 5.0})


# ---------------------------------------------------------------------------
# get_data() — orchestration, with the DB-backed helpers (including
# _get_bright_requirement_map) mocked out so only the row-building formula
# and the ceil()/zero-row-exclusion logic under test runs for real.
# ---------------------------------------------------------------------------


class TestGetData(unittest.TestCase):
	def _run(self, filters, items, stock_map=None, open_so_map=None, bright_requirement_map=None, warehouses=None):
		stock_map = stock_map or {}
		open_so_map = open_so_map or {}
		bright_requirement_map = bright_requirement_map or {}
		warehouses = ["WH-1"] if warehouses is None else warehouses

		with ExitStack() as stack:
			mock_frappe = stack.enter_context(patch(MODULE + ".frappe"))
			mock_frappe.db.sql.return_value = items
			stack.enter_context(
				patch(MODULE + "._get_planning_engine_warehouses", return_value=warehouses)
			)
			stack.enter_context(patch(MODULE + "._get_stock_map", return_value=stock_map))
			stack.enter_context(patch(MODULE + "._get_open_so_map", return_value=open_so_map))
			stack.enter_context(
				patch(MODULE + "._get_bright_requirement_map", return_value=bright_requirement_map)
			)

			from prakash_steel.prakash_steel.report.rolled_free_stock.rolled_free_stock import get_data

			return get_data(filters)

	def test_no_items_returns_empty_list(self):
		self.assertEqual(self._run(filters={}, items=[]), [])

	def test_basic_row_computation(self):
		items = [_item_row("RB-1", sku_type="RBMTO")]
		data = self._run(
			filters={},
			items=items,
			stock_map={"RB-1": 100.0},
			bright_requirement_map={"RB-1": 20.0},
			open_so_map={"RB-1": 30.0},
		)
		self.assertEqual(len(data), 1)
		row = data[0]
		self.assertEqual(row["item_code"], "RB-1")
		self.assertEqual(row["sku_type"], "RBMTO")
		self.assertEqual(row["on_hand_stock"], 100)
		self.assertEqual(row["bright_requirement"], 20)
		self.assertEqual(row["qty_available_to_sell"], 80)  # max(100-20, 0)
		self.assertEqual(row["open_so"], 30)
		self.assertEqual(row["free_stock"], 50)  # max(80-30, 0)

	def test_all_numeric_fields_are_ceiled(self):
		items = [_item_row("RB-1")]
		data = self._run(
			filters={},
			items=items,
			stock_map={"RB-1": 130.2},
			bright_requirement_map={"RB-1": 10.1},
			open_so_map={"RB-1": 5.05},
		)
		row = data[0]
		# raw: stock=130.2, requirement=10.1 -> qty_available=120.1 -> ceil 121
		#      open_so=5.05 -> free_stock = max(120.1-5.05,0)=115.05 -> ceil 116
		self.assertEqual(row["on_hand_stock"], 131)
		self.assertEqual(row["bright_requirement"], 11)
		self.assertEqual(row["qty_available_to_sell"], 121)
		self.assertEqual(row["open_so"], 6)
		self.assertEqual(row["free_stock"], 116)
		for fieldname in ("on_hand_stock", "bright_requirement", "qty_available_to_sell", "open_so", "free_stock"):
			self.assertIsInstance(row[fieldname], int)

	def test_qty_available_to_sell_floors_at_zero(self):
		# requirement exceeds on-hand stock
		items = [_item_row("RB-1")]
		data = self._run(
			filters={}, items=items, stock_map={"RB-1": 10.0}, bright_requirement_map={"RB-1": 50.0}
		)
		row = data[0]
		self.assertEqual(row["qty_available_to_sell"], 0)
		self.assertEqual(row["free_stock"], 0)

	def test_excludes_zero_stock_by_default(self):
		items = [_item_row("RB-1")]
		data = self._run(filters={}, items=items, stock_map={}, open_so_map={}, bright_requirement_map={})
		self.assertEqual(data, [])

	def test_nonzero_bright_requirement_does_not_prevent_zero_stock_exclusion(self):
		# The filter is based purely on on_hand_stock — a nonzero Bright
		# Requirement does NOT keep a zero-stock row visible when the
		# checkbox is unticked.
		items = [_item_row("RB-1")]
		data = self._run(
			filters={}, items=items, stock_map={}, open_so_map={}, bright_requirement_map={"RB-1": 2041.0}
		)
		self.assertEqual(data, [])

	def test_nonzero_open_so_does_not_prevent_zero_stock_exclusion(self):
		items = [_item_row("RB-1")]
		data = self._run(
			filters={}, items=items, stock_map={}, open_so_map={"RB-1": 15.0}, bright_requirement_map={}
		)
		self.assertEqual(data, [])

	def test_nonzero_stock_keeps_row_regardless_of_other_fields(self):
		items = [_item_row("RB-1")]
		data = self._run(
			filters={}, items=items, stock_map={"RB-1": 5.0}, open_so_map={}, bright_requirement_map={}
		)
		self.assertEqual(len(data), 1)

	def test_include_zero_stock_keeps_zero_stock_rows(self):
		items = [_item_row("RB-1")]
		data = self._run(
			filters={"include_zero_stock": 1},
			items=items,
			stock_map={},
			open_so_map={},
			bright_requirement_map={},
		)
		self.assertEqual(len(data), 1)

	def test_sku_type_passed_through_from_item_row(self):
		items = [_item_row("RB-1", sku_type="RBMTA")]
		data = self._run(filters={}, items=items, stock_map={"RB-1": 10.0})
		self.assertEqual(data[0]["sku_type"], "RBMTA")


# ---------------------------------------------------------------------------
# _get_bright_requirement_map() — sums Bright Plan's child_stock_shortage per
# child_item_code. _get_bright_plan_rows() (a thin wrapper around
# bright_plan.get_data()) is patched directly so these tests exercise only
# rolled_free_stock's own summing logic, not Bright Plan's internals.
# ---------------------------------------------------------------------------


class TestGetBrightRequirementMap(unittest.TestCase):
	def _run(self, bright_plan_rows):
		with patch(MODULE + "._get_bright_plan_rows", return_value=bright_plan_rows):
			from prakash_steel.prakash_steel.report.rolled_free_stock.rolled_free_stock import (
				_get_bright_requirement_map,
			)

			return _get_bright_requirement_map()

	def test_no_bright_plan_rows_returns_empty_dict(self):
		self.assertEqual(self._run([]), {})

	def test_sums_shortage_for_matching_child_item_code(self):
		rows = [
			{"child_item_code": "RB-1", "child_stock_shortage": 10},
			{"child_item_code": "RB-1", "child_stock_shortage": 20},
			{"child_item_code": "RB-2", "child_stock_shortage": 5},
		]
		self.assertEqual(self._run(rows), {"RB-1": 30, "RB-2": 5})

	def test_rows_without_child_item_code_ignored(self):
		rows = [
			{"child_item_code": None, "child_stock_shortage": 10},
			{"child_item_code": "RB-1", "child_stock_shortage": 5},
		]
		self.assertEqual(self._run(rows), {"RB-1": 5})

	def test_missing_shortage_defaults_to_zero(self):
		self.assertEqual(self._run([{"child_item_code": "RB-1"}]), {"RB-1": 0})

	def test_same_parent_multiple_batch_split_rows_accumulate(self):
		# Same Bright Bar parent can appear multiple times — one row per
		# MOQ/batch-size split — and every row's shortage must be summed.
		rows = [
			{"item_code": "BB-1", "child_item_code": "RB-1", "child_stock_shortage": 100},
			{"item_code": "BB-1", "child_item_code": "RB-1", "child_stock_shortage": 150},
		]
		self.assertEqual(self._run(rows), {"RB-1": 250})

	def test_multiple_different_parents_of_same_child_accumulate(self):
		rows = [
			{"item_code": "BB-1", "child_item_code": "RB-1", "child_stock_shortage": 40},
			{"item_code": "BB-2", "child_item_code": "RB-1", "child_stock_shortage": 60},
		]
		self.assertEqual(self._run(rows), {"RB-1": 100})


# ---------------------------------------------------------------------------
# get_bright_requirement_breakdown() — the debug endpoint, mirrors
# _get_bright_requirement_map but lists each matching Bright Plan row.
# ---------------------------------------------------------------------------


class TestGetBrightRequirementBreakdown(unittest.TestCase):
	def _run(self, item_code, item_row, bright_plan_rows):
		def _get_value_dispatch(doctype, name, fields, as_dict=None):
			if doctype == "Item" and name == item_code:
				return item_row
			return None

		with ExitStack() as stack:
			mock_frappe = stack.enter_context(patch(MODULE + ".frappe"))
			mock_frappe.has_permission.return_value = True
			mock_frappe.db.get_value.side_effect = _get_value_dispatch
			stack.enter_context(
				patch(MODULE + "._get_bright_plan_rows", return_value=bright_plan_rows)
			)

			from prakash_steel.prakash_steel.report.rolled_free_stock.rolled_free_stock import (
				get_bright_requirement_breakdown,
			)

			return get_bright_requirement_breakdown(item_code)

	def test_no_matching_rows_returns_no_parents(self):
		result = self._run(
			item_code="RB-1",
			item_row=frappe._dict(item_name="Rolled 1", custom_sku_type="RBMTO"),
			bright_plan_rows=[{"child_item_code": "RB-OTHER", "child_stock_shortage": 999}],
		)
		self.assertTrue(result["no_parents"])
		self.assertEqual(result["parents"], [])
		self.assertEqual(result["total_bright_requirement"], 0)
		self.assertEqual(result["item_code"], "RB-1")
		self.assertEqual(result["sku_type"], "RBMTO")

	def test_lists_and_sums_matching_rows_only(self):
		bright_plan_rows = [
			{
				"item_code": "BB-1",
				"item_name": "Bright 1",
				"machine": "M1",
				"sku_type": "BBMTA",
				"or_with_moq_batch_size": 6000,
				"child_item_code": "RB-1",
				"child_requirement": 6216,
				"child_stock": 10,
				"child_stock_soft_allocation_qty": 10,
				"child_stock_shortage": 6206,
			},
			{
				"item_code": "BB-1",
				"item_name": "Bright 1",
				"machine": "M1",
				"sku_type": "BBMTA",
				"or_with_moq_batch_size": 6000,
				"child_item_code": "RB-1",
				"child_requirement": 6216,
				"child_stock": 10,
				"child_stock_soft_allocation_qty": 0,
				"child_stock_shortage": 6216,
			},
			{"child_item_code": "RB-OTHER", "child_stock_shortage": 999},
		]
		result = self._run(
			item_code="RB-1",
			item_row=frappe._dict(item_name="Rolled 1", custom_sku_type="RBMTA"),
			bright_plan_rows=bright_plan_rows,
		)

		self.assertFalse(result["no_parents"])
		self.assertEqual(len(result["parents"]), 2)
		self.assertEqual(result["parents"][0]["parent_item"], "BB-1")
		self.assertEqual(result["parents"][0]["child_stock_shortage"], 6206)
		self.assertEqual(result["parents"][1]["child_stock_shortage"], 6216)
		self.assertEqual(result["total_bright_requirement"], 12422)

	def test_permission_denied_raises(self):
		with ExitStack() as stack:
			mock_frappe = stack.enter_context(patch(MODULE + ".frappe"))
			mock_frappe.has_permission.return_value = False
			mock_frappe.throw.side_effect = frappe.PermissionError("blocked")

			from prakash_steel.prakash_steel.report.rolled_free_stock.rolled_free_stock import (
				get_bright_requirement_breakdown,
			)

			with self.assertRaises(frappe.PermissionError):
				get_bright_requirement_breakdown("RB-1")

	def test_item_not_found_raises(self):
		with ExitStack() as stack:
			mock_frappe = stack.enter_context(patch(MODULE + ".frappe"))
			mock_frappe.has_permission.return_value = True
			mock_frappe.db.get_value.return_value = None
			mock_frappe.throw.side_effect = frappe.ValidationError("not found")

			from prakash_steel.prakash_steel.report.rolled_free_stock.rolled_free_stock import (
				get_bright_requirement_breakdown,
			)

			with self.assertRaises(frappe.ValidationError):
				get_bright_requirement_breakdown("MISSING-ITEM")


if __name__ == "__main__":
	unittest.main()
