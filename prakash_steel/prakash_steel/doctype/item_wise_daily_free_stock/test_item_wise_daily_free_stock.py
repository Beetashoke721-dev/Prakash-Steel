import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from prakash_steel.prakash_steel.doctype.item_wise_daily_free_stock import item_wise_daily_free_stock as MOD


class _Doc:
	def __init__(self):
		self.rows = {}

	def append(self, table_field, row):
		self.rows.setdefault(table_field, []).append(row)

	def insert(self, ignore_permissions=False):
		pass


class TestSaveDailyFreeStock(unittest.TestCase):
	def _patch(self, rows_by_module, exists=False):
		fake = MagicMock()
		fake.db.exists.return_value = exists
		fake.get_module.side_effect = lambda module: SimpleNamespace(
			get_data=rows_by_module[module.rsplit(".", 1)[1]]
		)
		fake.new_doc.return_value = _Doc()
		return patch.object(MOD, "frappe", fake)

	def test_saves_item_code_sku_type_and_free_stock_per_report(self):
		rows = {
			"bright_free_stock": lambda: [{"item_code": "BB-1", "item_name": "x", "sku_type": "BOTA", "free_stock": 5}],
			"rolled_free_stock": lambda: [{"item_code": "RB-1", "sku_type": None, "free_stock": 0}],
			"bo_free_stock": lambda: [],
			"traded_free_stock": lambda: [{"item_code": None, "free_stock": 9}],
		}
		with self._patch(rows) as fake:
			MOD.save_daily_free_stock("2026-10-16")
			doc = fake.new_doc.return_value
			fake.db.commit.assert_called_once()

		self.assertEqual(doc.posting_date, "2026-10-16")
		self.assertEqual(
			doc.rows,
			{
				"bright_free_stock": [{"item_code": "BB-1", "sku_type": "BOTA", "free_stock": 5.0}],
				"rolled_free_stock": [{"item_code": "RB-1", "sku_type": "", "free_stock": 0.0}],
			},
		)

	def test_already_saved_day_is_skipped(self):
		with self._patch({}, exists=True) as fake:
			MOD.save_daily_free_stock("2026-10-16")
			fake.get_module.assert_not_called()
			fake.new_doc.assert_not_called()

	def test_one_report_failing_still_saves_the_others(self):
		def boom():
			raise ValueError("bright plan broke")

		rows = {
			"bright_free_stock": lambda: [{"item_code": "BB-1", "sku_type": "BOTA", "free_stock": 5}],
			"rolled_free_stock": boom,
			"bo_free_stock": lambda: [],
			"traded_free_stock": lambda: [],
		}
		with self._patch(rows) as fake:
			MOD.save_daily_free_stock("2026-10-16")
			fake.log_error.assert_called_once()
			self.assertIn("bright_free_stock", fake.new_doc.return_value.rows)
