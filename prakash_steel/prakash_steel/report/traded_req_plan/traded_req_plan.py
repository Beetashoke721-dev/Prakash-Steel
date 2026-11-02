# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

from frappe import _
from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
	get_data as get_po_recomendation_data,
)


def execute(filters: dict | None = None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": _("SKU Type"),
			"fieldname": "sku_type",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("On Hand Colour"),
			"fieldname": "on_hand_colour",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Open PO"),
			"fieldname": "open_po",
			"fieldtype": "Int",
			"width": 120,
			"hidden":1,
		},
		{
			"label": _("Net Order Recommendation"),
			"fieldname": "or_with_moq_batch_size",
			"fieldtype": "Int",
			"width": 180,
		},
	]


def get_data(filters: dict | None = None) -> list[dict]:
	# On Hand Colour and Net Order Recommendation are computed identically to
	# "PO Recomendation for PSP" — reused here rather than re-derived.
	# TRMTA lives under buffer_flag=1, TRMTO lives under buffer_flag=0, so both
	# variants of the underlying report must be queried and merged.
	rows = get_po_recomendation_data({"purchase": 1, "buffer_flag": 1, "sku_type": "TRMTA"})
	rows += get_po_recomendation_data({"purchase": 1, "buffer_flag": 0, "sku_type": "TRMTO"})

	seen_item_codes = set()
	data = []
	for row in rows:
		item_code = row.get("item_code")
		if not item_code or item_code in seen_item_codes:
			continue
		if not (row.get("or_with_moq_batch_size") or 0) > 0:
			continue
		seen_item_codes.add(item_code)
		# TRMTO items are non-buffer, so on_hand_colour is never computed for them;
		# fall back to their propagated Priority colour (worst of own FIFO-SO
		# shortage and BOM ancestors, per propagate_priority_through_bom_tree),
		# which uses the same BLACK/RED/YELLOW/GREEN/WHITE vocabulary.
		on_hand_colour = row.get("on_hand_colour")
		if row.get("sku_type") == "TRMTO":
			on_hand_colour = row.get("priority")
		data.append(
			{
				"item_code": item_code,
				"sku_type": row.get("sku_type"),
				"on_hand_colour": on_hand_colour,
				"open_po": row.get("open_po"),
				"or_with_moq_batch_size": row.get("or_with_moq_batch_size"),
			}
		)

	return data
