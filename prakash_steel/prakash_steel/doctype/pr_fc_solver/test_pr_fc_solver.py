# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from prakash_steel.prakash_steel.doctype.pr_fc_solver.pr_fc_solver import apply_freight_payable_by


class TestPrFcSolver(FrappeTestCase):
	def test_apply_requires_rows(self):
		solver = frappe.get_single("pr fc solver")
		solver.items = []
		solver.save()

		self.assertRaises(frappe.ValidationError, apply_freight_payable_by)
