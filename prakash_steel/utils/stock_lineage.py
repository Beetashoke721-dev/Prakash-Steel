# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Trace stock that went out (e.g. a sale) back to the RB and end raw
material(s) it was actually made from, using the Stock Ledger.

ERPNext's FIFO stock_queue only holds [qty, rate] pairs - it doesn't say which
voucher a lot came from - so the FIFO queues are replayed here with every lot
tagged by the incoming SLE that created it. From a lot, the trace walks back:

- a Stock Entry transfer lot (the same Stock Entry Detail row has an outgoing
  SLE in the source warehouse) -> the lots that outgoing SLE drew from;
- a Manufacture finished-item lot -> every lot that Manufacture entry consumed
  (so whichever BOM / child items were actually used), split by consumed qty;
- and it stops at the first item that is not RB/BB - an RM (billet, or scrap /
  miss billet fed back in) or a BO - whose lot rate is the end-material rate,
  or at an RB/BB lot bought in through a Purchase Receipt/Invoice. Anything
  else (Material Receipt of an RB/BB, returns, subcontracting receipts) can't
  be traced further.

Quantities are SHARES of the traced-from quantity, not kg consumed: a sale of
3000 that drew 60/40 on two production batches splits 1800/1200 across their
RBs, and each RB's share splits again across its RMs in proportion to what
that batch consumed - so RB shares add up to the sold qty, and an RB's RM
shares add up to that RB's share (less anything untraced). Yield loss stays
in the report's Qty/Unit.

A Stock Reconciliation resets the item's FIFO queue in that warehouse to a
single lot of its qty_after_transaction at its valuation_rate, exactly as
ERPNext does - including rate-only reconciliations (actual_qty = 0) used to
revalue stock that had come in at zero.

A lot whose rate is below ``min_rate`` (stock received at a zero / placeholder
rate) counts as untraced rather than as cheap material.
"""

from collections import deque

import frappe
from frappe.utils import flt

TRACE_THROUGH_ITEM_TYPES = {"RB", "BB"}
PURCHASE_VOUCHER_TYPES = {"Purchase Receipt", "Purchase Invoice"}
QTY_EPSILON = 1e-9


class LotProfile:
	"""Per unit of a lot: ``parts`` maps (rb_item, rm_item) -> [share, value]
	(value = share * end-material rate), plus the share that is ``untraced``.
	rb_item is the RB/BO the material went through (None until an RB-level
	ancestor is reached); rm_item is None when the chain ended at the RB-level
	item itself (a BO, or an RB/BB that was bought in)."""

	__slots__ = ("parts", "untraced")

	def __init__(self, parts=None, untraced=0.0):
		self.parts = parts or {}
		self.untraced = untraced

	@classmethod
	def end(cls, key: tuple, rate: float) -> "LotProfile":
		return cls({key: [1.0, rate]})

	def add_scaled(self, other: "LotProfile", weight: float) -> None:
		for key, (share, value) in other.parts.items():
			part = self.parts.setdefault(key, [0.0, 0.0])
			part[0] += share * weight
			part[1] += value * weight
		self.untraced += other.untraced * weight

	def through_rb(self, rb_item: str) -> "LotProfile":
		"""This profile, with rb_item as the RB level wherever none was set yet."""
		parts = {}
		for (rb, rm), (share, value) in self.parts.items():
			part = parts.setdefault((rb or rb_item, rm), [0.0, 0.0])
			part[0] += share
			part[1] += value
		return LotProfile(parts, self.untraced)


UNTRACED = LotProfile(untraced=1.0)


class StockLineage:
	def __init__(self, sles: list, item_types: dict, min_rate: float):
		"""``sles``: non-cancelled SLEs in posting order (posting_datetime,
		creation), each with name, item_code, warehouse, actual_qty,
		stock_value_difference, valuation_rate, qty_after_transaction,
		voucher_type, voucher_no, voucher_detail_no and is_finished_item
		(Stock Entry Detail's, else None)."""
		self.item_types = item_types
		self.min_rate = min_rate
		self.sle_by_name = {}
		self.pieces = {}  # outgoing SLE name -> [(lot SLE name or None, qty)]
		self.outgoing_by_row = {}  # (voucher_type, voucher_no, voucher_detail_no) -> outgoing SLE names
		self.outgoing_by_voucher = {}  # (voucher_type, voucher_no) -> outgoing SLE names
		self.outgoing_by_detail = {}  # voucher_detail_no -> outgoing SLE names
		self._profiles = {}
		self._replay(sles)

	def _replay(self, sles: list) -> None:
		queues: dict[tuple, deque] = {}
		for sle in sles:
			self.sle_by_name[sle.name] = sle
			qty = flt(sle.actual_qty)
			queue = queues.setdefault((sle.item_code, sle.warehouse), deque())
			if sle.voucher_type == "Stock Reconciliation":
				queue.clear()
				if flt(sle.qty_after_transaction) > 0:
					queue.append([sle.name, flt(sle.qty_after_transaction)])
				continue
			if qty > 0:
				queue.append([sle.name, qty])
				continue
			if qty == 0:
				continue

			need = -qty
			pieces = []
			while need > QTY_EPSILON and queue:
				lot = queue[0]
				take = min(need, lot[1])
				pieces.append((lot[0], take))
				lot[1] -= take
				need -= take
				if lot[1] <= QTY_EPSILON:
					queue.popleft()
			if need > QTY_EPSILON:
				pieces.append((None, need))
			self.pieces[sle.name] = pieces

			self.outgoing_by_voucher.setdefault((sle.voucher_type, sle.voucher_no), []).append(sle.name)
			if sle.voucher_detail_no:
				self.outgoing_by_row.setdefault(
					(sle.voucher_type, sle.voucher_no, sle.voucher_detail_no), []
				).append(sle.name)
				self.outgoing_by_detail.setdefault(sle.voucher_detail_no, []).append(sle.name)

	def get_breakdown(self, voucher_detail_no: str) -> "frappe._dict | None":
		"""What the stock that went out on this voucher row (e.g. a Delivery
		Note Item / Sales Invoice Item name) was made from:

		- rate: share-weighted actual rate of the end materials (RM, or the
		  RB-level item where the chain ended there, e.g. a BO);
		- traced_percent: share of the out qty traced to a priced end material;
		- rbs: one entry per RB/BO it went through, largest first, each a dict
		  of rb (item; None for material that reached an RM without passing an
		  RB), qty, rate (the RB-level item's own rate when the chain ended at
		  it, e.g. a BO, else None) and rms: [(rm_item, qty, rate)], largest
		  first - the end raw materials that went into that RB.

		Qty is in units of the out qty (see module docstring). None when the
		row has no outgoing SLE or none of it could be traced."""
		names = self.outgoing_by_detail.get(voucher_detail_no)
		if not names:
			return None
		out_qty = sum(q for name in names for _lot, q in self.pieces[name])
		profile = self._combine(names)

		groups: dict[str | None, dict] = {}
		traced_share = traced_value = 0.0
		for (rb, rm), (share, value) in profile.parts.items():
			traced_share += share
			traced_value += value
			group = groups.setdefault(rb, {"qty": 0.0, "end_qty": 0.0, "end_value": 0.0, "rms": {}})
			group["qty"] += share * out_qty
			if rm:
				part = group["rms"].setdefault(rm, [0.0, 0.0])
				part[0] += share * out_qty
				part[1] += value * out_qty
			else:
				group["end_qty"] += share * out_qty
				group["end_value"] += value * out_qty

		if traced_share <= QTY_EPSILON:
			return None
		rbs = [
			frappe._dict(
				rb=rb,
				qty=group["qty"],
				rate=group["end_value"] / group["end_qty"] if group["end_qty"] > QTY_EPSILON else None,
				rms=sorted(
					((rm, qty, value / qty) for rm, (qty, value) in group["rms"].items() if qty > QTY_EPSILON),
					key=lambda r: -r[1],
				),
			)
			for rb, group in groups.items()
		]
		return frappe._dict(
			rate=traced_value / traced_share,
			traced_percent=traced_share * 100,
			rbs=sorted(rbs, key=lambda g: -g.qty),
		)

	def _combine(self, outgoing_names: list) -> LotProfile:
		"""Per unit of everything these outgoing SLEs drew, each lot weighted by
		the qty taken from it."""
		pieces = [piece for name in outgoing_names for piece in self.pieces[name]]
		total = sum(q for _lot, q in pieces)
		if total <= QTY_EPSILON:
			return UNTRACED
		profile = LotProfile()
		for lot, qty in pieces:
			profile.add_scaled(self._lot_profile(lot), qty / total)
		return profile

	def lot_rate(self, lot: str) -> float:
		sle = self.sle_by_name[lot]
		if sle.voucher_type == "Stock Reconciliation":
			return flt(sle.valuation_rate)
		return flt(sle.stock_value_difference) / flt(sle.actual_qty)

	def _lot_profile(self, lot: str | None) -> LotProfile:
		if lot is None:
			return UNTRACED
		if lot in self._profiles:
			return self._profiles[lot]
		self._profiles[lot] = UNTRACED  # guard against any malformed self-reference
		self._profiles[lot] = self._compute_lot_profile(self.sle_by_name[lot])
		return self._profiles[lot]

	def _compute_lot_profile(self, sle) -> LotProfile:
		item_type = self.item_types.get(sle.item_code)
		traces_through = item_type in TRACE_THROUGH_ITEM_TYPES

		if not traces_through or sle.voucher_type in PURCHASE_VOUCHER_TYPES:
			rate = self.lot_rate(sle.name)
			if rate < self.min_rate:
				return UNTRACED
			# RB-level items (BO, or an RB/BB bought in) end the chain at the RB
			# level with no RM under them; anything else is an end raw material.
			if item_type == "BO" or traces_through:
				return LotProfile.end((sle.item_code, None), rate)
			return LotProfile.end((None, sle.item_code), rate)

		if sle.voucher_type != "Stock Entry":
			return UNTRACED

		source = self.outgoing_by_row.get((sle.voucher_type, sle.voucher_no, sle.voucher_detail_no))
		if source:
			return self._combine(source)
		if sle.is_finished_item:
			profile = self._combine(self.outgoing_by_voucher.get((sle.voucher_type, sle.voucher_no), []))
			return profile.through_rb(sle.item_code) if item_type == "RB" else profile
		return UNTRACED


def load_stock_lineage(to_date, min_rate: float) -> StockLineage:
	"""Build a StockLineage over every non-cancelled SLE up to ``to_date``."""
	sles = frappe.db.sql(
		"""
		SELECT sle.name, sle.item_code, sle.warehouse, sle.actual_qty, sle.stock_value_difference,
			sle.valuation_rate, sle.qty_after_transaction, sle.voucher_type,
			sle.voucher_no, sle.voucher_detail_no, sed.is_finished_item
		FROM `tabStock Ledger Entry` sle
		LEFT JOIN `tabStock Entry Detail` sed
			ON sle.voucher_type = 'Stock Entry' AND sed.name = sle.voucher_detail_no
		WHERE sle.is_cancelled = 0 AND sle.posting_date <= %(to_date)s
			AND (sle.actual_qty != 0 OR sle.voucher_type = 'Stock Reconciliation')
		ORDER BY sle.posting_datetime, sle.creation
		""",
		{"to_date": to_date},
		as_dict=True,
	)
	item_types = dict(frappe.db.sql("SELECT name, custom_item_type FROM `tabItem`"))
	return StockLineage(sles, item_types, min_rate)
