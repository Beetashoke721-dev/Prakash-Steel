# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
Unit tests for traded_free_stock.py.

Follows the mocking style already established in
po_recomendation_for_psp/test_po_recomendation_for_psp.py: frappe is replaced
with a MagicMock on the module, frappe.db.sql is given a side-effect
dispatcher (or a plain return_value where only one query shape is issued),
and the module's own DB-backed helper functions are patched by name when
testing get_data()/execute() so only the orchestration logic under test runs
for real. No live site/DB connection is required.
"""

import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import frappe

MODULE = "prakash_steel.prakash_steel.report.traded_free_stock.traded_free_stock"


def _item_row(item_code, item_name="Item Name", item_group="Traded Items", category_name=None, sku_type=None):
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
		from prakash_steel.prakash_steel.report.traded_free_stock.traded_free_stock import get_columns

		self.columns = get_columns()

	def test_fieldnames_in_order(self):
		fieldnames = [c["fieldname"] for c in self.columns]
		self.assertEqual(
			fieldnames,
			["item_code", "item_name", "sku_type", "on_hand_stock", "open_so", "free_stock"],
		)

	def test_item_code_is_link_to_item(self):
		col = next(c for c in self.columns if c["fieldname"] == "item_code")
		self.assertEqual(col["fieldtype"], "Link")
		self.assertEqual(col["options"], "Item")

	def test_numeric_columns_are_float(self):
		for fieldname in ("on_hand_stock", "open_so", "free_stock"):
			col = next(c for c in self.columns if c["fieldname"] == fieldname)
			self.assertEqual(col["fieldtype"], "Float")


# ---------------------------------------------------------------------------
# _get_planning_engine_warehouses()
# ---------------------------------------------------------------------------


class TestGetPlanningEngineWarehouses(unittest.TestCase):
	def test_returns_only_truthy_warehouses(self):
		doc = MagicMock()
		doc.table_cmgr = [
			frappe._dict(warehouse="WH-1"),
			frappe._dict(warehouse=None),
			frappe._dict(warehouse="WH-2"),
			frappe._dict(warehouse=""),
		]
		with patch(MODULE + ".frappe") as mock_frappe:
			mock_frappe.get_single.return_value = doc
			from prakash_steel.prakash_steel.report.traded_free_stock.traded_free_stock import (
				_get_planning_engine_warehouses,
			)

			result = _get_planning_engine_warehouses()

		self.assertEqual(result, ["WH-1", "WH-2"])
		mock_frappe.get_single.assert_called_once_with("Planning Engine Warehouse Setup")

	def test_no_rows_returns_empty_list(self):
		doc = MagicMock()
		doc.table_cmgr = []
		with patch(MODULE + ".frappe") as mock_frappe:
			mock_frappe.get_single.return_value = doc
			from prakash_steel.prakash_steel.report.traded_free_stock.traded_free_stock import (
				_get_planning_engine_warehouses,
			)

			result = _get_planning_engine_warehouses()

		self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# _get_stock_map()
# ---------------------------------------------------------------------------


class TestGetStockMap(unittest.TestCase):
	def setUp(self):
		from prakash_steel.prakash_steel.report.traded_free_stock.traded_free_stock import _get_stock_map

		self._fn = _get_stock_map

	def test_empty_item_codes_returns_empty_without_query(self):
		with patch(MODULE + ".frappe") as mock_frappe:
			result = self._fn([], ["WH-1"])
		self.assertEqual(result, {})
		mock_frappe.db.sql.assert_not_called()

	def test_empty_warehouses_returns_empty_without_query(self):
		with patch(MODULE + ".frappe") as mock_frappe:
			result = self._fn(["ITEM-1"], [])
		self.assertEqual(result, {})
		mock_frappe.db.sql.assert_not_called()

	def test_maps_rows_to_dict(self):
		with patch(MODULE + ".frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = [
				frappe._dict(item_code="ITEM-1", stock=50.0),
				frappe._dict(item_code="ITEM-2", stock=0.0),
			]
			result = self._fn(["ITEM-1", "ITEM-2"], ["WH-1"])
		self.assertEqual(result, {"ITEM-1": 50.0, "ITEM-2": 0.0})


# ---------------------------------------------------------------------------
# _get_open_so_map()
# ---------------------------------------------------------------------------


class TestGetOpenSoMap(unittest.TestCase):
	def test_maps_rows_to_dict(self):
		with patch(MODULE + ".frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = [
				frappe._dict(item_code="ITEM-1", open_qty=20.0),
			]
			from prakash_steel.prakash_steel.report.traded_free_stock.traded_free_stock import (
				_get_open_so_map,
			)

			result = _get_open_so_map()
		self.assertEqual(result, {"ITEM-1": 20.0})

	def test_no_rows_returns_empty_dict(self):
		with patch(MODULE + ".frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = []
			from prakash_steel.prakash_steel.report.traded_free_stock.traded_free_stock import (
				_get_open_so_map,
			)

			result = _get_open_so_map()
		self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# get_data() — orchestration, with the DB-backed helpers mocked out
# ---------------------------------------------------------------------------


class TestGetData(unittest.TestCase):
	def _run(self, filters, items, stock_map=None, open_so_map=None, warehouses=None):
		stock_map = stock_map or {}
		open_so_map = open_so_map or {}
		warehouses = ["WH-1"] if warehouses is None else warehouses

		with ExitStack() as stack:
			mock_frappe = stack.enter_context(patch(MODULE + ".frappe"))
			mock_frappe.db.sql.return_value = items
			stack.enter_context(
				patch(MODULE + "._get_planning_engine_warehouses", return_value=warehouses)
			)
			stack.enter_context(patch(MODULE + "._get_stock_map", return_value=stock_map))
			stack.enter_context(patch(MODULE + "._get_open_so_map", return_value=open_so_map))

			from prakash_steel.prakash_steel.report.traded_free_stock.traded_free_stock import get_data

			return get_data(filters)

	def test_no_items_returns_empty_list(self):
		data = self._run(filters={}, items=[])
		self.assertEqual(data, [])

	def test_basic_row_computation(self):
		items = [_item_row("TR-1", sku_type="TRMTO")]
		data = self._run(
			filters={},
			items=items,
			stock_map={"TR-1": 100.0},
			open_so_map={"TR-1": 30.0},
		)
		self.assertEqual(len(data), 1)
		row = data[0]
		self.assertEqual(row["item_code"], "TR-1")
		self.assertEqual(row["item_name"], "Item Name")
		self.assertEqual(row["sku_type"], "TRMTO")
		self.assertEqual(row["on_hand_stock"], 100.0)
		self.assertEqual(row["open_so"], 30.0)
		self.assertEqual(row["free_stock"], 70.0)

	def test_sku_type_passed_through_from_item_row(self):
		items = [_item_row("TR-1", sku_type="TRMTA")]
		data = self._run(filters={}, items=items, stock_map={"TR-1": 10.0})
		self.assertEqual(data[0]["sku_type"], "TRMTA")

	def test_free_stock_floors_at_zero(self):
		items = [_item_row("TR-1")]
		data = self._run(
			filters={},
			items=items,
			stock_map={"TR-1": 10.0},
			open_so_map={"TR-1": 50.0},
		)
		self.assertEqual(data[0]["free_stock"], 0)

	def test_excludes_zero_stock_by_default(self):
		items = [_item_row("TR-1")]
		data = self._run(filters={}, items=items, stock_map={}, open_so_map={})
		self.assertEqual(data, [])

	def test_include_zero_stock_keeps_zero_stock_rows(self):
		items = [_item_row("TR-1")]
		data = self._run(
			filters={"include_zero_stock": 1}, items=items, stock_map={}, open_so_map={}
		)
		self.assertEqual(len(data), 1)
		self.assertEqual(data[0]["on_hand_stock"], 0)
		self.assertEqual(data[0]["free_stock"], 0)

	def test_nonzero_open_so_does_not_prevent_zero_stock_exclusion(self):
		# The filter is based purely on on_hand_stock — a nonzero open_so does
		# NOT keep a zero-stock row visible when the checkbox is unticked.
		items = [_item_row("TR-1")]
		data = self._run(
			filters={}, items=items, stock_map={}, open_so_map={"TR-1": 15.0}
		)
		self.assertEqual(data, [])

	def test_nonzero_stock_keeps_row_regardless_of_open_so(self):
		items = [_item_row("TR-1")]
		data = self._run(
			filters={}, items=items, stock_map={"TR-1": 5.0}, open_so_map={}
		)
		self.assertEqual(len(data), 1)

	def test_missing_item_in_maps_defaults_to_zero(self):
		# Item present in the item list but absent from both stock/open-so maps
		# entirely (not merely zero-valued) must not raise and must be excluded
		# by the default zero-stock filter.
		items = [_item_row("TR-1")]
		data = self._run(filters={}, items=items, stock_map={}, open_so_map={})
		self.assertEqual(data, [])

	def test_multiple_items_each_computed_independently(self):
		items = [_item_row("TR-1"), _item_row("TR-2")]
		data = self._run(
			filters={},
			items=items,
			stock_map={"TR-1": 100.0, "TR-2": 40.0},
			open_so_map={"TR-1": 10.0, "TR-2": 40.0},
		)
		by_code = {row["item_code"]: row for row in data}
		self.assertEqual(by_code["TR-1"]["free_stock"], 90.0)
		self.assertEqual(by_code["TR-2"]["free_stock"], 0.0)


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


class TestExecute(unittest.TestCase):
	def test_returns_columns_and_data(self):
		with ExitStack() as stack:
			stack.enter_context(
				patch(MODULE + ".get_columns", return_value=[{"fieldname": "item_code"}])
			)
			stack.enter_context(patch(MODULE + ".get_data", return_value=[{"item_code": "TR-1"}]))

			from prakash_steel.prakash_steel.report.traded_free_stock.traded_free_stock import execute

			columns, data = execute({})

		self.assertEqual(columns, [{"fieldname": "item_code"}])
		self.assertEqual(data, [{"item_code": "TR-1"}])


if __name__ == "__main__":
	unittest.main()
