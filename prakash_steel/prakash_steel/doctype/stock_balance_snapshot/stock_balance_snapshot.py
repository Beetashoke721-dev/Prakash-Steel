import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, today

from prakash_steel.utils.whitelist_permissions import require_all_permissions


class StockBalanceSnapshot(Document):
	def before_save(self) -> None:
		self.row_count = len(self.items)


def _capture_snapshot(trigger="Scheduled", filters=None) -> None:
	"""
	Run the Item Wise Stock Balance report and save results as a snapshot.
	Always sets include_zero_stock so every active item appears (zero balance included).
	Returns the new snapshot document name.
	"""
	from prakash_steel.prakash_steel.report.item_wise_stock_balance.item_wise_stock_balance import execute

	filters = frappe._dict(filters or {})
	# Match report behaviour with "Include Zero Stock Items" checked — all active items
	filters["include_zero_stock"] = 1

	try:
		_columns, data = execute(filters)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Stock Balance Snapshot Capture Failed")
		doc = frappe.new_doc("Stock Balance Snapshot")
		doc.snapshot_date = today()
		doc.snapshot_time = now_datetime().strftime("%H:%M:%S")
		doc.trigger = trigger
		doc.status = "Failed"
		doc.row_count = 0
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return doc.name

	snap = frappe.new_doc("Stock Balance Snapshot")
	snap.snapshot_date = today()
	snap.snapshot_time = now_datetime().strftime("%H:%M:%S")
	snap.trigger = trigger
	snap.status = "Success"

	for row in data or []:
		snap.append(
			"items",
			{
				"item_code": row.get("item_code"),
				"item_name": row.get("item_name") or "",
				"item_group": row.get("item_group") or "",
				"category_name": row.get("category_name") or "",
				"stock_uom": row.get("stock_uom") or "",
				"balance_qty": float(row.get("balance_qty") or 0),
			},
		)

	snap.row_count = len(snap.items)
	# Permission decision: snapshots are system-generated. Scheduled capture has no
	# user; the manual trigger (run_manual_snapshot) already enforces create+write
	# via require_all_permissions(). Data is computed server-side, not user-supplied.
	snap.insert(ignore_permissions=True)
	frappe.db.commit()
	return snap.name


def capture_daily_stock_balance_snapshot() -> None:
	"""Capture Item Wise Stock Balance snapshot on schedule (see hooks.py cron)."""
	_capture_snapshot(trigger="Scheduled")


@frappe.whitelist()
def run_manual_snapshot() -> None:
	require_all_permissions(
		[("Stock Balance Snapshot", "create"), ("Stock Balance Snapshot", "write")],
	)
	return _capture_snapshot(trigger="Manual")
