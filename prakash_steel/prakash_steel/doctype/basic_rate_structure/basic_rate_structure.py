# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import flt


def payment_terms_surcharge(payment_terms):
	"""IF(C6=15, 0.5, IF(C6=30, 1, 0))"""
	if payment_terms == 15:
		return 0.5
	if payment_terms == 30:
		return 1.0
	return 0.0


class BasicRateStructure(Document):
	def validate(self):
		self.calculate_rates()

	def calculate_rates(self):
		# MS Round Basic Rate = billet_basic_ms + rolling_charges + payment terms surcharge
		self.ms_round_basic_rate = (
			flt(self.billet_basic_ms)
			+ flt(self.rolling_charges)
			+ payment_terms_surcharge(self.payment_terms)
		)

		# MS Square Rate = MS Round Basic Rate + MS Square
		self.ms_square_rate = flt(self.ms_round_basic_rate) + flt(self.ms_square)

		# C4 Round Rate = C4 Round + MS Round Basic Rate
		self.c4_round_rate = flt(self.c4_round) + flt(self.ms_round_basic_rate)

		# C4 Flat & Square Rate = C4 Flat & Square + C4 Round Rate
		self.c4_flat_square_rate = flt(self.c4_flat_square) + flt(self.c4_round_rate)

		# Bright Round C4 Rate = C4 Round Rate + Bright Round C4 Difference
		self.round_bright_c4_rate = flt(self.c4_round_rate) + flt(self.round_bright_c4_difference)

		# Bright Round Basic = Billet Basic MS + 8.5 + Bright Round Basic Difference
		self.bright_round_basic = (
			flt(self.billet_basic_ms) + 8.5 + flt(self.bright_round_basic_difference)
		)

		# Bright Flat Basic = Bright Round Basic + 5 + Bright Flat Basic Difference
		self.bright_flat_basic = (
			flt(self.bright_round_basic) + 5 + flt(self.bright_flat_basic_difference)
		)
