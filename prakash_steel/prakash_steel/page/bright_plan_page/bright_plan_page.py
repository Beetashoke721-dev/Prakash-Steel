import frappe


@frappe.whitelist()
def get_bright_plan_data():
	from prakash_steel.prakash_steel.report.bright_plan.bright_plan import execute

	columns, data = execute()

	# Build item_code -> [machine_group_names] map from all rows in Bright Machine Master Table
	rows = frappe.db.sql(
		"""
		SELECT bmm.item_code, bmmt.machine_group_name
		FROM `tabBright Machine Master` bmm
		INNER JOIN `tabBright Machine Master Table` bmmt ON bmmt.parent = bmm.name
		ORDER BY bmm.item_code, bmmt.idx
		""",
		as_dict=True,
	)
	machine_groups = {}
	for r in rows:
		machine_groups.setdefault(r.item_code, []).append(r.machine_group_name)

	return {"columns": columns, "data": data, "machine_groups": machine_groups}
