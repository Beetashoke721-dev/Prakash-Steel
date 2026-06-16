import frappe
from frappe.utils import today


def on_production_plan_submit(doc, method):
	"""
	Server-side hook called when Production Plan is submitted.
	This will automatically create Billet Cutting documents for "Rolled Plan" Production Plans.
	"""
	print("=" * 80)
	print("🔔 Production Plan on_submit hook triggered")
	print(f"📄 Production Plan: {doc.name}")
	print(f"🧾 Naming Series: {doc.naming_series}")
	print("=" * 80)

	# Call the creation function
	result = create_billet_cutting_for_rolled_plan(doc.name)

	# Show message to user
	if result.get("created"):
		created_count = len(result.get("created", []))
		message = f"✅ Created {created_count} Billet Cutting document(s) automatically."
		frappe.msgprint(
			message,
			indicator="green",
			alert=True,
		)
		print(f"✅ User notified: {message}")
	else:
		msg = result.get("message", "No Billet Cutting documents were created.")
		print(f"ℹ️ {msg}")


@frappe.whitelist()
def create_billet_cutting_for_rolled_plan(production_plan_name: str):
	"""
	Create Billet Cutting documents automatically for a submitted Production Plan
	with naming_series containing 'Rolled Plan'.

	This is intended to be called from client-side JS after submit.
	"""
	print("=" * 80)
	print("create_billet_cutting_for_rolled_plan called")
	print(f"Production Plan: {production_plan_name}")
	print("=" * 80)

	if not production_plan_name:
		print("❌ No production_plan_name passed")
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
	print(f"Naming Series: {naming_series}")

	if "Rolled Plan" not in naming_series:
		print("❌ Naming series does not contain 'Rolled Plan', skipping creation")
		return {
			"created": [],
			"message": "Naming Series is not a Rolled Plan. Skipped Billet Cutting creation.",
		}

	po_items = list(pp.get("po_items") or [])
	mr_items = list(pp.get("mr_items") or [])

	print(f"PO Items (finished items) count: {len(po_items)}")
	print(f"MR Items (raw billets) count: {len(mr_items)}")

	if not po_items or not mr_items:
		print("❌ Either po_items or mr_items is empty. Nothing to process.")
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
			print(f"❌ BOM {bom_name} not found.")
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

	# We treat MR items as billets (raw material) and PO items as finished sizes
	for mr_row in mr_items:
		raw_item_code = (mr_row.get("item_code") or "").strip()
		if not raw_item_code:
			continue

		print("-" * 60)
		print(f"Processing MR Item row: {getattr(mr_row, 'name', '')}")
		print(f"Raw billet item_code (from MR): {raw_item_code}")

		# Find ALL PO rows whose BOM uses this raw item as a child.
		# For each such PO row, we will create one Billet Cutting document.
		matched_any_po = False

		for po in po_items:
			po_item_code = (po.get("item_code") or "").strip()
			bom_no = (po.get("bom_no") or "").strip()

			if not po_item_code or not bom_no:
				continue

			child_items = get_bom_child_items(bom_no)
			print(f"Checking PO row {getattr(po, 'name', '')} | item={po_item_code} | bom={bom_no}")
			print(f"  BOM child items: {child_items}")

			if raw_item_code in child_items:
				matched_any_po = True

				finished_item_code = po_item_code

				print(f"✅ Matched PO row: {getattr(po, 'name', '')}")
				print(f"Finished Size (from PO item): {finished_item_code}")
				print(f"BOM used for match: {bom_no}")

				# Prepare Billet Cutting document
				billet_doc = frappe.new_doc("Billet Cutting")
				billet_doc.production_plan = pp.name
				billet_doc.posting_date = today()

				# Billet Size from MR item (raw material)
				billet_doc.billet_size = raw_item_code

				# Finish Size from PO item (finished good)
				billet_doc.finish_size = finished_item_code

				# Default mandatory numeric fields to 0 to avoid validation errors
				# User can later update real values on the Billet Cutting form.
				billet_doc.billet_length_full = 0
				billet_doc.billet_pcs_full = 0
				billet_doc.billet_weight = 0
				billet_doc.total_billet_cutting_pcs = 0

				print("Inserting Billet Cutting document ...")
				billet_doc.insert(ignore_permissions=True)
				print(f"✅ Billet Cutting created: {billet_doc.name}")

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

		if not matched_any_po:
			print("⚠️ No PO row/BOM found that consumes this raw billet item. Skipping this MR row.")

	print("=" * 80)
	print(f"Total Billet Cutting docs created: {len(created_docs)}")
	for d in created_docs:
		print(
			f"  - {d['name']} | billet_size={d['billet_size']} | "
			f"finish_size={d['finish_size']} | po_row={d['po_row']} | "
			f"mr_row={d['mr_row']} | bom={d['bom_no']}"
		)
	print("=" * 80)

	if created_docs:
		message = f"Created {len(created_docs)} Billet Cutting document(s)."
	else:
		message = "No Billet Cutting documents were created."

	return {
		"created": created_docs,
		"message": message,
	}
