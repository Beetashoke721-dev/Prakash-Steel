# Copyright (c) 2026, Prakash Steel and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, flt, formatdate, getdate, today
from frappe.utils.data import escape_html

from prakash_steel.api.production_dashboard import (
	get_bright_production_data,
	get_rolled_production_data,
)

RECIPIENTS = [
	"avinash@prakashsteel.com",
]


def send_daily_production_dashboard_email() -> None:
	"""Email the Rolled Bar and Bright Bar production summary for the previous production day.

	Runs daily at 4:00 PM. The factory is closed on Sundays, so:
	  - Sunday: no email is sent.
	  - Monday: covers Saturday's production (Sunday is skipped since there's nothing to report).
	  - Every other day: covers yesterday's production, as usual.
	"""
	# Python's date.weekday(): Monday=0 ... Sunday=6
	weekday = getdate(today()).weekday()
	if weekday == 6:
		return
	target_date = add_days(today(), -2 if weekday == 0 else -1)

	rolled_rows = _aggregate_rolled_rows(target_date)
	bright_rows = _aggregate_bright_rows(target_date)

	date_display = formatdate(target_date, "dd/MM/yyyy")
	subject = f"Production Summary - {date_display}"
	body = _build_email_body(date_display, rolled_rows, bright_rows)

	frappe.sendmail(
		recipients=RECIPIENTS,
		subject=subject,
		message=body,
	)


def _aggregate_rolled_rows(target_date) -> list[dict]:
	"""Group Billet Cutting/Finish Weight/Hourly Production rows by finished item for the given date."""
	data = get_rolled_production_data(from_date=target_date, to_date=target_date)
	groups = {}
	order = []

	for row in data.get("rows", []):
		key = row.get("finished_item") or ""
		if key not in groups:
			groups[key] = {
				"finished_item": key,
				"actual_qty": 0.0,
				"total_hr_consumed": 0.0,
				"total_miss_roll_weight": 0.0,
				"rm_consumption": 0.0,
				"miss_billet_weight": 0.0,
				"total_miss_ingot_weight": 0.0,
				"melting_weight": 0.0,
			}
			order.append(key)
		group = groups[key]
		group["actual_qty"] += flt(row.get("actual_qty"))
		group["total_hr_consumed"] += flt(row.get("total_hr_consumed"))
		group["total_miss_roll_weight"] += flt(row.get("total_miss_roll_weight"))
		group["rm_consumption"] += flt(row.get("rm_consumption"))
		group["miss_billet_weight"] += flt(row.get("miss_billet_weight"))
		group["total_miss_ingot_weight"] += flt(row.get("total_miss_ingot_weight"))
		group["melting_weight"] += flt(row.get("melting_weight"))

	result = []
	for key in order:
		group = groups[key]
		rm_consumption = group["rm_consumption"]
		if rm_consumption > 0:
			# Same aggregate formula the Production Dashboard uses for its Burning Loss % KPI,
			# applied per finished item instead of across the whole dashboard.
			burning_loss = flt(
				(
					(rm_consumption + group["miss_billet_weight"] - group["actual_qty"] - group["total_miss_ingot_weight"])
					/ rm_consumption
				)
				* 100,
				2,
			)
		else:
			burning_loss = 0.0

		result.append(
			{
				"finished_item": group["finished_item"],
				"rm_consumption": flt(rm_consumption),
				"miss_billet_weight": flt(group["miss_billet_weight"]),
				"actual_qty": flt(group["actual_qty"]),
				"total_miss_roll_weight": flt(group["total_miss_roll_weight"]),
				"total_miss_ingot_weight": flt(group["total_miss_ingot_weight"]),
				"melting_weight": flt(group["melting_weight"]),
				"total_hr_consumed": flt(group["total_hr_consumed"], 2),
				"burning_loss": burning_loss,
			}
		)
	return result


def _aggregate_bright_rows(target_date) -> list[dict]:
	"""Group Bright Bar Production rows by machine, RM and finished item for the given date."""
	data = get_bright_production_data(from_date=target_date, to_date=target_date)
	groups = {}
	order = []

	for row in data.get("rows", []):
		key = (row.get("machine_name") or "", row.get("rm") or "", row.get("finished_item") or "")
		if key not in groups:
			groups[key] = {
				"machine_name": key[0],
				"rm": key[1],
				"finished_item": key[2],
				"rm_consumption": 0.0,
				"actual_qty": 0.0,
				"tolerance": row.get("tolerance") or "",
				"wastage_values": [],
			}
			order.append(key)
		group = groups[key]
		group["rm_consumption"] += flt(row.get("rm_consumption"))
		group["actual_qty"] += flt(row.get("actual_qty"))
		if row.get("wastage") is not None:
			group["wastage_values"].append(flt(row.get("wastage")))

	result = []
	for key in order:
		group = groups[key]
		avg_wastage = (
			flt(sum(group["wastage_values"]) / len(group["wastage_values"]), 2)
			if group["wastage_values"]
			else 0.0
		)
		result.append(
			{
				"machine_name": group["machine_name"],
				"rm": group["rm"],
				"rm_consumption": flt(group["rm_consumption"]),
				"finished_item": group["finished_item"],
				"actual_qty": flt(group["actual_qty"]),
				"tolerance": group["tolerance"],
				"avg_wastage": avg_wastage,
			}
		)
	return result


def _build_email_body(date_display, rolled_rows, bright_rows) -> str:
	"""Build the HTML body with the Rolled Bar and Bright Bar production tables."""
	rolled_total_qty = sum(r["actual_qty"] for r in rolled_rows)
	rolled_total_hr = sum(r["total_hr_consumed"] for r in rolled_rows)
	rolled_total_miss = sum(r["total_miss_roll_weight"] for r in rolled_rows)
	rolled_total_rm = sum(r["rm_consumption"] for r in rolled_rows)
	rolled_total_miss_billet = sum(r["miss_billet_weight"] for r in rolled_rows)
	rolled_total_miss_ingot = sum(r["total_miss_ingot_weight"] for r in rolled_rows)
	rolled_total_melting = sum(r["melting_weight"] for r in rolled_rows)

	rolled_rows_html = "".join(
		f"""
		<tr>
			<td style="padding:6px 10px;border:1px solid #999;">{date_display}</td>
			<td style="padding:6px 10px;border:1px solid #999;">{escape_html(r["finished_item"])}</td>
			<td style="padding:6px 10px;border:1px solid #999;text-align:right;">{r["rm_consumption"]:,.0f}</td>
			<td style="padding:6px 10px;border:1px solid #999;text-align:right;">{r["miss_billet_weight"]:,.0f}</td>
			<td style="padding:6px 10px;border:1px solid #999;text-align:right;">{r["actual_qty"]:,.0f}</td>
			<td style="padding:6px 10px;border:1px solid #999;text-align:right;">{r["total_miss_roll_weight"]:,.0f}</td>
			<td style="padding:6px 10px;border:1px solid #999;text-align:right;">{r["total_miss_ingot_weight"]:,.0f}</td>
			<td style="padding:6px 10px;border:1px solid #999;text-align:right;">{r["melting_weight"]:,.0f}</td>
			<td style="padding:6px 10px;border:1px solid #999;text-align:right;">{r["burning_loss"]:.2f}</td>
			<td style="padding:6px 10px;border:1px solid #999;text-align:right;">{r["total_hr_consumed"]:,.0f}</td>
		</tr>
		"""
		for r in rolled_rows
	) or (
		'<tr><td colspan="10" style="padding:8px 10px;border:1px solid #999;text-align:center;">'
		"No rolled bar production recorded.</td></tr>"
	)

	bright_total_qty = sum(r["actual_qty"] for r in bright_rows)
	bright_total_rm = sum(r["rm_consumption"] for r in bright_rows)

	bright_rows_html = "".join(
		f"""
		<tr>
			<td style="padding:6px 10px;border:1px solid #999;">{date_display}</td>
			<td style="padding:6px 10px;border:1px solid #999;">{escape_html(r["machine_name"])}</td>
			<td style="padding:6px 10px;border:1px solid #999;">{escape_html(r["rm"])}</td>
			<td style="padding:6px 10px;border:1px solid #999;text-align:right;">{r["rm_consumption"]:,.0f}</td>
			<td style="padding:6px 10px;border:1px solid #999;">{escape_html(r["finished_item"])}</td>
			<td style="padding:6px 10px;border:1px solid #999;text-align:right;">{r["actual_qty"]:,.0f}</td>
			<td style="padding:6px 10px;border:1px solid #999;">{escape_html(str(r["tolerance"]))}</td>
			<td style="padding:6px 10px;border:1px solid #999;text-align:right;">{r["avg_wastage"]:.2f}</td>
		</tr>
		"""
		for r in bright_rows
	) or (
		'<tr><td colspan="8" style="padding:8px 10px;border:1px solid #999;text-align:center;">'
		"No bright bar production recorded.</td></tr>"
	)

	return f"""
	<div style="font-family:Arial, Helvetica, sans-serif;color:#1f2937;">
		<p>Dear Team,</p>
		<p>Please find below the Production Dashboard summary for <b>{date_display}</b>.</p>

		<h3 style="background-color:#000;color:#fff;padding:8px 10px;margin:16px 0 0 0;">Rolling Mill Production Dashboard</h3>
		<table style="border-collapse:collapse;width:100%;font-size:13px;margin-bottom:24px;">
			<thead>
				<tr style="background-color:#d9ead3;">
					<th style="padding:8px 10px;border:1px solid #999;text-align:left;">Production Date</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:left;">Finished Item</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:right;">Actual RM</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:right;">Miss Billet Consumable</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:right;">Finish Qty</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:right;">Miss Roll Weight</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:right;">Miss Billet Weight</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:right;">Melting Weight</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:right;">Burning Loss %</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:right;">Total Hr Consumed</th>
				</tr>
			</thead>
			<tbody>
				{rolled_rows_html}
			</tbody>
			<tfoot>
				<tr style="font-weight:700;background-color:#d9ead3;">
					<td style="padding:8px 10px;border:1px solid #999;">Total</td>
					<td style="padding:8px 10px;border:1px solid #999;"></td>
					<td style="padding:8px 10px;border:1px solid #999;text-align:right;">{rolled_total_rm:,.0f}</td>
					<td style="padding:8px 10px;border:1px solid #999;text-align:right;">{rolled_total_miss_billet:,.0f}</td>
					<td style="padding:8px 10px;border:1px solid #999;text-align:right;">{rolled_total_qty:,.0f} Kg</td>
					<td style="padding:8px 10px;border:1px solid #999;text-align:right;">{rolled_total_miss:,.0f}</td>
					<td style="padding:8px 10px;border:1px solid #999;text-align:right;">{rolled_total_miss_ingot:,.0f}</td>
					<td style="padding:8px 10px;border:1px solid #999;text-align:right;">{rolled_total_melting:,.0f}</td>
					<td style="padding:8px 10px;border:1px solid #999;"></td>
					<td style="padding:8px 10px;border:1px solid #999;text-align:right;">{rolled_total_hr:,.0f}</td>
				</tr>
			</tfoot>
		</table>

		<h3 style="background-color:#cfe2f3;color:#000;padding:8px 10px;margin:0;">Bright Bar Production Dashboard</h3>
		<table style="border-collapse:collapse;width:100%;font-size:13px;">
			<thead>
				<tr style="background-color:#ead1dc;">
					<th style="padding:8px 10px;border:1px solid #999;text-align:left;">Date</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:left;">Machine Name</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:left;">RM</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:right;">Actual RM Consumption</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:left;">Finished Item</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:right;">Finish Qty</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:left;">Tolerance</th>
					<th style="padding:8px 10px;border:1px solid #999;text-align:right;">Wastage %</th>
				</tr>
			</thead>
			<tbody>
				{bright_rows_html}
			</tbody>
			<tfoot>
				<tr style="font-weight:700;background-color:#ead1dc;">
					<td style="padding:8px 10px;border:1px solid #999;">Total</td>
					<td style="padding:8px 10px;border:1px solid #999;"></td>
					<td style="padding:8px 10px;border:1px solid #999;"></td>
					<td style="padding:8px 10px;border:1px solid #999;text-align:right;">{bright_total_rm:,.0f}</td>
					<td style="padding:8px 10px;border:1px solid #999;"></td>
					<td style="padding:8px 10px;border:1px solid #999;text-align:right;">{bright_total_qty:,.0f} Kg</td>
					<td style="padding:8px 10px;border:1px solid #999;"></td>
					<td style="padding:8px 10px;border:1px solid #999;"></td>
				</tr>
			</tfoot>
		</table>

		<p style="margin-top:16px;">Regards,<br>Prakash Steel ERP</p>
	</div>
	"""
