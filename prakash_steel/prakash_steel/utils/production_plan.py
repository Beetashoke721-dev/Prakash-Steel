import frappe
from frappe.utils import today


def on_production_plan_submit(doc, method) -> None:
	"""
	Server-side hook called when Production Plan is submitted.
	This will automatically create Billet Cutting documents for "Rolled Plan" Production Plans.
	"""
	result = create_billet_cutting_for_rolled_plan(doc.name)

	if result.get("created"):
		created_count = len(result.get("created", []))
		frappe.msgprint(
			f"✅ Created {created_count} Billet Cutting document(s) automatically.",
			indicator="green",
			alert=True,
		)


@frappe.whitelist()
def create_billet_cutting_for_rolled_plan(production_plan_name: str) -> dict:
	"""
	Create Billet Cutting documents automatically for a submitted Production Plan
	with naming_series containing 'Rolled Plan'.

	This is intended to be called from client-side JS after submit.
	"""
	if not production_plan_name:
		return {
			"created": [],
			"message": "No Production Plan provided",
		}

	if not frappe.has_permission("Production Plan", "read") or not frappe.has_permission(
		"Billet Cutting", "create"
	):
		frappe.throw("Not permitted to create Billet Cutting documents.", frappe.PermissionError)

	pp = frappe.get_doc("Production Plan", production_plan_name)

	naming_series = (pp.naming_series or "").strip()

	if "Rolled Plan" not in naming_series:
		return {
			"created": [],
			"message": "Naming Series is not a Rolled Plan. Skipped Billet Cutting creation.",
		}

	po_items = list(pp.get("po_items") or [])
	mr_items = list(pp.get("mr_items") or [])

	if not po_items or not mr_items:
		return {
			"created": [],
			"message": "No PO Items or MR Items found on Production Plan.",
		}

	# Cache: BOM -> child item codes (raw materials)
	bom_child_map = {}

	def get_bom_child_items(bom_name: str):
		if bom_name in bom_child_map:
			return bom_child_map[bom_name]
		try:
			bom_doc = frappe.get_doc("BOM", bom_name)
		except frappe.DoesNotExistError:
			bom_child_map[bom_name] = []
			return []

		child_codes = []
		for bi in bom_doc.get("items") or []:
			child_code = (bi.get("item_code") or "").strip()
			if child_code:
				child_codes.append(child_code)
		bom_child_map[bom_name] = child_codes
		return child_codes

	created_docs = []

	for mr_row in mr_items:
		raw_item_code = (mr_row.get("item_code") or "").strip()
		if not raw_item_code:
			continue

		for po in po_items:
			po_item_code = (po.get("item_code") or "").strip()
			bom_no = (po.get("bom_no") or "").strip()

			if not po_item_code or not bom_no:
				continue

			child_items = get_bom_child_items(bom_no)

			if raw_item_code in child_items:
				finished_item_code = po_item_code

				billet_doc = frappe.new_doc("Billet Cutting")
				billet_doc.production_plan = pp.name
				billet_doc.posting_date = today()
				billet_doc.billet_size = raw_item_code
				billet_doc.finish_size = finished_item_code
				billet_doc.billet_length_full = 0
				billet_doc.billet_pcs_full = 0
				billet_doc.billet_weight = 0
				billet_doc.total_billet_cutting_pcs = 0

				billet_doc.insert(ignore_permissions=True)

				created_docs.append(
					{
						"name": billet_doc.name,
						"billet_size": billet_doc.billet_size,
						"finish_size": billet_doc.finish_size,
						"po_row": getattr(po, "name", None),
						"mr_row": getattr(mr_row, "name", None),
						"bom_no": bom_no,
					}
				)

	if created_docs:
		message = f"Created {len(created_docs)} Billet Cutting document(s)."
	else:
		message = "No Billet Cutting documents were created."

	return {
		"created": created_docs,
		"message": message,
	}
