# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

MACHINE_LOAD_COLOUR_CHAIN = ["Black", "Red", "Yellow", "Green", "White"]


class MachineLoadColourMaster(Document):
	def before_validate(self):
		self.normalize_colour_day_chain()

	def validate(self):
		self.validate_colour_day_chain()

	def _rows_by_colour(self):
		return {row.colour: row for row in (self.table_iobk or []) if row.colour}

	def normalize_colour_day_chain(self):
		rows_by_colour = self._rows_by_colour()

		black = rows_by_colour.get("Black")
		if black:
			black.from_days = 0
			black.to_days = 0

		white = rows_by_colour.get("White")
		if white:
			white.to_days = 0

		for prev_colour, colour in zip(MACHINE_LOAD_COLOUR_CHAIN, MACHINE_LOAD_COLOUR_CHAIN[1:]):
			row = rows_by_colour.get(colour)
			prev_row = rows_by_colour.get(prev_colour)
			if row and prev_row:
				row.from_days = cint(prev_row.to_days)

	def validate_colour_day_chain(self):
		rows_by_colour = self._rows_by_colour()

		for colour in MACHINE_LOAD_COLOUR_CHAIN:
			row = rows_by_colour.get(colour)
			if not row:
				continue

			if colour == "Black":
				if cint(row.from_days) != 0:
					frappe.throw(_("Black row From Days must be 0."))
				if cint(row.to_days) != 0:
					frappe.throw(_("Black row To Days must be 0."))
				continue

			if colour == "White":
				if cint(row.to_days) != 0:
					frappe.throw(_("White row To Days must be 0."))
				continue

			prev_colour = MACHINE_LOAD_COLOUR_CHAIN[
				MACHINE_LOAD_COLOUR_CHAIN.index(colour) - 1
			]
			prev_row = rows_by_colour.get(prev_colour)
			if not prev_row:
				continue

			expected_from = cint(prev_row.to_days)
			if cint(row.from_days) != expected_from:
				frappe.throw(
					_("{0} row From Days must be {1} (To Days of {2}).").format(
						colour,
						expected_from,
						prev_colour,
					)
				)
