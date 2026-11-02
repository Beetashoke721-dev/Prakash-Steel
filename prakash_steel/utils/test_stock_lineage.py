# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for utils/stock_lineage.py — no DB required."""

import unittest

import frappe

from prakash_steel.utils.stock_lineage import StockLineage

ITEM_TYPES = {
	"BILLET": "RM",
	"RB1": "RB",
	"RB_B": "RB",
	"RB_C": "RB",
	"RM_E": "RM",
	"RM_F": "RM",
	"RM_G": "RM",
	"ITEM_A": "BB",
	"BB1": "BB",
	"BO1": "BO",
	"SCRAP": "Scrap",
}


def _sle(name, item, wh, qty, value, vtype="Stock Entry", vno=None, detail=None, fg=None, **extra):
	return frappe._dict(
		name=name,
		item_code=item,
		warehouse=wh,
		actual_qty=qty,
		stock_value_difference=value,
		voucher_type=vtype,
		voucher_no=vno or name,
		voucher_detail_no=detail,
		is_finished_item=fg,
		valuation_rate=extra.get("valuation_rate", 0),
		qty_after_transaction=extra.get("qty_after_transaction", 0),
	)


def _groups(result):
	"""Breakdown rbs as plain, rounded tuples for comparison."""
	return [
		(
			g.rb,
			round(g.qty, 6),
			round(g.rate, 6) if g.rate is not None else None,
			[(rm, round(q, 6), round(r, 6)) for rm, q, r in g.rms],
		)
		for g in result.rbs
	]


def _rolling_and_bright_chain():
	"""Billet bought at 38.50 -> rolled to RB (with scrap credit) -> moved ->
	drawn to BB -> sold. Mirrors B 50mm Square MS / MAT-STE-2026-07130."""
	return [
		_sle("pr1", "BILLET", "Store", 1000, 38500, "Purchase Receipt", "PR-1", "pri1"),
		# RB Manufacture: 1000 billet -> 960 RB + 20 scrap (scrap valued, so RB < billet*ratio)
		_sle("m1-out", "BILLET", "Store", -1000, -38500, vno="MFG-RB", detail="r1"),
		_sle("m1-fg", "RB1", "Mill", 960, 37820, vno="MFG-RB", detail="r2", fg=1),
		_sle("m1-scrap", "SCRAP", "Mill", 20, 680, vno="MFG-RB", detail="r3", fg=0),
		# Transfer RB Mill -> Bright
		_sle("t1-out", "RB1", "Mill", -960, -37820, vno="TR-1", detail="t1"),
		_sle("t1-in", "RB1", "Bright", 960, 37820, vno="TR-1", detail="t1"),
		# BB Manufacture: 960 RB -> 930 BB
		_sle("m2-out", "RB1", "Bright", -960, -37820, vno="MFG-BB", detail="b1"),
		_sle("m2-fg", "BB1", "Bright", 930, 37820, vno="MFG-BB", detail="b2", fg=1),
		# Sale
		_sle("dn1", "BB1", "Bright", -465, -18910, "Delivery Note", "DN-1", "dni1"),
	]


class TestStockLineage(unittest.TestCase):
	def test_traces_bb_sale_back_to_billet_rate(self):
		lineage = StockLineage(_rolling_and_bright_chain(), ITEM_TYPES, 1.0)

		result = lineage.get_breakdown("dni1")

		self.assertAlmostEqual(result.rate, 38.5)
		self.assertAlmostEqual(result.traced_percent, 100)

	def test_mixed_billet_lots_are_qty_weighted(self):
		sles = [
			_sle("pr1", "BILLET", "Store", 600, 600 * 38, "Purchase Receipt", "PR-1", "a"),
			_sle("pr2", "BILLET", "Store", 600, 600 * 40, "Purchase Receipt", "PR-2", "b"),
			_sle("m-out", "BILLET", "Store", -1000, -(600 * 38 + 400 * 40), vno="MFG", detail="c"),
			_sle("m-fg", "RB1", "Mill", 1000, 600 * 38 + 400 * 40, vno="MFG", detail="d", fg=1),
			_sle("si1", "RB1", "Mill", -500, -19400, "Sales Invoice", "SI-1", "sii1"),
		]
		lineage = StockLineage(sles, ITEM_TYPES, 1.0)

		result = lineage.get_breakdown("sii1")

		self.assertAlmostEqual(result.rate, (600 * 38 + 400 * 40) / 1000)

	def test_bb_from_bo_stops_at_bo_rate(self):
		sles = [
			_sle("bo-in", "BO1", "Store", 100, 5000, "Purchase Receipt", "PR-1", "a"),
			_sle("m-out", "BO1", "Store", -100, -5000, vno="MFG", detail="b"),
			_sle("m-fg", "BB1", "Bright", 95, 5000, vno="MFG", detail="c", fg=1),
			_sle("dn1", "BB1", "Bright", -95, -5000, "Delivery Note", "DN-1", "dni1"),
		]
		lineage = StockLineage(sles, ITEM_TYPES, 1.0)

		self.assertAlmostEqual(lineage.get_breakdown("dni1").rate, 50)

	def test_rb_from_material_receipt_is_untraced_and_left_out_of_average(self):
		sles = _rolling_and_bright_chain()[:4] + [
			# 960 more RB in Mill with no production record (opening / old rolling entry)
			_sle("mr1", "RB1", "Mill", 960, 960 * 45, vno="MR-1", detail="m1", fg=0),
		]
		# BB made from 960 traced RB + 960 untraced RB, sold whole.
		sles += [
			_sle("m2-out", "RB1", "Mill", -1920, -(37820 + 960 * 45), vno="MFG-BB", detail="b1"),
			_sle("m2-fg", "BB1", "Bright", 1860, 37820 + 960 * 45, vno="MFG-BB", detail="b2", fg=1),
			_sle("dn1", "BB1", "Bright", -1860, -(37820 + 960 * 45), "Delivery Note", "DN-1", "dni1"),
		]
		lineage = StockLineage(sles, ITEM_TYPES, 1.0)

		result = lineage.get_breakdown("dni1")

		self.assertAlmostEqual(result.rate, 38.5)
		self.assertAlmostEqual(result.traced_percent, 50)

	def test_placeholder_rate_billet_is_untraced(self):
		sles = [
			_sle("mr1", "BILLET", "Store", 1000, 10, vno="MR-1", detail="a"),  # Rs 0.01/kg
			_sle("m-out", "BILLET", "Store", -1000, -10, vno="MFG", detail="b"),
			_sle("m-fg", "RB1", "Mill", 1000, 10, vno="MFG", detail="c", fg=1),
			_sle("si1", "RB1", "Mill", -1000, -10, "Sales Invoice", "SI-1", "sii1"),
		]
		lineage = StockLineage(sles, ITEM_TYPES, 1.0)

		self.assertIsNone(lineage.get_breakdown("sii1"))

	def test_stock_reconciliation_revalues_the_queue(self):
		sles = [
			_sle("mr1", "BILLET", "Store", 1000, 0, vno="MR-1", detail="a"),
			_sle(
				"reco",
				"BILLET",
				"Store",
				0,
				42540,
				"Stock Reconciliation",
				"RECO-1",
				"r",
				valuation_rate=42.54,
				qty_after_transaction=1000,
			),
			_sle("m-out", "BILLET", "Store", -500, -21270, vno="MFG", detail="b"),
			_sle("m-fg", "RB1", "Mill", 480, 21270, vno="MFG", detail="c", fg=1),
			_sle("si1", "RB1", "Mill", -480, -21270, "Sales Invoice", "SI-1", "sii1"),
		]
		lineage = StockLineage(sles, ITEM_TYPES, 1.0)

		self.assertAlmostEqual(lineage.get_breakdown("sii1").rate, 42.54)

	def test_sold_rm_is_its_own_end_material(self):
		sles = [
			_sle("pr1", "BILLET", "Store", 100, 3850, "Purchase Receipt", "PR-1", "a"),
			_sle("si1", "BILLET", "Store", -40, -1540, "Sales Invoice", "SI-1", "sii1"),
		]
		lineage = StockLineage(sles, ITEM_TYPES, 1.0)

		self.assertAlmostEqual(lineage.get_breakdown("sii1").rate, 38.5)

	def test_users_example_two_productions_with_their_own_rms(self):
		"""Item A 3000 sold from two BB batches: 1800 made with RB B (itself
		rolled from RM E 800 + RM F 1000) and 1200 made with RB C (from RM G)."""
		sles = [
			_sle("e", "RM_E", "Store", 800, 800 * 38, "Purchase Receipt", "PR-E", "pe"),
			_sle("f", "RM_F", "Store", 1000, 1000 * 40, "Purchase Receipt", "PR-F", "pf"),
			_sle("g", "RM_G", "Store", 1200, 1200 * 42, "Purchase Receipt", "PR-G", "pg"),
			# Roll RB B from E + F, RB C from G
			_sle("rb-e", "RM_E", "Store", -800, -800 * 38, vno="ROLL-B", detail="rb1"),
			_sle("rb-f", "RM_F", "Store", -1000, -1000 * 40, vno="ROLL-B", detail="rb2"),
			_sle("rb-b", "RB_B", "Mill", 1800, 70400, vno="ROLL-B", detail="rb3", fg=1),
			_sle("rc-g", "RM_G", "Store", -1200, -1200 * 42, vno="ROLL-C", detail="rc1"),
			_sle("rc-c", "RB_C", "Mill", 1200, 50400, vno="ROLL-C", detail="rc2", fg=1),
			# Draw A from B, then from C
			_sle("ab-b", "RB_B", "Mill", -1800, -70400, vno="DRAW-1", detail="d1"),
			_sle("ab-a", "ITEM_A", "Bright", 1800, 70400, vno="DRAW-1", detail="d2", fg=1),
			_sle("ac-c", "RB_C", "Mill", -1200, -50400, vno="DRAW-2", detail="d3"),
			_sle("ac-a", "ITEM_A", "Bright", 1200, 50400, vno="DRAW-2", detail="d4", fg=1),
			_sle("dn1", "ITEM_A", "Bright", -3000, -120800, "Delivery Note", "DN-1", "dni1"),
		]
		lineage = StockLineage(sles, ITEM_TYPES, 1.0)

		result = lineage.get_breakdown("dni1")

		self.assertEqual(
			_groups(result),
			[
				("RB_B", 1800, None, [("RM_F", 1000, 40), ("RM_E", 800, 38)]),
				("RB_C", 1200, None, [("RM_G", 1200, 42)]),
			],
		)
		self.assertAlmostEqual(result.rate, (800 * 38 + 1000 * 40 + 1200 * 42) / 3000)
		self.assertAlmostEqual(result.traced_percent, 100)

	def test_sold_rb_is_its_own_rb_with_its_rms_under_it(self):
		sles = _rolling_and_bright_chain()[:4] + [
			_sle("si1", "RB1", "Mill", -480, -18910, "Sales Invoice", "SI-1", "sii1"),
		]
		lineage = StockLineage(sles, ITEM_TYPES, 1.0)

		result = lineage.get_breakdown("sii1")

		self.assertEqual(_groups(result), [("RB1", 480, None, [("BILLET", 480, 38.5)])])

	def test_bb_from_bo_lists_bo_as_rb_with_its_own_rate_and_no_rm(self):
		sles = [
			_sle("bo-in", "BO1", "Store", 100, 5000, "Purchase Receipt", "PR-1", "a"),
			_sle("m-out", "BO1", "Store", -100, -5000, vno="MFG", detail="b"),
			_sle("m-fg", "BB1", "Bright", 95, 5000, vno="MFG", detail="c", fg=1),
			_sle("dn1", "BB1", "Bright", -95, -5000, "Delivery Note", "DN-1", "dni1"),
		]
		result = StockLineage(sles, ITEM_TYPES, 1.0).get_breakdown("dni1")

		self.assertEqual(_groups(result), [("BO1", 95, 50, [])])

	def test_unknown_detail_returns_none(self):
		lineage = StockLineage(_rolling_and_bright_chain(), ITEM_TYPES, 1.0)

		self.assertIsNone(lineage.get_breakdown("nope"))


if __name__ == "__main__":
	unittest.main()
