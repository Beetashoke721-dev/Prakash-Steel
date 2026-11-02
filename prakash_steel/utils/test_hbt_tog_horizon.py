import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from prakash_steel.utils import hbt_utils as MOD


class _Settings(dict):
	def get(self, key, default=None):
		return dict.get(self, key, default)


class TestTogHorizonPerItemType(unittest.TestCase):
	def _patch(self, values):
		fake = MagicMock()
		fake.utils.cint = MOD.cint
		fake.get_single.return_value = _Settings(values)
		fake.throw.side_effect = Exception
		return patch.object(MOD, "frappe", fake)

	def test_range_reads_item_type_fields(self):
		values = {
			"bb_from_date": "2026-04-01", "bb_to_date": "2026-06-30",
			"rb_from_date": "2026-01-01", "rb_to_date": "2026-03-31",
		}
		with self._patch(values):
			self.assertEqual(MOD.get_tog_horizon_range("RB"), (date(2026, 1, 1), date(2026, 3, 31)))
			self.assertEqual(MOD.get_tog_horizon_range("BB"), (date(2026, 4, 1), date(2026, 6, 30)))

	def test_range_missing_for_item_type_throws(self):
		with self._patch({"bb_from_date": "2026-04-01", "bb_to_date": "2026-06-30"}):
			with self.assertRaises(Exception):
				MOD.get_tog_horizon_range("Traded")

	def test_fos_per_item_type_with_fallbacks(self):
		values = {"bo_last_fos": 25, "bo_updated_fos": 40, "rm_last_fos": 20}
		with self._patch(values):
			self.assertEqual(MOD.get_default_fos("BO"), 40)
			self.assertEqual(MOD.get_last_fos("BO"), 25)
			self.assertEqual(MOD.get_default_fos("RM"), 20)
			self.assertEqual(MOD.get_default_fos("Traded"), 30)

	def test_stored_zero_fos_falls_back_to_30(self):
		# Blank Int fields in a Single are saved as 0
		with self._patch({"bb_last_fos": 0, "bb_updated_fos": 0}):
			self.assertEqual(MOD.get_default_fos("BB"), 30)
			self.assertEqual(MOD.get_last_fos("BB"), 30)

	def test_changed_fos_moves_previous_into_last_fos(self):
		with self._patch({"traded_last_fos": 25, "traded_updated_fos": 30}) as fake:
			self.assertEqual(MOD.set_updated_fos("Traded", "40"), 30)
			fake.db.set_single_value.assert_called_once_with(
				"TOG Horizon Setting", {"traded_last_fos": 30, "traded_updated_fos": 40}
			)

	def test_first_change_records_the_30_default_as_last_fos(self):
		with self._patch({"bb_last_fos": 0, "bb_updated_fos": 0}) as fake:
			self.assertEqual(MOD.set_updated_fos("BB", 35), 30)
			fake.db.set_single_value.assert_called_once_with(
				"TOG Horizon Setting", {"bb_last_fos": 30, "bb_updated_fos": 35}
			)

	def test_unchanged_fos_keeps_last_fos(self):
		with self._patch({"rm_last_fos": 25, "rm_updated_fos": 40}) as fake:
			self.assertEqual(MOD.set_updated_fos("RM", 40), 25)
			fake.db.set_single_value.assert_not_called()

	def test_unsupported_item_type_rejected(self):
		with self._patch({}):
			with self.assertRaises(Exception):
				MOD.get_last_fos("FG")


if __name__ == "__main__":
	unittest.main()
