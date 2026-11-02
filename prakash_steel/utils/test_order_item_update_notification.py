# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for utils/order_item_update_notification.py — no DB required."""

import json
import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.utils.order_item_update_notification"


def _row(name, item_code, qty, rate):
    row = MagicMock()
    row.name = name
    row.item_code = item_code
    row.qty = qty
    row.rate = rate
    return row


class TestBuildChangedRows(unittest.TestCase):

    def test_no_changes_returns_empty(self):
        from prakash_steel.utils.order_item_update_notification import build_changed_rows

        before = {"ROW-1": _row("ROW-1", "ITEM-1", 5, 100)}
        trans_items = [{"docname": "ROW-1", "item_code": "ITEM-1", "qty": 5, "rate": 100}]

        self.assertEqual(build_changed_rows(trans_items, before), [])

    def test_qty_only_change_sets_updated_rate_to_zero(self):
        from prakash_steel.utils.order_item_update_notification import build_changed_rows

        before = {"ROW-1": _row("ROW-1", "ITEM-1", 5, 100)}
        trans_items = [{"docname": "ROW-1", "item_code": "ITEM-1", "qty": 8, "rate": 100}]

        rows = build_changed_rows(trans_items, before)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["type"], "updated")
        self.assertEqual(row["qty"], 5)
        self.assertEqual(row["updated_qty"], 8)
        self.assertEqual(row["rate"], 100)
        self.assertEqual(row["updated_rate"], 0)

    def test_rate_only_change_sets_updated_qty_to_zero(self):
        from prakash_steel.utils.order_item_update_notification import build_changed_rows

        before = {"ROW-1": _row("ROW-1", "ITEM-1", 5, 100)}
        trans_items = [{"docname": "ROW-1", "item_code": "ITEM-1", "qty": 5, "rate": 120}]

        rows = build_changed_rows(trans_items, before)
        row = rows[0]
        self.assertEqual(row["updated_qty"], 0)
        self.assertEqual(row["updated_rate"], 120)

    def test_new_row_is_added_type(self):
        from prakash_steel.utils.order_item_update_notification import build_changed_rows

        before = {}
        trans_items = [{"docname": None, "item_code": "ITEM-NEW", "qty": 3, "rate": 40}]

        rows = build_changed_rows(trans_items, before)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "added")
        self.assertEqual(rows[0]["item_code"], "ITEM-NEW")

    def test_removed_row_is_deleted_type(self):
        from prakash_steel.utils.order_item_update_notification import build_changed_rows

        before = {"ROW-1": _row("ROW-1", "ITEM-1", 5, 100)}
        trans_items = []  # row dropped entirely

        rows = build_changed_rows(trans_items, before)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "deleted")
        self.assertEqual(rows[0]["item_code"], "ITEM-1")

    def test_item_code_swap_on_existing_row_is_delete_plus_add(self):
        from prakash_steel.utils.order_item_update_notification import build_changed_rows

        before = {"ROW-1": _row("ROW-1", "ITEM-OLD", 5, 100)}
        trans_items = [{"docname": "ROW-1", "item_code": "ITEM-NEW", "qty": 5, "rate": 100}]

        rows = build_changed_rows(trans_items, before)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["type"], "deleted")
        self.assertEqual(rows[0]["item_code"], "ITEM-OLD")
        self.assertEqual(rows[1]["type"], "added")
        self.assertEqual(rows[1]["item_code"], "ITEM-NEW")

    def test_rows_without_item_code_are_ignored(self):
        from prakash_steel.utils.order_item_update_notification import build_changed_rows

        before = {}
        trans_items = [{"docname": None, "qty": 1, "rate": 1}]

        self.assertEqual(build_changed_rows(trans_items, before), [])


class TestSendItemUpdateNotification(unittest.TestCase):

    @patch(MOD + ".fmt_money", side_effect=lambda amount, precision=None, **kw: str(amount))
    @patch(MOD + ".get_url", return_value="https://example.com")
    @patch(MOD + ".get_fullname", return_value="Pratikshya Gochhayat")
    @patch(MOD + ".frappe")
    def test_sends_mail_with_full_name_and_no_legend_for_plain_update(
        self, mock_frappe, mock_get_fullname, mock_get_url, mock_fmt_money
    ):
        from prakash_steel.utils.order_item_update_notification import send_item_update_notification

        mock_frappe.session.user = "pspp@gmail.com"
        mock_frappe.db.get_value.return_value = "Acme Corp"
        before_items = {"ROW-1": _row("ROW-1", "ITEM-1", 5, 100)}
        trans_items = json.dumps([{"docname": "ROW-1", "item_code": "ITEM-1", "qty": 8, "rate": 100}])

        send_item_update_notification("Sales Order", "SO-0001", trans_items, before_items)

        mock_frappe.sendmail.assert_called_once()
        mock_frappe.db.get_value.assert_called_once_with("Sales Order", "SO-0001", "customer_name")
        _, kwargs = mock_frappe.sendmail.call_args
        self.assertEqual(kwargs["subject"], "Sales Order Updated - SO-0001")
        self.assertIn("Pratikshya Gochhayat", kwargs["message"])
        self.assertNotIn("pspp@gmail.com", kwargs["message"])
        self.assertNotIn("is deleted", kwargs["message"])
        self.assertIn("ITEM-1", kwargs["message"])
        self.assertIn("Customer:", kwargs["message"])
        self.assertIn("Acme Corp", kwargs["message"])

    @patch(MOD + ".fmt_money", side_effect=lambda amount, precision=None, **kw: str(amount))
    @patch(MOD + ".get_url", return_value="https://example.com")
    @patch(MOD + ".get_fullname", return_value="Buyer Name")
    @patch(MOD + ".frappe")
    def test_shows_legend_when_row_added_or_deleted(
        self, mock_frappe, mock_get_fullname, mock_get_url, mock_fmt_money
    ):
        from prakash_steel.utils.order_item_update_notification import send_item_update_notification

        mock_frappe.session.user = "buyer@example.com"
        mock_frappe.db.get_value.return_value = "Steel Supplies Pvt Ltd"
        before_items = {"ROW-1": _row("ROW-1", "ITEM-1", 5, 100)}
        trans_items = json.dumps([{"docname": None, "item_code": "ITEM-2", "qty": 3, "rate": 40}])

        send_item_update_notification("Purchase Order", "PO-0001", trans_items, before_items)

        mock_frappe.db.get_value.assert_called_once_with("Purchase Order", "PO-0001", "supplier_name")
        _, kwargs = mock_frappe.sendmail.call_args
        self.assertIn("is deleted", kwargs["message"])
        self.assertIn("is added", kwargs["message"])
        self.assertIn("Supplier:", kwargs["message"])
        self.assertIn("Steel Supplies Pvt Ltd", kwargs["message"])

    @patch(MOD + ".frappe")
    def test_skips_sending_when_nothing_changed(self, mock_frappe):
        from prakash_steel.utils.order_item_update_notification import send_item_update_notification

        before_items = {"ROW-1": _row("ROW-1", "ITEM-1", 5, 100)}
        trans_items = json.dumps([{"docname": "ROW-1", "item_code": "ITEM-1", "qty": 5, "rate": 100}])

        send_item_update_notification("Purchase Order", "PO-0002", trans_items, before_items)

        mock_frappe.sendmail.assert_not_called()

    @patch(MOD + ".fmt_money", side_effect=lambda amount, precision=None, **kw: str(amount))
    @patch(MOD + ".get_url", return_value="https://example.com")
    @patch(MOD + ".get_fullname", return_value="Buyer Name")
    @patch(MOD + ".frappe")
    def test_logs_error_instead_of_raising_when_sendmail_fails(
        self, mock_frappe, mock_get_fullname, mock_get_url, mock_fmt_money
    ):
        from prakash_steel.utils.order_item_update_notification import send_item_update_notification

        mock_frappe.session.user = "buyer@example.com"
        mock_frappe.sendmail.side_effect = Exception("smtp down")
        before_items = {"ROW-1": _row("ROW-1", "ITEM-1", 5, 100)}
        trans_items = json.dumps([{"docname": "ROW-1", "item_code": "ITEM-1", "qty": 9, "rate": 100}])

        send_item_update_notification("Purchase Order", "PO-0003", trans_items, before_items)

        mock_frappe.log_error.assert_called_once()


class TestUpdateChildQtyRateWrapper(unittest.TestCase):

    @patch(MOD + ".send_item_update_notification")
    @patch(MOD + ".get_items_before_update", return_value={"snapshot": True})
    def test_calls_original_then_notifies_for_sales_order(self, mock_snapshot, mock_notify):
        from prakash_steel.utils import order_item_update_notification as module

        mock_original = MagicMock()
        with patch(
            "erpnext.controllers.accounts_controller.update_child_qty_rate",
            mock_original,
            create=True,
        ):
            module.update_child_qty_rate("Sales Order", "[]", "SO-0001", "items")

        mock_original.assert_called_once_with("Sales Order", "[]", "SO-0001", "items")
        mock_notify.assert_called_once_with("Sales Order", "SO-0001", "[]", {"snapshot": True})

    @patch(MOD + ".send_item_update_notification")
    @patch(MOD + ".get_items_before_update")
    def test_does_not_notify_for_other_doctypes(self, mock_snapshot, mock_notify):
        from prakash_steel.utils import order_item_update_notification as module

        mock_original = MagicMock()
        with patch(
            "erpnext.controllers.accounts_controller.update_child_qty_rate",
            mock_original,
            create=True,
        ):
            module.update_child_qty_rate("Quotation", "[]", "QTN-0001", "items")

        mock_notify.assert_not_called()
        mock_snapshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
