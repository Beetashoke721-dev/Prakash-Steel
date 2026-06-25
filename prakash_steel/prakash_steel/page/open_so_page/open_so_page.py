import frappe

from prakash_steel.utils.whitelist_permissions import require_permission


@frappe.whitelist()
def get_delay_reasons():
	require_permission("Sales Order", "read")
	return frappe.get_all(
		"Delivery Delay Reason Master",
		fields=["name", "delay_reason"],
		order_by="delay_reason asc",
	)


@frappe.whitelist()
def save_delay_info(rows):
	require_permission("Sales Order", "write")
	if isinstance(rows, str):
		import json
		rows = json.loads(rows)

	if not rows:
		return

	for row in rows:
		soi_name = row.get("soi_name")
		if not soi_name:
			continue

		frappe.db.set_value(
			"Sales Order Item",
			soi_name,
			{
				"custom_delay_reasons": row.get("delay_reason") or None,
				"custom_delay_remarks": row.get("delay_remarks") or None,
			},
			update_modified=False,
		)

	frappe.db.commit()
	return {"status": "ok", "updated": len(rows)}
