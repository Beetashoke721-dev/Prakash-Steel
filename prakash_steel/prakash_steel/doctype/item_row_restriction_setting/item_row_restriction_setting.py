import frappe
from frappe.model.document import Document


class ItemRowRestrictionSetting(Document):
	"""
	Single settings Doctype to control whether users can manually add item rows
	to Delivery Note and Sales Invoice, or must fetch them via
	"Get Items From > Sales Order".

	This file intentionally keeps logic minimal; the behavior is enforced in
	`prakash_steel.utils.item_row_restriction` and the corresponding client scripts.
	"""

	pass
