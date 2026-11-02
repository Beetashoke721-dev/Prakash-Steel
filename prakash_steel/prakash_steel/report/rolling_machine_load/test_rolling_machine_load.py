# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for rolling_machine_load report — no DB required."""

import unittest
from unittest.mock import patch

from frappe import _dict

from prakash_steel.prakash_steel.report.rolling_machine_load import rolling_machine_load as rml


class TestRollingMachineLoad(unittest.TestCase):
	def _run(self, items, per_hour, net_order, stock, open_so=None, qd=0, parents=None, parent_flags=None):
		with patch.object(rml, "frappe") as mock_frappe, \
			patch.object(rml, "compute_universe_net_order_recommendations", return_value=(net_order, {})), \
			patch.object(rml, "get_planning_stock_map", return_value=stock), \
			patch.object(rml, "get_qualified_demand_map", return_value=({}, {})), \
			patch.object(rml, "calculate_spike_map", return_value={}), \
			patch.object(rml, "get_qualified_demand_for_item", return_value=(qd, None, None)), \
			patch.object(rml, "apply_spike_threshold", side_effect=lambda q, *a: q), \
			patch.object(rml, "get_sales_order_qty_map", return_value=open_so or {}), \
			patch.object(rml, "get_parent_bom_map", return_value=parents or {}):
			mock_frappe.get_cached_doc.return_value = _dict(machine_name=None, oee=80, runtime=20)
			mock_frappe.db.sql.return_value = items
			mock_frappe.db.get_all.return_value = [
				_dict(item_code=k, per_hour_planned_qty=v) for k, v in per_hour.items()
			]
			mock_frappe.get_all.side_effect = lambda doctype, **kw: (
				[_dict(name=k, custom_buffer_flag=v) for k, v in (parent_flags or {}).items()]
				if doctype == "Item" else []
			)
			return rml.get_data()[0]

	def test_single_hardcoded_machine_row(self):
		with patch.object(rml, "get_item_rows", return_value=[]), patch.object(rml, "frappe") as mock_frappe:
			mock_frappe.get_cached_doc.return_value = _dict(machine_name=None, oee=80, runtime=20)
			_, data = rml.execute({})
		self.assertEqual(data, [{
			"machine_name": "Rolling Machine", "no_of_machines": 1,
			"net_prod_load": 0, "net_order_load": 0,
		}])

	def test_mto_load(self):
		items = [_dict(item_code="RB-A", buffer_flag="Non-Buffer", item_type="RB", tog=0)]
		row = self._run(items, {"RB-A": 10}, {"RB-A": 400}, {"RB-A": 100}, open_so={"RB-A": 500})
		eff = 16.0
		# prod: 400 / 10 = 40 h ; order: (500 - 100) / 10 = 40 h
		self.assertEqual(row["net_prod_load"], rml._round_half_up(40 / eff / rml.NO_OF_MACHINES, 1))
		self.assertEqual(row["net_order_load"], rml._round_half_up(40 / eff / rml.NO_OF_MACHINES, 1))

	def test_buffer_order_uses_qualified_demand(self):
		items = [_dict(item_code="RB-B", buffer_flag="Buffer", item_type="RB", tog=50)]
		row = self._run(items, {"RB-B": 10}, {"RB-B": 0}, {"RB-B": 20}, open_so={"RB-B": 9999}, qd=180)
		eff = 16.0
		self.assertEqual(row["net_prod_load"], 0)
		self.assertEqual(row["net_order_load"], rml._round_half_up(16 / eff, 1))

	def test_rbmto_falls_back_to_single_buffer_parent_per_hour(self):
		items = [_dict(item_code="RB-C", buffer_flag="Non-Buffer", item_type="RB", tog=0)]
		parents = {"RB-C": [{"parent_item": "BB-P", "bom_qty": 1, "bom_quantity": 1}]}
		row = self._run(
			items, {"BB-P": 20}, {"RB-C": 400}, {}, parents=parents, parent_flags={"BB-P": "Buffer"}
		)
		self.assertEqual(row["net_prod_load"], rml._round_half_up(20 / 16.0, 1))

	def test_no_per_hour_qty_contributes_nothing(self):
		items = [_dict(item_code="RB-D", buffer_flag="Non-Buffer", item_type="RB", tog=0)]
		row = self._run(items, {}, {"RB-D": 400}, {}, open_so={"RB-D": 500})
		self.assertEqual((row["net_prod_load"], row["net_order_load"]), (0, 0))

	def test_machine_name_and_runtime_from_rolling_machine_doctype(self):
		with patch.object(rml, "get_item_rows", return_value=[{"prod_hours": 38, "order_hours": 0}]), \
			patch.object(rml, "frappe") as mock_frappe:
			mock_frappe.get_cached_doc.return_value = _dict(machine_name="RM-1", oee=50, runtime=19)
			row = rml.get_data()[0]
		# 38 h / (19 * 0.5) = 4.0 days
		self.assertEqual((row["machine_name"], row["net_prod_load"]), ("RM-1", 4.0))

	def test_zero_oee_gives_zero_load(self):
		with patch.object(rml, "get_item_rows", return_value=[{"prod_hours": 38, "order_hours": 5}]), \
			patch.object(rml, "frappe") as mock_frappe:
			mock_frappe.get_cached_doc.return_value = _dict(machine_name="", oee=0, runtime=19)
			row = rml.get_data()[0]
		self.assertEqual((row["net_prod_load"], row["net_order_load"]), (0, 0))
