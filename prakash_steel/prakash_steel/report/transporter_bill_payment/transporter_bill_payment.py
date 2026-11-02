import frappe
from frappe.utils import flt, getdate


def execute(filters=None) -> tuple[list, list]:
    filters = filters or {}
    invoice_type = get_invoice_type(filters)
    columns = get_columns(invoice_type)
    data = get_data(filters)
    return columns, data


def get_invoice_type(filters) -> str:
    invoice_type = (filters.get("invoice_type") or "Purchase").strip().lower()
    mapping = {
        "sale": "sale",
        "subcontracting receipt": "subcontracting_receipt",
        "subcontracting delivery": "subcontracting_delivery",
        "internal transfer": "internal_transfer",
    }
    return mapping.get(invoice_type, "purchase")


def get_columns(invoice_type) -> list[dict]:
    if invoice_type == "internal_transfer":
        return [
            {
                "label": "Bill Date",
                "fieldname": "bill_date",
                "fieldtype": "Date",
                "width": 120,
            },
            {
                "label": "Stock Entry",
                "fieldname": "stock_entry",
                "fieldtype": "Link",
                "options": "Stock Entry",
                "width": 170,
            },
            {
                "label": "Truck No",
                "fieldname": "truck_no",
                "fieldtype": "Data",
                "width": 140,
            },
            {
                "label": "Transporter Name",
                "fieldname": "transporter_name",
                "fieldtype": "Data",
                "width": 190,
            },
            {
                "label": "Quantity",
                "fieldname": "qty",
                "fieldtype": "Float",
                "width": 130,
            },
            {
                "label": "Amount",
                "fieldname": "amount",
                "fieldtype": "Currency",
                "width": 140,
                "disable_total": 1,
            },
            {
                "label": "Freight Charges",
                "fieldname": "freight_charges",
                "fieldtype": "Currency",
                "width": 140,
                "disable_total": 1,
            },
        ]

    if invoice_type in ("sale", "subcontracting_delivery"):
        columns = [
            {
                "label": "Bill Date",
                "fieldname": "bill_date",
                "fieldtype": "Date",
                "width": 120,
            },
            {
                "label": "Sales Invoice",
                "fieldname": "sales_invoice",
                "fieldtype": "Link",
                "options": "Sales Invoice",
                "width": 170,
            },
            {
                "label": "Vendor Name",
                "fieldname": "vendor_name",
                "fieldtype": "Data",
                "width": 190,
            },
            {
                "label": "Truck No",
                "fieldname": "truck_no",
                "fieldtype": "Data",
                "width": 140,
            },
            {
                "label": "Transporter Name",
                "fieldname": "transporter_name",
                "fieldtype": "Data",
                "width": 190,
            },
        ]

        columns.extend(
            [
                {
                    "label": "Quantity",
                    "fieldname": "qty",
                    "fieldtype": "Float",
                    "width": 130,
                },
                {
                    "label": "Amount",
                    "fieldname": "amount",
                    "fieldtype": "Currency",
                    "width": 140,
                    "disable_total": 1,
                },
            ]
        )

        return columns

    columns = [
        {
            "label": "Bill Date",
            "fieldname": "bill_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": "Purchase Invoice",
            "fieldname": "purchase_invoice",
            "fieldtype": "Link",
            "options": "Purchase Invoice",
            "width": 160,
        },
        {
            "label": "Approval Status",
            "fieldname": "approval_status",
            "fieldtype": "Data",
            "width": 130,
            "align": "center",
        },
        {
            "label": "Supplier Invoice Date",
            "fieldname": "invoice_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Vendor Name",
            "fieldname": "vendor_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": "Bill Number",
            "fieldname": "bill_no",
            "fieldtype": "Data",
            "width": 140,
        },
        {
            "label": "Truck No",
            "fieldname": "truck_no",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": "Transporter Name",
            "fieldname": "transporter_name",
            "fieldtype": "Data",
            "width": 180,
        },
    ]

    if invoice_type == "subcontracting_receipt":
        columns.append(
            {
                "label": "Item",
                "fieldname": "item_code",
                "fieldtype": "Link",
                "options": "Item",
                "width": 160,
            }
        )

    columns.extend(
        [
            {
                "label": "Billing Quantity",
                "fieldname": "billing_qty",
                "fieldtype": "Float",
                "width": 130,
            },
            {
                "label": "Receiving Quantity",
                "fieldname": "receiving_qty",
                "fieldtype": "Float",
                "width": 140,
            },
            {
                "label": "Shortage Quantity",
                "fieldname": "shortage_qty",
                "fieldtype": "Float",
                "width": 140,
                "disable_total": 1,
            },
            {
                "label": "Freight Charges",
                "fieldname": "freight_charges",
                "fieldtype": "Currency",
                "width": 140,
                "disable_total": 1,
            },
        ]
    )

    return columns


def get_data(filters) -> list[dict]:
    invoice_type = get_invoice_type(filters)
    if invoice_type == "sale":
        return get_sale_data(filters)

    if invoice_type == "subcontracting_receipt":
        return get_subcontracting_receipt_data(filters)

    if invoice_type == "subcontracting_delivery":
        return get_subcontracting_delivery_data(filters)

    if invoice_type == "internal_transfer":
        return get_internal_transfer_data(filters)

    return get_purchase_data(filters)


def get_purchase_data(filters) -> list[dict]:
    conditions = ["pi.docstatus = 1", "ifnull(pi.transporter_name, '') != ''"]
    values = {}

    # Date range filter on posting_date (Bill Date)
    if filters.get("from_date"):
        conditions.append("pi.posting_date >= %(from_date)s")
        values["from_date"] = getdate(filters.get("from_date"))

    if filters.get("to_date"):
        conditions.append("pi.posting_date <= %(to_date)s")
        values["to_date"] = getdate(filters.get("to_date"))

    # Supplier Invoice date range filter on Purchase Invoice.bill_date
    if filters.get("supplier_invoice_from_date"):
        conditions.append("pi.bill_date >= %(supplier_invoice_from_date)s")
        values["supplier_invoice_from_date"] = getdate(filters.get("supplier_invoice_from_date"))

    if filters.get("supplier_invoice_to_date"):
        conditions.append("pi.bill_date <= %(supplier_invoice_to_date)s")
        values["supplier_invoice_to_date"] = getdate(filters.get("supplier_invoice_to_date"))

    # Transporter Name filter
    if filters.get("transporter_name"):
        conditions.append("pi.transporter_name = %(transporter_name)s")
        values["transporter_name"] = filters.get("transporter_name")

    where_clause = " AND ".join(conditions)

    # Billing Qty: sum of all Purchase Invoice Item quantities.
    # Receiving Qty: sum weight slip qty from Purchase Invoice Items.

    query = f"""
        SELECT
            pi.posting_date AS bill_date,
            pi.name AS purchase_invoice,
            CASE WHEN pi.workflow_state = 'Approved' THEN 'Approved' ELSE '' END AS approval_status,
            pi.bill_date AS invoice_date,
            pi.supplier AS vendor_name,
            pi.bill_no AS bill_no,
            pi.vehicle_no AS truck_no,
            pi.transporter_name AS transporter_name,
            SUM(pii.qty) AS billing_qty,
            IFNULL(SUM(pii.custom_weight_slip_qty), 0) AS receiving_qty,
            IFNULL(pi.custom_freight_charges, 0) AS freight_charges
        FROM
            `tabPurchase Invoice` pi
        INNER JOIN
            `tabPurchase Invoice Item` pii
        ON
            pi.name = pii.parent
        WHERE
            {where_clause}
        GROUP BY
            pi.name
        ORDER BY
            pi.posting_date ASC,
            pi.name ASC
    """

    result = frappe.db.sql(query, values=values, as_dict=True)

    for row in result:
        billing_qty = flt(row.get("billing_qty") or 0)
        receiving_qty = flt(row.get("receiving_qty") or 0)
        row["shortage_qty"] = billing_qty - receiving_qty

    return result


def get_subcontracting_receipt_data(filters) -> list[dict]:
    conditions = [
        "pi.docstatus = 1",
        "ifnull(pi.transporter_name, '') != ''",
        "pr.is_subcontracted = 1",
    ]
    values = {}

    if filters.get("from_date"):
        conditions.append("pi.posting_date >= %(from_date)s")
        values["from_date"] = getdate(filters.get("from_date"))

    if filters.get("to_date"):
        conditions.append("pi.posting_date <= %(to_date)s")
        values["to_date"] = getdate(filters.get("to_date"))

    if filters.get("supplier_invoice_from_date"):
        conditions.append("pi.bill_date >= %(supplier_invoice_from_date)s")
        values["supplier_invoice_from_date"] = getdate(filters.get("supplier_invoice_from_date"))

    if filters.get("supplier_invoice_to_date"):
        conditions.append("pi.bill_date <= %(supplier_invoice_to_date)s")
        values["supplier_invoice_to_date"] = getdate(filters.get("supplier_invoice_to_date"))

    if filters.get("transporter_name"):
        conditions.append("pi.transporter_name = %(transporter_name)s")
        values["transporter_name"] = filters.get("transporter_name")

    where_clause = " AND ".join(conditions)

    # Purchase Invoice/Purchase Receipt Item.item_code for a subcontracted
    # receipt is the generic "Job Work Service Charges" placeholder — the real
    # item is only recorded on the linked Subcontracting Receipt Item row.
    query = f"""
        SELECT
            pi.posting_date AS bill_date,
            pi.name AS purchase_invoice,
            CASE WHEN pi.workflow_state = 'Approved' THEN 'Approved' ELSE '' END AS approval_status,
            pi.bill_date AS invoice_date,
            pi.supplier AS vendor_name,
            pi.bill_no AS bill_no,
            pi.vehicle_no AS truck_no,
            pi.transporter_name AS transporter_name,
            COALESCE(scri.item_code, pii.item_code) AS item_code,
            SUM(pii.qty) AS billing_qty,
            IFNULL(SUM(pii.custom_weight_slip_qty), 0) AS receiving_qty,
            IFNULL(pi.custom_freight_charges, 0) AS freight_charges
        FROM
            `tabPurchase Invoice` pi
        INNER JOIN
            `tabPurchase Invoice Item` pii
        ON
            pi.name = pii.parent
        INNER JOIN
            `tabPurchase Receipt` pr
        ON
            pr.name = pii.purchase_receipt
        LEFT JOIN
            `tabPurchase Receipt Item` pri
        ON
            pri.name = pii.pr_detail
        LEFT JOIN
            `tabSubcontracting Receipt Item` scri
        ON
            scri.name = pri.subcontracting_receipt_item
        WHERE
            {where_clause}
        GROUP BY
            pi.name,
            COALESCE(scri.item_code, pii.item_code)
        ORDER BY
            pi.posting_date ASC,
            pi.name ASC
    """

    result = frappe.db.sql(query, values=values, as_dict=True)

    for row in result:
        billing_qty = flt(row.get("billing_qty") or 0)
        receiving_qty = flt(row.get("receiving_qty") or 0)
        row["shortage_qty"] = billing_qty - receiving_qty

    return result


def get_sale_data(filters) -> list[dict]:
    has_transporter_name = frappe.db.has_column("Sales Invoice", "transporter_name")
    has_vehicle_no = frappe.db.has_column("Sales Invoice", "vehicle_no")

    conditions = ["si.docstatus = 1"]
    values = {}

    if has_transporter_name:
        conditions.append("ifnull(si.transporter_name, '') != ''")

    if filters.get("from_date"):
        conditions.append("si.posting_date >= %(from_date)s")
        values["from_date"] = getdate(filters.get("from_date"))

    if filters.get("to_date"):
        conditions.append("si.posting_date <= %(to_date)s")
        values["to_date"] = getdate(filters.get("to_date"))

    if filters.get("transporter_name") and has_transporter_name:
        conditions.append("si.transporter_name = %(transporter_name)s")
        values["transporter_name"] = filters.get("transporter_name")
    elif filters.get("transporter_name") and not has_transporter_name:
        return []

    where_clause = " AND ".join(conditions)
    truck_no_field = "si.vehicle_no" if has_vehicle_no else "''"
    transporter_name_field = "si.transporter_name" if has_transporter_name else "''"

    query = f"""
        SELECT
            si.posting_date AS bill_date,
            si.name AS sales_invoice,
            si.customer AS vendor_name,
            {truck_no_field} AS truck_no,
            {transporter_name_field} AS transporter_name,
            IFNULL(
                (
                    SELECT SUM(sii.qty)
                    FROM `tabSales Invoice Item` sii
                    WHERE sii.parent = si.name
                ),
                0
            ) AS qty,
            si.grand_total AS amount
        FROM
            `tabSales Invoice` si
        WHERE
            {where_clause}
        ORDER BY
            si.posting_date ASC,
            si.name ASC
    """

    return frappe.db.sql(query, values=values, as_dict=True)


def get_subcontracting_delivery_data(filters) -> list[dict]:
    has_transporter_name = frappe.db.has_column("Sales Invoice", "transporter_name")
    has_vehicle_no = frappe.db.has_column("Sales Invoice", "vehicle_no")
    has_subcontracted_flag = frappe.db.has_column("Sales Invoice", "has_subcontracted")

    if not has_subcontracted_flag:
        return []

    conditions = ["si.docstatus = 1", "si.has_subcontracted = 1"]
    values = {}

    if has_transporter_name:
        conditions.append("ifnull(si.transporter_name, '') != ''")

    if filters.get("from_date"):
        conditions.append("si.posting_date >= %(from_date)s")
        values["from_date"] = getdate(filters.get("from_date"))

    if filters.get("to_date"):
        conditions.append("si.posting_date <= %(to_date)s")
        values["to_date"] = getdate(filters.get("to_date"))

    if filters.get("transporter_name") and has_transporter_name:
        conditions.append("si.transporter_name = %(transporter_name)s")
        values["transporter_name"] = filters.get("transporter_name")
    elif filters.get("transporter_name") and not has_transporter_name:
        return []

    where_clause = " AND ".join(conditions)
    truck_no_field = "si.vehicle_no" if has_vehicle_no else "''"
    transporter_name_field = "si.transporter_name" if has_transporter_name else "''"

    query = f"""
        SELECT
            si.posting_date AS bill_date,
            si.name AS sales_invoice,
            si.customer AS vendor_name,
            {truck_no_field} AS truck_no,
            {transporter_name_field} AS transporter_name,
            IFNULL(
                (
                    SELECT SUM(sii.qty)
                    FROM `tabSales Invoice Item` sii
                    WHERE sii.parent = si.name
                ),
                0
            ) AS qty,
            si.grand_total AS amount
        FROM
            `tabSales Invoice` si
        WHERE
            {where_clause}
        ORDER BY
            si.posting_date ASC,
            si.name ASC
    """

    return frappe.db.sql(query, values=values, as_dict=True)


def get_internal_transfer_data(filters) -> list[dict]:
    conditions = [
        "se.docstatus = 1",
        "se.stock_entry_type = 'Material Transfer'",
        "ifnull(se.transporter_name, '') != ''",
    ]
    values = {}

    if filters.get("from_date"):
        conditions.append("se.posting_date >= %(from_date)s")
        values["from_date"] = getdate(filters.get("from_date"))

    if filters.get("to_date"):
        conditions.append("se.posting_date <= %(to_date)s")
        values["to_date"] = getdate(filters.get("to_date"))

    if filters.get("transporter_name"):
        conditions.append("se.transporter_name = %(transporter_name)s")
        values["transporter_name"] = filters.get("transporter_name")

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            se.posting_date AS bill_date,
            se.name AS stock_entry,
            se.vehicle_no AS truck_no,
            se.transporter_name AS transporter_name,
            IFNULL(
                (
                    SELECT SUM(sed.qty)
                    FROM `tabStock Entry Detail` sed
                    WHERE sed.parent = se.name
                ),
                0
            ) AS qty,
            se.total_amount AS amount,
            IFNULL(se.custom_freight_charges, 0) AS freight_charges
        FROM
            `tabStock Entry` se
        WHERE
            {where_clause}
        ORDER BY
            se.posting_date ASC,
            se.name ASC
    """

    return frappe.db.sql(query, values=values, as_dict=True)

