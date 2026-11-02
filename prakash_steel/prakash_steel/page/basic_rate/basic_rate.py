# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, today

# Rate rules per tab.
#   base_field -> field on "Basic Rate Structure" that holds the base rate
#   offsets    -> rate = base rate + offset, keyed by Rate Component name
#                 (offset 0 means the rate equals the base field as-is)
_FLAT_OFFSETS = {
	"40x16,20,25,32": 0,
	"50x13,16,20,25,32,40": 0,
	"65x10,13,16,20,25,32": 0,
	"80x10,13,16,20,25,32": 0,
	"100/105x10,13,16,20,25": 0,
	"25x6,10,12,16,20": 1,
	"32x6,10,12,16,20,25": 1,
	"40x6,8,10,12": 1,
	"50x6,8,10": 1,
	"65x6,8,40,50": 1,
	"80x8,40,50": 1,
	"105x6,32,40,50":1,
	"130x10,13,16,20,25,32":1,
	"80x65": 2,
	"105x65": 2,
	"130x40,50": 2,
	"155x16,20,25,32,40,50": 2,
	"105x80": 3,
	"130x65,80": 3,
	"155x65,80": 3,
	"205x16,20,25,32,40,50": 4,
}

_ROUND_OFFSETS = {
	"24mm to 54mm": 0,
	"20mm, 22mm, 56mm to 65mm": 1,
	"16mm, 71mm & 95mm": 2,
	"100mm": 2.5,
	"105mm & 110mm": 3,
}

_BRIGHT_ROUND_OFFSETS = {
	'20mm to 50.8 (2")': 0,
	'55mm to 2.5" (63.5mm)': 1,
	'70mm & 3"': 2,
	'80mm, 3.25", 3.5", 90mm': 6.5,
	'4"': 7.5,
}

_BRIGHT_FLAT_OFFSETS = {
	'25x6,8,10,12,16,20': 0,
	'1"x1/2",3/4"': 0,
	'30x8,10,20': 0,
	'1.1/4"x3/8,1/2",5/8",3/4",1"': 0,
	'32x6,8,10,12,16,20,25': 0,
	'1.1/2"x1/4",3/8",1/2",5/8",3/4",1"': 0,
	'40x6,8,10,12,16,20,25,32': 0,
	'50x6,8,10,12,16,20,25': 0,
	'2"x3/8",1/2",5/8",3/4",1"': 0,
	'75x8,10,12,16,20,25': 0,
	'3"x1/2",5/8",3/4",1"': 0,
	'80x10': 0,
	'16x5,6,8,10': 2,
	'19x5, 3/4x1/2': 2,
	'20x5,8,10,12': 2,
	'25x5, 40x5': 2,
	'50x5,30,32': 1,
	'2"x1.1/4"': 1,
	'60x6,2.1/2x1/4,75x6': 1,
	'75x6': 1,
	'100x10,12,16,20,25': 1,
	'40x30, 2x1.1/4': 1,
	'4"x3/8,1/2",5/8",3/4",1"': 1,
	'20x16, 50x40': 2,
	'2x1.1/2': 2,
	'60x30,40': 2,
	'2.1/2x1.1/4, 1.1/2': 2,
}

_C4_HEX_OFFSETS = {
	"20.5,32,36,46,50": 4,
}

_C4_ROUND_BRIGHT_OFFSETS = {
	"18mm to 20mm": 6,
	"22mm to 50mm": 5,
}

_SQUARE_OFFSETS = {
	"25,28,32,36,40,45,50": 0,
	"20,22,55": 1,
	"65": 2,
	"16,80": 3,
}

RATE_RULES = {
	"ms_round": {"base_field": "ms_round_basic_rate", "offsets": _ROUND_OFFSETS},
	"c4_round": {"base_field": "c4_round_rate", "offsets": _ROUND_OFFSETS},
	"ms_flat": {"base_field": "ms_square_rate", "offsets": _FLAT_OFFSETS},
	"c4_flat": {"base_field": "c4_flat_square_rate", "offsets": _FLAT_OFFSETS},
	"ms_square": {"base_field": "ms_square_rate", "offsets": _SQUARE_OFFSETS},
	"c4_square": {"base_field": "c4_flat_square_rate", "offsets": _SQUARE_OFFSETS},
	"bright_round": {"base_field": "bright_round_basic", "offsets": _BRIGHT_ROUND_OFFSETS},
	"bright_flat": {"base_field": "bright_flat_basic", "offsets": _BRIGHT_FLAT_OFFSETS},
	"c4_hex": {"base_field": "c4_flat_square_rate", "offsets": _C4_HEX_OFFSETS},
	"c4_round_bright": {"base_field": "c4_round_rate", "offsets": _C4_ROUND_BRIGHT_OFFSETS},
}

# (Item.custom_grade, Item.custom_shape) -> rate rule key. Mirrors TABS in basic_rate.js.
TAB_BY_GRADE_SHAPE = {
	("MS", "Round"): "ms_round",
	("C4", "Round"): "c4_round",
	("MS", "Flat"): "ms_flat",
	("C4", "Flat"): "c4_flat",
	("MS", "Square"): "ms_square",
	("C4", "Square"): "c4_square",
	("C4", "Hex"): "c4_hex",
	("Bright", "Round"): "bright_round",
	("Bright", "Flat"): "bright_flat",
}


def submitted_rate_doc_asof(date):
	"""Most recent *submitted* Basic Rate Structure dated on or before ``date``.

	Unlike :func:`_effective_rate_doc`, draft docs never count here - callers
	that gate transactions (e.g. Sales Order rate validation) must price against
	an approved rate structure only.
	"""
	name = frappe.db.get_value(
		"Basic Rate Structure",
		{"docstatus": 1, "date": ["<=", date]},
		"name",
		order_by="date desc, creation desc",
	)
	return frappe.get_doc("Basic Rate Structure", name) if name else None


def component_rate(rate_doc, grade, shape, rate_component):
	"""Rate for ``rate_component`` from ``rate_doc`` given an Item's grade + shape.

	Returns ``None`` when the grade/shape has no rule or the component has no
	offset under that rule.
	"""
	rule = RATE_RULES.get(TAB_BY_GRADE_SHAPE.get((grade, shape)))
	if not rule or rate_component not in rule["offsets"]:
		return None
	return flt(rate_doc.get(rule["base_field"])) + rule["offsets"][rate_component]


def _effective_rate_doc():
	"""Today's Basic Rate Structure, else the most recent one before today.

	Draft and submitted docs both count; cancelled ones do not.
	"""
	filters = {"docstatus": ["<", 2], "date": ["<=", today()]}
	name = frappe.db.get_value(
		"Basic Rate Structure", filters, "name", order_by="date desc, creation desc"
	)
	if not name:
		name = frappe.db.get_value(
			"Basic Rate Structure", {"docstatus": ["<", 2]}, "name", order_by="date desc, creation desc"
		)
	return frappe.get_doc("Basic Rate Structure", name) if name else None


# Tabs with no matching Item Grade / Shape. "Bright" is not a real Item Grade -
# bright stock is stored as MS Round / MS Flat Items and identified only by which
# rate component it carries, so the component list comes straight from the rule.
# "C4 Round Bright" has no matching Items at all yet - it's rule-driven too.
_RULE_DRIVEN_TABS = {"bright_round", "bright_flat", "c4_round_bright"}

# Rate components belonging to a rule-driven tab are exclusive to that tab - an
# Item that happens to carry one of these (e.g. an MS Round Item tagged with a
# Bright Round component) must not make it bleed into ms_round/c4_round/etc.
_RESERVED_RATE_COMPONENTS = {
	rc for t in _RULE_DRIVEN_TABS for rc in RATE_RULES[t]["offsets"]
}


@frappe.whitelist()
def get_rate_components(tab, grade, shape):
	"""Rate components used by Items of a given grade + shape, with their computed rate."""
	rule = RATE_RULES.get(tab)

	if tab in _RULE_DRIVEN_TABS and rule:
		components = [
			frappe._dict(rate_component=rc) for rc in rule["offsets"]
		]
	else:
		components = frappe.get_all(
			"Item",
			filters=[
				["custom_grade", "=", grade],
				["custom_shape", "=", shape],
				["custom_rate_component", "is", "set"],
				["custom_rate_component", "not in", list(_RESERVED_RATE_COMPONENTS)],
			],
			fields=["custom_rate_component as rate_component"],
			distinct=True,
			order_by="custom_rate_component asc",
		)

	doc = _effective_rate_doc() if rule else None
	base_rate = flt(doc.get(rule["base_field"])) if doc else None

	rows = []
	for c in components:
		rate = None
		if rule and base_rate is not None and c.rate_component in rule["offsets"]:
			rate = base_rate + rule["offsets"][c.rate_component]
		rows.append({"rate_component": c.rate_component, "rate": rate})

	return {
		"rows": rows,
		"rate_date": str(doc.date) if doc else None,
		"rate_doc": doc.name if doc else None,
	}
