# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for Store & Service Item Purchase Register helpers — no DB / no site."""

from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

MOD = importlib.import_module(
	"prakash_steel.prakash_steel.page.store_svc_item_purchase_reg.store_svc_item_purchase_reg"
)


class TestTopParties(unittest.TestCase):
	def test_ranks_by_amount_and_limits(self):
		rows = [
			{"supplier": "S1", "supplier_name": "Alpha", "amount": 100},
			{"supplier": "S2", "supplier_name": "Beta", "amount": 500},
			{"supplier": "S1", "supplier_name": "Alpha", "amount": 50},
			{"supplier": "S3", "supplier_name": "Gamma", "amount": 200},
			{"supplier": "S4", "supplier_name": "Delta", "amount": 10},
			{"supplier": "S5", "supplier_name": "Epsilon", "amount": 300},
			{"supplier": "S6", "supplier_name": "Zeta", "amount": 80},
		]
		top = MOD._top_parties(rows, limit=5)
		self.assertEqual(len(top), 5)
		self.assertEqual([r["supplier"] for r in top], ["S2", "S5", "S3", "S1", "S6"])
		self.assertEqual(top[3]["amount"], 150.0)

	def test_empty_rows(self):
		self.assertEqual(MOD._top_parties([]), [])


class TestValidatePartyType(unittest.TestCase):
	def test_accepts_regular_and_service(self):
		self.assertEqual(MOD._validate_party_type("regular"), "regular")
		self.assertEqual(MOD._validate_party_type("SERVICE"), "service")

	def test_rejects_unknown(self):
		with patch.object(MOD.frappe, "throw", side_effect=Exception("bad")):
			with self.assertRaises(Exception):
				MOD._validate_party_type("other")


class TestItemFilterSql(unittest.TestCase):
	def test_regular_uses_store_item(self):
		sql = MOD._item_filter_sql("regular")
		self.assertIn("custom_store_item", sql)

	def test_service_uses_item_group(self):
		sql = MOD._item_filter_sql("service")
		self.assertIn("item_group", sql)
		self.assertIn("service_item_group", sql)


class TestOptionalFiltersSql(unittest.TestCase):
	def test_empty_when_no_filters(self):
		sql, values = MOD._optional_filters_sql()
		self.assertEqual(sql, "")
		self.assertEqual(values, {})

	def test_supplier_and_item(self):
		sql, values = MOD._optional_filters_sql(supplier="S1", item_code="I1")
		self.assertIn("pi.supplier", sql)
		self.assertIn("pii.item_code", sql)
		self.assertEqual(values["supplier"], "S1")
		self.assertEqual(values["item_code"], "I1")


if __name__ == "__main__":
	unittest.main()

