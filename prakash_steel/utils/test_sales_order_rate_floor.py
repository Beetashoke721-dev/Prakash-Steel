# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for utils/sales_order_rate_floor.py — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.utils.sales_order_rate_floor"


def _row(idx, rate, item_code="ITEM-001"):
    row = MagicMock()
    row.idx = idx
    row.rate = rate
    row.item_code = item_code
    row.item_name = item_code
    return row


def _doc(rows, transaction_date="2026-09-08"):
    doc = MagicMock()
    doc.transaction_date = transaction_date
    doc.get = lambda k, d=None: rows if k == "items" else d
    return doc


def _meta(grade="MS", shape="Round", component="24mm to 54mm"):
    m = MagicMock()
    m.name = "ITEM-001"
    m.custom_grade = grade
    m.custom_shape = shape
    m.custom_rate_component = component
    return m


class TestValidateItemRateFloor(unittest.TestCase):
    def setUp(self):
        p = patch(MOD + ".frappe")
        self.frappe = p.start()
        self.addCleanup(p.stop)
        self.frappe.bold.side_effect = lambda x: f"<b>{x}</b>"
        self.frappe.format.side_effect = lambda v, opts=None: str(v)
        self.frappe.throw.side_effect = Exception("rate below minimum")
        self.frappe.session.user = "sales.user@example.com"
        # no bypassed users by default
        settings = MagicMock()
        settings.get.return_value = []
        self.frappe.get_cached_doc.return_value = settings

        rate_doc = MagicMock()
        rate_doc.name = "2026-09-07"
        rate_doc.date = "2026-09-07"
        self.rate_doc = rate_doc

    def _call(self, doc):
        from prakash_steel.utils.sales_order_rate_floor import validate_item_rate_floor

        return validate_item_rate_floor(doc)

    @patch(MOD + ".submitted_rate_doc_asof", return_value=None)
    def test_noop_when_no_submitted_rate_doc(self, _asof):
        self._call(_doc([_row(1, 5.0)]))
        self.frappe.throw.assert_not_called()

    def test_noop_when_no_items(self):
        self._call(_doc([]))
        self.frappe.throw.assert_not_called()

    @patch(MOD + ".component_rate", return_value=100.0)
    def test_throws_when_rate_below_floor(self, _cr):
        with patch(MOD + ".submitted_rate_doc_asof", return_value=self.rate_doc):
            self.frappe.get_all.return_value = [_meta()]
            with self.assertRaises(Exception):
                self._call(_doc([_row(1, 99.99)]))
        self.frappe.throw.assert_called_once()
        self.assertIn("Row 1", self.frappe.throw.call_args[0][0])

    @patch(MOD + ".component_rate", return_value=100.0)
    def test_passes_when_rate_equals_floor(self, _cr):
        with patch(MOD + ".submitted_rate_doc_asof", return_value=self.rate_doc):
            self.frappe.get_all.return_value = [_meta()]
            self._call(_doc([_row(1, 100.0)]))
        self.frappe.throw.assert_not_called()

    @patch(MOD + ".component_rate", return_value=100.0)
    def test_skips_item_without_rate_component(self, _cr):
        with patch(MOD + ".submitted_rate_doc_asof", return_value=self.rate_doc):
            self.frappe.get_all.return_value = [_meta(component=None)]
            self._call(_doc([_row(1, 1.0)]))
        self.frappe.throw.assert_not_called()

    @patch(MOD + ".component_rate", return_value=None)
    def test_skips_item_with_unmapped_grade_shape(self, _cr):
        with patch(MOD + ".submitted_rate_doc_asof", return_value=self.rate_doc):
            self.frappe.get_all.return_value = [_meta(grade="EN8D")]
            self._call(_doc([_row(1, 1.0)]))
        self.frappe.throw.assert_not_called()


class TestRateBypass(unittest.TestCase):
    def setUp(self):
        p = patch(MOD + ".frappe")
        self.frappe = p.start()
        self.addCleanup(p.stop)
        self.frappe.bold.side_effect = lambda x: f"<b>{x}</b>"
        self.frappe.format.side_effect = lambda v, opts=None: str(v)
        self.frappe.throw.side_effect = Exception("rate below minimum")

        rate_doc = MagicMock()
        rate_doc.name = "2026-09-07"
        rate_doc.date = "2026-09-07"
        self.rate_doc = rate_doc

    def _bypass_row(self, user):
        row = MagicMock()
        row.user = user
        return row

    @patch(MOD + ".component_rate", return_value=100.0)
    @patch(MOD + ".submitted_rate_doc_asof")
    def test_bypassed_user_skips_check_entirely(self, asof, _cr):
        from prakash_steel.utils.sales_order_rate_floor import validate_item_rate_floor

        self.frappe.session.user = "bypassed@example.com"
        settings = MagicMock()
        settings.get.return_value = [self._bypass_row("bypassed@example.com")]
        self.frappe.get_cached_doc.return_value = settings

        # the hook itself no longer prompts - the client asks for confirmation
        # before the submit request is even sent (get_rate_floor_warnings)
        validate_item_rate_floor(_doc([_row(1, 0.0)]))
        self.frappe.throw.assert_not_called()
        asof.assert_not_called()

    @patch(MOD + ".component_rate", return_value=100.0)
    def test_non_bypassed_user_still_blocked(self, _cr):
        from prakash_steel.utils.sales_order_rate_floor import validate_item_rate_floor

        self.frappe.session.user = "regular@example.com"
        settings = MagicMock()
        settings.get.return_value = [self._bypass_row("bypassed@example.com")]
        self.frappe.get_cached_doc.return_value = settings

        with patch(MOD + ".submitted_rate_doc_asof", return_value=self.rate_doc):
            self.frappe.get_all.return_value = [_meta()]
            with self.assertRaises(Exception):
                validate_item_rate_floor(_doc([_row(1, 0.0)]))
        self.frappe.throw.assert_called_once()


class TestGetRateFloorWarnings(unittest.TestCase):
    def setUp(self):
        p = patch(MOD + ".frappe")
        self.frappe = p.start()
        self.addCleanup(p.stop)
        self.frappe.bold.side_effect = lambda x: f"<b>{x}</b>"
        self.frappe.format.side_effect = lambda v, opts=None: str(v)
        self.frappe.parse_json.side_effect = lambda s: s

        rate_doc = MagicMock()
        rate_doc.name = "2026-09-07"
        rate_doc.date = "2026-09-07"
        self.rate_doc = rate_doc

    def _bypass_row(self, user):
        row = MagicMock()
        row.user = user
        return row

    def test_non_bypassed_user_gets_no_warnings_without_lookup(self):
        from prakash_steel.utils.sales_order_rate_floor import get_rate_floor_warnings

        self.frappe.session.user = "regular@example.com"
        settings = MagicMock()
        settings.get.return_value = [self._bypass_row("bypassed@example.com")]
        self.frappe.get_cached_doc.return_value = settings

        result = get_rate_floor_warnings({"transaction_date": "2026-09-08", "items": []})
        self.assertEqual(result, {"warnings": []})
        self.frappe.get_doc.assert_not_called()

    @patch(MOD + ".component_rate", return_value=100.0)
    def test_bypassed_user_gets_warnings_for_below_floor_row(self, _cr):
        from prakash_steel.utils.sales_order_rate_floor import get_rate_floor_warnings

        self.frappe.session.user = "bypassed@example.com"
        settings = MagicMock()
        settings.get.return_value = [self._bypass_row("bypassed@example.com")]
        self.frappe.get_cached_doc.return_value = settings

        self.frappe.get_doc.return_value = _doc([_row(1, 0.0)])
        with patch(MOD + ".submitted_rate_doc_asof", return_value=self.rate_doc):
            self.frappe.get_all.return_value = [_meta()]
            result = get_rate_floor_warnings({"doctype": "Sales Order"})

        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("Row 1", result["warnings"][0])

    @patch(MOD + ".component_rate", return_value=100.0)
    def test_bypassed_user_gets_no_warnings_when_rate_is_fine(self, _cr):
        from prakash_steel.utils.sales_order_rate_floor import get_rate_floor_warnings

        self.frappe.session.user = "bypassed@example.com"
        settings = MagicMock()
        settings.get.return_value = [self._bypass_row("bypassed@example.com")]
        self.frappe.get_cached_doc.return_value = settings

        self.frappe.get_doc.return_value = _doc([_row(1, 100.0)])
        with patch(MOD + ".submitted_rate_doc_asof", return_value=self.rate_doc):
            self.frappe.get_all.return_value = [_meta()]
            result = get_rate_floor_warnings({"doctype": "Sales Order"})

        self.assertEqual(result, {"warnings": []})

    def test_parses_json_string_payload(self):
        from prakash_steel.utils.sales_order_rate_floor import get_rate_floor_warnings

        self.frappe.session.user = "bypassed@example.com"
        settings = MagicMock()
        settings.get.return_value = [self._bypass_row("bypassed@example.com")]
        self.frappe.get_cached_doc.return_value = settings
        self.frappe.parse_json.side_effect = lambda s: _doc([])
        self.frappe.get_doc.side_effect = lambda d: d

        result = get_rate_floor_warnings('{"doctype": "Sales Order"}')
        self.assertEqual(result, {"warnings": []})
        self.frappe.parse_json.assert_called_once_with('{"doctype": "Sales Order"}')


class TestComponentRate(unittest.TestCase):
    def test_ms_round_uses_ms_round_basic_rate(self):
        from prakash_steel.prakash_steel.page.basic_rate.basic_rate import component_rate

        rate_doc = {"ms_round_basic_rate": 60.5, "c4_round_rate": 63.5}
        # "20mm, 22mm, 56mm to 65mm" carries a +1 offset on the round table
        self.assertEqual(
            component_rate(rate_doc, "MS", "Round", "20mm, 22mm, 56mm to 65mm"), 61.5
        )
        self.assertEqual(
            component_rate(rate_doc, "C4", "Round", "20mm, 22mm, 56mm to 65mm"), 64.5
        )

    def test_returns_none_for_unknown_grade_shape(self):
        from prakash_steel.prakash_steel.page.basic_rate.basic_rate import component_rate

        self.assertIsNone(component_rate({}, "EN8D", "Round", "24mm to 54mm"))

    def test_returns_none_for_unknown_component(self):
        from prakash_steel.prakash_steel.page.basic_rate.basic_rate import component_rate

        self.assertIsNone(component_rate({"ms_round_basic_rate": 60.5}, "MS", "Round", "nope"))


if __name__ == "__main__":
    unittest.main()
