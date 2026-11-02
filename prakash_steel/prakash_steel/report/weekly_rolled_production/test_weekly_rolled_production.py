# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for weekly_rolled_production — no DB required."""

import unittest
from unittest.mock import patch

MODULE = "prakash_steel.prakash_steel.report.weekly_rolled_production.weekly_rolled_production"


class TestGetColumns(unittest.TestCase):
	def test_returns_eight_columns(self):
		from prakash_steel.prakash_steel.report.weekly_rolled_production.weekly_rolled_production import (
			get_columns,
		)

		cols = get_columns()
		self.assertEqual(len(cols), 8)
		fieldnames = [c["fieldname"] for c in cols]
		self.assertEqual(
			fieldnames,
			[
				"production_date",
				"item_code",
				"item_name",
				"item_group",
				"actual_qty",
				"uom",
				"production_plan",
				"vendor_name",
			],
		)

	def test_item_code_column_links_to_item(self):
		from prakash_steel.prakash_steel.report.weekly_rolled_production.weekly_rolled_production import (
			get_columns,
		)

		cols = {c["fieldname"]: c for c in get_columns()}
		self.assertEqual(cols["item_code"]["fieldtype"], "Link")
		self.assertEqual(cols["item_code"]["options"], "Item")

	def test_item_group_column_links_to_item_category(self):
		from prakash_steel.prakash_steel.report.weekly_rolled_production.weekly_rolled_production import (
			get_columns,
		)

		cols = {c["fieldname"]: c for c in get_columns()}
		self.assertEqual(cols["item_group"]["fieldtype"], "Link")
		self.assertEqual(cols["item_group"]["options"], "Item Category")

	def test_uom_column_links_to_uom(self):
		from prakash_steel.prakash_steel.report.weekly_rolled_production.weekly_rolled_production import (
			get_columns,
		)

		cols = {c["fieldname"]: c for c in get_columns()}
		self.assertEqual(cols["uom"]["fieldtype"], "Link")
		self.assertEqual(cols["uom"]["options"], "UOM")

	def test_actual_qty_column_is_float(self):
		from prakash_steel.prakash_steel.report.weekly_rolled_production.weekly_rolled_production import (
			get_columns,
		)

		cols = {c["fieldname"]: c for c in get_columns()}
		self.assertEqual(cols["actual_qty"]["fieldtype"], "Float")

	def test_production_plan_and_vendor_name_are_plain_data(self):
		"""production_plan can come from either Production Plan or Production
		Planning, and vendor_name is a static string — neither is a single-doctype
		Link, so both are rendered as Data columns."""
		from prakash_steel.prakash_steel.report.weekly_rolled_production.weekly_rolled_production import (
			get_columns,
		)

		cols = {c["fieldname"]: c for c in get_columns()}
		self.assertEqual(cols["production_plan"]["fieldtype"], "Data")
		self.assertEqual(cols["vendor_name"]["fieldtype"], "Data")


class TestGetData(unittest.TestCase):
	def _get_data(self, filters, sql_rows, today="2026-07-17"):
		from prakash_steel.prakash_steel.report.weekly_rolled_production.weekly_rolled_production import (
			get_data,
		)

		with patch(MODULE + ".frappe") as mock_frappe, patch(MODULE + ".today", return_value=today):
			mock_frappe.db.sql.return_value = sql_rows
			return get_data(filters), mock_frappe

	def test_docstatus_condition_always_applied(self):
		result, mock_frappe = self._get_data({}, [])
		self.assertEqual(result, [])
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("fw.docstatus = 1", query)
		self.assertIn("wo.docstatus = 1", query)
		self.assertIn("wo.custom_rolled_production = 1", query)

	def test_work_order_is_default_source(self):
		_, mock_frappe = self._get_data({}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("from `tabWork Order` wo", query)
		self.assertIn("wo.production_item as item_code", query)
		self.assertIn("wo.produced_qty as actual_qty", query)
		self.assertIn("date(wo.actual_start_date) as production_date", query)
		self.assertIn("wo.name as production_plan", query)
		self.assertIn("'Work Order' as production_plan_type", query)
		self.assertIn("union all", query)

	def test_work_order_vendor_name_comes_from_sales_order_customer(self):
		_, mock_frappe = self._get_data({}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("left join `tabSales Order` so on so.name = wo.sales_order", query)
		self.assertIn("coalesce(so.customer_name, '') as vendor_name", query)

	def test_work_order_item_code_filter_applied_when_given(self):
		_, mock_frappe = self._get_data({"item_code": "60mm Round C4"}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("wo.production_item = %(item_code)s", query)

	def test_rolled_plan_filter_always_applied(self):
		_, mock_frappe = self._get_data({}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("fw.production_planning like 'Rolled%%'", query)
		self.assertIn("fw.production_plan like 'Rolled%%'", query)

	def test_defaults_to_last_seven_days_when_no_dates_given(self):
		_, mock_frappe = self._get_data({}, [], today="2026-07-17")
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertEqual(params["from_date"], "2026-07-11")
		self.assertEqual(params["to_date"], "2026-07-17")

	def test_explicit_from_date_and_to_date_are_respected(self):
		filters = {"from_date": "2026-07-01", "to_date": "2026-07-09"}
		_, mock_frappe = self._get_data(filters, [])
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertEqual(params["from_date"], "2026-07-01")
		self.assertEqual(params["to_date"], "2026-07-09")

	def test_item_code_filter_applied_when_given(self):
		_, mock_frappe = self._get_data({"item_code": "60mm Round C4"}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertIn("fw.item_code = %(item_code)s", query)
		self.assertEqual(params["item_code"], "60mm Round C4")

	def test_item_code_filter_omitted_when_not_given(self):
		_, mock_frappe = self._get_data({}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertNotIn("fw.item_code = %(item_code)s", query)
		self.assertNotIn("item_code", params)

	def test_vendor_name_is_hardcoded_in_query(self):
		_, mock_frappe = self._get_data({}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("'Rolling Mill Production' as vendor_name", query)

	def test_production_plan_falls_back_between_the_two_fields(self):
		_, mock_frappe = self._get_data({}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("coalesce(fw.production_planning, fw.production_plan) as production_plan", query)

	def test_returns_rows_from_sql(self):
		rows = [
			{
				"production_date": "2026-07-09",
				"item_code": "56mm Round C4",
				"item_name": "56mm Round C4",
				"item_group": "C4 Rolled Bars",
				"actual_qty": 82750,
				"uom": "Kg",
				"production_plan": "Rolled Plan - 2026-07-09-0001",
				"vendor_name": "Rolling Mill Production",
			}
		]
		result, _ = self._get_data({}, rows)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["item_code"], "56mm Round C4")
		self.assertEqual(result[0]["vendor_name"], "Rolling Mill Production")

	def test_sql_called_as_dict(self):
		_, mock_frappe = self._get_data({}, [])
		self.assertTrue(mock_frappe.db.sql.call_args[1]["as_dict"])


class TestExecute(unittest.TestCase):
	@patch(MODULE + ".require_permission")
	@patch(MODULE + ".get_data")
	@patch(MODULE + ".get_columns")
	def test_execute_returns_columns_and_data(
		self, mock_get_columns, mock_get_data, mock_require_permission
	):
		from prakash_steel.prakash_steel.report.weekly_rolled_production.weekly_rolled_production import (
			execute,
		)

		mock_get_columns.return_value = [{"fieldname": "production_date"}]
		mock_get_data.return_value = [{"production_date": "2026-07-09"}]

		columns, data = execute({"item_code": "60mm Round C4"})

		mock_require_permission.assert_called_once_with("Finish Weight", "read")
		mock_get_data.assert_called_once_with({"item_code": "60mm Round C4"})
		self.assertEqual(columns, mock_get_columns.return_value)
		self.assertEqual(data, mock_get_data.return_value)

	@patch(MODULE + ".require_permission")
	@patch(MODULE + ".get_data")
	@patch(MODULE + ".get_columns")
	def test_execute_defaults_none_filters_to_empty_dict(
		self, mock_get_columns, mock_get_data, mock_require_permission
	):
		from prakash_steel.prakash_steel.report.weekly_rolled_production.weekly_rolled_production import (
			execute,
		)

		mock_get_columns.return_value = []
		mock_get_data.return_value = []

		execute(None)

		mock_get_data.assert_called_once_with({})


if __name__ == "__main__":
	unittest.main()
