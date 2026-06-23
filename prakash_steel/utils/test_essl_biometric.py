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


if __name__ == "__main__":
    unittest.main()
