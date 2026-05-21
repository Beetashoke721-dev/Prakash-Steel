import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_dashboard_data(from_date=None, to_date=None, item_code=None, sku_type=None):
	"""Return aggregated data for the PO History Dashboard."""
	filters = {"status": "Success"}
	if from_date and to_date:
		filters["snapshot_date"] = ["between", [from_date, to_date]]
	elif from_date:
		filters["snapshot_date"] = [">=", from_date]
	elif to_date:
		filters["snapshot_date"] = ["<=", to_date]

	snapshots = frappe.get_all(
		"PO Recommendation Snapshot",
		filters=filters,
		fields=["name", "snapshot_date", "trigger"],
		order_by="snapshot_date asc",
	)

	if not snapshots:
		return {"snapshots": [], "colour_heatmap": [], "top_order_items": [], "trend_data": {}}

	snap_names = [s.name for s in snapshots]
	snap_dates = {s.name: str(s.snapshot_date) for s in snapshots}

	item_filters = {"parent": ["in", snap_names]}
	if item_code:
		item_filters["item_code"] = item_code
	if sku_type:
		item_filters["sku_type"] = sku_type

	rows = frappe.get_all(
		"PO Recommendation Snapshot Item",
		filters=item_filters,
		fields=[
			"parent", "item_code", "sku_type",
			"on_hand_stock", "open_po", "net_order_recommendation",
			"on_hand_colour", "qualified_demand", "wip", "tog",
		],
	)

	# ---- Colour heatmap: item → date → colour ----
	colour_map = {}
	for r in rows:
		colour_map.setdefault(r.item_code, {})[snap_dates[r.parent]] = r.on_hand_colour or "WHITE"

	colour_heatmap = [
		{"item_code": item, "dates": dates}
		for item, dates in colour_map.items()
	]

	# ---- Top items by max net_order_recommendation ----
	item_max = {}
	for r in rows:
		val = flt(r.net_order_recommendation)
		if val > item_max.get(r.item_code, 0):
			item_max[r.item_code] = val

	top_order_items = sorted(
		[{"item_code": k, "max_net_order": v} for k, v in item_max.items()],
		key=lambda x: x["max_net_order"],
		reverse=True,
	)[:20]

	# ---- Trend data for charting (per snapshot date, avg stock / avg order rec) ----
	date_agg = {}
	for r in rows:
		d = snap_dates[r.parent]
		if d not in date_agg:
			date_agg[d] = {"stock": [], "order_rec": [], "open_po": []}
		date_agg[d]["stock"].append(flt(r.on_hand_stock))
		date_agg[d]["order_rec"].append(flt(r.net_order_recommendation))
		date_agg[d]["open_po"].append(flt(r.open_po))

	trend_data = {
		"dates": sorted(date_agg.keys()),
		"avg_stock": [round(sum(date_agg[d]["stock"]) / len(date_agg[d]["stock"]), 2) for d in sorted(date_agg)],
		"avg_order_rec": [round(sum(date_agg[d]["order_rec"]) / len(date_agg[d]["order_rec"]), 2) for d in sorted(date_agg)],
		"avg_open_po": [round(sum(date_agg[d]["open_po"]) / len(date_agg[d]["open_po"]), 2) for d in sorted(date_agg)],
	}

	# ---- Colour distribution for latest snapshot ----
	latest_snap = snap_names[-1]
	latest_rows = [r for r in rows if r.parent == latest_snap]
	colour_dist = {}
	for r in latest_rows:
		c = r.on_hand_colour or "WHITE"
		colour_dist[c] = colour_dist.get(c, 0) + 1

	return {
		"snapshots": [{"name": s.name, "date": str(s.snapshot_date), "trigger": s.trigger} for s in snapshots],
		"colour_heatmap": colour_heatmap,
		"top_order_items": top_order_items,
		"trend_data": trend_data,
		"colour_distribution": colour_dist,
		"latest_snapshot": latest_snap,
	}
