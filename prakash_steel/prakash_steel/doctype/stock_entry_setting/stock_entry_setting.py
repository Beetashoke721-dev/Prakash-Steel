import frappe
from frappe.model.document import Document


class StockEntrySetting(Document):
	"""
	Single settings Doctype to control Prakash Steel auto Stock Entry logic.

	This file intentionally keeps logic minimal; the behavior is enforced in
	`prakash_steel.utils.work_order`.
	"""

	pass

