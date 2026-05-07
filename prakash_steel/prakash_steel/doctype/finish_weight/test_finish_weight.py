# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestFinishWeight(FrappeTestCase):
	"""Unit tests for FinishWeight doctype business logic."""

	def _make_doc(self, **overrides):
		"""Build an in-memory FinishWeight document (no DB insert)."""
		data = {
			"doctype": "Finish Weight",
			"posting_date": "2026-01-01",
			"item_code": "TEST-FG-10MM",
			"bundling_check": "Good",
			"length": "12000MM",
			"finish_pcs": 100,
			"finish_weight": 5000,
			"fg_per_pcs_weight": 50.0,
			"melting_weight": 100,
			"colour_code": "RED",
			"cooling_pit": "Not Transferred",
			"miss_roll_item": "WASTAGE SCRAP OF STEEL BARS & RODS SCRAP",
			"melting_item": "WASTAGE SCRAP OF STEEL BARS & RODS SCRAP",
			"fg_target_warehouse": "Finish Goods - PSPL",
		}
		data.update(overrides)
		return frappe.get_doc(data)

	# ------------------------------------------------------------------ #
	# validate                                                             #
	# ------------------------------------------------------------------ #

	@patch("frappe.db.get_value", return_value=(1000, 50))
	def test_validate_sets_billet_weight_as_sum_of_linked_doc(self, _get_value):
		"""billet_weight = billet_weight + miss_billet_weight from linked Billet Cutting."""
		doc = self._make_doc(billet_cutting_id="BC-2026-01-01 - 65MM-10MM")
		doc.validate()
		self.assertEqual(doc.billet_weight, 1050)  # 1000 + 50

	@patch("frappe.db.get_value", return_value=(800, 0))
	def test_validate_sets_billet_weight_when_no_miss_billet(self, _get_value):
		"""billet_weight equals billet_weight only when miss_billet_weight is 0."""
		doc = self._make_doc(billet_cutting_id="BC-2026-01-01 - 65MM-10MM")
		doc.validate()
		self.assertEqual(doc.billet_weight, 800)

	def test_validate_skips_when_no_billet_cutting_id(self):
		"""No DB call or error when billet_cutting_id is not set."""
		doc = self._make_doc()
		doc.billet_cutting_id = None
		doc.validate()  # must not raise

	# ------------------------------------------------------------------ #
	# before_submit                                                        #
	# ------------------------------------------------------------------ #

	@patch("frappe.db.get_value", return_value=0)
	def test_before_submit_raises_when_billet_cutting_not_submitted(self, _get_value):
		"""Throws when linked Billet Cutting is not submitted (docstatus != 1)."""
		doc = self._make_doc(billet_cutting_id="BC-2026-01-01 - 65MM-10MM")
		with self.assertRaises(frappe.ValidationError):
			doc.before_submit()

	@patch("frappe.db.get_value", return_value=2)
	def test_before_submit_raises_when_billet_cutting_cancelled(self, _get_value):
		"""Throws when linked Billet Cutting is cancelled (docstatus=2)."""
		doc = self._make_doc(billet_cutting_id="BC-2026-01-01 - 65MM-10MM")
		with self.assertRaises(frappe.ValidationError):
			doc.before_submit()

	@patch("frappe.db.get_value", return_value=1)
	def test_before_submit_passes_when_billet_cutting_submitted(self, _get_value):
		"""No error when linked Billet Cutting is submitted (docstatus=1)."""
		doc = self._make_doc(billet_cutting_id="BC-2026-01-01 - 65MM-10MM")
		doc.before_submit()  # must not raise

	def test_before_submit_skips_when_no_billet_cutting_id(self):
		"""No DB call or error when billet_cutting_id is not set."""
		doc = self._make_doc()
		doc.billet_cutting_id = None
		doc.before_submit()  # must not raise

	# ------------------------------------------------------------------ #
	# on_submit — early field validations                                 #
	# ------------------------------------------------------------------ #

	@patch("frappe.log_error")
	def test_on_submit_raises_when_item_code_missing(self, _log_error):
		"""Throws when item_code is not set."""
		doc = self._make_doc(item_code=None)
		with self.assertRaises(frappe.ValidationError):
			doc.on_submit()

	@patch("frappe.log_error")
	def test_on_submit_raises_when_finish_weight_zero(self, _log_error):
		"""Throws when finish_weight is 0."""
		doc = self._make_doc(finish_weight=0)
		with self.assertRaises(frappe.ValidationError):
			doc.on_submit()

	@patch("frappe.log_error")
	def test_on_submit_raises_when_fg_target_warehouse_missing(self, _log_error):
		"""Throws when fg_target_warehouse is not set."""
		doc = self._make_doc(fg_target_warehouse=None)
		with self.assertRaises(frappe.ValidationError):
			doc.on_submit()

	def test_on_submit_raises_when_melting_item_differs_from_miss_roll_item(self):
		"""Throws when melting_item and miss_roll_item are set but differ."""
		doc = self._make_doc(
			melting_item="SCRAP-A",
			miss_roll_item="SCRAP-B",
		)

		mock_warehouse = MagicMock()
		mock_warehouse.company = "Test Company"
		mock_item = MagicMock()
		mock_item.stock_uom = "Kg"

		def _get_doc(doctype, name=None, *args, **kwargs):
			if isinstance(doctype, dict):
				# frappe.get_doc(dict) call for Stock Entry — return a mock doc
				mock_se = MagicMock()
				return mock_se
			if doctype == "Warehouse":
				return mock_warehouse
			return mock_item

		with patch("frappe.get_doc", side_effect=_get_doc), patch("frappe.log_error"):
			with self.assertRaises(frappe.ValidationError):
				doc.on_submit()

	# ------------------------------------------------------------------ #
	# update_production_plan_qty_from_finish_weight — no-op guard paths  #
	# ------------------------------------------------------------------ #

	def test_update_production_plan_qty_skips_when_no_production_plan(self):
		"""Returns early when production_plan is not set."""
		doc = self._make_doc()
		doc.production_plan = None
		doc.update_production_plan_qty_from_finish_weight()  # must not raise

	def test_update_production_plan_qty_skips_when_no_item_code(self):
		"""Returns early when item_code is not set."""
		doc = self._make_doc()
		doc.production_plan = "PP-ROLLED-0001"
		doc.item_code = None
		doc.update_production_plan_qty_from_finish_weight()  # must not raise

	def test_update_production_plan_qty_skips_when_finish_weight_zero(self):
		"""Returns early when finish_weight is 0."""
		doc = self._make_doc()
		doc.production_plan = "PP-ROLLED-0001"
		doc.finish_weight = 0
		doc.update_production_plan_qty_from_finish_weight()  # must not raise

	@patch("frappe.get_all", return_value=[])
	def test_update_production_plan_qty_no_op_when_no_matching_rows(self, _get_all):
		"""No db.set_value call when no Production Plan Item rows match."""
		doc = self._make_doc()
		doc.production_plan = "PP-ROLLED-0001"
		doc.update_production_plan_qty_from_finish_weight()  # must not raise

	@patch("frappe.log_error")
	@patch("frappe.db.commit")
	@patch("frappe.db.set_value")
	@patch("frappe.get_all")
	def test_update_production_plan_qty_accumulates_finish_weight(
		self, mock_get_all, mock_set_value, _commit, _log_error
	):
		"""Adds finish_weight to the existing custom_production_qty."""
		mock_get_all.return_value = [frappe._dict({"name": "PP-ITEM-0001", "custom_production_qty": 1000})]
		doc = self._make_doc()
		doc.production_plan = "PP-ROLLED-0001"
		doc.finish_weight = 500
		doc.update_production_plan_qty_from_finish_weight()
		mock_set_value.assert_called_once_with(
			"Production Plan Item", "PP-ITEM-0001", "custom_production_qty", 1500.0
		)

	@patch("frappe.log_error")
	@patch("frappe.db.commit")
	@patch("frappe.db.set_value")
	@patch("frappe.get_all")
	def test_update_production_plan_qty_starts_from_zero_when_null(
		self, mock_get_all, mock_set_value, _commit, _log_error
	):
		"""Treats NULL custom_production_qty as 0 when accumulating."""
		mock_get_all.return_value = [frappe._dict({"name": "PP-ITEM-0002", "custom_production_qty": None})]
		doc = self._make_doc()
		doc.production_plan = "PP-ROLLED-0001"
		doc.finish_weight = 300
		doc.update_production_plan_qty_from_finish_weight()
		mock_set_value.assert_called_once_with(
			"Production Plan Item", "PP-ITEM-0002", "custom_production_qty", 300.0
		)

	# ------------------------------------------------------------------ #
	# update_production_planning_produced_qty — no-op guard paths         #
	# ------------------------------------------------------------------ #

	def test_update_production_planning_produced_qty_skips_when_no_production_planning(self):
		"""Returns early when production_planning is not set."""
		doc = self._make_doc()
		doc.production_planning = None
		doc.update_production_planning_produced_qty()  # must not raise

	def test_update_production_planning_produced_qty_skips_when_no_item_code(self):
		"""Returns early when item_code is not set."""
		doc = self._make_doc()
		doc.production_planning = "PP-ROLLED-0001"
		doc.item_code = None
		doc.update_production_planning_produced_qty()  # must not raise

	# ------------------------------------------------------------------ #
	# before_cancel                                                        #
	# ------------------------------------------------------------------ #

	@patch("frappe.db.get_value", return_value=1)
	def test_before_cancel_blocks_when_stock_entry_submitted(self, _get_value):
		"""Throws when linked Stock Entry is submitted (docstatus=1)."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = "RM-2026-00001"
		with self.assertRaises(frappe.ValidationError):
			doc.before_cancel()

	@patch("frappe.db.get_value", return_value=0)
	def test_before_cancel_blocks_when_stock_entry_draft(self, _get_value):
		"""Throws when linked Stock Entry is draft (docstatus=0)."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = "RM-2026-00001"
		with self.assertRaises(frappe.ValidationError):
			doc.before_cancel()

	@patch("frappe.db.get_value", return_value=2)
	def test_before_cancel_allows_when_stock_entry_cancelled(self, _get_value):
		"""Allows cancel when linked Stock Entry is already cancelled (docstatus=2)."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = "RM-2026-00001"
		doc.before_cancel()  # must not raise

	def test_before_cancel_allows_when_no_stock_entry_linked(self):
		"""Allows cancel when no Stock Entry is linked."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = None
		doc.before_cancel()  # must not raise

	def test_before_cancel_skips_validation_for_cancel_all_flow(self):
		"""Skips block when called via 'Cancel All Documents' from Stock Entry."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = "RM-2026-00001"
		frappe.local.form_dict = frappe._dict(
			{"cmd": "frappe.desk.form.linked_with.cancel_all_linked_docs"}
		)
		try:
			doc.before_cancel()  # must not raise
		finally:
			frappe.local.form_dict = frappe._dict()

	# ------------------------------------------------------------------ #
	# on_cancel                                                            #
	# ------------------------------------------------------------------ #

	@patch("frappe.db.set_value")
	def test_on_cancel_clears_custom_stock_entry_id(self, mock_set_value):
		"""Clears custom_stock_entry_id on the doc and in the database."""
		doc = self._make_doc()
		doc.name = "FW/2026/0001"
		doc.custom_stock_entry_id = "RM-2026-00001"
		doc.on_cancel()
		self.assertEqual(doc.custom_stock_entry_id, "")
		mock_set_value.assert_called_once_with(
			"Finish Weight", doc.name, "custom_stock_entry_id", ""
		)

	@patch("frappe.db.set_value")
	def test_on_cancel_no_op_when_no_stock_entry_id(self, mock_set_value):
		"""Does not call db.set_value when custom_stock_entry_id is empty."""
		doc = self._make_doc()
		doc.name = "FW/2026/0001"
		doc.custom_stock_entry_id = ""
		doc.on_cancel()
		mock_set_value.assert_not_called()
