# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from prakash_steel.utils.whitelist_permissions import require_all_permissions, require_permission


_COMPANY = "Prakash Steel Products Pvt Ltd"


class JOBWorkOrder(Document):
	def on_submit(self) -> None:
		self.db_set("status", "Pending")


def _jwo_pr_received_fg_qty_by_item(jwo_name) -> dict:
	rows = frappe.db.sql(
		"""
		SELECT pri.item_code, COALESCE(SUM(pri.qty), 0)
		FROM `tabPurchase Receipt Item` pri
		INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
		WHERE pr.custom_job_work_order = %s AND pr.docstatus = 1
		GROUP BY pri.item_code
		""",
		(jwo_name,),
	)
	return {r[0]: flt(r[1]) for r in rows}


def _jwo_transferred_rm_qty_by_item(jwo_name, job_work_type) -> dict:
	if job_work_type == "Subcontracting":
		rows = frappe.db.sql(
			"""
			SELECT dni.item_code, COALESCE(SUM(dni.qty), 0)
			FROM `tabDelivery Note Item` dni
			INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
			WHERE dn.custom_job_work_order = %s AND dn.docstatus = 1
			GROUP BY dni.item_code
			""",
			(jwo_name,),
		)
	elif job_work_type == "Sale-Purchase":
		rows = frappe.db.sql(
			"""
			SELECT sii.item_code, COALESCE(SUM(sii.qty), 0)
			FROM `tabSales Invoice Item` sii
			INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
			WHERE si.custom_job_work_order = %s AND si.docstatus = 1
			GROUP BY sii.item_code
			""",
			(jwo_name,),
		)
	else:
		return {}
	return {r[0]: flt(r[1]) for r in rows}


def _jwo_has_submitted_rm_transfer(jwo_name, job_work_type) -> bool:
	if job_work_type == "Subcontracting":
		return bool(frappe.db.exists("Delivery Note", {"custom_job_work_order": jwo_name, "docstatus": 1}))
	if job_work_type == "Sale-Purchase":
		return bool(frappe.db.exists("Sales Invoice", {"custom_job_work_order": jwo_name, "docstatus": 1}))
	return False


def _validate_jwo_update_items(doc, items, original_by_name, incoming_names) -> None:
	received_fg = _jwo_pr_received_fg_qty_by_item(doc.name)
	transferred_rm = _jwo_transferred_rm_qty_by_item(doc.name, doc.job_work_type)
	lock_raw_material = _jwo_has_submitted_rm_transfer(doc.name, doc.job_work_type)

	# Cannot remove a work-item row if a submitted Purchase Receipt already references that FG item.
	for row in doc.work_item_table:
		if row.name in incoming_names:
			continue
		fg = row.fg_item
		if fg and flt(received_fg.get(fg, 0)) > 0:
			frappe.throw(
				_(
					"Cannot remove this row ({0}): a submitted Purchase Receipt already includes "
					"finished good {1}. You can add new rows or increase quantities beyond the received quantity."
				).format(row.idx, frappe.bold(fg)),
				title=_("Purchase Receipt"),
			)

	new_rm_totals = {}
	new_fg_totals = {}
	for item in items:
		rm = item.get("raw_material")
		fg = item.get("fg_item")
		rmq = cint(item.get("rm_qty_required") or 0)
		fgq = cint(item.get("fg_production_qty") or 0)
		if rm:
			new_rm_totals[rm] = new_rm_totals.get(rm, 0) + rmq
		if fg:
			new_fg_totals[fg] = new_fg_totals.get(fg, 0) + fgq

	# RM required (summed by item) must stay at least what was already transferred on SI/DN.
	for rm_item, delivered in transferred_rm.items():
		if delivered <= 0:
			continue
		total_req = flt(new_rm_totals.get(rm_item, 0))
		if total_req + 1e-9 < delivered:
			frappe.throw(
				_(
					"Total RM Qty Required for {0} is {1}, but submitted transfer documents already "
					"show {2} for this Job Work Order. Increase the total to at least {2}."
				).format(frappe.bold(rm_item), int(total_req), int(delivered)),
				title=_("Transfer quantity"),
			)

	# Total FG production (summed by FG item) must cover what Purchase Receipt already received.
	for fg_item, rec in received_fg.items():
		if rec <= 0:
			continue
		total_fg = flt(new_fg_totals.get(fg_item, 0))
		if total_fg + 1e-9 < rec:
			frappe.throw(
				_(
					"Total FG Production Qty for {0} is {1}, but submitted Purchase Receipts already "
					"show {2} for this Job Work Order. Increase the total to at least {2}."
				).format(frappe.bold(fg_item), int(total_fg), int(rec)),
				title=_("Purchase Receipt"),
			)

	# After a Delivery Note (Subcontracting) or Sales Invoice (Sale-Purchase), do not change Raw Material on existing rows.
	if lock_raw_material:
		for item in items:
			name = item.get("name")
			if not name or name not in original_by_name:
				continue
			old_rm = original_by_name[name].get("raw_material") or ""
			new_rm = item.get("raw_material") or ""
			if old_rm != new_rm:
				frappe.throw(
					_(
						"Cannot change Raw Material on an existing row after a transfer document "
						"(Delivery Note / Sales Invoice) is submitted for this Job Work Order."
					),
					title=_("Raw Material"),
				)

		# All rows that have a Raw Material must use the same item (no mixing RM types after transfer).
		rms = {item.get("raw_material") for item in items if item.get("raw_material")}
		if len(rms) > 1:
			frappe.throw(
				_("After a transfer document is submitted, every line must use the same Raw Material item."),
				title=_("Raw Material"),
			)


@frappe.whitelist()
def update_work_items(source_name, items) -> None:
	"""Sync work_item_table from the Update Items dialog: update, append new rows, and delete removed rows.

	Same idea as ERPNext ``validate_and_delete_children`` + update: any existing child name not present
	in the submitted list is removed.
	"""
	require_permission("JOB Work Order", "write")
	import json

	if isinstance(items, str):
		items = json.loads(items)
	if not items:
		items = []

	doc = frappe.get_doc("JOB Work Order", source_name)
	original_by_name = {
		r.name: {"fg_item": r.fg_item, "raw_material": r.raw_material} for r in doc.work_item_table
	}
	incoming_names = {item.get("name") for item in items if item.get("name")}

	_validate_jwo_update_items(doc, items, original_by_name, incoming_names)

	for row in list(doc.work_item_table):
		if row.name not in incoming_names:
			doc.remove(row)

	existing_by_name = {row.name: row for row in doc.work_item_table}

	for item in items:
		docname = item.get("name")
		if docname and docname in existing_by_name:
			row = existing_by_name[docname]
			row.fg_item = item.get("fg_item")
			row.default_bom = item.get("default_bom")
			row.fg_production_qty = item.get("fg_production_qty")
			row.raw_material = item.get("raw_material")
			row.rm_qty_required = item.get("rm_qty_required")
		else:
			doc.append(
				"work_item_table",
				{
					"fg_item": item.get("fg_item"),
					"default_bom": item.get("default_bom"),
					"fg_production_qty": item.get("fg_production_qty"),
					"raw_material": item.get("raw_material"),
					"rm_qty_required": item.get("rm_qty_required"),
				},
			)

	doc.flags.ignore_validate_update_after_submit = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()


def _build_rm_qty_map(work_item_table) -> dict:
	"""Sum rm_qty_required by raw_material across all work item rows."""
	rm_qty_map = {}
	for row in work_item_table:
		if row.raw_material and row.rm_qty_required:
			rm_qty_map[row.raw_material] = rm_qty_map.get(row.raw_material, 0) + (row.rm_qty_required or 0)
	return rm_qty_map


@frappe.whitelist()
def make_sales_invoice(source_name) -> object:
	require_all_permissions(
		[("JOB Work Order", "read"), ("Sales Invoice", "create")],
		_("Not permitted to create Sales Invoice from JOB Work Order."),
	)
	source = frappe.get_doc("JOB Work Order", source_name)

	si = frappe.new_doc("Sales Invoice")
	si.company = _COMPANY
	si.customer = source.customer
	si.posting_date = source.job_work_date
	si.custom_job_work_order = source_name

	rm_qty_map = _build_rm_qty_map(source.work_item_table)

	for raw_material, total_required in rm_qty_map.items():
		already = (
			frappe.db.sql(
				"""
			SELECT COALESCE(SUM(sii.qty), 0)
			FROM `tabSales Invoice Item` sii
			JOIN `tabSales Invoice` si ON si.name = sii.parent
			WHERE si.custom_job_work_order = %s
			  AND si.docstatus = 1
			  AND sii.item_code = %s
			""",
				(source_name, raw_material),
			)[0][0]
			or 0
		)
		pending_qty = total_required - already
		if pending_qty <= 0:
			continue
		si.append("items", {"item_code": raw_material, "qty": pending_qty})

	si.run_method("set_missing_values")
	si.run_method("calculate_taxes_and_totals")
	return si


@frappe.whitelist()
def make_delivery_note(source_name) -> object:
	require_all_permissions(
		[("JOB Work Order", "read"), ("Delivery Note", "create")],
		_("Not permitted to create Delivery Note from JOB Work Order."),
	)
	source = frappe.get_doc("JOB Work Order", source_name)

	dn = frappe.new_doc("Delivery Note")
	dn.company = _COMPANY
	dn.posting_date = source.job_work_date
	dn.customer = source.customer
	dn.custom_job_work_order = source_name

	company_currency = frappe.get_cached_value("Company", dn.company, "default_currency") or "INR"
	dn.currency = company_currency
	dn.conversion_rate = 1

	rm_qty_map = _build_rm_qty_map(source.work_item_table)

	for raw_material, total_required in rm_qty_map.items():
		already = (
			frappe.db.sql(
				"""
			SELECT COALESCE(SUM(dni.qty), 0)
			FROM `tabDelivery Note Item` dni
			JOIN `tabDelivery Note` dn ON dn.name = dni.parent
			WHERE dn.custom_job_work_order = %s
			  AND dn.docstatus = 1
			  AND dni.item_code = %s
			""",
				(source_name, raw_material),
			)[0][0]
			or 0
		)
		pending_qty = total_required - already
		if pending_qty <= 0:
			continue
		dn.append("items", {"item_code": raw_material, "qty": pending_qty})

	dn.run_method("set_missing_values")
	dn.run_method("calculate_taxes_and_totals")
	return dn


@frappe.whitelist()
def make_purchase_receipt(source_name) -> object:
	require_all_permissions(
		[("JOB Work Order", "read"), ("Purchase Receipt", "create")],
		_("Not permitted to create Purchase Receipt from JOB Work Order."),
	)
	source = frappe.get_doc("JOB Work Order", source_name)

	pr = frappe.new_doc("Purchase Receipt")
	pr.company = _COMPANY
	pr.supplier = source.customer
	pr.posting_date = source.job_work_date
	pr.custom_job_work_order = source_name

	company_currency = frappe.get_cached_value("Company", pr.company, "default_currency") or "INR"
	pr.currency = company_currency
	pr.conversion_rate = 1

	for row in source.work_item_table:
		if row.fg_item and row.fg_production_qty:
			pending_qty = (row.fg_production_qty or 0) - (row.actual_received_qty or 0)
			if pending_qty <= 0:
				continue
			pr.append(
				"items",
				{
					"item_code": row.fg_item,
					"qty": pending_qty,
				},
			)

	pr.run_method("set_missing_values")
	pr.run_method("calculate_taxes_and_totals")
	return pr
