import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime
from datetime import datetime


class FinishWeight(Document):
	def validate(self) -> None:
		"""Finish weight comes from linked Billet Cutting:
		finish_weight = billet_weight + miss_billet_weight
		"""
		bc = getattr(self, "billet_cutting_id", None)
		if not bc:
			return

		billet_weight, miss_billet_weight = frappe.db.get_value(
			"Billet Cutting", bc, ["billet_weight", "miss_billet_weight"]
		) or (0, 0)

		# billet_weight = billet_weight + miss_billet_weight from linked Billet Cutting
		self.billet_weight = flt(billet_weight) + flt(miss_billet_weight)

	def before_submit(self) -> None:
		"""Linked Billet Cutting must be submitted before Finish Weight can be submitted."""
		bc = getattr(self, "billet_cutting_id", None)
		if not bc:
			return
		docstatus = frappe.db.get_value("Billet Cutting", bc, "docstatus")
		if docstatus != 1:
			frappe.throw(
				_(
					"Cannot submit: Billet Cutting {0} is not submitted. Submit the Billet Cutting document first."
				).format(frappe.bold(bc)),
				title=_("Validation Error"),
			)

	def on_submit(self) -> None:

		try:
			if not self.item_code:
				frappe.throw(_("Item Code is required to create Stock Entry"))
			if not self.finish_weight or self.finish_weight <= 0:
				frappe.throw(_("Finish Weight must be greater than 0"))
			if not self.fg_target_warehouse:
				frappe.throw(_("FG Target Warehouse is required to create Stock Entry"))

			warehouse_doc = frappe.get_doc("Warehouse", self.fg_target_warehouse)
			company = warehouse_doc.company
			item_doc = frappe.get_doc("Item", self.item_code)
			stock_uom = item_doc.stock_uom or "Nos"

			posting_date = self.posting_date or frappe.utils.today()
			if self.production_plan:
				pp_doc = frappe.get_doc("Production Plan", self.production_plan)
				posting_date = pp_doc.posting_date or posting_date

			items = [
				{
					"item_code": self.item_code,
					"qty": self.finish_weight,
					"t_warehouse": self.fg_target_warehouse,
					"stock_uom": stock_uom,
					"uom": stock_uom,
					"conversion_factor": 1.0,
				}
			]

			if getattr(self, "melting_item", None) and getattr(self, "miss_roll_item", None):
				if self.melting_item != self.miss_roll_item:
					frappe.throw(
						_("Melting Item ({0}) must equal Miss Roll Item ({1})").format(
							self.melting_item, self.miss_roll_item
						)
					)
				total_miss_roll_weight = flt(getattr(self, "total_miss_roll_weight", 0))
				melting_qty = total_miss_roll_weight + flt(getattr(self, "melting_weight", 0))
				if melting_qty > 0:
					m_doc = frappe.get_doc("Item", self.melting_item)
					items.append(
						{
							"item_code": self.melting_item,
							"qty": melting_qty,
							"t_warehouse": self.fg_target_warehouse,
							"stock_uom": m_doc.stock_uom or "Kg",
							"uom": m_doc.stock_uom or "Kg",
							"conversion_factor": 1.0,
						}
					)

			if getattr(self, "miss_billet_item", None):
				total_miss_ingot = flt(getattr(self, "total_miss_ingot_weight", 0))
				if total_miss_ingot > 0:
					mb_doc = frappe.get_doc("Item", self.miss_billet_item)
					items.append(
						{
							"item_code": self.miss_billet_item,
							"qty": total_miss_ingot,
							"t_warehouse": self.fg_target_warehouse,
							"stock_uom": mb_doc.stock_uom or "Kg",
							"uom": mb_doc.stock_uom or "Kg",
							"conversion_factor": 1.0,
						}
					)

			stock_entry = frappe.get_doc(
				{
					"doctype": "Stock Entry",
					"naming_series": "RM/.####./.FY.",
					"stock_entry_type": "Material Receipt",
					"company": company,
					"set_posting_time": 1,
					"posting_date": posting_date,
					"posting_time": frappe.utils.nowtime(),
					"items": items,
				}
			)
			stock_entry.set_posting_time = 1
			stock_entry.posting_date = posting_date
			stock_entry.insert()
			stock_entry.set_posting_time = 1
			stock_entry.posting_date = posting_date
			stock_entry.submit()

			if stock_entry.posting_date != posting_date:
				frappe.db.sql(
					"UPDATE `tabStock Entry` SET posting_date=%s WHERE name=%s",
					(posting_date, stock_entry.name),
				)
				frappe.db.commit()

			self.custom_stock_entry_id = stock_entry.name
			frappe.db.set_value("Finish Weight", self.name, "custom_stock_entry_id", stock_entry.name)
			frappe.db.commit()

			# Push finish_weight to linked Production Plan Item row(s)
			self.update_production_plan_qty_from_finish_weight()

			# Update produced_qty in Production Planning FG Table
			self.update_production_planning_produced_qty()

			frappe.msgprint(
				_("Stock Entry {0} created and submitted successfully").format(frappe.bold(stock_entry.name)),
				indicator="green",
				alert=True,
			)

		except Exception as e:
			frappe.log_error(
				f"Stock Entry creation failed for Finish Weight {self.name}: {e}",
				"Finish Weight Stock Entry Error",
			)
			frappe.throw(_("Error creating Stock Entry: {0}").format(str(e)))

		try:
			if getattr(self, "cooling_pit", None) == "Transferred":
				now = now_datetime()
				p_date = str(self.posting_date)
				time_part = now.strftime("%H:%M:%S")
				mat_in = datetime.strptime(f"{p_date} {time_part}", "%Y-%m-%d %H:%M:%S")

				cp = frappe.new_doc("Cooling PIT")
				cp.item_code = self.item_code
				cp.finish_weight = self.name
				cp.material_in_time = mat_in

				cp.insert(ignore_permissions=True)
				frappe.db.commit()

				frappe.msgprint(
					_("Cooling PIT {0} created.").format(frappe.bold(cp.name)), indicator="blue", alert=True
				)

		except Exception as e:
			frappe.log_error(
				frappe.get_traceback(),
				f"Cooling PIT creation failed for Finish Weight {self.name}: {e}",
			)
			frappe.msgprint(_("Warning:  Error: {0}").format(str(e)), indicator="orange", alert=True)

	def update_production_plan_qty_from_finish_weight(self) -> None:
		"""
		Accumulate `finish_weight` into `custom_production_qty` in the linked
		Production Plan Item row(s) (child table `po_items`) for the Production
		Plan referenced on this Finish Weight document.

		Logic:
		- Use this document's `production_plan` link field.
		- Find child rows in `po_items` where `item_code == item_code`.
		- For each matching row, set:
		  custom_production_qty = existing custom_production_qty + finish_weight

		Note:
		- Production Plan is a submittable doctype; we therefore use
		  `frappe.db.set_value` on the child rows so this works even when
		  the Production Plan is already submitted.
		"""
		if not getattr(self, "production_plan", None):
			return

		if not getattr(self, "item_code", None):
			return

		if not getattr(self, "finish_weight", None) or self.finish_weight <= 0:
			return

		try:
			rows = frappe.get_all(
				"Production Plan Item",
				filters={
					"parent": self.production_plan,
					"parenttype": "Production Plan",
					"parentfield": "po_items",
					"item_code": self.item_code,
				},
				fields=["name", "custom_production_qty"],
			)

			if not rows:
				return

			for row in rows:
				existing_qty = flt(row.get("custom_production_qty") or 0)
				new_qty = existing_qty + flt(self.finish_weight)

				frappe.db.set_value(
					"Production Plan Item",
					row.name,
					"custom_production_qty",
					new_qty,
				)

			frappe.db.commit()

		except Exception as e:
			frappe.log_error(
				f"Error updating Production Plan Item custom_production_qty from Finish Weight {self.name}: {str(e)}",
				"Finish Weight → Production Plan Qty Sync Error",
			)

	def update_production_planning_produced_qty(self) -> None:
		"""Sum all submitted Finish Weight docs for this production_planning + item_code
		and write the total into produced_qty on the matching FG Table row."""
		if not getattr(self, "production_planning", None):
			return
		if not getattr(self, "item_code", None):
			return

		total = frappe.db.sql(
			"""SELECT COALESCE(SUM(finish_weight), 0)
			   FROM `tabFinish Weight`
			   WHERE production_planning = %s AND item_code = %s AND docstatus = 1""",
			(self.production_planning, self.item_code),
			as_dict=False,
		)[0][0] or 0

		frappe.db.set_value(
			"Production Planning FG Table",
			{"parent": self.production_planning, "fg_item": self.item_code},
			"produced_qty",
			total,
			update_modified=False,
		)
		frappe.db.commit()

	def before_cancel(self) -> None:
		"""Block cancel if linked Stock Entry is still active."""
		cmd = getattr(frappe.local, "form_dict", {}).get("cmd")
		if cmd == "frappe.desk.form.linked_with.cancel_all_linked_docs":
			return
		se_id = getattr(self, "custom_stock_entry_id", None)
		if not se_id:
			return
		docstatus = frappe.db.get_value("Stock Entry", se_id, "docstatus")
		if docstatus in (0, 1):
			frappe.throw(
				_("Please cancel Stock Entry {0} before cancelling this document.").format(frappe.bold(se_id))
			)

	def on_cancel(self) -> None:

		if getattr(self, "custom_stock_entry_id", None):
			self.custom_stock_entry_id = ""
			frappe.db.set_value(self.doctype, self.name, "custom_stock_entry_id", "")
