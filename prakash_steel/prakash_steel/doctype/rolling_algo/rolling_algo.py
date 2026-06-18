# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class RollingAlgo(Document):
	def before_save(self):
		self.update_final_sub_group_fields()

	def update_final_sub_group_fields(self):
		custom_shape = (self.shape or "").strip()

		sub_group_name = (
			(self.planning_sub_group_name if self.planning_sub_group else None)
			or self.item_sub_group
			or ""
		).strip()

		self.final_sub_group = sub_group_name
		self.final_sub_group_shape = (
			f"{sub_group_name}{custom_shape}" if sub_group_name or custom_shape else ""
		)
