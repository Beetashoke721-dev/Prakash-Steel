# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
Unit tests for columns.py — pure, no DB.
"""

import unittest

from prakash_steel.prakash_steel.report.po_recomendation_for_psp.columns import get_columns


class TestGetColumns(unittest.TestCase):
	def _fieldnames(self, filters):
		return {c["fieldname"] for c in get_columns(filters)}

	def test_no_filters_defaults_to_non_buffer_non_sell(self):
		fieldnames = self._fieldnames(None)
		self.assertIn("priority", fieldnames)
		self.assertIn("requirement", fieldnames)
		self.assertNotIn("tog", fieldnames)
		self.assertNotIn("child_item_code", fieldnames)

	def test_buffer_flag_shows_buffer_columns_hides_priority_requirement(self):
		fieldnames = self._fieldnames({"buffer_flag": 1})
		self.assertIn("tog", fieldnames)
		self.assertIn("toy", fieldnames)
		self.assertIn("on_hand_colour", fieldnames)
		self.assertNotIn("priority", fieldnames)
		self.assertNotIn("requirement", fieldnames)

	def test_buffer_flag_as_string_true_is_treated_as_buffer(self):
		fieldnames = self._fieldnames({"buffer_flag": "1"})
		self.assertIn("tog", fieldnames)

	def test_non_buffer_shows_open_so_qualified_not_open_so(self):
		fieldnames = self._fieldnames({"buffer_flag": 0})
		self.assertIn("open_so_qualified", fieldnames)
		self.assertNotIn("open_so", fieldnames)

	def test_sell_filter_adds_child_columns(self):
		without_sell = self._fieldnames({"sell": 0})
		with_sell = self._fieldnames({"sell": 1})
		self.assertNotIn("child_item_code", without_sell)
		self.assertIn("child_item_code", with_sell)
		self.assertIn("child_stock_shortage", with_sell)

	def test_core_recommendation_columns_always_present(self):
		for filters in ({}, {"buffer_flag": 1}, {"buffer_flag": 0, "sell": 1}):
			fieldnames = self._fieldnames(filters)
			for expected in (
				"item_code",
				"sku_type",
				"order_recommendation",
				"net_po_recommendation",
				"or_with_moq_batch_size",
				"moq",
				"batch_size",
			):
				self.assertIn(expected, fieldnames, f"{expected} missing for filters={filters}")


if __name__ == "__main__":
	unittest.main()
