# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import calendar
import frappe
from frappe.utils import flt, getdate, today, add_days


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    # Manually append a Total row that only sums selected columns
    if data:
        total_interest_amount = sum((row.get("interest_amount") or 0) for row in data)
        total_tds_10 = sum((row.get("tds_10") or 0) for row in data)
        total_total_amount = sum((row.get("total_amount") or 0) for row in data)

        total_row = {
            "month": "Total",
            "detail_date": None,
            "unsecured_loan": "",
            "interest_percent": None,
            "closing_balance": None,
            "day_interest": None,
            "interest_amount": total_interest_amount,
            "tds_10": total_tds_10,
            "total_amount": total_total_amount,
            # mark as Total so formatter can detect it
            "name": "Total",
        }

        data.append(total_row)

    return columns, data


def get_columns():
    return [
        {"label": "Month", "fieldname": "month", "fieldtype": "Data", "width": 110},
        {"label": "Date", "fieldname": "detail_date", "fieldtype": "Date", "width": 110},
        {"label": "Account Head", "fieldname": "unsecured_loan", "fieldtype": "Data", "width": 250},
        {
            "label": "Interest % Per Annum",
            "fieldname": "interest_percent",
            "fieldtype": "Float",
            "width": 150,
            "no_total": 1,
        },
        {
            "label": "Closing Balance",
            "fieldname": "closing_balance",
            "fieldtype": "Currency",
            "width": 150,
            "no_total": 1,
        },
        {
            "label": "Interest per Day",
            "fieldname": "day_interest",
            "fieldtype": "Float",
            "width": 130,
            "no_total": 1,
        },
        {"label": "Interest Amount", "fieldname": "interest_amount", "fieldtype": "Currency", "width": 150},
        {"label": "TDS (10%)", "fieldname": "tds_10", "fieldtype": "Currency", "width": 120},
        {"label": "Total Amount", "fieldname": "total_amount", "fieldtype": "Currency", "width": 150},
        {
            "label": "Voucher",
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Unsecured Loans and Transaction",
            "width": 200,
        },
    ]


def _get_daily_balances(account, loop_start, loop_end):
    """
    Pre-fetch closing balances for every date in [loop_start, loop_end] using
    2 SQL queries instead of one per day.

    Returns dict: {date_str: closing_balance}
    """
    opening_date = add_days(loop_start, -1)

    # 1. Signed opening balance (credit - debit) up to the day before loop_start
    result = frappe.db.sql(
        """
        SELECT SUM(credit) - SUM(debit) AS balance
        FROM `tabGL Entry`
        WHERE account = %(account)s
          AND posting_date <= %(date)s
          AND is_cancelled = 0
          AND docstatus = 1
        """,
        {"account": account, "date": str(opening_date)},
        as_dict=True,
    )
    running = flt((result[0].get("balance") or 0) if result else 0)

    # 2. Net daily movement within the range (one row per day that has activity)
    daily_rows = frappe.db.sql(
        """
        SELECT posting_date, SUM(credit) - SUM(debit) AS net
        FROM `tabGL Entry`
        WHERE account = %(account)s
          AND posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND is_cancelled = 0
          AND docstatus = 1
        GROUP BY posting_date
        ORDER BY posting_date ASC
        """,
        {"account": account, "from_date": str(loop_start), "to_date": str(loop_end)},
        as_dict=True,
    )
    daily_change = {str(r.posting_date): flt(r.net) for r in daily_rows}

    # Build cumulative closing balance for each day in the range
    balances = {}
    current = loop_start
    while current <= loop_end:
        date_str = str(current)
        running += daily_change.get(date_str, 0.0)
        balances[date_str] = abs(running)
        current = add_days(current, 1)

    return balances


# Month mapping
MONTH_MAP = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


def get_data(filters):
    conditions = []
    values = {}

    # Account Head Filter
    if filters.get("account_head"):
        conditions.append("unsecured_loan = %(account_head)s")
        values["account_head"] = filters["account_head"]

    # Financial Year Filter
    if filters.get("financial_year"):
        conditions.append("financial_year = %(financial_year)s")
        values["financial_year"] = filters["financial_year"]

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    records = frappe.db.sql(
        f"""
        SELECT
            name,
            unsecured_loan,
            financial_year,
            from_date,
            to_date,
            interest_percent
        FROM
            `tabUnsecured Loans and Transaction`
        {where_clause}
        ORDER BY
            unsecured_loan ASC,
            from_date ASC
        """,
        values,
        as_dict=True,
    )

    yesterday = add_days(getdate(today()), -1)

    # Month Filter
    selected_month = None
    if filters.get("month"):
        selected_month = MONTH_MAP.get(filters.get("month"))

    data = []

    for rec in records:

        from_date = getdate(rec["from_date"])
        to_date = getdate(rec["to_date"])
        interest_pct = flt(rec["interest_percent"])
        account = rec["unsecured_loan"]

        loop_start = from_date
        loop_end = min(to_date, yesterday)

        if selected_month:
            year = loop_start.year
            month_start = getdate(f"{year}-{selected_month}-01")
            month_end = add_days(month_start, calendar.monthrange(year, selected_month)[1] - 1)

            loop_start = max(loop_start, month_start)
            loop_end = min(loop_end, month_end)

        if loop_start > loop_end:
            continue

        # Pre-fetch all closing balances for this account in the date range (2 queries total)
        daily_balances = _get_daily_balances(account, loop_start, loop_end)

        is_first_row = True
        current = loop_start

        while current <= loop_end:

            month_name = calendar.month_name[current.month]
            days_in_month = calendar.monthrange(current.year, current.month)[1]

            # Daily Interest Calculation
            day_interest_pct = round((interest_pct / 12.0) / days_in_month, 6)

            closing_bal = daily_balances.get(str(current), 0.0)

            interest_amount = round(closing_bal * (day_interest_pct / 100), 2)

            tds_10 = round(interest_amount * 0.10, 2)

            total_amount = round(interest_amount - tds_10, 2)

            row = {
                "name": rec["name"] if is_first_row else "",
                "unsecured_loan": account if is_first_row else "",
                "interest_percent": interest_pct if is_first_row else None,
                "month": month_name,
                "detail_date": current,
                "closing_balance": closing_bal,
                "day_interest": day_interest_pct,
                "interest_amount": interest_amount,
                "tds_10": tds_10,
                "total_amount": total_amount,
            }

            data.append(row)

            is_first_row = False
            current = add_days(current, 1)

    return data