import re

import frappe
from frappe import _
from frappe.utils import cint, escape_html, flt, getdate
from frappe.utils.pdf import get_pdf
from frappe.utils.xlsxutils import make_xlsx


MONTH_LABELS = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


@frappe.whitelist()
def get_machine_wise_monthly_data(fiscal_year=None, machine_name=None):
    fiscal_year_doc = _get_fiscal_year_doc(fiscal_year)
    month_periods = _get_fiscal_month_periods(fiscal_year_doc)

    machine_conditions = ""
    machine_params = {}
    if machine_name:
        machine_conditions = "WHERE name = %(machine_name)s"
        machine_params["machine_name"] = machine_name

    machine_rows = frappe.db.sql(
        f"""
        SELECT name
        FROM `tabMachine Master`
        {machine_conditions}
        ORDER BY name
        """,
        machine_params,
        as_dict=True,
    )
    machine_names = [row.name for row in machine_rows if row.get("name")]

    production_conditions = ""
    production_params = {
        "from_date": fiscal_year_doc.year_start_date,
        "to_date": fiscal_year_doc.year_end_date,
    }
    if machine_name:
        production_conditions = "AND machine_name = %(machine_name)s"
        production_params["machine_name"] = machine_name

    production_rows = frappe.db.sql(
        f"""
        SELECT
            production_date,
            MONTH(production_date) AS month_number,
            machine_name,
            fg_weight
        FROM `tabBright Bar Production`
        WHERE docstatus = 1
          AND production_date BETWEEN %(from_date)s AND %(to_date)s
          AND machine_name IS NOT NULL
          AND machine_name != ''
          {production_conditions}
        ORDER BY production_date ASC
        """,
        production_params,
        as_dict=True,
    )

    used_machines = []
    for row in production_rows:
        machine_name = row.get("machine_name")
        if machine_name and machine_name not in used_machines:
            used_machines.append(machine_name)

    for machine in used_machines:
        if machine not in machine_names:
            machine_names.append(machine)

    matrix = {
        period["month_number"]: {
            machine: {"fg_weight": 0, "amount": 0}
            for machine in machine_names
        }
        for period in month_periods
    }

    rate_lookup = _build_machine_rate_lookup(machine_names)
    for row in production_rows:
        month_number = cint(row.get("month_number"))
        machine_name = row.get("machine_name")
        if month_number in matrix and machine_name in matrix[month_number]:
            fg_weight = flt(row.get("fg_weight"))
            production_date = getdate(row.get("production_date"))
            rate = _get_rate_for_date(rate_lookup.get(machine_name, []), production_date)
            matrix[month_number][machine_name]["fg_weight"] += fg_weight
            matrix[month_number][machine_name]["amount"] += fg_weight * rate

    data = []
    for period in month_periods:
        month_no = period["month_number"]
        row = {"month": period["label"], "month_number": month_no}
        for machine in machine_names:
            row[f"{machine}__fg_weight"] = matrix[month_no][machine]["fg_weight"]
            row[f"{machine}__amount"] = matrix[month_no][machine]["amount"]
        data.append(row)

    return {
        "fiscal_year": fiscal_year_doc.name,
        "from_date": fiscal_year_doc.year_start_date,
        "to_date": fiscal_year_doc.year_end_date,
        "machines": machine_names,
        "rows": data,
    }


def _get_fiscal_year_doc(fiscal_year=None):
    if fiscal_year:
        return frappe.get_doc("Fiscal Year", fiscal_year)

    default_fy = (
        frappe.defaults.get_user_default("fiscal_year")
        or frappe.defaults.get_global_default("fiscal_year")
    )
    if default_fy:
        return frappe.get_doc("Fiscal Year", default_fy)

    today = frappe.utils.nowdate()
    fy_name = frappe.db.get_value(
        "Fiscal Year",
        {
            "year_start_date": ("<=", today),
            "year_end_date": (">=", today),
        },
        "name",
    )
    if fy_name:
        return frappe.get_doc("Fiscal Year", fy_name)

    # Final fallback to latest fiscal year.
    latest_fy = frappe.db.get_value("Fiscal Year", {}, "name", order_by="year_end_date desc")
    if latest_fy:
        return frappe.get_doc("Fiscal Year", latest_fy)

    frappe.throw("No Fiscal Year found. Please create Fiscal Year first.")


def _get_fiscal_month_periods(fiscal_year_doc):
    periods = []
    current = fiscal_year_doc.year_start_date
    for _ in range(12):
        periods.append(
            {
                "month_number": current.month,
                "label": current.strftime("%b-%Y"),
            }
        )
        current = frappe.utils.add_months(current, 1)
    return periods


def _build_machine_rate_lookup(machine_names):
    if not machine_names:
        return {}

    rate_rows = frappe.db.sql(
        """
        SELECT
            parent AS machine_name,
            rate_application_date,
            rate
        FROM `tabMachine Master Table`
        WHERE parent IN %(machine_names)s
        ORDER BY parent, rate_application_date ASC, idx ASC
        """,
        {"machine_names": tuple(machine_names)},
        as_dict=True,
    )

    lookup = {machine: [] for machine in machine_names}
    for row in rate_rows:
        machine_name = row.get("machine_name")
        if machine_name in lookup:
            lookup[machine_name].append(
                {
                    "rate_application_date": getdate(row.get("rate_application_date")),
                    "rate": flt(row.get("rate")),
                }
            )
    return lookup


def _get_rate_for_date(rate_rows, production_date):
    """Return latest applicable rate as on production date."""
    applicable_rate = 0
    for rate_row in rate_rows:
        if rate_row["rate_application_date"] <= production_date:
            applicable_rate = rate_row["rate"]
        else:
            break
    return applicable_rate


def _safe_export_filename_part(value):
    return re.sub(r"[^\w\-.]+", "_", (value or "") or "")[:120] or "export"


def _build_flat_sheet_rows(machines, rows):
    header = [_("Month")]
    for machine in machines:
        header.append(f"{machine} — {_('FG Weight')}")
        header.append(f"{machine} — {_('Amount')}")
    header.extend([_("Total FG Weight"), _("Total Amount")])

    data_rows = []
    for row in rows:
        out = [row.get("month") or ""]
        total_fg = 0.0
        total_amt = 0.0
        for machine in machines:
            fg = flt(row.get(f"{machine}__fg_weight"))
            amt = flt(row.get(f"{machine}__amount"))
            total_fg += fg
            total_amt += amt
            out.extend([fg, amt])
        out.extend([flt(total_fg), flt(total_amt, 2)])
        data_rows.append(out)

    return header, data_rows


@frappe.whitelist()
def export_machine_wise_monthly_excel(fiscal_year=None, machine_name=None):
    result = get_machine_wise_monthly_data(fiscal_year, machine_name)
    machines = result.get("machines") or []
    rows = result.get("rows") or []
    if not machines:
        frappe.throw(_("No data to export"))

    header, data_rows = _build_flat_sheet_rows(machines, rows)
    table_data = [header] + data_rows
    fy = result.get("fiscal_year") or "dashboard"
    file_name = f"Machine_Wise_Monthly_{_safe_export_filename_part(fy)}.xlsx"
    xlsx_file = make_xlsx(table_data, _("Machine Wise Monthly"))

    frappe.response["filename"] = file_name
    frappe.response["filecontent"] = xlsx_file.getvalue()
    frappe.response["type"] = "binary"
    frappe.response["content_type"] = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@frappe.whitelist()
def export_machine_wise_monthly_pdf(fiscal_year=None, machine_name=None):
    result = get_machine_wise_monthly_data(fiscal_year, machine_name)
    machines = result.get("machines") or []
    rows = result.get("rows") or []
    fy = result.get("fiscal_year") or ""
    if not machines:
        frappe.throw(_("No data to export"))

    top_cells = [
        f'<th rowspan="2" style="border:1px solid #333;padding:6px;background:#e9ecef;">{escape_html(_("Month"))}</th>'
    ]
    sub_cells = []
    for idx, machine in enumerate(machines):
        border_right = "border-right:2px solid #555;" if idx < len(machines) - 1 else ""
        top_cells.append(
            f'<th colspan="2" style="border:1px solid #333;padding:6px;background:#e9ecef;{border_right}">'
            f"{escape_html(machine)}</th>"
        )
        sub_cells.append(
            f'<th style="border:1px solid #333;padding:4px;background:#f1f3f5;">{escape_html(_("FG Weight"))}</th>'
        )
        sub_cells.append(
            f'<th style="border:1px solid #333;padding:4px;background:#f1f3f5;{border_right}">'
            f"{escape_html(_('Amount'))}</th>"
        )

    top_cells.append(
        f'<th colspan="2" style="border:1px solid #333;padding:6px;background:#e9ecef;border-left:2px solid #555;">'
        f"{escape_html(_('Total'))}</th>"
    )
    sub_cells.append(
        '<th style="border:1px solid #333;padding:4px;background:#f1f3f5;border-left:2px solid #555;">'
        f"{escape_html(_('FG Weight'))}</th>"
    )
    sub_cells.append(
        f'<th style="border:1px solid #333;padding:4px;background:#f1f3f5;">{escape_html(_("Amount"))}</th>'
    )

    body_html = []
    for row in rows:
        cells = [
            f'<td style="border:1px solid #ccc;padding:4px;text-align:left;font-weight:600;">'
            f"{escape_html(row.get('month') or '')}</td>"
        ]
        total_fg = 0.0
        total_amt = 0.0
        for idx, machine in enumerate(machines):
            fg = flt(row.get(f"{machine}__fg_weight"))
            amt = flt(row.get(f"{machine}__amount"))
            total_fg += fg
            total_amt += amt
            border_right = "border-right:2px solid #555;" if idx < len(machines) - 1 else ""
            cells.append(
                f'<td style="border:1px solid #ccc;padding:4px;text-align:center;{border_right}">'
                f"{escape_html(str(int(round(fg))))}</td>"
            )
            cells.append(
                f'<td style="border:1px solid #ccc;padding:4px;text-align:right;{border_right}">'
                f"{escape_html(f'{flt(amt, 2):,.2f}')}</td>"
            )
        cells.append(
            '<td style="border:1px solid #ccc;padding:4px;text-align:center;border-left:2px solid #555;font-weight:600;">'
            f"{escape_html(str(int(round(total_fg))))}</td>"
        )
        cells.append(
            '<td style="border:1px solid #ccc;padding:4px;text-align:right;font-weight:600;">'
            f"{escape_html(f'{flt(total_amt, 2):,.2f}')}</td>"
        )
        body_html.append(f"<tr>{''.join(cells)}</tr>")

    title = escape_html(_("Machine-wise Monthly Dashboard"))
    subtitle = escape_html(_("Fiscal Year: {0}").format(fy)) if fy else ""
    subtitle_html = f'<p class="sub">{subtitle}</p>' if subtitle else ""
    foot = escape_html(
        _("Values are month-wise totals from Bright Bar Production. Month order follows the fiscal year.")
    )

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 12px; font-size: 9pt; }}
        h2 {{ text-align: center; margin: 0 0 4px 0; font-size: 14pt; }}
        .sub {{ text-align: center; color: #444; margin: 0 0 12px 0; font-size: 10pt; }}
        table {{ border-collapse: collapse; width: 100%; }}
        .foot {{ margin-top: 10px; font-size: 8pt; color: #555; }}
    </style>
</head>
<body>
    <h2>{title}</h2>
    {subtitle_html}
    <table>
        <thead>
            <tr>{"".join(top_cells)}</tr>
            <tr>{"".join(sub_cells)}</tr>
        </thead>
        <tbody>
            {"".join(body_html)}
        </tbody>
    </table>
    <p class="foot">{foot}</p>
</body>
</html>
    """

    pdf_content = get_pdf(html)
    file_name = f"Machine_Wise_Monthly_{_safe_export_filename_part(fy)}.pdf"
    frappe.response["filename"] = file_name
    frappe.response["filecontent"] = pdf_content
    frappe.response["type"] = "binary"
    frappe.response["content_type"] = "application/pdf"
