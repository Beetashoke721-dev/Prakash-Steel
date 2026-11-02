# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for psp_attendence_page — no DB required."""

import unittest
from datetime import date
from unittest import mock


class TestSummarise(unittest.TestCase):
	"""WO/HO is counted for a day whenever the calendar says it's a holiday,
	regardless of attendance that day - not just when there's no record."""

	def _summarise(self, attendance, holidays):
		from prakash_steel.prakash_steel.page.psp_attendence_page.psp_attendence_page import _summarise

		return _summarise(attendance, holidays)

	def test_plain_week_counts_present_and_absent(self):
		attendance = {
			"2026-09-01": {"status": "Present"},
			"2026-09-02": {"status": "Absent"},
		}
		s = self._summarise(attendance, {})
		self.assertEqual((s["p"], s["a"], s["wo"], s["ho"], s["extra"]), (1, 1, 0, 0, 0))
		self.assertEqual(s["total_pay_days"], 1)

	def test_weekoff_with_no_record_is_paid_wo(self):
		attendance = {"2026-09-06": {"status": ""}}
		s = self._summarise(attendance, {"2026-09-06": "WO"})
		self.assertEqual(s["wo"], 1)
		self.assertEqual(s["total_pay_days"], 1)

	def test_weekoff_with_present_record_pays_both_wo_and_extra(self):
		"""Working a Sunday pays for the Sunday itself (WO) AND an extra day
		on top for actually working it - two pay days for one calendar day."""
		attendance = {"2026-09-13": {"status": "Present"}}
		s = self._summarise(attendance, {"2026-09-13": "WO"})
		self.assertEqual(s["wo"], 1)
		self.assertEqual(s["extra"], 1)
		self.assertEqual(s["total_pay_days"], 2)

	def test_holiday_with_present_record_pays_both_ho_and_extra(self):
		attendance = {"2026-09-18": {"status": "Present"}}
		s = self._summarise(attendance, {"2026-09-18": "HO"})
		self.assertEqual(s["ho"], 1)
		self.assertEqual(s["extra"], 1)
		self.assertEqual(s["total_pay_days"], 2)

	def test_weekoff_with_absent_record_counts_both_absent_and_wo(self):
		"""A single punch not enough to complete a shift still marks the day
		Absent (informational), but the WO itself is still owed - the
		holiday pay doesn't depend on whether the employee showed up."""
		attendance = {"2026-09-20": {"status": "Absent"}}
		s = self._summarise(attendance, {"2026-09-20": "WO"})
		self.assertEqual(s["wo"], 1)
		self.assertEqual(s["a"], 1)
		self.assertEqual(s["total_pay_days"], 1)

	def test_holiday_with_absent_record_counts_both_absent_and_ho(self):
		attendance = {"2026-09-18": {"status": "Absent"}}
		s = self._summarise(attendance, {"2026-09-18": "HO"})
		self.assertEqual(s["ho"], 1)
		self.assertEqual(s["a"], 1)
		self.assertEqual(s["total_pay_days"], 1)

	def test_holiday_with_no_record_is_paid_ho(self):
		s = self._summarise({"2026-09-18": {"status": ""}}, {"2026-09-18": "HO"})
		self.assertEqual(s["ho"], 1)
		self.assertEqual(s["wo"], 0)
		self.assertEqual(s["total_pay_days"], 1)

	def test_empty_month_pays_nothing(self):
		"""Nothing is pre-counted: with no records and no passed holidays,
		the pay-days total is zero."""
		s = self._summarise({"2026-09-01": {"status": ""}}, {})
		self.assertEqual(s["total_pay_days"], 0)


class TestHolidayMapBounds(unittest.TestCase):
	"""_holiday_map must only return passed days inside employment."""

	def _run(self, employees, rows, today, from_date="2026-10-01", to_date="2026-10-31"):
		import prakash_steel.prakash_steel.page.psp_attendence_page.psp_attendence_page as mod

		fake_frappe = mock.MagicMock()
		fake_frappe.db.get_all.return_value = rows
		with mock.patch.object(mod, "frappe", fake_frappe), mock.patch.object(
			mod, "getdate", return_value=date.fromisoformat(today)
		), mock.patch.object(mod, "_get_fallback_holiday_list", return_value="HL-2026"):
			return mod._holiday_map(employees, from_date, to_date)

	def _sundays(self):
		return [
			{"parent": "HL-2026", "holiday_date": d, "weekly_off": 1}
			for d in ("2026-10-04", "2026-10-11", "2026-10-18", "2026-10-25")
		]

	def test_future_weekoffs_are_not_returned(self):
		emp = {"name": "E1", "date_of_joining": None, "relieving_date": None}
		result = self._run([emp], self._sundays(), today="2026-10-05")
		self.assertEqual(result["E1"], {"2026-10-04": "WO"})

	def test_resignation_on_second_day_drops_later_weekoffs(self):
		emp = {"name": "E1", "date_of_joining": None, "relieving_date": date(2026, 10, 2)}
		result = self._run([emp], self._sundays(), today="2026-10-31")
		# No passed weekoff inside employment -> the employee has no entry.
		self.assertEqual(result.get("E1", {}), {})

	def test_days_before_joining_are_not_returned(self):
		emp = {"name": "E1", "date_of_joining": date(2026, 10, 12), "relieving_date": None}
		result = self._run([emp], self._sundays(), today="2026-10-31")
		self.assertEqual(sorted(result["E1"]), ["2026-10-18", "2026-10-25"])

	def test_employee_without_holiday_list_is_skipped(self):
		import prakash_steel.prakash_steel.page.psp_attendence_page.psp_attendence_page as mod

		fake_frappe = mock.MagicMock()
		with mock.patch.object(mod, "frappe", fake_frappe), mock.patch.object(
			mod, "_get_fallback_holiday_list", return_value=None
		):
			result = mod._holiday_map(
				[{"name": "E1", "date_of_joining": None, "relieving_date": None}],
				"2026-10-01",
				"2026-10-31",
			)
		self.assertEqual(result, {})


class TestHolidayListPerDay(unittest.TestCase):
	"""The holiday list follows the shift that applies on each day: a Shift
	Assignment covering that day wins, else the employee's default shift."""

	def _run(self, employee, assignments, shift_hl, rows, today="2026-10-31"):
		import prakash_steel.prakash_steel.page.psp_attendence_page.psp_attendence_page as mod

		fake_frappe = mock.MagicMock()
		fake_frappe.db.get_all.return_value = rows
		with mock.patch.object(mod, "frappe", fake_frappe), mock.patch.object(
			mod, "getdate", return_value=date.fromisoformat(today)
		), mock.patch.object(mod, "_get_fallback_holiday_list", return_value="HL-FALLBACK"):
			return mod._holiday_map(
				[employee],
				"2026-10-01",
				"2026-10-31",
				assignments={employee["name"]: assignments},
				shift_holiday_lists=shift_hl,
			)

	def test_assignment_covering_day_overrides_default_shift(self):
		"""Default is Night Shift (HL-NIGHT), but Day Shift (HL-DAY) is
		assigned from 10 Oct: days from 10 Oct use HL-DAY's Sunday."""
		emp = {"name": "E1", "default_shift": "Night", "date_of_joining": None, "relieving_date": None}
		assignments = [
			{"shift_type": "Day", "start_date": date(2026, 10, 10), "end_date": None},
		]
		rows = [
			{"parent": "HL-NIGHT", "holiday_date": "2026-10-04", "weekly_off": 1},
			{"parent": "HL-DAY", "holiday_date": "2026-10-11", "weekly_off": 1},
		]
		result = self._run(emp, assignments, {"Day": "HL-DAY", "Night": "HL-NIGHT"}, rows)
		# 4 Oct is before the assignment -> default Night Shift's list -> WO.
		# 11 Oct is covered by the assignment -> Day Shift's list -> WO.
		self.assertEqual(result["E1"], {"2026-10-04": "WO", "2026-10-11": "WO"})

	def test_no_assignment_uses_default_shift_holiday_list(self):
		emp = {"name": "E1", "default_shift": "Night", "date_of_joining": None, "relieving_date": None}
		rows = [{"parent": "HL-NIGHT", "holiday_date": "2026-10-04", "weekly_off": 1}]
		result = self._run(emp, [], {"Night": "HL-NIGHT"}, rows)
		self.assertEqual(result["E1"], {"2026-10-04": "WO"})

	def test_expired_assignment_falls_back_to_default(self):
		emp = {"name": "E1", "default_shift": "Night", "date_of_joining": None, "relieving_date": None}
		assignments = [
			{"shift_type": "Day", "start_date": date(2026, 10, 1), "end_date": date(2026, 10, 5)},
		]
		rows = [{"parent": "HL-NIGHT", "holiday_date": "2026-10-11", "weekly_off": 0}]
		result = self._run(emp, assignments, {"Day": "HL-DAY", "Night": "HL-NIGHT"}, rows)
		self.assertEqual(result["E1"], {"2026-10-11": "HO"})


class TestLeftEmployeeRowBoundByRelievingDate(unittest.TestCase):
	"""A Left/Inactive employee's row shows for every month up to and
	including the one their Relieving Date falls in, never after -
	decided purely from the Employee master's Relieving Date, never from
	whether an Attendance record happens to exist. Attendance existing is
	not trustworthy proof someone was still employed: the ESSL sync used to
	keep fabricating daily Absent records for an employee long after they'd
	left (see _get_employee_map's att_date filter), so gating the dashboard
	on "has an Attendance record" would make it trust that same bad data. A
	stray record can never make a Left employee reappear under this rule."""

	def _employees(self):
		return [
			{
				"name": "E-ACTIVE",
				"employee_name": "Active Person",
				"branch": "B1",
				"custom_essl_employee_id": "1",
				"status": "Active",
				"default_shift": None,
				"date_of_joining": None,
				"relieving_date": None,
			},
			{
				"name": "E-LEFT",
				"employee_name": "Left Person",
				"branch": "B1",
				"custom_essl_employee_id": "2",
				"status": "Left",
				"default_shift": None,
				"date_of_joining": None,
				"relieving_date": date(2026, 9, 15),
			},
			{
				"name": "E-LEFT-NO-DATE",
				"employee_name": "Left No Relieving Date",
				"branch": "B1",
				"custom_essl_employee_id": "3",
				"status": "Left",
				"default_shift": None,
				"date_of_joining": None,
				"relieving_date": None,
			},
		]

	def _names_shown(self, from_date, to_date):
		import prakash_steel.prakash_steel.page.psp_attendence_page.psp_attendence_page as mod

		employees = self._employees()
		fake_frappe = mock.MagicMock()
		fake_frappe.db.get_all.side_effect = lambda doctype, **kw: (
			employees if doctype == "Employee" else []
		)
		with mock.patch.object(mod, "frappe", fake_frappe), mock.patch.object(
			mod, "require_permission", return_value=None
		), mock.patch.object(mod, "_shift_lookups", return_value=({}, {})), mock.patch.object(
			mod, "_holiday_map", return_value={}
		):
			data = mod.get_attendance_data(from_date, to_date)
		return {r["employee"] for r in data["employees"]}

	def test_shown_in_the_month_relieved(self):
		shown = self._names_shown("2026-09-01", "2026-09-30")
		self.assertEqual(shown, {"E-ACTIVE", "E-LEFT"})

	def test_shown_in_an_earlier_month(self):
		shown = self._names_shown("2026-07-01", "2026-07-31")
		self.assertEqual(shown, {"E-ACTIVE", "E-LEFT"})

	def test_never_shown_in_a_later_month(self):
		shown = self._names_shown("2026-10-01", "2026-10-31")
		self.assertEqual(shown, {"E-ACTIVE"})

	def test_left_with_no_relieving_date_never_shown(self):
		shown = self._names_shown("2026-09-01", "2026-09-30")
		self.assertNotIn("E-LEFT-NO-DATE", shown)


if __name__ == "__main__":
	unittest.main()
