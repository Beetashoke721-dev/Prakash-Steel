import frappe
from frappe import _
from frappe.utils import cint, flt

from prakash_steel.utils.whitelist_permissions import require_all_permissions


def is_automatic_manufacture_stock_entry_enabled() -> bool:
	"""Feature flag controlled by `Stock Entry Setting` single doctype."""
	try:
		return (
			cint(
				frappe.db.get_single_value(
					"Stock Entry Setting",
					"enable_automatic_manufacture_stock_entry",
				)
			)
			== 1
		)
	except Exception:
		# If the setting DocType isn't installed/migrated yet, keep auto logic off.
		return False


@frappe.whitelist()
def get_stock_entry_setting_auto_manufacture_enabled() -> dict:
	"""Used by Work Order JS to decide whether to patch Finish Stock Entry logic."""
	return {"enabled": is_automatic_manufacture_stock_entry_enabled()}


def _require_auto_stock_entry_enabled() -> None:
	if not is_automatic_manufacture_stock_entry_enabled():
		frappe.throw(
			_(
				"Automatic Manufacture Stock Entry is disabled. Enable it in `Stock Entry Setting`."
			)
		)


PRODUCTION_TYPE_FIELDS = (
	("custom_bright_production", "Bright Production"),
	("custom_rolled_production", "Rolled Production"),
	("custom_annealing", "Annealing"),
	("custom_straightning", "Straightning"),
	("custom_cutting", "Cutting"),
)


def _format_production_type_labels(labels, separator: str) -> str:
	bold = [f"<b>{_(label)}</b>" for label in labels]
	if len(bold) == 1:
		return bold[0]
	return "{0} {1} {2}".format(", ".join(bold[:-1]), separator, bold[-1])


def get_selected_production_types(doc) -> list[str]:
	return [label for fieldname, label in PRODUCTION_TYPE_FIELDS if cint(doc.get(fieldname))]


def validate_production_type(doc, method=None):
	"""Exactly one production type checkbox must be selected."""
	selected = get_selected_production_types(doc)

	if not selected:
		frappe.throw(
			_("Please select one production type: {0}.").format(
				_format_production_type_labels(
					[label for _fieldname, label in PRODUCTION_TYPE_FIELDS], _("or")
				)
			),
			title=_("Production Type Required"),
		)

	if len(selected) > 1:
		frappe.throw(
			_("Only one production type can be selected at a time. Currently selected: {0}.").format(
				_format_production_type_labels(selected, _("and"))
			),
			title=_("Production Type Conflict"),
		)


def get_total_consumed_qty(doc):
	return sum(flt(row.consumed_qty) for row in (doc.required_items or []))


def calculate_custom_wastage(doc, method=None):
	"""Set custom_wastage from produced_qty and total consumed raw material (Bright only)."""
	if not bool(doc.custom_bright_production):
		doc.custom_wastage = None
		return

	consumed_qty = get_total_consumed_qty(doc)
	produced_qty = flt(doc.produced_qty)

	if doc.produced_qty in (None, "") or consumed_qty == 0:
		doc.custom_wastage = None
		return

	doc.custom_wastage = flt(
		abs((produced_qty / consumed_qty) * 100 - 100),
		frappe.get_precision("Work Order", "custom_wastage") or 2,
	)


def calculate_cutting_weight_for_rolled_production(doc, method=None):
	"""Set custom_cutting_weight for rolled production work orders."""
	if not bool(doc.custom_rolled_production):
		doc.custom_cutting_weight = None
		return

	total_billet_cutting_pcs = flt(doc.custom_total_billet_cutting_pcs) or 0
	if total_billet_cutting_pcs <= 0:
		doc.custom_cutting_weight = None
		return

	consumed_qty = get_total_consumed_qty(doc)
	doc.custom_cutting_weight = consumed_qty / total_billet_cutting_pcs


def calculate_total_raw_material_pcs(doc, method=None):
	"""Set custom_total_raw_material_pcs for rolled production work orders."""
	if not bool(doc.custom_rolled_production):
		doc.custom_total_raw_material_pcs = None
		return

	doc.custom_total_raw_material_pcs = (
		flt(doc.custom_total_billet_cutting_pcs) + flt(doc.custom_miss_billet_pcs)
	)


def calculate_burning_loss_for_rolled_production(doc, method=None):
	"""Set custom_burning_loss for rolled production work orders."""
	if not bool(doc.custom_rolled_production):
		doc.custom_burning_loss = None
		return

	consumed_qty = get_total_consumed_qty(doc)
	if consumed_qty <= 0:
		doc.custom_burning_loss = None
		return

	miss_billet_weight = flt(doc.custom_miss_billet_weight) or 0
	produced_qty = flt(doc.produced_qty) or 0

	doc.custom_burning_loss = flt(
		abs(((consumed_qty - miss_billet_weight - produced_qty) / consumed_qty) * 100),
		frappe.get_precision("Work Order", "custom_burning_loss") or 2,
	)


def validate_miss_billet_weight(doc, method=None):
	"""Require custom_miss_billet_weight when custom_miss_billet_pcs > 0."""
	miss_billet_pcs = flt(doc.custom_miss_billet_pcs) or 0
	miss_billet_weight = flt(doc.custom_miss_billet_weight) or 0

	if miss_billet_pcs > 0 and miss_billet_weight <= 0:
		frappe.throw(
			_("Miss Billet Weight is mandatory when Miss Billet Pcs is greater than 0."),
			title=_("Validation Error"),
		)


def update_custom_wastage_after_stock_entry(doc, method=None):
	"""Persist calculated Work Order / Job Card fields after stock entries update quantities."""
	if not doc.work_order:
		return

	wo = frappe.get_doc("Work Order", doc.work_order)
	calculate_custom_wastage(wo)
	calculate_cutting_weight_for_rolled_production(wo)
	calculate_burning_loss_for_rolled_production(wo)

	# db.set_value writes SQL NULL for None; skip fields that are not yet calculable.
	update_values = {
		fieldname: value
		for fieldname, value in {
			"custom_wastage": wo.custom_wastage,
			"custom_cutting_weight": wo.custom_cutting_weight,
			"custom_burning_loss": wo.custom_burning_loss,
		}.items()
		if value is not None
	}

	if update_values:
		frappe.db.set_value(
			"Work Order",
			doc.work_order,
			update_values,
			update_modified=False,
		)

	# Consumed qty on Required Items updates with Stock Entry; refresh linked Job Cards.
	update_job_cards_billet_weight(doc.work_order)


def get_work_order_production_types(work_order: str) -> dict | None:
	"""Read every production type checkbox from a Work Order."""
	if not work_order:
		return None

	fieldnames = [fieldname for fieldname, _label in PRODUCTION_TYPE_FIELDS]
	wo = frappe.db.get_value("Work Order", work_order, fieldnames, as_dict=True)

	if not wo:
		return None

	return {fieldname: cint(wo.get(fieldname)) for fieldname in fieldnames}


def copy_production_type_to_job_card(doc, method=None):
	"""Copy production type checkboxes from the parent Work Order to this Job Card."""
	production_types = get_work_order_production_types(doc.work_order)

	if not production_types:
		return

	frappe.db.set_value(
		"Job Card",
		doc.name,
		production_types,
		update_modified=False,
	)


def lock_production_type_from_work_order(doc, method=None):
	"""Keep Job Card production type in sync with the linked Work Order."""
	production_types = get_work_order_production_types(doc.work_order)

	if not production_types:
		return

	for fieldname, value in production_types.items():
		doc.set(fieldname, value)


def _time_log_used_pcs(row) -> float:
	return flt(row.custom_finish_item) + flt(row.custom_miss_roll) + flt(row.custom_miss_ingot_or_billet)


def get_submitted_job_card_used_pcs(work_order: str, exclude_job_card: str | None = None) -> float:
	"""Sum used pcs from submitted Job Card time logs for a Work Order."""
	if not work_order:
		return 0.0

	conditions = ["jc.work_order = %(work_order)s", "jc.docstatus = 1"]
	values = {"work_order": work_order}

	if exclude_job_card:
		conditions.append("jc.name != %(exclude_job_card)s")
		values["exclude_job_card"] = exclude_job_card

	used = frappe.db.sql(
		f"""
		SELECT SUM(
			IFNULL(tl.custom_finish_item, 0)
			+ IFNULL(tl.custom_miss_roll, 0)
			+ IFNULL(tl.custom_miss_ingot_or_billet, 0)
		)
		FROM `tabJob Card Time Log` tl
		INNER JOIN `tabJob Card` jc ON jc.name = tl.parent
		WHERE {" AND ".join(conditions)}
		""",
		values,
	)

	return flt(used[0][0]) if used and used[0][0] is not None else 0.0


@frappe.whitelist()
def get_job_card_billet_cutting_context(work_order: str, exclude_job_card: str | None = None) -> dict:
	"""Return Work Order pool and already-used pcs for Job Card remaining calculation."""
	if not work_order:
		return {"pool": None, "other_used": 0, "is_rolled": 0}

	wo = frappe.db.get_value(
		"Work Order",
		work_order,
		["custom_rolled_production", "custom_total_raw_material_pcs"],
		as_dict=True,
	)
	if not wo or not wo.custom_rolled_production:
		return {"pool": None, "other_used": 0, "is_rolled": 0}

	return {
		"pool": flt(wo.custom_total_raw_material_pcs),
		"other_used": get_submitted_job_card_used_pcs(work_order, exclude_job_card),
		"is_rolled": 1,
	}


def is_last_operation_job_card(doc) -> bool:
	"""True when this Job Card is for the Work Order's last operation (or there are none)."""
	if not doc.work_order:
		return False

	operations = frappe.get_all(
		"Work Order Operation",
		filters={"parent": doc.work_order},
		fields=["name", "sequence_id", "operation"],
		order_by="sequence_id asc, idx asc",
	)
	if not operations:
		return True

	last = operations[-1]
	if getattr(doc, "operation_id", None):
		return doc.operation_id == last.get("name")
	if getattr(doc, "sequence_id", None):
		return flt(doc.sequence_id) == flt(last.get("sequence_id"))
	if getattr(doc, "operation", None):
		return doc.operation == last.get("operation")
	return True


def should_create_manufacture_stock_entry_for_job_card(doc) -> bool:
	"""Manufacture FG only after a normal last-operation Job Card is submitted."""
	if cint(getattr(doc, "docstatus", 0)) != 1:
		return False
	if cint(getattr(doc, "is_corrective_job_card", 0)):
		return False
	if not getattr(doc, "work_order", None):
		return False
	if cint(frappe.db.get_value("Work Order", doc.work_order, "track_semi_finished_goods")):
		return False
	return is_last_operation_job_card(doc)


def is_raw_material_stock_entry_row(row) -> bool:
	"""Outgoing consumption row: source warehouse only, not FG / scrap / secondary."""
	if cint(getattr(row, "is_finished_item", 0)):
		return False
	if getattr(row, "type", None):
		return False
	if cint(getattr(row, "is_legacy_scrap_item", 0)) or cint(getattr(row, "is_scrap_item", 0)):
		return False
	return bool(getattr(row, "s_warehouse", None)) and not getattr(row, "t_warehouse", None)


def is_finished_good_stock_entry_row(row) -> bool:
	if getattr(row, "type", None):
		return False
	return cint(getattr(row, "is_finished_item", 0)) == 1


def is_secondary_stock_entry_row(row) -> bool:
	if getattr(row, "type", None):
		return True
	return cint(getattr(row, "is_legacy_scrap_item", 0)) or cint(getattr(row, "is_scrap_item", 0))


def get_job_card_secondary_items(job_card) -> list:
	"""Return Job Card Secondary Items (Qty column is stock_qty)."""
	if not job_card:
		return []

	if not isinstance(job_card, str) and getattr(job_card, "secondary_items", None) is not None:
		rows = []
		for row in job_card.secondary_items or []:
			item_code = getattr(row, "item_code", None)
			qty = flt(getattr(row, "stock_qty", 0))
			if not item_code or qty <= 0:
				continue
			rows.append(
				{
					"type": getattr(row, "type", None),
					"item_code": item_code,
					"item_name": getattr(row, "item_name", None),
					"description": getattr(row, "description", None),
					"stock_qty": qty,
					"stock_uom": getattr(row, "stock_uom", None),
					"bom_secondary_item": getattr(row, "bom_secondary_item", None),
				}
			)
		return rows

	name = job_card if isinstance(job_card, str) else getattr(job_card, "name", None)
	if not name:
		return []

	items = frappe.get_all(
		"Job Card Secondary Item",
		filters={"parent": name, "parenttype": "Job Card"},
		fields=[
			"type",
			"item_code",
			"item_name",
			"description",
			"stock_qty",
			"stock_uom",
			"bom_secondary_item",
		],
		order_by="idx",
	)
	return [item for item in items if item.get("item_code") and flt(item.get("stock_qty")) > 0]


def get_process_loss_qty_from_secondary_items(secondary_items) -> float:
	return sum(flt(row.get("stock_qty")) for row in (secondary_items or []))


def get_job_card_process_loss_qty(job_card, secondary_items=None) -> float:
	"""Resolve process loss for Manufacture Stock Entry from a Job Card.

	Prefer Job Card Secondary Items qty. When those are empty, fall back to
	Job Card.process_loss_qty (ERPNext shortfall vs for_quantity).
	"""
	if secondary_items is None:
		secondary_items = get_job_card_secondary_items(job_card)

	loss = get_process_loss_qty_from_secondary_items(secondary_items)
	if loss:
		return loss

	if isinstance(job_card, str):
		return flt(frappe.db.get_value("Job Card", job_card, "process_loss_qty"))
	if isinstance(job_card, dict):
		return flt(job_card.get("process_loss_qty"))
	return flt(getattr(job_card, "process_loss_qty", 0))


def _secondary_item_warehouses(stock_entry) -> dict:
	fg = getattr(stock_entry, "to_warehouse", None)
	scrap = fg
	work_order = getattr(stock_entry, "work_order", None)
	if work_order and isinstance(work_order, str):
		wo = frappe.db.get_value(
			"Work Order", work_order, ["scrap_warehouse", "fg_warehouse"], as_dict=True
		)
		if wo:
			fg = wo.fg_warehouse or fg
			scrap = wo.scrap_warehouse or fg
	return {
		"Scrap": scrap,
		"Additional Finished Good": fg,
		"Co-Product": fg,
		"By-Product": fg,
		"default": fg,
	}


def apply_job_card_secondary_items(stock_entry, secondary_items) -> None:
	"""Replace Manufacture scrap/secondary rows with Job Card Secondary Items qtys."""
	payloads = []
	warehouses = _secondary_item_warehouses(stock_entry)
	for item in secondary_items or []:
		qty = flt(item.get("stock_qty"))
		item_code = item.get("item_code")
		if not item_code or qty <= 0:
			continue
		item_type = item.get("type")
		payloads.append(
			{
				"item_code": item_code,
				"item_name": item.get("item_name"),
				"description": item.get("description"),
				"qty": qty,
				"transfer_qty": qty,
				"uom": item.get("stock_uom"),
				"stock_uom": item.get("stock_uom"),
				"conversion_factor": 1,
				"type": item_type,
				"s_warehouse": None,
				"t_warehouse": warehouses.get(item_type) or warehouses["default"],
				"is_finished_item": 0,
				"is_scrap_item": 1 if item_type == "Scrap" else 0,
				"bom_secondary_item": item.get("bom_secondary_item"),
			}
		)

	if getattr(stock_entry, "doctype", None) == "Stock Entry":
		kept = [
			row.as_dict()
			for row in (stock_entry.items or [])
			if not is_secondary_stock_entry_row(row)
		]
		stock_entry.set("items", kept + payloads)
		return

	from types import SimpleNamespace

	kept_rows = [
		row for row in (stock_entry.items or []) if not is_secondary_stock_entry_row(row)
	]
	stock_entry.items = kept_rows + [SimpleNamespace(**payload) for payload in payloads]


def set_stock_entry_item_qty(row, qty: float) -> None:
	row.qty = flt(qty)
	conversion = flt(getattr(row, "conversion_factor", None)) or 1
	row.transfer_qty = flt(row.qty) * conversion


def _apply_qty_to_rows(rows, qty: float) -> None:
	if len(rows) == 1:
		set_stock_entry_item_qty(rows[0], qty)
		return

	current_total = sum(flt(row.qty) for row in rows)
	if current_total <= 0:
		set_stock_entry_item_qty(rows[0], qty)
		for row in rows[1:]:
			set_stock_entry_item_qty(row, 0)
		return

	remaining = qty
	for index, row in enumerate(rows):
		if index == len(rows) - 1:
			set_stock_entry_item_qty(row, remaining)
		else:
			share = flt(row.qty) / current_total * qty
			set_stock_entry_item_qty(row, share)
			remaining -= share


def apply_actual_rm_consumption(stock_entry, actual_rm_consumption: float) -> None:
	"""Replace Manufacture Stock Entry raw-material qty with Job Card actual consumption."""
	qty = flt(actual_rm_consumption)
	if qty <= 0:
		frappe.throw(_("Actual RM Consumption must be greater than 0."))

	rm_rows = [row for row in (stock_entry.items or []) if is_raw_material_stock_entry_row(row)]
	if not rm_rows:
		frappe.throw(_("No raw material rows found on the Manufacture Stock Entry."))

	_apply_qty_to_rows(rm_rows, qty)


def apply_finished_good_qty(
	stock_entry, finished_good_qty: float, process_loss_qty: float | None = None
) -> None:
	"""Set Manufacture Stock Entry FG qty from Job Card total_completed_qty.

	`fg_completed_qty` must stay FG qty + process loss so ERPNext
	`validate_fg_completed_qty` accepts the entry.
	"""
	qty = flt(finished_good_qty)
	if qty <= 0:
		frappe.throw(_("Completed Qty must be greater than 0."))

	fg_rows = [row for row in (stock_entry.items or []) if is_finished_good_stock_entry_row(row)]
	if not fg_rows:
		frappe.throw(_("No finished good row found on the Manufacture Stock Entry."))

	_apply_qty_to_rows(fg_rows, qty)
	if process_loss_qty is None:
		loss = flt(getattr(stock_entry, "process_loss_qty", 0))
	else:
		loss = flt(process_loss_qty)
		stock_entry.process_loss_qty = loss
	stock_entry.fg_completed_qty = qty + loss
	if qty + loss:
		stock_entry.process_loss_percentage = (loss / (qty + loss)) * 100
	else:
		stock_entry.process_loss_percentage = 0


def get_job_card_posting_date(job_card) -> str | None:
	"""Return Job Card posting_date from a doc or name."""
	if not job_card:
		return None
	if not isinstance(job_card, str):
		return getattr(job_card, "posting_date", None) or None
	return frappe.db.get_value("Job Card", job_card, "posting_date")


def apply_job_card_posting_date(stock_entry, posting_date) -> None:
	"""Use Job Card posting date on Manufacture Stock Entry (not today's date)."""
	if not posting_date:
		return
	stock_entry.set_posting_time = 1
	stock_entry.posting_date = posting_date


def prepare_auto_manufacture_stock_entry(
	stock_entry,
	actual_rm_consumption: float | None = None,
	finished_good_qty: float | None = None,
	process_loss_qty: float | None = None,
	secondary_items: list | None = None,
	posting_date=None,
) -> None:
	"""Apply Prakash Steel Finish defaults before insert/submit."""
	stock_entry.inspection_required = 0
	qty_changed = False

	apply_job_card_posting_date(stock_entry, posting_date)

	if actual_rm_consumption not in (None, ""):
		apply_actual_rm_consumption(stock_entry, actual_rm_consumption)
		qty_changed = True

	if finished_good_qty not in (None, ""):
		apply_finished_good_qty(stock_entry, finished_good_qty, process_loss_qty=process_loss_qty)
		qty_changed = True

	if secondary_items:
		apply_job_card_secondary_items(stock_entry, secondary_items)
		qty_changed = True

	if qty_changed and hasattr(stock_entry, "calculate_rate_and_amount"):
		stock_entry.calculate_rate_and_amount(raise_error_if_no_rate=False)


@frappe.whitelist()
def submit_manufacture_stock_entry(
	work_order_id: str,
	qty: float | None = None,
	job_card: str | None = None,
	actual_rm_consumption: float | None = None,
	finished_good_qty: float | None = None,
	process_loss_qty: float | None = None,
) -> dict:
	"""Create the Manufacture Stock Entry the same way as ERPNext Finish, then submit it."""
	from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

	_require_auto_stock_entry_enabled()

	require_all_permissions(
		[
			("Work Order", "read"),
			("Stock Entry", "create"),
			("Stock Entry", "submit"),
		]
	)

	if not work_order_id:
		frappe.throw(_("Work Order is required to create Stock Entry."))

	work_order = frappe.db.get_value(
		"Work Order",
		work_order_id,
		["name", "docstatus", "status"],
		as_dict=True,
	)
	if not work_order:
		frappe.throw(_("Work Order {0} not found.").format(frappe.bold(work_order_id)))
	if cint(work_order.docstatus) != 1:
		frappe.throw(_("Work Order {0} must be submitted.").format(frappe.bold(work_order_id)))
	if work_order.status in ("Stopped", "Closed"):
		frappe.throw(
			_("Cannot finish Work Order {0} because it is {1}.").format(
				frappe.bold(work_order_id), frappe.bold(work_order.status)
			)
		)

	qty = flt(qty) if qty not in (None, "") else None
	loss = flt(process_loss_qty) if process_loss_qty not in (None, "") else None
	fg_qty = flt(finished_good_qty) if finished_good_qty not in (None, "") else None
	rm_qty = flt(actual_rm_consumption) if actual_rm_consumption not in (None, "") else None
	secondary_items = []
	posting_date = None

	if job_card:
		if not rm_qty or rm_qty <= 0:
			frappe.throw(
				_(
					"Actual RM Consumption is required to create Manufacture Stock Entry for Job Card {0}."
				).format(frappe.bold(job_card))
			)
		if not fg_qty or fg_qty <= 0:
			frappe.throw(_("Completed Qty must be greater than 0."))
		secondary_items = get_job_card_secondary_items(job_card)
		loss = get_job_card_process_loss_qty(job_card, secondary_items)
		posting_date = get_job_card_posting_date(job_card)

	if qty is None and fg_qty:
		qty = fg_qty + (loss or 0)
	elif fg_qty is not None and loss is not None:
		qty = fg_qty + loss

	stock_entry = frappe.get_doc(make_stock_entry(work_order_id, "Manufacture", qty=qty))
	# Do not set stock_entry.job_card. That field is for semi-finished manufacture
	# against Job Card.finished_good; these mill Job Cards leave finished_good empty,
	# and ERPNext then throws "Finished Good must be None".
	prepare_auto_manufacture_stock_entry(
		stock_entry,
		actual_rm_consumption=rm_qty,
		finished_good_qty=fg_qty,
		process_loss_qty=loss,
		secondary_items=secondary_items,
		posting_date=posting_date,
	)
	stock_entry.insert()
	stock_entry.submit()
	return stock_entry.as_dict()


def submit_manufacture_stock_entry_for_job_card(doc, method=None):
	"""Auto-run Work Order Finish after the last-operation Job Card is submitted."""
	if not is_automatic_manufacture_stock_entry_enabled():
		return

	if not should_create_manufacture_stock_entry_for_job_card(doc):
		return

	completed_qty = flt(doc.total_completed_qty)
	if completed_qty <= 0:
		frappe.throw(
			_(
				"Cannot finish Work Order because Completed Qty is 0 on Job Card {0}."
			).format(frappe.bold(doc.name))
		)

	actual_rm_consumption = flt(getattr(doc, "custom_actual_rm_consumption", 0))
	if actual_rm_consumption <= 0:
		frappe.throw(
			_(
				"Actual RM Consumption is required to finish Work Order from Job Card {0}."
			).format(frappe.bold(doc.name))
		)

	secondary_items = get_job_card_secondary_items(doc)
	process_loss_qty = get_job_card_process_loss_qty(doc, secondary_items)

	stock_entry = submit_manufacture_stock_entry(
		doc.work_order,
		qty=completed_qty + process_loss_qty,
		job_card=doc.name,
		actual_rm_consumption=actual_rm_consumption,
		finished_good_qty=completed_qty,
		process_loss_qty=process_loss_qty,
	)
	frappe.msgprint(
		_("Work Order Finish submitted Stock Entry {0}").format(frappe.bold(stock_entry.get("name"))),
		indicator="green",
		alert=True,
	)


@frappe.whitelist()
def get_work_order_finish_defaults(work_order_id: str) -> dict:
	"""Qty defaults for the Work Order Finish popup: Job Card completed qty + process_loss_qty."""
	_require_auto_stock_entry_enabled()

	require_all_permissions([("Work Order", "read")])

	if not work_order_id:
		frappe.throw(_("Work Order is required."))

	job_cards = frappe.get_all(
		"Job Card",
		filters={
			"work_order": work_order_id,
			"docstatus": 1,
			"is_corrective_job_card": 0,
		},
		fields=[
			"name",
			"total_completed_qty",
			"process_loss_qty",
			"custom_actual_rm_consumption",
			"operation_id",
			"sequence_id",
			"operation",
		],
		order_by="modified desc",
	)

	job_card = None
	for card in job_cards:
		card_doc = frappe._dict(card)
		card_doc.work_order = work_order_id
		card_doc.docstatus = 1
		if should_create_manufacture_stock_entry_for_job_card(card_doc):
			job_card = card
			break

	if not job_card:
		return {
			"job_card": None,
			"total_completed_qty": 0,
			"process_loss_qty": 0,
			"actual_rm_consumption": 0,
			"qty": 0,
		}

	completed_qty = flt(job_card.get("total_completed_qty"))
	process_loss_qty = get_job_card_process_loss_qty(job_card.get("name"))
	return {
		"job_card": job_card.get("name"),
		"total_completed_qty": completed_qty,
		"process_loss_qty": process_loss_qty,
		"actual_rm_consumption": flt(job_card.get("custom_actual_rm_consumption")),
		"qty": completed_qty + process_loss_qty,
	}


def calculate_job_card_time_log_billet_cutting(doc, method=None):
	"""
	Set custom_total_billet_cutting per time log as remaining pcs before that row.

	remaining = WO.custom_total_raw_material_pcs
	           - submitted Job Card usage (same WO, excluding this Job Card)
	           - earlier rows' custom_total on this Job Card
	"""
	is_rolled = bool(doc.custom_rolled_production)
	if not is_rolled and doc.work_order:
		is_rolled = bool(
			frappe.db.get_value("Work Order", doc.work_order, "custom_rolled_production")
		)

	if not doc.work_order or not is_rolled:
		for row in doc.time_logs or []:
			row.custom_total_billet_cutting = None
		return

	pool = flt(
		frappe.db.get_value("Work Order", doc.work_order, "custom_total_raw_material_pcs")
	)
	other_used = get_submitted_job_card_used_pcs(
		doc.work_order, None if doc.is_new() else doc.name
	)

	running_used = 0.0
	for index, row in enumerate(doc.time_logs or [], start=1):
		row.custom_total = _time_log_used_pcs(row)
		remaining = pool - other_used - running_used
		row.custom_total_billet_cutting = remaining

		row_used = flt(row.custom_total)
		if remaining < 0 or row_used > remaining:
			over_by = abs(remaining) if remaining < 0 else (row_used - remaining)
			frappe.throw(
				_(
					"Row {0}: No pieces left! You are trying to use {1} more pieces than available. "
					"Please reduce the quantities."
				).format(index, flt(over_by, 0)),
				title=_("Billet Cutting Pcs Exceeded"),
			)

		running_used += row_used


def _job_card_completed_qty_total(doc) -> float:
	"""Sum completed_qty from Job Card time logs (skip when sub-operations drive totals)."""
	if doc.sub_operations:
		return flt(doc.total_completed_qty)

	return sum(flt(row.completed_qty) for row in (doc.time_logs or []))


def prepare_job_card_completed_qty(doc, method=None):
	"""Back-fill time log completed_qty before ERPNext validates submit totals."""
	if cint(doc.docstatus) != 1 or doc.sub_operations:
		return

	if _job_card_completed_qty_total(doc) > 0 or not flt(doc.for_quantity) or not doc.time_logs:
		return

	remaining_qty = (
		flt(doc.for_quantity) - flt(doc.pending_qty) - flt(doc.process_loss_qty)
	)
	if remaining_qty <= 0:
		return

	target_row = None
	for row in reversed(doc.time_logs):
		if row.to_time:
			target_row = row
			break

	if not target_row and len(doc.time_logs) == 1:
		target_row = doc.time_logs[0]

	if target_row:
		target_row.completed_qty = remaining_qty


def calculate_job_card_total_completed_qty(doc, method=None):
	"""Keep total_completed_qty aligned with time log completed_qty rows."""
	if doc.sub_operations:
		return

	doc.total_completed_qty = flt(
		_job_card_completed_qty_total(doc),
		frappe.get_precision("Job Card", "total_completed_qty") or 2,
	)


def calculate_job_card_finish_pcs(doc, method=None):
	"""Set custom_finish_pcs as the sum of custom_finish_item across time_logs."""
	doc.custom_finish_pcs = sum(cint(row.custom_finish_item) for row in (doc.time_logs or []))


def calculate_job_card_miss_pcs(doc, method=None):
	"""Set Job Card miss totals from time log miss pcs and weight fields."""
	doc.custom_total_miss_roll = sum(cint(row.custom_miss_roll) for row in (doc.time_logs or []))
	doc.custom_total_miss_ingot_or_billet = sum(
		cint(row.custom_miss_ingot_or_billet) for row in (doc.time_logs or [])
	)
	doc.custom_total_miss_roll_weight = sum(
		cint(row.custom_miss_roll_weight) for row in (doc.time_logs or [])
	)
	doc.custom_total_miss_ingot_or_billet_weight = sum(
		cint(row.custom_miss_ingot_or_billet_weight) for row in (doc.time_logs or [])
	)


def calculate_job_card_fg_per_pcs_weight(doc, method=None):
	"""Set custom_fg_per_pcs_weight = round(total_completed_qty / custom_finish_pcs, 2)."""
	finish_pcs = cint(doc.custom_finish_pcs)
	if finish_pcs > 0 and flt(doc.total_completed_qty):
		doc.custom_fg_per_pcs_weight = flt(flt(doc.total_completed_qty) / finish_pcs, 2)
	else:
		doc.custom_fg_per_pcs_weight = 0


def set_job_card_colour_code(doc, method=None):
	"""Set custom_colour_code from production_item grade via Item Grade wise Colour Code."""
	if not doc.production_item:
		doc.custom_colour_code = None
		return

	grade = frappe.db.get_value("Item", doc.production_item, "custom_grade")
	if not grade:
		doc.custom_colour_code = None
		return

	doc.custom_colour_code = frappe.db.get_value(
		"Item Grade wise Colour Code",
		{"item_grade": grade},
		"colour_code",
	)


def get_work_order_billet_weight(work_order: str) -> float:
	"""miss_billet_weight + sum(required_items.consumed_qty) for a Work Order."""
	if not work_order:
		return 0.0

	miss_billet_weight = flt(
		frappe.db.get_value("Work Order", work_order, "custom_miss_billet_weight")
	)
	consumed_qty = flt(
		frappe.db.sql(
			"""
			SELECT SUM(IFNULL(consumed_qty, 0))
			FROM `tabWork Order Item`
			WHERE parent = %s
			""",
			work_order,
		)[0][0]
	)
	return flt(miss_billet_weight + consumed_qty)


def calculate_job_card_billet_weight(doc, method=None):
	"""Set custom_billet_weight from linked Work Order miss billet weight + consumed qty.

	Skip form validate after submit to avoid allow_on_submit errors. Submitted Job Cards
	are refreshed from Stock Entry via update_job_cards_billet_weight.
	"""
	if doc.docstatus == 1:
		return

	if not doc.work_order:
		doc.custom_billet_weight = 0
		return

	doc.custom_billet_weight = get_work_order_billet_weight(doc.work_order)


def update_job_cards_billet_weight(work_order: str):
	"""Sync custom_billet_weight on Job Cards when Work Order consumption changes."""
	if not work_order:
		return

	billet_weight = get_work_order_billet_weight(work_order)
	job_cards = frappe.get_all(
		"Job Card",
		filters={"work_order": work_order, "docstatus": ("<", 2)},
		pluck="name",
	)
	for name in job_cards:
		frappe.db.set_value(
			"Job Card",
			name,
			"custom_billet_weight",
			billet_weight,
			update_modified=False,
		)


def validate_job_card_time_log_miss_fields(doc, method=None):
	"""Enforce miss-roll and miss-ingot dependent fields on Job Card time logs."""
	for index, row in enumerate(doc.time_logs or [], start=1):
		row.custom_total = _time_log_used_pcs(row)

		row_label = _("Row {0}").format(index)

		if flt(row.custom_miss_roll) > 0:
			if not row.custom_miss_roll_weight:
				frappe.throw(
					_("{0}: Miss Roll Weight is mandatory when Miss Roll (Pcs) is greater than 0.").format(
						row_label
					)
				)
			if not row.custom_reason_for_miss_roll:
				frappe.throw(
					_("{0}: Reason for Miss Roll is mandatory when Miss Roll (Pcs) is greater than 0.").format(
						row_label
					)
				)
		else:
			row.custom_miss_roll_weight = None
			row.custom_reason_for_miss_roll = None

		if flt(row.custom_miss_ingot_or_billet) > 0:
			if not row.custom_miss_ingot_or_billet_weight:
				frappe.throw(
					_(
						"{0}: Miss Ingot / Billet Weight is mandatory when Miss Ingot / Billet (Pcs) is greater than 0."
					).format(row_label)
				)
			if not row.custom_reason_for_miss_ingot_or_billet:
				frappe.throw(
					_(
						"{0}: Reason for Miss Ingot / Billet is mandatory when Miss Ingot / Billet (Pcs) is greater than 0."
					).format(row_label)
				)
		else:
			row.custom_miss_ingot_or_billet_weight = None
			row.custom_reason_for_miss_ingot_or_billet = None
