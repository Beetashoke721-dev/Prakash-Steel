import base64
import io
from datetime import datetime, timedelta

import frappe
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


@frappe.whitelist()
def get_attendance_data(from_date, to_date, employee=None):
	"""Return attendance data for all ESSL-mapped employees for the given date range."""

	# Build date list
	start = datetime.strptime(from_date, "%Y-%m-%d").date()
	end = datetime.strptime(to_date, "%Y-%m-%d").date()
	dates = []
	d = start
	while d <= end:
		dates.append(str(d))
		d += timedelta(days=1)

	# Get employees with ESSL mapping
	emp_filters = {"custom_essl_employee_id": ["!=", ""], "status": "Active"}
	if employee:
		emp_filters["name"] = employee

	employees = frappe.db.get_all(
		"Employee",
		filters=emp_filters,
		fields=["name", "employee_name", "custom_essl_employee_id"],
		order_by="name asc",
	)

	if not employees:
		return {"dates": dates, "employees": []}

	emp_names = [e["name"] for e in employees]

	# Fetch attendance records for the range
	attendance_records = frappe.db.get_all(
		"Attendance",
		filters={
			"employee": ["in", emp_names],
			"attendance_date": ["between", [from_date, to_date]],
			"docstatus": ["!=", 2],
		},
		fields=[
			"employee",
			"attendance_date",
			"status",
			"custom_punch_in_time",
			"custom_punch_out_time",
			"custom_work_hours",
		],
	)

	# Build lookup: {employee: {date_str: record}}
	att_map = {}
	for rec in attendance_records:
		emp = rec["employee"]
		dt = str(rec["attendance_date"])
		att_map.setdefault(emp, {})[dt] = {
			"status": rec["status"] or "",
			"punch_in": str(rec["custom_punch_in_time"]) if rec["custom_punch_in_time"] else "",
			"punch_out": str(rec["custom_punch_out_time"]) if rec["custom_punch_out_time"] else "",
			"work_hours": str(rec["custom_work_hours"]) if rec["custom_work_hours"] else "",
		}

	result = []
	for emp in employees:
		emp_att = att_map.get(emp["name"], {})
		attendance = {}
		for date_str in dates:
			attendance[date_str] = emp_att.get(
				date_str, {"status": "", "punch_in": "", "punch_out": "", "work_hours": ""}
			)
		result.append(
			{
				"employee": emp["name"],
				"employee_name": emp["employee_name"],
				"essl_id": emp["custom_essl_employee_id"] or "",
				"attendance": attendance,
			}
		)

	return {"dates": dates, "employees": result}


def _extract_time(val):
	"""Return HH:MM:SS from 'YYYY-MM-DD HH:MM:SS' or 'HH:MM:SS', else empty string."""
	if not val:
		return ""
	s = str(val).strip()
	parts = s.split(" ")
	return parts[1] if len(parts) > 1 else parts[0]


@frappe.whitelist()
def download_attendance_excel(from_date, to_date, employee=None):
	"""Generate and return a base64-encoded .xlsx attendance report."""
	data = get_attendance_data(from_date, to_date, employee)
	dates = data["dates"]
	employees = data["employees"]

	dow_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "Attendance"

	# ── Styles ────────────────────────────────────────────────────────────────
	hdr_font   = Font(bold=True, size=10)
	date_fill  = PatternFill("solid", fgColor="C6EFCE")   # green tint for date headers
	sub_fill   = PatternFill("solid", fgColor="EFF2F7")   # grey for sub-headers
	sun_fill   = PatternFill("solid", fgColor="FFE4E4")   # red tint for Sundays
	center     = Alignment(horizontal="center", vertical="center", wrap_text=False)
	left_align = Alignment(horizontal="left",   vertical="center")

	STICKY_COLS = 3   # Employee ID | Employee Name | ESSL Biometric ID

	# ── Row 1: static labels + merged date headers ─────────────────────────
	ws.cell(1, 1, "Employee ID").font   = hdr_font
	ws.cell(1, 2, "Employee Name").font = hdr_font
	ws.cell(1, 3, "ESSL Biometric ID").font = hdr_font
	for c in range(1, 4):
		ws.cell(1, c).fill      = sub_fill
		ws.cell(1, c).alignment = center
		ws.merge_cells(start_row=1, start_column=c, end_row=2, end_column=c)

	for i, d in enumerate(dates):
		col_start = STICKY_COLS + 1 + i * 4
		col_end   = col_start + 3
		day_num   = d.split("-")[2].lstrip("0")
		dow       = dow_names[datetime.strptime(d, "%Y-%m-%d").weekday() + 1 if datetime.strptime(d, "%Y-%m-%d").weekday() < 6 else 0]
		dow       = dow_names[datetime.strptime(d, "%Y-%m-%d").isoweekday() % 7]
		label     = f"{day_num} {dow}"
		fill      = sun_fill if dow == "Sun" else date_fill

		cell = ws.cell(1, col_start, label)
		cell.font      = hdr_font
		cell.fill      = fill
		cell.alignment = center
		ws.merge_cells(start_row=1, start_column=col_start, end_row=1, end_column=col_end)

		for j, sub in enumerate(["Status", "In Time", "Out Time", "Hours"]):
			sc = ws.cell(2, col_start + j, sub)
			sc.font      = hdr_font
			sc.fill      = fill
			sc.alignment = center

	# ── Data rows ─────────────────────────────────────────────────────────
	for row_idx, emp in enumerate(employees, start=3):
		ws.cell(row_idx, 1, emp["employee"]).alignment   = center
		ws.cell(row_idx, 2, emp["employee_name"]).alignment = left_align
		ws.cell(row_idx, 3, emp["essl_id"] or "").alignment = center

		for i, d in enumerate(dates):
			att     = emp["attendance"].get(d) or {}
			col_start = STICKY_COLS + 1 + i * 4
			status  = att.get("status") or ""
			in_t    = _extract_time(att.get("punch_in"))
			out_t   = _extract_time(att.get("punch_out"))
			wh      = _extract_time(att.get("work_hours"))

			for j, val in enumerate([status, in_t, out_t, wh]):
				c = ws.cell(row_idx, col_start + j, val)
				c.alignment = center

	# ── Column widths ────────────────────────────────────────────────────
	ws.column_dimensions["A"].width = 16
	ws.column_dimensions["B"].width = 22
	ws.column_dimensions["C"].width = 16
	for i in range(len(dates) * 4):
		col_letter = get_column_letter(STICKY_COLS + 1 + i)
		ws.column_dimensions[col_letter].width = 10

	# ── Freeze first 3 columns + 2 header rows ───────────────────────────
	ws.freeze_panes = ws.cell(3, STICKY_COLS + 1)

	# ── Serialise to base64 ───────────────────────────────────────────────
	buf = io.BytesIO()
	wb.save(buf)
	buf.seek(0)
	return base64.b64encode(buf.read()).decode("utf-8")
