# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from prakash_steel.prakash_steel.doctype.amc.amc import recalculate_amc_services


class AMCServiceVisit(Document):
    def validate(self):
        self.validate_services_remaining()

    def validate_services_remaining(self):
        if not self.amc_no:
            return

        total = frappe.db.get_value("AMC", self.amc_no, "total_services_available") or 0

        availed = frappe.db.count(
            "AMC Service Visit",
            {
                "amc_no": self.amc_no,
                "docstatus": 1,
                "name": ("!=", self.name),
            },
        )

        if availed >= total:
            frappe.throw(
                _(
                    "All {0} service(s) for AMC {1} have already been availed. No services remaining."
                ).format(total, frappe.bold(self.amc_no))
            )

    def on_submit(self):
        recalculate_amc_services(self.amc_no)

    def on_cancel(self):
        recalculate_amc_services(self.amc_no)
