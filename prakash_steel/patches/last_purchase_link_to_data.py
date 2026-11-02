"""Change Last Purchase Party from Link(Supplier) to Data on PO/PI items.

Migration safety:
- Link and Data both map to varchar columns, so no ALTER TABLE is required.
- Values already stored remain as-is; new fetches write supplier_name (display name),
  which is what get_item_insight_data returns and what the UI should show.
"""

import frappe


CUSTOM_FIELDS = (
	"Purchase Order Item-custom_last_purchase_party",
	"Purchase Invoice Item-custom_last_purchase_party",
)


def execute() -> None:
	for name in CUSTOM_FIELDS:
		if not frappe.db.exists("Custom Field", name):
			continue

		frappe.db.set_value(
			"Custom Field",
			name,
			{
				"fieldtype": "Data",
				"options": None,
			},
			update_modified=True,
		)

	frappe.clear_cache(doctype="Purchase Order Item")
	frappe.clear_cache(doctype="Purchase Invoice Item")
