# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import math
from bisect import bisect_right

import frappe
from frappe.utils import flt

from prakash_steel.prakash_steel.report.otif_report.otif_report import get_week_label
from prakash_steel.utils.lead_time import get_default_bom
from prakash_steel.utils.stock_lineage import load_stock_lineage


def round_up_2dp(value: float) -> float:
	"""Round UP (ceiling) to 2 decimal places, e.g. 1.323 -> 1.33, 0.121 -> 0.13."""
	return math.ceil(round(value * 100, 6)) / 100


def round_2dp(value) -> float:
	"""Round to 2 decimal places (the precision every numeric column here is
	displayed at), so a value feeding into a later formula is always the same
	number the user sees in this row, never a hidden full-precision one."""
	return round(flt(value), 2)


TVC_ZERO_ITEM_TYPES = {"JW Service", "Scrap"}
TVC_QUANTITY_RATE_ITEM_TYPES = {"Traded", "BO", "RM"}
TVC_QTY_PER_UNIT_ITEM_TYPES = {"BB", "RB"}
QTY_PER_UNIT_BLANK_ITEM_TYPES = {"BO", "Traded", "RM", "Scrap"}

# BO and Traded items don't really have a BOM (whatever the system happens to
# have on file for them), so RB Code/RM Code traversal never starts for them -
# Item Category falls straight back to the sold item's own category instead.
NO_BOM_ITEM_TYPES = {"BO", "Traded"}

# JW is a Category (Item.custom_category_name), not an Item Type - a job-work
# item keeps its normal item type (RM/RB/BB/BO/JW Service) but its category is
# "JW", so T/Kg and Total T's JW/Scrap check has to look at the item's own
# category, not its item type.
JW_SCRAP_CATEGORIES = {"JW", "Scrap"}


def execute(filters: dict | None = None) -> tuple[list, list]:
	filters = filters or {}

	data = get_data(filters)
	columns = get_columns(get_rm_counts_per_rb(data))
	blank_missing_breakdown_fields(data, columns)

	return columns, data


def get_columns(rm_counts_per_rb: list[int] | tuple = ()) -> list[dict]:
	columns = get_static_columns()
	after = next(i for i, c in enumerate(columns) if c["fieldname"] == "traced_percent") + 1
	columns[after:after] = get_breakdown_columns(rm_counts_per_rb)
	return columns


def get_breakdown_columns(rm_counts_per_rb: list[int] | tuple) -> list[dict]:
	"""Actual production breakdown columns: first every RB n set, then every
	RB n RM m set (RB 1's RMs, then RB 2's, ...). ``rm_counts_per_rb[n-1]`` is
	how many RM sets RB n needs - each RB position is sized on its own, so an
	RB n RM m column only exists if some row actually has that RM.
	Item columns are Data, like RB Code / RM Code: as Links to Item, ERPNext's
	Item link formatter would append the row's item_name - the SOLD item's
	name - to every one ("26x6mm Flat MS: B 25x5mm Flat MS")."""
	columns = []
	rb_count = len(rm_counts_per_rb)
	for i in range(1, rb_count + 1):
		columns += [
			{"label": f"RB {i}", "fieldname": f"rb_{i}", "fieldtype": "Data", "width": 130},
			{"label": f"RB {i} Qty", "fieldname": f"rb_{i}_qty", "fieldtype": "Float", "width": 90},
		]
	for i, rm_count in enumerate(rm_counts_per_rb, start=1):
		for j in range(1, rm_count + 1):
			prefix = f"rb_{i}_rm_{j}"
			columns += [
				{"label": f"RB {i} RM {j}", "fieldname": prefix, "fieldtype": "Data", "width": 130},
				{"label": f"RB {i} RM {j} Qty", "fieldname": f"{prefix}_qty", "fieldtype": "Float", "width": 110},
				{
					"label": f"RB {i} RM {j} Rate",
					"fieldname": f"{prefix}_rate",
					"fieldtype": "Currency",
					"width": 110,
				},
			]
	return columns


def get_rm_counts_per_rb(data: list[dict]) -> list[int]:
	"""For each RB position (RB 1, RB 2, ...) any row has, the most RMs any
	row has under that position."""
	counts: list[int] = []
	for row in data:
		for i, rm_count in enumerate(row.get("rm_counts") or []):
			if i == len(counts):
				counts.append(0)
			counts[i] = max(counts[i], rm_count)
	return counts


def get_static_columns() -> list[dict]:
	return [
		# From Sales Invoice / Sales Invoice Item
		{
			"label": "Invoice Date",
			"fieldname": "invoice_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": "Invoice Number",
			"fieldname": "invoice_number",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 130,
		},
		{
			"label": "Sales Order Number",
			"fieldname": "sales_order_number",
			"fieldtype": "Link",
			"options": "Sales Order",
			"width": 150,
		},
		{
			"label": "Customer Name",
			"fieldname": "customer_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "Customer Group",
			"fieldname": "customer_group",
			"fieldtype": "Link",
			"options": "Customer Group",
			"width": 130,
		},
		{
			"label": "Place of Supply",
			"fieldname": "place_of_supply",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": "Category Name",
			"fieldname": "category_name",
			"fieldtype": "Link",
			"options": "Item Category",
			"width": 130,
		},
		{
			"label": "Item Code",
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 130,
		},
		{
			"label": "Item Name",
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "Quantity",
			"fieldname": "quantity",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": "Item Price",
			"fieldname": "item_price",
			"fieldtype": "Currency",
			"width": 100,
		},
		# Derived / to be worked out
		{
			"label": "Expected Delivery Date",
			"fieldname": "expected",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": "Item Type",
			"fieldname": "item_type",
			"fieldtype": "Link",
			"options": "Item Type",
			"width": 100,
		},
		{
			"label": "Month",
			"fieldname": "month",
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"label": "Week",
			"fieldname": "week",
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"label": "Sales Value",
			"fieldname": "sales_value",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": "RB Code",
			"fieldname": "rb_code",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": "RB Type",
			"fieldname": "rb_type",
			"fieldtype": "Link",
			"options": "Item Type",
			"width": 90,
		},
		{
			"label": "RM Code",
			"fieldname": "rm_code",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": "Item Category",
			"fieldname": "item_category",
			"fieldtype": "Link",
			"options": "Item Category",
			"width": 130,
		},
		{
			"label": "Rate",
			"fieldname": "rate",
			"fieldtype": "Currency",
			"width": 90,
		},
		{
			"label": "Rate Source",
			"fieldname": "rate_source",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": "Traced %",
			"fieldname": "traced_percent",
			"fieldtype": "Percent",
			"width": 90,
		},
		{
			"label": "Purchase Month Taken",
			"fieldname": "purchase_month_taken",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": "Qty/Unit",
			"fieldname": "qty_per_unit",
			"fieldtype": "Float",
			"width": 90,
		},
		{
			"label": "TVC",
			"fieldname": "tvc",
			"fieldtype": "Currency",
			"width": 100,
		},
		{
			"label": "TVC/Kg",
			"fieldname": "tvc_per_kg",
			"fieldtype": "Currency",
			"width": 90,
		},
		{
			"label": "T/Kg",
			"fieldname": "t_per_kg",
			"fieldtype": "Float",
			"width": 80,
		},
		{
			"label": "T%",
			"fieldname": "t_percent",
			"fieldtype": "Percent",
			"width": 80,
		},
		{
			"label": "Total T",
			"fieldname": "total_t",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": "Rolling Time (Kgs/Hr)",
			"fieldname": "rolling_time_kgs_hr",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": "Total Rolling Time (Hrs)",
			"fieldname": "total_rolling_time_hrs",
			"fieldtype": "Float",
			"precision": 2,
			"width": 150,
		},
		{
			"label": "Rolling T/Cu",
			"fieldname": "rolling_t_per_cu",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": "Bright Machine",
			"fieldname": "bright_machine",
			"fieldtype": "Link",
			"options": "Bright Machine",
			"width": 120,
		},
		{
			"label": "Bright Time (Kgs/Hr)",
			"fieldname": "bright_time_kgs_hr",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": "Total Bright Time (Hrs)",
			"fieldname": "total_bright_time_hrs",
			"fieldtype": "Float",
			"precision": 2,
			"width": 150,
		},
		{
			"label": "Bright T/Cu",
			"fieldname": "bright_t_per_cu",
			"fieldtype": "Float",
			"width": 100,
		},
	]


def get_data(filters: dict) -> list[dict]:
	if not filters.get("from_date"):
		filters["from_date"] = "2020-01-01"
	if not filters.get("to_date"):
		filters["to_date"] = "2030-12-31"

	# Credit notes are not shown as their own rows; instead their effect is folded
	# back into the original invoice row they were issued against (see
	# apply_credit_note_adjustments), so the base query only pulls actual sales.
	# An item with no Item Type (e.g. a non-inventory line like "Rent") has no
	# place in this report's RB/RM/BB/TVC logic, so it's excluded outright.
	conditions = (
		"si.docstatus = 1 AND si.is_return = 0 AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s"
		" AND item.custom_item_type IS NOT NULL AND item.custom_item_type != ''"
	)

	if filters.get("customer"):
		conditions += " AND si.customer = %(customer)s"

	if filters.get("item_code"):
		conditions += " AND sii.item_code = %(item_code)s"

	query = f"""
		SELECT
			si.posting_date AS invoice_date,
			si.name AS invoice_number,
			sii.sales_order AS sales_order_number,
			si.customer_name AS customer_name,
			si.customer_group AS customer_group,
			si.place_of_supply AS place_of_supply,
			item.custom_category_name AS category_name,
			sii.item_code AS item_code,
			sii.item_name AS item_name,
			sii.qty AS quantity,
			sii.rate AS item_price,
			sii.expected_delivery_date AS expected,
			item.custom_item_type AS item_type,
			sii.name AS si_detail,
			sii.dn_detail AS dn_detail,
			si.update_stock AS update_stock

		FROM
			`tabSales Invoice` si
		INNER JOIN
			`tabSales Invoice Item` sii ON sii.parent = si.name
		LEFT JOIN
			`tabItem` item ON item.name = sii.item_code

		WHERE {conditions}

		ORDER BY si.posting_date ASC, si.name
	"""

	data = frappe.db.sql(query, filters, as_dict=True)

	apply_credit_note_adjustments(data)

	week_start_day = frappe.db.get_single_value("Calendar Settings", "week_start_day") or "Monday"
	fiscal_years = frappe.get_all(
		"Fiscal Year",
		fields=["year_start_date", "year_end_date"],
		order_by="year_start_date asc",
	)
	for row in data:
		row["week"] = get_week_label(row.get("invoice_date"), week_start_day, fiscal_years)
		row["month"] = format_month_label(row["invoice_date"]) if row.get("invoice_date") else None
		row["sales_value"] = round_2dp(flt(row.get("quantity")) * flt(row.get("item_price")))

	set_bom_derived_columns(data)
	set_purchase_rate_columns(data)
	set_actual_rate_columns(data, filters["to_date"])

	for row in data:
		tvc = get_tvc(row.get("item_type"), row.get("quantity"), row.get("rate"), row.get("qty_per_unit"))
		row["tvc"] = round_2dp(tvc) if tvc is not None else None
		row["tvc_per_kg"] = round_2dp(flt(row.get("rate")) * flt(row.get("qty_per_unit")))
		if row.get("category_name") in JW_SCRAP_CATEGORIES:
			row["t_per_kg"] = 0
		else:
			row["t_per_kg"] = round_2dp(flt(row.get("item_price")) - flt(row.get("tvc_per_kg")))

		row["t_percent"] = (
			round_2dp(flt(row.get("t_per_kg")) / flt(row.get("item_price")) * 100) if row.get("item_price") else None
		)

		if row.get("category_name") in JW_SCRAP_CATEGORIES:
			row["total_t"] = round_2dp(flt(row.get("quantity")) * flt(row.get("item_price")))
		else:
			row["total_t"] = round_2dp(max(flt(row.get("sales_value")) - flt(row.get("tvc")), 0))

	set_rolling_time_column(data)
	set_bright_machine_column(data)

	return data


def set_rolling_time_column(data: list[dict]) -> None:
	"""Rolling Time (Kgs/Hr), Total Rolling Time (Hrs) and Rolling T/Cu only
	apply to RB items (JW-category items and BB items are left blank). Rolling
	Time is looked up by the sold item's own item_code against Rolling Algo's
	per_hour_planned_qty; Total Rolling Time is Quantity / Rolling Time;
	Rolling T/Cu is T/Kg * Rolling Time."""
	per_hour_qty_map = {
		r.item_code: flt(r.per_hour_planned_qty)
		for r in frappe.get_all("Rolling Algo", fields=["item_code", "per_hour_planned_qty"])
	}

	for row in data:
		if row.get("category_name") != "JW" and row.get("item_type") == "RB":
			rolling_time_kgs_hr = per_hour_qty_map.get(row.get("item_code"))
			row["rolling_time_kgs_hr"] = round_2dp(rolling_time_kgs_hr) if rolling_time_kgs_hr else None
			row["total_rolling_time_hrs"] = (
				round_up_2dp(flt(row.get("quantity")) / flt(row["rolling_time_kgs_hr"]))
				if row.get("rolling_time_kgs_hr")
				else None
			)
			row["rolling_t_per_cu"] = round_2dp(flt(row.get("t_per_kg")) * flt(row.get("rolling_time_kgs_hr")))
		else:
			row["rolling_time_kgs_hr"] = None
			row["total_rolling_time_hrs"] = None
			row["rolling_t_per_cu"] = None


def set_bright_machine_column(data: list[dict]) -> None:
	"""Bright Machine, Bright Time (Kgs/Hr), Total Bright Time (Hrs) and Bright
	T/Cu only apply to BB items (JW-category items and RB items are left
	blank), looked up by the sold item's own item_code against Bright Machine
	Master's default (is_default = 1) machine row - its machine_group_name and
	mt_per_hour_production respectively; Total Bright Time is Quantity /
	Bright Time; Bright T/Cu is T/Kg * Bright Time."""
	machine_rows = frappe.db.sql(
		"""
		SELECT bmm.item_code AS item_code, bmmt.machine_group_name AS machine_group_name,
			bmmt.mt_per_hour_production AS mt_per_hour_production
		FROM `tabBright Machine Master` bmm
		INNER JOIN `tabBright Machine Master Table` bmmt ON bmmt.parent = bmm.name
		WHERE bmmt.is_default = 1
		""",
		as_dict=True,
	)
	default_machine_map = {r.item_code: r for r in machine_rows}

	for row in data:
		if row.get("category_name") != "JW" and row.get("item_type") == "BB":
			default_machine = default_machine_map.get(row.get("item_code"))
			row["bright_machine"] = default_machine.machine_group_name if default_machine else None
			row["bright_time_kgs_hr"] = (
				round_2dp(default_machine.mt_per_hour_production) if default_machine else None
			)
			row["total_bright_time_hrs"] = (
				round_up_2dp(flt(row.get("quantity")) / flt(row["bright_time_kgs_hr"]))
				if row.get("bright_time_kgs_hr")
				else None
			)
			row["bright_t_per_cu"] = round_2dp(flt(row.get("t_per_kg")) * flt(row.get("bright_time_kgs_hr")))
		else:
			row["bright_machine"] = None
			row["bright_time_kgs_hr"] = None
			row["total_bright_time_hrs"] = None
			row["bright_t_per_cu"] = None


def apply_credit_note_adjustments(data: list[dict]) -> None:
	"""Credit notes don't get their own row; instead they're folded back into the
	original invoice row(s) they were issued against (matched by return_against +
	item_code). A genuine stock return (update_stock = 1, or its linked Delivery
	Note was itself a return) reduces that row's Quantity. A billing-only credit
	note (e.g. a rate/weight adjustment that never moved stock) instead reduces
	that row's Item Price, spreading its amount evenly over the row's quantity -
	same real-vs-billing-only distinction the OTIF report applies."""
	invoice_numbers = {row["invoice_number"] for row in data if row.get("invoice_number")}
	if not invoice_numbers:
		return

	credit_note_rows = frappe.db.sql(
		"""
		SELECT
			si.return_against AS return_against,
			sii.item_code AS item_code,
			sii.qty AS qty,
			sii.amount AS amount,
			si.update_stock AS update_stock,
			dn.is_return AS dn_is_return
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		LEFT JOIN `tabDelivery Note` dn ON dn.name = sii.delivery_note
		WHERE si.docstatus = 1 AND si.is_return = 1 AND si.return_against IN %(invoices)s
		""",
		{"invoices": list(invoice_numbers)},
		as_dict=True,
	)
	if not credit_note_rows:
		return

	groups: dict[tuple, list[dict]] = {}
	for row in data:
		groups.setdefault((row.get("invoice_number"), row.get("item_code")), []).append(row)

	for credit_row in credit_note_rows:
		matched_rows = groups.get((credit_row.return_against, credit_row.item_code))
		if not matched_rows:
			continue

		group_qty_total = sum(flt(row.get("quantity")) for row in matched_rows)
		if group_qty_total <= 0:
			continue

		is_stock_return = bool(credit_row.update_stock) or bool(credit_row.dn_is_return)
		if is_stock_return:
			qty_to_remove = abs(flt(credit_row.qty))
			for row in matched_rows:
				share = flt(row.get("quantity")) / group_qty_total
				row["quantity"] = round_2dp(max(flt(row.get("quantity")) - qty_to_remove * share, 0))
		else:
			rate_reduction = abs(flt(credit_row.amount)) / group_qty_total
			for row in matched_rows:
				row["item_price"] = round_2dp(flt(row.get("item_price")) - rate_reduction)


RB_CODE_CHILD_ITEM_TYPES = {"RB", "BO"}


def set_bom_derived_columns(data: list[dict]) -> None:
	"""RB Code and RM Code walk the default BOM one level at a time, but which
	column a level's child lands in depends on THAT CHILD's own item type, not
	the traversal level: a level-1 child typed RB or BO is the sold item's RB
	precursor, so it lands in RB Code, and RB Code's own default BOM child (a
	billet, typed RM) then lands in RM Code. A level-1 child typed RM (e.g. the
	sold item is itself RB-tier, so its BOM child is a billet, not a rolled
	bar) skips RB Code entirely and lands directly in RM Code - RB Code is
	only ever the RB/BO item, never the billet. The traversal never even
	starts when the sold item's own Item Type is BO or Traded - those types
	don't really have a BOM regardless of what the system has on file for
	them, so RB Code and RM Code are always blank for them. The same applies
	one level down: if RB Code's own item type is BO (RB Code can be RB or
	BO), it doesn't get a level-2 BOM lookup either, so RM Code stays blank
	for it too. RB Type is RB Code's own item type - distinct from Item Type,
	which is the sold item's own item type. Item Category is RM Code's
	category when set; otherwise it falls back to RB Code's own category; if
	the sold item itself has no BOM (no RB Code or RM Code either, including
	the BO/Traded case), it falls back further to the sold item's own
	category.
	Qty/Unit chains the two BOM levels' consumption ratios (BOM Item.qty /
	BOM.quantity) together: units of RM Code per unit of RB Code, times units
	of RB Code per unit of the sold item - blank whenever the sold item's own
	Item Type is BO, Traded, RM or Scrap."""
	item_codes = {row["item_code"] for row in data if row.get("item_code")}
	item_type_by_item_code = {row["item_code"]: row.get("item_type") for row in data if row.get("item_code")}
	level1_map = {
		item_code: (
			None
			if item_type_by_item_code.get(item_code) in NO_BOM_ITEM_TYPES
			else get_default_bom_consumption(item_code)
		)
		for item_code in item_codes
	}

	level1_children = {c.item_code for c in level1_map.values() if c}
	item_info_map = {}
	if level1_children:
		item_info_map = {
			d.name: d
			for d in frappe.get_all(
				"Item",
				filters={"name": ["in", list(level1_children)]},
				fields=["name", "custom_item_type", "custom_category_name"],
			)
		}

	rb_code_map = {}
	direct_rm_code_map = {}
	for item_code, consumption in level1_map.items():
		if not consumption:
			continue
		child_type = item_info_map[consumption.item_code].custom_item_type if consumption.item_code in item_info_map else None
		if child_type in RB_CODE_CHILD_ITEM_TYPES:
			rb_code_map[item_code] = consumption.item_code
		elif child_type == "RM":
			direct_rm_code_map[item_code] = consumption.item_code

	rb_items = set(rb_code_map.values())
	level2_map = {
		rb_item: (
			None
			if item_info_map.get(rb_item) and item_info_map[rb_item].custom_item_type in NO_BOM_ITEM_TYPES
			else get_default_bom_consumption(rb_item)
		)
		for rb_item in rb_items
	}
	rm_code_map = {rb_item: (c.item_code if c else None) for rb_item, c in level2_map.items()}

	rm_items = {rm_item for rm_item in rm_code_map.values() if rm_item} | set(direct_rm_code_map.values())
	missing_items = rm_items - set(item_info_map.keys())
	if missing_items:
		item_info_map.update(
			{
				d.name: d
				for d in frappe.get_all(
					"Item",
					filters={"name": ["in", list(missing_items)]},
					fields=["name", "custom_item_type", "custom_category_name"],
				)
			}
		)

	for row in data:
		item_code = row.get("item_code")
		rb_code = rb_code_map.get(item_code)
		rm_code = rm_code_map.get(rb_code) if rb_code else direct_rm_code_map.get(item_code)
		row["rb_code"] = rb_code
		row["rb_type"] = item_info_map[rb_code].custom_item_type if rb_code in item_info_map else None
		row["rm_code"] = rm_code

		category_source = rm_code if rm_code else rb_code
		if category_source in item_info_map:
			row["item_category"] = item_info_map[category_source].custom_category_name
		else:
			row["item_category"] = row.get("category_name")

		# Qty/Unit is how many units of raw material go into one unit of the
		# sold item, chained across both BOM levels: x (item -> RB Code) *
		# y (RB Code -> RM Code). Only one level's ratio is used when the
		# other level has no BOM of its own.
		if row.get("item_type") in QTY_PER_UNIT_BLANK_ITEM_TYPES:
			row["qty_per_unit"] = None
		else:
			ratio1 = level1_map[item_code].ratio if level1_map.get(item_code) else None
			ratio2 = level2_map[rb_code].ratio if rb_code and level2_map.get(rb_code) else None
			if ratio1 is not None and ratio2 is not None:
				row["qty_per_unit"] = round_2dp(ratio1 * ratio2)
			else:
				row["qty_per_unit"] = round_2dp(ratio1) if ratio1 is not None else None


def get_tvc(item_type: str | None, quantity, rate, qty_per_unit) -> float | None:
	"""JW/Scrap items carry no variable cost. Traded/BO/RM items cost quantity *
	rate (the raw-material purchase rate). BB/RB items additionally scale by how
	many raw-material units it took to produce them (Qty/Unit)."""
	if item_type in TVC_ZERO_ITEM_TYPES:
		return 0
	if item_type in TVC_QUANTITY_RATE_ITEM_TYPES:
		return flt(quantity) * flt(rate)
	if item_type in TVC_QTY_PER_UNIT_ITEM_TYPES:
		return flt(quantity) * flt(rate) * flt(qty_per_unit)
	return None


RATE_SOURCE_ACTUAL = "Actual"
RATE_SOURCE_PARTIAL = "Partial"
RATE_SOURCE_ESTIMATED = "Estimated"

# Below this share traced, the row is flagged Partial rather than Actual.
FULLY_TRACED_PERCENT = 99.5

# Stock received through Material Receipts at a zero or token placeholder rate
# (e.g. Rs 0.01/kg, to get past ERPNext's zero-valuation check) flows through
# FIFO at that same meaningless cost. No real raw material costs under this per
# unit, so such a lot counts as untraced, not as cheap material.
MIN_ACTUAL_RATE = 1.0


def set_actual_rate_columns(data: list[dict], to_date) -> None:
	"""Replace Rate with the actual rate of the END raw material the sold
	quantity was made from, and lay out what it was actually made from in the
	RB 1..n / RM 1..n columns. The sale's outgoing Stock Ledger Entry (the
	invoice's own when update_stock = 1, else its Delivery Note line's via
	dn_detail) is traced back through the actual FIFO lots, transfers and
	Manufacture entries (whichever BOM / child items were really consumed)
	until it reaches an item that is not RB/BB - the RM billet, or a BO (see
	utils/stock_lineage.py).

	RB n / RB n Qty: the RB items the sold qty went through, with the share
	of the sold qty each one accounts for; a sold RB is its own RB 1. RB n RM
	m / Qty / Rate: the end raw materials that went into RB n, each one's
	share of RB n's qty and its actual rate. Where the chain stops at a BO (or
	at stock that was bought in rather than produced) there is nothing behind
	it to show: that share gets no RB / RM columns, but its own actual rate
	still counts in Rate. Rate is the share-weighted average of all the
	end-material rates. A sold RM/BO/Traded item is its own end material and gets no
	breakdown columns. Rate stays per unit of raw material,
	so TVC still scales BB/RB by Qty/Unit.

	Traced % is how much of the sold quantity could be followed back to a
	priced end material; the rest came from stock received at a zero /
	placeholder rate or without a production record (e.g. an RB brought in by
	Material Receipt) and is left out of the breakdown and the average. Rate
	Source: Actual when fully traced, Partial when only some was, Estimated
	when nothing could be traced and the category-average estimate from
	set_purchase_rate_columns is kept instead."""
	detail_by_row = {}
	for row in data:
		detail = row.get("si_detail") if row.get("update_stock") else row.get("dn_detail")
		if detail and row.get("category_name") not in JW_SCRAP_CATEGORIES:
			detail_by_row[id(row)] = detail

	lineage = load_stock_lineage(to_date, MIN_ACTUAL_RATE) if detail_by_row else None

	for row in data:
		detail = detail_by_row.get(id(row))
		breakdown = lineage.get_breakdown(detail) if lineage and detail else None
		if breakdown:
			row["rate"] = breakdown.rate
			row["traced_percent"] = round_2dp(breakdown.traced_percent)
			row["rate_source"] = (
				RATE_SOURCE_ACTUAL if breakdown.traced_percent >= FULLY_TRACED_PERCENT else RATE_SOURCE_PARTIAL
			)
			row["purchase_month_taken"] = None
			if row.get("item_type") in TVC_QTY_PER_UNIT_ITEM_TYPES:
				set_breakdown_fields(row, breakdown)
		else:
			row["traced_percent"] = None
			row["rate_source"] = RATE_SOURCE_ESTIMATED if row.get("rate") is not None else None

		for key in ("si_detail", "dn_detail", "update_stock"):
			row.pop(key, None)


def blank_missing_breakdown_fields(data: list[dict], columns: list[dict]) -> None:
	"""Rows with fewer (or no) RBs / RMs than the widest row get explicit
	blanks in the extra breakdown columns - a missing key renders as 0.00 in a
	Float column rather than as empty."""
	fieldnames = [c["fieldname"] for c in columns if c["fieldname"].startswith("rb_") and c["fieldname"] not in ("rb_code", "rb_type")]
	for row in data:
		for fieldname in fieldnames:
			row.setdefault(fieldname, None)


def set_breakdown_fields(row: dict, breakdown) -> None:
	"""Flatten a stock_lineage breakdown into the row's RB n / RB n RM m
	fields, recording how many RMs each of its RBs has (rm_counts) so the
	report knows how many column sets to show. Only RBs with RMs behind them
	are listed: where the chain stopped at the RB level - a BO, or an RB/BB
	(including the sold item itself) that was bought in - the trace ends
	there, so it gets no RB / RM columns; its rate is still in Rate."""
	groups = [g for g in breakdown.rbs if g.rms]
	for i, group in enumerate(groups, start=1):
		row[f"rb_{i}"] = group.rb
		row[f"rb_{i}_qty"] = round_2dp(group.qty)
		for j, (rm_item, qty, rate) in enumerate(group.rms, start=1):
			row[f"rb_{i}_rm_{j}"] = rm_item
			row[f"rb_{i}_rm_{j}_qty"] = round_2dp(qty)
			row[f"rb_{i}_rm_{j}_rate"] = rate
	row["rm_counts"] = [len(group.rms) for group in groups]


def set_purchase_rate_columns(data: list[dict]) -> None:
	"""Estimated Rate - only the fallback for rows set_actual_rate_columns can't
	trace through the Stock Ledger.
	Rate is the average purchase rate (amount/qty) of Purchase Receipt lines
	whose item shares the row's Item Category, within the invoice's own
	calendar month - grouped by category + month exactly like the Purchase
	report's Avg Rate, so the two reports agree. This is a category average:
	it applies whenever the CATEGORY was received that month, even if the
	row's own specific item wasn't one of the lines received - no per-item
	check on top of the category+month match. Only when the category itself
	has no receipts that month does it fall back to the specific raw-material
	item's (RM Code, else RB Code, else the sold item) own most recent
	purchase receipt rate as of the invoice date (never a later one - it
	hadn't been received yet at the time of this sale), and record that
	receipt's date in Purchase Month Taken. If the item was never received
	before this sale at all, Rate and Purchase Month Taken are left blank.
	JW/Scrap-category rows are always blank - there is no raw-material
	purchase rate to show for them."""
	categories = {row["item_category"] for row in data if row.get("item_category")}
	rate_source_items = {
		(row.get("rm_code") or row.get("rb_code") or row.get("item_code"))
		for row in data
		if row.get("rm_code") or row.get("rb_code") or row.get("item_code")
	}
	if not categories and not rate_source_items:
		for row in data:
			row["rate"] = None
			row["purchase_month_taken"] = None
		return

	monthly_rate_map = {}
	if categories:
		monthly_rows = frappe.db.sql(
			"""
			SELECT
				item.custom_category_name AS category,
				YEAR(pr.posting_date) AS y,
				MONTH(pr.posting_date) AS m,
				AVG(pri.amount / pri.qty) AS avg_rate
			FROM `tabPurchase Receipt Item` pri
			INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
			LEFT JOIN `tabItem` item ON item.name = pri.item_code
			WHERE pr.docstatus = 1 AND item.custom_category_name IN %(categories)s AND pri.qty != 0
			GROUP BY item.custom_category_name, y, m
			""",
			{"categories": list(categories)},
			as_dict=True,
		)
		monthly_rate_map = {(r.category, r.y, r.m): r.avg_rate for r in monthly_rows}

	purchases_by_item: dict[str, list] = {}
	if rate_source_items:
		purchase_rows = frappe.db.sql(
			"""
			SELECT pri.item_code AS item_code, pr.posting_date AS posting_date, (pri.amount / pri.qty) AS rate
			FROM `tabPurchase Receipt Item` pri
			INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
			WHERE pr.docstatus = 1 AND pri.item_code IN %(items)s AND pri.qty != 0
			ORDER BY pr.posting_date ASC
			""",
			{"items": list(rate_source_items)},
			as_dict=True,
		)
		for purchase_row in purchase_rows:
			purchases_by_item.setdefault(purchase_row.item_code, []).append(purchase_row)

	for row in data:
		if row.get("category_name") in JW_SCRAP_CATEGORIES:
			row["rate"] = None
			row["purchase_month_taken"] = None
			continue

		category = row.get("item_category")
		invoice_date = row.get("invoice_date")
		rate_source_item = row.get("rm_code") or row.get("rb_code") or row.get("item_code")
		item_purchases = purchases_by_item.get(rate_source_item)

		monthly_key = (category, invoice_date.year, invoice_date.month) if category and invoice_date else None

		if monthly_key and monthly_key in monthly_rate_map:
			# Kept at full precision (the Currency fieldtype already displays this
			# rounded to 2dp) - Rate gets multiplied by large quantities downstream
			# (TVC etc.), where even a tiny rounding gap would compound noticeably.
			row["rate"] = flt(monthly_rate_map[monthly_key])
			row["purchase_month_taken"] = None
			continue

		nearest_purchase = (
			get_nearest_purchase(item_purchases, invoice_date) if rate_source_item and invoice_date else None
		)
		if nearest_purchase:
			row["rate"] = flt(nearest_purchase.rate)
			row["purchase_month_taken"] = format_month_label(nearest_purchase.posting_date)
		else:
			row["rate"] = None
			row["purchase_month_taken"] = None


def format_month_label(date) -> str:
	"""e.g. 15 April 2026 -> '4-26', matching the Purchase report's month column."""
	return f"{date.month}-{date.year % 100:02d}"


def get_nearest_purchase(purchases: list | None, invoice_date):
	"""The latest of ``purchases`` (ascending by posting_date) not later than
	``invoice_date``, found by bisecting instead of scanning per row. If the
	item was never purchased on or before ``invoice_date`` (it hadn't been
	bought yet at that point), there is no rate to show - never reach forward
	into a purchase that hadn't happened yet."""
	if not purchases:
		return None

	dates = [p.posting_date for p in purchases]
	index = bisect_right(dates, invoice_date) - 1
	return purchases[index] if index >= 0 else None


def get_default_bom_consumption(item_code: str) -> "frappe._dict | None":
	"""The single raw material item that ``item_code``'s default BOM consumes,
	and how many units of it go into one unit of ``item_code`` (BOM Item.qty /
	BOM.quantity)."""
	bom_name = get_default_bom(item_code)
	if not bom_name:
		return None

	bom_item = frappe.db.get_value(
		"BOM Item", {"parent": bom_name}, ["item_code", "qty"], order_by="idx asc", as_dict=True
	)
	if not bom_item:
		return None

	bom_quantity = flt(frappe.db.get_value("BOM", bom_name, "quantity")) or 1.0
	return frappe._dict(item_code=bom_item.item_code, ratio=flt(bom_item.qty) / bom_quantity)
