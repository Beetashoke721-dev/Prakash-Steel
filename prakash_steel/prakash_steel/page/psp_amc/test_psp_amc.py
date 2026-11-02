# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

"""Unit tests for the PSP AMC page backend — no DB / no site required."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from prakash_steel.prakash_steel.page.psp_amc import psp_amc as MOD


class D(dict):
	def __getattr__(self, key):
		return self.get(key)


def visit_dispatcher(visits_submitted=None, visits_draft=None, parts_by_visit=None):
	"""Build a frappe.get_all replacement dispatching by doctype + docstatus."""
	visits_submitted = visits_submitted or []
	visits_draft = visits_draft or []
	parts_by_visit = parts_by_visit or {}

	def _get_all(doctype, filters=None, fields=None, order_by=None):
		filters = filters or {}
		if doctype == "AMC Service Visit":
			return [
				D(v)
				for v in (visits_submitted if filters.get("docstatus") == 1 else visits_draft)
			]
		if doctype == "AMC Service Part":
			return [D(p) for p in parts_by_visit.get(filters.get("parent"), [])]
		if doctype == "AMC":
			return []
		return []

	return _get_all


class TestGetHistory(unittest.TestCase):
	@patch.object(MOD, "frappe")
	def test_newest_first_with_nested_parts(self, mock_frappe):
		mock_frappe.get_all = visit_dispatcher(
			visits_submitted=[
				{"name": "SER-1", "service_date": "2026-02-01", "part_change": 1},
				{"name": "SER-2", "service_date": "2026-03-01", "part_change": 0},
			],
			parts_by_visit={
				"SER-1": [
					{"part_no": "P-1", "part_description": "Seal", "qty": 2, "part_cost": 100},
				]
			},
		)

		history = MOD.get_history("AMC-0001")

		self.assertEqual([v["name"] for v in history], ["SER-1", "SER-2"])
		self.assertEqual(len(history[0]["parts"]), 1)
		self.assertEqual(history[0]["parts"][0]["part_no"], "P-1")
		# part_change falsy -> no part query, empty list
		self.assertEqual(history[1]["parts"], [])

	@patch.object(MOD, "frappe")
	def test_empty_when_no_submitted_visits(self, mock_frappe):
		mock_frappe.get_all = visit_dispatcher()
		self.assertEqual(MOD.get_history("AMC-0001"), [])


class TestGetUpcoming(unittest.TestCase):
	@patch.object(MOD, "frappe")
	def test_next_and_later_split(self, mock_frappe):
		mock_frappe.get_all = visit_dispatcher(
			visits_draft=[
				{"name": "SER-3", "estimated_service_date": "2026-09-16"},
				{"name": "SER-4", "estimated_service_date": "2026-09-23"},
				{"name": "SER-5", "estimated_service_date": "2026-09-30"},
			]
		)
		mock_frappe.db.get_value.return_value = "2026-12-31"

		upcoming = MOD.get_upcoming("AMC-0001")

		self.assertEqual(upcoming["next"]["name"], "SER-3")
		self.assertEqual([v["name"] for v in upcoming["later"]], ["SER-4", "SER-5"])

	@patch.object(MOD, "frappe")
	def test_flags_dates_beyond_contract_end(self, mock_frappe):
		mock_frappe.get_all = visit_dispatcher(
			visits_draft=[
				{"name": "SER-3", "estimated_service_date": "2026-09-16"},
				{"name": "SER-4", "estimated_service_date": "2027-01-05"},
			]
		)
		mock_frappe.db.get_value.return_value = "2026-12-31"

		upcoming = MOD.get_upcoming("AMC-0001")

		self.assertFalse(upcoming["next"]["beyond_contract"])
		self.assertTrue(upcoming["later"][0]["beyond_contract"])

	@patch.object(MOD, "frappe")
	def test_no_drafts(self, mock_frappe):
		mock_frappe.get_all = visit_dispatcher()
		mock_frappe.db.get_value.return_value = None

		upcoming = MOD.get_upcoming("AMC-0001")

		self.assertIsNone(upcoming["next"])
		self.assertEqual(upcoming["later"], [])


class TestFlattenReportLines(unittest.TestCase):
	def test_explodes_one_row_per_part_and_skips_parent_fields(self):
		history = [
			{
				"name": "SER-1",
				"service_date": "2026-03-01",
				"overall_equipment_condition": "Good",
				"part_change": 1,
				"parts": [
					{
						"part_no": "P-1",
						"part_description": "Seal",
						"part_cost": 100,
						"extra_charges": 10,
						"qty": 2,
					},
					{
						"part_no": "P-2",
						"part_description": "Bearing",
						"part_cost": 200,
						"extra_charges": 0,
						"qty": 1,
					},
				],
			}
		]

		lines = MOD.flatten_report_lines(history)

		self.assertEqual(len(lines), 2)
		self.assertEqual([l["part_no"] for l in lines], ["P-1", "P-2"])
		self.assertEqual(lines[0]["part_change"], "Yes")
		self.assertEqual(lines[0]["service_date"], "2026-03-01")
		# no AMC-level keys leaked in — including Next Service Date, which is
		# a parent-only field (AMC.estimated_service_date), not per-line.
		self.assertNotIn("item", lines[0])
		self.assertNotIn("supplier", lines[0])
		self.assertNotIn("estimated_service_date", lines[0])
		self.assertNotIn("next_service_date", lines[0])

	def test_visit_without_parts_yields_single_blank_part_row(self):
		history = [
			{
				"name": "SER-2",
				"service_date": "2026-04-01",
				"overall_equipment_condition": "Satisfactory",
				"part_change": 0,
				"parts": [],
			}
		]

		lines = MOD.flatten_report_lines(history)

		self.assertEqual(len(lines), 1)
		self.assertEqual(lines[0]["part_change"], "No")
		self.assertIsNone(lines[0]["part_no"])
		self.assertIsNone(lines[0]["qty"])


class TestGetAmcList(unittest.TestCase):
	@patch.object(MOD, "frappe")
	def test_lists_submitted_amcs_with_next_date(self, mock_frappe):
		mock_frappe.get_all.return_value = [
			D(
				{
					"name": "AMC-0001",
					"item": "PUMP",
					"services_remaining": 3,
					"estimated_service_date": date(2026, 9, 16),
				}
			)
		]

		rows = MOD.get_amc_list()

		# next_service_date mirrors the AMC's own estimated_service_date field
		# (no per-visit schedule lookup / no extra db.get_value call).
		self.assertEqual(rows[0]["next_service_date"], date(2026, 9, 16))
		mock_frappe.db.get_value.assert_not_called()
		doctype, filters = mock_frappe.get_all.call_args[0][0], mock_frappe.get_all.call_args[1]["filters"]
		self.assertEqual(doctype, "AMC")
		self.assertEqual(filters, {"docstatus": 1})


class TestGetAmcDetails(unittest.TestCase):
	@patch.object(MOD, "frappe")
	def test_assembles_header_history_report_lines_upcoming(self, mock_frappe):
		mock_frappe.db.get_value.side_effect = [
			D(
				{
					"name": "AMC-0001",
					"services_remaining": 2,
					"estimated_service_date": "2026-09-16",
				}
			),  # header
			"2026-12-31",  # amc_end_date inside get_upcoming
		]
		mock_frappe.get_all = visit_dispatcher(
			visits_submitted=[
				{"name": "SER-1", "service_date": "2026-02-01", "part_change": 0},
				{"name": "SER-0", "service_date": "2026-04-01", "part_change": 0},
			],
			visits_draft=[{"name": "SER-2", "estimated_service_date": "2026-09-23"}],
		)

		result = MOD.get_amc_details("AMC-0001")

		self.assertEqual(result["header"]["name"], "AMC-0001")
		# next_service_date comes straight from the AMC's own field, not the
		# draft visit schedule (that draft is "2026-09-23", not this).
		self.assertEqual(result["header"]["next_service_date"], "2026-09-16")
		self.assertEqual(result["header"]["amc_applicable"], "Yes")
		# last_service_date = latest submitted visit's service_date
		self.assertEqual(result["header"]["last_service_date"], "2026-04-01")
		self.assertEqual(len(result["history"]), 2)
		self.assertEqual(len(result["report_lines"]), 2)
		self.assertEqual(result["upcoming"]["next"]["name"], "SER-2")

	@patch.object(MOD, "frappe")
	def test_throws_when_amc_missing(self, mock_frappe):
		mock_frappe.db.get_value.return_value = None
		mock_frappe.throw.side_effect = RuntimeError

		with self.assertRaises(RuntimeError):
			MOD.get_amc_details("AMC-XXXX")


if __name__ == "__main__":
	unittest.main()
