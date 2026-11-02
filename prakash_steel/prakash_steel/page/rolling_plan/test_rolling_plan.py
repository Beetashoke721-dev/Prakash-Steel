# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for the Rolling Plan page's Execute (Work Order creation) — no DB required."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from prakash_steel.prakash_steel.page.rolling_plan import rolling_plan as MOD

MACHINE = {"machine_name": "Rolling Machine", "no_of_machines": 1, "runtime": 12, "oee": 40}


class TestExecuteWorkOrders(unittest.TestCase):
	def _run(self, rows, bom="BOM-RB-001", workstation_exists=True, save_error=None):
		wo = MagicMock()
		wo.name = "MFG-WO-0001"
		wo.required_items = [SimpleNamespace(source_warehouse="Stores - PSPL")]
		wo.operations = [SimpleNamespace(workstation="Some Other")]
		if save_error:
			wo.save.side_effect = save_error

		with patch.object(MOD, "frappe") as mock_frappe, \
			patch.object(MOD, "require_all_permissions"), \
			patch.object(MOD, "get_machine", return_value=MACHINE), \
			patch.object(MOD, "_get_bom_for_row", return_value=bom) as get_bom:
			mock_frappe.db.exists.return_value = workstation_exists
			mock_frappe.new_doc.return_value = wo
			mock_frappe.conf.developer_mode = 0
			result = MOD.execute_work_orders(rows)
		return result, wo, mock_frappe, get_bom

	def test_creates_rolled_work_order_from_plan_qty(self):
		rows = [{
			"item_code": "50mm Round MS", "child_item_code": "Billet MS", "plan_qty": 2500,
			"planned_start_date": "2026-10-31", "shift_type": "Night",
		}]
		result, wo, _, get_bom = self._run(rows)

		self.assertEqual(result, {"created": ["MFG-WO-0001"], "errors": []})
		get_bom.assert_called_once_with("50mm Round MS", "Billet MS")
		self.assertEqual(wo.qty, 2500)
		self.assertEqual(wo.bom_no, "BOM-RB-001")
		self.assertEqual(wo.custom_rolled_production, 1)
		self.assertEqual(wo.wip_warehouse, "Work In Progress - PSPL")
		self.assertEqual(wo.fg_warehouse, "Rolling Mill - PSPL")
		self.assertEqual(wo.source_warehouse, "Rolling Mill - PSPL")
		self.assertEqual(wo.required_items[0].source_warehouse, "Rolling Mill - PSPL")
		self.assertEqual(wo.operations[0].workstation, "Rolling Machine")
		self.assertEqual(wo.custom_machine_name, "Rolling Machine")
		self.assertEqual(wo.custom_shift_type, "Night")
		self.assertEqual(wo.planned_start_date, "2026-10-31")
		wo.save.assert_called_once()
		wo.submit.assert_not_called()  # left as draft for the user to submit

	def test_rows_without_qty_are_skipped(self):
		result, _, mock_frappe, _ = self._run([{"item_code": "X", "plan_qty": 0}, {"plan_qty": 10}])
		self.assertEqual(result, {"created": [], "errors": []})
		mock_frappe.new_doc.assert_not_called()

	def test_missing_bom_is_reported(self):
		result, _, mock_frappe, _ = self._run([{"item_code": "X", "plan_qty": 5}], bom=None)
		self.assertEqual(result["created"], [])
		self.assertIn("No active BOM", result["errors"][0])
		mock_frappe.new_doc.assert_not_called()

	def test_operations_untouched_when_workstation_missing(self):
		_, wo, _, _ = self._run([{"item_code": "X", "plan_qty": 5}], workstation_exists=False)
		self.assertEqual(wo.operations[0].workstation, "Some Other")

	def test_failed_save_rolls_back_to_savepoint(self):
		result, _, mock_frappe, _ = self._run(
			[{"item_code": "X", "plan_qty": 5}], save_error=Exception("boom")
		)
		self.assertEqual(result["created"], [])
		self.assertIn("boom", result["errors"][0])
		savepoint = mock_frappe.db.savepoint.call_args[0][0]
		mock_frappe.db.rollback.assert_called_once_with(save_point=savepoint)


if __name__ == "__main__":
	unittest.main()
