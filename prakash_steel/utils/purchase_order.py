# Copyright (c) 2025, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def validate_purchase_order_quantity_on_close(doc, method=None) -> None:
	"""
	Validate Purchase Order items when status is changed to "Closed".
	Send email notification if received_qty is more than 5% less than qty for any item.

	Args:
		doc: Purchase Order document
		method: Method name (for compatibility with doc_events)
	"""
	# Only process if status is "Closed"
	if doc.status != "Closed":
		return

	# Check if status was just changed to "Closed" (to avoid duplicate emails)
	# Use has_value_changed to check if status field was modified in this update
	if not doc.has_value_changed("status"):
		return

	# Get the previous status from doc_before_save if available
	previous_status = None
	if hasattr(doc, "_doc_before_save") and doc._doc_before_save:
		previous_status = doc._doc_before_save.get("status")

	# If status was already "Closed" before this update, don't send email again
	if previous_status == "Closed":
		return

	# Track items that have received_qty less than 95% of qty
	shortfall_items = []

	# Process each item in Purchase Order
	for item in doc.items:
		# Get qty and received_qty
		po_qty = flt(item.qty) if item.qty else 0
		received_qty = flt(item.received_qty) if item.received_qty else 0

		if po_qty <= 0:
			continue

		# Calculate 5% threshold (95% of qty)
		threshold_qty = po_qty * 0.95

		# Check if received_qty is more than 5% less than qty
		# This means received_qty < threshold_qty
		if received_qty < threshold_qty:
			shortfall_qty = po_qty - received_qty
			shortfall_percentage = ((shortfall_qty / po_qty) * 100) if po_qty > 0 else 0
			# Get rate from Purchase Order Item
			rate = flt(item.rate) or 0

			shortfall_items.append(
				{
					"item_code": item.item_code,
					"item_name": item.item_name or item.item_code,
					"po_qty": po_qty,
					"received_qty": received_qty,
					"shortfall_qty": shortfall_qty,
					"shortfall_percentage": shortfall_percentage,
					"rate": rate,
					"uom": item.uom or "",
				}
			)

	# Send email notification if any items have shortfall
	if shortfall_items:
		send_quantity_shortfall_notification(doc, shortfall_items)


def send_quantity_shortfall_notification(doc, shortfall_items) -> None:
	"""
	Send email notification when Purchase Order is closed and items have received_qty
	more than 5% less than qty.

	Args:
		doc: Purchase Order document
		shortfall_items: List of items that have shortfall
	"""
	from frappe.utils import get_url

	# Get recipients
	recipients = get_notification_recipients()

	if not recipients:
		frappe.log_error(
			f"No recipients configured for Purchase Order quantity shortfall notification. Purchase Order: {doc.name}",
			"Purchase Order Notification Error",
		)
		return

	# Prepare email content
	subject = f"Purchase Order Quantity Shortfall - {doc.name}"

	# Build email message
	message = f"""
	<p>Dear Team,</p>
	
	<p>The following Purchase Order has been closed with items that have received quantity more than 5% less than ordered quantity:</p>
	
	<p><strong>Purchase Order:</strong> <a href="{get_url()}/app/purchase-order/{doc.name}">{doc.name}</a></p>
	<p><strong>Transaction Date:</strong> {doc.transaction_date}</p>
	<p><strong>Supplier:</strong> {doc.supplier}</p>
	
	<table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%; margin-top: 10px;">
		<thead>
			<tr style="background-color: #f0f0f0;">
				<th style="text-align: center;">Item Code</th>
				<th style="text-align: center;">Item Name</th>
				<th style="text-align: center;">Rate</th>
				<th style="text-align: center;">Ordered Qty</th>
				<th style="text-align: center;">Received Qty</th>
				<th style="text-align: center;">Shortfall Qty</th>
				<th style="text-align: center;">Shortfall %</th>
				<th style="text-align: center;">UOM</th>
			</tr>
		</thead>
		<tbody>
	"""

	for item in shortfall_items:
		message += f"""
			<tr>
				<td style="text-align: center;">{item["item_code"]}</td>
				<td style="text-align: center;">{item["item_name"]}</td>
				<td style="text-align: center;">{flt(item["rate"], 2)}</td>
				<td style="text-align: center;">{flt(item["po_qty"], 2)}</td>
				<td style="text-align: center;">{flt(item["received_qty"], 2)}</td>
				<td style="text-align: center; color: red; font-weight: bold;">{flt(item["shortfall_qty"], 2)}</td>
				<td style="text-align: center; color: red; font-weight: bold;">{flt(item["shortfall_percentage"], 2)}%</td>
				<td style="text-align: center;">{item["uom"]}</td>
			</tr>
		"""

	message += """
		</tbody>
	</table>
	
	<p>Please review and take necessary action.</p>
	
	<p>Best regards,<br>System Notification</p>
	"""

	# Send email
	try:
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			reference_doctype="Purchase Order",
			reference_name=doc.name,
		)
	except Exception as e:
		frappe.log_error(
			f"Error sending quantity shortfall notification for Purchase Order {doc.name}: {str(e)}",
			"Purchase Order Email Error",
		)


def get_notification_recipients() -> None:
	"""
	Get list of email recipients for quantity shortfall notifications.

	Returns:
		List of email addresses
	"""
	# Hardcoded email recipients for Purchase Order quantity shortfall notifications
	recipients = [
		"beetashoke.chakraborty@clapgrow.com",
		"ritika@clapgrow.com",
	]

	return recipients


@frappe.whitelist()
def make_purchase_receipt(source_name, target_doc=None, args=None) -> object:
	from erpnext.buying.doctype.purchase_order.purchase_order import (
		make_purchase_receipt as _make_purchase_receipt,
	)

	doc = _make_purchase_receipt(source_name, target_doc, args)

	if not (doc and doc.items):
		return doc

	original_count = len(doc.items)

	doc.items = [
		item
		for item in doc.items
		if not (
			item.get("purchase_order_item")
			and frappe.db.get_value("Purchase Order Item", item.purchase_order_item, "custom_closed")
		)
	]

	# Re-index after filtering
	for idx, item in enumerate(doc.items, 1):
		item.idx = idx

	closed_count = original_count - len(doc.items)
	if closed_count:
		frappe.msgprint(
			_("{0} closed item(s) were excluded from the Purchase Receipt.").format(closed_count),
			indicator="orange",
			alert=True,
		)

	return doc
