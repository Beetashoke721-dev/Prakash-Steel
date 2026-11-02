# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

from bisect import bisect_right
from datetime import date

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, flt, getdate, nowdate


from prakash_steel.prakash_steel.report.throughput.throughput import get_data as get_throughput_rows

WEEKDAY_INDEX = {
	"Monday": 0,
	"Tuesday": 1,
	"Wednesday": 2,
	"Thursday": 3,
	"Friday": 4,
	"Saturday": 5,
	"Sunday": 6,
}

CRORE = 10_000_000
CRORE_DECIMALS = 2


def execute(filters: dict | None = None):
	filters = filters or {}

	weeks = get_weeks(filters.get("fiscal_year"))
	columns = get_columns(weeks)
	data = get_data(weeks)

	return columns, data


def get_weeks(fiscal_year: str | None) -> list[dict]:
	"""Split the fiscal year into weeks using Calendar Settings.

	Week 1 runs from the fiscal year start to the day before the first
	configured week start day, and the last week is cut off by the fiscal
	year end, so both may be shorter than 7 days.
	"""
	if not fiscal_year:
		return []

	year_start, year_end = frappe.db.get_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"])
	year_start, year_end = getdate(year_start), getdate(year_end)

	week_start_day = frappe.db.get_single_value("Calendar Settings", "week_start_day") or "Monday"
	days_to_first_week_end = (WEEKDAY_INDEX[week_start_day] - year_start.weekday() - 1) % 7

	weeks = []
	start = year_start
	end = min(add_days(start, days_to_first_week_end), year_end)
	while start <= year_end:
		weeks.append({"week_no": len(weeks) + 1, "from_date": start, "to_date": end})
		start = add_days(end, 1)
		end = min(add_days(start, 6), year_end)

	return weeks


def get_columns(weeks: list[dict]) -> list[dict]:
	columns = [
		{
			"label": _("Business Measures"),
			"fieldname": "business_measure",
			"fieldtype": "Data",
			"width": 260,
		},
		{
			"label": _("UOM"),
			"fieldname": "uom",
			"fieldtype": "Data",
			"width": 90,
		},
	]

	for week in weeks:
		columns.append(
			{
				"label": _("W{0} ({1} - {2})").format(
					week["week_no"],
					week["from_date"].strftime("%d %b"),
					week["to_date"].strftime("%d %b"),
				),
				"fieldname": f"week_{week['week_no']}",
				"fieldtype": "Float",
				"precision": CRORE_DECIMALS,
				"width": 130,
			}
		)

	return columns


def get_measure_tree() -> list[dict]:
	"""Hierarchy of business measures shown as a tree, similar to the Trial Balance report.

	Each node is `{"label": ..., "children": [...]}`; leaf nodes omit `children`.
	Branches with no children yet (Financial/Sales Measures) render as empty group nodes
	until measures are added under them.
	"""
	return [
		{
			"label": _("Business Measures"),
			"children": [
				{
					"label": _("Financial Measures"),
					"children": [
						{"label": _("Free Cash Score")},
						{"label": _("Throughput(T)"), "key": "throughput_t", "uom": _("Rs. Cr")},
						{"label": _("T%"), "key": "t_percent", "uom": _("Rs. Cr")},
						{"label": _("T/Cu"), "key": "t_per_cu", "uom": _("Rs. Cr")},
						{"label": _("TVC"), "key": "tvc", "uom": _("Rs. Cr")},
						{"label": _("OE"), "key": "oe", "uom": _("Rs. Cr")},
						{"label": _("T/OE"), "key": "t_oe", "uom": _("Ratio")},
						{
							"label": _("Receivables"),
							"key": "receivables",
							"uom": _("Rs. Cr"),
							"children": [
								{"label": _("Overdue Receivables"), "key": "overdue_receivables", "uom": _("Rs. Cr")},
							],
						},
						{"label": _("Collections"), "key": "collections", "uom": _("Rs. Cr")},
						{
							"label": _("Payables"),
							"key": "payables",
							"uom": _("Rs. Cr"),
							"children": [
								{"label": _("Overdue Payables"), "key": "overdue_payables", "uom": _("Rs. Cr")},
							],
						},
					],
				},
				{
					"label": _("Sales Measures"),
					"children": [
						{
							"label": _("Sales"),
							"key": "sales_total",
							"uom": _("Rs. Cr"),
							"children": [
								{"label": _("Sales Bright"), "key": "sales_bright", "uom": _("Rs. Cr")},
								{"label": _("Sales Rolled"), "key": "sales_rolled", "uom": _("Rs. Cr")},
								{"label": _("Sales BO+Traded"), "key": "sales_bo_traded", "uom": _("Rs. Cr")},
								{"label": _("Sales Others"), "key": "sales_others", "uom": _("Rs. Cr")},
							],
						},
						{
							"label": _("Sales Orders Booked"),
							"key": "order_booking_total",
							"uom": _("Rs. Cr"),
							"children": [
								{"label": _("Order Booking Bright"), "key": "order_booking_bright", "uom": _("Rs. Cr")},
								{"label": _("Order Booking Rolled"), "key": "order_booking_rolled", "uom": _("Rs. Cr")},
								{"label": _("Order Booking BO+Traded"), "key": "order_booking_bo_traded", "uom": _("Rs. Cr")},
								{"label": _("Order Booking Others"), "key": "order_booking_others", "uom": _("Rs. Cr")},
							],
						},
						{
							"label": _("Open Sales Orders"),
							"key": "open_so_total",
							"uom": _("Rs. Cr"),
							"children": [
								{"label": _("Open SO Bright"), "key": "open_so_bright", "uom": _("Rs. Cr")},
								{"label": _("Open SO Rolled"), "key": "open_so_rolled", "uom": _("Rs. Cr")},
								{"label": _("Open SO BO+Traded"), "key": "open_so_bo_traded", "uom": _("Rs. Cr")},
								{"label": _("Open SO Others"), "key": "open_so_others", "uom": _("Rs. Cr")},
							],
						},
						{
							"label": _("Pending Sales Order in Black"),
							"key": "pending_so_black_total",
							"uom": _("Rs. Cr"),
							"children": [
								{"label": _("Pending SO Black Bright"), "key": "pending_so_black_bright", "uom": _("Rs. Cr")},
								{"label": _("Pending SO Black Rolled"), "key": "pending_so_black_rolled", "uom": _("Rs. Cr")},
								{"label": _("Pending SO Black BO+Traded"), "key": "pending_so_black_bo_traded", "uom": _("Rs. Cr")},
							],
						},
						{
							"label": _("Sales Order Full-kit"),
							"key": "fullkit_total",
							"uom": _("Tonnes"),
							"children": [
								{"label": _("Order Full-kit Qty"), "key": "order_fullkit_qty", "uom": _("Tonnes")},
								{"label": _("Line Full-kit Qty"), "key": "line_fullkit_qty", "uom": _("Tonnes")},
							],
						},
						{
							"label": _("Sales (Qty)"), "key": "sales_qty_total",
							"uom": _("Tonnes"),
							"children": [
								{"label": _("Sales Qty Bright"), "key": "sales_qty_bright", "uom": _("Tonnes")},
								{"label": _("Sales Qty Rolled"), "key": "sales_qty_rolled", "uom": _("Tonnes")},
								{"label": _("Sales Qty BO+Traded"), "key": "sales_qty_bo_traded", "uom": _("Tonnes")},
								{"label": _("RB Consumption by Bright"), "key": "rb_consumption_by_bright", "uom": _("Tonnes")},
							],
						},
						{
							"label": _("Production (Qty)"), "key": "production_qty_total",
							"uom": _("Tonnes"),
							"children": [
								{"label": _("Production Qty Bright"), "key": "production_qty_bright", "uom": _("Tonnes")},
								{"label": _("Production Qty Rolled"), "key": "production_qty_rolled", "uom": _("Tonnes")},
								{"label": _("Production Qty Rolled SubCon"), "key": "production_qty_rolled_subcon", "uom": _("Tonnes")},
							],
						},
						{
							"label": _("Inventory"),
							"key": "inv_TOTAL",
							"uom": _("Tonnes"),
							"children": [
								{
									"label": _("Bright Inventory"), "key": "inv_BRIGHT",
									"uom": _("Tonnes"),
									"children": [
										{"label": _("BBMTA"), "key": "inv_BBMTA", "uom": _("Tonnes")},
										{"label": _("BBMTO"), "key": "inv_BBMTO", "uom": _("Tonnes")},
									],
								},
								{
									"label": _("Rolled Inventory"), "key": "inv_ROLLED",
									"uom": _("Tonnes"),
									"children": [
										{"label": _("RBMTA"), "key": "inv_RBMTA", "uom": _("Tonnes")},
										{"label": _("RBMTO"), "key": "inv_RBMTO", "uom": _("Tonnes")},
									],
								},
								{
									"label": _("BO Inventory"), "key": "inv_BO",
									"uom": _("Tonnes"),
									"children": [
										{"label": _("BOTA"), "key": "inv_BOTA", "uom": _("Tonnes")},
										{"label": _("BOTO"), "key": "inv_BOTO", "uom": _("Tonnes")},
									],
								},
								{
									"label": _("RM Inventory"), "key": "inv_RM",
									"uom": _("Tonnes"),
									"children": [
										{"label": _("PTA"), "key": "inv_PTA", "uom": _("Tonnes")},
										{"label": _("PTO"), "key": "inv_PTO", "uom": _("Tonnes")},
									],
								},
							],
						},
						{
							"label": _("Free Stock"),
							"uom": _("Tonnes"),
							"children": [
								{"label": _("Free Stock Bright"), "key": "free_stock_bright", "uom": _("Tonnes")},
								{"label": _("Free Stock Rolled"), "key": "free_stock_rolled", "uom": _("Tonnes")},
								{"label": _("Free Stock BO"), "key": "free_stock_bo", "uom": _("Tonnes")},
								{"label": _("Free Stock Traded"), "key": "free_stock_traded", "uom": _("Tonnes")},
							],
						},
					],
				},
				{
					"label": _("Operational Measures"),
					"children": [
						{
							"label": _("OTIF"),
							"key": "otif",
							"uom": _("%"),
							"children": [
								{"label": _("Bright OTIF"), "key": "bright_otif", "uom": _("%")},
								{"label": _("Rolled OTIF"), "key": "rolled_otif", "uom": _("%")},
							],
						},
						{
							"label": _("Availability"),
							"key": "ALL_availability",
							"uom": _("%"),
							"children": [
								{
									"label": _("Bright Availability"),
									"key": "BBMTA_availability",
									"uom": _("%"),
									"children": [
										{"label": _("Bright MTA Blacks%"), "key": "BBMTA_black", "uom": _("%")},
										{"label": _("Bright MTA Reds%"), "key": "BBMTA_red", "uom": _("%")},
										{"label": _("Bright MTA Whites%"), "key": "BBMTA_white", "uom": _("%")},
									],
								},
								{
									"label": _("Rolled Availability"),
									"key": "RBMTA_availability",
									"uom": _("%"),
									"children": [
										{"label": _("Rolled MTA Blacks%"), "key": "RBMTA_black", "uom": _("%")},
										{"label": _("Rolled MTA Reds%"), "key": "RBMTA_red", "uom": _("%")},
										{"label": _("Rolled MTA Whites%"), "key": "RBMTA_white", "uom": _("%")},
									],
								},
								{
									"label": _("BO Availability"),
									"key": "BOTA_availability",
									"uom": _("%"),
									"children": [
										{"label": _("BO Blacks%"), "key": "BOTA_black", "uom": _("%")},
										{"label": _("BO Reds%"), "key": "BOTA_red", "uom": _("%")},
										{"label": _("BO Whites%"), "key": "BOTA_white", "uom": _("%")},
									],
								},
								{
									"label": _("RM Availability"),
									"key": "PTA_availability",
									"uom": _("%"),
									"children": [
										{"label": _("PTA Blacks%"), "key": "PTA_black", "uom": _("%")},
										{"label": _("PTA Reds%"), "key": "PTA_red", "uom": _("%")},
										{"label": _("PTA Whites%"), "key": "PTA_white", "uom": _("%")},
									],
								},
								{
									"label": _("TRADED Availability"),
									"key": "TRMTA_availability",
									"uom": _("%"),
									"children": [
										{"label": _("TRADED Blacks%"), "key": "TRMTA_black", "uom": _("%")},
										{"label": _("TRADED Reds%"), "key": "TRMTA_red", "uom": _("%")},
										{"label": _("TRADED Whites%"), "key": "TRMTA_white", "uom": _("%")},
									],
								},
								{
									"label": _("Bright CS Availability"),
									"key": "bcs_availability",
									"uom": _("%"),
									"children": [
										{"label": _("Bright CS Blacks%"), "key": "bcs_black", "uom": _("%")},
										{"label": _("Bright CS Reds%"), "key": "bcs_red", "uom": _("%")},
										{"label": _("Bright CS Whites%"), "key": "bcs_white", "uom": _("%")},
									],
								},
								{
									"label": _("Rolled CS Availability"),
									"key": "rcs_availability",
									"uom": _("%"),
									"children": [
										{"label": _("Rolled CS Blacks%"), "key": "rcs_black", "uom": _("%")},
										{"label": _("Rolled CS Reds%"), "key": "rcs_red", "uom": _("%")},
										{"label": _("Rolled CS Whites%"), "key": "rcs_white", "uom": _("%")},
									],
								},
							],
						},
						{
							"label": _("Bright Machine Net SO Load"),
							"uom": _("Days"),
							"children": [
								{"label": _("Load CDB - 16MM"), "key": "load_CDB_16MM", "uom": _("Days")},
								{"label": _("Load CDB - 27MM"), "key": "load_CDB_27MM", "uom": _("Days")},
								{"label": _("Load DB - 25MM"), "key": "load_DB_25MM", "uom": _("Days")},
								{"label": _("Load DB - 40MM"), "key": "load_DB_40MM", "uom": _("Days")},
								{"label": _("Load DB - 80MM"), "key": "load_DB_80MM", "uom": _("Days")},
								{"label": _("Load DB - 100MM"), "key": "load_DB_100MM", "uom": _("Days")},
								{"label": _("Load PL - 100MM"), "key": "load_PL_100MM", "uom": _("Days")},
							],
						},
						{
							"label": _("Overall Equipment Effectiveness (OEE)"),
							"children": [
								{
									"label": _("Bright OEE"),
									"key": "bright_oee",
									"uom": _("%"),
									"children": [
										{
											"label": _("CDB - 16MM"),
											"key": "cdb_16mm",
											"uom": _("%"),
											"children": [
												{"label": _("OEE CDB - 16MM - Day"), "key": "oee_cdb_16mm_day", "uom": _("%")},
												{"label": _("OEE CDB - 16MM - Night"), "key": "oee_cdb_16mm_night", "uom": _("%")},
											],
										},
										{
											"label": _("CDB - 27MM"),
											"key": "cdb_27mm",
											"uom": _("%"),
											"children": [
												{"label": _("OEE CDB - 27MM - Day"), "key": "oee_cdb_27mm_day", "uom": _("%")},
												{"label": _("OEE CDB - 27MM - Night"), "key": "oee_cdb_27mm_night", "uom": _("%")},
											],
										},
										{
											"label": _("DB - 25MM"),
											"key": "db_25mm",
											"uom": _("%"),
											"children": [
												{"label": _("OEE DB - 25MM - Day"), "key": "oee_db_25mm_day", "uom": _("%")},
												{"label": _("OEE DB - 25MM - Night"), "key": "oee_db_25mm_night", "uom": _("%")},
											],
										},
										{
											"label": _("DB - 40MM"),
											"key": "db_40mm",
											"uom": _("%"),
											"children": [
												{"label": _("OEE DB - 40MM - Day"), "key": "oee_db_40mm_day", "uom": _("%")},
												{"label": _("OEE DB - 40MM - Night"), "key": "oee_db_40mm_night", "uom": _("%")},
											],
										},
										{
											"label": _("DB - 80MM"),
											"key": "db_80mm",
											"uom": _("%"),
											"children": [
												{"label": _("OEE DB - 80MM - Day"), "key": "oee_db_80mm_day", "uom": _("%")},
												{"label": _("OEE DB - 80MM - Night"), "key": "oee_db_80mm_night", "uom": _("%")},
											],
										},
										{
											"label": _("DB - 100MM"),
											"key": "db_100mm",
											"uom": _("%"),
											"children": [
												{"label": _("OEE DB - 100MM - Day"), "key": "oee_db_100mm_day", "uom": _("%")},
												{"label": _("OEE DB - 100MM - Night"), "key": "oee_db_100mm_night", "uom": _("%")},
											],
										},
										{"label": _("PL - 100MM"), "key": "pl_100mm", "uom": _("%")},
									],
								},
							],
						},
					],
				},
			],
		}
	]


def get_data(weeks: list[dict]) -> list[dict]:
	totals = get_throughput_totals_by_week(weeks)
	receivable_totals = get_invoice_totals_by_week(weeks, "Sales Invoice")
	otif = get_otif_percent_by_week(weeks)
	sku_percent = get_sku_percent_by_week(weeks)
	sales = get_sales_by_week(weeks)
	inventory = get_inventory_by_week(weeks)
	sales_qty = get_sales_qty_by_week(weeks)
	rb_consumption = get_rb_consumption_by_week(weeks)
	production_qty = get_production_qty_by_week(weeks)
	oe = get_oe_by_week(weeks)
	production_qty_subcon = get_production_qty_rolled_subcon_by_week(weeks)
	free_stock = get_free_stock_by_week(weeks)

	# Production (Qty) = Bright + Rolled + Rolled SubCon.
	production_qty_total: dict[int, float] = {}
	for source, measure in (
		(production_qty, "production_qty_bright"),
		(production_qty, "production_qty_rolled"),
		(production_qty_subcon, "production_qty_rolled_subcon"),
	):
		for week_no, qty in source.get(measure, {}).items():
			production_qty_total[week_no] = production_qty_total.get(week_no, 0) + qty
	production_qty["production_qty_total"] = {
		week_no: round(qty, 2) for week_no, qty in production_qty_total.items()
	}
	machine_load = get_bright_machine_load_by_week(weeks)
	order_booking = get_order_booking_by_week(weeks)
	open_so = get_open_so_by_week(weeks)
	pending_so_black = get_pending_so_black_by_week(weeks)
	fullkit = get_fullkit_by_week(weeks)
	cs_percent = get_cs_percent_by_week(weeks)
	payable_totals = get_invoice_totals_by_week(weeks, "Purchase Invoice")

	# Throughput report values are in Rs; the sheet's UoM is Rs. Cr.
	throughput_t = {week_no: round(t["total_t"] / CRORE, CRORE_DECIMALS) for week_no, t in totals.items()}
	# T/OE: Throughput(T) over OE for the same week. Blank wherever OE is blank (not
	# yet a completed/in-progress quarter) or zero, same weeks T/OE can't be computed for.
	oee = get_oee_by_week(weeks)
	t_oe = {
		week_no: round(t_value / oe["oe"][week_no], CRORE_DECIMALS)
		for week_no, t_value in throughput_t.items()
		if oe["oe"].get(week_no)
	}

	week_values = {
		**sku_percent,
		**sales,
		**inventory,
		**sales_qty,
		**rb_consumption,
		**production_qty,
		**oe,
		**production_qty_subcon,
		**free_stock,
		**machine_load,
		**order_booking,
		**open_so,
		**pending_so_black,
		**fullkit,
		**cs_percent,
		**oee,
		"throughput_t": throughput_t,
		"t_oe": t_oe,
		"tvc": {week_no: round(t["tvc"] / CRORE, CRORE_DECIMALS) for week_no, t in totals.items()},
		"t_per_cu": {week_no: round(t["t_per_cu"] / CRORE, CRORE_DECIMALS) for week_no, t in totals.items()},
		"receivables": {
			week_no: round(t["invoiced"] / CRORE, CRORE_DECIMALS) for week_no, t in receivable_totals.items()
		},
		"overdue_receivables": {
			week_no: round(t["overdue"] / CRORE, CRORE_DECIMALS) for week_no, t in receivable_totals.items()
		},
		"collections": {
			week_no: round(t["paid"] / CRORE, CRORE_DECIMALS) for week_no, t in receivable_totals.items()
		},
		"payables": {
			week_no: round(t["invoiced"] / CRORE, CRORE_DECIMALS) for week_no, t in payable_totals.items()
		},
		"overdue_payables": {
			week_no: round(t["overdue"] / CRORE, CRORE_DECIMALS) for week_no, t in payable_totals.items()
		},
		"bright_otif": otif["bright_otif"],
		"rolled_otif": otif["rolled_otif"],
		"otif": otif["otif"],
		# T% is weighted: total T over total sales value for the week, not an average of row percentages.
		"t_percent": {
			week_no: round(t["total_t"] / t["sales_value"] * 100, 2)
			for week_no, t in totals.items()
			if t["sales_value"]
		},
	}

	data = []
	add_measure_rows(get_measure_tree(), parent=None, indent=0, data=data, week_values=week_values)
	return data


# Same mapping as the Category Wise Trend report: a buffer item's SKU type.
MTA_SKU_BY_ITEM_TYPE = {"BB": "BBMTA", "RB": "RBMTA", "BO": "BOTA", "RM": "PTA", "Traded": "TRMTA"}
SKU_COLOURS = ("BLACK", "RED", "YELLOW", "GREEN", "WHITE")


def get_sku_percent_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Availability and Black/Red/White % per SKU type, averaged over each week's days.

	Logic copied from the Category Wise Trend report: for each SKU type (BBMTA, RBMTA,
	BOTA, PTA, TRMTA), a day's % per colour is the colour count over the day's total of
	the five colours, over the buffer items of that SKU type. Availability is
	100 - Black% - Red%. A week's value is the sum of its daily values divided by the
	number of days in the week (days with no colour data count as 0, as in the report).
	Days after today aren't counted, so the current week isn't diluted by days not yet reached.
	"""
	result: dict[str, dict[int, float]] = {}
	if not weeks:
		return result

	start, end = weeks[0]["from_date"], weeks[-1]["to_date"]

	current_sku = {}
	for item in frappe.get_all(
		"Item",
		filters={"custom_buffer_flag": "Buffer", "custom_item_type": ["in", list(MTA_SKU_BY_ITEM_TYPE)]},
		fields=["name", "custom_item_type"],
	):
		current_sku[item.name] = MTA_SKU_BY_ITEM_TYPE[item.custom_item_type]

	snapshot = frappe.db.sql(
		"""
		SELECT p.posting_date, c.item_code, c.sku_type, c.on_hand_colour
		FROM `tabItem wise Daily On Hand Colour` p
		INNER JOIN `tabOn hand colour table` c ON c.parent = p.name
		WHERE p.posting_date BETWEEN %(start)s AND %(end)s
		ORDER BY p.posting_date
		""",
		{"start": start, "end": end},
		as_dict=True,
	)

	# (date, sku) -> {item: colour} for the buffer items of each SKU type, and
	# date -> {item: colour} for every item. A later row for the same item/date overwrites, as in the report.
	colour_map: dict[tuple, dict[str, str]] = {}
	all_colours: dict[date, dict[str, str]] = {}
	for row in snapshot:
		if not row.item_code:
			continue
		posting_date = getdate(row.posting_date)
		colour = (row.on_hand_colour or "").strip().upper()
		all_colours.setdefault(posting_date, {})[row.item_code] = colour
		if row.sku_type in MTA_SKU_BY_ITEM_TYPE.values() and current_sku.get(row.item_code) == row.sku_type:
			colour_map.setdefault((posting_date, row.sku_type), {})[row.item_code] = colour

	def day_percentages(colours: dict[str, str]) -> dict[str, float] | None:
		counts = {colour: 0 for colour in SKU_COLOURS}
		for colour in colours.values():
			if colour in counts:
				counts[colour] += 1
		total = sum(counts.values())
		if not total:
			return None
		black = counts["BLACK"] / total * 100
		red = counts["RED"] / total * 100
		return {
			"availability": 100 - black - red,
			"black": black,
			"red": red,
			"white": counts["WHITE"] / total * 100,
		}

	# key -> {date: daily %}
	daily: dict[str, dict[date, float]] = {}
	for posting_date, colours in all_colours.items():
		values = day_percentages(colours)
		if values:
			daily.setdefault("ALL_availability", {})[posting_date] = values["availability"]

	for (posting_date, sku), colours in colour_map.items():
		values = day_percentages(colours)
		if not values:
			continue
		for measure, value in values.items():
			daily.setdefault(f"{sku}_{measure}", {})[posting_date] = value

	today = getdate(nowdate())
	for key, by_date in daily.items():
		averages = {}
		for week in weeks:
			if week["from_date"] > today:
				continue
			days_so_far = (min(week["to_date"], today) - week["from_date"]).days + 1
			total = sum(v for d, v in by_date.items() if week["from_date"] <= d <= week["to_date"])
			averages[week["week_no"]] = round(total / days_so_far, 2)
		result[key] = averages

	return result


def get_sales_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Sales per week split by item type, from submitted Sales Invoice Items.

	Summing the row amount, bucketed by Sales Invoice posting date. A credit note
	(return) is dated by the invoice it was issued against, so it reduces that
	invoice's week rather than the week it was posted:
	Sales Bright = BB, Sales Rolled = RB, Sales BO+Traded = BO or Traded,
	Sales Others = any other item type (including none).
	"""
	result: dict[str, dict[int, float]] = {}
	if not weeks:
		return result

	rows = frappe.db.sql(
		"""
		SELECT
			COALESCE(orig.posting_date, si.posting_date) AS posting_date,
			item.custom_item_type AS item_type,
			SUM(sii.amount) AS amount
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		LEFT JOIN `tabSales Invoice` orig ON si.is_return = 1 AND orig.name = si.return_against
		LEFT JOIN `tabItem` item ON item.name = sii.item_code
		WHERE si.docstatus = 1
			AND COALESCE(orig.posting_date, si.posting_date) BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY COALESCE(orig.posting_date, si.posting_date), item.custom_item_type
		""",
		{"from_date": weeks[0]["from_date"], "to_date": weeks[-1]["to_date"]},
		as_dict=True,
	)

	def measure_for(item_type: str | None) -> str:
		if item_type == "BB":
			return "sales_bright"
		if item_type == "RB":
			return "sales_rolled"
		if item_type in ("BO", "Traded"):
			return "sales_bo_traded"
		return "sales_others"

	totals: dict[tuple[str, int], float] = {}
	for row in rows:
		week = next((w for w in weeks if w["from_date"] <= row.posting_date <= w["to_date"]), None)
		if not week:
			continue
		key = (measure_for(row.item_type), week["week_no"])
		totals[key] = totals.get(key, 0) + flt(row.amount)

	for (measure, week_no), amount in totals.items():
		result.setdefault(measure, {})[week_no] = round(amount / CRORE, CRORE_DECIMALS)

	total: dict[int, float] = {}
	for measure in ("sales_bright", "sales_rolled", "sales_bo_traded", "sales_others"):
		for week_no, amount in result.get(measure, {}).items():
			total[week_no] = total.get(week_no, 0) + amount
	result["sales_total"] = {week_no: round(amount, CRORE_DECIMALS) for week_no, amount in total.items()}

	return result


def get_planning_engine_warehouses() -> list[str]:
	doc = frappe.get_single("Planning Engine Warehouse Setup")
	return [row.warehouse for row in doc.table_cmgr if row.warehouse]


INVENTORY_SKU_TYPES = ("BBMTA", "BBMTO", "RBMTA", "RBMTO", "BOTA", "BOTO", "PTA", "PTO")
MTA_SNAPSHOT = {"parent": "Item wise Daily On Hand Colour", "child": "On hand colour table"}
MTO_SNAPSHOT = {"parent": "Item wise Daily MTO SKU", "child": "MTO SKU Status Table"}

# Group headings add up the child SKU rows.
INVENTORY_GROUPS = {
	"inv_BRIGHT": ("inv_BBMTA", "inv_BBMTO"),
	"inv_ROLLED": ("inv_RBMTA", "inv_RBMTO"),
	"inv_BO": ("inv_BOTA", "inv_BOTO"),
	"inv_RM": ("inv_PTA", "inv_PTO"),
}


def get_inventory_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Inventory in tonnes per SKU type at each week's end, in Planning Engine warehouses.

	MTA (buffer) SKUs come from the Item wise Daily On Hand Colour snapshot and MTO
	(non-buffer) SKUs from the Item wise Daily MTO SKU doctype. An item's stock is its
	latest Stock Ledger balance on or before the week end, summed per SKU type and
	divided by 1000 (kg to tonnes). Weeks starting after today are left blank; the
	current week uses today.

	The Stock Ledger and both snapshot tables are each read once (not once per week) and
	walked forward together, since re-querying "balance/SKU as of this date" per week with
	a window function is what made this report slow (106 full-ledger scans for 53 weeks).
	"""
	result: dict[str, dict[int, float]] = {f"inv_{sku}": {} for sku in INVENTORY_SKU_TYPES}
	warehouses = get_planning_engine_warehouses()
	if not warehouses or not weeks:
		return result

	today = getdate(nowdate())
	weeks_in_range = sorted((w for w in weeks if w["from_date"] <= today), key=lambda w: w["to_date"])
	if not weeks_in_range:
		return result

	mta_by_date = get_snapshot_membership_by_date(MTA_SNAPSHOT, today)
	mto_by_date = get_snapshot_membership_by_date(MTO_SNAPSHOT, today)
	mta_dates = sorted(mta_by_date)
	mto_dates = sorted(mto_by_date)

	ledger_rows = frappe.db.sql(
		"""
		SELECT item_code, warehouse, posting_date, qty_after_transaction
		FROM `tabStock Ledger Entry`
		WHERE is_cancelled = 0 AND warehouse IN %(warehouses)s AND posting_date <= %(today)s
		ORDER BY posting_date, posting_time, creation
		""",
		{"warehouses": tuple(warehouses), "today": today},
		as_dict=True,
	)

	balances: dict[tuple[str, str], float] = {}
	idx = 0
	for week in weeks_in_range:
		as_of = min(week["to_date"], today)
		while idx < len(ledger_rows) and ledger_rows[idx].posting_date <= as_of:
			row = ledger_rows[idx]
			balances[(row.item_code, row.warehouse)] = flt(row.qty_after_transaction)
			idx += 1

		item_qty: dict[str, float] = {}
		for (item_code, _warehouse), qty in balances.items():
			item_qty[item_code] = item_qty.get(item_code, 0.0) + qty

		mta_map = mta_by_date.get(nearest_date_on_or_before(mta_dates, as_of), {})
		mto_map = mto_by_date.get(nearest_date_on_or_before(mto_dates, as_of), {})

		sku_totals: dict[str, float] = {}
		for item_code, qty in item_qty.items():
			sku = mta_map.get(item_code) or mto_map.get(item_code)
			if sku:
				sku_totals[sku] = sku_totals.get(sku, 0.0) + qty
		for sku, qty in sku_totals.items():
			result[f"inv_{sku}"][week["week_no"]] = round(qty / 1000, 2)

	for group, members in INVENTORY_GROUPS.items():
		group_values: dict[int, float] = {}
		for member in members:
			for week_no, value in result[member].items():
				group_values[week_no] = group_values.get(week_no, 0) + value
		result[group] = {week_no: round(value, 2) for week_no, value in group_values.items()}

	# Inventory = Bright + Rolled + BO + RM.
	total_values: dict[int, float] = {}
	for group in INVENTORY_GROUPS:
		for week_no, value in result[group].items():
			total_values[week_no] = total_values.get(week_no, 0) + value
	result["inv_TOTAL"] = {week_no: round(value, 2) for week_no, value in total_values.items()}

	return result


def get_snapshot_membership_by_date(snapshot: dict, today) -> dict:
	"""{date: {item_code: sku_type}} for every day in one snapshot doctype, up to today."""
	rows = frappe.db.sql(
		f"""
		SELECT p.posting_date AS posting_date, c.item_code AS item_code, c.sku_type AS sku_type
		FROM `tab{snapshot['parent']}` p
		INNER JOIN `tab{snapshot['child']}` c ON c.parent = p.name
		WHERE p.posting_date <= %(today)s AND c.sku_type IN %(skus)s
		ORDER BY p.posting_date
		""",
		{"today": today, "skus": INVENTORY_SKU_TYPES},
		as_dict=True,
	)
	by_date: dict = {}
	for row in rows:
		by_date.setdefault(getdate(row.posting_date), {})[row.item_code] = row.sku_type
	return by_date


def nearest_date_on_or_before(sorted_dates: list, target):
	"""The rightmost date in a sorted list that is <= target, or None."""
	idx = bisect_right(sorted_dates, target) - 1
	return sorted_dates[idx] if idx >= 0 else None


def get_sales_qty_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Sales Order qty per week split by item type, bucketed by the order's transaction date.

	Qty is in the item's stock UOM (Kg), summed then divided by 1000 for tonnes.

	Sales Qty Bright = BB, Sales Qty Rolled = RB, Sales Qty BO+Traded = BO or Traded.
	Any other item type isn't shown here (there's no "Sales Qty Others" row).
	"""
	result: dict[str, dict[int, float]] = {}
	if not weeks:
		return result

	rows = frappe.db.sql(
		"""
		SELECT so.transaction_date AS transaction_date, item.custom_item_type AS item_type, SUM(soi.qty) AS qty
		FROM `tabSales Order Item` soi
		INNER JOIN `tabSales Order` so ON so.name = soi.parent
		LEFT JOIN `tabItem` item ON item.name = soi.item_code
		WHERE so.docstatus = 1
			AND so.transaction_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY so.transaction_date, item.custom_item_type
		""",
		{"from_date": weeks[0]["from_date"], "to_date": weeks[-1]["to_date"]},
		as_dict=True,
	)

	measure_by_item_type = {"BB": "sales_qty_bright", "RB": "sales_qty_rolled"}

	totals: dict[tuple[str, int], float] = {}
	for row in rows:
		if row.item_type in measure_by_item_type:
			measure = measure_by_item_type[row.item_type]
		elif row.item_type in ("BO", "Traded"):
			measure = "sales_qty_bo_traded"
		else:
			continue
		week = next((w for w in weeks if w["from_date"] <= row.transaction_date <= w["to_date"]), None)
		if not week:
			continue
		key = (measure, week["week_no"])
		totals[key] = totals.get(key, 0) + flt(row.qty)

	for (measure, week_no), qty in totals.items():
		result.setdefault(measure, {})[week_no] = round(qty / 1000, 2)

	total: dict[int, float] = {}
	for measure in ("sales_qty_bright", "sales_qty_rolled", "sales_qty_bo_traded"):
		for week_no, qty in result.get(measure, {}).items():
			total[week_no] = total.get(week_no, 0) + qty
	result["sales_qty_total"] = {week_no: round(qty, 2) for week_no, qty in total.items()}

	return result


# Machine Name (as saved daily) -> the register's row key.
MACHINE_LOAD_KEYS = {
	"CDB - 16MM": "load_CDB_16MM",
	"CDB - 27MM": "load_CDB_27MM",
	"DB - 25MM": "load_DB_25MM",
	"DB - 40MM": "load_DB_40MM",
	"DB - 80MM": "load_DB_80MM",
	"DB - 100MM": "load_DB_100MM",
	"PL - 100MM": "load_PL_100MM",
}


def get_bright_machine_load_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Net Order Load (days) per Bright Machine at each week's end.

	Same pattern as the inventory rows: read the latest Item wise Daily Bright Machine
	Load saved on or before the week end. Weeks starting after today are left blank;
	the current week uses today.
	"""
	result: dict[str, dict[int, float]] = {key: {} for key in MACHINE_LOAD_KEYS.values()}
	if not weeks:
		return result

	today = getdate(nowdate())
	for week in weeks:
		if week["from_date"] > today:
			continue
		as_of = min(week["to_date"], today)
		snapshot_date = frappe.db.sql(
			"SELECT MAX(posting_date) FROM `tabItem wise Daily Bright Machine Load` WHERE posting_date <= %s",
			as_of,
		)[0][0]
		if not snapshot_date:
			continue

		rows = frappe.db.sql(
			"""
			SELECT c.machine_name AS machine_name, c.net_order_load AS net_order_load
			FROM `tabItem wise Daily Bright Machine Load` p
			INNER JOIN `tabBright Machine Load Status Table` c ON c.parent = p.name
			WHERE p.posting_date = %(snapshot_date)s
			""",
			{"snapshot_date": snapshot_date},
			as_dict=True,
		)
		for row in rows:
			key = MACHINE_LOAD_KEYS.get(row.machine_name)
			if key:
				result[key][week["week_no"]] = round(flt(row.net_order_load), 1)

	return result


def get_order_booking_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Sales Order Item amount per week split by item type, bucketed by the order's
	transaction date (the week it was booked in), same split as the Sales rows:
	Order Booking Bright = BB, Order Booking Rolled = RB, Order Booking BO+Traded = BO
	or Traded, Order Booking Others = any other item type (including none).
	"""
	result: dict[str, dict[int, float]] = {}
	if not weeks:
		return result

	rows = frappe.db.sql(
		"""
		SELECT so.transaction_date AS transaction_date, item.custom_item_type AS item_type, SUM(soi.amount) AS amount
		FROM `tabSales Order Item` soi
		INNER JOIN `tabSales Order` so ON so.name = soi.parent
		LEFT JOIN `tabItem` item ON item.name = soi.item_code
		WHERE so.docstatus = 1
			AND so.transaction_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY so.transaction_date, item.custom_item_type
		""",
		{"from_date": weeks[0]["from_date"], "to_date": weeks[-1]["to_date"]},
		as_dict=True,
	)

	def measure_for(item_type: str | None) -> str:
		if item_type == "BB":
			return "order_booking_bright"
		if item_type == "RB":
			return "order_booking_rolled"
		if item_type in ("BO", "Traded"):
			return "order_booking_bo_traded"
		return "order_booking_others"

	totals: dict[tuple[str, int], float] = {}
	for row in rows:
		week = next((w for w in weeks if w["from_date"] <= row.transaction_date <= w["to_date"]), None)
		if not week:
			continue
		key = (measure_for(row.item_type), week["week_no"])
		totals[key] = totals.get(key, 0) + flt(row.amount)

	for (measure, week_no), amount in totals.items():
		result.setdefault(measure, {})[week_no] = round(amount / CRORE, CRORE_DECIMALS)

	total: dict[int, float] = {}
	for measure in ("order_booking_bright", "order_booking_rolled", "order_booking_bo_traded", "order_booking_others"):
		for week_no, amount in result.get(measure, {}).items():
			total[week_no] = total.get(week_no, 0) + amount
	result["order_booking_total"] = {week_no: round(amount, CRORE_DECIMALS) for week_no, amount in total.items()}

	return result


def get_open_so_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Open SO qty per week split by item type, from the SO Recommendation Snapshot.

	Same pattern as Inventory: a point-in-time level, not a total, so each week uses the
	latest daily snapshot on or before the week end (today for the current week), not a
	sum across the week's 7 snapshots (that would count a still-open order repeatedly).
	Open SO Bright = BB, Open SO Rolled = RB, Open SO BO+Traded = BO or Traded,
	Open SO Others = any other item type (including none). Shown in crore, like the
	other money rows.
	"""
	result: dict[str, dict[int, float]] = {}
	if not weeks:
		return result

	def measure_for(item_type: str | None) -> str:
		if item_type == "BB":
			return "open_so_bright"
		if item_type == "RB":
			return "open_so_rolled"
		if item_type in ("BO", "Traded"):
			return "open_so_bo_traded"
		return "open_so_others"

	today = getdate(nowdate())
	for week in weeks:
		if week["from_date"] > today:
			continue
		as_of = min(week["to_date"], today)
		snapshot_date = frappe.db.sql(
			"SELECT MAX(snapshot_date) FROM `tabSO Recommendation Snapshot` WHERE snapshot_date <= %s AND status = 'Success'",
			as_of,
		)[0][0]
		if not snapshot_date:
			continue

		rows = frappe.db.sql(
			"""
			SELECT c.item_type AS item_type, SUM(c.amount) AS amount
			FROM `tabSO Recommendation Snapshot` p
			INNER JOIN `tabSO Recommendation Snapshot Item` c ON c.parent = p.name
			WHERE p.snapshot_date = %(snapshot_date)s AND p.status = 'Success'
			GROUP BY c.item_type
			""",
			{"snapshot_date": snapshot_date},
			as_dict=True,
		)
		for row in rows:
			measure = measure_for(row.item_type)
			result.setdefault(measure, {})[week["week_no"]] = (
				result.get(measure, {}).get(week["week_no"], 0) + flt(row.amount)
			)

	for key in list(result):
		result[key] = {week_no: round(amount / CRORE, CRORE_DECIMALS) for week_no, amount in result[key].items()}

	total: dict[int, float] = {}
	for measure in ("open_so_bright", "open_so_rolled", "open_so_bo_traded", "open_so_others"):
		for week_no, amount in result.get(measure, {}).items():
			total[week_no] = total.get(week_no, 0) + amount
	result["open_so_total"] = {week_no: round(amount, CRORE_DECIMALS) for week_no, amount in total.items()}

	return result


def get_pending_so_black_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Pending SO amount per week for BLACK-status lines, split by item type.

	Same source and point-in-time approach as Open Sales Orders (the latest daily
	SO Recommendation Snapshot on or before the week end), restricted to order_status
	= BLACK. Pending SO Black Bright = BB, Rolled = RB, BO+Traded = BO or Traded.
	There's no "Others" row here. Shown in crore.
	"""
	result: dict[str, dict[int, float]] = {}
	if not weeks:
		return result

	measure_by_item_type = {
		"BB": "pending_so_black_bright",
		"RB": "pending_so_black_rolled",
		"BO": "pending_so_black_bo_traded",
		"Traded": "pending_so_black_bo_traded",
	}

	today = getdate(nowdate())
	for week in weeks:
		if week["from_date"] > today:
			continue
		as_of = min(week["to_date"], today)
		snapshot_date = frappe.db.sql(
			"SELECT MAX(snapshot_date) FROM `tabSO Recommendation Snapshot` WHERE snapshot_date <= %s AND status = 'Success'",
			as_of,
		)[0][0]
		if not snapshot_date:
			continue

		rows = frappe.db.sql(
			"""
			SELECT c.item_type AS item_type, SUM(c.amount) AS amount
			FROM `tabSO Recommendation Snapshot` p
			INNER JOIN `tabSO Recommendation Snapshot Item` c ON c.parent = p.name
			WHERE p.snapshot_date = %(snapshot_date)s AND p.status = 'Success'
				AND c.order_status = 'BLACK'
			GROUP BY c.item_type
			""",
			{"snapshot_date": snapshot_date},
			as_dict=True,
		)
		for row in rows:
			measure = measure_by_item_type.get(row.item_type)
			if not measure:
				continue
			result.setdefault(measure, {})[week["week_no"]] = (
				result.get(measure, {}).get(week["week_no"], 0) + flt(row.amount)
			)

	for key in list(result):
		result[key] = {week_no: round(amount / CRORE, CRORE_DECIMALS) for week_no, amount in result[key].items()}

	total: dict[int, float] = {}
	for measure in ("pending_so_black_bright", "pending_so_black_rolled", "pending_so_black_bo_traded"):
		for week_no, amount in result.get(measure, {}).items():
			total[week_no] = total.get(week_no, 0) + amount
	result["pending_so_black_total"] = {week_no: round(amount, CRORE_DECIMALS) for week_no, amount in total.items()}

	return result


def get_fullkit_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Full-kit qty per week, from the SO Recommendation Snapshot.

	Same point-in-time approach as Open Sales Orders: the latest daily snapshot on or
	before the week end. Order Full-kit Qty sums qty where order_fullkit = 'Full-kit';
	Line Full-kit Qty sums qty where line_fullkit = 'Full-kit'.
	"""
	result: dict[str, dict[int, float]] = {}
	if not weeks:
		return result

	today = getdate(nowdate())
	for week in weeks:
		if week["from_date"] > today:
			continue
		as_of = min(week["to_date"], today)
		snapshot_date = frappe.db.sql(
			"SELECT MAX(snapshot_date) FROM `tabSO Recommendation Snapshot` WHERE snapshot_date <= %s AND status = 'Success'",
			as_of,
		)[0][0]
		if not snapshot_date:
			continue

		row = frappe.db.sql(
			"""
			SELECT
				SUM(CASE WHEN c.order_fullkit = 'Full-kit' THEN c.qty ELSE 0 END) AS order_fullkit_qty,
				SUM(CASE WHEN c.line_fullkit = 'Full-kit' THEN c.qty ELSE 0 END) AS line_fullkit_qty
			FROM `tabSO Recommendation Snapshot` p
			INNER JOIN `tabSO Recommendation Snapshot Item` c ON c.parent = p.name
			WHERE p.snapshot_date = %(snapshot_date)s AND p.status = 'Success'
			""",
			{"snapshot_date": snapshot_date},
			as_dict=True,
		)[0]
		result.setdefault("order_fullkit_qty", {})[week["week_no"]] = flt(row.order_fullkit_qty)
		result.setdefault("line_fullkit_qty", {})[week["week_no"]] = flt(row.line_fullkit_qty)

	# Qty is in Kg; the sheet's UoM for these rows is Tonnes.
	for key in list(result):
		result[key] = {week_no: round(qty / 1000, 2) for week_no, qty in result[key].items()}

	total: dict[int, float] = {}
	for measure in ("order_fullkit_qty", "line_fullkit_qty"):
		for week_no, qty in result.get(measure, {}).items():
			total[week_no] = total.get(week_no, 0) + qty
	result["fullkit_total"] = {week_no: round(qty, 2) for week_no, qty in total.items()}

	return result


# cs_type -> the register's key prefix for that type's rows.
CS_KEY_PREFIX = {"Bright": "bcs", "Rolled": "rcs"}


def get_cs_percent_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Bright/Rolled CS Availability and Black/Red/White % per week, averaged over each
	week's days.

	Same formula as the Category Wise Trend report (and the sku-type Availability rows):
	a day's % per colour is the colour count over the day's total of the five colours,
	and Availability is 100 - Black% - Red%. A week's value is the sum of its daily
	values divided by the number of days in the week (a day with no snapshot counts as 0).
	Days after today aren't counted, so the current week isn't diluted.
	"""
	result: dict[str, dict[int, float]] = {}
	if not weeks:
		return result

	rows = frappe.db.sql(
		"""
		SELECT p.posting_date AS posting_date, c.cs_type AS cs_type, c.on_hand_colour AS on_hand_colour
		FROM `tabItem wise Daily CS Colour` p
		INNER JOIN `tabCS Colour Status Table` c ON c.parent = p.name
		WHERE p.posting_date BETWEEN %(start)s AND %(end)s
		""",
		{"start": weeks[0]["from_date"], "end": weeks[-1]["to_date"]},
		as_dict=True,
	)

	colours_by_date: dict[tuple[str, date], list[str]] = {}
	for row in rows:
		if row.cs_type not in CS_KEY_PREFIX:
			continue
		colours_by_date.setdefault((row.cs_type, getdate(row.posting_date)), []).append(
			(row.on_hand_colour or "").strip().upper()
		)

	daily: dict[str, dict[date, float]] = {}
	for (cs_type, posting_date), colours in colours_by_date.items():
		counts = {colour: 0 for colour in SKU_COLOURS}
		for colour in colours:
			if colour in counts:
				counts[colour] += 1
		total = sum(counts.values())
		if not total:
			continue
		black = counts["BLACK"] / total * 100
		red = counts["RED"] / total * 100
		prefix = CS_KEY_PREFIX[cs_type]
		values = {
			f"{prefix}_availability": 100 - black - red,
			f"{prefix}_black": black,
			f"{prefix}_red": red,
			f"{prefix}_white": counts["WHITE"] / total * 100,
		}
		for key, value in values.items():
			daily.setdefault(key, {})[posting_date] = value

	today = getdate(nowdate())
	for key, by_date in daily.items():
		averages = {}
		for week in weeks:
			if week["from_date"] > today:
				continue
			days_so_far = (min(week["to_date"], today) - week["from_date"]).days + 1
			total = sum(v for d, v in by_date.items() if week["from_date"] <= d <= week["to_date"])
			averages[week["week_no"]] = round(total / days_so_far, 2)
		result[key] = averages

	return result


def get_rb_consumption_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""RB Consumption by Bright per week, bucketed by Production Date.

	Same two sources as the Rolled Bar Consumption for Bright report, unioned: Bright Bar
	Production entries, and Work Order Items on Work Orders flagged
	custom_bright_production. actual_rm_consumption is in Kg, summed then divided by 1000.
	"""
	result: dict[str, dict[int, float]] = {}
	if not weeks:
		return result

	rows = frappe.db.sql(
		"""
		select production_date, sum(actual_rm_consumption) as actual_rm_consumption
		from (
			select
				bbp.production_date as production_date,
				bbp.actual_rm_consumption as actual_rm_consumption
			from `tabBright Bar Production` bbp
			where bbp.docstatus = 1
				and bbp.production_date between %(from_date)s and %(to_date)s

			union all

			select
				date(wo.actual_start_date) as production_date,
				woi.consumed_qty as actual_rm_consumption
			from `tabWork Order Item` woi
			inner join `tabWork Order` wo on wo.name = woi.parent
			where wo.docstatus = 1
				and wo.custom_bright_production = 1
				and woi.consumed_qty > 0
				and date(wo.actual_start_date) between %(from_date)s and %(to_date)s
		) rm_consumption
		group by production_date
		""",
		{"from_date": weeks[0]["from_date"], "to_date": weeks[-1]["to_date"]},
		as_dict=True,
	)

	totals: dict[int, float] = {}
	for row in rows:
		if not row.production_date:
			continue
		week = next((w for w in weeks if w["from_date"] <= row.production_date <= w["to_date"]), None)
		if not week:
			continue
		totals[week["week_no"]] = totals.get(week["week_no"], 0) + flt(row.actual_rm_consumption)

	result["rb_consumption_by_bright"] = {week_no: round(qty / 1000, 2) for week_no, qty in totals.items()}
	return result


def get_production_qty_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Production Qty Bright/Rolled per week, from three sources, each in Kg summed then
	divided by 1000 for tonnes:

	- Work Order: produced_qty, dated by actual_start_date (a datetime - only its date
	  matters for the week). Goes to Bright or Rolled depending on the production item's
	  custom_item_type (BB or RB); anything else is not counted here.
	- Bright Bar Production: fg_weight, dated by production_date. The finished item here
	  is always BB, so every row goes to Production Qty Bright.
	- Finish Weight: finish_weight, dated by posting_date. Goes to Production Qty Rolled.
	"""
	result: dict[str, dict[int, float]] = {"production_qty_bright": {}, "production_qty_rolled": {}}
	if not weeks:
		return result

	from_date, to_date = weeks[0]["from_date"], weeks[-1]["to_date"]
	totals: dict[str, dict[int, float]] = {"production_qty_bright": {}, "production_qty_rolled": {}}

	def add(measure: str, event_date, qty) -> None:
		if not event_date:
			return
		week = next((w for w in weeks if w["from_date"] <= event_date <= w["to_date"]), None)
		if not week:
			return
		bucket = totals[measure]
		bucket[week["week_no"]] = bucket.get(week["week_no"], 0) + flt(qty)

	measure_by_item_type = {"BB": "production_qty_bright", "RB": "production_qty_rolled"}
	wo_rows = frappe.db.sql(
		"""
		SELECT DATE(wo.actual_start_date) AS event_date, wo.produced_qty AS qty, item.custom_item_type AS item_type
		FROM `tabWork Order` wo
		LEFT JOIN `tabItem` item ON item.name = wo.production_item
		WHERE wo.docstatus = 1
			AND DATE(wo.actual_start_date) BETWEEN %(from_date)s AND %(to_date)s
		""",
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	for row in wo_rows:
		measure = measure_by_item_type.get(row.item_type)
		if measure:
			add(measure, row.event_date, row.qty)

	bbp_rows = frappe.db.sql(
		"""
		SELECT production_date AS event_date, fg_weight AS qty
		FROM `tabBright Bar Production`
		WHERE docstatus = 1 AND production_date BETWEEN %(from_date)s AND %(to_date)s
		""",
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	for row in bbp_rows:
		add("production_qty_bright", row.event_date, row.qty)

	fw_rows = frappe.db.sql(
		"""
		SELECT posting_date AS event_date, finish_weight AS qty
		FROM `tabFinish Weight`
		WHERE docstatus = 1 AND posting_date BETWEEN %(from_date)s AND %(to_date)s
		""",
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	for row in fw_rows:
		add("production_qty_rolled", row.event_date, row.qty)

	for measure, by_week in totals.items():
		result[measure] = {week_no: round(qty / 1000, 2) for week_no, qty in by_week.items()}

	total: dict[int, float] = {}
	for measure in ("production_qty_bright", "production_qty_rolled"):
		for week_no, qty in result[measure].items():
			total[week_no] = total.get(week_no, 0) + qty
	result["production_qty_total"] = {week_no: round(qty, 2) for week_no, qty in total.items()}

	return result


def get_oe_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""OE (Operating Expense) per week, from the Profit and Loss Statement's Expenses,
	minus the Stock Expenses account group (Cost of Goods Sold, Stock Adjustment, etc. -
	those are TVC, not OE).

	Computed per calendar quarter of the fiscal year (not per week - OE is a financial
	period measure), then divided by 13 for a weekly figure, applied to every week in
	that quarter. Read straight from GL Entry using the Account tree's lft/rgt, rather
	than running the full P&L report.

	A quarter that hasn't fully ended yet has incomplete GL data, so it isn't computed
	on its own. The one currently in progress repeats the last fully-ended quarter's
	weekly value instead (blank if there's no completed quarter yet, e.g. early in the
	fiscal year); a quarter that hasn't started at all yet is left blank too, not
	carried forward - carrying a value into weeks that haven't happened yet would be
	misleading.
	"""
	result: dict[str, dict[int, float]] = {"oe": {}}
	if not weeks:
		return result

	company = frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		companies = frappe.get_all("Company", limit=1, pluck="name")
		company = companies[0] if companies else None
	if not company:
		return result

	expense_root = frappe.db.sql(
		"SELECT lft, rgt FROM `tabAccount` WHERE company = %s AND root_type = 'Expense' AND parent_account IS NULL LIMIT 1",
		company,
		as_dict=True,
	)
	if not expense_root:
		return result
	exp_lft, exp_rgt = expense_root[0].lft, expense_root[0].rgt

	stock_group = frappe.db.sql(
		"SELECT lft, rgt FROM `tabAccount` WHERE company = %s AND name LIKE 'Stock Expenses%%' LIMIT 1",
		company,
		as_dict=True,
	)
	stock_lft, stock_rgt = (stock_group[0].lft, stock_group[0].rgt) if stock_group else (None, None)

	fy_start, fy_end = weeks[0]["from_date"], weeks[-1]["to_date"]
	quarters = []
	q_start = fy_start
	while q_start <= fy_end:
		q_end = min(add_days(add_months(q_start, 3), -1), fy_end)
		quarters.append({"from_date": q_start, "to_date": q_end})
		q_start = add_days(q_end, 1)

	today = getdate(nowdate())
	last_completed_weekly_oe = None
	for quarter in quarters:
		if quarter["from_date"] > today:
			# Hasn't started yet - leave blank, don't carry a value into it.
			weekly_oe = None
		elif quarter["to_date"] >= today:
			# Currently in progress - borrow the last completed quarter's value.
			weekly_oe = last_completed_weekly_oe
		else:
			conditions = "acc.lft >= %(exp_lft)s AND acc.lft <= %(exp_rgt)s"
			params = {
				"exp_lft": exp_lft,
				"exp_rgt": exp_rgt,
				"company": company,
				"from_date": quarter["from_date"],
				"to_date": quarter["to_date"],
			}
			if stock_lft is not None:
				conditions += " AND NOT (acc.lft >= %(stock_lft)s AND acc.lft <= %(stock_rgt)s)"
				params["stock_lft"] = stock_lft
				params["stock_rgt"] = stock_rgt

			amount = frappe.db.sql(
				f"""
				SELECT SUM(gle.debit - gle.credit)
				FROM `tabGL Entry` gle
				INNER JOIN `tabAccount` acc ON acc.name = gle.account
				WHERE {conditions}
					AND gle.company = %(company)s
					AND gle.is_cancelled = 0
					AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
				""",
				params,
			)[0][0]

			weekly_oe = round(flt(amount) / CRORE / 13, CRORE_DECIMALS)
			last_completed_weekly_oe = weekly_oe

		if weekly_oe is None:
			continue
		for week in weeks:
			if quarter["from_date"] <= week["from_date"] <= quarter["to_date"]:
				result["oe"][week["week_no"]] = weekly_oe

	return result


OEE_FIELDS = (
	"bright_oee",
	"cdb_16mm", "oee_cdb_16mm_day", "oee_cdb_16mm_night",
	"cdb_27mm", "oee_cdb_27mm_day", "oee_cdb_27mm_night",
	"db_25mm", "oee_db_25mm_day", "oee_db_25mm_night",
	"db_40mm", "oee_db_40mm_day", "oee_db_40mm_night",
	"db_80mm", "oee_db_80mm_day", "oee_db_80mm_night",
	"db_100mm", "oee_db_100mm_day", "oee_db_100mm_night",
	"pl_100mm",
)


def get_oee_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Overall Equipment Effectiveness % per week, straight from the OEE doctype.

	One submitted OEE document is expected per week (its From Date/To Date define the
	week, per its autoname "{from_date} - {to_date}"), so each week just looks up the
	submitted document whose From Date matches the week's start.
	"""
	result: dict[str, dict[int, float]] = {field: {} for field in OEE_FIELDS}
	if not weeks:
		return result

	rows = frappe.get_all(
		"OEE",
		filters={
			"docstatus": 1,
			"from_date": ["between", [weeks[0]["from_date"], weeks[-1]["to_date"]]],
		},
		fields=["from_date", *OEE_FIELDS],
	)
	oee_by_from_date = {row.from_date: row for row in rows}

	for week in weeks:
		row = oee_by_from_date.get(week["from_date"])
		if not row:
			continue
		for field in OEE_FIELDS:
			value = row.get(field)
			if value is not None:
				result[field][week["week_no"]] = flt(value)

	return result


def get_production_qty_rolled_subcon_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Production Qty Rolled SubCon per week, bucketed by Subcontracting Receipt posting date.

	Only lines whose item is custom_item_type RB are counted; qty is in Kg, summed then
	divided by 1000 for tonnes.
	"""
	result: dict[str, dict[int, float]] = {"production_qty_rolled_subcon": {}}
	if not weeks:
		return result

	rows = frappe.db.sql(
		"""
		SELECT scr.posting_date AS posting_date, SUM(sci.qty) AS qty
		FROM `tabSubcontracting Receipt Item` sci
		INNER JOIN `tabSubcontracting Receipt` scr ON scr.name = sci.parent
		INNER JOIN `tabItem` item ON item.name = sci.item_code
		WHERE scr.docstatus = 1
			AND item.custom_item_type = 'RB'
			AND scr.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY scr.posting_date
		""",
		{"from_date": weeks[0]["from_date"], "to_date": weeks[-1]["to_date"]},
		as_dict=True,
	)

	totals: dict[int, float] = {}
	for row in rows:
		if not row.posting_date:
			continue
		week = next((w for w in weeks if w["from_date"] <= row.posting_date <= w["to_date"]), None)
		if not week:
			continue
		totals[week["week_no"]] = totals.get(week["week_no"], 0) + flt(row.qty)

	result["production_qty_rolled_subcon"] = {week_no: round(qty / 1000, 2) for week_no, qty in totals.items()}
	return result


FREE_STOCK_MEASURE_BY_PARENTFIELD = {
	"bright_free_stock": "free_stock_bright",
	"rolled_free_stock": "free_stock_rolled",
	"bo_free_stock": "free_stock_bo",
	"traded_free_stock": "free_stock_traded",
}


def get_free_stock_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Free Stock Bright/Rolled/BO/Traded per week, at each week's end.

	Same point-in-time approach as Inventory: a stock level, not a total, so each week
	uses the latest Item wise Daily Free Stock document on or before the week end (today
	for the current week). That document holds four child tables (one per type, covering
	both its MTA and MTO sku types together); free_stock is in Kg, summed per table and
	divided by 1000 for tonnes.
	"""
	result: dict[str, dict[int, float]] = {measure: {} for measure in FREE_STOCK_MEASURE_BY_PARENTFIELD.values()}
	if not weeks:
		return result

	today = getdate(nowdate())
	for week in weeks:
		if week["from_date"] > today:
			continue
		as_of = min(week["to_date"], today)
		doc_name = frappe.db.sql(
			"SELECT name FROM `tabItem wise Daily Free Stock` WHERE posting_date <= %s ORDER BY posting_date DESC LIMIT 1",
			as_of,
		)
		if not doc_name:
			continue
		rows = frappe.db.sql(
			"SELECT parentfield, SUM(free_stock) AS qty FROM `tabDaily Free Stock Item` WHERE parent = %s GROUP BY parentfield",
			doc_name[0][0],
			as_dict=True,
		)
		for row in rows:
			measure = FREE_STOCK_MEASURE_BY_PARENTFIELD.get(row.parentfield)
			if measure:
				result[measure][week["week_no"]] = round(flt(row.qty) / 1000, 2)

	return result


def get_otif_rows_for_period(from_date, to_date) -> list[dict]:
	"""Bright (BB) and Rolled (RB) Sales Order lines delivered in the period, with their OTIF.

	Same line logic as the OTIF report (line_otif), without the report's other columns,
	so the weekly register doesn't run the full report.
	"""
	delivered_qty_tolerance = flt(frappe.db.get_single_value("OTIF Settings", "delivered_qty_tolerance"))
	delivery_date_tolerance = cint(frappe.db.get_single_value("OTIF Settings", "delivery_date_tolerance"))

	return frappe.db.sql(
		"""
		SELECT
			soi.delivery_date AS delivery_date,
			i.custom_item_type AS item_type,
			(soi.qty * soi.rate) AS book_value,
			(
				SELECT COALESCE(SUM(sii.qty * sii.rate), 0)
				FROM `tabSales Invoice Item` sii
				INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
				WHERE sii.so_detail = soi.name AND si.docstatus = 1
			) AS sales_value,
			CASE
				WHEN (
					SELECT COALESCE(SUM(
						CASE
							WHEN si.is_return = 0 THEN
								CASE
									WHEN si.posting_date <= DATE_ADD(soi.delivery_date, INTERVAL %(delivery_date_tolerance)s DAY)
										THEN sii.qty
									ELSE 0
								END
							WHEN si.update_stock = 1 OR dn.is_return = 1 THEN sii.qty
							ELSE 0
						END
					), 0)
					FROM `tabSales Invoice Item` sii
					INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
					LEFT JOIN `tabDelivery Note` dn ON dn.name = sii.delivery_note
					WHERE sii.so_detail = soi.name AND si.docstatus = 1
				) >= soi.qty * (1 - %(delivered_qty_tolerance)s / 100) THEN 100
				ELSE 0
			END AS line_otif
		FROM `tabSales Order` so
		INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
		INNER JOIN `tabItem` i ON i.name = soi.item_code
		WHERE so.docstatus = 1
			AND i.custom_item_type IN ('BB', 'RB')
			AND soi.delivery_date BETWEEN %(from_date)s AND %(to_date)s
		""",
		{
			"from_date": from_date,
			"to_date": to_date,
			"delivered_qty_tolerance": delivered_qty_tolerance,
			"delivery_date_tolerance": delivery_date_tolerance,
		},
		as_dict=True,
	)


def get_otif_percent_by_week(weeks: list[dict]) -> dict[str, dict[int, float]]:
	"""Bright, Rolled and overall OTIF % per week, the same calculation as the OTIF page.

	Per item type (BB = Bright, RB = Rolled): sales value of lines delivered on time
	divided by book value of all lines, bucketed by delivery date. OTIF is the same
	ratio over Bright and Rolled lines together (summed data, not an average of the two %).
	"""
	result = {"bright_otif": {}, "rolled_otif": {}, "otif": {}}
	if not weeks:
		return result

	rows = get_otif_rows_for_period(weeks[0]["from_date"], weeks[-1]["to_date"])

	totals: dict[tuple[int, str], list[float]] = {}
	for row in rows:
		week = next((w for w in weeks if w["from_date"] <= row.delivery_date <= w["to_date"]), None)
		if not week:
			continue
		for item_type in (row.item_type, "ALL"):
			bucket = totals.setdefault((week["week_no"], item_type), [0.0, 0.0])
			bucket[0] += flt(row.book_value)
			if row.line_otif == 100:
				bucket[1] += flt(row.sales_value)

	measure_by_item_type = {"BB": "bright_otif", "RB": "rolled_otif", "ALL": "otif"}
	for (week_no, item_type), (book, line) in totals.items():
		if book:
			result[measure_by_item_type[item_type]][week_no] = round(line / book * 100, 2)

	return result


def get_invoice_totals_by_week(weeks: list[dict], doctype: str) -> dict[int, dict[str, float]]:
	"""Sum invoices of ``doctype`` per week, bucketed by Due Date, as of today.

	Read straight from the invoices (not the AR/AP report) so fully paid invoices
	are still counted.

	- invoiced: rounded_total of every submitted invoice due in the week.
	- paid: rounded_total - outstanding_amount - credit notes (returns) against the invoice.
	- overdue: outstanding_amount of those whose due date is before today.
	"""
	if not weeks:
		return {}

	today = getdate(nowdate())
	invoices = frappe.get_all(
		doctype,
		filters={
			"docstatus": 1,
			"is_return": 0,
			"posting_date": ["<=", today],
			"due_date": ["between", [weeks[0]["from_date"], weeks[-1]["to_date"]]],
		},
		fields=["name", "due_date", "rounded_total", "outstanding_amount"],
	)

	credit_notes = {}
	returns = frappe.get_all(
		doctype,
		filters={
			"docstatus": 1,
			"is_return": 1,
			"posting_date": ["<=", today],
			"return_against": ["is", "set"],
		},
		fields=["return_against", "rounded_total"],
	)
	for ret in returns:
		credit_notes[ret.return_against] = credit_notes.get(ret.return_against, 0) + abs(flt(ret.rounded_total))

	totals: dict[int, dict[str, float]] = {}
	for inv in invoices:
		week = next((w for w in weeks if w["from_date"] <= inv.due_date <= w["to_date"]), None)
		if not week:
			continue

		invoiced = flt(inv.rounded_total)
		outstanding = flt(inv.outstanding_amount)
		paid = invoiced - outstanding - credit_notes.get(inv.name, 0)

		week_totals = totals.setdefault(week["week_no"], {"invoiced": 0.0, "paid": 0.0, "overdue": 0.0})
		week_totals["invoiced"] += invoiced
		week_totals["paid"] += paid
		if inv.due_date < today:
			week_totals["overdue"] += outstanding

	return totals


def get_throughput_totals_by_week(weeks: list[dict]) -> dict[int, dict[str, float]]:
	"""Sum Throughput report Total T, Sales Value, TVC and T/Cu per week, bucketed by invoice date.

	T/Cu is Rolling T/Cu + Bright T/Cu, summed over the week's rows.
	"""
	if not weeks:
		return {}

	throughput_rows = get_throughput_rows(
		{
			"from_date": str(weeks[0]["from_date"]),
			"to_date": str(weeks[-1]["to_date"]),
		}
	)

	totals: dict[int, dict[str, float]] = {}
	for row in throughput_rows:
		invoice_date = row.get("invoice_date")
		if not invoice_date:
			continue
		for week in weeks:
			if week["from_date"] <= invoice_date <= week["to_date"]:
				week_totals = totals.setdefault(
					week["week_no"], {"total_t": 0.0, "sales_value": 0.0, "tvc": 0.0, "t_per_cu": 0.0}
				)
				week_totals["total_t"] += flt(row.get("total_t"))
				week_totals["sales_value"] += flt(row.get("sales_value"))
				week_totals["tvc"] += flt(row.get("tvc"))
				week_totals["t_per_cu"] += flt(row.get("rolling_t_per_cu")) + flt(row.get("bright_t_per_cu"))
				break

	return totals


def add_measure_rows(
	nodes: list[dict],
	parent: str | None,
	indent: int,
	data: list[dict],
	week_values: dict[str, dict[int, float]] | None = None,
) -> None:
	week_values = week_values or {}
	for node in nodes:
		children = node.get("children") or []
		row = {
			"business_measure": node["label"],
			"uom": node.get("uom") or "",
			"parent_measure": parent,
			"indent": indent,
			"is_group": bool(children),
		}
		for week_no, value in week_values.get(node.get("key"), {}).items():
			row[f"week_{week_no}"] = value
		data.append(row)
		if children:
			add_measure_rows(children, node["label"], indent + 1, data, week_values)
