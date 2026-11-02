import math

from frappe.utils import date_diff, flt, nowdate


_STATUS_PRIORITY = {"BLACK": 5, "RED": 4, "YELLOW": 3, "GREEN": 2, "WHITE": 1}
_PRIORITY_TO_COLOUR = {5: "BLACK", 4: "RED", 3: "YELLOW", 2: "GREEN", 1: "WHITE"}


def calculate_sku_type(buffer_flag: str, item_type: str | None) -> str | None:
	if not item_type:
		return None

	is_buffer = buffer_flag == "Buffer"

	if item_type == "BB":
		return "BBMTA" if is_buffer else "BBMTO"
	elif item_type == "RB":
		return "RBMTA" if is_buffer else "RBMTO"
	elif item_type == "BO":
		return "BOTA" if is_buffer else "BOTO"
	elif item_type == "RM":
		return "PTA" if is_buffer else "PTO"
	elif item_type == "Traded":
		return "TRMTA" if is_buffer else "TRMTO"

	return None


def _compute_order_status(delivery_date: str | None, transaction_date: str | None) -> str | None:
	if not delivery_date:
		return None
	today = nowdate()
	remaining_days = date_diff(delivery_date, today)
	lead_time = date_diff(delivery_date, transaction_date) if transaction_date else None
	if lead_time:
		buffer_pct = (flt(remaining_days) / flt(lead_time)) * 100
	else:
		buffer_pct = flt(remaining_days) * 100
	numeric = math.ceil(buffer_pct)
	if numeric < 0:
		return "BLACK"
	elif numeric <= 34:
		return "RED"
	elif numeric <= 67:
		return "YELLOW"
	elif numeric <= 100:
		return "GREEN"
	else:
		return "WHITE"


def _non_buffer_priority(item_code: str, level: float, so_map: dict) -> str:
	sos = so_map.get(item_code, [])
	if not sos:
		return ""
	available = flt(level)
	worst_shortage = 0
	worst_no_shortage = 0
	for so in sos:
		required = flt(so["pending_qty"])
		allocated = min(required, available)
		shortage = required - allocated
		available -= allocated
		priority = _STATUS_PRIORITY.get(so["order_status"], 0)
		if shortage > 0:
			if priority > worst_shortage:
				worst_shortage = priority
		else:
			if priority > worst_no_shortage:
				worst_no_shortage = priority
	if worst_shortage > 0:
		return _PRIORITY_TO_COLOUR.get(worst_shortage, "")
	if worst_no_shortage > 0:
		return _PRIORITY_TO_COLOUR.get(worst_no_shortage, "")
	return ""


def buffer_order_recommendation_colour(level: float, total: float) -> str:
	level = flt(level)
	total = flt(total)
	if level == 0:
		return "Black"
	if total <= 0:
		return ""
	if level <= total / 3:
		return "Red"
	if level <= (2 * total) / 3:
		return "Yellow"
	if level <= total:
		return "Green"
	return "White"


def calculate_net_order_recommendation(base_order_rec: float, moq: float, batch_size: float) -> float:
	base_order_rec = flt(base_order_rec)
	moq = flt(moq)
	batch_size = flt(batch_size)

	if base_order_rec < 1:
		return 0

	if moq > 0:
		if moq < base_order_rec:
			net_order_rec = base_order_rec
		else:
			net_order_rec = moq
	elif batch_size > 0:
		net_order_rec = math.ceil(base_order_rec / batch_size) * batch_size
	else:
		net_order_rec = base_order_rec

	return max(0, flt(net_order_rec))


def calculate_initial_order_recommendation(
	item_code: str,
	item_buffer_map: dict[str, str],
	item_tog_map: dict[str, float],
	item_sku_type_map: dict[str, str],
	stock_map: dict[str, float],
	wip_map: dict[str, float],
	open_so_map: dict[str, float],
	qualified_demand_map: dict[str, float],
	open_po_map: dict[str, float],
	open_subcon_po_map: dict[str, float] | None = None,
) -> float:
	buffer_flag = item_buffer_map.get(item_code, "Non-Buffer")
	is_buffer = buffer_flag == "Buffer"

	stock = flt(stock_map.get(item_code, 0))
	wip = flt(wip_map.get(item_code, 0))
	open_subcon_po = flt((open_subcon_po_map or {}).get(item_code, 0))

	if is_buffer:
		tog = flt(item_tog_map.get(item_code, 0))
		qualified_demand = flt(qualified_demand_map.get(item_code, 0))
		sku_type = item_sku_type_map.get(item_code)
		open_po = flt(open_po_map.get(item_code, 0))

		if sku_type in ["BOTA", "PTA"]:
			order_rec = max(0, tog + qualified_demand - stock - wip - open_po - open_subcon_po)
		else:
			order_rec = max(0, tog + qualified_demand - stock - wip - open_po - open_subcon_po)
	else:
		qualified_demand = flt(open_so_map.get(item_code, 0))
		sku_type = item_sku_type_map.get(item_code)
		open_po = flt(open_po_map.get(item_code, 0))

		if sku_type in ["PTO", "BOTO", "TRMTO"]:
			order_rec = max(0, qualified_demand - stock - wip - open_po - open_subcon_po)
		else:
			order_rec = max(0, qualified_demand - stock - wip - open_po - open_subcon_po)

	return order_rec


def calculate_final_order_recommendation(
	item_code: str,
	item_buffer_map: dict[str, str],
	item_tog_map: dict[str, float],
	item_sku_type_map: dict[str, str],
	stock_map: dict[str, float],
	wip_map: dict[str, float],
	open_so_map: dict[str, float],
	qualified_demand_map: dict[str, float],
	open_po_map: dict[str, float],
	mrq_map: dict[str, float],
	parent_demand_map: dict[str, float],
	item_type_map: dict[str, str] | None = None,
	spike_master_map: dict[str, dict] | None = None,
	open_subcon_po_map: dict[str, float] | None = None,
) -> float:
	buffer_flag = item_buffer_map.get(item_code, "Non-Buffer")
	is_buffer = buffer_flag == "Buffer"

	stock = flt(stock_map.get(item_code, 0))
	wip = flt(wip_map.get(item_code, 0))
	mrq = flt(mrq_map.get(item_code, 0))
	open_subcon_po = flt((open_subcon_po_map or {}).get(item_code, 0))

	if is_buffer:
		tog = flt(item_tog_map.get(item_code, 0))
		total_demand = calculate_total_demand(
			item_code,
			True,
			qualified_demand_map,
			parent_demand_map,
			item_tog_map,
			item_type_map,
			spike_master_map,
		)
		sku_type = item_sku_type_map.get(item_code)
		open_po = flt(open_po_map.get(item_code, 0))

		if sku_type in ["BOTA", "PTA"]:
			base_order_rec = tog + total_demand - stock - wip - open_po - open_subcon_po
		else:
			base_order_rec = tog + total_demand - stock - wip - open_po - open_subcon_po

		order_rec = max(0, base_order_rec - mrq)
	else:
		open_so = flt(open_so_map.get(item_code, 0))
		parent_demand = flt(parent_demand_map.get(item_code, 0))
		requirement = open_so + parent_demand
		sku_type = item_sku_type_map.get(item_code)
		open_po = flt(open_po_map.get(item_code, 0))

		if sku_type in ["PTO", "BOTO", "TRMTO"]:
			base_order_rec = requirement - stock - wip - open_po - open_subcon_po
		else:
			base_order_rec = requirement - stock - wip - open_po - open_subcon_po

		order_rec = max(0, base_order_rec - mrq)

	return order_rec


def get_qualified_demand_for_item(
	item_code: str,
	till_today_map: dict[str, float],
	spike_map: dict[str, float],
	item_buffer_map: dict[str, str],
) -> tuple[float, float, float]:
	till_today = flt(till_today_map.get(item_code, 0))

	buffer_flag = item_buffer_map.get(item_code, "Non-Buffer")
	if buffer_flag != "Buffer":
		spike = 0.0
	else:
		spike = flt(spike_map.get(item_code, 0))

	qualified_demand = till_today + spike
	return qualified_demand, till_today, spike


def apply_spike_threshold(
	total_demand: float,
	tog: float,
	item_type: str | None,
	spike_master_map: dict[str, dict] | None,
) -> float:
	if not spike_master_map or not item_type or tog <= 0:
		return total_demand

	spike_config = spike_master_map.get(item_type)
	if not spike_config:
		return total_demand

	spike_threshold_pct = flt(spike_config.get("spike_threshold", 0))
	spike_threshold_qty = tog * spike_threshold_pct / 100

	if spike_threshold_qty > 0 and total_demand < spike_threshold_qty:
		return 0.0

	return total_demand


def calculate_total_demand(
	item_code: str,
	is_buffer: bool,
	qualified_demand_map: dict[str, float],
	parent_demand_map: dict[str, float],
	item_tog_map: dict[str, float] | None = None,
	item_type_map: dict[str, str] | None = None,
	spike_master_map: dict[str, dict] | None = None,
) -> float:
	qualified_demand = flt(qualified_demand_map.get(item_code, 0))
	parent_demand = flt(parent_demand_map.get(item_code, 0))
	total_demand = qualified_demand + parent_demand

	if is_buffer:
		tog = flt((item_tog_map or {}).get(item_code, 0))
		item_type = (item_type_map or {}).get(item_code)
		total_demand = apply_spike_threshold(total_demand, tog, item_type, spike_master_map)

	return total_demand


def build_calculation_breakdown_po_report(
	item_code: str,
	buffer_flag: str,
	is_buffer: bool,
	sku_type: str | None,
	tog: float,
	qualified_demand: float,
	open_so: float,
	stock: float,
	wip: float,
	open_po: float,
	mrq: float,
	moq: float,
	batch_size: float,
	total_parent_demand: float,
	final_order_rec: float,
	net_order_rec: float,
	parent_demand_details_list: list[dict],
	till_today: float | None = None,
	spike: float | None = None,
	open_subcon_po: float = 0,
) -> str:
	lines = []
	lines.append(f"\n  Item: {item_code}")
	lines.append(f"  Type: {buffer_flag}")
	if sku_type and sku_type != "N/A":
		lines.append(f"  SKU Type: {sku_type}")

	if is_buffer:
		lines.append(f"  TOG: {tog}")
		if till_today is not None and spike is not None:
			lines.append(f"  Till Today: {till_today}")
			lines.append(f"  Spike: {spike}")
			lines.append(f"  Qualified Demand (Till Today + Spike): {qualified_demand}")
		else:
			lines.append(f"  Qualified Demand: {qualified_demand}")
		lines.append(f"  Total Parent Demand: {total_parent_demand}")

		if total_parent_demand > 0 and parent_demand_details_list:
			lines.append("  Parent Demands Breakdown:")
			for pd in parent_demand_details_list:
				if pd.get("applied", True):
					lines.append(
						f"    - From {pd['parent_item']} (BOM: {pd['bom_name']}): {pd['demand_qty']} {pd.get('reason', '')}"
					)
				else:
					lines.append(
						f"    - From {pd['parent_item']} (BOM: {pd['bom_name']}): {pd['demand_qty']} [IGNORED - {pd.get('reason', '')}]"
					)

		total_demand = qualified_demand + total_parent_demand
		lines.append(
			f"  Total Demand (Qualified Demand + Parent Demand): {qualified_demand} + {total_parent_demand} = {total_demand}"
		)
		lines.append(f"  Stock: {stock}")
		lines.append(f"  WIP: {wip}")
		lines.append(f"  Open PO: {open_po}")
		lines.append(f"  Open Subcon PO: {open_subcon_po}")
		lines.append(f"  MRQ: {mrq}")

		if sku_type in ["BOTA", "PTA"]:
			base_calc = tog + total_demand - stock - wip - open_po - open_subcon_po
			lines.append(
				"  Base Calculation: TOG + (Qualified Demand + Parent Demand) - Stock - WIP - Open PO - Open Subcon PO"
			)
			lines.append(
				f"                    = {tog} + ({qualified_demand} + {total_parent_demand}) - {stock} - {wip} - {open_po} - {open_subcon_po}"
			)
			lines.append(
				f"                    = {tog} + {total_demand} - {stock} - {wip} - {open_po} - {open_subcon_po}"
			)
			lines.append(f"                    = {base_calc}")
			lines.append(f"  After MRQ: Base - MRQ = {base_calc} - {mrq} = {final_order_rec}")
		else:
			base_calc = tog + total_demand - stock - wip - open_po - open_subcon_po
			lines.append(
				"  Base Calculation: TOG + (Qualified Demand + Parent Demand) - Stock - WIP - Open PO - Open Subcon PO"
			)
			lines.append(
				f"                    = {tog} + ({qualified_demand} + {total_parent_demand}) - {stock} - {wip} - {open_po} - {open_subcon_po}"
			)
			lines.append(
				f"                    = {tog} + {total_demand} - {stock} - {wip} - {open_po} - {open_subcon_po}"
			)
			lines.append(f"                    = {base_calc}")
			lines.append(f"  After MRQ: Base - MRQ = {base_calc} - {mrq} = {final_order_rec}")

		if final_order_rec <= 0:
			if moq > 0:
				lines.append(f"  MOQ: {moq} (Not applied - base order rec is {final_order_rec} <= 0)")
			elif batch_size > 0:
				lines.append(
					f"  Batch Size: {batch_size} (Not applied - base order rec is {final_order_rec} <= 0)"
				)
			else:
				lines.append("  No MOQ or Batch Size")
			lines.append(f"  Net Order Recommendation: 0 (Base order rec is {final_order_rec} <= 0)")
		elif moq > 0:
			if moq < final_order_rec:
				lines.append(f"  MOQ: {moq} (MOQ < Order Rec, using Order Rec)")
				lines.append(f"  Net Order Recommendation: {final_order_rec}")
			else:
				lines.append(f"  MOQ: {moq} (MOQ >= Order Rec, using MOQ)")
				lines.append(f"  Net Order Recommendation: {moq}")
		elif batch_size > 0:
			net_calc = math.ceil(final_order_rec / batch_size) * batch_size
			lines.append(f"  Batch Size: {batch_size}")
			lines.append(
				f"  Net Order Recommendation: ceil({final_order_rec} / {batch_size}) x {batch_size} = {net_calc}"
			)
		else:
			lines.append("  No MOQ or Batch Size")
			lines.append(f"  Net Order Recommendation: {final_order_rec}")
	else:
		open_so_for_breakdown = qualified_demand
		lines.append(f"  Open SO: {open_so_for_breakdown}")
		if till_today is not None and spike is not None:
			lines.append(f"    - Till Today: {till_today}")
			lines.append(f"    - Spike: {spike} (always 0 for non-buffer items)")
		lines.append(f"  Stock: {stock}")
		lines.append(f"  WIP: {wip}")
		lines.append(f"  Open PO: {open_po}")
		lines.append(f"  Open Subcon PO: {open_subcon_po}")
		lines.append(f"  Total Parent Demand: {total_parent_demand}")

		if total_parent_demand > 0 and parent_demand_details_list:
			lines.append("  Parent Demands Breakdown:")
			for pd in parent_demand_details_list:
				if pd.get("applied", True):
					lines.append(
						f"    - From {pd['parent_item']} (BOM: {pd['bom_name']}): {pd['demand_qty']} {pd.get('reason', '')}"
					)
				else:
					lines.append(
						f"    - From {pd['parent_item']} (BOM: {pd['bom_name']}): {pd['demand_qty']} [IGNORED - {pd.get('reason', '')}]"
					)

		requirement = open_so_for_breakdown + total_parent_demand

		if sku_type in ["PTO", "BOTO"]:
			base_calc = requirement - stock - wip - open_po - open_subcon_po
			lines.append(
				f"  Requirement: Open SO + Parent Demand = {open_so_for_breakdown} + {total_parent_demand} = {requirement}"
			)
			lines.append("  Base Calculation: Requirement - Stock - WIP - Open PO - Open Subcon PO")
			lines.append(
				f"                    = {requirement} - {stock} - {wip} - {open_po} - {open_subcon_po}"
			)
			lines.append(f"                    = {base_calc}")
			lines.append(f"  After MRQ: Base - MRQ = {base_calc} - {mrq} = {final_order_rec}")
		else:
			base_calc = requirement - stock - wip - open_po - open_subcon_po
			lines.append(
				f"  Requirement: Open SO + Parent Demand = {open_so_for_breakdown} + {total_parent_demand} = {requirement}"
			)
			lines.append("  Base Calculation: Requirement - Stock - WIP - Open PO - Open Subcon PO")
			lines.append(
				f"                    = {requirement} - {stock} - {wip} - {open_po} - {open_subcon_po}"
			)
			lines.append(f"                    = {base_calc}")
			lines.append(f"  After MRQ: Base - MRQ = {base_calc} - {mrq} = {final_order_rec}")

		if final_order_rec <= 0:
			if moq > 0:
				lines.append(f"  MOQ: {moq} (Not applied - base order rec is {final_order_rec} <= 0)")
			elif batch_size > 0:
				lines.append(
					f"  Batch Size: {batch_size} (Not applied - base order rec is {final_order_rec} <= 0)"
				)
			else:
				lines.append("  No MOQ or Batch Size")
			lines.append(f"  Net Order Recommendation: 0 (Base order rec is {final_order_rec} <= 0)")
		elif moq > 0:
			if moq < final_order_rec:
				lines.append(f"  MOQ: {moq} (MOQ < Order Rec, using Order Rec)")
				lines.append(f"  Net Order Recommendation: {final_order_rec}")
			else:
				lines.append(f"  MOQ: {moq} (MOQ >= Order Rec, using MOQ)")
				lines.append(f"  Net Order Recommendation: {moq}")
		elif batch_size > 0:
			net_calc = math.ceil(final_order_rec / batch_size) * batch_size
			lines.append(f"  Batch Size: {batch_size}")
			lines.append(
				f"  Net Order Recommendation: ceil({final_order_rec} / {batch_size}) x {batch_size} = {net_calc}"
			)
		else:
			lines.append("  No MOQ or Batch Size")
			lines.append(f"  Net Order Recommendation: {final_order_rec}")

	return "\n".join(lines)


def generate_detailed_log_po_report(data: list[dict], net_order_recommendations: dict[str, float]) -> str:
	lines = []
	lines.append("\n" + "=" * 100)
	lines.append("PO RECOMMENDATION FOR PSP - DETAILED BREAKDOWN (NET ORDER RECOMMENDATIONS)")
	lines.append("=" * 100)

	item_row_map = {}
	for row in data:
		item_code = row.get("item_code")
		if item_code:
			if item_code not in item_row_map:
				item_row_map[item_code] = []
			item_row_map[item_code].append(row)

	all_item_codes = set(item_row_map.keys())
	lines.append(f"\nTotal Items Processed: {len(all_item_codes)}")

	items_with_net_rec = [
		item_code for item_code in all_item_codes if flt(net_order_recommendations.get(item_code, 0)) > 0
	]

	lines.append("\n" + "-" * 100)
	lines.append("SUMMARY (Items with Net Order Recommendation > 0)")
	lines.append("-" * 100)

	for item_code in sorted(items_with_net_rec):
		net_rec = flt(net_order_recommendations.get(item_code, 0))
		rows = item_row_map.get(item_code, [])
		if rows:
			first_row = rows[0]
			buffer_flag = first_row.get("buffer_flag", "Unknown")
			order_rec = first_row.get("order_recommendation", 0)
			lines.append(f"  {item_code} ({buffer_flag}): Net Order Rec = {net_rec} (Base: {order_rec})")

	lines.append("\n" + "=" * 100)
	lines.append("DETAILED BREAKDOWN FOR ALL ITEMS")
	lines.append("=" * 100)

	sorted_item_codes = sorted(
		all_item_codes,
		key=lambda x: (flt(net_order_recommendations.get(x, 0)), x),
		reverse=True,
	)

	for item_code in sorted_item_codes:
		rows = item_row_map.get(item_code, [])
		if rows:
			first_row = rows[0]
			breakdown = first_row.get("calculation_breakdown", "")
			if breakdown and breakdown.strip():
				lines.append(breakdown)
			else:
				buffer_flag = first_row.get("buffer_flag", "Unknown")
				order_rec = first_row.get("order_recommendation", 0)
				net_rec = flt(net_order_recommendations.get(item_code, 0))
				moq = first_row.get("moq", 0)
				batch_size = first_row.get("batch_size", 0)
				lines.append(f"\n  Item: {item_code}")
				lines.append(f"  Type: {buffer_flag}")
				lines.append(f"  Base Order Recommendation: {order_rec}")
				lines.append(f"  Net Order Recommendation: {net_rec}")
				if moq > 0:
					lines.append(f"  MOQ: {moq}")
				if batch_size > 0:
					lines.append(f"  Batch Size: {batch_size}")
				lines.append("  Note: Detailed breakdown not available")
		else:
			net_rec = flt(net_order_recommendations.get(item_code, 0))
			lines.append(f"\n  Item: {item_code}")
			lines.append(f"  Net Order Recommendation: {net_rec}")
			lines.append("  Note: Item not in data")
		lines.append("-" * 100)

	lines.append("\n" + "=" * 100)
	return "\n".join(lines)
