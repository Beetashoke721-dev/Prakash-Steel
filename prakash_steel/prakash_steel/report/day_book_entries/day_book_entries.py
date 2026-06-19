import frappe
from frappe import _
from frappe.utils import getdate, today

from prakash_steel.utils.whitelist_permissions import require_any_permission


def _normalize_filter_value(value) -> str:
	if isinstance(value, (list, tuple)):
		for item in value:
			if item:
				return str(item)
		return ""
	return str(value or "")


def execute(filters=None) -> tuple[list, list]:
	filters = frappe._dict(filters or {})
	filters.date = getdate(filters.get("date") or today())
	filters.party_name = _normalize_filter_value(filters.get("party_name"))
	filters.vch_type = _normalize_filter_value(filters.get("vch_type"))
	filters.vch_no = _normalize_filter_value(filters.get("vch_no"))

	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns() -> list[dict]:
	return [
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 120},
		{
			"label": _("Particulars"),
			"fieldname": "particulars",
			"fieldtype": "Dynamic Link",
			"options": "party_type",
			"width": 220,
		},
		{"label": _("Vch Type"), "fieldname": "vch_type", "fieldtype": "Data", "width": 160},
		{
			"label": _("Vch No."),
			"fieldname": "vch_no",
			"fieldtype": "Dynamic Link",
			"options": "doc_type",
			"width": 160,
		},
		{"label": _("Debit Amount"), "fieldname": "debit_amount", "fieldtype": "Currency", "width": 140},
		{"label": _("Credit Amount"), "fieldname": "credit_amount", "fieldtype": "Currency", "width": 140},
	]


def get_data(filters) -> list[dict]:
	query = """
		SELECT
			entries.posting_date AS date,
			entries.particulars,
			entries.party_type,
			entries.doc_type,
			entries.vch_type,
			entries.vch_no,
			IFNULL(gl_sums.debit_amount, 0) AS debit_amount,
			IFNULL(gl_sums.credit_amount, 0) AS credit_amount
		FROM (
			SELECT
				pe.posting_date,
				COALESCE(pe.party, '') AS particulars,
				COALESCE(pe.party_type, '') AS party_type,
				'Payment Entry' AS doc_type,
				COALESCE(pe.payment_type, 'Payment Entry') AS vch_type,
				pe.name AS vch_no
			FROM `tabPayment Entry` pe
			WHERE pe.docstatus = 1
				AND pe.posting_date = %(date)s

			UNION ALL

			SELECT
				je.posting_date,
				COALESCE(MAX(NULLIF(jea.party, '')), '') AS particulars,
				COALESCE(MAX(NULLIF(jea.party_type, '')), '') AS party_type,
				'Journal Entry' AS doc_type,
				COALESCE(je.voucher_type, 'Journal Entry') AS vch_type,
				je.name AS vch_no
			FROM `tabJournal Entry` je
			LEFT JOIN `tabJournal Entry Account` jea
				ON jea.parent = je.name
			WHERE je.docstatus = 1
				AND je.posting_date = %(date)s
			GROUP BY je.name, je.posting_date, je.user_remark, je.title

			UNION ALL

			SELECT
				si.posting_date,
				COALESCE(si.customer, '') AS particulars,
				'Customer' AS party_type,
				'Sales Invoice' AS doc_type,
				'Sales Invoice' AS vch_type,
				si.name AS vch_no
			FROM `tabSales Invoice` si
			WHERE si.docstatus = 1
				AND si.posting_date = %(date)s

			UNION ALL

			SELECT
				pi.posting_date,
				COALESCE(pi.supplier, '') AS particulars,
				'Supplier' AS party_type,
				'Purchase Invoice' AS doc_type,
				'Purchase Invoice' AS vch_type,
				pi.name AS vch_no
			FROM `tabPurchase Invoice` pi
			WHERE pi.docstatus = 1
				AND pi.posting_date = %(date)s
		) entries
		LEFT JOIN (
			SELECT
				gle.voucher_type AS doc_type,
				gle.voucher_no AS vch_no,
				SUM(IFNULL(gle.debit, 0)) AS debit_amount,
				SUM(IFNULL(gle.credit, 0)) AS credit_amount
			FROM `tabGL Entry` gle
			WHERE gle.is_cancelled = 0
				AND gle.posting_date = %(date)s
				AND gle.party IS NOT NULL
				AND gle.party != ''
				AND gle.voucher_type IN ('Payment Entry', 'Journal Entry', 'Sales Invoice', 'Purchase Invoice')
			GROUP BY gle.voucher_type, gle.voucher_no
		) gl_sums
			ON gl_sums.doc_type = entries.doc_type
			AND gl_sums.vch_no = entries.vch_no
		WHERE (%(party_name)s IS NULL OR %(party_name)s = '' OR entries.particulars LIKE CONCAT('%%', %(party_name)s, '%%'))
			AND (%(vch_type)s IS NULL OR %(vch_type)s = '' OR entries.vch_type = %(vch_type)s)
			AND (%(vch_no)s IS NULL OR %(vch_no)s = '' OR entries.vch_no LIKE CONCAT('%%', %(vch_no)s, '%%'))
		ORDER BY entries.posting_date DESC, entries.vch_type, entries.vch_no
	"""

	return frappe.db.sql(query, filters, as_dict=True)


@frappe.whitelist()
def get_filter_options(fieldname, txt="", date=None) -> str:
	require_any_permission(
		[
			("Journal Entry", "read"),
			("Payment Entry", "read"),
			("Sales Invoice", "read"),
		],
		_("Not permitted to access day book filter options."),
	)
	field_map = {
		"party_name": "entries.particulars",
		"vch_type": "entries.vch_type",
		"vch_no": "entries.vch_no",
	}
	if fieldname not in field_map:
		return []

	filters = {
		"date": getdate(date or today()),
		"txt": f"%{(txt or '').strip()}%",
	}

	query = f"""
		SELECT DISTINCT {field_map[fieldname]} AS value
		FROM (
			SELECT
				COALESCE(pe.party, '') AS particulars,
				COALESCE(pe.payment_type, 'Payment Entry') AS vch_type,
				pe.name AS vch_no
			FROM `tabPayment Entry` pe
			WHERE pe.docstatus = 1
				AND pe.posting_date = %(date)s

			UNION ALL

			SELECT
				COALESCE(MAX(NULLIF(jea.party, '')), '') AS particulars,
				COALESCE(je.voucher_type, 'Journal Entry') AS vch_type,
				je.name AS vch_no
			FROM `tabJournal Entry` je
			LEFT JOIN `tabJournal Entry Account` jea
				ON jea.parent = je.name
			WHERE je.docstatus = 1
				AND je.posting_date = %(date)s
			GROUP BY je.name

			UNION ALL

			SELECT
				COALESCE(si.customer, '') AS particulars,
				'Sales Invoice' AS vch_type,
				si.name AS vch_no
			FROM `tabSales Invoice` si
			WHERE si.docstatus = 1
				AND si.posting_date = %(date)s

			UNION ALL

			SELECT
				COALESCE(pi.supplier, '') AS particulars,
				'Purchase Invoice' AS vch_type,
				pi.name AS vch_no
			FROM `tabPurchase Invoice` pi
			WHERE pi.docstatus = 1
				AND pi.posting_date = %(date)s
		) entries
		WHERE {field_map[fieldname]} != ''
			AND {field_map[fieldname]} LIKE %(txt)s
		ORDER BY {field_map[fieldname]}
		LIMIT 20
	"""

	return [
		{
			"value": row.value,
			"label": row.value,
			"description": "",
		}
		for row in frappe.db.sql(query, filters, as_dict=True)
	]
