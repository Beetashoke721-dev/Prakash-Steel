# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from prakash_steel.utils.whitelist_permissions import require_all_permissions, require_permission


class ProductionPlanning(Document):
	def on_submit(self) -> None:
		if "Rolled Plan" not in (self.naming_series or ""):
			return

		created = _create_billet_cutting_for_rows(self.name, self.production_plan, self.shift_type, self.posting_date)
		if created:
			frappe.msgprint(
				f"Created {len(created)} Billet Cutting document(s) automatically.",
				indicator="green",
				alert=True,
			)


def _billet_cutting_exists(production_planning_name, fg_item, raw_material) -> bool:
	"""Check if a Billet Cutting doc already exists for this row combination."""
	return frappe.db.exists(
		"Billet Cutting",
		{
			"production_planning": production_planning_name,
			"finish_size": fg_item,
			"billet_size": raw_material,
		},
	)


def _create_billet_cutting_for_rows(production_planning_name, rows, shift_type, posting_date=None) -> None:
	"""Create Billet Cutting docs for rows that don't already have one."""
	created = []

	for row in rows or []:
		if not row.raw_material or not row.fg_item:
			continue

		if _billet_cutting_exists(production_planning_name, row.fg_item, row.raw_material):
			continue

		billet_doc = frappe.new_doc("Billet Cutting")
		billet_doc.production_planning = production_planning_name
		billet_doc.posting_date = posting_date or today()
		billet_doc.shift_type = shift_type
		billet_doc.billet_size = row.raw_material
		billet_doc.finish_size = row.fg_item
		billet_doc.billet_length_full = 0
		billet_doc.billet_pcs_full = 0
		billet_doc.billet_weight = 0
		billet_doc.total_billet_cutting_pcs = 0

		# Permission decision: caller permission is enforced at the whitelisted entry
		# point; these Billet Cutting rows are derived server-side from Production Planning.
		billet_doc.insert(ignore_permissions=True)
		created.append(billet_doc.name)

	return created


@frappe.whitelist()
def get_fg_items_for_production_planning(production_planning) -> dict | list:
	"""Return fg_item and raw_material rows from Production Planning FG Table."""
	require_permission("Production Planning", "read")
	rows = frappe.get_all(
		"Production Planning FG Table",
		filters={"parent": production_planning},
		fields=["fg_item", "raw_material"],
	)
	return rows


@frappe.whitelist()
def update_production_plan(source_name, items) -> None:
	"""Sync production_plan child table from the Update Items dialog."""
	require_all_permissions(
		[
			("Production Planning", "write"),
			("Billet Cutting", "create"),
		],
		_("Not permitted to update Production Planning."),
	)
	import json

	if isinstance(items, str):
		items = json.loads(items)
	if not items:
		items = []

	doc = frappe.get_doc("Production Planning", source_name)
	incoming_names = {item.get("name") for item in items if item.get("name")}

	# Block deletion of any row that already has a Billet Cutting doc
	for row in doc.production_plan:
		if row.name not in incoming_names:
			existing = _billet_cutting_exists(source_name, row.fg_item, row.raw_material)
			if existing:
				frappe.throw(
					_(
						"Cannot remove row for {0} — Billet Cutting {1} already exists for it. "
						"Cancel the Billet Cutting document first."
					).format(frappe.bold(row.fg_item), frappe.bold(existing)),
					title=_("Billet Cutting Exists"),
				)

	# Remove rows not in incoming list
	for row in list(doc.production_plan):
		if row.name not in incoming_names:
			doc.remove(row)

	existing_by_name = {row.name: row for row in doc.production_plan}

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
				"production_plan",
				{
					"fg_item": item.get("fg_item"),
					"default_bom": item.get("default_bom"),
					"fg_production_qty": item.get("fg_production_qty"),
					"raw_material": item.get("raw_material"),
					"rm_qty_required": item.get("rm_qty_required"),
				},
			)

	doc.flags.ignore_validate_update_after_submit = True
	# Permission decision: update_production_plan already enforces Production Planning
	# write + Billet Cutting create via require_all_permissions() above; this save
	# bypasses the update-after-submit interactive check, not the permission decision.
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	# Create Billet Cutting docs for any new rows (Rolled Plan only)
	if "Rolled Plan" in (doc.naming_series or ""):
		doc.reload()
		created = _create_billet_cutting_for_rows(source_name, doc.production_plan, doc.shift_type, doc.posting_date)
		if created:
			frappe.msgprint(
				f"Created {len(created)} new Billet Cutting document(s).",
				indicator="green",
				alert=True,
			)
