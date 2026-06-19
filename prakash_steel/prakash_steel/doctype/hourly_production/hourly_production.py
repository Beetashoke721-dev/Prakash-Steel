# Copyright (c) 2025, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class HourlyProduction(Document):
	def validate(self) -> None:
		# Clear and make non-mandatory fields when miss_roll_pcs is empty or 0
		if not self.miss_roll_pcs or self.miss_roll_pcs <= 0:
			self.miss_roll_weight = None
			self.remarks_for_miss_roll = None
		
		# Clear and make non-mandatory fields when miss_ingot_pcs is empty or 0
		if not self.miss_ingot_pcs or self.miss_ingot_pcs <= 0:
			self.miss_ingot__billet_weight = None
			self.reason_for_miss_ingot__billet = None
