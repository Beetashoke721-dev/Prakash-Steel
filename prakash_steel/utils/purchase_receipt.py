# Copyright (c) 2025, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def validate_purchase_receipt_quantity(doc, method=None) -> None:
	"""
	Validate Purchase Receipt quantity against Purchase Order quantity.
	Send email notification if total received quantity exceeds 5% of PO quantity.

	Args:
		doc: Purchase Receipt document
		method: Method name (for compatibility with doc_events)
	"""
	# Only process if Purchase Receipt is submitted (docstatus = 1)
	if doc.docstatus != 1:
		return

	# Track items that exceed threshold for email notification
	exceeded_items = []

	# Process each item in Purchase Receipt
	for item in doc.items:
		# Check if item is linked to a Purchase Order
		if not item.purchase_order or not item.purchase_order_item:
			continue

		# Get Purchase Order Item details
		try:
			po_item = frappe.get_doc("Purchase Order Item", item.purchase_order_item)
			po_qty = flt(po_item.qty) if po_item.qty else 0

			if po_qty <= 0:
				continue

			# Calculate total received quantity for this PO Item across all Purchase Receipts
			total_received = get_total_received_qty_for_po_item(item.purchase_order_item, doc.name)

			# Calculate 5% threshold
			threshold_qty = po_qty * 1.05

			# Check if total received exceeds threshold
			if total_received > threshold_qty:
				extra_qty = total_received - po_qty
				# Get rate from Purchase Receipt Item or Purchase Order Item
				rate = flt(item.rate) or flt(po_item.rate) or 0

				exceeded_items.append(
					{
						"purchase_order": item.purchase_order,
						"purchase_order_item": item.purchase_order_item,
						"item_code": item.item_code,
						"po_qty": po_qty,
						"total_received": total_received,
						"extra_qty": extra_qty,
						"rate": rate,
					}
				)

		except frappe.DoesNotExistError:
			# Purchase Order Item not found, skip
			frappe.log_error(
				f"Purchase Order Item {item.purchase_order_item} not found for Purchase Receipt {doc.name}",
				"Purchase Receipt Validation Error",
			)
			continue
		except Exception as e:
			frappe.log_error(
				f"Error validating quantity for item {item.item_code} in Purchase Receipt {doc.name}: {str(e)}",
				"Purchase Receipt Validation Error",
			)
			continue

	# Send email notification if any items exceeded threshold
	if exceeded_items:
		send_quantity_exceeded_notification(doc, exceeded_items)


def get_total_received_qty_for_po_item(purchase_order_item, current_pr_name) -> float:
	"""
	Get total received quantity for a Purchase Order Item across all submitted Purchase Receipts.
	This includes the current Purchase Receipt being submitted.

	Args:
		purchase_order_item: Name of Purchase Order Item
		current_pr_name: Name of current Purchase Receipt (already submitted at this point)

	Returns:
		Total received quantity (float)
	"""
	# Get total received quantity from all submitted Purchase Receipts for this PO Item
	# The current PR is already submitted (docstatus=1) when on_submit hook is called
	total_received = frappe.db.sql(
		"""
		SELECT SUM(pri.qty) as total_qty
		FROM `tabPurchase Receipt Item` pri
		INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
		WHERE pri.purchase_order_item = %s
		AND pr.docstatus = 1
		""",
		(purchase_order_item,),
		as_dict=True,
	)[0]

	return flt(total_received.get("total_qty") or 0)


def send_quantity_exceeded_notification(doc, exceeded_items) -> None:
	"""
	Send email notification when Purchase Receipt quantity exceeds 5% of PO quantity.

	Args:
		doc: Purchase Receipt document
		exceeded_items: List of items that exceeded threshold
	"""
	from frappe.utils import get_url

	# Get recipients - you can configure this via Customize Form or System Settings
	# For now, using a default approach - you may want to make this configurable
	recipients = get_notification_recipients()

	if not recipients:
		frappe.log_error(
			f"No recipients configured for Purchase Receipt quantity exceeded notification. Purchase Receipt: {doc.name}",
			"Purchase Receipt Notification Error",
		)
		return

	# Prepare email content
	subject = f"Purchase Receipt Quantity Exceeded - {doc.name}"

	# Build email message
	message = f"""
	<p>Dear Team,</p>
	
	<p>The following Purchase Receipt has items that exceed the 5% tolerance limit:</p>
	
	<p><strong>Purchase Receipt:</strong> <a href="{get_url()}/app/purchase-receipt/{doc.name}">{doc.name}</a></p>
	<p><strong>Posting Date:</strong> {doc.posting_date}</p>
	<p><strong>Supplier:</strong> {doc.supplier}</p>
	
	<table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%; margin-top: 10px;">
		<thead>
			<tr style="background-color: #f0f0f0;">
				<th style="text-align: center;">Purchase Order</th>
				<th style="text-align: center;">Item Code</th>
				<th style="text-align: center;">Rate</th>
				<th style="text-align: center;">Original Qty (PO)</th>
				<th style="text-align: center;">Total Received Qty</th>
				<th style="text-align: center;">Extra Qty</th>
			</tr>
		</thead>
		<tbody>
	"""

	for item in exceeded_items:
		message += f"""
			<tr>
				<td style="text-align: center;"><a href="{get_url()}/app/purchase-order/{item["purchase_order"]}">{item["purchase_order"]}</a></td>
				<td style="text-align: center;">{item["item_code"]}</td>
				<td style="text-align: center;">{flt(item["rate"], 2)}</td>
				<td style="text-align: center;">{flt(item["po_qty"], 2)}</td>
				<td style="text-align: center;">{flt(item["total_received"], 2)}</td>
				<td style="text-align: center; color: red; font-weight: bold;">{flt(item["extra_qty"], 2)}</td>
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
			reference_doctype="Purchase Receipt",
			reference_name=doc.name,
		)
	except Exception as e:
		frappe.log_error(
			f"Error sending quantity exceeded notification for Purchase Receipt {doc.name}: {str(e)}",
			"Purchase Receipt Email Error",
		)


def get_notification_recipients() -> None:
	"""
	Get list of email recipients for quantity exceeded notifications.

	Returns:
		List of email addresses
	"""
	# Hardcoded email recipients for Purchase Receipt quantity exceeded notifications
	recipients = [
		"avinash@prakashsteel.com",
		"purchase@prakashsteel.com",
	]

	return recipients
