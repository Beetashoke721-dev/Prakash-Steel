# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for rolled_bar_consumption_for_bright — no DB required."""

import unittest
from unittest.mock import patch

MODULE = (
	"prakash_steel.prakash_steel.report.rolled_bar_consumption_for_bright."
	"rolled_bar_consumption_for_bright"
)


class TestGetColumns(unittest.TestCase):
	def test_returns_five_columns(self):
		from prakash_steel.prakash_steel.report.rolled_bar_consumption_for_bright.rolled_bar_consumption_for_bright import (
			get_columns,
		)

		cols = get_columns()
		self.assertEqual(len(cols), 5)
		fieldnames = [c["fieldname"] for c in cols]
		self.assertEqual(
			fieldnames,
			[
				"production_date",
				"rm_code",
				"rm_name",
				"rm_category_name",
				"actual_rm_consumption",
			],
		)

	def test_rm_code_column_links_to_item(self):
		from prakash_steel.prakash_steel.report.rolled_bar_consumption_for_bright.rolled_bar_consumption_for_bright import (
			get_columns,
		)

		cols = {c["fieldname"]: c for c in get_columns()}
		self.assertEqual(cols["rm_code"]["fieldtype"], "Link")
		self.assertEqual(cols["rm_code"]["options"], "Item")

	def test_rm_category_name_column_links_to_item_category(self):
		from prakash_steel.prakash_steel.report.rolled_bar_consumption_for_bright.rolled_bar_consumption_for_bright import (
			get_columns,
		)

		cols = {c["fieldname"]: c for c in get_columns()}
		self.assertEqual(cols["rm_category_name"]["fieldtype"], "Link")
		self.assertEqual(cols["rm_category_name"]["options"], "Item Category")

	def test_actual_rm_consumption_column_is_float(self):
		from prakash_steel.prakash_steel.report.rolled_bar_consumption_for_bright.rolled_bar_consumption_for_bright import (
			get_columns,
		)

		cols = {c["fieldname"]: c for c in get_columns()}
		self.assertEqual(cols["actual_rm_consumption"]["fieldtype"], "Float")

	def test_rm_name_column_is_plain_data(self):
		from prakash_steel.prakash_steel.report.rolled_bar_consumption_for_bright.rolled_bar_consumption_for_bright import (
			get_columns,
		)

		cols = {c["fieldname"]: c for c in get_columns()}
		self.assertEqual(cols["rm_name"]["fieldtype"], "Data")


class TestGetData(unittest.TestCase):
	def _get_data(self, filters, sql_rows):
		from prakash_steel.prakash_steel.report.rolled_bar_consumption_for_bright.rolled_bar_consumption_for_bright import (
			get_data,
		)

		with patch(MODULE + ".frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = sql_rows
			return get_data(filters), mock_frappe

	def test_docstatus_condition_always_applied(self):
		result, mock_frappe = self._get_data({}, [])
		self.assertEqual(result, [])
		query = mock_frappe.db.sql.call_args[0][0]
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertIn("bbp.docstatus = 1", query)
		self.assertEqual(params, {})

	def test_no_default_date_range_when_dates_not_given(self):
		_, mock_frappe = self._get_data({}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertNotIn("bbp.production_date >=", query)
		self.assertNotIn("bbp.production_date <=", query)
		self.assertEqual(params, {})

	def test_from_date_filter_applied(self):
		_, mock_frappe = self._get_data({"from_date": "2026-07-01"}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertIn("bbp.production_date >= %(from_date)s", query)
		self.assertEqual(params["from_date"], "2026-07-01")

	def test_to_date_filter_applied(self):
		_, mock_frappe = self._get_data({"to_date": "2026-07-09"}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertIn("bbp.production_date <= %(to_date)s", query)
		self.assertEqual(params["to_date"], "2026-07-09")

	def test_rm_code_filter_applied_when_given(self):
		_, mock_frappe = self._get_data({"rm_code": "30mm Round MS"}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertIn("coalesce(bbp.material, bbp.raw_material) = %(rm_code)s", query)
		self.assertEqual(params["rm_code"], "30mm Round MS")

	def test_rm_code_filter_omitted_when_not_given(self):
		_, mock_frappe = self._get_data({}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertNotIn("coalesce(bbp.material, bbp.raw_material) = %(rm_code)s", query)
		self.assertNotIn("rm_code", params)

	def test_rm_code_falls_back_between_material_and_raw_material(self):
		_, mock_frappe = self._get_data({}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("coalesce(bbp.material, bbp.raw_material) as rm_code", query)

	def test_all_filters_combined(self):
		filters = {
			"from_date": "2026-07-01",
			"to_date": "2026-07-09",
			"rm_code": "30mm Round MS",
		}
		_, mock_frappe = self._get_data(filters, [])
		query = mock_frappe.db.sql.call_args[0][0]
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertIn("bbp.production_date >= %(from_date)s", query)
		self.assertIn("bbp.production_date <= %(to_date)s", query)
		self.assertIn("coalesce(bbp.material, bbp.raw_material) = %(rm_code)s", query)
		self.assertEqual(params, filters)

	def test_returns_rows_from_sql(self):
		rows = [
			{
				"production_date": "2026-07-09",
				"rm_code": "101.5x26.5mm Flat MS",
				"rm_name": "101.5x26.5mm Flat MS",
				"rm_category_name": "MS Rolled Bars",
				"actual_rm_consumption": 7110,
			}
		]
		result, _ = self._get_data({}, rows)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["rm_code"], "101.5x26.5mm Flat MS")
		self.assertEqual(result[0]["actual_rm_consumption"], 7110)

	def test_sql_called_as_dict(self):
		_, mock_frappe = self._get_data({}, [])
		self.assertTrue(mock_frappe.db.sql.call_args[1]["as_dict"])

	def test_work_order_branch_unioned_in(self):
		_, mock_frappe = self._get_data({}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("union all", query)
		self.assertIn("`tabWork Order Item` woi", query)
		self.assertIn("wo.custom_bright_production = 1", query)
		self.assertIn("wo.docstatus = 1", query)
		self.assertIn("woi.consumed_qty as actual_rm_consumption", query)
		self.assertIn("woi.consumed_qty > 0", query)

	def test_work_order_branch_dated_on_actual_start_date(self):
		_, mock_frappe = self._get_data({}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("date(wo.actual_start_date) as production_date", query)

	def test_from_date_filter_applied_to_work_order_branch(self):
		_, mock_frappe = self._get_data({"from_date": "2026-07-01"}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("date(wo.actual_start_date) >= %(from_date)s", query)

	def test_to_date_filter_applied_to_work_order_branch(self):
		_, mock_frappe = self._get_data({"to_date": "2026-07-09"}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("date(wo.actual_start_date) <= %(to_date)s", query)

	def test_no_date_range_on_work_order_branch_when_dates_not_given(self):
		_, mock_frappe = self._get_data({}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertNotIn("date(wo.actual_start_date) >=", query)
		self.assertNotIn("date(wo.actual_start_date) <=", query)

	def test_rm_code_filter_applied_to_work_order_branch(self):
		_, mock_frappe = self._get_data({"rm_code": "150mm Billet C4"}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("woi.item_code = %(rm_code)s", query)


class TestExecute(unittest.TestCase):
	@patch(MODULE + ".require_permission")
	@patch(MODULE + ".get_data")
	@patch(MODULE + ".get_columns")
	def test_execute_returns_columns_and_data(
		self, mock_get_columns, mock_get_data, mock_require_permission
	):
		from prakash_steel.prakash_steel.report.rolled_bar_consumption_for_bright.rolled_bar_consumption_for_bright import (
			execute,
		)

		mock_get_columns.return_value = [{"fieldname": "production_date"}]
		mock_get_data.return_value = [{"production_date": "2026-07-09"}]

		columns, data = execute({"rm_code": "30mm Round MS"})

		mock_require_permission.assert_called_once_with("Bright Bar Production", "read")
		mock_get_data.assert_called_once_with({"rm_code": "30mm Round MS"})
		self.assertEqual(columns, mock_get_columns.return_value)
		self.assertEqual(data, mock_get_data.return_value)

	@patch(MODULE + ".require_permission")
	@patch(MODULE + ".get_data")
	@patch(MODULE + ".get_columns")
	def test_execute_defaults_none_filters_to_empty_dict(
		self, mock_get_columns, mock_get_data, mock_require_permission
	):
		from prakash_steel.prakash_steel.report.rolled_bar_consumption_for_bright.rolled_bar_consumption_for_bright import (
			execute,
		)

		mock_get_columns.return_value = []
		mock_get_data.return_value = []

		execute(None)

		mock_get_data.assert_called_once_with({})


if __name__ == "__main__":
	unittest.main()
