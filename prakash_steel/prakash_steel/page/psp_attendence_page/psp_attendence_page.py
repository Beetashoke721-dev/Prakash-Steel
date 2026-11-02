import base64
import io
from datetime import datetime, timedelta

import frappe
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from frappe.utils import getdate

from prakash_steel.utils.essl_biometric import _get_fallback_holiday_list, pick_shift_type
from prakash_steel.utils.whitelist_permissions import require_permission


def _fmt_duration(val) -> str:
	"""
	HH:MM:SS for a Time/timedelta value. str(timedelta) renders 24h+ as
	"1 day, 0:22:22", which the page then cut down to "day,"; total hours are
	kept instead (e.g. "24:22:22") so a bad punch pairing is visible as such.
	"""
	if not val:
		return ""
	if isinstance(val, timedelta):
		h, rem = divmod(int(val.total_seconds()), 3600)
		m, s = divmod(rem, 60)
		return f"{h:02d}:{m:02d}:{s:02d}"
	return str(val)


def _attendance_row(rec) -> dict:
	"""
	Build the {status, punch_in, punch_out, work_hours} row for one Attendance
	record. Prefers the ESSL custom punch fields; if those are blank but the
	record was marked Present manually (standard in_time/out_time set instead),
	falls back to those and derives work hours as the difference.
	"""
	status = rec["status"] or ""
	punch_in = str(rec["custom_punch_in_time"]) if rec["custom_punch_in_time"] else ""
	punch_out = str(rec["custom_punch_out_time"]) if rec["custom_punch_out_time"] else ""
	work_hours = _fmt_duration(rec["custom_work_hours"])

	if not punch_in and not punch_out and status == "Present" and rec["in_time"] and rec["out_time"]:
		punch_in = str(rec["in_time"])
		punch_out = str(rec["out_time"])
		diff_seconds = int((rec["out_time"] - rec["in_time"]).total_seconds())
		if diff_seconds > 0:
			h, rem = divmod(diff_seconds, 3600)
			m, s = divmod(rem, 60)
			work_hours = f"{h:02d}:{m:02d}:{s:02d}"

	return {
		"status": status,
		"punch_in": punch_in,
		"punch_out": punch_out,
		"work_hours": work_hours,
	}


def _holiday_map(employees, from_date, to_date, assignments=None, shift_holiday_lists=None) -> dict:
	"""
	{employee: {date_str: "WO" | "HO"}} for the range.

	The holiday list is chosen PER DAY, the same way the ESSL sync does it:
	the Shift Type for that day (a Shift Assignment covering the day, else the
	employee's Default Shift) → that shift's Holiday List → else the employee /
	company Holiday List. Weekly-off rows are "WO", every other holiday is "HO".

	`assignments` ({employee: [assignment dicts]}) and `shift_holiday_lists`
	({shift_type: holiday_list}) are optional prefetched maps; they are loaded
	from the DB when not given.

	Only days that have actually happened AND fall inside the employee's
	employment are returned: nothing before date_of_joining, nothing after
	relieving_date, nothing after today. A WO/HO is a day the calendar says
	is off, not a day the employee is paid for in advance.
	"""
	assignments = assignments or {}
	shift_holiday_lists = shift_holiday_lists or {}
	day_list = {e["name"]: _holiday_list_by_day(e, assignments, shift_holiday_lists, from_date, to_date) for e in employees}
	holiday_lists = {hl for days in day_list.values() for hl in days.values() if hl}
	if not holiday_lists:
		return {}

	rows = frappe.db.get_all(
		"Holiday",
		filters={
			"parent": ["in", list(holiday_lists)],
			"parenttype": "Holiday List",
			"holiday_date": ["between", [from_date, to_date]],
		},
		fields=["parent", "holiday_date", "weekly_off"],
	)
	by_list = {}
	for r in rows:
		by_list.setdefault(r["parent"], {})[str(r["holiday_date"])] = "WO" if r["weekly_off"] else "HO"

	# ISO date strings compare correctly, so the bounds can be plain strings.
	today = str(getdate())
	result = {}
	for e in employees:
		lo = str(e["date_of_joining"]) if e.get("date_of_joining") else str(from_date)
		lo = max(str(from_date), lo)
		hi_bounds = [str(to_date), today]
		if e.get("relieving_date"):
			hi_bounds.append(str(e["relieving_date"]))
		hi = min(hi_bounds)

		emp_days = {}
		for d, hl in day_list.get(e["name"], {}).items():
			if not hl or not (lo <= d <= hi):
				continue
			kind = by_list.get(hl, {}).get(d)
			if kind:
				emp_days[d] = kind
		if emp_days:
			result[e["name"]] = emp_days
	return result


def _holiday_list_by_day(employee, assignments, shift_holiday_lists, from_date, to_date) -> dict:
	"""{date_str: holiday_list_name or None} for one employee across the range."""
	start = datetime.strptime(from_date, "%Y-%m-%d").date()
	end = datetime.strptime(to_date, "%Y-%m-%d").date()
	emp_assignments = assignments.get(employee["name"], [])
	fallback = _get_fallback_holiday_list(employee["name"], from_date)

	days = {}
	for i in range((end - start).days + 1):
		day = start + timedelta(days=i)
		shift_type = pick_shift_type(emp_assignments, employee.get("default_shift"), day)
		hl = shift_holiday_lists.get(shift_type) if shift_type else None
		days[str(day)] = hl or fallback
	return days


def _summarise(attendance, holidays) -> dict:
	"""
	Per-employee summary counts.

	WO/HO is counted for a day WHENEVER the calendar says it's a weekoff or
	holiday (already limited to days that have passed and fall inside
	employment, see _holiday_map) — regardless of what attendance happened
	that day, exactly like A is counted for every Absent day regardless of
	whether it's also a holiday. The two aren't mutually exclusive: a single
	punch on a holiday (not enough to complete a shift) is marked BOTH
	Absent, informationally, and HO, because the holiday is still owed
	whether or not the employee showed up.

	On top of that:
	  P     – Present on an ordinary (non-holiday) working day
	  extra – Present on a WO/HO day: paid on top of the WO/HO itself, two
	          days' pay for one calendar day, same as if the employee had
	          the day off paid, then also came in and worked a normal day.
	  A     – Absent (any day with an Absent record, holiday or not)

	total_pay_days = P + WO + HO + extra  (A is never a pay day)
	"""
	p = a = extra = wo = ho = 0
	for date_str, att in attendance.items():
		status = att.get("status")
		is_holiday = date_str in holidays

		if status == "Present":
			if is_holiday:
				extra += 1
			else:
				p += 1
		elif status == "Absent":
			a += 1

		if is_holiday:
			if holidays[date_str] == "WO":
				wo += 1
			else:
				ho += 1
	return {
		"p": p,
		"wo": wo,
		"ho": ho,
		"extra": extra,
		"a": a,
		"total_pay_days": p + wo + ho + extra,
	}


def _shift_lookups(employee_names, from_date, to_date) -> tuple[dict, dict]:
	"""
	Prefetch everything the per-day shift resolution needs, in two queries:
	  assignments         – {employee: [submitted, Active Shift Assignments that
	                        could cover the range]}
	  shift_holiday_lists – {shift_type: holiday_list}
	"""
	if not employee_names:
		return {}, {}

	rows = frappe.db.get_all(
		"Shift Assignment",
		filters={
			"employee": ["in", employee_names],
			"docstatus": 1,
			"status": "Active",
			"start_date": ["<=", to_date],
		},
		fields=["employee", "shift_type", "start_date", "end_date"],
	)
	assignments = {}
	for r in rows:
		if r["end_date"] and str(r["end_date"]) < from_date:
			continue
		assignments.setdefault(r["employee"], []).append(r)

	shift_types = {r["shift_type"] for r in rows}
	default_rows = frappe.db.get_all(
		"Employee", filters={"name": ["in", employee_names]}, fields=["default_shift"], pluck="default_shift"
	)
	shift_types.update(s for s in default_rows if s)
	shift_holiday_lists = {}
	if shift_types:
		for st in frappe.db.get_all(
			"Shift Type", filters={"name": ["in", list(shift_types)]}, fields=["name", "holiday_list"]
		):
			shift_holiday_lists[st["name"]] = st["holiday_list"]
	return assignments, shift_holiday_lists


@frappe.whitelist()
def get_attendance_data(from_date, to_date, branch=None, employee=None) -> list[dict]:
	"""Return attendance data for all ESSL-mapped employees for the given date range."""
	require_permission("Attendance", "read")
	# Build date list
	start = datetime.strptime(from_date, "%Y-%m-%d").date()
	end = datetime.strptime(to_date, "%Y-%m-%d").date()
	dates = [str(start + timedelta(days=i)) for i in range((end - start).days + 1)]

	# An employee's row shows if they're Active, OR if they left but their
	# Relieving Date falls on/after this range's start - i.e. every month up
	# to and including the one they left in, never after. This is decided
	# PURELY from the Employee master's Relieving Date, never from whether an
	# Attendance record happens to exist: the ESSL sync used to keep
	# fabricating daily Absent records for employees long after they left
	# (see _get_employee_map's att_date filter, added after finding exactly
	# this - an employee relieved in June still had Absent records generated
	# for them in October). Gating visibility on "has an Attendance record"
	# would make the dashboard trust that same bad data; a stray record can
	# never make a Left employee reappear under this rule.
	emp_filters = {"custom_essl_employee_id": ["!=", ""]}
	if branch:
		emp_filters["branch"] = branch
	if employee:
		emp_filters["name"] = employee

	all_employees = frappe.db.get_all(
		"Employee",
		filters=emp_filters,
		fields=[
			"name",
			"employee_name",
			"branch",
			"custom_essl_employee_id",
			"status",
			"default_shift",
			"date_of_joining",
			"relieving_date",
		],
		order_by="name asc",
	)
	employees = [
		e
		for e in all_employees
		if e["status"] == "Active" or (e.get("relieving_date") and str(e["relieving_date"]) >= from_date)
	]

	if not employees:
		return {"dates": dates, "employees": []}

	emp_names = [e["name"] for e in employees]

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
			"in_time",
			"out_time",
		],
	)

	# Build lookup: {employee: {date_str: record}}
	att_map = {}
	for rec in attendance_records:
		emp = rec["employee"]
		dt = str(rec["attendance_date"])
		att_map.setdefault(emp, {})[dt] = _attendance_row(rec)

	assignments, shift_holiday_lists = _shift_lookups(emp_names, from_date, to_date)
	holiday_map = _holiday_map(
		employees, from_date, to_date, assignments=assignments, shift_holiday_lists=shift_holiday_lists
	)

	result = []
	for emp in employees:
		emp_att = att_map.get(emp["name"], {})
		holidays = holiday_map.get(emp["name"], {})
		attendance = {}
		for date_str in dates:
			attendance[date_str] = emp_att.get(
				date_str, {"status": "", "punch_in": "", "punch_out": "", "work_hours": ""}
			)
		result.append(
			{
				"employee": emp["name"],
				"employee_name": emp["employee_name"],
				"branch": emp["branch"] or "",
				"essl_id": emp["custom_essl_employee_id"] or "",
				"attendance": attendance,
				"holidays": holidays,
				"summary": _summarise(attendance, holidays),
			}
		)

	return {"dates": dates, "employees": result}


def _extract_time(val) -> int | None:
	"""Return HH:MM:SS from 'YYYY-MM-DD HH:MM:SS' or 'HH:MM:SS', else empty string."""
	if not val:
		return ""
	s = str(val).strip()
	parts = s.split(" ")
	return parts[1] if len(parts) > 1 else parts[0]


def _parse_minutes(val) -> int | None:
	"""Parse HH:MM:SS time string into total minutes (int)."""
	s = _extract_time(val)
	if not s:
		return 0
	parts = s.split(":")
	try:
		return int(parts[0]) * 60 + int(parts[1])
	except (IndexError, ValueError):
		return 0


@frappe.whitelist()
def download_attendance_excel(from_date, to_date, branch=None, employee=None) -> dict:
	"""Generate and return a base64-encoded .xlsx attendance report."""
	require_permission("Attendance", "read")
	data = get_attendance_data(from_date, to_date, branch=branch, employee=employee)
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

	STICKY_COLS = 4   # Employee ID | Employee Name | Branch | ESSL Biometric ID

	# ── Row 1: static labels + merged date headers ─────────────────────────
	ws.cell(1, 1, "Employee ID").font   = hdr_font
	ws.cell(1, 2, "Employee Name").font = hdr_font
	ws.cell(1, 3, "Branch").font = hdr_font
	ws.cell(1, 4, "ESSL Biometric ID").font = hdr_font
	for c in range(1, 5):
		ws.cell(1, c).fill      = sub_fill
		ws.cell(1, c).alignment = center
		ws.merge_cells(start_row=1, start_column=c, end_row=2, end_column=c)

	for i, d in enumerate(dates):
		col_start = STICKY_COLS + 1 + i * 4
		col_end   = col_start + 3
		day_num   = d.split("-")[2].lstrip("0")
		dt_obj    = datetime.strptime(d, "%Y-%m-%d")
		dow       = dow_names[dt_obj.isoweekday() % 7]
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

	# ── Summary header columns ────────────────────────────────────────────
	# (label, summary key, column width); "hrs" is derived from work hours
	SUMMARY_COLS = [
		("P", "p", 6),
		("WO", "wo", 6),
		("HO", "ho", 6),
		("Extra Pay Days", "extra", 10),
		("A", "a", 6),
		("Total Pay Days", "total_pay_days", 10),
		("Hrs", "hrs", 10),
	]
	sum_fill   = PatternFill("solid", fgColor="D9E1EC")
	sum_col_start = STICKY_COLS + 1 + len(dates) * 4
	ws.merge_cells(
		start_row=1, start_column=sum_col_start, end_row=1, end_column=sum_col_start + len(SUMMARY_COLS) - 1
	)
	sc = ws.cell(1, sum_col_start, "Summary")
	sc.font = hdr_font
	sc.fill = sum_fill
	sc.alignment = center
	for j, (lbl, _key, _width) in enumerate(SUMMARY_COLS):
		sc = ws.cell(2, sum_col_start + j, lbl)
		sc.font = hdr_font
		sc.fill = sum_fill
		sc.alignment = center

	# ── Data rows ─────────────────────────────────────────────────────────
	p_fill = PatternFill("solid", fgColor="E2F8EC")
	a_fill = PatternFill("solid", fgColor="FDE8E8")
	p_font = Font(bold=True, size=10, color="1A6B3C")
	a_font = Font(bold=True, size=10, color="9B1C1C")

	for row_idx, emp in enumerate(employees, start=3):
		ws.cell(row_idx, 1, emp["employee"]).alignment   = center
		ws.cell(row_idx, 2, emp["employee_name"]).alignment = left_align
		ws.cell(row_idx, 3, emp.get("branch") or "").alignment = left_align
		ws.cell(row_idx, 4, emp["essl_id"] or "").alignment = center

		emp_total_mins = 0
		for i, d in enumerate(dates):
			att     = emp["attendance"].get(d) or {}
			col_start = STICKY_COLS + 1 + i * 4
			status  = att.get("status") or ""
			in_t    = _extract_time(att.get("punch_in"))
			out_t   = _extract_time(att.get("punch_out"))
			wh      = _extract_time(att.get("work_hours"))

			if not status:
				status = emp["holidays"].get(d, "")
			emp_total_mins += _parse_minutes(att.get("work_hours"))

			for j, val in enumerate([status, in_t, out_t, wh]):
				c = ws.cell(row_idx, col_start + j, val)
				c.alignment = center

		# Write summary cells
		summary = dict(emp["summary"])
		summary["hrs"] = f"{emp_total_mins // 60}h {emp_total_mins % 60:02d}m" if emp_total_mins else ""
		for j, (_lbl, key, _width) in enumerate(SUMMARY_COLS):
			c = ws.cell(row_idx, sum_col_start + j, summary[key] or "")
			c.alignment = center
			if key == "a":
				c.font, c.fill = a_font, a_fill
			elif key == "hrs":
				c.font = Font(bold=True, size=10, color="1A3A8F")
				c.fill = PatternFill("solid", fgColor="EBF5FF")
			elif key == "total_pay_days":
				c.font = Font(bold=True, size=10, color="1A3A8F")
			else:
				c.font, c.fill = p_font, p_fill

	# ── Column widths ────────────────────────────────────────────────────
	ws.column_dimensions["A"].width = 16
	ws.column_dimensions["B"].width = 22
	ws.column_dimensions["C"].width = 18
	ws.column_dimensions["D"].width = 16
	for i in range(len(dates) * 4):
		col_letter = get_column_letter(STICKY_COLS + 1 + i)
		ws.column_dimensions[col_letter].width = 10
	for j, (_lbl, _key, width) in enumerate(SUMMARY_COLS):
		ws.column_dimensions[get_column_letter(sum_col_start + j)].width = width

	# ── Freeze first 4 columns + 2 header rows ───────────────────────────
	ws.freeze_panes = ws.cell(3, STICKY_COLS + 1)

	# ── Serialise to base64 ───────────────────────────────────────────────
	buf = io.BytesIO()
	wb.save(buf)
	buf.seek(0)
	return base64.b64encode(buf.read()).decode("utf-8")
