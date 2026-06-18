import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, today

from prakash_steel.utils.whitelist_permissions import require_all_permissions


class SORecommendationSnapshot(Document):
	def before_save(self):
		self.row_count = len(self.items)


# ---------------------------------------------------------------------------
# Core capture logic
# ---------------------------------------------------------------------------


def _capture_snapshot(trigger="Scheduled"):
	"""
	Run the Open SO Analysis report and save results as a snapshot.
	Returns the new snapshot document name.
	"""
	from prakash_steel.prakash_steel.report.open_so_analysis.open_so_analysis import execute

	filters = frappe._dict(
		from_date="2000-01-01",
		to_date=today(),
		line_fullkit_status=["Pending", "Partial", "Full-kit"],
	)

	try:
		result = execute(filters)
		# execute returns (columns, data, None, chart_data)
		_columns, data = result[0], result[1]
	except Exception:
		frappe.log_error(frappe.get_traceback(), "SO Snapshot Capture Failed")
		doc = frappe.new_doc("SO Recommendation Snapshot")
		doc.snapshot_date = today()
		doc.snapshot_time = now_datetime().strftime("%H:%M:%S")
		doc.trigger = trigger
		doc.status = "Failed"
		doc.row_count = 0
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return doc.name

	# Fetch payment_terms_template and custom_special_condition from Sales Order
	so_names = list({row.get("sales_order") for row in (data or []) if row.get("sales_order")})
	so_extra = {}
	if so_names:
		rows = frappe.db.sql(
			"""
			SELECT name, payment_terms_template, custom_special_condition
			FROM `tabSales Order`
			WHERE name IN %(so_names)s
			""",
			{"so_names": tuple(so_names)},
			as_dict=True,
		)
		so_extra = {r.name: r for r in rows}

	snap = frappe.new_doc("SO Recommendation Snapshot")
	snap.snapshot_date = today()
	snap.snapshot_time = now_datetime().strftime("%H:%M:%S")
	snap.trigger = trigger
	snap.status = "Success"

	for row in data or []:
		so_name = row.get("sales_order")
		extra = so_extra.get(so_name) or {}
		snap.append(
			"items",
			{
				"sales_order": so_name,
				"so_date": row.get("date"),
				"customer": row.get("customer"),
				"item_code": row.get("item_code"),
				"status": row.get("status") or "",
				"qty": row.get("qty") or 0,
				"rate": row.get("rate") or 0,
				"payment_terms_template": extra.get("payment_terms_template") or "",
				"lead_time": row.get("lead_time") or 0,
				"special_condition": extra.get("custom_special_condition") or "",
				"delivered_qty": row.get("delivered_qty") or 0,
				"delivery_date": row.get("delivery_date"),
				"pending_qty": row.get("pending_qty") or 0,
				"item_type": row.get("item_type") or "",
				"sku_type": row.get("sku_type") or "",
				"remaining_days": row.get("remaining_days") or 0,
				"buffer_status": row.get("buffer_status") or "",
				"order_status": row.get("order_status") or "",
				"stock": row.get("stock") or 0,
				"stock_allocation": row.get("stock_allocation") or 0,
				"shortage": row.get("shortage") or 0,
				"line_fullkit": row.get("line_fullkit") or "",
				"order_fullkit": row.get("order_fullkit") or "",
				"amount": row.get("amount") or 0,
				"pending_amount": row.get("pending_amount") or 0,
			},
		)

	snap.row_count = len(snap.items)
	snap.insert(ignore_permissions=True)
	frappe.db.commit()
	return snap.name


# ---------------------------------------------------------------------------
# Scheduled job — runs at 4:30 PM IST daily (wired in hooks.py)
# ---------------------------------------------------------------------------


def capture_daily_so_snapshot():
	"""Capture Open SO Analysis snapshot at 4:30 PM IST."""
	_capture_snapshot(trigger="Scheduled")


# ---------------------------------------------------------------------------
# Whitelisted API — manual trigger from UI
# ---------------------------------------------------------------------------


@frappe.whitelist()
def run_manual_snapshot():
	require_all_permissions(
		[("SO Recommendation Snapshot", "create"), ("SO Recommendation Snapshot", "write")],
	)
	name = _capture_snapshot(trigger="Manual")
	return name
