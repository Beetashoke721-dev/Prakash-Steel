import frappe


@frappe.whitelist()
def get_bright_plan_data():
	from prakash_steel.prakash_steel.report.bright_plan.bright_plan import execute

	columns, data = execute()
	return {"columns": columns, "data": data}
