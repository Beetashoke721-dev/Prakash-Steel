# Copyright (c) 2026, Prakash Steel and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def validate_no_income_accounts(doc, method=None) -> None:
	"""
	Block Journal Entry if any account head / ledger belongs under Income.
	"""
	accounts = doc.get("accounts") or []
	if not accounts:
		return

	account_names = list({row.account for row in accounts if row.account})
	if not account_names:
		return

	income_accounts = set(
		frappe.get_all(
			"Account",
			filters={"name": ["in", account_names], "root_type": "Income"},
			pluck="name",
		)
		or []
	)
	if not income_accounts:
		return

	errors = []
	for row in accounts:
		if row.account and row.account in income_accounts:
			errors.append(
				_("Row {0}: Account {1} is under Income and cannot be used in Journal Entry.").format(
					row.idx, frappe.bold(row.account)
				)
			)

	if errors:
		frappe.throw(
			"<br>".join(errors),
			title=_("Income Account Not Allowed"),
		)
