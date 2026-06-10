# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BrightMachineMaster(Document):
	def validate(self):
		self.validate_is_default()
		self.validate_unique_machine_groups()

	def validate_unique_machine_groups(self):
		seen = set()
		for row in self.machine_details or []:
			machine_group = (row.machine_group_name or "").strip()
			if not machine_group:
				continue
			if machine_group in seen:
				frappe.throw(
					_("Machine Group Name {0} cannot appear in more than one row.").format(
						frappe.bold(machine_group)
					)
				)
			seen.add(machine_group)

	def validate_is_default(self):
		rows = self.machine_details or []
		if not rows:
			return
		default_rows = [row for row in rows if row.is_default]

		if len(default_rows) != 1:
			frappe.throw(
				_("Please mark exactly one row in Machine Details as Default (Is Default).")
			)
