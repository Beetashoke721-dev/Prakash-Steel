# """
# ESSL Biometric Integration
# --------------------------
# Fetches attendance punch logs from ESSL SOAP API for all configured devices,
# determines IN/OUT per employee per day, creates Employee Checkin records,
# and marks Attendance (Present) in ERPNext.

# Employee mapping: Employee.custom_essl_employee_id  ←→  ESSL user_id
# Settings:         ESSL Biometric Settings  (Single DocType)
# """

# import xml.etree.ElementTree as ET
# from collections import defaultdict
# from datetime import datetime, timedelta

# import frappe
# import requests


# # ---------------------------------------------------------------------------
# # SOAP API helpers
# # ---------------------------------------------------------------------------

# def _build_soap_body(from_dt, to_dt, serial, username, password):
# 	return f"""<?xml version="1.0" encoding="utf-8"?>
# <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
#                xmlns:xsd="http://www.w3.org/2001/XMLSchema"
#                xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
#   <soap:Body>
#     <GetTransactionsLog xmlns="http://tempuri.org/">
#       <FromDateTime>{from_dt}</FromDateTime>
#       <ToDateTime>{to_dt}</ToDateTime>
#       <SerialNumber>{serial}</SerialNumber>
#       <UserName>{username}</UserName>
#       <UserPassword>{password}</UserPassword>
#       <strDataList></strDataList>
#     </GetTransactionsLog>
#   </soap:Body>
# </soap:Envelope>"""


# def _fetch_device_logs(api_url, serial, from_dt, to_dt, username, password):
# 	"""Call ESSL SOAP API and return raw XML response text."""
# 	soap_body = _build_soap_body(from_dt, to_dt, serial, username, password)
# 	headers = {
# 		"Content-Type": "text/xml; charset=utf-8",
# 		"SOAPAction": "http://tempuri.org/GetTransactionsLog",
# 	}
# 	response = requests.post(api_url, data=soap_body.encode("utf-8"), headers=headers, timeout=30)
# 	response.raise_for_status()
# 	return response.text


# def _parse_logs(xml_text, device_serial, device_label):
# 	"""
# 	Parse ESSL XML response and return list of punch dicts:
# 	  { user_id, timestamp (datetime), device_serial, device_label }
# 	"""
# 	root = ET.fromstring(xml_text)
# 	ns = {
# 		"soap": "http://schemas.xmlsoap.org/soap/envelope/",
# 		"t": "http://tempuri.org/",
# 	}

# 	result_node = root.find(".//t:GetTransactionsLogResult", ns)
# 	data_node = root.find(".//t:strDataList", ns)

# 	result_text = result_node.text if result_node is not None else "No result"
# 	frappe.logger().info(f"[ESSL] {device_label} ({device_serial}): {result_text}")

# 	if data_node is None or not (data_node.text or "").strip():
# 		return []

# 	punches = []
# 	for line in data_node.text.strip().splitlines():
# 		parts = line.strip().split("\t")
# 		if len(parts) < 2:
# 			continue
# 		user_id = parts[0].strip()
# 		ts_str = parts[1].strip()
# 		try:
# 			ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
# 		except ValueError:
# 			continue
# 		punches.append({
# 			"user_id": user_id,
# 			"timestamp": ts,
# 			"device_serial": device_serial,
# 			"device_label": device_label,
# 		})
# 	return punches


# # ---------------------------------------------------------------------------
# # Group punches → IN/OUT checkins + attendance summary
# # ---------------------------------------------------------------------------

# def _process_punches(all_punches):
# 	"""
# 	Group punches by (user_id, date) across all devices.
# 	Returns:
# 	  checkins  – list of { user_id, timestamp (str), log_type, device_label }
# 	  attendance – list of { user_id, date (str), in_time (str), out_time (str|None), working_hours (float) }
# 	"""
# 	grouped = defaultdict(list)
# 	for p in all_punches:
# 		date_key = p["timestamp"].strftime("%Y-%m-%d")
# 		grouped[(p["user_id"], date_key)].append(p)

# 	checkins = []
# 	attendance = []

# 	for (user_id, date_key), entries in grouped.items():
# 		entries.sort(key=lambda x: x["timestamp"])
# 		first = entries[0]
# 		last = entries[-1]

# 		# --- Employee Checkin records ---
# 		checkins.append({
# 			"user_id": user_id,
# 			"timestamp": first["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
# 			"log_type": "IN",
# 			"device_label": first["device_label"],
# 		})
# 		if last["timestamp"] != first["timestamp"]:
# 			checkins.append({
# 				"user_id": user_id,
# 				"timestamp": last["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
# 				"log_type": "OUT",
# 				"device_label": last["device_label"],
# 			})

# 		# --- Attendance summary ---
# 		out_time = last["timestamp"] if last["timestamp"] != first["timestamp"] else None
# 		working_hours = 0.0
# 		if out_time:
# 			diff = last["timestamp"] - first["timestamp"]
# 			working_hours = round(diff.total_seconds() / 3600, 2)

# 		attendance.append({
# 			"user_id": user_id,
# 			"date": date_key,
# 			"in_time": first["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
# 			"out_time": last["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if out_time else None,
# 			"working_hours": working_hours,
# 		})

# 	return checkins, attendance


# # ---------------------------------------------------------------------------
# # Employee map
# # ---------------------------------------------------------------------------

# def _get_employee_map():
# 	"""Return dict { essl_id_str: {name, company} } for all employees."""
# 	rows = frappe.db.get_all(
# 		"Employee",
# 		filters={"custom_essl_employee_id": ["!=", ""]},
# 		fields=["name", "custom_essl_employee_id", "company"],
# 	)
# 	return {
# 		str(r.custom_essl_employee_id).strip(): {"name": r.name, "company": r.company}
# 		for r in rows if r.custom_essl_employee_id
# 	}


# # ---------------------------------------------------------------------------
# # Create Employee Checkins
# # ---------------------------------------------------------------------------

# def _create_checkins(checkins, employee_map):
# 	success = failed = skipped = 0

# 	for log in checkins:
# 		emp = employee_map.get(log["user_id"])
# 		if not emp:
# 			frappe.logger().warning(f"[ESSL] No employee for ESSL ID '{log['user_id']}' – skipping checkin")
# 			failed += 1
# 			continue

# 		if frappe.db.exists("Employee Checkin", {"employee": emp["name"], "time": log["timestamp"]}):
# 			skipped += 1
# 			continue

# 		try:
# 			frappe.get_doc({
# 				"doctype": "Employee Checkin",
# 				"employee": emp["name"],
# 				"time": log["timestamp"],
# 				"log_type": log["log_type"],
# 				"device_id": log["device_label"],
# 			}).insert(ignore_permissions=True)
# 			success += 1
# 		except Exception as e:
# 			frappe.logger().error(f"[ESSL] Checkin failed for {emp['name']} at {log['timestamp']}: {e}")
# 			failed += 1

# 	frappe.db.commit()
# 	frappe.logger().info(f"[ESSL] Checkins → created: {success}, skipped: {skipped}, failed: {failed}")
# 	return {"checkin_success": success, "checkin_skipped": skipped, "checkin_failed": failed}


# # ---------------------------------------------------------------------------
# # Create / update Attendance
# # ---------------------------------------------------------------------------

# def _create_attendance(attendance_list, employee_map):
# 	success = skipped = failed = 0

# 	for rec in attendance_list:
# 		emp = employee_map.get(rec["user_id"])
# 		if not emp:
# 			failed += 1
# 			continue

# 		employee = emp["name"]
# 		company = emp["company"]
# 		att_date = rec["date"]

# 		existing = frappe.db.get_value(
# 			"Attendance",
# 			{"employee": employee, "attendance_date": att_date, "docstatus": ["!=", 2]},
# 			["name", "docstatus"],
# 			as_dict=True,
# 		)

# 		if existing:
# 			# Already exists — update the custom time fields
# 			in_dt  = datetime.strptime(rec["in_time"],  "%Y-%m-%d %H:%M:%S") if rec["in_time"]  else None
# 			out_dt = datetime.strptime(rec["out_time"], "%Y-%m-%d %H:%M:%S") if rec["out_time"] else None
# 			wh = round((out_dt - in_dt).total_seconds() / 3600, 2) if (in_dt and out_dt and out_dt > in_dt) else 0.0
# 			frappe.db.set_value("Attendance", existing.name, "custom_punch_in_time", rec["in_time"])
# 			frappe.db.set_value("Attendance", existing.name, "custom_punch_out_time", rec["out_time"])
# 			frappe.db.set_value("Attendance", existing.name, "custom_working_hours", wh)
# 			skipped += 1
# 			continue

# 		_insert_and_submit_attendance(employee, company, att_date, rec)
# 		success += 1

# 	frappe.db.commit()
# 	frappe.logger().info(
# 		f"[ESSL] Attendance → created/submitted: {success}, already existed: {skipped}, failed: {failed}"
# 	)
# 	return {"att_success": success, "att_skipped": skipped, "att_failed": failed}


# def _insert_and_submit_attendance(employee, company, att_date, rec):
# 	"""Create a submitted Attendance record with custom punch time fields."""
# 	in_dt  = datetime.strptime(rec["in_time"],  "%Y-%m-%d %H:%M:%S") if rec["in_time"]  else None
# 	out_dt = datetime.strptime(rec["out_time"], "%Y-%m-%d %H:%M:%S") if rec["out_time"] else None

# 	if in_dt and out_dt and out_dt > in_dt:
# 		working_hours = round((out_dt - in_dt).total_seconds() / 3600, 2)
# 	else:
# 		working_hours = 0.0

# 	doc = frappe.get_doc({
# 		"doctype": "Attendance",
# 		"employee": employee,
# 		"attendance_date": att_date,
# 		"company": company,
# 		"status": "Present",
# 		"custom_punch_in_time": rec["in_time"],
# 		"custom_punch_out_time": rec["out_time"],
# 	})
# 	doc.insert(ignore_permissions=True)
# 	doc.submit()

# 	# Use db.set_value to bypass any controller that may reset custom float fields
# 	frappe.db.set_value("Attendance", doc.name, "custom_working_hours", working_hours)


# # ---------------------------------------------------------------------------
# # Main entry point
# # ---------------------------------------------------------------------------

# def sync_essl_checkins(from_dt=None, to_dt=None):
# 	"""
# 	Fetch punch logs from all active ESSL devices, create Employee Checkins,
# 	and mark Attendance as Present.

# 	Args:
# 		from_dt (str | None): "YYYY-MM-DD HH:MM:SS" – defaults to yesterday 00:00:00
# 		to_dt   (str | None): "YYYY-MM-DD HH:MM:SS" – defaults to yesterday 23:59:59
# 	"""
# 	settings = frappe.get_single("ESSL Biometric Settings")

# 	if not settings.api_url or not settings.username or not settings.password:
# 		frappe.logger().warning("[ESSL] ESSL Biometric Settings incomplete – aborting sync.")
# 		return

# 	active_devices = [d for d in settings.devices if d.is_active]
# 	if not active_devices:
# 		frappe.logger().warning("[ESSL] No active devices configured – aborting sync.")
# 		return

# 	# Default: yesterday's full day
# 	if not from_dt or not to_dt:
# 		yesterday = datetime.now() - timedelta(days=1)
# 		from_dt = from_dt or yesterday.strftime("%Y-%m-%d") + " 00:00:00"
# 		to_dt   = to_dt   or yesterday.strftime("%Y-%m-%d") + " 23:59:59"

# 	# Convert to ESSL date format (YYYY/MM/DD HH:MM)
# 	essl_from = datetime.strptime(from_dt, "%Y-%m-%d %H:%M:%S").strftime("%Y/%m/%d %H:%M")
# 	essl_to   = datetime.strptime(to_dt,   "%Y-%m-%d %H:%M:%S").strftime("%Y/%m/%d %H:%M")

# 	password = settings.get_password("password")

# 	frappe.logger().info(
# 		f"[ESSL] Starting sync | range: {essl_from} → {essl_to} | devices: {len(active_devices)}"
# 	)

# 	all_punches = []
# 	for device in active_devices:
# 		label = device.device_label or device.serial_number
# 		try:
# 			xml_text = _fetch_device_logs(
# 				settings.api_url, device.serial_number, essl_from, essl_to,
# 				settings.username, password,
# 			)
# 			punches = _parse_logs(xml_text, device.serial_number, label)
# 			frappe.logger().info(f"[ESSL] {label}: {len(punches)} punches")
# 			all_punches.extend(punches)
# 		except Exception as e:
# 			frappe.logger().error(f"[ESSL] Error fetching {label} ({device.serial_number}): {e}")

# 	frappe.logger().info(f"[ESSL] Total punches across all devices: {len(all_punches)}")

# 	if not all_punches:
# 		_update_last_synced()
# 		return {"message": "No punches found for the given date range"}

# 	checkins, attendance_list = _process_punches(all_punches)
# 	employee_map = _get_employee_map()

# 	checkin_result = _create_checkins(checkins, employee_map)
# 	att_result = _create_attendance(attendance_list, employee_map)

# 	_update_last_synced()
# 	return {**checkin_result, **att_result}


# def _update_last_synced():
# 	frappe.db.set_single_value(
# 		"ESSL Biometric Settings", "last_synced_on", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
# 	)


# # ---------------------------------------------------------------------------
# # Whitelisted API – manual trigger from UI / console
# # ---------------------------------------------------------------------------

# @frappe.whitelist()
# def manual_sync(from_dt=None, to_dt=None):
# 	"""Trigger ESSL sync manually. Defaults to yesterday if no dates given."""
# 	result = sync_essl_checkins(from_dt=from_dt, to_dt=to_dt)
# 	return result or {"message": "Sync complete"}
