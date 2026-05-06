# Copyright (c) 2025, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import re
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from frappe.utils import flt, nowdate, nowtime
from erpnext.stock.stock_ledger import get_previous_sle
from prakash_steel.prakash_steel.api.adu import update_adu_for_sales_invoice
from datetime import datetime


class CustomSalesInvoice(SalesInvoice):
	"""Custom Sales Invoice that automatically creates Material Receipt Stock Entry
	for items with insufficient stock when custom_stock_in_for_weight_variance is checked.
	"""

	def _update_gross_amount_on_items(self) -> None:
		"""Set custom_gross_amount on each child row based on taxable value and GST split.

		Formula:
		  gross = taxable_value + (igst_amount if igst_amount else (cgst_amount + sgst_amount))

		Fallbacks:
		  - taxable_value falls back to net_amount, then amount if not present
		  - GST fields default to 0 if missing
		"""
		if not getattr(self, "items", None):
			return

		for item in self.get("items"):
			# Taxable base
			taxable_value = flt(
				item.get("taxable_value")
				or item.get("net_amount")
				or item.get("amount")
				or 0
			)

			# GST split
			igst_amount = flt(item.get("igst_amount") or 0)
			cgst_amount = flt(item.get("cgst_amount") or 0)
			sgst_amount = flt(item.get("sgst_amount") or 0)

			gst_component = igst_amount if igst_amount else (cgst_amount + sgst_amount)
			item.custom_gross_amount = taxable_value + gst_component

	@staticmethod
	def _extract_sales_order_serial(so_name: str) -> str | None:
		"""
		Extract the serial-like numeric part from Sales Order name while
		skipping year-ranges (e.g. `25-26`).

		Examples:
		- `SO/25-26/01514` -> `01514`
		- `SO/01007/25-26` -> `01007`
		- `SO-0001/2025` -> `0001`

		Implementation approach:
		- remove slash-delimited year-range segments like `/25-26/` (and trailing `/25-26`)
		- return the first remaining numeric token, skipping common 4-digit calendar years
		"""
		if not so_name:
			return None

		so_name = str(so_name).strip()
		if not so_name:
			return None

		# Remove year ranges first, e.g. `25-26` from `SO/25-26/01514`.
		# This ensures we never accidentally pick those tokens as the serial.
		so_name = re.sub(r"(?<=/)\d{2}-\d{2}(?=/|$)", "", so_name)

		# Now pick the first numeric token that is not a common 4-digit calendar year.
		# (We keep leading zeros by returning the matched text as-is.)
		for match in re.finditer(r"\d+", so_name):
			token = match.group(0)
			if len(token) == 4 and 1900 <= int(token) <= 2099:
				continue
			return token

		return None

	def before_insert(self):
		"""On amendment, clear fields that should not carry forward from the original."""
		if getattr(self, "amended_from", None):
			self.custom_stock_entry_id = None
			self.custom_cancel_reason = None

		try:
			super().before_insert()
		except AttributeError:
			pass

	def validate(self):
		"""Run parent validate, recompute gross amounts, then re-clear amendment fields if needed."""
		super().validate()
		self._update_gross_amount_on_items()
		# ERPNext's validate chain may re-copy values from amended_from; clear them again here.
		if self.is_new() and getattr(self, "amended_from", None):
			self.custom_stock_entry_id = None
			self.custom_cancel_reason = None

	def _build_other_references(self) -> str | None:
		"""Build ordered, unique Sales Order serial list from child item rows."""
		references = self._get_ordered_sales_order_references()
		ordered_serials = [ref["serial"] for ref in references]
		return ", ".join(ordered_serials) if ordered_serials else None

	def _get_ordered_sales_order_references(self) -> list[dict]:
		"""Return ordered, unique references used by Other References field."""
		seen_serials = set()
		ordered_references = []

		for item in self.get("items") or []:
			so_name = getattr(item, "sales_order", None) or item.get("sales_order")
			serial = self._extract_sales_order_serial(so_name)
			if so_name and serial and serial not in seen_serials:
				seen_serials.add(serial)
				ordered_references.append({"serial": serial, "sales_order": so_name})

		return ordered_references

	def _build_sales_order_dates(self) -> str | None:
		"""Build ordered, unique SO transaction dates for SOs included in Other References."""
		references = self._get_ordered_sales_order_references()
		ordered_so_names = [ref["sales_order"] for ref in references]

		if not ordered_so_names:
			return None

		so_dates = {
			d.name: str(d.transaction_date)
			for d in frappe.get_all(
				"Sales Order",
				filters={"name": ["in", ordered_so_names]},
				fields=["name", "transaction_date"],
			)
			if d.get("transaction_date")
		}

		seen_dates = set()
		ordered_dates = []
		for so_name in ordered_so_names:
			transaction_date = so_dates.get(so_name)
			if transaction_date and transaction_date not in seen_dates:
				seen_dates.add(transaction_date)
				try:
					formatted_date = datetime.strptime(transaction_date, "%Y-%m-%d").strftime("%d-%m-%Y")
				except ValueError:
					formatted_date = transaction_date
				ordered_dates.append(formatted_date)

		return ", ".join(ordered_dates) if ordered_dates else None

	def on_submit(self):
		"""Run standard submit, set custom references, then update ADU (custom)."""
		super().on_submit()

		other_references = self._build_other_references()
		self.custom_other_references = other_references
		self.db_set("custom_other_references", other_references, update_modified=False)

		sales_order_dates = self._build_sales_order_dates()
		self.custom_sales_order_date = sales_order_dates
		self.db_set("custom_sales_order_date", sales_order_dates, update_modified=False)

		try:
			update_adu_for_sales_invoice(self)
		except Exception:
			frappe.log_error(
				title=_("Error updating ADU for Sales Invoice {0}").format(self.name),
				message=frappe.get_traceback(),
			)

	def before_submit(self):
		"""Run stock-entry (conditional) before submit."""
		custom_field_value = self.get("custom_stock_in_for_weight_variance")

		if custom_field_value and custom_field_value not in [None, "", 0, "0", "No"]:
			if self.update_stock:
				self.create_material_receipt_for_insufficient_stock()

		super().before_submit()

	def before_cancel(self):
		"""Ensure cancel reason is provided before allowing cancellation."""
		if not (self.custom_cancel_reason or "").strip():
			frappe.throw(
				_("Please enter Cancel Reason before cancelling this Sales Invoice."),
				title=_("Cancel Reason Required"),
			)

		# Continue with standard cancellation flow
		super().before_cancel()

	def create_material_receipt_for_insufficient_stock(self):
		"""Create Material Receipt Stock Entry for items with insufficient stock in warehouse."""
		if not self.items:
			return

		items_to_receipt = []
		stock_entry_items = []

		# Check each item for insufficient stock
		for item in self.get("items"):
			if not item.item_code or not item.warehouse:
				continue

			# Skip if item is not a stock item
			if not frappe.get_cached_value("Item", item.item_code, "is_stock_item"):
				continue

			# Get required quantity in stock UOM
			# Use stock_qty if available (already in stock UOM), otherwise convert qty to stock UOM
			if hasattr(item, "stock_qty") and item.stock_qty:
				required_qty = flt(item.stock_qty, item.precision("stock_qty"))
			else:
				# Convert qty to stock UOM using conversion_factor
				conversion_factor = flt(item.conversion_factor) or 1.0
				required_qty = flt(item.qty, item.precision("qty")) * conversion_factor

			if required_qty <= 0:
				continue

			# Get available stock from warehous
			available_qty = self.get_available_stock(item.item_code, item.warehouse)

			# Validation: If any item has 0 quantity in warehouse, throw error and prevent submission
			if available_qty == 0:
				frappe.throw(
					_(
						"Item {0} has 0 quantity in warehouse {1}. Cannot create Material Receipt for items with zero stock. Please add stock manually before submitting."
					).format(frappe.bold(item.item_code), frappe.bold(item.warehouse)),
					title=_("Zero Stock Error"),
				)

			# Check if stock is insufficient
			if available_qty < required_qty:
				shortage_qty = required_qty - available_qty

				# If linked to a Sales Order, check if we can serve the invoice with max 10% extra stock-in
				if getattr(item, "sales_order", None) and getattr(item, "so_detail", None):
					so_item = frappe.db.get_value(
						"Sales Order Item",
						item.so_detail,
						["qty", "stock_qty", "conversion_factor"],
						as_dict=True,
					)

					if so_item:
						# Convert SO qty to stock UOM
						so_cf = flt(so_item.conversion_factor or 1.0) or 1.0
						so_qty = flt(so_item.qty or 0)
						so_stock_qty = flt(so_item.stock_qty or 0) or (so_qty * so_cf)

						if so_stock_qty > 0:
							# Max extra we are allowed to auto stock-in = 10% of SO qty (in stock UOM)
							max_extra_stock_in = so_stock_qty * 0.10

							# Check: After adding max_extra_stock_in, will we have enough to serve the invoice?
							available_after_max_stock_in = available_qty + max_extra_stock_in

							if available_after_max_stock_in < required_qty:
								# Even with max 10% stock-in, we cannot serve this invoice
								# Calculate how much more we would need
								still_short = required_qty - available_after_max_stock_in
								frappe.throw(
									_(
										"Row #{0}: Item {1} - Even after maximum allowed 10% stock-in ({2}), "
										"available stock ({3}) will be insufficient. Required: {4}, "
										"still short by: {5}. Please reduce the invoice quantity "
										"or receive stock manually."
									).format(
										item.idx,
										frappe.bold(item.item_code),
										frappe.bold(max_extra_stock_in),
										frappe.bold(available_after_max_stock_in),
										frappe.bold(required_qty),
										frappe.bold(still_short),
									),
									title=_("Insufficient Stock Even After Max Stock-in"),
								)

							# We can serve it, but only stock-in up to the shortage OR max_extra_stock_in, whichever is smaller
							actual_stock_in_qty = min(shortage_qty, max_extra_stock_in)

							# Only add to receipt list if we need to stock-in something
							if actual_stock_in_qty > 0:
								items_to_receipt.append(
									{
										"item": item,
										"shortage_qty": actual_stock_in_qty,  # Use capped quantity
										"available_qty": available_qty,
										"required_qty": required_qty,
									}
								)
				else:
					# No SO link, use original logic (stock-in full shortage)
					items_to_receipt.append(
						{
							"item": item,
							"shortage_qty": shortage_qty,
							"available_qty": available_qty,
							"required_qty": required_qty,
						}
					)

		# If no items need stock receipt, return
		if not items_to_receipt:
			return

		# Create Material Receipt Stock Entry
		try:
			# Get company from Sales Invoice
			company = self.company

			# Get posting date and time
			posting_date = self.posting_date or nowdate()
			posting_time = self.posting_time or nowtime()

			# Prepare items for Stock Entry
			for receipt_item in items_to_receipt:
				item = receipt_item["item"]
				shortage_qty = receipt_item["shortage_qty"]

				# Get item details
				item_doc = frappe.get_doc("Item", item.item_code)
				stock_uom = item_doc.stock_uom or item.uom or "Nos"

				# Calculate rate in stock UOM if needed
				conversion_factor = flt(item.conversion_factor) or 1.0
				rate_in_stock_uom = (
					flt(item.rate or 0) / conversion_factor if conversion_factor > 0 else flt(item.rate or 0)
				)

				# Add to stock entry items (shortage_qty is already in stock UOM)
				stock_entry_items.append(
					{
						"item_code": item.item_code,
						"item_name": item.item_name,
						"description": item.description,
						"qty": shortage_qty,
						"uom": stock_uom,  # Use stock UOM for Material Receipt
						"stock_uom": stock_uom,
						"conversion_factor": 1.0,  # Already in stock UOM
						"t_warehouse": item.warehouse,  # Target warehouse for Material Receipt
						"basic_rate": rate_in_stock_uom,
						"basic_amount": flt(shortage_qty * rate_in_stock_uom),
						"expense_account": item.expense_account,
						"cost_center": item.cost_center or self.cost_center,
					}
				)

			# Create Stock Entry
			stock_entry = frappe.get_doc(
				{
					"doctype": "Stock Entry",
					"stock_entry_type": "Material Receipt",
					"company": company,
					"set_posting_time": 1,
					"posting_date": posting_date,
					"posting_time": posting_time,
					"items": stock_entry_items,
					"remarks": _(
						"Auto-created Material Receipt for insufficient stock in Sales Invoice {0}"
					).format(self.name),
				}
			)

			# Explicitly set posting time and date
			stock_entry.set_posting_time = 1
			stock_entry.posting_date = posting_date
			stock_entry.posting_time = posting_time

			# Insert the stock entry
			stock_entry.insert(ignore_permissions=True)

			# Submit the stock entry
			stock_entry.set_posting_time = 1
			stock_entry.posting_date = posting_date
			stock_entry.submit()

			# Final check - if posting_date was changed, force set it via SQL
			if stock_entry.posting_date != posting_date:
				frappe.db.sql(
					"UPDATE `tabStock Entry` SET posting_date = %s WHERE name = %s",
					(posting_date, stock_entry.name),
				)
				frappe.db.commit()
				stock_entry.reload()

			# Save Stock Entry ID to custom field
			self.custom_stock_entry_id = stock_entry.name
			# Update the field in database since we're in on_submit
			frappe.db.set_value("Sales Invoice", self.name, "custom_stock_entry_id", stock_entry.name)
			frappe.db.commit()

			# Show success message
			item_list = ", ".join([f"{r['item'].item_code} ({r['shortage_qty']})" for r in items_to_receipt])
			frappe.msgprint(
				_(
					"Material Receipt {0} created and submitted automatically for insufficient stock items: {1}"
				).format(frappe.bold(stock_entry.name), item_list),
				indicator="green",
				alert=True,
			)

		except Exception as e:
			frappe.log_error(
				title=_("Error creating Material Receipt for Sales Invoice {0}").format(self.name),
				message=frappe.get_traceback(),
			)
			frappe.throw(
				_("Error creating Material Receipt for insufficient stock: {0}").format(str(e)),
				title=_("Stock Entry Creation Failed"),
			)

	def get_available_stock(self, item_code, warehouse):
		"""Get available stock quantity for an item in a warehouse.

		Uses Stock Ledger Entry to get accurate stock as of the posting date.
		"""
		try:
			# Use get_previous_sle to get accurate stock as of posting date
			previous_sle = get_previous_sle(
				{
					"item_code": item_code,
					"warehouse": warehouse,
					"posting_date": self.posting_date or nowdate(),
					"posting_time": self.posting_time or nowtime(),
				}
			)

			# Get actual stock quantity
			actual_qty = flt(previous_sle.get("qty_after_transaction") or 0)

			return actual_qty

		except Exception:
			# Fallback to Bin table if SLE method fails
			try:
				bin_data = frappe.db.sql(
					"""
					SELECT actual_qty
					FROM `tabBin`
					WHERE item_code = %s AND warehouse = %s
					LIMIT 1
					""",
					(item_code, warehouse),
					as_dict=True,
				)

				if bin_data:
					return flt(bin_data[0].get("actual_qty") or 0)

			except Exception:
				pass

			return 0
