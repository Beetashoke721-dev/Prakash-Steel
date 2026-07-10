import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, today

from prakash_steel.utils.whitelist_permissions import require_all_permissions


class BrightMachineLoadSnapshot(Document):
	def before_save(self) -> None:
		self.row_count = len(self.items)


# ---------------------------------------------------------------------------
# Core capture logic
# ---------------------------------------------------------------------------


def _capture_snapshot(trigger="Scheduled") -> str:
	"""Run the Bright Machine Load report and save results as a snapshot."""
	from prakash_steel.prakash_steel.report.bright_machine_load.bright_machine_load import get_data

	try:
		data = get_data()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Bright Machine Load Snapshot Capture Failed")
		doc = frappe.new_doc("Bright Machine Load Snapshot")
		doc.snapshot_date = today()
		doc.snapshot_time = now_datetime().strftime("%H:%M:%S")
		doc.trigger = trigger
		doc.status = "Failed"
		doc.row_count = 0
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return doc.name

	snap = frappe.new_doc("Bright Machine Load Snapshot")
	snap.snapshot_date = today()
	snap.snapshot_time = now_datetime().strftime("%H:%M:%S")
	snap.trigger = trigger
	snap.status = "Success"

	for row in data or []:
		snap.append(
			"items",
			{
				"machine_name": row.get("machine_name") or "",
				"no_of_machines": row.get("no_of_machines") or 0,
				"net_prod_load": row.get("net_prod_load") or 0,
				"net_order_load": row.get("net_order_load") or 0,
			},
		)

	snap.row_count = len(snap.items)
	snap.insert(ignore_permissions=True)
	frappe.db.commit()
	return snap.name


# ---------------------------------------------------------------------------
# Scheduled job — runs at 4:30 AM IST daily (wired in hooks.py)
# ---------------------------------------------------------------------------


def capture_daily_snapshot() -> None:
	"""Capture Bright Machine Load snapshot at 4:30 AM IST."""
	_capture_snapshot(trigger="Scheduled")


# ---------------------------------------------------------------------------
# Whitelisted API — manual trigger from UI
# ---------------------------------------------------------------------------


@frappe.whitelist()
def run_manual_snapshot() -> str:
	require_all_permissions(
		[
			("Bright Machine Load Snapshot", "create"),
			("Bright Machine Load Snapshot", "write"),
		],
	)
	return _capture_snapshot(trigger="Manual")
