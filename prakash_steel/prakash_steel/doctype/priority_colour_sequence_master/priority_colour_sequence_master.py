# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class PriorityColourSequenceMaster(Document):
	def validate(self):
		self.validate_table_rows()

	def validate_table_rows(self):
		priority_colours_seen = set()
		sequences_seen = set()

		for row in self.table_avyc or []:
			priority_colour = (row.priority_colour or "").strip()
			if priority_colour:
				if priority_colour in priority_colours_seen:
					frappe.throw(
						_("Priority Colour {0} cannot appear in more than one row.").format(
							frappe.bold(priority_colour)
						)
					)
				priority_colours_seen.add(priority_colour)

			if row.sequence is None:
				continue

			sequence = cint(row.sequence)
			if sequence == 0:
				frappe.throw(_("Sequence cannot be 0."))

			if sequence in sequences_seen:
				frappe.throw(
					_("Sequence {0} cannot appear in more than one row.").format(
						frappe.bold(sequence)
					)
				)
			sequences_seen.add(sequence)
