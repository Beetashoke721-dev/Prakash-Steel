import frappe
from frappe.utils import today, fmt_money


RECIPIENTS = [
	"avinash@prakashsteel.com",
	"srimanta@prakashsteel.com",
	"psprm@prakashsteel.com",
]


def send_daily_sales_invoice_email():
	posting_date = today()
	posting_date_display = frappe.utils.formatdate(posting_date, "dd-MM-yyyy")

	invoices = frappe.db.sql(
		"""
		SELECT
			si.name,
			si.customer,
			si.grand_total,
			COALESCE(SUM(sii.qty), 0) AS total_qty,
			(SELECT ps.payment_term FROM `tabPayment Schedule` ps WHERE ps.parent = si.name ORDER BY ps.idx LIMIT 1) AS payment_term
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE si.docstatus = 1
		  AND si.posting_date = %s
		GROUP BY si.name, si.customer, si.grand_total
		ORDER BY si.name
		""",
		(posting_date,),
		as_dict=True,
	)

	if not invoices:
		frappe.sendmail(
			recipients=RECIPIENTS,
			subject=f"Sales Invoice Summary – {posting_date}",
			message=f"<p>No submitted Sales Invoices found for <b>{posting_date}</b>.</p>",
		)
		return

	def format_payment_term(term):
		if not term:
			return ""
		if term.startswith("N") and term[1:].isdigit():
			return f"{term[1:]} Days"
		return term

	# Build summary table rows
	rows_html = ""
	for inv in invoices:
		rows_html += f"""
		<tr>
			<td style="padding:6px 12px;border:1px solid #ddd;">{inv.name}</td>
			<td style="padding:6px 12px;border:1px solid #ddd;">{inv.customer}</td>
			<td style="padding:6px 12px;border:1px solid #ddd;text-align:right;">{fmt_money(inv.grand_total, currency="INR")}</td>
			<td style="padding:6px 12px;border:1px solid #ddd;text-align:right;">{int(inv.total_qty)}</td>
			<td style="padding:6px 12px;border:1px solid #ddd;text-align:center;">{format_payment_term(inv.payment_term)}</td>
		</tr>"""

	total_grand = sum(inv.grand_total for inv in invoices)
	total_qty = sum(inv.total_qty for inv in invoices)

	body = f"""
	<p>Dear Team,</p>
	<p>Please find below the summary of all submitted Sales Invoices for <b>{posting_date_display}</b>. PDFs of each invoice are attached.</p>

	<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px;">
		<thead>
			<tr style="background:#f2f2f2;">
				<th style="padding:8px 12px;border:1px solid #ddd;text-align:left;">Sales Invoice</th>
				<th style="padding:8px 12px;border:1px solid #ddd;text-align:left;">Customer</th>
				<th style="padding:8px 12px;border:1px solid #ddd;text-align:right;">Grand Total</th>
				<th style="padding:8px 12px;border:1px solid #ddd;text-align:right;">Total Qty</th>
				<th style="padding:8px 12px;border:1px solid #ddd;text-align:center;">Payment Terms</th>
			</tr>
		</thead>
		<tbody>
			{rows_html}
		</tbody>
		<tfoot>
			<tr style="font-weight:bold;background:#fafafa;">
				<td colspan="2" style="padding:8px 12px;border:1px solid #ddd;">Total ({len(invoices)} invoices)</td>
				<td style="padding:8px 12px;border:1px solid #ddd;text-align:right;">{fmt_money(total_grand, currency="INR")}</td>
				<td style="padding:8px 12px;border:1px solid #ddd;text-align:right;">{int(total_qty)}</td>
				<td style="padding:8px 12px;border:1px solid #ddd;"></td>
			</tr>
		</tfoot>
	</table>

	<br><p>Regards,<br>Prakash Steel ERP</p>
	"""

	# Build print-format attachment references for each invoice (Frappe native format)
	attachments = [
		{
			"print_format": "Custom Sales Invoice",
			"print_format_attachment": 1,
			"doctype": "Sales Invoice",
			"name": inv.name,
			"lang": "en",
			"print_letterhead": "1",
		}
		for inv in invoices
	]

	frappe.sendmail(
		recipients=RECIPIENTS,
		subject=f"Sales Invoice Summary – {posting_date} ({len(invoices)} Invoices)",
		message=body,
		attachments=attachments,
	)
