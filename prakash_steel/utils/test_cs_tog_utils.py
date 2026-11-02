import unittest
from unittest.mock import MagicMock, call, patch

from prakash_steel.utils import cs_tog_utils as MOD


class _Row(dict):
	__getattr__ = dict.get


class TestCsTogPerWarehouse(unittest.TestCase):
	def _patch(self, get_all_return):
		fake = MagicMock()
		fake.get_all.return_value = get_all_return
		return fake, patch.object(MOD, "frappe", fake)

	def test_tog_row_map_scoped_to_warehouse_first_row_wins(self):
		rows = [
			_Row(name="r1", parent="A", top_of_green=10, last_saved_tog=0),
			_Row(name="r2", parent="A", top_of_green=99, last_saved_tog=0),
			_Row(name="r3", parent="B", top_of_green=5, last_saved_tog=7),
		]
		fake, p = self._patch(rows)
		with p:
			result = MOD.get_tog_row_map(["A", "B"], MOD.ROLLED_WAREHOUSE)
		self.assertEqual(result["A"]["name"], "r1")
		self.assertEqual(result["B"]["last_saved_tog"], 7)
		filters = fake.get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["warehouse"], MOD.ROLLED_WAREHOUSE)
		self.assertEqual(filters["parentfield"], "custom_cs_tog_table")

	def test_update_buffer_writes_only_this_warehouse_row(self):
		fake, p = self._patch(["row-bright"])
		with p, patch.object(MOD, "set_updated_fos", return_value=30):
			MOD.update_tog(
				MOD.BRIGHT_WAREHOUSE,
				[{"item_code": "A", "tog": 30, "buffer_flag": "Buffer", "sku_type": "CSMTA"}],
				fos=30,
			)
		self.assertEqual(fake.get_all.call_args.kwargs["filters"]["warehouse"], MOD.BRIGHT_WAREHOUSE)
		fake.db.set_value.assert_has_calls([
			call("Item", "A", {"custom_buffer_flag": "Buffer", "custom_sku_type": "CSMTA"}),
			call("CS Tog table", "row-bright", {
				"top_of_green": 30, "top_of_yellow": 20, "top_of_red": 10, "last_saved_tog": 30,
			}),
		])
		# Item-level safety_stock / last saved TOG are no longer touched
		for c in fake.db.set_value.call_args_list:
			if c.args[0] == "Item":
				self.assertNotIn("safety_stock", c.args[2])
				self.assertNotIn("custom_last_saved_tog", c.args[2])

	def test_update_non_buffer_zeroes_warehouse_row(self):
		fake, p = self._patch(["row-rolled"])
		with p:
			MOD.update_tog(
				MOD.ROLLED_WAREHOUSE,
				[{"item_code": "A", "tog": 50, "buffer_flag": "Non-Buffer", "sku_type": "CSMTO"}],
			)
		fake.db.set_value.assert_any_call("CS Tog table", "row-rolled", {
			"top_of_green": 0, "top_of_yellow": 0, "top_of_red": 0, "last_saved_tog": 0,
		})

	def test_save_tog_writes_last_saved_on_warehouse_row(self):
		fake, p = self._patch(["r1"])
		with p:
			result = MOD.save_tog(MOD.ROLLED_WAREHOUSE, '[{"item_code": "A", "tog": 12}]')
		fake.db.set_value.assert_called_once_with("CS Tog table", "r1", {"last_saved_tog": 12})
		self.assertEqual(result["saved"], 1)


if __name__ == "__main__":
	unittest.main()
