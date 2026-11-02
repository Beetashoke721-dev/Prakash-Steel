# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for Desc Code Wise Summary page — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa"


class TestValidateFilters(unittest.TestCase):
	def test_to_date_without_from_date_throws(self):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_validate_filters,
		)

		with self.assertRaises(Exception):
			_validate_filters({"to_date": "2026-08-13"})

	def test_from_after_to_throws(self):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_validate_filters,
		)

		with self.assertRaises(Exception):
			_validate_filters({"from_date": "2026-08-13", "to_date": "2026-08-01"})

	def test_valid_range_does_not_throw(self):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_validate_filters,
		)

		_validate_filters({"from_date": "2026-08-01", "to_date": "2026-08-13"})

	def test_no_dates_does_not_throw(self):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_validate_filters,
		)

		_validate_filters({})


class TestAppendTotalRow(unittest.TestCase):
	def test_empty_returns_empty(self):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_append_total_row,
		)

		self.assertEqual(_append_total_row([]), [])

	def test_sums_numeric_fields(self):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_append_total_row,
		)

		rows = [
			{
				"desc_code": "A",
				"hsn_code": "1001",
				"qty": 10,
				"taxable_value": 100.0,
				"cgst_amt": 9.0,
				"sgst_amt": 9.0,
				"igst_amt": 0.0,
				"total_taxes_and_charges": 18.0,
				"gross_total": 118.0,
			},
			{
				"desc_code": "B",
				"hsn_code": "1002",
				"qty": 5,
				"taxable_value": 50.0,
				"cgst_amt": 0.0,
				"sgst_amt": 0.0,
				"igst_amt": 9.0,
				"total_taxes_and_charges": 9.0,
				"gross_total": 59.0,
			},
		]
		out = _append_total_row(rows)
		self.assertEqual(len(out), 3)
		total = out[-1]
		self.assertEqual(total["row_type"], "Total")
		self.assertEqual(total["qty"], 15)
		self.assertEqual(total["taxable_value"], 150.0)
		self.assertEqual(total["gross_total"], 177.0)


class TestGetSummary(unittest.TestCase):
	@patch(MOD + "._append_total_row", return_value=[{"desc_code": "A"}])
	@patch(MOD + "._get_data", return_value=[{"desc_code": "A"}])
	@patch(MOD + ".require_permission")
	def test_checks_permissions_for_sale(self, mock_perm, mock_data, mock_total):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			get_summary,
		)

		get_summary(transaction_type="Sale")
		mock_perm.assert_any_call("Sales Invoice", "read")
		mock_perm.assert_any_call("Item", "read")

	@patch(MOD + "._append_total_row", return_value=[])
	@patch(MOD + "._get_data", return_value=[])
	@patch(MOD + ".require_permission")
	def test_checks_permissions_for_purchase(self, mock_perm, mock_data, mock_total):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			get_summary,
		)

		get_summary(transaction_type="Purchase")
		mock_perm.assert_any_call("Purchase Invoice", "read")
		mock_perm.assert_any_call("Item", "read")

	@patch(MOD + "._append_total_row", return_value=[])
	@patch(MOD + "._get_data", return_value=[])
	@patch(MOD + ".require_permission")
	def test_sale_tab_keeps_returns_by_default(self, mock_perm, mock_data, mock_total):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			get_summary,
		)

		get_summary(transaction_type="Sale")
		self.assertEqual(mock_data.call_args[0][0]["exclude_returns"], 0)

	@patch(MOD + "._append_total_row", return_value=[])
	@patch(MOD + "._get_data", return_value=[])
	@patch(MOD + ".require_permission")
	def test_sales_tab_excludes_returns(self, mock_perm, mock_data, mock_total):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			get_summary,
		)

		get_summary(transaction_type="Sale", exclude_returns=1)
		self.assertEqual(mock_data.call_args[0][0]["exclude_returns"], 1)


class TestGetData(unittest.TestCase):
	@patch(MOD + "._run_summary_query", return_value=[])
	def test_exclude_returns_adds_is_return_condition(self, mock_query):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_get_data,
		)

		_get_data({"transaction_type": "Sale", "exclude_returns": 1})
		conditions = mock_query.call_args[0][2]
		self.assertIn("txn.is_return = 0", conditions)

	@patch(MOD + "._run_summary_query", return_value=[])
	def test_without_exclude_returns_no_is_return_condition(self, mock_query):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_get_data,
		)

		_get_data({"transaction_type": "Sale"})
		conditions = mock_query.call_args[0][2]
		self.assertNotIn("is_return", conditions)


class TestGetReturnData(unittest.TestCase):
	@patch(MOD + "._run_return_detail_query", return_value=[])
	def test_sales_return_debit_note_filters_by_dn_prefix(self, mock_query):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_get_return_data,
		)

		_get_return_data("sales_return", "debit_note", {})
		args, _kwargs = mock_query.call_args
		parent_doctype, child_doctype, party_field, conditions, values = args
		self.assertEqual(parent_doctype, "Sales Invoice")
		self.assertEqual(child_doctype, "Sales Invoice Item")
		self.assertEqual(party_field, "customer_name")
		self.assertIn("txn.name LIKE %(name_prefix)s", conditions)
		self.assertEqual(values["name_prefix"], "DN%")

	@patch(MOD + "._run_return_detail_query", return_value=[])
	def test_purchase_return_credit_note_filters_by_cn_prefix(self, mock_query):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_get_return_data,
		)

		_get_return_data("purchase_return", "credit_note", {})
		args, _kwargs = mock_query.call_args
		parent_doctype, child_doctype, party_field, conditions, values = args
		self.assertEqual(parent_doctype, "Purchase Invoice")
		self.assertEqual(child_doctype, "Purchase Invoice Item")
		self.assertEqual(party_field, "supplier_name")
		self.assertEqual(values["name_prefix"], "CN%")

	def test_run_summary_query_always_excludes_draft_and_cancelled(self):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_run_summary_query,
		)

		with patch(MOD + ".frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = []
			_run_summary_query("Sales Invoice", "Sales Invoice Item", "", {})
			query = mock_frappe.db.sql.call_args[0][0]
			self.assertIn("txn.docstatus = 1", query)

	def test_return_detail_query_is_row_level_and_excludes_draft_and_cancelled(self):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_run_return_detail_query,
		)

		with patch(MOD + ".frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = []
			_run_return_detail_query(
				"Sales Invoice", "Sales Invoice Item", "customer_name", "", {}
			)
			query = mock_frappe.db.sql.call_args[0][0]
			self.assertIn("txn.docstatus = 1", query)
			self.assertIn("txn.customer_name AS party_name", query)
			self.assertIn("txn.name AS note_no", query)
			self.assertIn("txn.return_against AS return_against", query)
			self.assertNotIn("item.custom_desc_code", query)


class TestGetReturnSummary(unittest.TestCase):
	@patch(MOD + "._append_total_row", return_value=[])
	@patch(MOD + "._get_return_data", return_value=[])
	@patch(MOD + ".require_permission")
	def test_checks_permissions_for_sales_return(self, mock_perm, mock_data, mock_total):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			get_return_summary,
		)

		get_return_summary(return_type="sales_return", note_type="debit_note")
		mock_perm.assert_any_call("Sales Invoice", "read")
		mock_perm.assert_any_call("Item", "read")
		mock_data.assert_called_once_with("sales_return", "debit_note", {"from_date": None, "to_date": None})

	@patch(MOD + "._append_total_row", return_value=[])
	@patch(MOD + "._get_return_data", return_value=[])
	@patch(MOD + ".require_permission")
	def test_checks_permissions_for_purchase_return(self, mock_perm, mock_data, mock_total):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			get_return_summary,
		)

		get_return_summary(return_type="purchase_return", note_type="credit_note")
		mock_perm.assert_any_call("Purchase Invoice", "read")
		mock_perm.assert_any_call("Item", "read")

	def test_invalid_return_type_throws(self):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			get_return_summary,
		)

		with self.assertRaises(Exception):
			get_return_summary(return_type="bogus", note_type="debit_note")

	@patch(MOD + ".require_permission")
	def test_invalid_note_type_throws(self, _mock_perm):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			get_return_summary,
		)

		with self.assertRaises(Exception):
			get_return_summary(return_type="sales_return", note_type="bogus")


class TestGetPlanningEngineWarehouses(unittest.TestCase):
	def test_collects_warehouse_from_each_child_row(self):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_get_planning_engine_warehouses,
		)

		mock_doc = type(
			"Doc",
			(),
			{
				"table_cmgr": [
					type("Row", (), {"warehouse": "WH1"})(),
					type("Row", (), {"warehouse": None})(),
					type("Row", (), {"warehouse": "WH2"})(),
				]
			},
		)()

		with patch(MOD + ".frappe") as mock_frappe:
			mock_frappe.get_single.return_value = mock_doc
			result = _get_planning_engine_warehouses()

		self.assertEqual(result, ["WH1", "WH2"])
		mock_frappe.get_single.assert_called_once_with("Planning Engine Warehouse Setup")


class TestGetStockData(unittest.TestCase):
	@patch(MOD + "._get_planning_engine_warehouses", return_value=[])
	def test_no_warehouses_returns_empty_without_querying(self, mock_warehouses):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_get_stock_data,
		)

		with patch(MOD + ".frappe") as mock_frappe:
			result = _get_stock_data("2026-08-17")
			mock_frappe.db.sql.assert_not_called()

		self.assertEqual(result, [])

	@patch(MOD + "._get_planning_engine_warehouses", return_value=["WH1", "WH2"])
	def test_queries_sle_scoped_to_allowed_warehouses_and_as_of_date(self, mock_warehouses):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_get_stock_data,
		)

		with patch(MOD + ".frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = [{"desc_code": "A", "on_hand_stock": 10}]
			result = _get_stock_data("2026-07-01")

		query, params = mock_frappe.db.sql.call_args[0][:2]
		self.assertIn("tabStock Ledger Entry", query)
		self.assertIn("SUM(bal.stock_value) AS stock_value", query)
		self.assertEqual(params["warehouses"], ("WH1", "WH2"))
		self.assertEqual(params["as_of_date"], "2026-07-01")
		self.assertEqual(result, [{"desc_code": "A", "on_hand_stock": 10}])


class TestAppendStockTotalRow(unittest.TestCase):
	def test_empty_returns_empty(self):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_append_stock_total_row,
		)

		self.assertEqual(_append_stock_total_row([]), [])

	def test_sums_on_hand_stock(self):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			_append_stock_total_row,
		)

		rows = [
			{"desc_code": "A", "on_hand_stock": 10.5, "stock_value": 1000.0},
			{"desc_code": "B", "on_hand_stock": 4.5, "stock_value": 250.0},
		]
		out = _append_stock_total_row(rows)
		self.assertEqual(len(out), 3)
		self.assertEqual(out[-1]["row_type"], "Total")
		self.assertEqual(out[-1]["on_hand_stock"], 15.0)
		self.assertEqual(out[-1]["stock_value"], 1250.0)


class TestGetStockSummary(unittest.TestCase):
	@patch(MOD + "._append_stock_total_row", return_value=[{"desc_code": "A"}])
	@patch(MOD + "._get_stock_data", return_value=[{"desc_code": "A"}])
	@patch(MOD + ".require_permission")
	def test_checks_permissions(self, mock_perm, mock_data, mock_total):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			get_stock_summary,
		)

		result = get_stock_summary()
		mock_perm.assert_any_call("Bin", "read")
		mock_perm.assert_any_call("Item", "read")
		self.assertEqual(result, [{"desc_code": "A"}])

	@patch(MOD + "._append_stock_total_row", return_value=[])
	@patch(MOD + "._get_stock_data", return_value=[])
	@patch(MOD + ".require_permission")
	def test_defaults_to_today_when_no_to_date(self, mock_perm, mock_data, mock_total):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			get_stock_summary,
			nowdate,
		)

		get_stock_summary()
		mock_data.assert_called_once_with(nowdate())

	@patch(MOD + "._append_stock_total_row", return_value=[])
	@patch(MOD + "._get_stock_data", return_value=[])
	@patch(MOD + ".require_permission")
	def test_uses_given_to_date(self, mock_perm, mock_data, mock_total):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			get_stock_summary,
		)

		get_stock_summary(from_date="2026-07-01", to_date="2026-07-15")
		mock_data.assert_called_once_with("2026-07-15")

	@patch(MOD + ".require_permission")
	def test_to_date_without_from_date_throws(self, _mock_perm):
		from prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa import (
			get_stock_summary,
		)

		with self.assertRaises(Exception):
			get_stock_summary(to_date="2026-07-15")


if __name__ == "__main__":
	unittest.main()
