# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for utils/mrp_dates.py — no DB required.

Exercises compute_required_by_and_transaction_dates() directly with
explicit maps (lead_time_map, decoupled_lead_time_map, earliest_so_map,
child_to_parents_map), matching the worked examples given for the feature:
- Non-buffer chain A -> B -> C driven by an Open SO on the root item.
- Buffer item D, and a buffer-with-inserted-non-buffer-child D -> S -> E.
- A shared child reached from two parents: the earlier date wins.
- An item with no traceable source at all: falls back to today + lead_time.
"""

import unittest
from datetime import date
from unittest.mock import patch

MOD = "prakash_steel.utils.mrp_dates"

TODAY = "2026-07-22"


def _mocked_today():
	from prakash_steel.utils.mrp_dates import compute_required_by_and_transaction_dates

	return patch(MOD + ".today", return_value=TODAY), compute_required_by_and_transaction_dates


class TestNonBufferChain(unittest.TestCase):
	"""A(non-buffer, LT5) -> B(non-buffer, LT7) -> C(non-buffer, LT10), SO due 2026-08-15."""

	def test_chain_dates_match_worked_example(self):
		today_patch, compute = _mocked_today()
		with today_patch:
			result = compute(
				net_order_recommendations={"A": 10, "B": 10, "C": 10},
				item_buffer_map={"A": "Non-Buffer", "B": "Non-Buffer", "C": "Non-Buffer"},
				lead_time_map={"A": 5, "B": 7, "C": 10},
				decoupled_lead_time_map={"A": 22, "B": 17, "C": 10},
				earliest_so_map={"A": date(2026, 8, 15)},
				child_to_parents_map={"B": ["A"], "C": ["B"]},
			)

		self.assertEqual(result["A"]["required_by"], date(2026, 8, 15))
		self.assertEqual(result["A"]["transaction_date"], date(2026, 8, 10))

		self.assertEqual(result["B"]["required_by"], date(2026, 8, 10))
		self.assertEqual(result["B"]["transaction_date"], date(2026, 8, 3))

		self.assertEqual(result["C"]["required_by"], date(2026, 8, 3))
		self.assertEqual(result["C"]["transaction_date"], date(2026, 7, 24))


class TestBufferItems(unittest.TestCase):
	"""D(buffer, own decoupled_lead_time=5) with "today" = 2026-07-22."""

	def test_buffer_item_uses_today_plus_decoupled_lead_time(self):
		today_patch, compute = _mocked_today()
		with today_patch:
			result = compute(
				net_order_recommendations={"D": 5},
				item_buffer_map={"D": "Buffer"},
				lead_time_map={"D": 5},
				decoupled_lead_time_map={"D": 5},
				earliest_so_map={},
				child_to_parents_map={},
			)

		self.assertEqual(result["D"]["required_by"], date(2026, 7, 27))
		self.assertEqual(result["D"]["transaction_date"], date(2026, 7, 22))

	def test_buffer_item_pushes_transaction_date_to_non_buffer_child(self):
		"""D(buffer, decoupled_lead_time=5) -> S(non-buffer, LT2) -> E(buffer).

		S is not itself buffer, so it inherits required_by = transaction_date(D).
		E is buffer, so it ignores S entirely and uses its own formula.

		S's raw transaction_date (required_by - lead_time) would fall on
		2026-07-20, two days before "today" (2026-07-22) - that's clamped up
		to today so no backdated Material Request gets raised.
		"""
		today_patch, compute = _mocked_today()
		with today_patch:
			result = compute(
				net_order_recommendations={"D": 5, "S": 5, "E": 5},
				item_buffer_map={"D": "Buffer", "S": "Non-Buffer", "E": "Buffer"},
				lead_time_map={"D": 5, "S": 2, "E": 3},
				decoupled_lead_time_map={"D": 5, "E": 9},
				earliest_so_map={},
				child_to_parents_map={"S": ["D"], "E": ["S"]},
			)

		self.assertEqual(result["D"]["required_by"], date(2026, 7, 27))
		self.assertEqual(result["D"]["transaction_date"], date(2026, 7, 22))

		self.assertEqual(result["S"]["required_by"], date(2026, 7, 22))
		self.assertEqual(result["S"]["transaction_date"], date(2026, 7, 22))

		# E is buffer: unaffected by S's transaction_date, uses its own decoupled_lead_time.
		self.assertEqual(result["E"]["required_by"], date(2026, 7, 31))
		self.assertEqual(result["E"]["transaction_date"], date(2026, 7, 28))


class TestMultiParentAndFallback(unittest.TestCase):
	def test_shared_child_takes_earliest_of_multiple_parents(self):
		"""X is a BOM component of both P1 (earlier need) and P2 (later need)."""
		today_patch, compute = _mocked_today()
		with today_patch:
			result = compute(
				net_order_recommendations={"P1": 10, "P2": 10, "X": 10},
				item_buffer_map={"P1": "Non-Buffer", "P2": "Non-Buffer", "X": "Non-Buffer"},
				lead_time_map={"P1": 2, "P2": 2, "X": 1},
				decoupled_lead_time_map={},
				earliest_so_map={"P1": date(2026, 8, 1), "P2": date(2026, 8, 10)},
				child_to_parents_map={"X": ["P1", "P2"]},
			)

		# P1 transaction_date = 2026-07-30, P2 transaction_date = 2026-08-08 -> earliest wins.
		self.assertEqual(result["X"]["required_by"], date(2026, 7, 30))
		self.assertEqual(result["X"]["transaction_date"], date(2026, 7, 29))

	def test_shared_child_with_mixed_buffer_and_non_buffer_parents(self):
		"""B is a BOM component of both A (buffer) and C (non-buffer).

		Each parent's required_by is computed with its own rules (A: today +
		decoupled_lead_time; C: driven by its own Open SO), then whichever
		parent's resulting transaction_date is earlier wins for B - the
		parent's buffer/non-buffer flag itself plays no direct role in the
		push-down step, only in how that parent's own date was derived.
		"""
		today_patch, compute = _mocked_today()
		with today_patch:
			result = compute(
				net_order_recommendations={"A": 5, "C": 5, "B": 5},
				item_buffer_map={"A": "Buffer", "C": "Non-Buffer", "B": "Non-Buffer"},
				lead_time_map={"A": 4, "C": 6, "B": 3},
				decoupled_lead_time_map={"A": 8},
				earliest_so_map={"C": date(2026, 8, 15)},
				child_to_parents_map={"B": ["A", "C"]},
			)

		# A: required_by = today+8 = 2026-07-30, transaction_date = 2026-07-26
		self.assertEqual(result["A"]["required_by"], date(2026, 7, 30))
		self.assertEqual(result["A"]["transaction_date"], date(2026, 7, 26))

		# C: driven by its own Open SO, transaction_date = 2026-08-09
		self.assertEqual(result["C"]["required_by"], date(2026, 8, 15))
		self.assertEqual(result["C"]["transaction_date"], date(2026, 8, 9))

		# B takes the earlier of the two parent transaction_dates: A's (2026-07-26) beats C's (2026-08-09).
		self.assertEqual(result["B"]["required_by"], date(2026, 7, 26))
		self.assertEqual(result["B"]["transaction_date"], date(2026, 7, 23))

	def test_shared_child_with_own_so_competes_against_both_mixed_parents(self):
		"""Same A(buffer)/C(non-buffer) parents as above, but B also has its
		own Open SO due 2026-07-25 - earlier than both parents' pushed-down
		dates (A: 07-26, C: 08-09). B's own SO must win over both.
		"""
		today_patch, compute = _mocked_today()
		with today_patch:
			result = compute(
				net_order_recommendations={"A": 5, "C": 5, "B": 5},
				item_buffer_map={"A": "Buffer", "C": "Non-Buffer", "B": "Non-Buffer"},
				lead_time_map={"A": 4, "C": 6, "B": 3},
				decoupled_lead_time_map={"A": 8},
				earliest_so_map={"C": date(2026, 8, 15), "B": date(2026, 7, 25)},
				child_to_parents_map={"B": ["A", "C"]},
			)

		# Candidates for B: [own SO 07-25, from A 07-26, from C 08-09] -> earliest (own SO) wins.
		self.assertEqual(result["B"]["required_by"], date(2026, 7, 25))
		self.assertEqual(result["B"]["transaction_date"], date(2026, 7, 22))

	def test_no_traceable_source_falls_back_to_today_plus_lead_time(self):
		today_patch, compute = _mocked_today()
		with today_patch:
			result = compute(
				net_order_recommendations={"ORPHAN": 5},
				item_buffer_map={"ORPHAN": "Non-Buffer"},
				lead_time_map={"ORPHAN": 4},
				decoupled_lead_time_map={},
				earliest_so_map={},
				child_to_parents_map={},
			)

		self.assertEqual(result["ORPHAN"]["required_by"], date(2026, 7, 26))
		self.assertEqual(result["ORPHAN"]["transaction_date"], date(2026, 7, 22))

	def test_items_with_zero_or_negative_recommendation_are_skipped(self):
		today_patch, compute = _mocked_today()
		with today_patch:
			result = compute(
				net_order_recommendations={"A": 0, "B": -5},
				item_buffer_map={"A": "Non-Buffer", "B": "Non-Buffer"},
				lead_time_map={"A": 1, "B": 1},
				decoupled_lead_time_map={},
				earliest_so_map={},
				child_to_parents_map={},
			)

		self.assertEqual(result, {})


class TestNoBackdatedDates(unittest.TestCase):
	"""No Material Request should ever get a date before today - any computed
	required_by/transaction_date earlier than today is clamped up to today.
	"""

	def test_overdue_open_so_clamps_required_by_and_transaction_date(self):
		"""OVERDUE(non-buffer, LT3) has an Open SO delivery_date already in the
		past (2026-07-10, 12 days before "today" 2026-07-22). Both the raw
		required_by (07-10) and the raw transaction_date (07-07) are before
		today, so both clamp up to 2026-07-22.
		"""
		today_patch, compute = _mocked_today()
		with today_patch:
			result = compute(
				net_order_recommendations={"OVERDUE": 5},
				item_buffer_map={"OVERDUE": "Non-Buffer"},
				lead_time_map={"OVERDUE": 3},
				decoupled_lead_time_map={},
				earliest_so_map={"OVERDUE": date(2026, 7, 10)},
				child_to_parents_map={},
			)

		self.assertEqual(result["OVERDUE"]["required_by"], date(2026, 7, 22))
		self.assertEqual(result["OVERDUE"]["transaction_date"], date(2026, 7, 22))

	def test_clamped_parent_transaction_date_still_propagates_to_child(self):
		"""P(non-buffer, LT10) has an overdue Open SO (2026-07-15, before
		today). P's raw transaction_date (07-05) clamps to today (07-22).
		CHILD(non-buffer, LT1), sourced only from P, must inherit the
		clamped 07-22 - not the raw, backdated 07-05.
		"""
		today_patch, compute = _mocked_today()
		with today_patch:
			result = compute(
				net_order_recommendations={"P": 5, "CHILD": 5},
				item_buffer_map={"P": "Non-Buffer", "CHILD": "Non-Buffer"},
				lead_time_map={"P": 10, "CHILD": 1},
				decoupled_lead_time_map={},
				earliest_so_map={"P": date(2026, 7, 15)},
				child_to_parents_map={"CHILD": ["P"]},
			)

		self.assertEqual(result["P"]["required_by"], date(2026, 7, 22))
		self.assertEqual(result["P"]["transaction_date"], date(2026, 7, 22))

		self.assertEqual(result["CHILD"]["required_by"], date(2026, 7, 22))
		# CHILD's own raw transaction_date (07-22 - 1 day = 07-21) is still
		# before today, so it clamps again to today.
		self.assertEqual(result["CHILD"]["transaction_date"], date(2026, 7, 22))


if __name__ == "__main__":
	unittest.main()
