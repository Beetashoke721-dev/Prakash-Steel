# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class RollingSubgroupSetup(Document):
	def validate(self):
		self.validate_duplicate_subgroup_shape()

	def validate_duplicate_subgroup_shape(self):
		duplicate = frappe.db.exists(
			"Rolling Subgroup Setup",
			{
				"subgroup_name": self.subgroup_name,
				"shape": self.shape,
				"name": ["!=", self.name],
			},
		)
		if duplicate:
			frappe.throw(
				_("Another Rolling Subgroup Setup {0} already exists with the same Subgroup Name and Shape").format(
					frappe.bold(duplicate)
				)
			)
