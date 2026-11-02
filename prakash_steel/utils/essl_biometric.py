"""
ESSL Biometric Integration
--------------------------
Fetches attendance punch logs from ESSL SOAP API for all configured devices,
determines IN/OUT per employee per day, creates Employee Checkin records,
and marks Attendance (Present) in ERPNext.

Employee mapping: Employee.custom_essl_employee_id  ←→  ESSL user_id
Settings:         ESSL Biometric Settings  (Single DocType)
"""

import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta

import frappe
import requests
from frappe.utils import get_time
from frappe.utils import now_datetime as _now


# ---------------------------------------------------------------------------
# SOAP API helpers
# ---------------------------------------------------------------------------


def _build_soap_body(from_dt, to_dt, serial, username, password) -> str:
	return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetTransactionsLog xmlns="http://tempuri.org/">
      <FromDateTime>{from_dt}</FromDateTime>
      <ToDateTime>{to_dt}</ToDateTime>
      <SerialNumber>{serial}</SerialNumber>
      <UserName>{username}</UserName>
      <UserPassword>{password}</UserPassword>
      <strDataList></strDataList>
    </GetTransactionsLog>
  </soap:Body>
</soap:Envelope>"""


def _fetch_device_logs(api_url, serial, from_dt, to_dt, username, password) -> list:
	"""Call ESSL SOAP API and return raw XML response text."""
	soap_body = _build_soap_body(from_dt, to_dt, serial, username, password)
	headers = {
		"Content-Type": "text/xml; charset=utf-8",
		"SOAPAction": "http://tempuri.org/GetTransactionsLog",
	}
	response = requests.post(api_url, data=soap_body.encode("utf-8"), headers=headers, timeout=30)
	response.raise_for_status()
	return response.text


def _parse_logs(xml_text, device_serial, device_label) -> list:
	"""
	Parse ESSL XML response and return list of punch dicts:
	  { user_id, timestamp (datetime), device_serial, device_label }
	"""
	root = ET.fromstring(xml_text)
	ns = {
		"soap": "http://schemas.xmlsoap.org/soap/envelope/",
		"t": "http://tempuri.org/",
	}

	result_node = root.find(".//t:GetTransactionsLogResult", ns)
	data_node = root.find(".//t:strDataList", ns)

	result_text = result_node.text if result_node is not None else "No result"
	frappe.logger().info(f"[ESSL] {device_label} ({device_serial}): {result_text}")

	if data_node is None or not (data_node.text or "").strip():
		return []

	punches = []
	for line in data_node.text.strip().splitlines():
		parts = line.strip().split("\t")
		if len(parts) < 2:
			continue
		user_id = parts[0].strip()
		ts_str = parts[1].strip()
		try:
			ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
		except ValueError:
			continue
		punches.append(
			{
				"user_id": user_id,
				"timestamp": ts,
				"device_serial": device_serial,
				"device_label": device_label,
			}
		)
	return punches


MOBILE_SOURCE_LABEL = "Mobile / All Sources"


def _dedupe_punches(all_punches) -> list:
	"""
	Drop repeats of the same (user, timestamp). The blank-serial call may also
	echo punches already returned by a device call; the device label wins since
	device punches are listed first. The IN/OUT text ESSL sends is never used —
	only the times matter (first of the day = IN, last = OUT).
	"""
	seen = set()
	unique = []
	for p in all_punches:
		key = (p["user_id"], p["timestamp"])
		if key in seen:
			continue
		seen.add(key)
		unique.append(p)
	return unique


# ---------------------------------------------------------------------------
# Group punches → IN/OUT checkins + attendance summary
# ---------------------------------------------------------------------------


def pick_shift_type(assignments, default_shift, for_date):
	"""
	Shift Type that applies on calendar date `for_date`, decided by date only.

	`assignments` is one employee's submitted, Active Shift Assignments as
	dicts {shift_type, start_date, end_date} (end_date may be None = open
	ended). An assignment covering `for_date` wins — if several cover it, the
	one that started most recently. Only when none covers the date does the
	Employee's `default_shift` apply.
	"""
	covering = [
		a
		for a in assignments
		if a["start_date"] <= for_date and (not a["end_date"] or a["end_date"] >= for_date)
	]
	if covering:
		return max(covering, key=lambda a: a["start_date"])["shift_type"]
	return default_shift or None


def _get_shift_type_for_date(employee, for_date):
	"""
	DB-backed `pick_shift_type` for one employee and one date.

	Deliberately NOT filtered on status == "Active": HRMS's daily
	`mark_expired_shift_assignments_as_inactive` flips every assignment whose
	end_date has passed to "Inactive". The sync only ever looks at past dates,
	so a one-day Night Shift assignment for yesterday-but-one is already
	Inactive when the morning-after punch is grouped — ignoring it made that
	checkout land on the next day as its IN (e.g. 08:14 IN -> next-day 08:36
	OUT = 24h 22m). Cancelled assignments are still excluded via docstatus.
	"""
	assignments = frappe.get_all(
		"Shift Assignment",
		filters={
			"employee": employee,
			"docstatus": 1,
			"start_date": ["<=", for_date],
		},
		fields=["shift_type", "start_date", "end_date"],
	)
	default_shift = frappe.db.get_value("Employee", employee, "default_shift")
	return pick_shift_type(assignments, default_shift, for_date)


def _night_shift_window(shift_type, day):
	"""
	(start_datetime, actual_end_datetime) of the shift instance that starts on
	`day`, or None if the Shift Type is not an overnight shift. Overnight means
	end_time is earlier than start_time, e.g. Night Shift 18:00 -> 17:00 next day.
	"""
	from hrms.hr.doctype.shift_assignment.shift_assignment import get_shift_details

	st = frappe.db.get_value("Shift Type", shift_type, ["start_time", "end_time"], as_dict=True)
	if not st or not st.start_time or not st.end_time:
		return None
	start_t, end_t = get_time(st.start_time), get_time(st.end_time)
	if not end_t < start_t:
		return None
	details = get_shift_details(shift_type, for_timestamp=datetime.combine(day, start_t))
	if not details or not details.get("start_datetime"):
		return None
	return details.start_datetime, details.actual_end


def _previous_night_shift_date(employee, ts):
	"""
	If `ts` falls inside the previous calendar day's overnight shift (its
	start through its check-out end, incl. allowed check-out grace), return
	that previous day. Otherwise None.
	"""
	previous_day = ts.date() - timedelta(days=1)
	shift_type = _get_shift_type_for_date(employee, previous_day)
	if not shift_type:
		return None
	window = _night_shift_window(shift_type, previous_day)
	if window and window[0] <= ts <= window[1]:
		return previous_day
	return None


def _get_employee_shift_date(employee, ts):
	"""
	Resolve the shift-day (a `date`) that punch time `ts` belongs to for `employee`.

	The Shift Type is chosen per calendar day (see `_get_shift_type_for_date`):
	a Shift Assignment covering that day, otherwise the Employee's default
	shift. Its start for the punch is then computed by HRMS's shift timing.

	For a normal shift this is just `ts`'s own calendar date. For an overnight
	shift (e.g. Night Shift 18:00 -> 06:00), a punch made after midnight is the
	shift's trailing OUT, so the start date of the shift it falls into is used.

	If no shift applies at all, falls back to `ts`'s own calendar date.
	"""
	try:
		from hrms.hr.doctype.shift_assignment.shift_assignment import get_shift_details

		# A punch in the early hours can be the check-out of the PREVIOUS day's
		# overnight shift. That shift is governed by the previous day's
		# assignment, not by whatever shift the next day happens to have.
		previous_day = _previous_night_shift_date(employee, ts)
		if previous_day:
			return previous_day

		shift_type = _get_shift_type_for_date(employee, ts.date())
		if shift_type:
			details = get_shift_details(shift_type, for_timestamp=ts)
			start_datetime = details.get("start_datetime") if details else None
			actual_end = details.get("actual_end") if details else None
			# HRMS hands back the PREVIOUS day's shift for any punch before
			# today's check-in window opens, even hours after that shift's
			# check-out window closed (e.g. General 1 10:00-18:30, 07:26 next
			# morning). Only fold back when the punch is inside that window;
			# otherwise a missed checkout pairs with tomorrow's first punch
			# and shows ~20h of work.
			#
			# That alone isn't enough for a shift assigned for ONE day only
			# (e.g. a one-off Night Shift just for today): a punch a few
			# minutes before the begin-check-in grace opens (25 min here) is
			# computed by HRMS as "yesterday's shift, not today's" purely
			# from the shift TYPE's own start/end times - it has no idea
			# yesterday's actual assignment is a different shift entirely
			# (or none). Confirm the earlier day genuinely resolves to this
			# SAME shift type (an assignment or default that really covers
			# it) before trusting the fold-back; otherwise this is just an
			# early arrival for TODAY that missed the grace window, and
			# belongs on its own day, not a shift instance that doesn't
			# exist on the day HRMS's math pushed it onto.
			if start_datetime and (
				start_datetime.date() == ts.date()
				or (
					actual_end
					and ts <= actual_end
					and _get_shift_type_for_date(employee, start_datetime.date()) == shift_type
				)
			):
				return start_datetime.date()
	except Exception as e:
		frappe.logger().warning(f"[ESSL] Shift-date lookup failed for {employee} at {ts}: {e}")
	return ts.date()


def _process_punches(all_punches, employee_map=None, target_date=None) -> dict:
	"""
	Group punches by (user_id, shift-day) across all devices — NOT simply by
	the calendar date each punch happened to land on. This matters for an
	overnight shift: its trailing OUT punch (e.g. ~06:00 the next morning for
	an 18:00 -> 06:00 Night Shift) is folded back onto the day the shift
	started, via `_get_employee_shift_date`, so it pairs with that day's IN
	instead of showing up as a stray single punch on the following day.

	Within a shift-day group, punches are split by which side of the shift
	they actually fall on, not just by chronological first/last:
	  - "same-day" punches: own calendar date == the shift-day (the evening
	    side of an overnight shift, or the whole thing for an ordinary
	    same-day shift). The EARLIEST one is the IN.
	  - "next-day" punches: folded back from the following calendar date (the
	    morning-after side of an overnight shift). The LATEST one is the OUT.
	If there are no next-day punches, the LATEST same-day punch (if it's a
	distinct entry) is used as OUT instead — this is what makes an ordinary
	same-day shift's first/last pairing keep working exactly as before.

	This distinction matters when one side is missing entirely:
	  - Same-day punch(es) only, no next-day punch -> IN filled, OUT blank
	    (unchanged from before: a lone evening punch with no checkout yet).
	  - Next-day punch(es) only, NO same-day punch at all (e.g. the employee
	    never punched in that evening) -> OUT filled, IN left blank, and the
	    record still lands on the shift-START date, not the date the
	    checkout physically happened on. Before this split, an orphaned
	    next-day-only punch was mislabelled as an "IN" (since it was simply
	    the sole entry in the group), and a *cluster* of several such
	    unmatched next-day punches (e.g. multiple morning taps) was
	    mispaired into a fabricated first/last "shift" — falsely marking a
	    day Present with a few minutes of fictitious working hours. Neither
	    happens now: `_create_attendance`/`_insert_and_submit_attendance`
	    only mark Present when BOTH an in_time and an out_time are present.

	`employee_map` (essl_id -> {name, company}) is needed to look up the
	Employee's shift; punches from an unmapped essl id fall back to grouping
	by the punch's own calendar date (they'll be reported as failed further
	down the pipeline anyway, same as before) — every punch is then
	"same-day" by definition, which degrades to the original first/last
	pairing.

	`target_date` ("YYYY-MM-DD"), if given, drops any shift-day group that
	doesn't match it. The raw fetch window in `sync_essl_checkins` reaches
	into the next morning to catch overnight OUT punches, which can also pull
	in a few of the *next* day's ordinary punches (e.g. a day-shift employee
	clocking in early) — those belong to tomorrow's run, not this one.

	Returns:
	  checkins  – list of { user_id, timestamp (str), log_type, device_label }
	  attendance – list of { user_id, date (str), in_time (str|None), out_time (str|None), working_hours (float) }
	"""
	employee_map = employee_map or {}
	shift_date_cache: dict = {}

	def _shift_date(p):
		emp = employee_map.get(p["user_id"])
		if not emp:
			return p["timestamp"].date()
		cache_key = (emp["name"], p["timestamp"])
		if cache_key not in shift_date_cache:
			shift_date_cache[cache_key] = _get_employee_shift_date(emp["name"], p["timestamp"])
		return shift_date_cache[cache_key]

	grouped = defaultdict(list)
	for p in all_punches:
		shift_date = _shift_date(p)
		date_key = shift_date.strftime("%Y-%m-%d")
		if target_date and date_key != target_date:
			continue
		# Tag each punch with which side of the shift-day it's really on, so
		# a lone/leftover punch never gets mislabelled as the wrong end.
		p = {**p, "is_same_day": p["timestamp"].date() == shift_date}
		grouped[(p["user_id"], date_key)].append(p)

	checkins = []
	attendance = []

	for (user_id, date_key), entries in grouped.items():
		same_day = sorted((e for e in entries if e["is_same_day"]), key=lambda x: x["timestamp"])
		next_day = sorted((e for e in entries if not e["is_same_day"]), key=lambda x: x["timestamp"])

		in_entry = same_day[0] if same_day else None
		if next_day:
			out_entry = next_day[-1]
		elif len(same_day) > 1:
			out_entry = same_day[-1]
		else:
			out_entry = None

		# --- Employee Checkin records ---
		if in_entry:
			checkins.append(
				{
					"user_id": user_id,
					"timestamp": in_entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
					"log_type": "IN",
					"device_label": in_entry["device_label"],
				}
			)
		if out_entry:
			checkins.append(
				{
					"user_id": user_id,
					"timestamp": out_entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
					"log_type": "OUT",
					"device_label": out_entry["device_label"],
				}
			)

		# --- Attendance summary ---
		working_hours = 0.0
		if in_entry and out_entry:
			diff = out_entry["timestamp"] - in_entry["timestamp"]
			working_hours = round(diff.total_seconds() / 3600, 2)

		attendance.append(
			{
				"user_id": user_id,
				"date": date_key,
				"in_time": in_entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if in_entry else None,
				"out_time": out_entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if out_entry else None,
				"working_hours": working_hours,
			}
		)

	return checkins, attendance


# ---------------------------------------------------------------------------
# Employee map
# ---------------------------------------------------------------------------


def _get_employee_map(att_date: str) -> dict:
	"""
	Return dict { essl_id_str: {name, company} } for employees who were still
	employed on `att_date` ("YYYY-MM-DD") - either currently Active, or not
	Active but with a Relieving Date on or after `att_date` (they hadn't left
	yet as of that day).

	Without this, an employee who has left keeps getting processed by every
	future sync forever: Employee.status isn't checked at all by ERPNext's
	own safety net (hrms.hr.utils.validate_active_employee only blocks status
	"Inactive", not "Left" - the normal status for someone who has actually
	departed), so nothing stops Attendance/Employee Checkin records from
	being fabricated for them indefinitely, well past their last real day.
	That's exactly what happened to an employee relieved in August, who kept
	getting fresh daily Absent records in October before this filter existed.

	An employee who isn't Active and has no Relieving Date at all is excluded
	outright - there's no date to trust, so the safer default is to stop
	creating new records for them rather than guess.
	"""
	rows = frappe.db.get_all(
		"Employee",
		filters={"custom_essl_employee_id": ["!=", ""]},
		fields=["name", "custom_essl_employee_id", "company", "status", "relieving_date"],
	)
	employed = [
		r
		for r in rows
		if r.status == "Active" or (r.relieving_date and str(r.relieving_date) >= att_date)
	]
	return {
		str(r.custom_essl_employee_id).strip(): {"name": r.name, "company": r.company}
		for r in employed
		if r.custom_essl_employee_id
	}


# ---------------------------------------------------------------------------
# Create Employee Checkins
# ---------------------------------------------------------------------------


def _create_checkins(checkins, employee_map) -> dict:
	success = failed = skipped = 0

	for log in checkins:
		emp = employee_map.get(log["user_id"])
		if not emp:
			frappe.logger().warning(f"[ESSL] No employee for ESSL ID '{log['user_id']}' – skipping checkin")
			failed += 1
			continue

		if frappe.db.exists("Employee Checkin", {"employee": emp["name"], "time": log["timestamp"]}):
			skipped += 1
			continue

		try:
			# Permission decision: biometric sync runs either as a scheduled job (no
			# user) or via manual_sync(), which already enforces Employee Checkin
			# create/write permission. Records originate from the device, not the user.
			frappe.get_doc(
				{
					"doctype": "Employee Checkin",
					"employee": emp["name"],
					"time": log["timestamp"],
					"log_type": log["log_type"],
					"device_id": log["device_label"],
				}
			).insert(ignore_permissions=True)
			success += 1
		except Exception as e:
			frappe.logger().error(f"[ESSL] Checkin failed for {emp['name']} at {log['timestamp']}: {e}")
			failed += 1

	frappe.db.commit()
	frappe.logger().info(f"[ESSL] Checkins → created: {success}, skipped: {skipped}, failed: {failed}")
	return {"checkin_success": success, "checkin_skipped": skipped, "checkin_failed": failed}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seconds_to_hhmmss(total_seconds) -> str:
	"""Convert total seconds to HH:MM:SS string for Time field."""
	h = total_seconds // 3600
	m = (total_seconds % 3600) // 60
	s = total_seconds % 60
	return f"{h:02d}:{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Create / update Attendance
# ---------------------------------------------------------------------------


def _create_attendance(attendance_list, employee_map) -> dict:
	success = skipped = failed = 0

	for rec in attendance_list:
		emp = employee_map.get(rec["user_id"])
		if not emp:
			failed += 1
			continue

		employee = emp["name"]
		company = emp["company"]
		att_date = rec["date"]

		existing = frappe.db.get_value(
			"Attendance",
			{"employee": employee, "attendance_date": att_date, "docstatus": ["!=", 2]},
			["name", "docstatus"],
			as_dict=True,
		)

		if existing:
			# Already exists — update status + custom time fields. Present
			# requires BOTH ends of the shift (a lone punch on either side,
			# in or out, is Absent — see _process_punches for why an
			# unmatched out_time with no in_time is still valid data worth
			# recording, just not a completed shift).
			has_in = bool(rec["in_time"])
			has_out = bool(rec["out_time"])
			in_dt = datetime.strptime(rec["in_time"], "%Y-%m-%d %H:%M:%S") if has_in else None
			out_dt = datetime.strptime(rec["out_time"], "%Y-%m-%d %H:%M:%S") if has_out else None
			wh = _seconds_to_hhmmss(int((out_dt - in_dt).total_seconds())) if (in_dt and out_dt and out_dt > in_dt) else None
			frappe.db.set_value("Attendance", existing.name, "status", "Present" if (has_in and has_out) else "Absent")
			frappe.db.set_value("Attendance", existing.name, "custom_work_hours", wh)
			if has_in:
				frappe.db.set_value("Attendance", existing.name, "custom_punch_in_time", rec["in_time"])
			else:
				frappe.db.sql(
					"UPDATE `tabAttendance` SET `custom_punch_in_time` = NULL WHERE `name` = %s",
					existing.name,
				)
			if has_out:
				frappe.db.set_value("Attendance", existing.name, "custom_punch_out_time", rec["out_time"])
			else:
				frappe.db.sql(
					"UPDATE `tabAttendance` SET `custom_punch_out_time` = NULL WHERE `name` = %s",
					existing.name,
				)
			skipped += 1
			continue

		try:
			_insert_and_submit_attendance(employee, company, att_date, rec)
			success += 1
		except Exception as e:
			frappe.logger().error(f"[ESSL] Attendance failed for {employee} on {att_date}: {e}")
			failed += 1

	frappe.db.commit()
	frappe.logger().info(
		f"[ESSL] Attendance → created/submitted: {success}, already existed: {skipped}, failed: {failed}"
	)
	return {"att_success": success, "att_skipped": skipped, "att_failed": failed}


def _insert_and_submit_attendance(employee, company, att_date, rec) -> None:
	"""Create a submitted Attendance record with custom punch time fields.
	Present requires BOTH an in_time and an out_time — a punch on only one
	side (including an unmatched out_time with no in_time; see
	_process_punches) is Absent."""
	has_in = bool(rec["in_time"])
	has_out = bool(rec["out_time"])
	status = "Present" if (has_in and has_out) else "Absent"

	in_dt = datetime.strptime(rec["in_time"], "%Y-%m-%d %H:%M:%S") if has_in else None
	out_dt = datetime.strptime(rec["out_time"], "%Y-%m-%d %H:%M:%S") if has_out else None
	working_hours = (
		_seconds_to_hhmmss(int((out_dt - in_dt).total_seconds())) if (in_dt and out_dt and out_dt > in_dt) else None
	)

	doc_data = {
		"doctype": "Attendance",
		"employee": employee,
		"attendance_date": att_date,
		"company": company,
		"status": status,
		"custom_punch_in_time": rec["in_time"],
	}
	if has_out:
		doc_data["custom_punch_out_time"] = rec["out_time"]

	doc = frappe.get_doc(doc_data)
	# Permission decision: Attendance is generated from synced device punches in a
	# scheduled/gated context (see manual_sync permission checks); not user-entered.
	doc.insert(ignore_permissions=True)
	doc.submit()

	# Always write via db.set_value to bypass field defaults set by Frappe
	frappe.db.set_value("Attendance", doc.name, "custom_work_hours", working_hours)
	if has_out:
		frappe.db.set_value("Attendance", doc.name, "custom_punch_out_time", rec["out_time"])
	else:
		# frappe.db.set_value skips None in dicts — use raw SQL to force NULL
		frappe.db.sql(
			"UPDATE `tabAttendance` SET `custom_punch_out_time` = NULL WHERE `name` = %s",
			doc.name,
		)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def sync_essl_checkins(from_dt=None, to_dt=None) -> None:
	"""
	Fetch punch logs from all active ESSL devices, create Employee Checkins,
	and mark Attendance as Present.

	`from_dt`'s date is the single "attendance date" (att_date) this call closes
	out. The raw ESSL fetch always reaches past `to_dt` into the following
	morning so an overnight shift's OUT punch (after midnight) is captured;
	see the night_shift_reach comment below and `_process_punches`.

	Args:
		from_dt (str | None): "YYYY-MM-DD HH:MM:SS" – defaults to yesterday 00:00:00
		to_dt   (str | None): "YYYY-MM-DD HH:MM:SS" – defaults to yesterday 23:59:59
	"""
	settings = frappe.get_single("ESSL Biometric Settings")

	if not settings.api_url or not settings.username or not settings.password:
		frappe.logger().warning("[ESSL] ESSL Biometric Settings incomplete – aborting sync.")
		return

	active_devices = [d for d in settings.devices if d.is_active]
	if not active_devices:
		frappe.logger().warning("[ESSL] No active devices configured – aborting sync.")
		return

	# Default: yesterday's full day
	if not from_dt or not to_dt:
		yesterday = _now() - timedelta(days=1)
		from_dt = from_dt or yesterday.strftime("%Y-%m-%d") + " 00:00:00"
		to_dt = to_dt or yesterday.strftime("%Y-%m-%d") + " 23:59:59"

	att_date = from_dt.split(" ")[0]  # "YYYY-MM-DD"
	att_date_obj = datetime.strptime(att_date, "%Y-%m-%d")

	# An overnight shift (e.g. Night Shift 18:00 -> 06:00, or a long shift
	# like 20:00 -> 14:00 the next day) punches OUT well into the next day,
	# so a fetch window that stops at att_date 23:59:59 would never see that
	# OUT punch at all. Always reach through the entire following day; this
	# is capped at "now" below, so it only ever pulls punches that already
	# exist, and _process_punches() (via target_date) folds any such tail
	# punch back onto att_date using the employee's shift, and drops
	# anything that actually belongs to the next day instead (e.g. a
	# day-shift employee's early punch-in caught by the wider window).
	# Note this window alone doesn't fix a shift that checks out AFTER this
	# function happens to run — that's why sync_essl_checkins is scheduled
	# twice daily (10:30 AM and 6 PM; see hooks.py), both re-processing
	# "yesterday" so a late OUT punch missed by the morning run is picked
	# up and flips that employee from Absent to Present by the evening run.
	night_shift_reach = att_date_obj + timedelta(days=2)
	fetch_to_dt = max(datetime.strptime(to_dt, "%Y-%m-%d %H:%M:%S"), night_shift_reach)
	fetch_to_dt = min(fetch_to_dt, _now())  # never ask ESSL for the future

	# Convert to ESSL date format (YYYY/MM/DD HH:MM)
	essl_from = datetime.strptime(from_dt, "%Y-%m-%d %H:%M:%S").strftime("%Y/%m/%d %H:%M")
	essl_to = fetch_to_dt.strftime("%Y/%m/%d %H:%M")

	password = settings.get_password("password")

	frappe.logger().info(
		f"[ESSL] Starting sync | range: {essl_from} → {essl_to} | devices: {len(active_devices)}"
	)

	# Each configured device, plus one call with a blank serial number: ESSL
	# returns the mobile-app punches for that (and is not tied to any device).
	sources = [(d.serial_number, d.device_label or d.serial_number) for d in active_devices]
	sources.append(("", MOBILE_SOURCE_LABEL))

	all_punches = []
	for serial, label in sources:
		try:
			xml_text = _fetch_device_logs(
				settings.api_url,
				serial,
				essl_from,
				essl_to,
				settings.username,
				password,
			)
			punches = _parse_logs(xml_text, serial, label)
			frappe.logger().info(f"[ESSL] {label}: {len(punches)} punches")
			all_punches.extend(punches)
		except Exception as e:
			frappe.logger().error(f"[ESSL] Error fetching {label} ({serial}): {e}")

	all_punches = _dedupe_punches(all_punches)
	employee_map = _get_employee_map(att_date)

	frappe.logger().info(f"[ESSL] Total punches across all devices: {len(all_punches)}")

	if not all_punches:
		_update_last_synced()
		absent_result = _mark_absent_employees(set(), employee_map, att_date)
		return {"message": "No punches found for the given date range", **absent_result}

	checkins, attendance_list = _process_punches(all_punches, employee_map, target_date=att_date)

	checkin_result = _create_checkins(checkins, employee_map)
	att_result = _create_attendance(attendance_list, employee_map)

	punched_user_ids = {rec["user_id"] for rec in attendance_list}
	absent_result = _mark_absent_employees(punched_user_ids, employee_map, att_date)

	_update_last_synced()
	return {**checkin_result, **att_result, **absent_result}


# ---------------------------------------------------------------------------
# Scheduler entry points
# ---------------------------------------------------------------------------
#
# Frappe's scheduler keys "Scheduled Job Type" by METHOD NAME ALONE (see
# frappe/core/doctype/scheduled_job_type/scheduled_job_type.py,
# insert_single_event: `frappe.db.exists("Scheduled Job Type", {"method": event})`).
# So the same method can't be registered under two different cron entries in
# hooks.py — whichever entry a migrate processes last overwrites the other's
# cron_format on the SAME record, and `clear_events` then deletes whichever
# cron_format no longer matches. That's why only one of the two daily runs
# was ever actually scheduled in production, flipping between them on every
# migrate. Two distinct method names avoids the collision entirely.


def sync_essl_checkins_morning() -> None:
	"""10:30 AM scheduled run - see hooks.py. Just calls sync_essl_checkins();
	exists only so this cron has a method name of its own (see note above)."""
	sync_essl_checkins()


def sync_essl_checkins_evening() -> None:
	"""6 PM scheduled run - see hooks.py. Re-processes the same "yesterday" the
	morning run did, picking up any checkout that hadn't happened yet at
	10:30 AM. Just calls sync_essl_checkins(); exists only so this cron has a
	method name of its own (see note above)."""
	sync_essl_checkins()


# ---------------------------------------------------------------------------
# Mark Absent for employees with no punch data
# ---------------------------------------------------------------------------


def _mark_absent_employees(punched_user_ids, employee_map, att_date) -> dict:
	"""
	For every ESSL-mapped employee NOT in punched_user_ids, create a submitted
	Absent attendance record (if one doesn't already exist for that date).

	Employees whose day falls on a holiday (per the Holiday List on their shift,
	falling back to the employee/company Holiday List) are left untouched — no
	punch on a weekly-off / holiday must never read as "Absent". If the device
	*did* report a punch for such a day, that employee is in punched_user_ids and
	is handled by _create_attendance instead.
	"""
	success = skipped = failed = holiday_skipped = 0
	hl_cache: dict = {}
	holiday_cache: dict = {}

	for user_id, emp in employee_map.items():
		if user_id in punched_user_ids:
			continue  # already handled by _create_attendance

		employee = emp["name"]
		company = emp["company"]

		existing = frappe.db.get_value(
			"Attendance",
			{"employee": employee, "attendance_date": att_date, "docstatus": ["!=", 2]},
			"name",
		)
		if existing:
			skipped += 1
			continue

		if _is_holiday_for_employee(employee, att_date, hl_cache, holiday_cache):
			holiday_skipped += 1
			continue

		try:
			doc = frappe.get_doc(
				{
					"doctype": "Attendance",
					"employee": employee,
					"attendance_date": att_date,
					"company": company,
					"status": "Absent",
				}
			)
			# Permission decision: system-generated "Absent" Attendance from the
			# scheduled/gated biometric sync; bypasses interactive permission model.
			doc.insert(ignore_permissions=True)
			doc.submit()
			success += 1
		except Exception as e:
			frappe.logger().error(f"[ESSL] Absent marking failed for {employee} on {att_date}: {e}")
			failed += 1

	frappe.db.commit()
	frappe.logger().info(
		f"[ESSL] Absent → marked: {success}, skipped: {skipped}, "
		f"holiday-skipped: {holiday_skipped}, failed: {failed}"
	)
	return {
		"absent_success": success,
		"absent_skipped": skipped,
		"absent_holiday_skipped": holiday_skipped,
		"absent_failed": failed,
	}


# ---------------------------------------------------------------------------
# Holiday-list resolution (skip "Absent" on weekly-offs / holidays)
# ---------------------------------------------------------------------------


def _get_employee_holiday_list(employee, att_date) -> str | None:
	"""
	Resolve the Holiday List that applies to `employee` on `att_date`.

	Order (matches how the site is set up — shift carries the holiday list):
	  1. Holiday List on the employee's Shift Type for that date
	     (Shift Assignment for the date, else the employee's default shift)
	  2. Holiday List assigned to the employee, else their company default
	"""
	try:
		# Shift Type for this calendar day: Shift Assignment covering the day,
		# else the Employee's default shift (see _get_shift_type_for_date).
		shift_type_name = _get_shift_type_for_date(employee, datetime.strptime(att_date, "%Y-%m-%d").date())
		if shift_type_name:
			hl = frappe.db.get_value("Shift Type", shift_type_name, "holiday_list")
			if hl:
				return hl
	except Exception as e:
		frappe.logger().warning(f"[ESSL] Shift lookup failed for {employee} on {att_date}: {e}")

	return _get_fallback_holiday_list(employee, att_date)


def _get_fallback_holiday_list(employee, att_date) -> str | None:
	"""Holiday List on the Employee, else the company default (no shift involved)."""
	try:
		from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

		return get_holiday_list_for_employee(employee, False, att_date) or None
	except Exception:
		return None


def _is_holiday_for_employee(employee, att_date, hl_cache, holiday_cache) -> bool:
	"""True if `att_date` is a holiday for `employee`. Caches per (employee, date)
	and per (holiday_list, date) to keep the sync loop cheap. Keyed by date too,
	because the employee's shift (and so its holiday list) can change day to day."""
	if (employee, att_date) not in hl_cache:
		hl_cache[(employee, att_date)] = _get_employee_holiday_list(employee, att_date)
	holiday_list = hl_cache[(employee, att_date)]

	if not holiday_list:
		return False

	key = (holiday_list, att_date)
	if key not in holiday_cache:
		holiday_cache[key] = bool(
			frappe.db.exists("Holiday", {"parent": holiday_list, "holiday_date": att_date})
		)
	return holiday_cache[key]


def _update_last_synced() -> None:
	frappe.db.set_single_value(
		"ESSL Biometric Settings", "last_synced_on", _now().strftime("%Y-%m-%d %H:%M:%S")
	)


# ---------------------------------------------------------------------------
# Whitelisted API – manual trigger from UI / console
# ---------------------------------------------------------------------------


@frappe.whitelist()
def manual_sync(from_dt=None, to_dt=None) -> None:
	"""Trigger ESSL sync manually. Defaults to yesterday if no dates given."""
	if not frappe.has_permission("Attendance", "write") and not frappe.has_permission(
		"Attendance", "submit"
	):
		frappe.throw("Not permitted to sync Attendance.", frappe.PermissionError)

	if not frappe.has_permission("Employee Checkin", "create") and not frappe.has_permission(
		"Employee Checkin", "write"
	):
		frappe.throw("Not permitted to create Employee Checkins.", frappe.PermissionError)

	result = sync_essl_checkins(from_dt=from_dt, to_dt=to_dt)
	return result or {"message": "Sync complete"}


@frappe.whitelist()
def manual_sync_range(from_date, to_date) -> dict:
	"""
	Re-sync each day in [from_date, to_date] individually (not as one ranged
	call) and re-enqueue the day-by-day results as a background job.

	Querying one day at a time mirrors the daily scheduled sync and avoids
	asking the ESSL API for a huge multi-day/multi-employee window in a
	single call, which is when partial/incomplete responses are most likely.
	"""
	if not frappe.has_permission("Attendance", "write") and not frappe.has_permission(
		"Attendance", "submit"
	):
		frappe.throw("Not permitted to sync Attendance.", frappe.PermissionError)

	if not frappe.has_permission("Employee Checkin", "create") and not frappe.has_permission(
		"Employee Checkin", "write"
	):
		frappe.throw("Not permitted to create Employee Checkins.", frappe.PermissionError)

	start = datetime.strptime(from_date, "%Y-%m-%d").date()
	end = datetime.strptime(to_date, "%Y-%m-%d").date()
	if start > end:
		frappe.throw("From Date cannot be after To Date.")

	yesterday = (_now() - timedelta(days=1)).date()
	if end > yesterday:
		frappe.throw(
			f"To Date cannot be later than yesterday ({yesterday}). "
			"Today's attendance isn't complete yet — syncing it now would mark employees "
			"Absent before their day (and out-punch) is even over."
		)

	total_days = (end - start).days + 1
	if total_days > 92:
		frappe.throw("Please limit the range to 92 days or fewer per run.")

	frappe.enqueue(
		"prakash_steel.utils.essl_biometric._run_sync_range",
		queue="long",
		timeout=total_days * 300,
		from_date=from_date,
		to_date=to_date,
		user=frappe.session.user,
	)
	return {
		"message": (
			f"Sync started in the background for {total_days} day(s) "
			f"({from_date} to {to_date}). You'll get a summary here when it's done."
		)
	}


def _run_sync_range(from_date, to_date, user) -> None:
	start = datetime.strptime(from_date, "%Y-%m-%d").date()
	end = datetime.strptime(to_date, "%Y-%m-%d").date()

	day_results = []
	day = start
	while day <= end:
		day_str = day.strftime("%Y-%m-%d")
		try:
			result = sync_essl_checkins(from_dt=f"{day_str} 00:00:00", to_dt=f"{day_str} 23:59:59") or {}
		except Exception as e:
			frappe.log_error(title="ESSL Range Sync Failed", message=f"{day_str}: {e}")
			result = {"error": str(e)}
		result["date"] = day_str
		day_results.append(result)
		day += timedelta(days=1)

	frappe.publish_realtime(
		event="essl_sync_range_done",
		message={"from_date": from_date, "to_date": to_date, "days": day_results},
		user=user,
	)
