# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class BrightBarProduction(Document):
	def on_submit(self):
		"""Create Stock Entry on submit"""
		try:
			# Validate required fields
			if not self.material:
				frappe.throw(_("Raw Material is required to create Stock Entry"))

			if not self.actual_rm_consumption or self.actual_rm_consumption <= 0:
				frappe.throw(_("Actual RM Consumption must be greater than 0"))

			if not self.rm_source_warehouse:
				frappe.throw(_("RM Source Warehouse is required to create Stock Entry"))

			if not self.finished:
				frappe.throw(_("Finished Good is required to create Stock Entry"))

			if not self.fg_weight or self.fg_weight <= 0:
				frappe.throw(_("FG Weight must be greater than 0"))

			if not self.fg_target_warehouse:
				frappe.throw(_("FG Target Warehouse is required to create Stock Entry"))

			# Get company from source warehouse
			warehouse_doc = frappe.get_doc("Warehouse", self.rm_source_warehouse)
			company = warehouse_doc.company

			# Get item details for Raw Material UOM
			rm_item_doc = frappe.get_doc("Item", self.material)
			rm_stock_uom = rm_item_doc.stock_uom or "Kg"

			# Get item details for Finished Good UOM
			fg_item_doc = frappe.get_doc("Item", self.finished)
			fg_stock_uom = fg_item_doc.stock_uom or "Kg"

			# Get posting_date from production_date field
			posting_date = self.production_date

			# Create Stock Entry with Manufacture type
			items = [
				{
					"item_code": self.material,
					"qty": self.actual_rm_consumption,
					"s_warehouse": self.rm_source_warehouse,
					"t_warehouse": "",
					"stock_uom": rm_stock_uom,
					"uom": rm_stock_uom,
					"conversion_factor": 1.0,
					"is_finished_item": 0,
				},
				{
					"item_code": self.finished,
					"qty": self.fg_weight,
					"s_warehouse": "",
					"t_warehouse": self.fg_target_warehouse,
					"stock_uom": fg_stock_uom,
					"uom": fg_stock_uom,
					"conversion_factor": 1.0,
					"is_finished_item": 1,
				},
			]

			# Add End Cutting item (scrap/by-product) back to RM Source Warehouse, if provided
			if getattr(self, "end_cutting_item", None) and flt(getattr(self, "end_cutting_weight", 0)) > 0:
				items.append(
					{
						"item_code": self.end_cutting_item,
						"qty": flt(self.end_cutting_weight),
						"s_warehouse": "",
						"t_warehouse": self.rm_source_warehouse,
						"stock_uom": rm_stock_uom,
						"uom": rm_stock_uom,
						"conversion_factor": 1.0,
						"is_finished_item": 0,
						"is_scrap_item": 1,
						"is_legacy_scrap_item": 1,
					}
				)

			stock_entry_data = {
				"doctype": "Stock Entry",
				"naming_series": "BU/.####./.FY.",
				"stock_entry_type": "Manufacture",
				"company": company,
				"set_posting_time": 1,  # Enable custom posting date/time
				"posting_date": posting_date,
				"posting_time": self.custom_posting_time or frappe.utils.nowtime(),
				"items": items,
			}

			stock_entry = frappe.get_doc(stock_entry_data)
			# Explicitly set set_posting_time and posting_date to ensure they're not overridden
			stock_entry.set_posting_time = 1
			stock_entry.posting_date = posting_date
			stock_entry.insert()

			# Submit the stock entry
			# Ensure set_posting_time and posting_date are set before submit
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

			# Update custom_stock_entry_id field with the created stock entry ID
			# Set on the current document so it appears immediately after submit
			self.custom_stock_entry_id = stock_entry.name
			# Also persist explicitly in the database
			frappe.db.set_value("Bright Bar Production", self.name, "custom_stock_entry_id", stock_entry.name)
			frappe.db.commit()

			# Push FG weight to linked Production Plan Item row(s)
			self.update_production_plan_qty_from_fg_weight()

			# Update produced_qty in Production Planning FG Table
			self.update_production_planning_produced_qty()

			frappe.msgprint(
				_("Stock Entry {0} created and submitted successfully").format(frappe.bold(stock_entry.name)),
				indicator="green",
				alert=True,
			)

		except Exception as e:
			frappe.log_error(
				f"Error creating Stock Entry from Bright Bar Production {self.name}: {str(e)}",
				"Bright Bar Production Stock Entry Creation Error",
			)
			frappe.throw(_("Error creating Stock Entry: {0}").format(str(e)))

	def update_production_plan_qty_from_fg_weight(self):
		"""
		Update `custom_production_qty` in the linked Production Plan Item row(s)
		(child table `po_items`) for the Production Plan referenced on this
		Bright Bar Production document.

		Logic:
		- Use this document's `production_plan` link field.
		- Find child rows in `po_items` where `item_code == finished_good`.
		- For each matching row, set `custom_production_qty = fg_weight`.

		Note:
		- Production Plan is a submittable doctype; we therefore use
		  `frappe.db.set_value` on the child rows so this works even when
		  the Production Plan is already submitted.
		"""
		if not getattr(self, "production_plan", None):
			return

		if not getattr(self, "finished", None):
			return

		if not getattr(self, "fg_weight", None) or self.fg_weight <= 0:
			return

		try:
			# Fetch all Production Plan Item rows under this Production Plan
			# in the `po_items` child table that match the finished good.
			rows = frappe.get_all(
				"Production Plan Item",
				filters={
					"parent": self.production_plan,
					"parenttype": "Production Plan",
					"parentfield": "po_items",
					"item_code": self.finished,
				},
				fields=["name", "custom_production_qty"],
			)

			if not rows:
				return

			for row in rows:
				# Sum up: existing custom_production_qty + this fg_weight
				existing_qty = flt(row.get("custom_production_qty") or 0)
				new_qty = existing_qty + flt(self.fg_weight)

				frappe.db.set_value(
					"Production Plan Item",
					row.name,
					"custom_production_qty",
					new_qty,
				)

			# Commit so that the value is persisted even if Production Plan is submitted
			frappe.db.commit()

		except Exception as e:
			frappe.log_error(
				f"Error updating Production Plan Item custom_production_qty from Bright Bar Production {self.name}: {str(e)}",
				"Bright Bar Production → Production Plan Qty Sync Error",
			)

	def update_production_planning_produced_qty(self):
		"""Sum all submitted Bright Bar Production docs for this production_planning + finished
		and write the total into produced_qty on the matching FG Table row."""
		if not getattr(self, "production_planning", None):
			return
		if not getattr(self, "finished", None):
			return

		total = frappe.db.sql(
			"""SELECT COALESCE(SUM(fg_weight), 0)
			   FROM `tabBright Bar Production`
			   WHERE production_planning = %s AND finished = %s AND docstatus = 1""",
			(self.production_planning, self.finished),
		)[0][0] or 0

		rows = frappe.get_all(
			"Production Planning FG Table",
			filters={"parent": self.production_planning, "fg_item": self.finished},
			fields=["name"],
		)
		for row in rows:
			frappe.db.set_value("Production Planning FG Table", row.name, "produced_qty", total)

		frappe.db.commit()

	def before_cancel(self):
		"""Prevent cancellation if linked Stock Entry is not cancelled.

		Note: When cancelling from the linked Stock Entry using
		\"Cancel All Documents\", allow this document to be cancelled so
		ERPNext's standard flow works without deadlock.
		"""

		# Skip validation when called via "Cancel All Documents" from Stock Entry
		cmd = None
		if hasattr(frappe.local, "form_dict"):
			cmd = frappe.local.form_dict.get("cmd")
		if cmd == "frappe.desk.form.linked_with.cancel_all_linked_docs":
			return

		stock_entry_id = getattr(self, "custom_stock_entry_id", None)

		# If no linked stock entry, allow normal cancel
		if not stock_entry_id:
			return

		# Get docstatus of linked Stock Entry (0 = Draft, 1 = Submitted, 2 = Cancelled)
		docstatus = frappe.db.get_value("Stock Entry", stock_entry_id, "docstatus")

		# If Stock Entry exists and is not cancelled, block cancellation of this document
		if docstatus in (0, 1):
			frappe.throw(
				_(
					"Please cancel the linked Stock Entry {0} before cancelling this Bright Bar Production document."
				).format(frappe.bold(stock_entry_id))
			)

	def on_cancel(self):
		"""Clear linked Stock Entry ID on cancel so amended docs don't copy old reference."""
		if getattr(self, "custom_stock_entry_id", None):
			# Clear in memory and in the database
			self.custom_stock_entry_id = ""
			frappe.db.set_value(self.doctype, self.name, "custom_stock_entry_id", "")
