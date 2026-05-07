# Copyright (c) 2026, beetashoke chakraborty and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestBrightBarProduction(FrappeTestCase):
	"""Unit tests for BrightBarProduction doctype business logic."""

	def _make_doc(self, **overrides):
		"""Build an in-memory BrightBarProduction document (no DB insert)."""
		data = {
			"doctype": "Bright Bar Production",
			"production_date": "2026-01-01",
			"material": "10MM BRIGHT BAR RM",
			"actual_rm_consumption": 500,
			"rm_source_warehouse": "Bright Bar Unit - PSPL",
			"finished": "10MM BRIGHT BAR FG",
			"fg_weight": 450,
			"fg_target_warehouse": "Bright Bar Unit - PSPL",
			"die_number": "D-001",
			"finish_length": "3000MM",
			"tolerance": "+/- 0.5",
			"end_cutting_weight": 10,
			"end_cutting_item": "WASTAGE SCRAP",
			"machine_name": "BBU-MACHINE-1",
			"custom_posting_time": "08:00:00",
		}
		data.update(overrides)
		return frappe.get_doc(data)

	# ------------------------------------------------------------------ #
	# on_submit — early field validations                                 #
	# ------------------------------------------------------------------ #

	@patch("frappe.log_error")
	def test_on_submit_raises_when_material_missing(self, _log_error):
		"""Throws when raw material (material) is not set."""
		doc = self._make_doc(material=None)
		with self.assertRaises(frappe.ValidationError):
			doc.on_submit()

	@patch("frappe.log_error")
	def test_on_submit_raises_when_actual_rm_consumption_zero(self, _log_error):
		"""Throws when actual_rm_consumption is 0."""
		doc = self._make_doc(actual_rm_consumption=0)
		with self.assertRaises(frappe.ValidationError):
			doc.on_submit()

	@patch("frappe.log_error")
	def test_on_submit_raises_when_actual_rm_consumption_negative(self, _log_error):
		"""Throws when actual_rm_consumption is negative."""
		doc = self._make_doc(actual_rm_consumption=-10)
		with self.assertRaises(frappe.ValidationError):
			doc.on_submit()

	@patch("frappe.log_error")
	def test_on_submit_raises_when_rm_source_warehouse_missing(self, _log_error):
		"""Throws when rm_source_warehouse is not set."""
		doc = self._make_doc(rm_source_warehouse=None)
		with self.assertRaises(frappe.ValidationError):
			doc.on_submit()

	@patch("frappe.log_error")
	def test_on_submit_raises_when_finished_missing(self, _log_error):
		"""Throws when finished good (finished) is not set."""
		doc = self._make_doc(finished=None)
		with self.assertRaises(frappe.ValidationError):
			doc.on_submit()

	@patch("frappe.log_error")
	def test_on_submit_raises_when_fg_weight_zero(self, _log_error):
		"""Throws when fg_weight is 0."""
		doc = self._make_doc(fg_weight=0)
		with self.assertRaises(frappe.ValidationError):
			doc.on_submit()

	@patch("frappe.log_error")
	def test_on_submit_raises_when_fg_target_warehouse_missing(self, _log_error):
		"""Throws when fg_target_warehouse is not set."""
		doc = self._make_doc(fg_target_warehouse=None)
		with self.assertRaises(frappe.ValidationError):
			doc.on_submit()

	# ------------------------------------------------------------------ #
	# update_production_plan_qty_from_fg_weight — no-op guard paths      #
	# ------------------------------------------------------------------ #

	def test_update_production_plan_qty_skips_when_no_production_plan(self):
		"""Returns early when production_plan is not set."""
		doc = self._make_doc()
		doc.production_plan = None
		doc.update_production_plan_qty_from_fg_weight()  # must not raise

	def test_update_production_plan_qty_skips_when_no_finished(self):
		"""Returns early when finished is not set."""
		doc = self._make_doc()
		doc.production_plan = "PP-BRIGHT-0001"
		doc.finished = None
		doc.update_production_plan_qty_from_fg_weight()  # must not raise

	def test_update_production_plan_qty_skips_when_fg_weight_zero(self):
		"""Returns early when fg_weight is 0."""
		doc = self._make_doc()
		doc.production_plan = "PP-BRIGHT-0001"
		doc.fg_weight = 0
		doc.update_production_plan_qty_from_fg_weight()  # must not raise

	@patch("frappe.get_all", return_value=[])
	def test_update_production_plan_qty_no_op_when_no_matching_rows(self, _get_all):
		"""No db.set_value call when no Production Plan Item rows match."""
		doc = self._make_doc()
		doc.production_plan = "PP-BRIGHT-0001"
		doc.update_production_plan_qty_from_fg_weight()  # must not raise

	@patch("frappe.log_error")
	@patch("frappe.db.commit")
	@patch("frappe.db.set_value")
	@patch("frappe.get_all")
	def test_update_production_plan_qty_accumulates_fg_weight(
		self, mock_get_all, mock_set_value, _commit, _log_error
	):
		"""Adds fg_weight to the existing custom_production_qty."""
		mock_get_all.return_value = [frappe._dict({"name": "PP-ITEM-0001", "custom_production_qty": 200})]
		doc = self._make_doc()
		doc.production_plan = "PP-BRIGHT-0001"
		doc.finished = "10MM BRIGHT BAR FG"
		doc.fg_weight = 100
		doc.update_production_plan_qty_from_fg_weight()
		mock_set_value.assert_called_once_with(
			"Production Plan Item", "PP-ITEM-0001", "custom_production_qty", 300.0
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
		doc.production_plan = "PP-BRIGHT-0001"
		doc.finished = "10MM BRIGHT BAR FG"
		doc.fg_weight = 150
		doc.update_production_plan_qty_from_fg_weight()
		mock_set_value.assert_called_once_with(
			"Production Plan Item", "PP-ITEM-0002", "custom_production_qty", 150.0
		)

	# ------------------------------------------------------------------ #
	# update_production_planning_produced_qty — no-op guard paths         #
	# ------------------------------------------------------------------ #

	def test_update_production_planning_produced_qty_skips_when_no_production_planning(self):
		"""Returns early when production_planning is not set."""
		doc = self._make_doc()
		doc.production_planning = None
		doc.update_production_planning_produced_qty()  # must not raise

	def test_update_production_planning_produced_qty_skips_when_no_finished(self):
		"""Returns early when finished is not set."""
		doc = self._make_doc()
		doc.production_planning = "PP-BRIGHT-0001"
		doc.finished = None
		doc.update_production_planning_produced_qty()  # must not raise

	# ------------------------------------------------------------------ #
	# before_cancel                                                        #
	# ------------------------------------------------------------------ #

	@patch("frappe.db.get_value", return_value=1)
	def test_before_cancel_blocks_when_stock_entry_submitted(self, _get_value):
		"""Throws when linked Stock Entry is submitted (docstatus=1)."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = "BU-2026-00001"
		with self.assertRaises(frappe.ValidationError):
			doc.before_cancel()

	@patch("frappe.db.get_value", return_value=0)
	def test_before_cancel_blocks_when_stock_entry_draft(self, _get_value):
		"""Throws when linked Stock Entry is draft (docstatus=0)."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = "BU-2026-00001"
		with self.assertRaises(frappe.ValidationError):
			doc.before_cancel()

	@patch("frappe.db.get_value", return_value=2)
	def test_before_cancel_allows_when_stock_entry_cancelled(self, _get_value):
		"""Allows cancel when linked Stock Entry is already cancelled (docstatus=2)."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = "BU-2026-00001"
		doc.before_cancel()  # must not raise

	def test_before_cancel_allows_when_no_stock_entry_linked(self):
		"""Allows cancel when no Stock Entry is linked."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = None
		doc.before_cancel()  # must not raise

	def test_before_cancel_skips_validation_for_cancel_all_flow(self):
		"""Skips block when called via 'Cancel All Documents' from Stock Entry."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = "BU-2026-00001"
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
		doc.name = "2026-01-01 - 10MM BRIGHT BAR FG-10MM BRIGHT BAR RM-450"
		doc.custom_stock_entry_id = "BU-2026-00001"
		doc.on_cancel()
		self.assertEqual(doc.custom_stock_entry_id, "")
		mock_set_value.assert_called_once_with(
			"Bright Bar Production", doc.name, "custom_stock_entry_id", ""
		)

	@patch("frappe.db.set_value")
	def test_on_cancel_no_op_when_no_stock_entry_id(self, mock_set_value):
		"""Does not call db.set_value when custom_stock_entry_id is empty."""
		doc = self._make_doc()
		doc.name = "2026-01-01 - 10MM BRIGHT BAR FG-10MM BRIGHT BAR RM-450"
		doc.custom_stock_entry_id = ""
		doc.on_cancel()
		mock_set_value.assert_not_called()
