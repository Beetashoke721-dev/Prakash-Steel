import math

import frappe


def update_jwo_on_sales_invoice_submit(doc, method) -> None:
	jwo_name = doc.get("custom_job_work_order")
	if not jwo_name:
		return

	jwo = frappe.get_doc("JOB Work Order", jwo_name)
	if jwo.job_work_type != "Sale-Purchase":
		return

	_update_transferred_qty(jwo, "Sales Invoice", "Sales Invoice Item")
	_set_transfer_status(jwo)
	_update_loss_per(jwo)
	_update_qty_available_with_party(jwo)
	frappe.publish_realtime("jwo_updated", {"name": jwo_name}, after_commit=True)


def update_jwo_on_delivery_note_submit(doc, method) -> None:
	jwo_name = doc.get("custom_job_work_order")
	if not jwo_name:
		return

	jwo = frappe.get_doc("JOB Work Order", jwo_name)
	if jwo.job_work_type != "Subcontracting":
		return

	_update_transferred_qty(jwo, "Delivery Note", "Delivery Note Item")
	_set_transfer_status(jwo)
	_update_loss_per(jwo)
	_update_qty_available_with_party(jwo)
	frappe.publish_realtime("jwo_updated", {"name": jwo_name}, after_commit=True)


def update_jwo_on_purchase_receipt_submit(doc, method) -> None:
	jwo_name = doc.get("custom_job_work_order")
	if not jwo_name:
		return

	jwo = frappe.get_doc("JOB Work Order", jwo_name)

	# Update per-row actual_received_qty in child table
	for row in jwo.work_item_table:
		if not row.fg_item:
			continue

		total = (
			frappe.db.sql(
				"""
			SELECT COALESCE(SUM(pri.qty), 0)
			FROM `tabPurchase Receipt Item` pri
			JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
			WHERE pr.custom_job_work_order = %s
			  AND pr.docstatus = 1
			  AND pri.item_code = %s
			""",
				(jwo.name, row.fg_item),
			)[0][0]
			or 0
		)

		frappe.db.set_value("JOB Work Item table", row.name, "actual_received_qty", total)

	jwo.reload()
	_update_total_received_qty(jwo)
	_update_qty_available_with_party(jwo)
	_set_received_status(jwo)
	_update_loss_per(jwo)
	frappe.publish_realtime("jwo_updated", {"name": jwo.name}, after_commit=True)


def _update_transferred_qty(jwo, parent_doctype, child_doctype) -> None:
	"""Sum ALL item qty from all submitted docs and set actual_transferred_qty on parent JWO."""
	total = (
		frappe.db.sql(
			f"""
		SELECT COALESCE(SUM(ci.qty), 0)
		FROM `tab{child_doctype}` ci
		JOIN `tab{parent_doctype}` p ON p.name = ci.parent
		WHERE p.custom_job_work_order = %s
		  AND p.docstatus = 1
		""",
			(jwo.name,),
		)[0][0]
		or 0
	)

	frappe.db.set_value("JOB Work Order", jwo.name, "actual_transferred_qty", total)


def _update_total_received_qty(jwo) -> None:
	"""Sum all child rows' actual_received_qty and set total_received_qty on parent JWO."""
	total = sum(row.actual_received_qty or 0 for row in jwo.work_item_table)
	frappe.db.set_value("JOB Work Order", jwo.name, "total_received_qty", total)


def _set_transfer_status(jwo) -> None:
	"""Pending → In-Process → Material Transferred based on actual_transferred_qty vs sum of rm_qty_required."""
	jwo.reload()
	total_required = sum(row.rm_qty_required or 0 for row in jwo.work_item_table if row.raw_material)
	transferred = jwo.actual_transferred_qty or 0

	if total_required > 0 and transferred >= total_required:
		new_status = "Material Transferred"
	elif transferred > 0:
		new_status = "In-Process"
	else:
		new_status = "Pending"

	frappe.db.set_value("JOB Work Order", jwo.name, "status", new_status)


def _set_received_status(jwo) -> None:
	"""Pending → Partially Received → Completed based on total_received_qty vs sum of fg_production_qty."""
	jwo.reload()
	total_required = sum(row.fg_production_qty or 0 for row in jwo.work_item_table if row.fg_item)
	received = jwo.total_received_qty or 0

	if total_required > 0 and received >= total_required:
		new_status = "Completed"
	elif received > 0:
		new_status = "Partially Received"
	else:
		new_status = "Pending"

	frappe.db.set_value("JOB Work Order", jwo.name, "status", new_status)


def _update_loss_per(jwo) -> None:
	"""loss_per = ((actual_transferred_qty - total_received_qty) / actual_transferred_qty) * 100. Min 0."""
	jwo.reload()
	transferred = jwo.actual_transferred_qty or 0
	received = jwo.total_received_qty or 0

	if transferred > 0:
		loss_per = max((transferred - received) / transferred * 100, 0)
	else:
		loss_per = 0

	frappe.db.set_value("JOB Work Order", jwo.name, "loss_per", round(loss_per, 2))


def _update_qty_available_with_party(jwo) -> None:
	"""qty_available_with_party = actual_transferred_qty - sum(rm_back per row)
	where rm_back = ceil((actual_received_qty / bom_fg_qty) * bom_rm_qty)."""
	jwo.reload()
	total_rm_back = 0
	for row in jwo.work_item_table:
		received_fg = row.actual_received_qty or 0

		if received_fg and row.default_bom:
			bom = frappe.db.get_value("BOM", row.default_bom, ["quantity", "name"], as_dict=True)
			if bom:
				bom_rm_qty = frappe.db.get_value("BOM Item", {"parent": row.default_bom}, "qty") or 0
				bom_fg_qty = bom.quantity or 0
				if bom_fg_qty:
					total_rm_back += math.ceil((received_fg / bom_fg_qty) * bom_rm_qty)

	transferred = jwo.actual_transferred_qty or 0
	qty_available = max(transferred - total_rm_back, 0)
	frappe.db.set_value("JOB Work Order", jwo.name, "qty_available_with_party", qty_available)
