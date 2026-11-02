import frappe


def execute() -> None:
	"""Make Payment Terms Template mandatory only for non-return Sales Invoices.

	A site Property Setter had forced ``payment_terms_template`` to always be
	required. Credit notes (``is_return``) hide that field via standard
	``depends_on``, so unconditional ``reqd`` blocked save/submit. Switch to
	``mandatory_depends_on`` instead.
	"""
	# Drop unconditional required flag
	if frappe.db.exists("Property Setter", "Sales Invoice-payment_terms_template-reqd"):
		frappe.db.set_value(
			"Property Setter",
			"Sales Invoice-payment_terms_template-reqd",
			"value",
			"0",
			update_modified=False,
		)
	else:
		frappe.get_doc(
			{
				"doctype": "Property Setter",
				"doctype_or_field": "DocField",
				"doc_type": "Sales Invoice",
				"field_name": "payment_terms_template",
				"property": "reqd",
				"property_type": "Check",
				"value": "0",
			}
		).insert(ignore_permissions=True)

	# Conditionally mandatory when not a return (and not POS — field is hidden there too)
	mandatory_depends_on = "eval:!doc.is_return && !doc.is_pos"
	ps_name = "Sales Invoice-payment_terms_template-mandatory_depends_on"

	if frappe.db.exists("Property Setter", ps_name):
		frappe.db.set_value(
			"Property Setter",
			ps_name,
			"value",
			mandatory_depends_on,
			update_modified=False,
		)
	else:
		frappe.get_doc(
			{
				"doctype": "Property Setter",
				"doctype_or_field": "DocField",
				"doc_type": "Sales Invoice",
				"field_name": "payment_terms_template",
				"property": "mandatory_depends_on",
				"property_type": "Data",
				"value": mandatory_depends_on,
			}
		).insert(ignore_permissions=True)

	frappe.clear_cache(doctype="Sales Invoice")
