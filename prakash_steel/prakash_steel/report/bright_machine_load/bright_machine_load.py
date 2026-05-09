# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	return columns, data


def get_columns():
	return [
		{
			"label": "Machine Name",
			"fieldname": "machine_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": "No of Machines",
			"fieldname": "no_of_machines",
			"fieldtype": "Int",
			"width": 150,
		},
		{
			"label": "Net Prod Load (Days)",
			"fieldname": "net_prod_load",
			"fieldtype": "Float",
			"width": 180,
		},
		{
			"label": "Net Order Load (Days)",
			"fieldname": "net_order_load",
			"fieldtype": "Float",
			"width": 180,
		},
	]


def get_data():
	machines = frappe.get_all(
		"Bright Machine",
		fields=["machine_group_name", "no_of_machines"],
		order_by="machine_group_name asc",
	)

	data = []
	for m in machines:
		data.append({
			"machine_name": m.machine_group_name,
			"no_of_machines": m.no_of_machines,
			"net_prod_load": 0,
			"net_order_load": 0,
		})

	return data
