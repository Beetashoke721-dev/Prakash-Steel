# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for throughput report — no DB required."""

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.throughput.throughput"


class TestGetColumns(unittest.TestCase):
	def test_returns_list_with_fieldnames(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_columns

		cols = get_columns()
		self.assertIsInstance(cols, list)
		self.assertGreater(len(cols), 0)
		for col in cols:
			self.assertIn("fieldname", col)
			self.assertIn("label", col)
			self.assertIn("fieldtype", col)

	def test_includes_tvc_and_bright_rolling_fieldnames(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_columns

		fieldnames = {col["fieldname"] for col in get_columns()}
		for expected in ("tvc", "tvc_per_kg", "t_per_kg", "t_percent", "total_t",
						 "rolling_time_kgs_hr", "bright_time_kgs_hr", "rb_code", "rm_code"):
			self.assertIn(expected, fieldnames)


class TestRoundUp1dp(unittest.TestCase):
	def test_rounds_up_fraction(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import round_up_1dp

		self.assertEqual(round_up_1dp(1.53), 1.6)
		self.assertEqual(round_up_1dp(0.12), 0.2)

	def test_exact_tenth_stays_the_same(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import round_up_1dp

		self.assertEqual(round_up_1dp(2.0), 2.0)
		self.assertEqual(round_up_1dp(1.5), 1.5)

	def test_zero_stays_zero(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import round_up_1dp

		self.assertEqual(round_up_1dp(0), 0.0)


class TestGetTvc(unittest.TestCase):
	def test_jw_service_and_scrap_are_zero(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_tvc

		self.assertEqual(get_tvc("JW Service", 10, 5, 2), 0)
		self.assertEqual(get_tvc("Scrap", 10, 5, 2), 0)

	def test_quantity_rate_item_types(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_tvc

		for item_type in ("Traded", "BO", "RM"):
			self.assertEqual(get_tvc(item_type, 10, 5, 2), 50)

	def test_qty_per_unit_item_types_scale_by_ratio(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_tvc

		for item_type in ("BB", "RB"):
			self.assertEqual(get_tvc(item_type, 10, 5, 2), 100)

	def test_unknown_item_type_returns_none(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_tvc

		self.assertIsNone(get_tvc("Something Else", 10, 5, 2))
		self.assertIsNone(get_tvc(None, 10, 5, 2))


class TestFormatMonthLabel(unittest.TestCase):
	def test_formats_month_dash_two_digit_year(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import format_month_label

		self.assertEqual(format_month_label(date(2026, 4, 15)), "4-26")
		self.assertEqual(format_month_label(date(2030, 12, 1)), "12-30")


class TestGetLastPurchaseOnOrBefore(unittest.TestCase):
	def test_returns_none_when_no_purchases(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_last_purchase_on_or_before

		self.assertIsNone(get_last_purchase_on_or_before(None, date(2026, 1, 1)))
		self.assertIsNone(get_last_purchase_on_or_before([], date(2026, 1, 1)))

	def test_returns_none_when_invoice_date_before_all_purchases(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_last_purchase_on_or_before

		purchases = [SimpleNamespace(posting_date=date(2026, 2, 1), rate=10)]
		self.assertIsNone(get_last_purchase_on_or_before(purchases, date(2026, 1, 1)))

	def test_returns_latest_purchase_not_after_invoice_date(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_last_purchase_on_or_before

		purchases = [
			SimpleNamespace(posting_date=date(2026, 1, 1), rate=10),
			SimpleNamespace(posting_date=date(2026, 2, 1), rate=20),
			SimpleNamespace(posting_date=date(2026, 4, 1), rate=40),
		]
		result = get_last_purchase_on_or_before(purchases, date(2026, 3, 1))
		self.assertEqual(result.rate, 20)

	def test_exact_date_match_is_returned(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_last_purchase_on_or_before

		purchases = [
			SimpleNamespace(posting_date=date(2026, 1, 1), rate=10),
			SimpleNamespace(posting_date=date(2026, 2, 1), rate=20),
		]
		result = get_last_purchase_on_or_before(purchases, date(2026, 2, 1))
		self.assertEqual(result.rate, 20)

	def test_never_returns_a_later_purchase(self):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_last_purchase_on_or_before

		purchases = [SimpleNamespace(posting_date=date(2026, 5, 1), rate=50)]
		self.assertIsNone(get_last_purchase_on_or_before(purchases, date(2026, 4, 1)))


class TestApplyCreditNoteAdjustments(unittest.TestCase):
	@patch(MOD + ".frappe")
	def test_no_invoice_numbers_is_noop(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import apply_credit_note_adjustments

		data = [{"invoice_number": None, "item_code": "ITEM-1", "quantity": 10, "item_price": 5}]
		apply_credit_note_adjustments(data)
		mock_frappe.db.sql.assert_not_called()
		self.assertEqual(data[0]["quantity"], 10)

	@patch(MOD + ".frappe")
	def test_no_credit_notes_found_is_noop(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import apply_credit_note_adjustments

		mock_frappe.db.sql.return_value = []
		data = [{"invoice_number": "SI-1", "item_code": "ITEM-1", "quantity": 10, "item_price": 5}]
		apply_credit_note_adjustments(data)
		self.assertEqual(data[0]["quantity"], 10)

	@patch(MOD + ".frappe")
	def test_stock_return_reduces_quantity_proportionally(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import apply_credit_note_adjustments

		mock_frappe.db.sql.return_value = [
			SimpleNamespace(
				return_against="SI-1", item_code="ITEM-1", qty=4, amount=40,
				update_stock=1, dn_is_return=0,
			)
		]
		# Two rows for the same invoice/item share the qty reduction by their share of qty.
		data = [
			{"invoice_number": "SI-1", "item_code": "ITEM-1", "quantity": 6, "item_price": 10},
			{"invoice_number": "SI-1", "item_code": "ITEM-1", "quantity": 4, "item_price": 10},
		]
		apply_credit_note_adjustments(data)
		self.assertAlmostEqual(data[0]["quantity"], 6 - 4 * 0.6)
		self.assertAlmostEqual(data[1]["quantity"], 4 - 4 * 0.4)

	@patch(MOD + ".frappe")
	def test_stock_return_via_delivery_note_flag(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import apply_credit_note_adjustments

		mock_frappe.db.sql.return_value = [
			SimpleNamespace(
				return_against="SI-1", item_code="ITEM-1", qty=5, amount=50,
				update_stock=0, dn_is_return=1,
			)
		]
		data = [{"invoice_number": "SI-1", "item_code": "ITEM-1", "quantity": 10, "item_price": 10}]
		apply_credit_note_adjustments(data)
		self.assertEqual(data[0]["quantity"], 5)

	@patch(MOD + ".frappe")
	def test_billing_only_credit_note_reduces_item_price(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import apply_credit_note_adjustments

		mock_frappe.db.sql.return_value = [
			SimpleNamespace(
				return_against="SI-1", item_code="ITEM-1", qty=4, amount=40,
				update_stock=0, dn_is_return=0,
			)
		]
		data = [{"invoice_number": "SI-1", "item_code": "ITEM-1", "quantity": 10, "item_price": 10}]
		apply_credit_note_adjustments(data)
		# rate_reduction = 40 / 10 = 4
		self.assertEqual(data[0]["item_price"], 6)
		self.assertEqual(data[0]["quantity"], 10)

	@patch(MOD + ".frappe")
	def test_credit_note_with_no_matching_row_is_ignored(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import apply_credit_note_adjustments

		mock_frappe.db.sql.return_value = [
			SimpleNamespace(
				return_against="SI-OTHER", item_code="ITEM-1", qty=4, amount=40,
				update_stock=1, dn_is_return=0,
			)
		]
		data = [{"invoice_number": "SI-1", "item_code": "ITEM-1", "quantity": 10, "item_price": 10}]
		apply_credit_note_adjustments(data)
		self.assertEqual(data[0]["quantity"], 10)

	@patch(MOD + ".frappe")
	def test_zero_group_qty_total_is_skipped_safely(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import apply_credit_note_adjustments

		mock_frappe.db.sql.return_value = [
			SimpleNamespace(
				return_against="SI-1", item_code="ITEM-1", qty=4, amount=40,
				update_stock=1, dn_is_return=0,
			)
		]
		data = [{"invoice_number": "SI-1", "item_code": "ITEM-1", "quantity": 0, "item_price": 10}]
		# Should not raise a ZeroDivisionError.
		apply_credit_note_adjustments(data)
		self.assertEqual(data[0]["quantity"], 0)


	@patch(MOD + ".frappe")
	def test_debit_note_raises_item_price(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import apply_credit_note_adjustments

		mock_frappe.db.sql.return_value = [
			SimpleNamespace(
				return_against="SI-1", item_code="ITEM-1", qty=10, amount=30,
				update_stock=0, is_debit_note=1, dn_is_return=0,
			)
		]
		data = [{"invoice_number": "SI-1", "item_code": "ITEM-1", "quantity": 10, "item_price": 10}]
		apply_credit_note_adjustments(data)
		# rate_increase = 30 / 10 = 3; quantity is untouched.
		self.assertEqual(data[0]["item_price"], 13)
		self.assertEqual(data[0]["quantity"], 10)

	@patch(MOD + ".frappe")
	def test_debit_note_spreads_over_split_rows(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import apply_credit_note_adjustments

		mock_frappe.db.sql.return_value = [
			SimpleNamespace(
				return_against="SI-1", item_code="ITEM-1", qty=10, amount=20,
				update_stock=0, is_debit_note=1, dn_is_return=0,
			)
		]
		data = [
			{"invoice_number": "SI-1", "item_code": "ITEM-1", "quantity": 6, "item_price": 10},
			{"invoice_number": "SI-1", "item_code": "ITEM-1", "quantity": 4, "item_price": 10},
		]
		apply_credit_note_adjustments(data)
		self.assertEqual(data[0]["item_price"], 12)
		self.assertEqual(data[1]["item_price"], 12)
		self.assertEqual(data[0]["quantity"], 6)

	@patch(MOD + ".frappe")
	def test_credit_and_debit_note_on_same_row_net_out(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import apply_credit_note_adjustments

		mock_frappe.db.sql.return_value = [
			SimpleNamespace(
				return_against="SI-1", item_code="ITEM-1", qty=-10, amount=-40,
				update_stock=0, is_debit_note=0, dn_is_return=0,
			),
			SimpleNamespace(
				return_against="SI-1", item_code="ITEM-1", qty=10, amount=15,
				update_stock=0, is_debit_note=1, dn_is_return=0,
			),
		]
		data = [{"invoice_number": "SI-1", "item_code": "ITEM-1", "quantity": 10, "item_price": 10}]
		apply_credit_note_adjustments(data)
		# 10 - 40/10 + 15/10
		self.assertEqual(data[0]["item_price"], 7.5)


class TestSetRollingTimeColumn(unittest.TestCase):
	@patch(MOD + ".frappe")
	def test_rb_item_gets_rolling_time_columns(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import set_rolling_time_column

		mock_frappe.get_all.return_value = [
			SimpleNamespace(item_code="ITEM-RB", per_hour_planned_qty=100)
		]
		data = [
			{"item_code": "ITEM-RB", "item_type": "RB", "category_name": "Std", "quantity": 250, "t_per_kg": 2}
		]
		set_rolling_time_column(data)
		self.assertEqual(data[0]["rolling_time_kgs_hr"], 100)
		self.assertEqual(data[0]["total_rolling_time_hrs"], 2.5)
		self.assertEqual(data[0]["rolling_t_per_cu"], 200)

	@patch(MOD + ".frappe")
	def test_jw_category_rb_item_is_skipped(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import set_rolling_time_column

		mock_frappe.get_all.return_value = [
			SimpleNamespace(item_code="ITEM-RB", per_hour_planned_qty=100)
		]
		data = [
			{"item_code": "ITEM-RB", "item_type": "RB", "category_name": "JW", "quantity": 250, "t_per_kg": 2}
		]
		set_rolling_time_column(data)
		self.assertIsNone(data[0]["rolling_time_kgs_hr"])
		self.assertIsNone(data[0]["total_rolling_time_hrs"])
		self.assertIsNone(data[0]["rolling_t_per_cu"])

	@patch(MOD + ".frappe")
	def test_non_rb_item_is_skipped(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import set_rolling_time_column

		mock_frappe.get_all.return_value = []
		data = [{"item_code": "ITEM-BB", "item_type": "BB", "category_name": "Std", "quantity": 100, "t_per_kg": 2}]
		set_rolling_time_column(data)
		self.assertIsNone(data[0]["rolling_time_kgs_hr"])

	@patch(MOD + ".frappe")
	def test_missing_rolling_algo_row_leaves_hours_none(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import set_rolling_time_column

		mock_frappe.get_all.return_value = []
		data = [{"item_code": "ITEM-RB", "item_type": "RB", "category_name": "Std", "quantity": 100, "t_per_kg": 2}]
		set_rolling_time_column(data)
		self.assertIsNone(data[0]["rolling_time_kgs_hr"])
		self.assertIsNone(data[0]["total_rolling_time_hrs"])


class TestSetBrightMachineColumn(unittest.TestCase):
	@patch(MOD + ".frappe")
	def test_bb_item_gets_bright_machine_columns(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import set_bright_machine_column

		mock_frappe.db.sql.return_value = [
			SimpleNamespace(item_code="ITEM-BB", machine_group_name="M1", mt_per_hour_production=50)
		]
		data = [
			{"item_code": "ITEM-BB", "item_type": "BB", "category_name": "Std", "quantity": 125, "t_per_kg": 3}
		]
		set_bright_machine_column(data)
		self.assertEqual(data[0]["bright_machine"], "M1")
		self.assertEqual(data[0]["bright_time_kgs_hr"], 50)
		self.assertEqual(data[0]["total_bright_time_hrs"], 2.5)
		self.assertEqual(data[0]["bright_t_per_cu"], 150)

	@patch(MOD + ".frappe")
	def test_jw_category_bb_item_is_skipped(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import set_bright_machine_column

		mock_frappe.db.sql.return_value = [
			SimpleNamespace(item_code="ITEM-BB", machine_group_name="M1", mt_per_hour_production=50)
		]
		data = [
			{"item_code": "ITEM-BB", "item_type": "BB", "category_name": "JW", "quantity": 125, "t_per_kg": 3}
		]
		set_bright_machine_column(data)
		self.assertIsNone(data[0]["bright_machine"])

	@patch(MOD + ".frappe")
	def test_non_bb_item_is_skipped(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import set_bright_machine_column

		mock_frappe.db.sql.return_value = []
		data = [{"item_code": "ITEM-RB", "item_type": "RB", "category_name": "Std", "quantity": 100, "t_per_kg": 3}]
		set_bright_machine_column(data)
		self.assertIsNone(data[0]["bright_machine"])
		self.assertIsNone(data[0]["bright_time_kgs_hr"])


class TestSetPurchaseRateColumns(unittest.TestCase):
	@patch(MOD + ".frappe")
	def test_no_source_items_clears_rate_columns(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import set_purchase_rate_columns

		data = [{"_rate_source_item": None, "invoice_date": date(2026, 4, 1)}]
		set_purchase_rate_columns(data)
		self.assertIsNone(data[0]["rate"])
		self.assertIsNone(data[0]["purchase_month_taken"])
		self.assertNotIn("_rate_source_item", data[0])
		mock_frappe.db.sql.assert_not_called()

	@patch(MOD + ".frappe")
	def test_uses_same_month_average_rate_when_available(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import set_purchase_rate_columns

		monthly_rows = [SimpleNamespace(item_code="RM-1", y=2026, m=4, avg_rate=12.5)]
		mock_frappe.db.sql.side_effect = [monthly_rows, []]
		data = [{"_rate_source_item": "RM-1", "invoice_date": date(2026, 4, 15)}]
		set_purchase_rate_columns(data)
		self.assertEqual(data[0]["rate"], 12.5)
		self.assertIsNone(data[0]["purchase_month_taken"])

	@patch(MOD + ".frappe")
	def test_falls_back_to_last_purchase_when_no_same_month_rate(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import set_purchase_rate_columns

		purchase_rows = [SimpleNamespace(item_code="RM-1", posting_date=date(2026, 2, 1), rate=9.0)]
		mock_frappe.db.sql.side_effect = [[], purchase_rows]
		data = [{"_rate_source_item": "RM-1", "invoice_date": date(2026, 4, 15)}]
		set_purchase_rate_columns(data)
		self.assertEqual(data[0]["rate"], 9.0)
		self.assertEqual(data[0]["purchase_month_taken"], "2-26")

	@patch(MOD + ".frappe")
	def test_no_purchase_history_leaves_rate_none(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import set_purchase_rate_columns

		mock_frappe.db.sql.side_effect = [[], []]
		data = [{"_rate_source_item": "RM-1", "invoice_date": date(2026, 4, 15)}]
		set_purchase_rate_columns(data)
		self.assertIsNone(data[0]["rate"])
		self.assertIsNone(data[0]["purchase_month_taken"])


class TestGetDefaultBomConsumption(unittest.TestCase):
	@patch(MOD + ".frappe")
	@patch(MOD + ".get_default_bom")
	def test_no_default_bom_returns_none(self, mock_get_default_bom, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_default_bom_consumption

		mock_get_default_bom.return_value = None
		self.assertIsNone(get_default_bom_consumption("ITEM-1"))

	@patch(MOD + ".frappe")
	@patch(MOD + ".get_default_bom")
	def test_no_bom_item_returns_none(self, mock_get_default_bom, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_default_bom_consumption

		mock_get_default_bom.return_value = "BOM-1"
		mock_frappe.db.get_value.return_value = None
		self.assertIsNone(get_default_bom_consumption("ITEM-1"))

	@patch(MOD + ".frappe")
	@patch(MOD + ".get_default_bom")
	def test_computes_consumption_ratio(self, mock_get_default_bom, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_default_bom_consumption

		mock_get_default_bom.return_value = "BOM-1"
		mock_frappe.db.get_value.side_effect = [
			SimpleNamespace(item_code="RM-1", qty=2),
			10,
		]
		mock_frappe._dict.side_effect = lambda **kw: SimpleNamespace(**kw)
		result = get_default_bom_consumption("ITEM-1")
		self.assertEqual(result.item_code, "RM-1")
		self.assertEqual(result.ratio, 0.2)

	@patch(MOD + ".frappe")
	@patch(MOD + ".get_default_bom")
	def test_zero_bom_quantity_falls_back_to_one(self, mock_get_default_bom, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import get_default_bom_consumption

		mock_get_default_bom.return_value = "BOM-1"
		mock_frappe.db.get_value.side_effect = [
			SimpleNamespace(item_code="RM-1", qty=3),
			0,
		]
		mock_frappe._dict.side_effect = lambda **kw: SimpleNamespace(**kw)
		result = get_default_bom_consumption("ITEM-1")
		self.assertEqual(result.ratio, 3)


class TestPreloadDefaultBomNames(unittest.TestCase):
	@patch(MOD + ".frappe")
	def test_empty_item_codes_returns_empty_without_querying(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import preload_default_bom_names

		result = preload_default_bom_names(set())
		self.assertEqual(result, {})
		mock_frappe.db.sql.assert_not_called()

	@patch(MOD + ".frappe")
	def test_falls_through_tiers_for_unresolved_items(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import preload_default_bom_names

		# Tier 1 (active+default+submitted) resolves ITEM-A; tier 2 (active+submitted)
		# resolves ITEM-B; tier 3 (active) resolves ITEM-C. ITEM-D is never found.
		mock_frappe.db.sql.side_effect = [
			[SimpleNamespace(item="ITEM-A", name="BOM-A")],
			[SimpleNamespace(item="ITEM-B", name="BOM-B")],
			[SimpleNamespace(item="ITEM-C", name="BOM-C")],
		]
		result = preload_default_bom_names({"ITEM-A", "ITEM-B", "ITEM-C", "ITEM-D"})
		self.assertEqual(result, {"ITEM-A": "BOM-A", "ITEM-B": "BOM-B", "ITEM-C": "BOM-C"})
		self.assertEqual(mock_frappe.db.sql.call_count, 3)

	@patch(MOD + ".frappe")
	def test_stops_once_everything_is_resolved(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import preload_default_bom_names

		mock_frappe.db.sql.return_value = [SimpleNamespace(item="ITEM-A", name="BOM-A")]
		result = preload_default_bom_names({"ITEM-A"})
		self.assertEqual(result, {"ITEM-A": "BOM-A"})
		# Tier 1 already resolved the only item, so tiers 2 and 3 never run.
		self.assertEqual(mock_frappe.db.sql.call_count, 1)

	@patch(MOD + ".frappe")
	def test_most_recent_bom_wins_within_a_tier(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import preload_default_bom_names

		# ORDER BY item, creation DESC - the first row per item in the result is the
		# most recently created one, same as the single-item order_by="creation desc".
		mock_frappe.db.sql.return_value = [
			SimpleNamespace(item="ITEM-A", name="BOM-NEW"),
			SimpleNamespace(item="ITEM-A", name="BOM-OLD"),
		]
		result = preload_default_bom_names({"ITEM-A"})
		self.assertEqual(result, {"ITEM-A": "BOM-NEW"})


class TestPreloadBomConsumption(unittest.TestCase):
	@patch(MOD + ".frappe")
	def test_empty_item_codes_returns_empty_without_querying(self, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import preload_bom_consumption

		result = preload_bom_consumption(set())
		self.assertEqual(result, {})
		mock_frappe.db.sql.assert_not_called()
		mock_frappe.get_all.assert_not_called()

	@patch(MOD + ".frappe")
	@patch(MOD + ".preload_default_bom_names")
	def test_item_with_no_default_bom_maps_to_none(self, mock_preload_names, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import preload_bom_consumption

		mock_preload_names.return_value = {}
		result = preload_bom_consumption({"ITEM-1"})
		self.assertEqual(result, {"ITEM-1": None})
		mock_frappe.db.sql.assert_not_called()

	@patch(MOD + ".frappe")
	@patch(MOD + ".preload_default_bom_names")
	def test_builds_consumption_for_every_item(self, mock_preload_names, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import preload_bom_consumption

		mock_preload_names.return_value = {"ITEM-1": "BOM-1", "ITEM-2": "BOM-2"}
		mock_frappe.db.sql.return_value = [
			SimpleNamespace(parent="BOM-1", item_code="RM-1", qty=2),
			SimpleNamespace(parent="BOM-2", item_code="RM-2", qty=3),
		]
		mock_frappe.get_all.return_value = [
			SimpleNamespace(name="BOM-1", quantity=10),
			SimpleNamespace(name="BOM-2", quantity=0),  # falls back to 1.0
		]
		mock_frappe._dict.side_effect = lambda **kw: SimpleNamespace(**kw)

		result = preload_bom_consumption({"ITEM-1", "ITEM-2"})
		self.assertEqual(result["ITEM-1"].item_code, "RM-1")
		self.assertEqual(result["ITEM-1"].ratio, 0.2)
		self.assertEqual(result["ITEM-2"].item_code, "RM-2")
		self.assertEqual(result["ITEM-2"].ratio, 3)

	@patch(MOD + ".frappe")
	@patch(MOD + ".preload_default_bom_names")
	def test_bom_with_no_items_maps_to_none(self, mock_preload_names, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import preload_bom_consumption

		mock_preload_names.return_value = {"ITEM-1": "BOM-1"}
		mock_frappe.db.sql.return_value = []  # BOM-1 has no BOM Item rows
		mock_frappe.get_all.return_value = [SimpleNamespace(name="BOM-1", quantity=10)]
		result = preload_bom_consumption({"ITEM-1"})
		self.assertIsNone(result["ITEM-1"])


class TestSetBomDerivedColumns(unittest.TestCase):
	@patch(MOD + ".frappe")
	@patch(MOD + ".preload_bom_consumption")
	def test_two_level_bom_chain(self, mock_preload_consumption, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import set_bom_derived_columns

		def preload_side_effect(item_codes):
			result = {}
			if "ITEM-1" in item_codes:
				result["ITEM-1"] = SimpleNamespace(item_code="RB-1", ratio=2.0)
			if "RB-1" in item_codes:
				result["RB-1"] = SimpleNamespace(item_code="RM-1", ratio=0.5)
			return result

		mock_preload_consumption.side_effect = preload_side_effect
		mock_frappe.get_all.return_value = [
			SimpleNamespace(name="RB-1", custom_item_type="RB", custom_category_name="Std"),
			SimpleNamespace(name="RM-1", custom_item_type="RM", custom_category_name="RawSteel"),
		]
		data = [{"item_code": "ITEM-1", "category_name": "Finished"}]
		set_bom_derived_columns(data)
		self.assertEqual(data[0]["rb_code"], "RB-1")
		self.assertEqual(data[0]["rb_type"], "RB")
		self.assertEqual(data[0]["rm_code"], "RM-1")
		self.assertEqual(data[0]["item_category"], "RawSteel")
		self.assertEqual(data[0]["qty_per_unit"], 1.0)

	@patch(MOD + ".frappe")
	@patch(MOD + ".preload_bom_consumption")
	def test_no_bom_falls_back_to_own_category(self, mock_preload_consumption, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import set_bom_derived_columns

		mock_preload_consumption.return_value = {}
		mock_frappe.get_all.return_value = []
		data = [{"item_code": "ITEM-1", "category_name": "Traded"}]
		set_bom_derived_columns(data)
		self.assertIsNone(data[0]["rb_code"])
		self.assertIsNone(data[0]["rb_type"])
		self.assertIsNone(data[0]["rm_code"])
		self.assertEqual(data[0]["item_category"], "Traded")
		self.assertIsNone(data[0]["qty_per_unit"])

	@patch(MOD + ".frappe")
	@patch(MOD + ".preload_bom_consumption")
	def test_only_first_level_bom_uses_its_ratio_alone(self, mock_preload_consumption, mock_frappe):
		from prakash_steel.prakash_steel.report.throughput.throughput import set_bom_derived_columns

		def preload_side_effect(item_codes):
			if "ITEM-1" in item_codes:
				return {"ITEM-1": SimpleNamespace(item_code="RB-1", ratio=3.0)}
			return {}

		mock_preload_consumption.side_effect = preload_side_effect
		mock_frappe.get_all.return_value = [
			SimpleNamespace(name="RB-1", custom_item_type="RB", custom_category_name="Std"),
		]
		data = [{"item_code": "ITEM-1", "category_name": "Finished"}]
		set_bom_derived_columns(data)
		self.assertEqual(data[0]["rb_code"], "RB-1")
		self.assertEqual(data[0]["rm_code"], None)
		# No RM code -> item_category falls back to RB Code's own category.
		self.assertEqual(data[0]["item_category"], "Std")
		self.assertEqual(data[0]["qty_per_unit"], 3.0)


class TestExecute(unittest.TestCase):
	@patch(MOD + ".get_default_bom")
	@patch(MOD + ".frappe")
	def test_returns_tuple_for_empty_data(self, mock_frappe, mock_get_default_bom):
		from prakash_steel.prakash_steel.report.throughput.throughput import execute

		mock_frappe.db.sql.return_value = []
		mock_frappe.db.get_single_value.return_value = "Monday"
		mock_frappe.get_all.return_value = []
		cols, data = execute({})
		self.assertIsInstance(cols, list)
		self.assertEqual(data, [])


if __name__ == "__main__":
	unittest.main()
