# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Shared test utilities — no production imports, no DB required."""


class _Row(dict):
	"""Dict with attribute access — mimics frappe._dict for SQL result rows.

	Use this in tests that pass rows through ``assign_hbt_labels``, which
	writes via item access (``row["hbt"]``) and reads via ``row.get(key)``.
	"""

	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(key)

	def __setattr__(self, key, val):
		self[key] = val


# ---------------------------------------------------------------------------
# Tests for _Row
# ---------------------------------------------------------------------------

import unittest


class TestRow(unittest.TestCase):
	def test_dict_access(self):
		row = _Row({"item_code": "ITEM-001", "qty": 10})
		self.assertEqual(row["item_code"], "ITEM-001")
		self.assertEqual(row["qty"], 10)

	def test_attribute_read(self):
		row = _Row({"item_code": "ITEM-001"})
		self.assertEqual(row.item_code, "ITEM-001")

	def test_attribute_write(self):
		row = _Row()
		row.hbt = "H"
		self.assertEqual(row["hbt"], "H")

	def test_dict_write_readable_as_attr(self):
		row = _Row()
		row["label"] = "High"
		self.assertEqual(row.label, "High")

	def test_missing_attribute_raises_attribute_error(self):
		row = _Row()
		with self.assertRaises(AttributeError):
			_ = row.nonexistent_key

	def test_get_returns_none_for_missing_key(self):
		row = _Row({"a": 1})
		self.assertIsNone(row.get("missing"))

	def test_get_returns_default(self):
		row = _Row()
		self.assertEqual(row.get("qty", 0), 0)

	def test_is_a_dict(self):
		row = _Row({"x": 1})
		self.assertIsInstance(row, dict)

	def test_multiple_fields(self):
		row = _Row({"a": 1, "b": 2, "c": 3})
		row.d = 4
		self.assertEqual(len(row), 4)
		self.assertEqual(row.d, 4)


if __name__ == "__main__":
	unittest.main()
