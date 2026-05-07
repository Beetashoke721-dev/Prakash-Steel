# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestBilletCutting(FrappeTestCase):
	"""Unit tests for BilletCutting doctype business logic."""

	def _make_doc(self, **overrides):
		"""Build an in-memory BilletCutting document (no DB insert)."""
		data = {
			"doctype": "Billet Cutting",
			"posting_date": "2026-01-01",
			"production_planning": "PP-ROLLING-0001",
			"billet_size": "65MM BILLET",
			"finish_size": "TEST-FG-10MM",
			"miss_billet_item": "WASTAGE SCRAP",
			"billet_pcs_full": 10,
			"billet_length_full": 6.0,
			"billet_weight": 1000,
			"total_billet_cutting_pcs": 100,
			"total_raw_material_pcs": 100,
			"cutting_weight_per_pcs": 10.0,
			"miss_billet_pcs": 0,
			"miss_billet_weight": 0,
			"rm_source_warehouse": "Rolling Mill - PSPL",
		}
		data.update(overrides)
		return frappe.get_doc(data)

	# ------------------------------------------------------------------ #
	# validate_miss_billet_weight                                         #
	# ------------------------------------------------------------------ #

	def test_miss_billet_weight_required_when_pcs_positive(self):
		"""Throws ValidationError when miss_billet_pcs > 0 but weight is 0."""
		doc = self._make_doc(miss_billet_pcs=5, miss_billet_weight=0)
		with self.assertRaises(frappe.ValidationError):
			doc.validate_miss_billet_weight()

	def test_miss_billet_weight_required_when_pcs_positive_and_weight_none(self):
		"""Throws ValidationError when miss_billet_pcs > 0 and weight is None."""
		doc = self._make_doc(miss_billet_pcs=3, miss_billet_weight=None)
		with self.assertRaises(frappe.ValidationError):
			doc.validate_miss_billet_weight()

	def test_miss_billet_weight_not_required_when_pcs_zero(self):
		"""No error when miss_billet_pcs == 0 and weight is 0."""
		doc = self._make_doc(miss_billet_pcs=0, miss_billet_weight=0)
		doc.validate_miss_billet_weight()  # must not raise

	def test_miss_billet_weight_passes_when_both_provided(self):
		"""No error when both miss_billet_pcs and miss_billet_weight are > 0."""
		doc = self._make_doc(miss_billet_pcs=3, miss_billet_weight=150)
		doc.validate_miss_billet_weight()  # must not raise

	# ------------------------------------------------------------------ #
	# validate_calculations                                               #
	# ------------------------------------------------------------------ #

	def test_cutting_weight_per_pcs_is_auto_corrected(self):
		"""cutting_weight_per_pcs is recalculated when it deviates by > 0.01."""
		doc = self._make_doc(
			billet_weight=1000,
			total_billet_cutting_pcs=100,
			cutting_weight_per_pcs=5.0,  # wrong — expected 10.0
		)
		doc.validate_calculations()
		self.assertAlmostEqual(doc.cutting_weight_per_pcs, 10.0, places=2)

	def test_cutting_weight_within_tolerance_not_changed(self):
		"""Values within 0.01 tolerance are left unchanged."""
		doc = self._make_doc(
			billet_weight=1000,
			total_billet_cutting_pcs=100,
			cutting_weight_per_pcs=10.005,  # within 0.01 of 10.0
		)
		doc.validate_calculations()
		self.assertAlmostEqual(doc.cutting_weight_per_pcs, 10.005, places=3)

	def test_total_raw_material_pcs_auto_corrected(self):
		"""total_raw_material_pcs is set to total_billet_cutting_pcs + miss_billet_pcs."""
		doc = self._make_doc(
			total_billet_cutting_pcs=100,
			miss_billet_pcs=5,
			total_raw_material_pcs=50,  # wrong
		)
		doc.validate_calculations()
		self.assertEqual(doc.total_raw_material_pcs, 105)

	def test_total_raw_material_pcs_no_correction_when_correct(self):
		"""No change when total_raw_material_pcs already equals the expected value."""
		doc = self._make_doc(
			total_billet_cutting_pcs=100,
			miss_billet_pcs=0,
			total_raw_material_pcs=100,
		)
		doc.validate_calculations()
		self.assertEqual(doc.total_raw_material_pcs, 100)

	def test_cutting_weight_not_calculated_when_pcs_zero(self):
		"""Skips cutting_weight calculation when total_billet_cutting_pcs == 0."""
		doc = self._make_doc(
			billet_weight=1000,
			total_billet_cutting_pcs=0,
			cutting_weight_per_pcs=0.0,
		)
		doc.validate_calculations()  # must not raise ZeroDivisionError
		self.assertAlmostEqual(doc.cutting_weight_per_pcs, 0.0, places=2)

	# ------------------------------------------------------------------ #
	# on_submit — early field validations                                 #
	# ------------------------------------------------------------------ #

	@patch("frappe.log_error")
	def test_on_submit_raises_when_billet_size_missing(self, _log_error):
		"""Throws when billet_size is not set."""
		doc = self._make_doc(billet_size=None)
		with self.assertRaises(frappe.ValidationError):
			doc.on_submit()

	@patch("frappe.log_error")
	def test_on_submit_raises_when_billet_weight_zero(self, _log_error):
		"""Throws when billet_weight is 0."""
		doc = self._make_doc(billet_weight=0)
		with self.assertRaises(frappe.ValidationError):
			doc.on_submit()

	@patch("frappe.log_error")
	def test_on_submit_raises_when_rm_source_warehouse_missing(self, _log_error):
		"""Throws when rm_source_warehouse is not set."""
		doc = self._make_doc(rm_source_warehouse=None)
		with self.assertRaises(frappe.ValidationError):
			doc.on_submit()

	# ------------------------------------------------------------------ #
	# before_cancel                                                        #
	# ------------------------------------------------------------------ #

	@patch("frappe.db.get_value", return_value=1)
	def test_before_cancel_blocks_when_stock_entry_submitted(self, _get_value):
		"""Throws when linked Stock Entry is submitted (docstatus=1)."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = "PRMI-2026-00001"
		with self.assertRaises(frappe.ValidationError):
			doc.before_cancel()

	@patch("frappe.db.get_value", return_value=0)
	def test_before_cancel_blocks_when_stock_entry_draft(self, _get_value):
		"""Throws when linked Stock Entry is draft (docstatus=0)."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = "PRMI-2026-00001"
		with self.assertRaises(frappe.ValidationError):
			doc.before_cancel()

	@patch("frappe.db.get_value", return_value=2)
	def test_before_cancel_allows_when_stock_entry_cancelled(self, _get_value):
		"""Allows cancel when linked Stock Entry is already cancelled (docstatus=2)."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = "PRMI-2026-00001"
		doc.before_cancel()  # must not raise

	def test_before_cancel_allows_when_no_stock_entry_linked(self):
		"""Allows cancel when no Stock Entry is linked."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = None
		doc.before_cancel()  # must not raise

	def test_before_cancel_skips_validation_for_cancel_all_flow(self):
		"""Skips block when called via 'Cancel All Documents' from Stock Entry."""
		doc = self._make_doc()
		doc.custom_stock_entry_id = "PRMI-2026-00001"
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
		doc.name = "2026-01-01 - 65MM BILLET-TEST-FG-10MM"
		doc.custom_stock_entry_id = "PRMI-2026-00001"
		doc.on_cancel()
		self.assertEqual(doc.custom_stock_entry_id, "")
		mock_set_value.assert_called_once_with(
			"Billet Cutting", doc.name, "custom_stock_entry_id", ""
		)

	@patch("frappe.db.set_value")
	def test_on_cancel_no_op_when_no_stock_entry_id(self, mock_set_value):
		"""Does not call db.set_value when custom_stock_entry_id is empty."""
		doc = self._make_doc()
		doc.name = "2026-01-01 - 65MM BILLET-TEST-FG-10MM"
		doc.custom_stock_entry_id = ""
		doc.on_cancel()
		mock_set_value.assert_not_called()
