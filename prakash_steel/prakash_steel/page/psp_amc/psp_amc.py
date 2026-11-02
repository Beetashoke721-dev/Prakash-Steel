# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate

AMC_HEADER_FIELDS = (
	"name",
	"posting_date",
	"item",
	"asset_value",
	"make_model",
	"serial_no",
	"installation_date",
	"location",
	"supplier",
	"amc_provider",
	"amc_type",
	"amc_start_date",
	"amc_end_date",
	"estimated_service_date",
	"amc_charges",
	"contract_period",
	"total_services_available",
	"services_availed",
	"services_remaining",
)


@frappe.whitelist()
def get_amc_list():
	"""Submitted AMCs for the left list, ordered by AMC id."""
	amcs = frappe.get_all(
		"AMC",
		filters={"docstatus": 1},
		fields=[
			"name",
			"item",
			"supplier",
			"total_services_available",
			"services_availed",
			"services_remaining",
			"estimated_service_date",
		],
		order_by="name asc",
	)

	for amc in amcs:
		amc["next_service_date"] = amc.get("estimated_service_date")

	return amcs


@frappe.whitelist()
def get_amc_details(amc):
	"""Header + service history + upcoming schedule for a single AMC."""
	header = frappe.db.get_value(
		"AMC", amc, AMC_HEADER_FIELDS, as_dict=True
	)
	if not header:
		frappe.throw(frappe._("AMC {0} not found").format(amc))

	# Next Service Date is maintained directly on the AMC (manually updated
	# after each service), not derived from any AMC Service Visit schedule.
	header["next_service_date"] = header.get("estimated_service_date")
	header["amc_applicable"] = "Yes"

	history = get_history(amc)
	service_dates = [v["service_date"] for v in history if v["service_date"]]
	header["last_service_date"] = max(service_dates) if service_dates else None

	return {
		"header": header,
		"history": history,
		"report_lines": flatten_report_lines(history),
		"upcoming": get_upcoming(amc),
	}


def flatten_report_lines(history):
	"""One row per part line (exploded), or one row per visit with no part change.

	Parent / AMC-level fields are NOT repeated here — they live in the header.
	Next Service Date is one such parent field (the AMC's own
	``estimated_service_date``) so it is not repeated per line either.
	"""
	lines = []
	for visit in history:
		base = {
			"visit": visit["name"],
			"service_date": visit.get("service_date"),
			"part_change": "Yes" if visit.get("part_change") else "No",
			"overall_equipment_condition": visit.get("overall_equipment_condition"),
		}
		if visit.get("parts"):
			for part in visit["parts"]:
				lines.append(
					{
						**base,
						"part_description": part["part_description"],
						"part_no": part["part_no"],
						"part_cost": part["part_cost"],
						"extra_charges": part["extra_charges"],
						"qty": part["qty"],
					}
				)
		else:
			lines.append(
				{
					**base,
					"part_description": None,
					"part_no": None,
					"part_cost": None,
					"extra_charges": None,
					"qty": None,
				}
			)
	return lines


def get_history(amc):
	"""Submitted service visits, newest first, with their part lines nested."""
	visits = frappe.get_all(
		"AMC Service Visit",
		filters={"amc_no": amc, "docstatus": 1},
		fields=[
			"name",
			"service_date",
			"service_type",
			"service_engineer",
			"overall_equipment_condition",
			"remarks",
			"part_change",
		],
		order_by="service_date desc, creation desc",
	)

	for visit in visits:
		visit["parts"] = (
			frappe.get_all(
				"AMC Service Part",
				filters={"parent": visit["name"], "parenttype": "AMC Service Visit"},
				fields=[
					"part_no",
					"part_description",
					"issue_description",
					"qty",
					"part_cost",
					"extra_charges",
				],
				order_by="idx asc",
			)
			if visit["part_change"]
			else []
		)

	return visits


def get_upcoming(amc):
	"""The next unsubmitted visit, plus the remaining scheduled drafts."""
	drafts = frappe.get_all(
		"AMC Service Visit",
		filters={"amc_no": amc, "docstatus": 0},
		fields=["name", "estimated_service_date", "service_type"],
		order_by="estimated_service_date asc, creation asc",
	)

	amc_end_date = frappe.db.get_value("AMC", amc, "amc_end_date")
	for draft in drafts:
		draft["beyond_contract"] = bool(
			amc_end_date
			and draft["estimated_service_date"]
			and getdate(draft["estimated_service_date"]) > getdate(amc_end_date)
		)

	return {"next": drafts[0] if drafts else None, "later": drafts[1:]}
