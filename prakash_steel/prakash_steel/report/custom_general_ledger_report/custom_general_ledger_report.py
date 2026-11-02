# Copyright (c) 2026, Prakash Steel and contributors
# For license information, please see license.txt
#
# Same as ERPNext General Ledger, with TDS GL lines included when filtering by party
# (standard GL omits them because TDS payable entries usually have no party)
# and an extra "TDS Division" column (Tax Withholding Section / category).

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from erpnext import get_default_company
from erpnext.accounts.report.general_ledger import general_ledger as gl
from erpnext.accounts.report.general_ledger.general_ledger import (
	get_balance,
	get_columns as erpnext_get_columns,
)
from erpnext.accounts.report.general_ledger.general_ledger import (
	get_conditions as erpnext_get_conditions,
)
from frappe.utils import cstr, flt


def execute(filters: dict[str, Any] | None = None):
	filters = frappe._dict(filters or {})
	_apply_default_filters(filters)
	_resolve_party_name_filter(filters)

	original_get_conditions = gl.get_conditions
	original_get_columns = gl.get_columns

	gl.get_conditions = _get_conditions_with_tds
	gl.get_columns = _get_columns_with_tds_division
	try:
		columns, data = gl.execute(filters)
	finally:
		gl.get_conditions = original_get_conditions
		gl.get_columns = original_get_columns

	_enrich_tds_division(data)
	_offset_tds_rows_against_party_rows(data)
	_recalculate_balances(data)
	return columns, data


def _offset_tds_rows_against_party_rows(data: list) -> None:
	"""Present TDS/TCS lines next to the party's own row without changing the
	party balance standard GL would show for the voucher.

	TDS lines have no party of their own (that's why the standard GL report omits
	them); they are only in this data set because they share a voucher (or
	"against") with the filtered party's row, so listing them raw would count the
	tax a second time. Per voucher, each TDS line is moved to the other side and
	the party row(s) are adjusted by the same amount so the voucher still nets to
	its GL party amount:

	- TDS opposite the party (payment PE/JE, TCS on Sales Invoice): move TDS onto
	  the party side and shrink the party row, e.g. Creditors Dr 50,00,000 +
	  TDS Cr 5,000 -> Creditors Dr 49,95,000 + TDS Dr 5,000 (party row = amount
	  actually paid, e.g. Payment Entry paid_amount).
	- TDS on the party side (TDS deducted on Purchase Invoice / expense JE, where
	  the party row is already net): move TDS opposite and gross up the party row,
	  e.g. Creditors Cr 17,13,028 + TDS Cr 1,453 -> Creditors Cr 17,14,481 +
	  TDS Dr 1,453 (party row = invoice gross).
	"""
	if not data:
		return

	party_side: dict[tuple[str, str], str] = {}
	party_rows: dict[tuple[str, str], list[dict]] = {}
	for row in data:
		if not row.get("party") or _is_summary_row(row):
			continue

		key = (row.get("voucher_type"), row.get("voucher_no"))
		if key not in party_side:
			if flt(row.get("debit")):
				party_side[key] = "debit"
			elif flt(row.get("credit")):
				party_side[key] = "credit"
		if key in party_side:
			party_rows.setdefault(key, []).append(row)

	party_delta: dict[tuple[str, str], float] = {}
	orphan_ids: set[int] = set()
	for row in data:
		if row.get("party") or _is_summary_row(row):
			continue

		key = (row.get("voucher_type"), row.get("voucher_no"))
		side = party_side.get(key)
		if not side:
			# Matched only via "against" (e.g. same name as a Customer of a Sales Invoice
			# while filtering Supplier): nothing of this party's to offset, so drop it.
			if key[1]:
				orphan_ids.add(id(row))
			continue

		other_side = "credit" if side == "debit" else "debit"
		if flt(row.get(other_side)):
			amount = flt(row.get(other_side))
			_swap_dr_cr(row, to_field=side)
			party_delta[key] = party_delta.get(key, 0.0) - amount
		elif flt(row.get(side)):
			amount = flt(row.get(side))
			_swap_dr_cr(row, to_field=other_side)
			party_delta[key] = party_delta.get(key, 0.0) + amount

	for key, delta in party_delta.items():
		_adjust_party_rows(party_rows.get(key), party_side[key], delta)

	if orphan_ids:
		data[:] = [row for row in data if id(row) not in orphan_ids]


def _adjust_party_rows(rows: list[dict] | None, field: str, delta: float) -> None:
	"""Spread `delta` over the party rows' `field` in proportion to their amounts."""
	if not rows or not delta:
		return

	total = sum(flt(row.get(field)) for row in rows)
	if total <= 0:
		return

	if delta < 0:
		delta = max(delta, -total)

	currency_field = f"{field}_in_account_currency"
	for row in rows:
		amount = flt(row.get(field))
		if not amount:
			continue
		new_amount = amount + amount * (delta / total)
		_scale_account_currency_amount(row, field, currency_field, new_amount)
		row[field] = new_amount


def _swap_dr_cr(row: dict, to_field: str) -> None:
	"""Move a row's amount (and account-currency amount) onto `to_field`, zeroing the other side."""
	from_field = "credit" if to_field == "debit" else "debit"

	row[to_field] = flt(row.get(from_field))
	row[from_field] = 0.0

	from_currency_field = f"{from_field}_in_account_currency"
	to_currency_field = f"{to_field}_in_account_currency"
	if row.get(from_currency_field) is not None:
		row[to_currency_field] = flt(row.get(from_currency_field))
		row[from_currency_field] = 0.0


def _scale_account_currency_amount(
	row: dict, company_field: str, account_field: str, new_company_amount: float
) -> None:
	old_company = flt(row.get(company_field))
	if not old_company or row.get(account_field) is None:
		return
	old_account = flt(row.get(account_field))
	if abs(old_company - old_account) < 0.005:
		row[account_field] = new_company_amount
	else:
		row[account_field] = old_account * (new_company_amount / old_company)


def _is_summary_row(row: dict) -> bool:
	account = cstr(row.get("account") or "").strip("'")
	if not account:
		return not row.get("posting_date") and not row.get("voucher_no")
	return account.startswith(("Opening", "Total", "Closing"))


def _recalculate_balances(data: list) -> None:
	"""Rebuild running balance and Total/Closing after TDS row adjustments."""
	if not data:
		return

	balance = 0.0
	opening_debit = opening_credit = 0.0
	period_debit = period_credit = 0.0
	total_row = closing_row = None

	for row in data:
		if _is_summary_row(row):
			account = cstr(row.get("account") or "").strip("'")
			if account.startswith("Opening"):
				balance = get_balance(row, 0.0, "debit", "credit")
				row["balance"] = balance
				opening_debit = flt(row.get("debit"))
				opening_credit = flt(row.get("credit"))
			elif account.startswith("Closing"):
				closing_row = row
			elif account.startswith("Total"):
				total_row = row
			continue

		if not row.get("posting_date") and not row.get("voucher_no"):
			continue

		balance = get_balance(row, balance, "debit", "credit")
		row["balance"] = balance
		period_debit += flt(row.get("debit"))
		period_credit += flt(row.get("credit"))

	if total_row is not None:
		total_row["debit"] = period_debit
		total_row["credit"] = period_credit
		total_row["balance"] = get_balance(total_row, 0.0, "debit", "credit")

	if closing_row is not None:
		closing_row["debit"] = opening_debit + period_debit
		closing_row["credit"] = opening_credit + period_credit
		closing_row["balance"] = get_balance(closing_row, 0.0, "debit", "credit")


def _apply_default_filters(filters: frappe._dict) -> None:
	"""Hidden defaults required by General Ledger after UI filters were simplified."""
	if not filters.get("company"):
		filters.company = frappe.defaults.get_user_default("Company") or get_default_company()
	if not filters.get("company"):
		frappe.throw(_("Set a default Company in User Defaults to run this report."))

	filters.setdefault("include_default_book_entries", 1)
	filters.setdefault("include_dimensions", 0)
	if filters.get("account") and isinstance(filters.account, str):
		filters.account = frappe.parse_json(filters.account)
	if filters.get("party_name") and isinstance(filters.party_name, str):
		filters.party_name = frappe.parse_json(filters.party_name)


def _resolve_party_name_filter(filters: frappe._dict) -> None:
	"""Map Party Name selections (value = PartyType::Party or party id) onto GL party filters."""
	selected_party_type = filters.get("party_type")

	party_names = filters.get("party_name") or []
	if isinstance(party_names, str):
		party_names = frappe.parse_json(party_names) or []
	if not party_names:
		return

	parties: list[str] = []
	party_types: set[str] = set()
	for value in party_names:
		if "::" in value:
			party_type, party = value.split("::", 1)
		else:
			party_type, party = _guess_party(value, preferred_type=selected_party_type)
		if not party_type or not party:
			continue
		if selected_party_type and party_type != selected_party_type:
			continue
		parties.append(party)
		party_types.add(party_type)

	if not parties:
		return

	filters.party = parties
	if selected_party_type:
		filters.party_type = selected_party_type
	elif len(party_types) == 1:
		filters.party_type = next(iter(party_types))
	else:
		filters.party_type = None


def _guess_party(
	name_or_id: str, preferred_type: str | None = None
) -> tuple[str | None, str | None]:
	candidates = [preferred_type] if preferred_type else ["Supplier", "Customer"]
	# Keep other common types as fallback when no preferred type.
	for party_type in candidates + [t for t in ("Supplier", "Customer", "Employee") if t not in candidates]:
		if not frappe.db.exists("DocType", party_type):
			continue
		if frappe.db.exists(party_type, name_or_id):
			return party_type, name_or_id

		name_field = {
			"Supplier": "supplier_name",
			"Customer": "customer_name",
			"Employee": "employee_name",
		}.get(party_type)
		if name_field and frappe.db.has_column(party_type, name_field):
			party = frappe.db.get_value(party_type, {name_field: name_or_id}, "name")
			if party:
				return party_type, party

	return None, None


@frappe.whitelist()
def get_party_name_options(txt: str | None = None, party_type: str | None = None) -> list[dict[str, str]]:
	"""Options for Party Name MultiSelectList, optionally scoped by Party Type."""
	txt = (txt or "").strip()
	like = f"%{txt}%"
	limit = 20
	options: list[dict[str, str]] = []

	party_types = [party_type] if party_type else ["Supplier", "Customer"]
	name_fields = {
		"Supplier": "supplier_name",
		"Customer": "customer_name",
		"Employee": "employee_name",
	}

	for pt in party_types:
		if not frappe.db.exists("DocType", pt):
			continue

		name_field = name_fields.get(pt)
		fields = ["name"]
		if name_field and frappe.db.has_column(pt, name_field):
			fields.append(name_field)

		kwargs: dict[str, Any] = {
			"fields": fields,
			"limit_page_length": limit,
			"order_by": f"{name_field} asc" if name_field and name_field in fields else "name asc",
		}
		if txt:
			or_filters = [["name", "like", like]]
			if name_field and name_field in fields:
				or_filters.append([name_field, "like", like])
			kwargs["or_filters"] = or_filters

		for row in frappe.get_all(pt, **kwargs):
			label = (row.get(name_field) if name_field else None) or row.name
			options.append(
				{
					"value": f"{pt}::{row.name}",
					"description": f"{label} ({_(pt)})",
				}
			)

	return options[:limit]


def _get_tds_accounts(company: str | None) -> list[str]:
	"""Accounts used for tax withholding / TDS (and name matches as fallback)."""
	accounts: set[str] = set()

	if frappe.db.has_column("Account", "is_tax_withholding_account"):
		filters: dict[str, Any] = {"is_tax_withholding_account": 1}
		if company:
			filters["company"] = company
		accounts.update(frappe.get_all("Account", filters=filters, pluck="name") or [])

	if frappe.db.exists("DocType", "Tax Withholding Account"):
		twa_filters: dict[str, Any] = {}
		if company:
			twa_filters["company"] = company
		accounts.update(
			frappe.get_all("Tax Withholding Account", filters=twa_filters, pluck="account") or []
		)

	like_filters: dict[str, Any] = {"name": ["like", "%TDS%"]}
	if company:
		like_filters["company"] = company
	accounts.update(frappe.get_all("Account", filters=like_filters, pluck="name") or [])

	# Also match TCS accounts by name.
	tcs_filters: dict[str, Any] = {"name": ["like", "%TCS%"]}
	if company:
		tcs_filters["company"] = company
	accounts.update(frappe.get_all("Account", filters=tcs_filters, pluck="name") or [])

	return sorted(a for a in accounts if a)


def _party_voucher_subquery() -> str:
	return """
		SELECT DISTINCT voucher_no
		FROM `tabGL Entry`
		WHERE company = %(company)s
			AND IFNULL(is_cancelled, 0) = 0
			AND party in %(party)s
	"""


def _get_conditions_with_tds(filters):
	"""Extend standard GL conditions so party filter also pulls related TDS lines."""
	conditions = erpnext_get_conditions(filters)

	if not filters.get("party"):
		return conditions

	tds_accounts = _get_tds_accounts(filters.get("company"))
	# Placeholder so SQL `IN` never receives an empty list.
	filters["tds_accounts"] = tds_accounts or ["__no_tds_account__"]

	party_names = _get_party_display_names(filters.get("party_type"), filters.get("party"))
	filters["party_against_names"] = party_names or ["__no_party_name__"]

	voucher_sq = _party_voucher_subquery()
	# TDS lines are only pulled in for the period itself: there they get flipped onto the
	# party side (net zero vs. the party row), but the Opening row is a raw SQL aggregate
	# that can't be flipped, so earlier TDS credits would inflate it vs. standard GL.
	party_or_tds = f"""(
		party in %(party)s
		OR (
			account in %(tds_accounts)s
			AND posting_date >= %(from_date)s
			AND voucher_no in ({voucher_sq})
		)
		OR (
			account in %(tds_accounts)s
			AND posting_date >= %(from_date)s
			AND (
				against in %(party)s
				OR against in %(party_against_names)s
			)
		)
	)"""

	if "party in %(party)s" in conditions:
		conditions = conditions.replace("party in %(party)s", party_or_tds)
	else:
		conditions = f"{conditions} and {party_or_tds}" if conditions else f"and {party_or_tds}"

	# TDS payable lines usually have blank party_type; relax when party_type is filtered.
	if filters.get("party_type") and "party_type=%(party_type)s" in conditions:
		party_type_or_tds = f"""(
			party_type=%(party_type)s
			OR (
				account in %(tds_accounts)s
				AND (
					voucher_no in ({voucher_sq})
					OR against in %(party)s
					OR against in %(party_against_names)s
				)
			)
		)"""
		conditions = conditions.replace("party_type=%(party_type)s", party_type_or_tds)

	return conditions


def _get_columns_with_tds_division(filters):
	columns = erpnext_get_columns(filters)
	insert_at = len(columns)
	for i, col in enumerate(columns):
		if col.get("fieldname") == "party":
			insert_at = i + 1
		if col.get("fieldname") == "party_name":
			insert_at = i + 1

	columns.insert(
		insert_at,
		{
			"label": _("TDS Division"),
			"fieldname": "tds_division",
			"fieldtype": "Data",
			"width": 180,
		},
	)
	return columns


def _get_party_display_names(party_type: str | None, parties: list[str] | None) -> list[str]:
	if not parties:
		return []

	names = set(parties)
	types = [party_type] if party_type else ["Supplier", "Customer"]

	if "Supplier" in types:
		for row in frappe.get_all(
			"Supplier", filters={"name": ["in", parties]}, fields=["name", "supplier_name"]
		):
			if row.supplier_name:
				names.add(row.supplier_name)
	if "Customer" in types:
		for row in frappe.get_all(
			"Customer", filters={"name": ["in", parties]}, fields=["name", "customer_name"]
		):
			if row.customer_name:
				names.add(row.customer_name)

	return sorted(names)


def _enrich_tds_division(data: list) -> None:
	"""Fill tds_division from Tax Withholding Category section / category / TDS account."""
	if not data:
		return

	vouchers_by_type: dict[str, set[str]] = {}
	for row in data:
		vt, vn = row.get("voucher_type"), row.get("voucher_no")
		if vt and vn and not str(vn).startswith("'"):
			vouchers_by_type.setdefault(vt, set()).add(vn)

	category_by_voucher = _get_tax_withholding_category_by_voucher(vouchers_by_type)
	categories = {c for c in category_by_voucher.values() if c}
	section_map: dict[str, str] = {}
	if categories:
		for row in frappe.get_all(
			"Tax Withholding Category",
			filters={"name": ["in", list(categories)]},
			fields=["name", "tds_section"],
		):
			section_map[row.name] = row.tds_section or row.name

	for row in data:
		key = (row.get("voucher_type"), row.get("voucher_no"))
		category = category_by_voucher.get(key)
		if category:
			row["tds_division"] = section_map.get(category) or category
			continue

		account = row.get("account") or ""
		if "TDS" in account.upper() or "TCS" in account.upper():
			row["tds_division"] = account.rsplit(" - ", 1)[0] if " - " in account else account


def _get_tax_withholding_category_by_voucher(
	vouchers_by_type: dict[str, set[str]],
) -> dict[tuple[str, str], str | None]:
	mapping: dict[tuple[str, str], str | None] = {}

	pe_names = list(vouchers_by_type.get("Payment Entry") or [])
	if pe_names:
		for pe in frappe.get_all(
			"Payment Entry",
			filters={"name": ["in", pe_names]},
			fields=["name", "tax_withholding_category", "party", "party_type"],
		):
			cat = pe.tax_withholding_category
			if not cat and pe.party_type == "Supplier" and pe.party:
				cat = frappe.db.get_value("Supplier", pe.party, "tax_withholding_category")
			mapping[("Payment Entry", pe.name)] = cat

	je_names = list(vouchers_by_type.get("Journal Entry") or [])
	if je_names:
		for je in frappe.get_all(
			"Journal Entry",
			filters={"name": ["in", je_names]},
			fields=["name", "tax_withholding_category"],
		):
			mapping[("Journal Entry", je.name)] = je.tax_withholding_category

	pi_names = list(vouchers_by_type.get("Purchase Invoice") or [])
	if pi_names:
		for pi in frappe.get_all(
			"Purchase Invoice",
			filters={"name": ["in", pi_names]},
			fields=["name", "supplier"],
		):
			cat = None
			if pi.supplier:
				cat = frappe.db.get_value("Supplier", pi.supplier, "tax_withholding_category")
			mapping[("Purchase Invoice", pi.name)] = cat

	si_names = list(vouchers_by_type.get("Sales Invoice") or [])
	if si_names:
		for si in frappe.get_all(
			"Sales Invoice",
			filters={"name": ["in", si_names]},
			fields=["name", "customer"],
		):
			cat = None
			if si.customer and frappe.db.has_column("Customer", "tax_withholding_category"):
				cat = frappe.db.get_value("Customer", si.customer, "tax_withholding_category")
			mapping[("Sales Invoice", si.name)] = cat

	return mapping
