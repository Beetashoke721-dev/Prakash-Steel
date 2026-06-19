import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, today

from prakash_steel.utils.whitelist_permissions import require_all_permissions


class PurchaseOrderRecommendationSnapshot(Document):
	def before_save(self) -> None:
		self.row_count = len(self.items)


# ---------------------------------------------------------------------------
# Core capture logic
# ---------------------------------------------------------------------------

def _capture_snapshot(trigger="Scheduled") -> None:
	"""
	Run the Open PO Analysis report and save results as a snapshot.
	Returns the new snapshot document name.
	"""
	from prakash_steel.prakash_steel.report.open_po_analysis.open_po_analysis import execute

	filters = frappe._dict(
		from_date="2000-01-01",
		to_date=today(),
	)

	try:
		result = execute(filters)
		_columns, data = result[0], result[1]
	except Exception:
		frappe.log_error(frappe.get_traceback(), "PO Rec Snapshot Capture Failed")
		doc = frappe.new_doc("Purchase Order Recommendation Snapshot")
		doc.snapshot_date = today()
		doc.snapshot_time = now_datetime().strftime("%H:%M:%S")
		doc.trigger = trigger
		doc.status = "Failed"
		doc.row_count = 0
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return doc.name

	snap = frappe.new_doc("Purchase Order Recommendation Snapshot")
	snap.snapshot_date = today()
	snap.snapshot_time = now_datetime().strftime("%H:%M:%S")
	snap.trigger = trigger
	snap.status = "Success"

	for row in (data or []):
		snap.append("items", {
			"purchase_order": row.get("purchase_order"),
			"po_date": row.get("date"),
			"required_date": row.get("required_date"),
			"status": row.get("status") or "",
			"supplier": row.get("supplier"),
			"project": row.get("project"),
			"item_code": row.get("item_code"),
			"category_name": row.get("category_name") or "",
			"rate": row.get("rate") or 0,
			"cf_lead_time": row.get("cf_lead_time") or 0,
			"warehouse": row.get("warehouse"),
			"company": row.get("company"),
			"qty": row.get("qty") or 0,
			"received_qty": row.get("received_qty") or 0,
			"pending_qty": row.get("pending_qty") or 0,
			"billed_qty": row.get("billed_qty") or 0,
			"qty_to_bill": row.get("qty_to_bill") or 0,
			"amount": row.get("amount") or 0,
			"billed_amount": row.get("billed_amount") or 0,
			"pending_amount": row.get("pending_amount") or 0,
			"received_qty_amount": row.get("received_qty_amount") or 0,
		})

	snap.row_count = len(snap.items)
	snap.insert(ignore_permissions=True)
	frappe.db.commit()
	return snap.name


# ---------------------------------------------------------------------------
# Scheduled job — runs daily at 4:00 PM IST (wired in hooks.py)
# ---------------------------------------------------------------------------

def capture_daily_po_rec_snapshot() -> None:
	"""Capture Open PO Analysis snapshot at 4:00 PM IST."""
	_capture_snapshot(trigger="Scheduled")


# ---------------------------------------------------------------------------
# Whitelisted API — manual trigger from UI
# ---------------------------------------------------------------------------

@frappe.whitelist()
def run_manual_snapshot() -> None:
	require_all_permissions(
		[
			("Purchase Order Recommendation Snapshot", "create"),
			("Purchase Order Recommendation Snapshot", "write"),
		],
	)
	name = _capture_snapshot(trigger="Manual")
	return name
