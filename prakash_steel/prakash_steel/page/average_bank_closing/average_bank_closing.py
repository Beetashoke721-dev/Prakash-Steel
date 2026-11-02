# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import calendar

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, today

from prakash_steel.prakash_steel.report.psp_unsecured_loans_and_transaction_report.psp_unsecured_loans_and_transaction_report import (
	_get_daily_balances,
)
from prakash_steel.utils.whitelist_permissions import require_permission

REF_DOCTYPE = "Account"


def _validate_dates(from_date, to_date):
	if not from_date or not to_date:
		frappe.throw(_("From Date and To Date are required."))

	start = getdate(from_date)
	end = getdate(to_date)
	if start > end:
		frappe.throw(_("From Date cannot be after To Date."))

	return start, end


def _require_bank_account(bank_account):
	if not bank_account:
		frappe.throw(_("Bank Account is required."))
	return bank_account


def _month_label(d) -> str:
	return f"{calendar.month_name[d.month]} {d.year}"


def _get_bank_accounts(bank_account=None) -> list[str]:
	"""Leaf Chart of Accounts entries with account_type Bank."""
	filters = {"account_type": "Bank", "is_group": 0, "disabled": 0}
	company = frappe.defaults.get_user_default("Company")
	if company:
		filters["company"] = company

	if bank_account:
		if not frappe.has_permission("Account", "read", bank_account):
			frappe.throw(
				_("Not permitted to access {0}.").format(bank_account),
				frappe.PermissionError,
			)
		meta = frappe.db.get_value(
			"Account", bank_account, ["account_type", "is_group", "disabled", "company"], as_dict=True
		)
		if not meta:
			frappe.throw(_("Account Head {0} does not exist.").format(bank_account))
		if meta.account_type != "Bank" or meta.is_group:
			frappe.throw(
				_("{0} is not a Bank Account in the Chart of Accounts.").format(bank_account)
			)
		if meta.disabled:
			frappe.throw(_("Account Head {0} is disabled.").format(bank_account))
		if company and meta.company and meta.company != company:
			frappe.throw(
				_("Account Head {0} does not belong to company {1}.").format(
					bank_account, company
				)
			)
		return [bank_account]

	return frappe.get_list("Account", filters=filters, pluck="name", order_by="name") or []


def _build_transaction_details(accounts: list[str], from_date, to_date) -> list[dict]:
	"""One row per date per bank account, with GL closing balance (same source as Unsecured Loans)."""
	loop_end = min(getdate(to_date), getdate(today()))
	loop_start = getdate(from_date)
	if loop_start > loop_end:
		return []

	rows = []
	for account in accounts:
		daily_balances = _get_daily_balances(account, loop_start, loop_end)
		current = loop_start
		while current <= loop_end:
			rows.append(
				{
					"detail_date": current,
					"account_head": account,
					"closing_balance": round(flt(daily_balances.get(str(current), 0.0)), 2),
				}
			)
			current = add_days(current, 1)

	rows.sort(key=lambda r: (getdate(r["detail_date"]), r["account_head"]))
	return _append_average_and_total(rows, "detail_date")


def _build_month_wise_summary(detail_rows: list[dict]) -> list[dict]:
	"""Average daily closing balance per month and account head."""
	buckets: dict[tuple, dict] = {}

	for row in detail_rows:
		if row.get("row_type") in ("Average", "Total"):
			continue
		d = getdate(row["detail_date"])
		key = (d.year, d.month, row["account_head"])
		if key not in buckets:
			buckets[key] = {
				"month": _month_label(d),
				"account_head": row["account_head"],
				"total": 0.0,
				"count": 0,
			}
		buckets[key]["total"] += flt(row.get("closing_balance"))
		buckets[key]["count"] += 1

	summary = []
	for key in sorted(buckets):
		entry = buckets[key]
		count = entry["count"] or 1
		summary.append(
			{
				"month": entry["month"],
				"account_head": entry["account_head"],
				"closing_balance": round(entry["total"] / count, 2),
			}
		)
	return summary


def _append_average_and_total(rows: list[dict], label_field: str) -> list[dict]:
	"""Append Total then Average footer rows for the Closing Balance column."""
	data_rows = [r for r in rows if r.get("row_type") not in ("Average", "Total")]
	if not data_rows:
		return data_rows

	balances = [flt(r.get("closing_balance")) for r in data_rows]
	total = round(sum(balances), 2)
	average = round(total / len(balances), 2)

	def _footer(label: str, value: float) -> dict:
		return {
			label_field: label,
			"account_head": "",
			"closing_balance": value,
			"row_type": label,
		}

	return data_rows + [_footer("Total", total), _footer("Average", average)]


@frappe.whitelist()
def get_transaction_details(from_date=None, to_date=None, bank_account=None):
	require_permission(REF_DOCTYPE, "read")
	require_permission("GL Entry", "read")
	_require_bank_account(bank_account)
	start, end = _validate_dates(from_date, to_date)
	accounts = _get_bank_accounts(bank_account)
	return _build_transaction_details(accounts, start, end)


@frappe.whitelist()
def get_month_wise_summary(from_date=None, to_date=None, bank_account=None):
	require_permission(REF_DOCTYPE, "read")
	require_permission("GL Entry", "read")
	_require_bank_account(bank_account)
	start, end = _validate_dates(from_date, to_date)
	accounts = _get_bank_accounts(bank_account)
	return _build_month_wise_summary(_build_transaction_details(accounts, start, end))
