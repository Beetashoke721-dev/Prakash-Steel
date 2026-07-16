# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.xlsxutils import make_xlsx

from prakash_steel.utils.whitelist_permissions import require_permission

REPORT_NAME = "PSP Unsecured Loans and Transaction Report"
REF_DOCTYPE = "Unsecured Loans and Transaction"

FISCAL_MONTH_ORDER = [
	"April",
	"May",
	"June",
	"July",
	"August",
	"September",
	"October",
	"November",
	"December",
	"January",
	"February",
	"March",
]


def _run_report(filters: dict) -> list[dict]:
	from prakash_steel.prakash_steel.report.psp_unsecured_loans_and_transaction_report.psp_unsecured_loans_and_transaction_report import (
		execute,
	)

	_columns, data = execute(filters or {})
	return data or []


def _build_month_wise_summary(rows: list[dict]) -> list[dict]:
	"""Aggregate Interest Amount, TDS and Total Amount by month (fiscal-year order)."""
	totals: dict[str, dict] = {}

	for row in rows:
		if row.get("name") == "Total" or row.get("month") == "Total":
			continue

		month = row.get("month")
		if not month:
			continue

		if month not in totals:
			totals[month] = {
				"month": month,
				"interest_amount": 0.0,
				"tds_10": 0.0,
				"total_amount": 0.0,
			}

		totals[month]["interest_amount"] += float(row.get("interest_amount") or 0)
		totals[month]["tds_10"] += float(row.get("tds_10") or 0)
		totals[month]["total_amount"] += float(row.get("total_amount") or 0)

	def _entry(entry: dict) -> dict:
		return {
			"month": entry["month"],
			"interest_amount": round(entry["interest_amount"], 2),
			"tds_10": round(entry["tds_10"], 2),
			"total_amount": round(entry["total_amount"], 2),
		}

	summary = []
	for month in FISCAL_MONTH_ORDER:
		if month in totals:
			summary.append(_entry(totals[month]))

	# Append any unexpected month labels in discovery order
	for month, entry in totals.items():
		if month not in FISCAL_MONTH_ORDER:
			summary.append(_entry(entry))

	if summary:
		summary.append(
			{
				"month": "Total",
				"interest_amount": round(sum(r["interest_amount"] for r in summary), 2),
				"tds_10": round(sum(r["tds_10"] for r in summary), 2),
				"total_amount": round(sum(r["total_amount"] for r in summary), 2),
			}
		)

	return summary


@frappe.whitelist()
def get_month_wise_summary(financial_year=None, month=None, account_head=None):
	require_permission(REF_DOCTYPE, "read")

	if not financial_year or not account_head:
		frappe.throw("Financial Year and Account Head are required.")

	filters = {
		"financial_year": financial_year,
		"account_head": account_head,
	}
	if month:
		filters["month"] = month

	return _build_month_wise_summary(_run_report(filters))


@frappe.whitelist()
def export_month_wise_xlsx(financial_year=None, month=None, account_head=None):
	require_permission(REF_DOCTYPE, "read")
	data = get_month_wise_summary(
		financial_year=financial_year,
		month=month,
		account_head=account_head,
	)

	rows = [["Month", "Interest Amount", "TDS (10%)", "Total Amount"]]
	for r in data:
		rows.append(
			[
				r.get("month", ""),
				r.get("interest_amount", 0),
				r.get("tds_10", 0),
				r.get("total_amount", 0),
			]
		)

	xlsx_file = make_xlsx(rows, "Month-wise Summary")
	frappe.response["filename"] = "Unsecured Loans Month-wise Summary.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"


@frappe.whitelist()
def export_details_xlsx(financial_year=None, month=None, account_head=None):
	require_permission(REF_DOCTYPE, "read")

	if not financial_year or not account_head:
		frappe.throw("Financial Year and Account Head are required.")

	filters = {
		"financial_year": financial_year,
		"account_head": account_head,
	}
	if month:
		filters["month"] = month

	data = _run_report(filters)

	rows = [
		[
			"Month",
			"Date",
			"Account Head",
			"Interest % Per Annum",
			"Closing Balance",
			"Interest per Day",
			"Interest Amount",
			"TDS (10%)",
			"Total Amount",
			"Voucher",
		]
	]
	for r in data:
		detail_date = r.get("detail_date")
		if detail_date:
			parts = str(detail_date).split("-")
			detail_date = (
				f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else str(detail_date)
			)
		rows.append(
			[
				r.get("month") or "",
				detail_date or "",
				r.get("unsecured_loan") or "",
				r.get("interest_percent"),
				r.get("closing_balance"),
				r.get("day_interest"),
				r.get("interest_amount"),
				r.get("tds_10"),
				r.get("total_amount"),
				"" if r.get("name") == "Total" else (r.get("name") or ""),
			]
		)

	xlsx_file = make_xlsx(rows, "Transaction Details")
	frappe.response["filename"] = "Unsecured Loans and Transaction.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"
