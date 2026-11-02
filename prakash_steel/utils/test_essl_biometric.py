# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for utils/essl_biometric.py — no DB required."""

import unittest
from datetime import datetime


class TestSecondsToHhmmss(unittest.TestCase):

    def test_zero(self):
        from prakash_steel.utils.essl_biometric import _seconds_to_hhmmss
        self.assertEqual(_seconds_to_hhmmss(0), "00:00:00")

    def test_one_hour(self):
        from prakash_steel.utils.essl_biometric import _seconds_to_hhmmss
        self.assertEqual(_seconds_to_hhmmss(3600), "01:00:00")

    def test_one_minute(self):
        from prakash_steel.utils.essl_biometric import _seconds_to_hhmmss
        self.assertEqual(_seconds_to_hhmmss(60), "00:01:00")

    def test_one_second(self):
        from prakash_steel.utils.essl_biometric import _seconds_to_hhmmss
        self.assertEqual(_seconds_to_hhmmss(1), "00:00:01")

    def test_mixed(self):
        from prakash_steel.utils.essl_biometric import _seconds_to_hhmmss
        # 2h 30m 15s = 9015 seconds
        self.assertEqual(_seconds_to_hhmmss(9015), "02:30:15")

    def test_more_than_24_hours(self):
        from prakash_steel.utils.essl_biometric import _seconds_to_hhmmss
        # 25 hours = 90000 seconds
        self.assertEqual(_seconds_to_hhmmss(90000), "25:00:00")


class TestParseLogs(unittest.TestCase):

    VALID_XML = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetTransactionsLogResponse xmlns="http://tempuri.org/">
      <GetTransactionsLogResult>OK</GetTransactionsLogResult>
      <strDataList>1\t2026-01-15 08:05:00\n2\t2026-01-15 09:10:00</strDataList>
    </GetTransactionsLogResponse>
  </soap:Body>
</soap:Envelope>"""

    EMPTY_DATA_XML = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetTransactionsLogResponse xmlns="http://tempuri.org/">
      <GetTransactionsLogResult>OK</GetTransactionsLogResult>
      <strDataList></strDataList>
    </GetTransactionsLogResponse>
  </soap:Body>
</soap:Envelope>"""

    def test_parses_two_punches(self):
        from prakash_steel.utils.essl_biometric import _parse_logs
        punches = _parse_logs(self.VALID_XML, "SN-001", "Device A")
        self.assertEqual(len(punches), 2)

    def test_punch_has_correct_user_id(self):
        from prakash_steel.utils.essl_biometric import _parse_logs
        punches = _parse_logs(self.VALID_XML, "SN-001", "Device A")
        self.assertEqual(punches[0]["user_id"], "1")
        self.assertEqual(punches[1]["user_id"], "2")

    def test_punch_timestamp_is_datetime(self):
        from prakash_steel.utils.essl_biometric import _parse_logs
        punches = _parse_logs(self.VALID_XML, "SN-001", "Device A")
        self.assertIsInstance(punches[0]["timestamp"], datetime)

    def test_punch_has_device_label(self):
        from prakash_steel.utils.essl_biometric import _parse_logs
        punches = _parse_logs(self.VALID_XML, "SN-001", "Device A")
        self.assertEqual(punches[0]["device_label"], "Device A")

    def test_empty_data_returns_empty_list(self):
        from prakash_steel.utils.essl_biometric import _parse_logs
        punches = _parse_logs(self.EMPTY_DATA_XML, "SN-001", "Device A")
        self.assertEqual(punches, [])

    def test_invalid_timestamp_line_skipped(self):
        from prakash_steel.utils.essl_biometric import _parse_logs
        xml = self.VALID_XML.replace("2026-01-15 08:05:00", "not-a-date")
        punches = _parse_logs(xml, "SN-001", "Device A")
        # Only the valid line should parse
        self.assertEqual(len(punches), 1)

    def test_line_with_only_one_field_skipped(self):
        from prakash_steel.utils.essl_biometric import _parse_logs
        xml = self.VALID_XML.replace("1\t2026-01-15 08:05:00", "1")
        punches = _parse_logs(xml, "SN-001", "Device A")
        self.assertEqual(len(punches), 1)


class TestProcessPunches(unittest.TestCase):

    def _punch(self, user_id, ts_str, device="Device A"):
        return {
            "user_id": user_id,
            "timestamp": datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S"),
            "device_serial": "SN-001",
            "device_label": device,
        }

    def test_single_punch_creates_in_only(self):
        from prakash_steel.utils.essl_biometric import _process_punches
        punches = [self._punch("1", "2026-01-15 08:00:00")]
        checkins, attendance = _process_punches(punches)
        # Only one punch → only IN, no OUT
        self.assertEqual(len([c for c in checkins if c["log_type"] == "IN"]), 1)
        self.assertEqual(len([c for c in checkins if c["log_type"] == "OUT"]), 0)

    def test_two_punches_create_in_and_out(self):
        from prakash_steel.utils.essl_biometric import _process_punches
        punches = [
            self._punch("1", "2026-01-15 08:00:00"),
            self._punch("1", "2026-01-15 17:00:00"),
        ]
        checkins, attendance = _process_punches(punches)
        log_types = {c["log_type"] for c in checkins}
        self.assertIn("IN", log_types)
        self.assertIn("OUT", log_types)

    def test_working_hours_calculated(self):
        from prakash_steel.utils.essl_biometric import _process_punches
        punches = [
            self._punch("1", "2026-01-15 08:00:00"),
            self._punch("1", "2026-01-15 16:30:00"),
        ]
        _, attendance = _process_punches(punches)
        self.assertEqual(len(attendance), 1)
        self.assertAlmostEqual(attendance[0]["working_hours"], 8.5)

    def test_groups_by_user_and_date(self):
        from prakash_steel.utils.essl_biometric import _process_punches
        punches = [
            self._punch("1", "2026-01-15 08:00:00"),
            self._punch("1", "2026-01-15 17:00:00"),
            self._punch("2", "2026-01-15 09:00:00"),
            self._punch("2", "2026-01-15 18:00:00"),
        ]
        checkins, attendance = _process_punches(punches)
        # 2 users × (IN + OUT) = 4 checkins, 2 attendance records
        self.assertEqual(len(attendance), 2)
        self.assertEqual(len(checkins), 4)

    def test_first_punch_is_in(self):
        from prakash_steel.utils.essl_biometric import _process_punches
        punches = [
            self._punch("1", "2026-01-15 10:00:00"),
            self._punch("1", "2026-01-15 08:00:00"),  # earlier, second in list
            self._punch("1", "2026-01-15 17:00:00"),
        ]
        checkins, _ = _process_punches(punches)
        in_checkin = next(c for c in checkins if c["log_type"] == "IN")
        self.assertEqual(in_checkin["timestamp"], "2026-01-15 08:00:00")

    def test_no_working_hours_when_single_punch(self):
        from prakash_steel.utils.essl_biometric import _process_punches
        punches = [self._punch("1", "2026-01-15 08:00:00")]
        _, attendance = _process_punches(punches)
        self.assertEqual(attendance[0]["working_hours"], 0.0)
        self.assertIsNone(attendance[0]["out_time"])


class TestGetEmployeeShiftDate(unittest.TestCase):
    """_get_employee_shift_date() must never raise — any lookup failure (no
    site context here, or no shift assignment on a real site) falls back to
    the punch's own calendar date."""

    def test_falls_back_to_punch_calendar_date(self):
        from prakash_steel.utils.essl_biometric import _get_employee_shift_date
        ts = datetime(2026, 1, 16, 6, 0, 0)
        self.assertEqual(_get_employee_shift_date("HR-EMP-0007", ts), ts.date())


class TestProcessPunchesShiftAware(unittest.TestCase):
    """_process_punches() must fold an overnight shift's post-midnight OUT
    punch back onto the day the shift started, using the employee's shift —
    instead of blindly grouping by the punch's own calendar date."""

    def _punch(self, user_id, ts_str):
        return {
            "user_id": user_id,
            "timestamp": datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S"),
            "device_serial": "SN-001",
            "device_label": "Device A",
        }

    def _patch_shift_date(self, mapping):
        """mapping: {(employee, "YYYY-MM-DD HH:MM:SS"): "YYYY-MM-DD"}"""
        import prakash_steel.utils.essl_biometric as mod

        def fake(employee, ts):
            key = (employee, ts.strftime("%Y-%m-%d %H:%M:%S"))
            return datetime.strptime(mapping[key], "%Y-%m-%d").date()

        orig = mod._get_employee_shift_date
        mod._get_employee_shift_date = fake
        return mod, orig

    def test_night_shift_out_punch_grouped_with_previous_day(self):
        employee_map = {"7": {"name": "HR-EMP-0007", "company": "PSP"}}
        punches = [
            self._punch("7", "2026-01-15 18:00:00"),  # night shift IN
            self._punch("7", "2026-01-16 06:00:00"),  # OUT, next calendar day
        ]
        mapping = {
            ("HR-EMP-0007", "2026-01-15 18:00:00"): "2026-01-15",
            ("HR-EMP-0007", "2026-01-16 06:00:00"): "2026-01-15",  # tail folds back
        }
        mod, orig = self._patch_shift_date(mapping)
        try:
            checkins, attendance = mod._process_punches(punches, employee_map)
        finally:
            mod._get_employee_shift_date = orig

        self.assertEqual(len(attendance), 1)
        self.assertEqual(attendance[0]["date"], "2026-01-15")
        self.assertEqual(attendance[0]["in_time"], "2026-01-15 18:00:00")
        self.assertEqual(attendance[0]["out_time"], "2026-01-16 06:00:00")
        self.assertEqual({c["log_type"] for c in checkins}, {"IN", "OUT"})

    def test_unmapped_employee_falls_back_to_calendar_date(self):
        import prakash_steel.utils.essl_biometric as mod

        punches = [
            self._punch("99", "2026-01-15 18:00:00"),
            self._punch("99", "2026-01-16 06:00:00"),
        ]
        # No employee_map entry for "99" -> old calendar-date grouping, so
        # these land in two SEPARATE single-punch groups, not one pair.
        checkins, attendance = mod._process_punches(punches, employee_map={})
        self.assertEqual(len(attendance), 2)
        self.assertEqual({a["date"] for a in attendance}, {"2026-01-15", "2026-01-16"})

    def test_target_date_drops_other_shift_days(self):
        employee_map = {"7": {"name": "HR-EMP-0007", "company": "PSP"}}
        punches = [
            self._punch("7", "2026-01-15 18:00:00"),
            self._punch("7", "2026-01-16 06:00:00"),  # folds back to 01-15
            self._punch("7", "2026-01-16 09:00:00"),  # genuinely belongs to 01-16
        ]
        mapping = {
            ("HR-EMP-0007", "2026-01-15 18:00:00"): "2026-01-15",
            ("HR-EMP-0007", "2026-01-16 06:00:00"): "2026-01-15",
            ("HR-EMP-0007", "2026-01-16 09:00:00"): "2026-01-16",
        }
        mod, orig = self._patch_shift_date(mapping)
        try:
            checkins, attendance = mod._process_punches(punches, employee_map, target_date="2026-01-15")
        finally:
            mod._get_employee_shift_date = orig

        # Only the 01-15 shift-day group survives this run; the 01-16 09:00
        # punch (the start of a different shift-day) must not leak in.
        self.assertEqual(len(attendance), 1)
        self.assertEqual(attendance[0]["date"], "2026-01-15")
        self.assertEqual(attendance[0]["out_time"], "2026-01-16 06:00:00")

    def test_orphan_next_day_punch_fills_out_time_not_in_time(self):
        """An employee who never punched IN that evening, but has a punch
        that folds back from the next morning (e.g. multiple stray taps),
        must NOT be recorded as if that punch were the IN. It goes in
        out_time, in_time stays blank, and the record still lands on the
        shift-start date."""
        employee_map = {"7": {"name": "HR-EMP-0007", "company": "PSP"}}
        punches = [
            self._punch("7", "2026-01-16 08:00:00"),
            self._punch("7", "2026-01-16 08:05:00"),
            self._punch("7", "2026-01-16 08:10:00"),
        ]
        # No evening punch on 01-15 at all -> every punch here is "next-day"
        # (folded back) relative to shift-day 01-15, none is "same-day".
        mapping = {
            ("HR-EMP-0007", "2026-01-16 08:00:00"): "2026-01-15",
            ("HR-EMP-0007", "2026-01-16 08:05:00"): "2026-01-15",
            ("HR-EMP-0007", "2026-01-16 08:10:00"): "2026-01-15",
        }
        mod, orig = self._patch_shift_date(mapping)
        try:
            checkins, attendance = mod._process_punches(punches, employee_map)
        finally:
            mod._get_employee_shift_date = orig

        self.assertEqual(len(attendance), 1)
        rec = attendance[0]
        self.assertEqual(rec["date"], "2026-01-15")
        self.assertIsNone(rec["in_time"])
        # Latest of the orphaned punches becomes the recorded out_time.
        self.assertEqual(rec["out_time"], "2026-01-16 08:10:00")
        self.assertEqual(rec["working_hours"], 0.0)
        # Only a single OUT checkin is created - no fabricated IN.
        self.assertEqual(len(checkins), 1)
        self.assertEqual(checkins[0]["log_type"], "OUT")

    def test_evening_only_punch_still_fills_in_time_no_out(self):
        """Unchanged case: a lone evening punch with nothing folding back
        from the next morning stays IN-only, Absent (has_in and not
        has_out) - this must keep working exactly as before."""
        employee_map = {"7": {"name": "HR-EMP-0007", "company": "PSP"}}
        punches = [self._punch("7", "2026-01-15 18:00:00")]
        mapping = {("HR-EMP-0007", "2026-01-15 18:00:00"): "2026-01-15"}
        mod, orig = self._patch_shift_date(mapping)
        try:
            checkins, attendance = mod._process_punches(punches, employee_map)
        finally:
            mod._get_employee_shift_date = orig

        self.assertEqual(len(attendance), 1)
        self.assertEqual(attendance[0]["in_time"], "2026-01-15 18:00:00")
        self.assertIsNone(attendance[0]["out_time"])
        self.assertEqual(len(checkins), 1)
        self.assertEqual(checkins[0]["log_type"], "IN")


class TestInsertAndSubmitAttendanceStatus(unittest.TestCase):
    """_insert_and_submit_attendance must only mark Present when BOTH
    in_time and out_time are set - an out_time with no in_time (an orphaned
    punch, see TestProcessPunchesShiftAware) must stay Absent, not Present."""

    def _run(self, rec):
        import types

        import prakash_steel.utils.essl_biometric as mod

        orig_frappe = mod.frappe
        captured = {}

        class FakeDoc:
            def __init__(self, data):
                captured["doc_data"] = data
                self.name = "HR-ATT-TEST"

            def insert(self, ignore_permissions=False):
                pass

            def submit(self):
                pass

        set_values = []

        mod.frappe = types.SimpleNamespace(
            get_doc=lambda data: FakeDoc(data),
            db=types.SimpleNamespace(
                set_value=lambda *a, **k: set_values.append(a),
                sql=lambda *a, **k: None,
            ),
        )
        try:
            mod._insert_and_submit_attendance("HR-EMP-0007", "PSP", "2026-01-15", rec)
        finally:
            mod.frappe = orig_frappe
        return captured["doc_data"]

    def test_out_only_stays_absent(self):
        rec = {"in_time": None, "out_time": "2026-01-16 08:10:00", "user_id": "7"}
        doc_data = self._run(rec)
        self.assertEqual(doc_data["status"], "Absent")
        self.assertIsNone(doc_data["custom_punch_in_time"])
        self.assertEqual(doc_data["custom_punch_out_time"], "2026-01-16 08:10:00")

    def test_in_only_stays_absent(self):
        rec = {"in_time": "2026-01-15 18:00:00", "out_time": None, "user_id": "7"}
        doc_data = self._run(rec)
        self.assertEqual(doc_data["status"], "Absent")

    def test_both_present_marks_present(self):
        rec = {"in_time": "2026-01-15 18:00:00", "out_time": "2026-01-16 08:10:00", "user_id": "7"}
        doc_data = self._run(rec)
        self.assertEqual(doc_data["status"], "Present")


class TestIsHolidayForEmployee(unittest.TestCase):
    """_is_holiday_for_employee should short-circuit / cache correctly. DB and
    holiday-list resolution are stubbed so no site is needed."""

    def _run(self, monkeypatch_hl, exists_return):
        import types

        import prakash_steel.utils.essl_biometric as mod

        orig_get_hl = mod._get_employee_holiday_list
        orig_frappe = mod.frappe
        calls = {"exists": 0}

        def fake_exists(*_a, **_k):
            calls["exists"] += 1
            return exists_return

        mod._get_employee_holiday_list = lambda emp, dt: monkeypatch_hl
        mod.frappe = types.SimpleNamespace(db=types.SimpleNamespace(exists=fake_exists))
        try:
            hl_cache, holiday_cache = {}, {}
            r1 = mod._is_holiday_for_employee("EMP-1", "2026-01-04", hl_cache, holiday_cache)
            r2 = mod._is_holiday_for_employee("EMP-1", "2026-01-04", hl_cache, holiday_cache)
            return r1, r2, calls["exists"]
        finally:
            mod._get_employee_holiday_list = orig_get_hl
            mod.frappe = orig_frappe

    def test_no_holiday_list_returns_false_without_db_hit(self):
        r1, r2, exists_calls = self._run(monkeypatch_hl=None, exists_return=True)
        self.assertFalse(r1)
        self.assertFalse(r2)
        self.assertEqual(exists_calls, 0)

    def test_date_in_holiday_list_returns_true(self):
        r1, r2, _ = self._run(monkeypatch_hl="HL-Factory", exists_return=True)
        self.assertTrue(r1)
        self.assertTrue(r2)

    def test_result_is_cached_across_calls(self):
        r1, r2, exists_calls = self._run(monkeypatch_hl="HL-Factory", exists_return=False)
        self.assertFalse(r1)
        self.assertFalse(r2)
        self.assertEqual(exists_calls, 1)  # second call served from holiday_cache


if __name__ == "__main__":
    unittest.main()


class TestPreviousNightShiftCheckout(unittest.TestCase):
    """A punch in the early hours is the check-out of the previous day's
    overnight shift when that day's assignment is overnight and the punch
    falls inside its window. The next day's shift must not claim it."""

    def _run(self, ts, prev_shift, window):
        from datetime import date as _date
        from unittest import mock

        import prakash_steel.utils.essl_biometric as mod

        def fake_for_date(employee, d):
            return prev_shift if d == _date(2026, 1, 15) else "Day Shift"

        with mock.patch.object(mod, "_get_shift_type_for_date", side_effect=fake_for_date), mock.patch.object(
            mod, "_night_shift_window", return_value=window
        ):
            return mod._get_employee_shift_date("HR-EMP-0007", ts)

    def test_morning_checkout_belongs_to_previous_night(self):
        from datetime import date as _date

        window = (datetime(2026, 1, 15, 18, 0), datetime(2026, 1, 16, 17, 0))
        got = self._run(datetime(2026, 1, 16, 4, 30), "Night Shift", window)
        self.assertEqual(got, _date(2026, 1, 15))

    def test_punch_after_previous_night_window_uses_own_day(self):
        from datetime import date as _date

        window = (datetime(2026, 1, 15, 18, 0), datetime(2026, 1, 16, 6, 0))
        got = self._run(datetime(2026, 1, 16, 9, 0), "Night Shift", window)
        self.assertEqual(got, _date(2026, 1, 16))

    def test_previous_day_not_overnight_uses_own_day(self):
        from datetime import date as _date

        got = self._run(datetime(2026, 1, 16, 4, 30), "Day Shift", None)
        self.assertEqual(got, _date(2026, 1, 16))


class TestShiftTypeForDateIncludesExpired(unittest.TestCase):
    """HRMS marks past assignments Inactive daily; the sync works on past
    dates, so the lookup must not drop them by status."""

    def test_status_not_filtered(self):
        from datetime import date as _date
        from unittest import mock

        import prakash_steel.utils.essl_biometric as mod

        fake = mock.MagicMock()
        fake.get_all.return_value = [
            {"shift_type": "Night Shift", "start_date": _date(2026, 10, 6), "end_date": _date(2026, 10, 6)}
        ]
        fake.db.get_value.return_value = "Day Shift 2"
        with mock.patch.object(mod, "frappe", fake):
            got = mod._get_shift_type_for_date("HR-EMP-00065", _date(2026, 10, 6))

        self.assertEqual(got, "Night Shift")
        self.assertNotIn("status", fake.get_all.call_args.kwargs["filters"])


class TestShiftDateOutsideCheckoutWindow(unittest.TestCase):
    """A punch HRMS attributes to yesterday's shift only folds back when it is
    inside that shift's check-out window."""

    def _run(self, ts, details):
        from unittest import mock

        import prakash_steel.utils.essl_biometric as mod

        with mock.patch.object(mod, "_previous_night_shift_date", return_value=None), mock.patch.object(
            mod, "_get_shift_type_for_date", return_value="General 1"
        ), mock.patch(
            "hrms.hr.doctype.shift_assignment.shift_assignment.get_shift_details", return_value=details
        ):
            return mod._get_employee_shift_date("HR-EMP-00016", ts)

    def test_morning_punch_after_window_stays_on_own_day(self):
        from datetime import date as _date

        import frappe

        details = frappe._dict(
            start_datetime=datetime(2026, 10, 8, 10, 0), actual_end=datetime(2026, 10, 9, 0, 0)
        )
        self.assertEqual(self._run(datetime(2026, 10, 9, 7, 26), details), _date(2026, 10, 9))

    def test_punch_inside_window_folds_back(self):
        from datetime import date as _date

        import frappe

        details = frappe._dict(
            start_datetime=datetime(2026, 10, 10, 8, 0), actual_end=datetime(2026, 10, 11, 3, 0)
        )
        self.assertEqual(self._run(datetime(2026, 10, 11, 2, 10), details), _date(2026, 10, 10))
