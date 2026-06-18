import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, today

from prakash_steel.utils.whitelist_permissions import require_all_permissions


class PORecommendationSnapshot(Document):
	def before_save(self):
		self.item_count = len(self.items)


# ---------------------------------------------------------------------------
# Core capture logic
# ---------------------------------------------------------------------------

def _capture_snapshot(purchase=1, sell=0, buffer_flag=1, sku_type_filter=None, item_code_filter=None, trigger="Scheduled"):
	"""
	Run the PO Recommendation for PSP report and save results as a snapshot.
	Returns the new snapshot document name.
	"""
	from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import execute

	filters = frappe._dict(
		purchase=purchase,
		sell=sell,
		buffer_flag=buffer_flag,
	)
	if sku_type_filter:
		filters.sku_type = sku_type_filter
	if item_code_filter:
		filters.item_code = item_code_filter

	try:
		_columns, data = execute(filters)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "PO Snapshot Capture Failed")
		doc = frappe.new_doc("PO Recommendation Snapshot")
		doc.snapshot_date = today()
		doc.snapshot_time = now_datetime().strftime("%H:%M:%S")
		doc.trigger = trigger
		doc.status = "Failed"
		doc.purchase = purchase
		doc.sell = sell
		doc.buffer_flag = buffer_flag
		doc.sku_type_filter = sku_type_filter or ""
		doc.item_code_filter = item_code_filter or ""
		doc.item_count = 0
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return doc.name

	snap = frappe.new_doc("PO Recommendation Snapshot")
	snap.snapshot_date = today()
	snap.snapshot_time = now_datetime().strftime("%H:%M:%S")
	snap.trigger = trigger
	snap.status = "Success"
	snap.purchase = purchase
	snap.sell = sell
	snap.buffer_flag = buffer_flag
	snap.sku_type_filter = sku_type_filter or ""
	snap.item_code_filter = item_code_filter or ""

	for row in (data or []):
		snap.append("items", {
			"item_code": row.get("item_code"),
			"sku_type": row.get("sku_type"),
			"requirement": row.get("requirement") or 0,
			"tog": row.get("tog") or 0,
			"toy": row.get("toy") or 0,
			"tor": row.get("tor") or 0,
			"open_so": row.get("open_so") or 0,
			"total_so": row.get("total_so") or 0,
			"open_so_qualified": row.get("open_so_qualified") or 0,
			"on_hand_stock": row.get("on_hand_stock") or 0,
			"wip": row.get("wip") or 0,
			"open_po": row.get("open_po") or 0,
			"open_subcon_po": row.get("open_subcon_po") or 0,
			"additional_demand": row.get("additional_demand") or 0,
			"qualified_demand": row.get("qualify_demand") or 0,
			"on_hand_status": row.get("on_hand_status") or "",
			"on_hand_colour": row.get("on_hand_colour") or "",
			"net_flow": row.get("net_flow") or 0,
			"order_recommendation": row.get("order_recommendation") or 0,
			"mrq": row.get("mrq") or 0,
			"balance_order_recommendation": row.get("net_po_recommendation") or 0,
			"net_order_recommendation": row.get("or_with_moq_batch_size") or 0,
			"moq": row.get("moq") or 0,
			"batch_size": row.get("batch_size") or 0,
			"production_qty_based_on_child_stock": row.get("production_qty_based_on_child_stock") or 0,
			"child_full_kit_status": row.get("child_full_kit_status") or "",
			"production_qty_based_on_child_stock_wip_open_po": row.get("production_qty_based_on_child_stock_wip_open_po") or 0,
			"child_wip_open_po_full_kit_status": row.get("child_wip_open_po_full_kit_status") or "",
			"child_item_code": row.get("child_item_code"),
			"child_item_type": row.get("child_item_type") or "",
			"child_sku_type": row.get("child_sku_type") or "",
			"child_requirement": row.get("child_requirement") or 0,
			"child_stock": row.get("child_stock") or 0,
			"child_stock_soft_allocation_qty": row.get("child_stock_soft_allocation_qty") or 0,
			"child_stock_shortage": row.get("child_stock_shortage") or 0,
			"child_wip_open_po": row.get("child_wip_open_po") or 0,
			"child_wip_open_po_soft_allocation_qty": row.get("child_wip_open_po_soft_allocation_qty") or 0,
			"child_wip_open_po_shortage": row.get("child_wip_open_po_shortage") or 0,
		})

	snap.item_count = len(snap.items)
	snap.insert(ignore_permissions=True)
	frappe.db.commit()
	return snap.name


# ---------------------------------------------------------------------------
# Scheduled job — runs at 8 AM daily (wired in hooks.py)
# ---------------------------------------------------------------------------

def capture_daily_po_snapshot():
	"""Capture all 4 PO recommendation snapshots at 8 AM."""
	_capture_snapshot(purchase=1, sell=0, buffer_flag=1, trigger="Scheduled")
	_capture_snapshot(purchase=1, sell=0, buffer_flag=0, trigger="Scheduled")
	_capture_snapshot(purchase=0, sell=1, buffer_flag=1, trigger="Scheduled")
	_capture_snapshot(purchase=0, sell=1, buffer_flag=0, trigger="Scheduled")


# ---------------------------------------------------------------------------
# Whitelisted API — manual trigger from UI
# ---------------------------------------------------------------------------

@frappe.whitelist()
def run_manual_snapshot(purchase=1, sell=0, buffer_flag=1, sku_type_filter=None, item_code_filter=None):
	require_all_permissions(
		[("PO Recommendation Snapshot", "create"), ("PO Recommendation Snapshot", "write")],
	)
	name = _capture_snapshot(
		purchase=int(purchase),
		sell=int(sell),
		buffer_flag=int(buffer_flag),
		sku_type_filter=sku_type_filter,
		item_code_filter=item_code_filter,
		trigger="Manual",
	)
	return name
