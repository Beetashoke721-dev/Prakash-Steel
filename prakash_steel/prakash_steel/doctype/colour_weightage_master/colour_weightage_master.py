# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class ColourWeightageMaster(Document):
	def validate(self) -> None:
		self.validate_table_rows()

	def validate_table_rows(self):
		colours_seen = set()
		weightages_seen = set()

		for row in self.table_zdau or []:
			colour = (row.colour or "").strip()
			if colour:
				if colour in colours_seen:
					frappe.throw(
						_("Colour {0} cannot appear in more than one row.").format(
							frappe.bold(colour)
						)
					)
				colours_seen.add(colour)

			if row.weightage is None:
				continue

			weightage = cint(row.weightage)
			if weightage == 0:
				frappe.throw(_("Weightage cannot be 0."))

			if weightage in weightages_seen:
				frappe.throw(
					_("Weightage {0} cannot appear in more than one row.").format(
						frappe.bold(weightage)
					)
				)
			weightages_seen.add(weightage)
