import frappe
from frappe import _


@frappe.whitelist()
def get_all_uom_settings():
	"""Get all Number Card UOM settings as a dictionary"""
	if not frappe.has_permission("Number Card UOM Setting", "read"):
		frappe.throw(_("Not permitted to access Number Card UOM settings."), frappe.PermissionError)

	settings = frappe.get_all("Number Card UOM Setting", fields=["number_card", "uom"])
	return {s.number_card: s.uom for s in settings}
