# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for auto-submit of Manufacture Stock Entry from Work Order Finish."""

import itertools
import unittest
from unittest.mock import MagicMock, patch

from frappe.utils import cint

MOD = "prakash_steel.utils.work_order"


def _job_card(**fields):
	doc = MagicMock()
	defaults = {
		"name": "JC-0001",
		"docstatus": 1,
		"work_order": "WO-0001",
		"is_corrective_job_card": 0,
		"operation_id": "OP-LAST",
		"sequence_id": 2,
		"operation": "Mill",
		"total_completed_qty": 12.5,
		"process_loss_qty": 0,
		"custom_actual_rm_consumption": 500,
		"secondary_items": [],
	}
	defaults.update(fields)
	for key, value in defaults.items():
		setattr(doc, key, value)
	return doc


def _se_row(**fields):
	row = MagicMock()
	defaults = {
		"is_finished_item": 0,
		"type": None,
		"is_legacy_scrap_item": 0,
		"is_scrap_item": 0,
		"s_warehouse": "WIP - PSP",
		"t_warehouse": None,
		"qty": 100,
		"conversion_factor": 1,
		"transfer_qty": 100,
	}
	defaults.update(fields)
	for key, value in defaults.items():
		setattr(row, key, value)
	return row


def _jc_secondary(**fields):
	row = MagicMock()
	defaults = {
		"type": "Scrap",
		"item_code": "WASTAGE SCRAP",
		"item_name": "WASTAGE SCRAP",
		"description": "WASTAGE SCRAP",
		"stock_qty": 100,
		"stock_uom": "Kg",
		"bom_secondary_item": None,
	}
	defaults.update(fields)
	for key, value in defaults.items():
		setattr(row, key, value)
	return row


SECONDARY_ITEMS = [
	{
		"type": "Scrap",
		"item_code": "WASTAGE SCRAP",
		"item_name": "WASTAGE SCRAP",
		"description": "WASTAGE SCRAP",
		"stock_qty": 100,
		"stock_uom": "Kg",
		"bom_secondary_item": None,
	},
	{
		"type": "Additional Finished Good",
		"item_code": "Miss Billet C4",
		"item_name": "Miss Billet C4",
		"description": "Miss Billet C4",
		"stock_qty": 50,
		"stock_uom": "Kg",
		"bom_secondary_item": None,
	},
]


class TestSubmitManufactureStockEntry(unittest.TestCase):
	def _work_order(self, docstatus=1, status="In Process"):
		wo = MagicMock()
		wo.name = "WO-0001"
		wo.docstatus = docstatus
		wo.status = status
		return wo

	def _call(self, qty=10, job_card=None, **kwargs):
		from prakash_steel.utils.work_order import submit_manufacture_stock_entry

		return submit_manufacture_stock_entry("WO-0001", qty=qty, job_card=job_card, **kwargs)

	@patch(f"{MOD}.require_all_permissions")
	@patch(f"{MOD}.frappe")
	def test_throws_when_work_order_missing(self, mock_frappe, _mock_perms):
		from prakash_steel.utils.work_order import submit_manufacture_stock_entry

		mock_frappe.db.get_value.return_value = None
		mock_frappe.bold.side_effect = lambda value: value
		mock_frappe.throw.side_effect = Exception("not found")

		with self.assertRaises(Exception):
			submit_manufacture_stock_entry("")

		mock_frappe.throw.assert_called()

	@patch(f"{MOD}.require_all_permissions")
	@patch(f"{MOD}.frappe")
	def test_throws_when_work_order_not_found(self, mock_frappe, _mock_perms):
		mock_frappe.db.get_value.return_value = None
		mock_frappe.bold.side_effect = lambda value: value
		mock_frappe.throw.side_effect = Exception("not found")

		with self.assertRaises(Exception):
			self._call()

	@patch(f"{MOD}.require_all_permissions")
	@patch(f"{MOD}.frappe")
	def test_throws_when_work_order_not_submitted(self, mock_frappe, _mock_perms):
		mock_frappe.db.get_value.return_value = self._work_order(docstatus=0)
		mock_frappe.bold.side_effect = lambda value: value
		mock_frappe.throw.side_effect = Exception("not submitted")

		with self.assertRaises(Exception):
			self._call()

	@patch(f"{MOD}.require_all_permissions")
	@patch(f"{MOD}.frappe")
	def test_throws_when_work_order_stopped(self, mock_frappe, _mock_perms):
		mock_frappe.db.get_value.return_value = self._work_order(status="Stopped")
		mock_frappe.bold.side_effect = lambda value: value
		mock_frappe.throw.side_effect = Exception("stopped")

		with self.assertRaises(Exception):
			self._call()

	@patch("erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry")
	@patch(f"{MOD}.require_all_permissions")
	@patch(f"{MOD}.frappe")
	def test_builds_manufacture_entry_and_submits(self, mock_frappe, mock_perms, mock_make_se):
		mock_frappe.db.get_value.return_value = self._work_order()
		mock_make_se.return_value = {"doctype": "Stock Entry", "purpose": "Manufacture"}

		stock_entry = MagicMock()
		stock_entry.items = []
		stock_entry.as_dict.return_value = {"doctype": "Stock Entry", "name": "MAT-STE-0001"}
		mock_frappe.get_doc.return_value = stock_entry

		result = self._call(qty=12.5)

		mock_perms.assert_called_once()
		mock_make_se.assert_called_once_with("WO-0001", "Manufacture", qty=12.5)
		self.assertEqual(stock_entry.inspection_required, 0)
		stock_entry.insert.assert_called_once_with()
		stock_entry.submit.assert_called_once_with()
		self.assertEqual(result["name"], "MAT-STE-0001")
		self.assertEqual(result["doctype"], "Stock Entry")

	@patch(f"{MOD}.require_all_permissions")
	@patch(f"{MOD}.frappe")
	def test_throws_when_job_card_actual_rm_missing(self, mock_frappe, _mock_perms):
		mock_frappe.db.get_value.return_value = self._work_order()
		mock_frappe.bold.side_effect = lambda value: value
		mock_frappe.throw.side_effect = Exception("rm required")

		with self.assertRaises(Exception):
			self._call(qty=17.5, job_card="JC-0001", finished_good_qty=12.5, process_loss_qty=5)

		mock_frappe.throw.assert_called()

	@patch("erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry")
	@patch(f"{MOD}.require_all_permissions")
	@patch(f"{MOD}.frappe")
	def test_uses_secondary_item_qty_as_process_loss(self, mock_frappe, _mock_perms, mock_make_se):
		def get_value(doctype, name, fields=None, as_dict=False):
			if doctype == "Work Order":
				return self._work_order()
			if doctype == "Job Card" and fields == "posting_date":
				return "2026-08-10"
			return None

		mock_frappe.db.get_value.side_effect = get_value
		mock_frappe.get_all.return_value = SECONDARY_ITEMS
		mock_make_se.return_value = {"doctype": "Stock Entry", "purpose": "Manufacture"}

		rm = _se_row(qty=80, transfer_qty=80)
		fg = _se_row(
			is_finished_item=1,
			s_warehouse=None,
			t_warehouse="FG - PSP",
			qty=17.5,
			transfer_qty=17.5,
		)
		bom_scrap = _se_row(
			type="Scrap",
			is_legacy_scrap_item=1,
			s_warehouse=None,
			t_warehouse="SCRAP - PSP",
			qty=10,
			transfer_qty=10,
		)
		stock_entry = MagicMock()
		stock_entry.doctype = "Dummy"
		stock_entry.items = [rm, fg, bom_scrap]
		stock_entry.to_warehouse = "FG - PSP"
		stock_entry.as_dict.return_value = {"doctype": "Stock Entry", "name": "MAT-STE-0001"}
		mock_frappe.get_doc.return_value = stock_entry

		result = self._call(
			qty=17.5,
			job_card="JC-0001",
			actual_rm_consumption=500,
			finished_good_qty=12.5,
			process_loss_qty=5,
		)

		mock_make_se.assert_called_once_with("WO-0001", "Manufacture", qty=162.5)
		self.assertEqual(stock_entry.inspection_required, 0)
		self.assertEqual(stock_entry.set_posting_time, 1)
		self.assertEqual(stock_entry.posting_date, "2026-08-10")
		self.assertEqual(rm.qty, 500)
		self.assertEqual(fg.qty, 12.5)
		self.assertEqual(stock_entry.fg_completed_qty, 162.5)
		self.assertEqual(stock_entry.process_loss_qty, 150)
		self.assertEqual(len(stock_entry.items), 4)
		self.assertEqual(stock_entry.items[2].item_code, "WASTAGE SCRAP")
		self.assertEqual(stock_entry.items[2].qty, 100)
		self.assertEqual(stock_entry.items[2].type, "Scrap")
		self.assertEqual(stock_entry.items[3].item_code, "Miss Billet C4")
		self.assertEqual(stock_entry.items[3].qty, 50)
		self.assertEqual(stock_entry.items[3].type, "Additional Finished Good")
		self.assertEqual(result["name"], "MAT-STE-0001")

	def test_apply_job_card_posting_date_sets_edit_posting_time(self):
		from prakash_steel.utils.work_order import apply_job_card_posting_date

		stock_entry = MagicMock()
		apply_job_card_posting_date(stock_entry, "2026-08-10")
		self.assertEqual(stock_entry.set_posting_time, 1)
		self.assertEqual(stock_entry.posting_date, "2026-08-10")

	def test_apply_job_card_posting_date_skips_when_missing(self):
		from prakash_steel.utils.work_order import apply_job_card_posting_date

		class StockEntryStub:
			pass

		stock_entry = StockEntryStub()
		apply_job_card_posting_date(stock_entry, None)
		self.assertFalse(hasattr(stock_entry, "set_posting_time"))
		self.assertFalse(hasattr(stock_entry, "posting_date"))


class TestJobCardManufactureEligibility(unittest.TestCase):
	@patch(f"{MOD}.frappe")
	def test_skips_corrective_job_card(self, mock_frappe):
		from prakash_steel.utils.work_order import should_create_manufacture_stock_entry_for_job_card

		self.assertFalse(
			should_create_manufacture_stock_entry_for_job_card(_job_card(is_corrective_job_card=1))
		)

	@patch(f"{MOD}.frappe")
	def test_skips_when_work_order_missing(self, mock_frappe):
		from prakash_steel.utils.work_order import should_create_manufacture_stock_entry_for_job_card

		self.assertFalse(should_create_manufacture_stock_entry_for_job_card(_job_card(work_order=None)))

	@patch(f"{MOD}.frappe")
	def test_skips_semi_finished_tracking(self, mock_frappe):
		from prakash_steel.utils.work_order import should_create_manufacture_stock_entry_for_job_card

		mock_frappe.db.get_value.return_value = 1
		self.assertFalse(should_create_manufacture_stock_entry_for_job_card(_job_card()))

	@patch(f"{MOD}.frappe")
	def test_skips_earlier_operation(self, mock_frappe):
		from prakash_steel.utils.work_order import should_create_manufacture_stock_entry_for_job_card

		mock_frappe.db.get_value.return_value = 0
		mock_frappe.get_all.return_value = [
			{"name": "OP-1", "sequence_id": 1, "operation": "Cut"},
			{"name": "OP-LAST", "sequence_id": 2, "operation": "Mill"},
		]
		self.assertFalse(
			should_create_manufacture_stock_entry_for_job_card(_job_card(operation_id="OP-1"))
		)

	@patch(f"{MOD}.frappe")
	def test_allows_last_operation(self, mock_frappe):
		from prakash_steel.utils.work_order import should_create_manufacture_stock_entry_for_job_card

		mock_frappe.db.get_value.return_value = 0
		mock_frappe.get_all.return_value = [
			{"name": "OP-1", "sequence_id": 1, "operation": "Cut"},
			{"name": "OP-LAST", "sequence_id": 2, "operation": "Mill"},
		]
		self.assertTrue(should_create_manufacture_stock_entry_for_job_card(_job_card()))


class TestJobCardAutoFinish(unittest.TestCase):
	@patch(f"{MOD}.submit_manufacture_stock_entry")
	@patch(f"{MOD}.should_create_manufacture_stock_entry_for_job_card", return_value=False)
	def test_hook_returns_when_job_card_should_not_finish(self, _should, mock_submit):
		from prakash_steel.utils.work_order import submit_manufacture_stock_entry_for_job_card

		submit_manufacture_stock_entry_for_job_card(_job_card())
		mock_submit.assert_not_called()

	@patch(f"{MOD}.is_automatic_manufacture_stock_entry_enabled", return_value=False)
	@patch(f"{MOD}.submit_manufacture_stock_entry")
	def test_hook_returns_when_auto_setting_disabled(self, mock_submit, _auto_enabled):
		from prakash_steel.utils.work_order import submit_manufacture_stock_entry_for_job_card

		submit_manufacture_stock_entry_for_job_card(_job_card(process_loss_qty=5))
		mock_submit.assert_not_called()

	@patch(f"{MOD}.submit_manufacture_stock_entry")
	@patch(f"{MOD}.should_create_manufacture_stock_entry_for_job_card", return_value=True)
	@patch(f"{MOD}.frappe")
	def test_hook_throws_when_completed_qty_is_zero(self, mock_frappe, _should, mock_submit):
		from prakash_steel.utils.work_order import submit_manufacture_stock_entry_for_job_card

		mock_frappe.bold.side_effect = lambda value: value
		mock_frappe.throw.side_effect = Exception("zero qty")

		with self.assertRaises(Exception):
			submit_manufacture_stock_entry_for_job_card(_job_card(total_completed_qty=0))

		mock_submit.assert_not_called()

	@patch(f"{MOD}.submit_manufacture_stock_entry")
	@patch(f"{MOD}.should_create_manufacture_stock_entry_for_job_card", return_value=True)
	@patch(f"{MOD}.frappe")
	def test_hook_throws_when_actual_rm_consumption_missing(self, mock_frappe, _should, mock_submit):
		from prakash_steel.utils.work_order import submit_manufacture_stock_entry_for_job_card

		mock_frappe.bold.side_effect = lambda value: value
		mock_frappe.throw.side_effect = Exception("rm required")

		with self.assertRaises(Exception):
			submit_manufacture_stock_entry_for_job_card(_job_card(custom_actual_rm_consumption=0))

		mock_submit.assert_not_called()

	@patch(f"{MOD}.submit_manufacture_stock_entry")
	@patch(f"{MOD}.should_create_manufacture_stock_entry_for_job_card", return_value=True)
	@patch(f"{MOD}.frappe")
	def test_hook_finishes_work_order_with_job_card_process_loss(
		self, mock_frappe, _should, mock_submit
	):
		from prakash_steel.utils.work_order import submit_manufacture_stock_entry_for_job_card

		mock_submit.return_value = {"name": "MAT-STE-0001"}
		mock_frappe.bold.side_effect = lambda value: value

		submit_manufacture_stock_entry_for_job_card(
			_job_card(
				secondary_items=[
					_jc_secondary(),
					_jc_secondary(
						type="Additional Finished Good",
						item_code="Miss Billet C4",
						item_name="Miss Billet C4",
						stock_qty=50,
					),
				]
			)
		)

		mock_submit.assert_called_once_with(
			"WO-0001",
			qty=162.5,
			job_card="JC-0001",
			actual_rm_consumption=500,
			finished_good_qty=12.5,
			process_loss_qty=150,
		)
		mock_frappe.msgprint.assert_called_once()

	@patch(f"{MOD}.submit_manufacture_stock_entry")
	@patch(f"{MOD}.should_create_manufacture_stock_entry_for_job_card", return_value=True)
	@patch(f"{MOD}.frappe")
	def test_hook_uses_job_card_process_loss_without_secondary_items(
		self, mock_frappe, _should, mock_submit
	):
		from prakash_steel.utils.work_order import submit_manufacture_stock_entry_for_job_card

		mock_submit.return_value = {"name": "MAT-STE-0001"}
		mock_frappe.bold.side_effect = lambda value: value

		submit_manufacture_stock_entry_for_job_card(_job_card(process_loss_qty=5, secondary_items=[]))

		mock_submit.assert_called_once_with(
			"WO-0001",
			qty=17.5,
			job_card="JC-0001",
			actual_rm_consumption=500,
			finished_good_qty=12.5,
			process_loss_qty=5,
		)


class TestGetWorkOrderFinishDefaults(unittest.TestCase):
	class _Dict(dict):
		def __getattr__(self, key):
			try:
				return self[key]
			except KeyError:
				return None

		def __setattr__(self, key, value):
			self[key] = value

	def _get_all(self, doctype, **kwargs):
		if doctype == "Work Order Operation":
			return [
				{"name": "OP-1", "sequence_id": 1, "operation": "Cut"},
				{"name": "OP-LAST", "sequence_id": 2, "operation": "Mill"},
			]
		if doctype == "Job Card":
			return [
				{
					"name": "JC-0001",
					"total_completed_qty": 12.5,
					"process_loss_qty": 5,
					"custom_actual_rm_consumption": 500,
					"operation_id": "OP-LAST",
					"sequence_id": 2,
					"operation": "Mill",
				}
			]
		if doctype == "Job Card Secondary Item":
			return list(SECONDARY_ITEMS)
		return []

	@patch(f"{MOD}.require_all_permissions")
	@patch(f"{MOD}.frappe")
	def test_returns_completed_qty_plus_process_loss(self, mock_frappe, mock_perms):
		from prakash_steel.utils.work_order import get_work_order_finish_defaults

		mock_frappe.get_all.side_effect = self._get_all
		mock_frappe.db.get_value.return_value = 0
		mock_frappe._dict = self._Dict

		result = get_work_order_finish_defaults("WO-0001")

		mock_perms.assert_called_once()
		self.assertEqual(result["job_card"], "JC-0001")
		self.assertEqual(result["total_completed_qty"], 12.5)
		self.assertEqual(result["process_loss_qty"], 150)
		self.assertEqual(result["actual_rm_consumption"], 500)
		self.assertEqual(result["qty"], 162.5)

	@patch(f"{MOD}.require_all_permissions")
	@patch(f"{MOD}.frappe")
	def test_returns_zero_process_loss_when_no_job_card(self, mock_frappe, _mock_perms):
		from prakash_steel.utils.work_order import get_work_order_finish_defaults

		def get_all(doctype, **kwargs):
			return []

		mock_frappe.get_all.side_effect = get_all
		mock_frappe._dict = self._Dict

		result = get_work_order_finish_defaults("WO-0001")

		self.assertIsNone(result["job_card"])
		self.assertEqual(result["total_completed_qty"], 0)
		self.assertEqual(result["process_loss_qty"], 0)
		self.assertEqual(result["qty"], 0)

	@patch(f"{MOD}.require_all_permissions")
	@patch(f"{MOD}.frappe")
	def test_uses_job_card_process_loss_even_when_zero(self, mock_frappe, mock_perms):
		from prakash_steel.utils.work_order import get_work_order_finish_defaults

		def get_all(doctype, **kwargs):
			if doctype == "Work Order Operation":
				return [
					{"name": "OP-LAST", "sequence_id": 1, "operation": "Mill", "process_loss_qty": 9}
				]
			if doctype == "Job Card":
				return [
					{
						"name": "JC-0001",
						"total_completed_qty": 12.5,
						"process_loss_qty": 0,
						"custom_actual_rm_consumption": 500,
						"operation_id": "OP-LAST",
						"sequence_id": 1,
						"operation": "Mill",
					}
				]
			return []

		mock_frappe.get_all.side_effect = get_all
		mock_frappe.db.get_value.return_value = 0
		mock_frappe._dict = self._Dict

		result = get_work_order_finish_defaults("WO-0001")

		self.assertEqual(result["job_card"], "JC-0001")
		self.assertEqual(result["process_loss_qty"], 0)
		self.assertEqual(result["qty"], 12.5)

	@patch(f"{MOD}.require_all_permissions")
	@patch(f"{MOD}.frappe")
	def test_falls_back_to_job_card_process_loss_without_secondary_items(self, mock_frappe, _mock_perms):
		from prakash_steel.utils.work_order import get_work_order_finish_defaults

		def get_all(doctype, **kwargs):
			if doctype == "Work Order Operation":
				return [
					{"name": "OP-1", "sequence_id": 1, "operation": "Cut"},
					{"name": "OP-LAST", "sequence_id": 2, "operation": "Mill"},
				]
			if doctype == "Job Card":
				return [
					{
						"name": "JC-0001",
						"total_completed_qty": 12.5,
						"process_loss_qty": 5,
						"custom_actual_rm_consumption": 500,
						"operation_id": "OP-LAST",
						"sequence_id": 2,
						"operation": "Mill",
					}
				]
			if doctype == "Job Card Secondary Item":
				return []
			return []

		mock_frappe.get_all.side_effect = get_all
		mock_frappe.db.get_value.side_effect = lambda doctype, name, field=None, **kwargs: (
			5 if doctype == "Job Card" and field == "process_loss_qty" else 0
		)
		mock_frappe._dict = self._Dict

		result = get_work_order_finish_defaults("WO-0001")

		self.assertEqual(result["process_loss_qty"], 5)
		self.assertEqual(result["qty"], 17.5)


class TestPrepareAutoManufactureStockEntry(unittest.TestCase):
	def test_unchecks_inspection_required(self):
		from prakash_steel.utils.work_order import prepare_auto_manufacture_stock_entry

		stock_entry = MagicMock()
		stock_entry.items = []
		stock_entry.inspection_required = 1

		prepare_auto_manufacture_stock_entry(stock_entry)

		self.assertEqual(stock_entry.inspection_required, 0)
		stock_entry.calculate_rate_and_amount.assert_not_called()

	def test_sets_single_rm_qty_from_actual_consumption(self):
		from prakash_steel.utils.work_order import prepare_auto_manufacture_stock_entry

		rm = _se_row(qty=80, transfer_qty=80)
		fg = _se_row(
			is_finished_item=1,
			s_warehouse=None,
			t_warehouse="FG - PSP",
			qty=12.5,
			transfer_qty=12.5,
		)
		stock_entry = MagicMock()
		stock_entry.items = [rm, fg]
		stock_entry.inspection_required = 1

		prepare_auto_manufacture_stock_entry(stock_entry, actual_rm_consumption=500)

		self.assertEqual(stock_entry.inspection_required, 0)
		self.assertEqual(rm.qty, 500)
		self.assertEqual(rm.transfer_qty, 500)
		self.assertEqual(fg.qty, 12.5)
		stock_entry.calculate_rate_and_amount.assert_called_once_with(raise_error_if_no_rate=False)

	def test_does_not_change_scrap_qty(self):
		from prakash_steel.utils.work_order import prepare_auto_manufacture_stock_entry

		rm = _se_row(qty=80)
		scrap = _se_row(
			is_legacy_scrap_item=1,
			s_warehouse=None,
			t_warehouse="WIP - PSP",
			qty=10,
			transfer_qty=10,
		)
		stock_entry = MagicMock()
		stock_entry.items = [rm, scrap]

		prepare_auto_manufacture_stock_entry(stock_entry, actual_rm_consumption=500)

		self.assertEqual(rm.qty, 500)
		self.assertEqual(scrap.qty, 10)

	def test_keeps_process_loss_and_sets_fg_completed_qty(self):
		from prakash_steel.utils.work_order import prepare_auto_manufacture_stock_entry

		rm = _se_row(qty=80, transfer_qty=80)
		fg = _se_row(
			is_finished_item=1,
			s_warehouse=None,
			t_warehouse="FG - PSP",
			qty=100,
			transfer_qty=100,
		)
		stock_entry = MagicMock()
		stock_entry.items = [rm, fg]
		stock_entry.fg_completed_qty = 100
		stock_entry.process_loss_qty = 0
		stock_entry.process_loss_percentage = 0

		prepare_auto_manufacture_stock_entry(
			stock_entry,
			actual_rm_consumption=500,
			finished_good_qty=12.5,
			process_loss_qty=5,
		)

		self.assertEqual(rm.qty, 500)
		self.assertEqual(fg.qty, 12.5)
		self.assertEqual(fg.transfer_qty, 12.5)
		self.assertEqual(stock_entry.fg_completed_qty, 17.5)
		self.assertEqual(stock_entry.process_loss_qty, 5)
		self.assertEqual(stock_entry.process_loss_percentage, (5 / 17.5) * 100)

	def test_keeps_existing_process_loss_when_not_passed(self):
		from prakash_steel.utils.work_order import prepare_auto_manufacture_stock_entry

		fg = _se_row(
			is_finished_item=1,
			s_warehouse=None,
			t_warehouse="FG - PSP",
			qty=100,
			transfer_qty=100,
		)
		stock_entry = MagicMock()
		stock_entry.items = [fg]
		stock_entry.process_loss_qty = 5
		stock_entry.process_loss_percentage = 5

		prepare_auto_manufacture_stock_entry(stock_entry, finished_good_qty=12.5)

		self.assertEqual(fg.qty, 12.5)
		self.assertEqual(stock_entry.process_loss_qty, 5)
		self.assertEqual(stock_entry.fg_completed_qty, 17.5)

	def test_splits_actual_consumption_across_multiple_rm_rows(self):
		from prakash_steel.utils.work_order import prepare_auto_manufacture_stock_entry

		rm1 = _se_row(qty=60, transfer_qty=60)
		rm2 = _se_row(qty=40, transfer_qty=40)
		stock_entry = MagicMock()
		stock_entry.items = [rm1, rm2]

		prepare_auto_manufacture_stock_entry(stock_entry, actual_rm_consumption=200)

		self.assertEqual(rm1.qty, 120)
		self.assertEqual(rm2.qty, 80)

	def test_splits_secondary_items_from_job_card_qty_column(self):
		from prakash_steel.utils.work_order import prepare_auto_manufacture_stock_entry

		rm = _se_row(qty=80, transfer_qty=80)
		fg = _se_row(
			is_finished_item=1,
			s_warehouse=None,
			t_warehouse="FG - PSP",
			qty=100,
			transfer_qty=100,
		)
		bom_scrap = _se_row(
			type="Scrap",
			item_code="BOM SCRAP",
			s_warehouse=None,
			t_warehouse="SCRAP - PSP",
			qty=10,
			transfer_qty=10,
		)
		stock_entry = MagicMock()
		stock_entry.doctype = "Dummy"
		stock_entry.items = [rm, fg, bom_scrap]
		stock_entry.to_warehouse = "FG - PSP"

		prepare_auto_manufacture_stock_entry(
			stock_entry,
			actual_rm_consumption=500,
			finished_good_qty=12.5,
			process_loss_qty=150,
			secondary_items=SECONDARY_ITEMS,
		)

		self.assertEqual(rm.qty, 500)
		self.assertEqual(fg.qty, 12.5)
		self.assertEqual(stock_entry.fg_completed_qty, 162.5)
		self.assertEqual(stock_entry.process_loss_qty, 150)
		self.assertEqual([row.item_code for row in stock_entry.items[2:]], ["WASTAGE SCRAP", "Miss Billet C4"])
		self.assertEqual(stock_entry.items[2].qty, 100)
		self.assertEqual(stock_entry.items[2].type, "Scrap")
		self.assertEqual(stock_entry.items[3].qty, 50)
		self.assertEqual(stock_entry.items[3].type, "Additional Finished Good")


class TestJobCardSecondaryItems(unittest.TestCase):
	def test_sums_qty_column_as_process_loss(self):
		from prakash_steel.utils.work_order import get_process_loss_qty_from_secondary_items

		self.assertEqual(get_process_loss_qty_from_secondary_items(SECONDARY_ITEMS), 150)
		self.assertEqual(get_process_loss_qty_from_secondary_items([]), 0)

	def test_prefers_secondary_items_over_job_card_process_loss(self):
		from prakash_steel.utils.work_order import get_job_card_process_loss_qty

		self.assertEqual(
			get_job_card_process_loss_qty(_job_card(process_loss_qty=5), SECONDARY_ITEMS),
			150,
		)

	def test_falls_back_to_job_card_process_loss_without_secondary_items(self):
		from prakash_steel.utils.work_order import get_job_card_process_loss_qty

		self.assertEqual(
			get_job_card_process_loss_qty(_job_card(process_loss_qty=5), []),
			5,
		)
		self.assertEqual(
			get_job_card_process_loss_qty(_job_card(process_loss_qty=0), []),
			0,
		)

	def test_reads_secondary_items_from_job_card_doc(self):
		from prakash_steel.utils.work_order import get_job_card_secondary_items

		items = get_job_card_secondary_items(
			_job_card(
				secondary_items=[
					_jc_secondary(),
					_jc_secondary(type="Additional Finished Good", item_code="Miss Billet C4", stock_qty=50),
					_jc_secondary(item_code="SKIP", stock_qty=0),
				]
			)
		)
		self.assertEqual(len(items), 2)
		self.assertEqual(items[0]["item_code"], "WASTAGE SCRAP")
		self.assertEqual(items[0]["stock_qty"], 100)
		self.assertEqual(items[1]["item_code"], "Miss Billet C4")
		self.assertEqual(items[1]["stock_qty"], 50)


class _WorkOrderStub:
	def __init__(self, **fields):
		self._fields = fields

	def get(self, fieldname, default=None):
		return self._fields.get(fieldname, default)


class TestValidateProductionType(unittest.TestCase):
	"""Exactly one of the five production type checkboxes may be selected."""

	def _validate(self, **fields):
		from prakash_steel.utils.work_order import validate_production_type

		with patch(f"{MOD}.frappe") as mock_frappe:
			mock_frappe.throw.side_effect = Exception("throw")
			validate_production_type(_WorkOrderStub(**fields))
			return mock_frappe

	def _assert_throws(self, **fields):
		with self.assertRaises(Exception):
			self._validate(**fields)

	def test_allows_each_production_type_on_its_own(self):
		from prakash_steel.utils.work_order import PRODUCTION_TYPE_FIELDS

		for fieldname, _label in PRODUCTION_TYPE_FIELDS:
			with self.subTest(fieldname=fieldname):
				mock_frappe = self._validate(**{fieldname: 1})
				mock_frappe.throw.assert_not_called()

	def test_throws_when_nothing_is_selected(self):
		self._assert_throws()
		self._assert_throws(custom_bright_production=0, custom_cutting=0)

	def test_throws_for_any_pair_of_production_types(self):
		from prakash_steel.utils.work_order import PRODUCTION_TYPE_FIELDS

		fieldnames = [fieldname for fieldname, _label in PRODUCTION_TYPE_FIELDS]
		for first, second in itertools.combinations(fieldnames, 2):
			with self.subTest(first=first, second=second):
				self._assert_throws(**{first: 1, second: 1})

	def test_conflict_message_lists_the_selected_types(self):
		from prakash_steel.utils.work_order import validate_production_type

		with patch(f"{MOD}.frappe") as mock_frappe:
			mock_frappe.throw.side_effect = Exception("throw")
			with self.assertRaises(Exception):
				validate_production_type(
					_WorkOrderStub(custom_annealing=1, custom_cutting=1)
				)

		message = mock_frappe.throw.call_args[0][0]
		self.assertIn("Annealing", message)
		self.assertIn("Cutting", message)
		self.assertNotIn("Bright Production", message)


class _JobCardStub:
	def __init__(self, work_order="WO-0001", name="JC-0001"):
		self.work_order = work_order
		self.name = name
		self.values = {}

	def set(self, fieldname, value):
		self.values[fieldname] = value


def _work_order_production_types(**selected):
	from prakash_steel.utils.work_order import PRODUCTION_TYPE_FIELDS

	return {fieldname: cint(selected.get(fieldname, 0)) for fieldname, _label in PRODUCTION_TYPE_FIELDS}


class TestJobCardProductionTypeSync(unittest.TestCase):
	"""Job Card mirrors whichever production type is selected on the Work Order."""

	def test_copies_every_production_type_from_work_order(self):
		from prakash_steel.utils.work_order import PRODUCTION_TYPE_FIELDS, copy_production_type_to_job_card

		for fieldname, _label in PRODUCTION_TYPE_FIELDS:
			with self.subTest(fieldname=fieldname):
				with patch(f"{MOD}.frappe") as mock_frappe:
					mock_frappe.db.get_value.return_value = _work_order_production_types(**{fieldname: 1})
					copy_production_type_to_job_card(_JobCardStub())

				mock_frappe.db.set_value.assert_called_once()
				doctype, name, values = mock_frappe.db.set_value.call_args[0]
				self.assertEqual(doctype, "Job Card")
				self.assertEqual(name, "JC-0001")
				self.assertEqual(values, _work_order_production_types(**{fieldname: 1}))

	def test_lock_overwrites_job_card_with_work_order_selection(self):
		from prakash_steel.utils.work_order import lock_production_type_from_work_order

		doc = _JobCardStub()
		with patch(f"{MOD}.frappe") as mock_frappe:
			mock_frappe.db.get_value.return_value = _work_order_production_types(custom_straightning=1)
			lock_production_type_from_work_order(doc)

		self.assertEqual(doc.values, _work_order_production_types(custom_straightning=1))

	def test_skips_when_job_card_has_no_work_order(self):
		from prakash_steel.utils.work_order import (
			copy_production_type_to_job_card,
			lock_production_type_from_work_order,
		)

		doc = _JobCardStub(work_order=None)
		with patch(f"{MOD}.frappe") as mock_frappe:
			copy_production_type_to_job_card(doc)
			lock_production_type_from_work_order(doc)

		mock_frappe.db.get_value.assert_not_called()
		mock_frappe.db.set_value.assert_not_called()
		self.assertEqual(doc.values, {})

	def test_skips_when_work_order_is_missing(self):
		from prakash_steel.utils.work_order import (
			copy_production_type_to_job_card,
			lock_production_type_from_work_order,
		)

		doc = _JobCardStub()
		with patch(f"{MOD}.frappe") as mock_frappe:
			mock_frappe.db.get_value.return_value = None
			copy_production_type_to_job_card(doc)
			lock_production_type_from_work_order(doc)

		mock_frappe.db.set_value.assert_not_called()
		self.assertEqual(doc.values, {})
