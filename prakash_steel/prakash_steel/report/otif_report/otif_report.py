# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint, flt

WEEKDAY_INDEX = {
	"Monday": 0,
	"Tuesday": 1,
	"Wednesday": 2,
	"Thursday": 3,
	"Friday": 4,
	"Saturday": 5,
	"Sunday": 6,
}


def execute(filters=None) -> tuple[list, list]:
	filters = filters or {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"label": "Order Date",
			"fieldname": "order_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": "Customer Name",
			"fieldname": "customer_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": "Customer Group Name",
			"fieldname": "customer_group_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": "Item Code",
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 200,
		},
		{
			"label": "Item Name",
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": "Quantity Ordered",
			"fieldname": "qty_ordered",
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"label": "Payment Terms Label",
			"fieldname": "payment_terms_label",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": "CF.Lead Time",
			"fieldname": "lead_time",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": "CF.Special Condition",
			"fieldname": "special_condition",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": "Status",
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": "Delivery Date",
			"fieldname": "delivery_date",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"label": "SalesOrder Number",
			"fieldname": "sales_order_number",
			"fieldtype": "Link",
			"options": "Sales Order",
			"width": 170,
		},
		{
			"label": "Quantity Invoiced",
			"fieldname": "qty_invoiced",
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"label": "CF.Loading and Cutting",
			"fieldname": "loading_and_cutting",
			"fieldtype": "Data",
			"width": 170,
		},
		{
			"label": "Item Type",
			"fieldname": "item_type",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": "Week",
			"fieldname": "week",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": "Invoice Qty",
			"fieldname": "invoice_qty",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": "Pending Qty",
			"fieldname": "pending_qty",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": "Max Invoice Date",
			"fieldname": "max_invoice_date",
			"fieldtype": "Date",
			"width": 140,
		},
		{
			"label": "Line OTIF",
			"fieldname": "line_otif",
			"fieldtype": "Percent",
			"width": 110,
		},
		{
			"label": "Order OTIF",
			"fieldname": "order_otif",
			"fieldtype": "Percent",
			"width": 110,
		},
		{
			"label": "Booking Week",
			"fieldname": "booking_week",
			"fieldtype": "Data",
			"width": 120,
			"hidden":1,
		},
		{
			"label": "Book Value",
			"fieldname": "book_value",
			"fieldtype": "Currency",
			"width": 130,
			"hidden":1,
		},
		{
			"label": "Sell Value",
			"fieldname": "sales_value",
			"fieldtype": "Currency",
			"width": 130,
			"hidden":1,
		},
		{
			"label": "Line Percentage",
			"fieldname": "line_percentage",
			"fieldtype": "Percent",
			"width": 130,
			"hidden":1,
		},
		{
			"label": "Order Percentage",
			"fieldname": "order_percentage",
			"fieldtype": "Percent",
			"width": 130,
			"hidden":1,
		},
	]


def get_data(filters) -> list[dict]:
	conditions = ["so.docstatus = 1", "COALESCE(i.custom_item_type, '') != ''"]

	if filters.get("company"):
		conditions.append("so.company = %(company)s")

	# MultiSelectList filters arrive as lists (or a single string from saved/URL filters)
	for key, column in (("sales_order", "so.name"), ("status", "so.status")):
		values = filters.get(key)
		if values:
			filters[key] = [values] if isinstance(values, str) else list(values)
			conditions.append(f"{column} IN %({key})s")

	if filters.get("customer"):
		conditions.append("so.customer = %(customer)s")

	if filters.get("customer_group_name"):
		conditions.append("cust.custom_customer_group_name = %(customer_group_name)s")

	if filters.get("item_code"):
		conditions.append("soi.item_code = %(item_code)s")

	if filters.get("from_date"):
		conditions.append("soi.delivery_date >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append("soi.delivery_date <= %(to_date)s")

	# soi.delivered_qty only reflects stock movement (Delivery Note, or an invoice with
	# update_stock = 1). A line can be fully invoiced with update_stock = 0 (billed with
	# no stock-moving document) and delivered_qty stays 0 even though it was invoiced.
	# So when delivered_qty is 0, fall back to the net qty actually invoiced (real
	# returns still net off; a billing-only "return" that never moved stock does not).
	invoiced_qty_fallback = """(
		SELECT COALESCE(SUM(
			CASE
				WHEN si.is_return = 0 THEN sii.qty
				WHEN si.update_stock = 1 OR dn.is_return = 1 THEN sii.qty
				ELSE 0
			END
		), 0)
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		LEFT JOIN `tabDelivery Note` dn ON dn.name = sii.delivery_note
		WHERE sii.so_detail = soi.name
			AND si.docstatus = 1
	)"""
	effective_invoiced_qty = f"""(
		CASE WHEN soi.delivered_qty != 0 THEN soi.delivered_qty ELSE {invoiced_qty_fallback} END
	)"""

	query = f"""
		SELECT
			so.transaction_date AS order_date,
			so.customer AS customer,
			so.customer_name AS customer_name,
			COALESCE(NULLIF(cust.custom_customer_group_name, ''), '') AS customer_group_name,
			soi.name AS so_detail,
			soi.item_code,
			soi.item_name,
			soi.qty AS qty_ordered,
			so.payment_terms_template AS payment_terms_label,
			DATEDIFF(soi.delivery_date, so.transaction_date) AS lead_time,
			so.custom_special_condition AS special_condition,
			so.status AS status,
			soi.delivery_date AS delivery_date,
			so.name AS sales_order_number,
			{effective_invoiced_qty} AS qty_invoiced,
			so.custom_loading_and_cutting AS loading_and_cutting,
			i.custom_item_type AS item_type,
			{effective_invoiced_qty} AS invoice_qty,
			GREATEST(soi.qty - {effective_invoiced_qty}, 0) AS pending_qty,
			(
				-- Only actual delivering invoices count as "invoiced on"; a return/credit
				-- note is a reversal, not a delivery, so it never sets this date.
				SELECT MAX(si.posting_date)
				FROM `tabSales Invoice Item` sii
				INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
				WHERE sii.so_detail = soi.name
					AND si.docstatus = 1
					AND si.is_return = 0
			) AS max_invoice_date,
			CASE
				WHEN soi.delivery_date IS NULL THEN NULL
				WHEN (
					-- On-time delivered qty (within the date tolerance) minus any qty that
					-- was genuinely returned later (real stock return, regardless of when
					-- the return was posted). A billing-only credit note (update_stock = 0
					-- and not tied to a returning Delivery Note) is ignored either way.
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
					WHERE sii.so_detail = soi.name
						AND si.docstatus = 1
				) >= soi.qty * (1 - %(delivered_qty_tolerance)s / 100) THEN 100
				ELSE 0
			END AS line_otif,
			CASE
				WHEN EXISTS (
					SELECT 1
					FROM `tabSales Order Item` soi2
					WHERE soi2.parent = so.name
						AND (
							soi2.delivery_date IS NULL
							OR (
								SELECT COALESCE(SUM(
									CASE
										WHEN si2.is_return = 0 THEN
											CASE
												WHEN si2.posting_date <= DATE_ADD(soi2.delivery_date, INTERVAL %(delivery_date_tolerance)s DAY)
													THEN sii2.qty
												ELSE 0
											END
										WHEN si2.update_stock = 1 OR dn2.is_return = 1 THEN sii2.qty
										ELSE 0
									END
								), 0)
								FROM `tabSales Invoice Item` sii2
								INNER JOIN `tabSales Invoice` si2 ON si2.name = sii2.parent
								LEFT JOIN `tabDelivery Note` dn2 ON dn2.name = sii2.delivery_note
								WHERE sii2.so_detail = soi2.name
									AND si2.docstatus = 1
							) < soi2.qty * (1 - %(delivered_qty_tolerance)s / 100)
						)
				) THEN 0
				ELSE 100
			END AS order_otif,
			(soi.qty * soi.rate) AS book_value,
			(
				SELECT COALESCE(SUM(sii.qty * sii.rate), 0)
				FROM `tabSales Invoice Item` sii
				INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
				WHERE sii.so_detail = soi.name
					AND si.docstatus = 1
			) AS sales_value
		FROM `tabSales Order` so
		INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
		LEFT JOIN `tabCustomer` cust ON cust.name = so.customer
		LEFT JOIN `tabItem` i ON i.name = soi.item_code
		WHERE {" AND ".join(conditions)}
		ORDER BY so.transaction_date ASC, so.name ASC, soi.idx ASC
	"""

	settings = frappe.get_cached_doc("OTIF Settings")
	params = {
		**filters,
		"delivered_qty_tolerance": flt(settings.delivered_qty_tolerance),
		"delivery_date_tolerance": cint(settings.delivery_date_tolerance),
	}

	data = frappe.db.sql(query, params, as_dict=True)

	week_start_day = frappe.db.get_single_value("Calendar Settings", "week_start_day") or "Monday"
	fiscal_years = frappe.get_all(
		"Fiscal Year",
		fields=["year_start_date", "year_end_date"],
		order_by="year_start_date asc",
	)
	for row in data:
		row["week"] = get_week_label(row.get("delivery_date"), week_start_day, fiscal_years)
		row["booking_week"] = get_week_label(row.get("order_date"), week_start_day, fiscal_years)

	add_week_percentages(data)

	return data


def _week_totals(data: list[dict]) -> dict:
	# Per delivery week: book value of all lines, plus invoiced sales value of Line/Order-OTIF-100 lines.
	totals: dict = {}
	for row in data:
		bucket = totals.setdefault(row.get("week"), {"all": 0.0, "line": 0.0, "order": 0.0})
		value = float(row.get("book_value") or 0)
		sales_value = float(row.get("sales_value") or 0)
		bucket["all"] += value
		if row.get("line_otif") == 100:
			bucket["line"] += sales_value
		if row.get("order_otif") == 100:
			bucket["order"] += sales_value
	return totals


def add_week_percentages(data: list[dict]) -> None:
	totals = _week_totals(data)
	for row in data:
		bucket = totals[row.get("week")]
		total = bucket["all"]
		row["line_percentage"] = round(bucket["line"] / total * 100, 2) if total else 0
		row["order_percentage"] = round(bucket["order"] / total * 100, 2) if total else 0


@frappe.whitelist()
def get_week_breakdown(filters=None, week=None) -> dict:
	frappe.has_permission("Sales Order", "read", throw=True)
	filters = frappe.parse_json(filters) if filters else {}
	week = week or None

	rows = [r for r in get_data(filters) if r.get("week") == week]
	bucket = _week_totals(rows).get(week, {"all": 0.0, "line": 0.0, "order": 0.0})

	invoices: dict = {}
	so_details = [r["so_detail"] for r in rows if r.get("so_detail")]
	if so_details:
		for inv in frappe.db.sql(
			"""
			SELECT sii.so_detail, si.name AS invoice, si.posting_date, sii.qty, sii.rate,
				(sii.qty * sii.rate) AS value
			FROM `tabSales Invoice Item` sii
			INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
			WHERE sii.so_detail IN %(so_details)s AND si.docstatus = 1
			ORDER BY si.posting_date ASC, si.name ASC
			""",
			{"so_details": so_details},
			as_dict=True,
		):
			invoices.setdefault(inv["so_detail"], []).append(inv)

	return {
		"week": week,
		"rows": [
			{
				"invoices": invoices.get(r.get("so_detail"), []),
				"sales_order_number": r.get("sales_order_number"),
				"item_code": r.get("item_code"),
				"delivery_date": r.get("delivery_date"),
				"qty_ordered": r.get("qty_ordered"),
				"invoice_qty": r.get("invoice_qty"),
				"max_invoice_date": r.get("max_invoice_date"),
				"line_otif": r.get("line_otif"),
				"order_otif": r.get("order_otif"),
				"book_value": r.get("book_value"),
				"sales_value": r.get("sales_value"),
			}
			for r in rows
		],
		"book_total": bucket["all"],
		"line_sales_total": bucket["line"],
		"order_sales_total": bucket["order"],
		"line_percentage": rows[0]["line_percentage"] if rows else 0,
		"order_percentage": rows[0]["order_percentage"] if rows else 0,
	}


def get_week_label(delivery_date, week_start_day: str, fiscal_years: list[dict]) -> str | None:
	if not delivery_date:
		return None

	fy_start_date = _find_fiscal_year_start(delivery_date, fiscal_years)
	if not fy_start_date:
		return None

	# Week 1 runs from the fiscal year start date to the first configured
	# week-end day, so it (and the final week, cut off by fiscal year end)
	# may be shorter than a full week; every week in between is 7 days.
	offset = (fy_start_date.weekday() - WEEKDAY_INDEX[week_start_day]) % 7
	week_number = ((delivery_date - fy_start_date).days + offset) // 7 + 1

	return f"{week_number}-{fy_start_date.year % 100:02d}"


def _find_fiscal_year_start(delivery_date, fiscal_years: list[dict]):
	for fy in fiscal_years:
		if fy["year_start_date"] <= delivery_date <= fy["year_end_date"]:
			return fy["year_start_date"]
	return None
