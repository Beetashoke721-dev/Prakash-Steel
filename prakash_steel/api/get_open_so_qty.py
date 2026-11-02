import frappe
from frappe.utils import flt

from prakash_steel.utils.whitelist_permissions import require_permission


@frappe.whitelist()
def get_open_so_qty(item_code, company=None) -> float:
	"""
	Total "Qty to Deliver" for an item, as shown on the Open SO page.

	Runs the Open SO Analysis report with the page's default filters
	(company, no date range, all Line Full Kit statuses) and sums pending_qty.
	"""
	require_permission("Sales Order", "read")

	if not item_code:
		return 0

	from prakash_steel.prakash_steel.report.open_so_analysis.open_so_analysis import execute

	filters = frappe._dict(
		{
			"item_code": item_code,
			"line_fullkit_status": ["Partial", "Full-kit", "Pending"],
		}
	)
	if company:
		filters.company = company

	data = execute(filters)[1] or []
	return sum(flt(row.get("pending_qty")) for row in data)
