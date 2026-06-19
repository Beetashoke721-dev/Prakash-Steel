# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
Unit tests for bom_traversal.py — all DB/frappe calls are mocked.
"""

import unittest
from unittest.mock import MagicMock, patch


MODULE = "prakash_steel.prakash_steel.report.po_recomendation_for_psp.bom_traversal"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _item_doc(item_group):
	doc = MagicMock()
	doc.get = lambda key: item_group if key == "item_group" else None
	return doc


def _frappe_get_doc(item_doc_group, bom_map):
	"""Returns a side_effect for frappe.get_doc that dispatches by doctype."""

	def _dispatch(doctype, name):
		if doctype == "Item":
			return _item_doc(item_doc_group)
		if doctype == "BOM":
			return bom_map[name]
		return MagicMock()

	return _dispatch


# ---------------------------------------------------------------------------
# traverse_bom_for_parent_demand_simple
# ---------------------------------------------------------------------------


class TestTraverseBomSimple(unittest.TestCase):
	def setUp(self):
		from prakash_steel.prakash_steel.report.po_recomendation_for_psp.bom_traversal import (
			traverse_bom_for_parent_demand_simple,
		)
		self._fn = traverse_bom_for_parent_demand_simple

	def test_already_visited_skips(self):
		demand_map = {}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom") as mgb:
			self._fn("ITEM-A", 100, demand_map, {"ITEM-A"}, {}, {})
			mf.get_doc.assert_not_called()
			mgb.assert_not_called()
		self.assertEqual(demand_map, {})

	def test_raw_material_stops_traversal(self):
		demand_map = {}
		with patch(MODULE + ".get_default_bom") as mgb:
			self._fn("RM", 100, demand_map, set(), {"RM": "Raw Material"}, {})
			mgb.assert_not_called()
		self.assertEqual(demand_map, {})

	def test_raw_material_from_db_stops_traversal(self):
		# item_groups_cache miss → fetches from DB, still stops if Raw Material
		demand_map = {}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom") as mgb:
			mf.get_doc.return_value = _item_doc("Raw Material")
			self._fn("RM", 100, demand_map, set(), {}, {})
			mgb.assert_not_called()
		self.assertEqual(demand_map, {})

	def test_no_bom_stops_traversal(self):
		demand_map = {}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom", return_value=None):
			mf.get_doc.return_value = _item_doc("Finished Goods")
			self._fn("FG", 100, demand_map, set(), {}, {})
		self.assertEqual(demand_map, {})

	def test_basic_demand_accumulation(self):
		# BOM: 1 FG = 2 CHILD-A + 3 CHILD-B, parent needs 10 → child-A 20, child-B 30
		# Children are "Raw Material" so recursion stops after first level
		bom = _bom_doc("BOM-001", 1, [_bom_item("CHILD-A", 2), _bom_item("CHILD-B", 3)])
		demand_map = {}
		cache = {"CHILD-A": "Raw Material", "CHILD-B": "Raw Material"}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom", return_value="BOM-001"):
			mf.get_doc.side_effect = _frappe_get_doc("Finished Goods", {"BOM-001": bom})
			self._fn("FG", 10, demand_map, set(), cache, {})
		self.assertEqual(demand_map["CHILD-A"], 20.0)
		self.assertEqual(demand_map["CHILD-B"], 30.0)

	def test_bom_quantity_normalises_ratio(self):
		# BOM produces 5 FG, needs 10 CHILD-A → ratio 2.0; parent=50 → child-A=100
		bom = _bom_doc("BOM-001", 5, [_bom_item("CHILD-A", 10)])
		demand_map = {}
		cache = {"CHILD-A": "Raw Material"}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom", return_value="BOM-001"):
			mf.get_doc.side_effect = _frappe_get_doc("Finished Goods", {"BOM-001": bom})
			self._fn("FG", 50, demand_map, set(), cache, {})
		self.assertEqual(demand_map["CHILD-A"], 100.0)

	def test_accumulates_across_multiple_parents(self):
		# Two parents each contribute demand for CHILD-A
		# get_default_bom returns None for CHILD-A → recursion stops naturally
		bom_a = _bom_doc("BOM-A", 1, [_bom_item("CHILD-A", 1)])
		bom_b = _bom_doc("BOM-B", 1, [_bom_item("CHILD-A", 2)])
		bom_map = {"BOM-A": bom_a, "BOM-B": bom_b}
		dbom_map = {"PARENT-A": "BOM-A", "PARENT-B": "BOM-B"}
		demand_map = {}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom", side_effect=lambda ic: dbom_map.get(ic)):
			mf.get_doc.side_effect = _frappe_get_doc("FG", bom_map)
			self._fn("PARENT-A", 10, demand_map, set(), {}, {})
			self._fn("PARENT-B", 10, demand_map, set(), {}, {})
		# PARENT-A: 10×1=10, PARENT-B: 10×2=20 → total 30
		self.assertEqual(demand_map["CHILD-A"], 30.0)

	def test_bom_quantity_zero_defaults_to_one(self):
		# bom_quantity=0 → treated as 1
		bom = _bom_doc("BOM-001", 0, [_bom_item("CHILD-A", 5)])
		demand_map = {}
		cache = {"CHILD-A": "Raw Material"}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom", return_value="BOM-001"):
			mf.get_doc.side_effect = _frappe_get_doc("FG", {"BOM-001": bom})
			self._fn("FG", 10, demand_map, set(), cache, {})
		self.assertEqual(demand_map["CHILD-A"], 50.0)

	def test_exception_in_get_doc_silenced(self):
		# frappe.get_doc raises → should not propagate
		demand_map = {}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom", return_value="BOM-001"):
			mf.get_doc.side_effect = Exception("DB error")
			try:
				self._fn("FG", 10, demand_map, set(), {}, {})
			except Exception:
				self.fail("Exception should have been silenced")


# ---------------------------------------------------------------------------
# traverse_bom_for_parent_demand (full version)
# ---------------------------------------------------------------------------


class TestTraverseBomForParentDemand(unittest.TestCase):
	def setUp(self):
		from prakash_steel.prakash_steel.report.po_recomendation_for_psp.bom_traversal import (
			traverse_bom_for_parent_demand,
		)
		self._fn = traverse_bom_for_parent_demand

	def _call(
		self,
		parent_item="FG",
		parent_net_order_qty=100,
		demand_map=None,
		demand_details=None,
		item_buffer_map=None,
		item_sku_type_map=None,
		item_tog_map=None,
		open_so_map=None,
		stock_map=None,
		wip_map=None,
		open_po_map=None,
		mrq_map=None,
		moq_map=None,
		batch_size_map=None,
		get_item_details_func=None,
		bom=None,
	):
		demand_map = demand_map if demand_map is not None else {}
		demand_details = demand_details if demand_details is not None else {}
		item_buffer_map = item_buffer_map or {}
		item_sku_type_map = item_sku_type_map or {}
		item_tog_map = item_tog_map or {}
		open_so_map = open_so_map or {}
		stock_map = stock_map or {}
		wip_map = wip_map or {}
		open_po_map = open_po_map or {}
		mrq_map = mrq_map or {}
		moq_map = moq_map or {}
		batch_size_map = batch_size_map or {}
		get_item_details_func = get_item_details_func or (lambda ic: None)

		child_item = "CHILD-A"
		bom_doc = _bom_doc("BOM-FG", 1, [_bom_item(child_item, 1)])
		bom_name = bom or "BOM-FG"

		# Only return a BOM for the parent; children get None → recursion stops
		with patch(MODULE + ".frappe") as mf, \
			 patch(MODULE + ".get_default_bom", side_effect=lambda ic: bom_name if ic == parent_item else None):
			mf.get_doc.side_effect = _frappe_get_doc("FG", {bom_name: bom_doc})
			self._fn(
				parent_item, parent_net_order_qty, demand_map, demand_details,
				set(), {}, open_so_map, stock_map, wip_map, open_po_map,
				mrq_map, moq_map, batch_size_map, item_buffer_map,
				item_sku_type_map, item_tog_map, get_item_details_func,
			)
		return demand_map, demand_details

	def test_already_visited_skips(self):
		demand_map = {}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom") as mgb:
			self._fn(
				"FG", 100, demand_map, {}, {"FG"}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, lambda ic: None
			)
			mf.get_doc.assert_not_called()
		self.assertEqual(demand_map, {})

	def test_raw_material_stops(self):
		demand_map = {}
		with patch(MODULE + ".get_default_bom") as mgb:
			self._fn(
				"RM", 100, demand_map, {}, set(), {"RM": "Raw Material"}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, lambda ic: None
			)
			mgb.assert_not_called()
		self.assertEqual(demand_map, {})

	def test_demand_map_populated(self):
		demand_map, _ = self._call()
		self.assertIn("CHILD-A", demand_map)
		self.assertEqual(demand_map["CHILD-A"], 100.0)

	def test_demand_details_recorded(self):
		_, details = self._call()
		self.assertIn("CHILD-A", details)
		self.assertGreater(len(details["CHILD-A"]), 0)
		entry = details["CHILD-A"][0]
		self.assertIn("parent_item", entry)
		self.assertIn("demand_qty", entry)
		self.assertEqual(entry["parent_item"], "FG")

	def test_buffer_child_label_indicates_buffer(self):
		_, details = self._call(
			item_buffer_map={"CHILD-A": "Buffer"},
			item_sku_type_map={"CHILD-A": "BBMTA"},
		)
		entry = details["CHILD-A"][0]
		self.assertIn("Buffer item", entry.get("reason", ""))

	def test_non_buffer_child_uses_reason_string(self):
		_, details = self._call()
		entry = details["CHILD-A"][0]
		# Non-buffer shows "From parent" reasoning
		self.assertIn("From parent", entry.get("reason", ""))

	def test_get_item_details_func_called_per_child(self):
		called = []
		self._call(get_item_details_func=lambda ic: called.append(ic))
		self.assertIn("CHILD-A", called)


# ---------------------------------------------------------------------------
# traverse_bom_for_po
# ---------------------------------------------------------------------------


class TestTraverseBomForPo(unittest.TestCase):
	def setUp(self):
		from prakash_steel.prakash_steel.report.po_recomendation_for_psp.bom_traversal import (
			traverse_bom_for_po,
		)
		self._fn = traverse_bom_for_po

	def test_already_visited_skips(self):
		po_recs = {}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom") as mgb:
			self._fn("ITEM-A", 10, po_recs, {}, {"ITEM-A"}, {})
			mf.get_doc.assert_not_called()
		self.assertEqual(po_recs, {})

	def test_raw_material_stops(self):
		po_recs = {}
		with patch(MODULE + ".get_default_bom") as mgb:
			self._fn("RM", 10, po_recs, {}, set(), {"RM": "Raw Material"})
			mgb.assert_not_called()
		self.assertEqual(po_recs, {})

	def test_no_bom_stops(self):
		po_recs = {}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom", return_value=None):
			mf.get_doc.return_value = _item_doc("FG")
			self._fn("FG", 10, po_recs, {}, set(), {})
		self.assertEqual(po_recs, {})

	def test_stock_covers_requirement_no_po(self):
		bom = _bom_doc("BOM-001", 1, [_bom_item("CHILD-A", 1)])
		remaining_stock = {"CHILD-A": 20.0}
		po_recs = {}
		# CHILD-A is Raw Material so recursion stops after first level
		cache = {"CHILD-A": "Raw Material"}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom", return_value="BOM-001"):
			mf.get_doc.side_effect = _frappe_get_doc("FG", {"BOM-001": bom})
			self._fn("PARENT", 10, po_recs, remaining_stock, set(), cache)
		self.assertEqual(po_recs.get("CHILD-A", 0), 0.0)
		self.assertEqual(remaining_stock["CHILD-A"], 10.0)

	def test_no_stock_full_po(self):
		bom = _bom_doc("BOM-001", 1, [_bom_item("CHILD-A", 1)])
		remaining_stock = {"CHILD-A": 0.0}
		po_recs = {}
		cache = {"CHILD-A": "Raw Material"}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom", return_value="BOM-001"):
			mf.get_doc.side_effect = _frappe_get_doc("FG", {"BOM-001": bom})
			self._fn("PARENT", 10, po_recs, remaining_stock, set(), cache)
		self.assertEqual(po_recs["CHILD-A"], 10.0)

	def test_partial_stock_partial_po(self):
		bom = _bom_doc("BOM-001", 1, [_bom_item("CHILD-A", 1)])
		remaining_stock = {"CHILD-A": 4.0}
		po_recs = {}
		cache = {"CHILD-A": "Raw Material"}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom", return_value="BOM-001"):
			mf.get_doc.side_effect = _frappe_get_doc("FG", {"BOM-001": bom})
			self._fn("PARENT", 10, po_recs, remaining_stock, set(), cache)
		self.assertEqual(po_recs["CHILD-A"], 6.0)
		self.assertEqual(remaining_stock["CHILD-A"], 0.0)

	def test_stock_fetched_from_db_when_not_in_map(self):
		# CHILD-A not pre-populated → fetched via frappe.db.sql
		bom = _bom_doc("BOM-001", 1, [_bom_item("CHILD-A", 1)])
		remaining_stock = {}
		po_recs = {}
		cache = {"CHILD-A": "Raw Material"}
		mock_row = MagicMock()
		mock_row.stock = 3.0
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom", return_value="BOM-001"):
			mf.get_doc.side_effect = _frappe_get_doc("FG", {"BOM-001": bom})
			mf.db.sql.return_value = [mock_row]
			self._fn("PARENT", 10, po_recs, remaining_stock, set(), cache)
		# DB returned stock=3, need 10 → PO=7
		self.assertEqual(po_recs["CHILD-A"], 7.0)

	def test_po_accumulates_across_multiple_parents(self):
		bom_p1 = _bom_doc("BOM-P1", 1, [_bom_item("CHILD-A", 1)])
		bom_p2 = _bom_doc("BOM-P2", 1, [_bom_item("CHILD-A", 1)])
		bom_map = {"BOM-P1": bom_p1, "BOM-P2": bom_p2}
		# get_default_bom only returns BOM for P1 and P2; None for CHILD-A stops recursion
		dbom_map = {"P1": "BOM-P1", "P2": "BOM-P2"}
		remaining_stock = {"CHILD-A": 0.0}
		po_recs = {}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom", side_effect=lambda ic: dbom_map.get(ic)):
			mf.get_doc.side_effect = _frappe_get_doc("FG", bom_map)
			self._fn("P1", 10, po_recs, remaining_stock, set(), {})
			self._fn("P2", 5, po_recs, remaining_stock, set(), {})
		# P1→10 PO + P2→5 PO = 15
		self.assertEqual(po_recs["CHILD-A"], 15.0)

	def test_multiple_bom_items_each_tracked(self):
		bom = _bom_doc("BOM-001", 1, [_bom_item("CHILD-A", 2), _bom_item("CHILD-B", 3)])
		remaining_stock = {"CHILD-A": 0.0, "CHILD-B": 0.0}
		po_recs = {}
		cache = {"CHILD-A": "Raw Material", "CHILD-B": "Raw Material"}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom", return_value="BOM-001"):
			mf.get_doc.side_effect = _frappe_get_doc("FG", {"BOM-001": bom})
			self._fn("PARENT", 10, po_recs, remaining_stock, set(), cache)
		self.assertEqual(po_recs["CHILD-A"], 20.0)
		self.assertEqual(po_recs["CHILD-B"], 30.0)

	def test_item_group_cached(self):
		# Second call with same item uses cache, not frappe.get_doc for Item
		bom = _bom_doc("BOM-001", 1, [_bom_item("CHILD-A", 1)])
		cache = {}
		po_recs = {}
		with patch(MODULE + ".frappe") as mf, patch(MODULE + ".get_default_bom", return_value="BOM-001"):
			mf.get_doc.side_effect = _frappe_get_doc("FG", {"BOM-001": bom})
			# First call populates cache
			self._fn("PARENT", 10, po_recs, {"CHILD-A": 0.0}, set(), cache)
		# "PARENT" should now be in the cache
		self.assertIn("PARENT", cache)


if __name__ == "__main__":
	unittest.main()
