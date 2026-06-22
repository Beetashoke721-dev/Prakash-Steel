# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Shared test utilities — no production imports, no DB required."""


class _Row(dict):
	"""Dict with attribute access — mimics frappe._dict for SQL result rows.

	Use this in tests that pass rows through ``assign_hbt_labels``, which
	writes via item access (``row["hbt"]``) and reads via ``row.get(key)``.
	"""

	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(key)

	def __setattr__(self, key, val):
		self[key] = val
