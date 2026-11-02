# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AMC(Document):
	def validate(self):
		self.set_service_counts()

	def set_service_counts(self):
		availed = get_services_availed(self.name)
		self.services_availed = availed
		self.services_remaining = (self.total_services_available or 0) - availed


def get_services_availed(amc_no):
	if not amc_no:
		return 0
	return frappe.db.count(
		"AMC Service Visit",
		{"amc_no": amc_no, "docstatus": 1},
	)


def recalculate_amc_services(amc_no):
	"""Refresh services_availed / services_remaining on the AMC from its submitted visits."""
	if not amc_no:
		return

	total = frappe.db.get_value("AMC", amc_no, "total_services_available") or 0
	availed = get_services_availed(amc_no)

	frappe.db.set_value(
		"AMC",
		amc_no,
		{
			"services_availed": availed,
			"services_remaining": total - availed,
		},
	)
