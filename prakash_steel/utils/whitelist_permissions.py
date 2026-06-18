import frappe
from frappe import _


def require_permission(doctype, permtype="read", message=None):
	"""Raise PermissionError unless the current user has the given DocType permission."""
	if not frappe.has_permission(doctype, permtype):
		frappe.throw(
			message or _("Not permitted to access {0}.").format(doctype),
			frappe.PermissionError,
		)


def require_any_permission(pairs, message=None):
	"""Raise PermissionError unless the user has at least one listed permission."""
	if any(frappe.has_permission(doctype, permtype) for doctype, permtype in pairs):
		return
	frappe.throw(message or _("Not permitted."), frappe.PermissionError)


def require_all_permissions(pairs, message=None):
	"""Raise PermissionError unless the user has every listed permission."""
	for doctype, permtype in pairs:
		if not frappe.has_permission(doctype, permtype):
			frappe.throw(
				message or _("Not permitted to access {0}.").format(doctype),
				frappe.PermissionError,
			)
