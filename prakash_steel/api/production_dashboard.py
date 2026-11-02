# Copyright (c) 2025, Prakash Steel and contributors
# For license information, please see license.txt

import frappe
from datetime import date as _date, timedelta
from io import BytesIO

import openpyxl
from frappe import _
from frappe.utils import flt
from frappe.utils.xlsxutils import make_xlsx


def _rolled_loss_percentages(rm_consumption, miss_billet_weight, actual_qty,
                             miss_ingot_weight, melting_weight, miss_roll_weight):
    """Return (wastage %, melting wastage %, finish goods %) for the Rolled Production tab.

    Total RM Weight = RM consumption + Miss Billet Weight (same as the "Total RM Weight" column).
    Wastage %         = (Total RM Weight - Miss Ingot/Billet Wt - Actual Qty) / Total RM Weight
    Melting Wastage % = (Melting Wt + Miss Roll Wt) / Actual Qty
    Finish Goods %    = 100 - (Wastage % + Melting Wastage %)
    """
    total_rm_weight = flt(rm_consumption) + flt(miss_billet_weight)
    wastage = 0.0
    if total_rm_weight > 0:
        wastage = (
            (total_rm_weight - flt(miss_ingot_weight) - flt(actual_qty)) / total_rm_weight
        ) * 100
    melting_wastage = 0.0
    if flt(actual_qty) > 0:
        melting_wastage = ((flt(melting_weight) + flt(miss_roll_weight)) / flt(actual_qty)) * 100
    finish_goods = 100 - (wastage + melting_wastage)
    return flt(wastage, 2), flt(melting_wastage, 2), flt(finish_goods, 2)


@frappe.whitelist()
def get_rolled_production_data(
    from_date=None,
    to_date=None,
    item_code=None,
    production_plan=None,
    machine_name=None,
    category_name=None,
) -> dict:
    """
    Fetch Rolled Production data for the Production Dashboard.

    Primary source: Billet Cutting (submitted)
    Cross-referenced with:
      - Production Plan Item (po_items) → FG Planned Qty
      - Finish Weight → Actual Qty & related FG fields
      - Burning Loss % (KPI) = aggregate formula on dashboard totals (not Finish Weight field)

    Returns dict with 'rows' (table data) and 'totals' (KPI aggregates).
    """
    if not frappe.has_permission("Billet Cutting", "report"):
        frappe.throw(_("Not permitted to access production dashboard data."), frappe.PermissionError)

    # ── 1.  Fetch Billet Cutting records ────────────────────────────
    conditions = "bc.docstatus = 1"
    params = {}

    if from_date:
        conditions += " AND bc.posting_date >= %(from_date)s"
        params["from_date"] = from_date
    if to_date:
        conditions += " AND bc.posting_date <= %(to_date)s"
        params["to_date"] = to_date
    if item_code:
        conditions += " AND (bc.finish_size = %(item_code)s OR bc.billet_size = %(item_code)s)"
        params["item_code"] = item_code
    if production_plan:
        # Match legacy `Production Plan` link OR new `Production Planning` link
        conditions += (
            " AND (bc.production_plan = %(production_plan)s"
            " OR bc.production_planning = %(production_plan)s)"
        )
        params["production_plan"] = production_plan
    if category_name:
        cat_items = frappe.db.sql(
            """SELECT name FROM `tabItem` WHERE custom_category_name = %(cat)s""",
            {"cat": category_name},
            as_dict=True,
        )
        cat_item_codes = [r.name for r in cat_items]
        if cat_item_codes:
            conditions += " AND (bc.billet_size IN %(cat_items)s OR bc.finish_size IN %(cat_items)s)"
            params["cat_items"] = cat_item_codes
        else:
            # No legacy items match this category — that only rules out the
            # old Billet Cutting rows, not the new Work Order block below,
            # so don't return early here.
            conditions += " AND 1=0"

    billet_cutting_data = frappe.db.sql(
        f"""
		SELECT
			bc.name              AS billet_cutting_name,
			bc.production_plan,
			bc.production_planning,
			bc.posting_date      AS production_date,
			bc.finish_size       AS finished_item,
			bc.billet_length_full AS fg_length,
			bc.billet_size       AS rm,
			bc.billet_weight     AS rm_consumption,
			bc.billet_pcs_full   AS billet_pcs,
			bc.description_of_cutting_billet AS description_of_cutting_billet,
			bc.total_raw_material_pcs AS total_raw_material_pcs,
			bc.miss_billet_pcs   AS miss_billet_pcs,
			bc.miss_billet_weight AS miss_billet_weight,
			bc.heat_no            AS heat_no
		FROM `tabBillet Cutting` bc
		WHERE {conditions}
		ORDER BY bc.posting_date DESC, bc.name DESC
		""",
        params,
        as_dict=True,
    )

    # NOTE: previously returned early here when Billet Cutting had no rows.
    # That's no longer safe to do — the new Work Order + Job Card block further
    # below must still run even when there's no legacy Billet Cutting data.
    # Every step between here and that block already no-ops safely on an
    # empty `billet_cutting_data` list, so nothing else needs to change.

    # Collect unique (production_plan, finished_item) pairs for batch lookups
    pp_item_pairs = set()
    pp_names = set()
    planning_names = set()
    for row in billet_cutting_data:
        if row.production_plan and row.finished_item:
            pp_item_pairs.add((row.production_plan, row.finished_item))
            pp_names.add(row.production_plan)
        if row.production_planning:
            planning_names.add(row.production_planning)

    # ── 2.  Batch-fetch FG Planned Qty from Production Plan Item (legacy) ───
    planned_qty_map = {}  # key: (production_plan, item_code)
    if pp_names:
        pp_list = list(pp_names)
        planned_rows = frappe.db.sql(
            """
			SELECT
				ppi.parent   AS production_plan,
				ppi.item_code,
				ppi.planned_qty
			FROM `tabProduction Plan Item` ppi
			WHERE ppi.parent IN %(pp_list)s
			""",
            {"pp_list": pp_list},
            as_dict=True,
        )
        for pr in planned_rows:
            planned_qty_map[(pr.production_plan, pr.item_code)] = flt(pr.planned_qty)

    # ── 2.a  Fallback: Batch-fetch FG Planned Qty from Production Planning FG Table ──
    # Used only when the legacy Production Plan mapping has no entry for a row.
    planning_qty_map = {}  # key: (production_planning, fg_item)
    if planning_names:
        planning_list = list(planning_names)
        planning_rows = frappe.db.sql(
            """
			SELECT
				ppfg.parent       AS production_planning,
				ppfg.fg_item      AS item_code,
				ppfg.fg_production_qty AS planned_qty
			FROM `tabProduction Planning FG Table` ppfg
			WHERE ppfg.parent IN %(planning_list)s
			""",
            {"planning_list": planning_list},
            as_dict=True,
        )
        for pr in planning_rows:
            planning_qty_map[(pr.production_planning, pr.item_code)] = flt(pr.planned_qty)

    # ── 3.  Batch-fetch Actual Qty/Length/Melting/Miss fields from Finish Weight
    # Map by Billet Cutting ID so values stay tied to the exact RM row.
    fw_map = {}
    if billet_cutting_data:
        bc_names = [
            row.billet_cutting_name
            for row in billet_cutting_data
            if row.get("billet_cutting_name")
        ]
        if bc_names:
            fw_rows = frappe.db.sql(
                """
			SELECT
				fw.billet_cutting_id AS billet_cutting_name,
				SUM(fw.finish_weight)               AS total_finish_weight,
				SUM(fw.melting_weight)              AS total_melting_weight,
				SUM(fw.finish_pcs)                 AS total_finish_pcs,
				SUM(fw.total_miss_roll_pcs)        AS total_miss_roll_pcs,
				SUM(fw.total_miss_roll_weight)     AS total_miss_roll_weight,
				SUM(fw.total_miss_ingot_pcs)       AS total_miss_ingot_pcs,
				SUM(fw.total_miss_ingot_weight)    AS total_miss_ingot_weight,
				(SELECT fw2.length
				 FROM `tabFinish Weight` fw2
				 WHERE fw2.docstatus = 1
				   AND fw2.billet_cutting_id = fw.billet_cutting_id
				   AND fw2.length IS NOT NULL
				   AND fw2.length != ''
				 ORDER BY fw2.creation DESC
				 LIMIT 1) AS length
			FROM `tabFinish Weight` fw
			WHERE fw.docstatus = 1
			  AND fw.billet_cutting_id IN %(bc_names)s
			GROUP BY fw.billet_cutting_id
			""",
                {"bc_names": tuple(bc_names)},
                as_dict=True,
            )
            for fr in fw_rows:
                fw_map[fr.billet_cutting_name] = {
                    "actual_qty": flt(fr.total_finish_weight),
                    "length": fr.length or "",
                    "melting_weight": flt(fr.total_melting_weight),
                    "finish_pcs": flt(fr.total_finish_pcs),
                    "total_miss_roll_pcs": flt(fr.total_miss_roll_pcs),
                    "total_miss_roll_weight": flt(fr.total_miss_roll_weight),
                    "total_miss_ingot_pcs": flt(fr.total_miss_ingot_pcs),
                    "total_miss_ingot_weight": flt(fr.total_miss_ingot_weight),
                }

    # ── 3.a  Compute Total Hr Consumed from Hourly Production (per Billet Cutting) ──
    hours_map = {}
    if billet_cutting_data:
        bc_names = [
            row.billet_cutting_name
            for row in billet_cutting_data
            if row.get("billet_cutting_name")
        ]
        if bc_names:
            hour_rows = frappe.db.sql(
                """
				SELECT
					hp.billet_cutting_id AS billet_cutting_name,
					SUM(
						IF(
							TIME_TO_SEC(hp.time_to) < TIME_TO_SEC(hp.time_from),
							TIME_TO_SEC(hp.time_to) - TIME_TO_SEC(hp.time_from) + 86400,
							TIME_TO_SEC(hp.time_to) - TIME_TO_SEC(hp.time_from)
						)
					) / 3600.0 AS total_hours
				FROM `tabHourly Production` hp
				WHERE hp.docstatus = 1
				  AND hp.billet_cutting_id IN %(bc_names)s
				GROUP BY hp.billet_cutting_id
				""",
                {"bc_names": tuple(bc_names)},
                as_dict=True,
            )
            for hr in hour_rows:
                hours_map[hr.billet_cutting_name] = flt(hr.total_hours, 2)

    # ── 3.b  Batch-fetch custom_category_name from Item ──────────────
    all_item_codes_rolled = set()
    for row in billet_cutting_data:
        if row.rm:
            all_item_codes_rolled.add(row.rm)
        if row.finished_item:
            all_item_codes_rolled.add(row.finished_item)

    category_map_rolled = {}
    if all_item_codes_rolled:
        item_cat_rows = frappe.db.sql(
            """SELECT name, custom_category_name FROM `tabItem` WHERE name IN %(items)s""",
            {"items": list(all_item_codes_rolled)},
            as_dict=True,
        )
        for ir in item_cat_rows:
            category_map_rolled[ir.name] = ir.custom_category_name or ""

    # ── 4.  Assemble final rows ────────────────────────────────────
    rows = []
    total_production = 0
    total_rm_consumption = 0
    total_hours_overall = 0
    total_melting_weight_overall = 0
    total_miss_billet_weight_overall = 0
    total_miss_roll_weight_overall = 0
    total_miss_ingot_weight_overall = 0

    for row in billet_cutting_data:
        pp = row.production_plan or ""
        pp_planning = row.production_planning or ""
        fi = row.finished_item or ""

        # Source priority: legacy `Production Plan` first, then fall back to
        # `Production Planning` if the legacy mapping has no entry for this row.
        old_key = (pp, fi)
        new_key = (pp_planning, fi)
        if pp and fi and old_key in planned_qty_map:
            fg_planned_qty = planned_qty_map[old_key]
        elif pp_planning and fi and new_key in planning_qty_map:
            fg_planned_qty = planning_qty_map[new_key]
        else:
            fg_planned_qty = 0

        fw_data = fw_map.get(row.billet_cutting_name, {})
        actual_qty = fw_data.get("actual_qty", 0)
        melting_weight = fw_data.get("melting_weight", 0)
        finish_pcs = fw_data.get("finish_pcs", 0)
        total_miss_roll_pcs = fw_data.get("total_miss_roll_pcs", 0)
        total_miss_roll_weight = fw_data.get("total_miss_roll_weight", 0)
        total_miss_ingot_pcs = fw_data.get("total_miss_ingot_pcs", 0)
        total_miss_ingot_weight = fw_data.get("total_miss_ingot_weight", 0)
        fg_length = fw_data.get("length", "") or row.fg_length or ""

        burning_loss, melting_wastage, finish_goods = _rolled_loss_percentages(
            row.rm_consumption,
            row.miss_billet_weight,
            actual_qty,
            total_miss_ingot_weight,
            melting_weight,
            total_miss_roll_weight,
        )

        total_production += flt(actual_qty)
        total_rm_consumption += flt(row.rm_consumption)
        total_melting_weight_overall += flt(melting_weight)
        total_miss_billet_weight_overall += flt(row.miss_billet_weight)
        total_miss_roll_weight_overall += flt(total_miss_roll_weight)
        total_miss_ingot_weight_overall += flt(total_miss_ingot_weight)

        total_hr_consumed = hours_map.get(row.billet_cutting_name, 0)
        total_hours_overall += flt(total_hr_consumed)

        rows.append(
            {
                # Show legacy Production Plan if present, otherwise fall back
                # to Production Planning — same response key so the UI is unchanged.
                "production_plan": pp or pp_planning,
                "production_plan_doctype": (
                    "Production Plan" if pp else ("Production Planning" if pp_planning else "")
                ),
                "production_date": (
                    str(row.production_date) if row.production_date else ""
                ),
                "finished_item": fi,
                "fg_planned_qty": flt(fg_planned_qty),
                "actual_qty": flt(actual_qty),
                "melting_weight": flt(melting_weight),
                "finish_pcs": flt(finish_pcs),
                "total_miss_roll_pcs": flt(total_miss_roll_pcs),
                "total_miss_roll_weight": flt(total_miss_roll_weight),
                "total_miss_ingot_pcs": flt(total_miss_ingot_pcs),
                "total_miss_ingot_weight": flt(total_miss_ingot_weight),
                "billet_pcs": flt(row.billet_pcs) if row.billet_pcs else 0,
                "description_of_cutting_billet": row.description_of_cutting_billet
                or "",
                "total_raw_material_pcs": (
                    flt(row.total_raw_material_pcs) if row.total_raw_material_pcs else 0
                ),
                "miss_billet_pcs": (
                    flt(row.miss_billet_pcs) if row.miss_billet_pcs else 0
                ),
                "miss_billet_weight": (
                    flt(row.miss_billet_weight) if row.miss_billet_weight else 0
                ),
                "heat_no": row.heat_no or "",
                "total_hr_consumed": flt(total_hr_consumed, 2),
                "fg_length": fg_length,
                "rm": row.rm or "",
                "rm_consumption": flt(row.rm_consumption),
                "burning_loss": burning_loss,
                "melting_wastage": melting_wastage,
                "finish_goods": finish_goods,
                "rm_category_name": category_map_rolled.get(row.rm or "", ""),
                "finished_item_category_name": category_map_rolled.get(fi, ""),
            }
        )

    # ── 5.  NEW SOURCE: Work Order + Job Card ──────────────────────
    # Billet Cutting / Finish Weight / Hourly Production above stay exactly
    # as they were (old data must remain visible). This block adds rows
    # sourced from the new Work Order + Job Card flow on top, and folds
    # their totals into the same KPI aggregates computed below.
    # A Work Order only counts as real production once there's a submitted
    # Manufacture Stock Entry actually linked to it — submitted or cancelled
    # Work Orders are both eligible, but only when that linkage exists.
    wo_conditions = (
        "wo.docstatus IN (1, 2) AND wo.custom_rolled_production = 1"
        " AND EXISTS ("
        "   SELECT 1 FROM `tabStock Entry` wose"
        "   WHERE wose.work_order = wo.name"
        "     AND wose.stock_entry_type = 'Manufacture'"
        "     AND wose.docstatus = 1"
        " )"
    )
    wo_params = {}

    if from_date:
        wo_conditions += " AND DATE(wo.actual_start_date) >= %(from_date)s"
        wo_params["from_date"] = from_date
    if to_date:
        wo_conditions += " AND DATE(wo.actual_start_date) <= %(to_date)s"
        wo_params["to_date"] = to_date
    if item_code:
        wo_conditions += " AND wo.production_item = %(item_code)s"
        wo_params["item_code"] = item_code
    if production_plan:
        wo_conditions += (
            " AND (wo.name = %(production_plan)s OR wo.production_plan = %(production_plan)s)"
        )
        wo_params["production_plan"] = production_plan
    if category_name:
        cat_items_wo = frappe.db.sql(
            """SELECT name FROM `tabItem` WHERE custom_category_name = %(cat)s""",
            {"cat": category_name},
            as_dict=True,
        )
        cat_item_codes_wo = [r.name for r in cat_items_wo]
        if cat_item_codes_wo:
            wo_conditions += (
                " AND (wo.production_item IN %(wo_cat_items)s"
                " OR EXISTS ("
                "   SELECT 1 FROM `tabWork Order Item` woic"
                "   WHERE woic.parent = wo.name AND woic.item_code IN %(wo_cat_items)s"
                " ))"
            )
            wo_params["wo_cat_items"] = cat_item_codes_wo
        else:
            wo_conditions += " AND 1=0"

    work_order_data = frappe.db.sql(
        f"""
		SELECT
			wo.name                                  AS work_order_name,
			wo.production_plan                       AS production_plan,
			DATE(wo.actual_start_date)                AS production_date,
			wo.production_item                       AS finished_item,
			wo.qty                                   AS fg_planned_qty,
			wo.produced_qty                          AS actual_qty,
			wo.custom_billet_pcs                     AS billet_pcs,
			wo.custom_billet_length                  AS billet_length,
			wo.custom_description_of_cutting_billet  AS description_of_cutting_billet,
			wo.custom_total_raw_material_pcs         AS total_raw_material_pcs,
			wo.custom_miss_billet_pcs                AS miss_billet_pcs,
			wo.custom_miss_billet_weight              AS miss_billet_weight,
			wo.custom_heat_no                        AS heat_no,
			wo.custom_burning_loss                   AS burning_loss,
			(SELECT woi.item_code
			 FROM `tabWork Order Item` woi
			 WHERE woi.parent = wo.name
			 ORDER BY woi.idx ASC LIMIT 1)                                 AS rm,
			(SELECT woi.consumed_qty
			 FROM `tabWork Order Item` woi
			 WHERE woi.parent = wo.name
			 ORDER BY woi.idx ASC LIMIT 1)                                 AS rm_consumption,
			(SELECT jcl.custom_fg_length
			 FROM `tabJob Card` jcl
			 WHERE jcl.work_order = wo.name AND jcl.docstatus = 1
			   AND jcl.custom_fg_length IS NOT NULL AND jcl.custom_fg_length != ''
			 ORDER BY jcl.creation DESC LIMIT 1)                          AS jc_fg_length,
			SUM(COALESCE(jc.custom_melting_weight, 0))                    AS melting_weight,
			SUM(COALESCE(jc.custom_finish_pcs, 0))                        AS finish_pcs,
			SUM(COALESCE(jc.custom_total_miss_roll, 0))                   AS total_miss_roll_pcs,
			SUM(COALESCE(jc.custom_total_miss_roll_weight, 0))            AS total_miss_roll_weight,
			SUM(COALESCE(jc.custom_total_miss_ingot_or_billet, 0))        AS total_miss_ingot_pcs,
			SUM(COALESCE(jc.custom_total_miss_ingot_or_billet_weight, 0)) AS total_miss_ingot_weight,
			(SELECT SUM(jctl.time_in_mins)
			 FROM `tabJob Card Time Log` jctl
			 INNER JOIN `tabJob Card` jct ON jct.name = jctl.parent
			 WHERE jct.work_order = wo.name AND jct.docstatus = 1)        AS total_time_in_mins
		FROM `tabWork Order` wo
		LEFT JOIN `tabJob Card` jc ON jc.work_order = wo.name AND jc.docstatus = 1
		WHERE {wo_conditions}
		GROUP BY wo.name
		ORDER BY wo.actual_start_date DESC, wo.name DESC
		""",
        wo_params,
        as_dict=True,
    )

    if work_order_data:
        # Batch-fetch custom_category_name for any items not already covered above.
        # (FG Planned Qty for these rows comes straight from wo.qty — no Production
        # Plan Item / Production Planning FG Table lookup needed here.)
        extra_item_codes = set()
        for r in work_order_data:
            if r.rm:
                extra_item_codes.add(r.rm)
            if r.finished_item:
                extra_item_codes.add(r.finished_item)
        extra_item_codes -= set(category_map_rolled.keys())
        if extra_item_codes:
            extra_item_cat_rows = frappe.db.sql(
                """SELECT name, custom_category_name FROM `tabItem` WHERE name IN %(items)s""",
                {"items": list(extra_item_codes)},
                as_dict=True,
            )
            for ir in extra_item_cat_rows:
                category_map_rolled[ir.name] = ir.custom_category_name or ""

        for row in work_order_data:
            fi = row.finished_item or ""

            # FG Planned Qty is the Work Order's own Qty To Manufacture field
            # for the new flow — no Production Plan Item lookup needed.
            fg_planned_qty = flt(row.fg_planned_qty)

            actual_qty = flt(row.actual_qty)
            rm_c = flt(row.rm_consumption)
            miss_bw = flt(row.miss_billet_weight)
            total_miss_ingot_weight = flt(row.total_miss_ingot_weight)

            burning_loss, melting_wastage, finish_goods = _rolled_loss_percentages(
                rm_c,
                miss_bw,
                actual_qty,
                total_miss_ingot_weight,
                row.melting_weight,
                row.total_miss_roll_weight,
            )

            total_hr_consumed = flt((row.total_time_in_mins or 0) / 60.0, 2)

            total_production += actual_qty
            total_rm_consumption += rm_c
            total_melting_weight_overall += flt(row.melting_weight)
            total_miss_billet_weight_overall += miss_bw
            total_miss_roll_weight_overall += flt(row.total_miss_roll_weight)
            total_miss_ingot_weight_overall += total_miss_ingot_weight
            total_hours_overall += total_hr_consumed

            rows.append(
                {
                    "production_plan": row.work_order_name,
                    "production_plan_doctype": "Work Order",
                    "production_date": (
                        str(row.production_date) if row.production_date else ""
                    ),
                    "finished_item": fi,
                    "fg_planned_qty": flt(fg_planned_qty),
                    "actual_qty": actual_qty,
                    "melting_weight": flt(row.melting_weight),
                    "finish_pcs": flt(row.finish_pcs),
                    "total_miss_roll_pcs": flt(row.total_miss_roll_pcs),
                    "total_miss_roll_weight": flt(row.total_miss_roll_weight),
                    "total_miss_ingot_pcs": flt(row.total_miss_ingot_pcs),
                    "total_miss_ingot_weight": total_miss_ingot_weight,
                    "billet_pcs": flt(row.billet_pcs) if row.billet_pcs else 0,
                    "description_of_cutting_billet": row.description_of_cutting_billet or "",
                    "total_raw_material_pcs": (
                        flt(row.total_raw_material_pcs) if row.total_raw_material_pcs else 0
                    ),
                    "miss_billet_pcs": flt(row.miss_billet_pcs) if row.miss_billet_pcs else 0,
                    "miss_billet_weight": miss_bw,
                    "heat_no": row.heat_no or "",
                    "total_hr_consumed": total_hr_consumed,
                    "fg_length": row.jc_fg_length or row.billet_length or "",
                    "rm": row.rm or "",
                    "rm_consumption": rm_c,
                    "burning_loss": burning_loss,
                    "melting_wastage": melting_wastage,
                    "finish_goods": finish_goods,
                    "rm_category_name": category_map_rolled.get(row.rm or "", ""),
                    "finished_item_category_name": category_map_rolled.get(fi, ""),
                }
            )

    # Old rows and new (Work Order-sourced) rows were built as two separate
    # blocks above and are otherwise each already date-sorted individually —
    # re-sort the combined list so they interleave by date instead of the new
    # ones always trailing at the very end regardless of how recent they are.
    rows.sort(key=lambda r: r.get("production_date") or "", reverse=True)

    # Dashboard Wastage % = (Total RM Weight - Miss Ingot - Production) / Total RM Weight × 100,
    # where Total RM Weight = RM + Miss Billet.
    burning_loss_per_total, melting_wastage_per_total, finish_goods_per_total = (
        _rolled_loss_percentages(
            total_rm_consumption,
            total_miss_billet_weight_overall,
            total_production,
            total_miss_ingot_weight_overall,
            total_melting_weight_overall,
            total_miss_roll_weight_overall,
        )
    )

    return {
        "rows": rows,
        "totals": {
            "total_production": flt(total_production),
            "rm_consumption": flt(total_rm_consumption),
            "total_hr_consumed": flt(total_hours_overall, 2),
            "total_melting_weight": flt(total_melting_weight_overall),
            "total_miss_billet_weight": flt(total_miss_billet_weight_overall),
            "total_miss_roll_weight": flt(total_miss_roll_weight_overall),
            "total_miss_ingot_weight": flt(total_miss_ingot_weight_overall),
            "burning_loss_per": burning_loss_per_total,
            "melting_wastage_per": melting_wastage_per_total,
            "finish_goods_per": finish_goods_per_total,
        },
    }


@frappe.whitelist()
def get_bright_production_data(
    from_date=None,
    to_date=None,
    item_code=None,
    production_plan=None,
    machine_name=None,
    category_name=None,
) -> dict:
    """
    Fetch Bright Production data for the Production Dashboard.

    Primary source: Bright Bar Production (submitted)
    Cross-referenced with:
      - Production Plan Item (po_items) → FG Planned Qty

    Returns dict with 'rows' (table data) and 'totals' (KPI aggregates).
    """
    if not frappe.has_permission("Bright Bar Production", "read"):
        frappe.throw(_("Not permitted to access bright production dashboard data."), frappe.PermissionError)

    # ── 1.  Fetch Bright Bar Production records ────────────────────
    conditions = "bbp.docstatus = 1"
    params = {}

    if from_date:
        conditions += " AND bbp.production_date >= %(from_date)s"
        params["from_date"] = from_date
    if to_date:
        conditions += " AND bbp.production_date <= %(to_date)s"
        params["to_date"] = to_date
    if item_code:
        # Match against both legacy (`finished_good` / `raw_material`) and new
        # (`finished` / `material`) fields so Production Planning-based rows work.
        conditions += (
            " AND ("
            "bbp.finished_good = %(item_code)s"
            " OR bbp.raw_material = %(item_code)s"
            " OR bbp.finished = %(item_code)s"
            " OR bbp.material = %(item_code)s"
            ")"
        )
        params["item_code"] = item_code
    if production_plan:
        # Match legacy `Production Plan` link OR new `Production Planning` link
        conditions += (
            " AND (bbp.production_plan = %(production_plan)s"
            " OR bbp.production_planning = %(production_plan)s)"
        )
        params["production_plan"] = production_plan
    if machine_name:
        conditions += " AND bbp.machine_name = %(machine_name)s"
        params["machine_name"] = machine_name
    if category_name:
        cat_items = frappe.db.sql(
            """SELECT name FROM `tabItem` WHERE custom_category_name = %(cat)s""",
            {"cat": category_name},
            as_dict=True,
        )
        cat_item_codes = [r.name for r in cat_items]
        if cat_item_codes:
            # Match against both legacy and new RM/FG fields so Production
            # Planning-based rows are picked up too.
            conditions += (
                " AND ("
                "bbp.raw_material IN %(cat_items)s"
                " OR bbp.finished_good IN %(cat_items)s"
                " OR bbp.material IN %(cat_items)s"
                " OR bbp.finished IN %(cat_items)s"
                ")"
            )
            params["cat_items"] = cat_item_codes
        else:
            # No legacy items match this category — that only rules out the
            # old Bright Bar Production rows, not the new Work Order block
            # below, so don't return early here.
            conditions += " AND 1=0"

    # Bright Bar Production has two sets of RM / FG fields:
    #   - Legacy `raw_material` / `finished_good` populated when the old
    #     `Production Plan` link is used.
    #   - New `material` / `finished` populated when the new `Production Planning`
    #     link is used (see bright_bar_production.js -> load_options_from_production_planning).
    # Use COALESCE so the dashboard shows whichever one actually holds a value.
    bright_data = frappe.db.sql(
        f"""
		SELECT
			bbp.name                  AS bright_bar_name,
			bbp.production_plan,
			bbp.production_planning,
			bbp.production_date,
			COALESCE(NULLIF(bbp.finished_good, ''), bbp.finished) AS finished_item,
			bbp.fg_weight             AS fg_weight,
			bbp.fg_weight             AS actual_qty,
			bbp.end_cutting_weight    AS end_cutting_weight,
			bbp.finish_length         AS fg_length,
			COALESCE(NULLIF(bbp.raw_material, ''), bbp.material)  AS rm,
			bbp.actual_rm_consumption AS rm_consumption,
			bbp.wastage_per           AS wastage,
			bbp.machine_name          AS machine_name,
			bbp.finish_length         AS finish_length,
			bbp.tolerance             AS tolerance
		FROM `tabBright Bar Production` bbp
		WHERE {conditions}
		ORDER BY bbp.production_date DESC, bbp.name DESC
		""",
        params,
        as_dict=True,
    )

    # NOTE: previously returned early here when Bright Bar Production had no
    # rows. That's no longer safe — the new Work Order + Job Card block
    # further below must still run even when there's no legacy data. Every
    # step between here and that block already no-ops safely on an empty
    # `bright_data` list, so nothing else needs to change.

    # Collect unique production plan names for batch lookup
    pp_names = set()
    planning_names = set()
    pp_item_pairs = set()
    for row in bright_data:
        if row.production_plan:
            pp_names.add(row.production_plan)
            if row.finished_item:
                pp_item_pairs.add((row.production_plan, row.finished_item))
        if row.production_planning:
            planning_names.add(row.production_planning)

    # ── 2.  Batch-fetch FG Planned Qty from Production Plan Item (legacy) ───
    planned_qty_map = {}
    if pp_names:
        pp_list = list(pp_names)
        planned_rows = frappe.db.sql(
            """
			SELECT
				ppi.parent   AS production_plan,
				ppi.item_code,
				ppi.planned_qty
			FROM `tabProduction Plan Item` ppi
			WHERE ppi.parent IN %(pp_list)s
			""",
            {"pp_list": pp_list},
            as_dict=True,
        )
        for pr in planned_rows:
            planned_qty_map[(pr.production_plan, pr.item_code)] = flt(pr.planned_qty)

    # ── 2.a  Fallback: Batch-fetch FG Planned Qty from Production Planning FG Table ──
    # Used only when the legacy Production Plan mapping has no entry for a row.
    planning_qty_map = {}
    if planning_names:
        planning_list = list(planning_names)
        planning_rows = frappe.db.sql(
            """
			SELECT
				ppfg.parent       AS production_planning,
				ppfg.fg_item      AS item_code,
				ppfg.fg_production_qty AS planned_qty
			FROM `tabProduction Planning FG Table` ppfg
			WHERE ppfg.parent IN %(planning_list)s
			""",
            {"planning_list": planning_list},
            as_dict=True,
        )
        for pr in planning_rows:
            planning_qty_map[(pr.production_planning, pr.item_code)] = flt(pr.planned_qty)

    # ── 2.b  Batch-fetch End Cutting Weight from Job Card ────────────
    # Job Card has no direct link to Bright Bar Production, so rows are matched the
    # same way FG Planned Qty is: on the legacy Production Plan plus the finished item.
    # Only bright-production Job Cards count; Bright Bar Production is the fallback.
    job_card_end_cutting_map = {}  # key: (production_plan, item_code)
    if pp_names:
        jc_rows = frappe.db.sql(
            """
			SELECT
				wo.production_plan AS production_plan,
				jc.production_item AS item_code,
				SUM(jc.custom_end_cutting_weight) AS end_cutting_weight
			FROM `tabJob Card` jc
			INNER JOIN `tabWork Order` wo ON wo.name = jc.work_order
			WHERE jc.docstatus = 1
			  AND jc.custom_bright_production = 1
			  AND wo.production_plan IN %(pp_list)s
			GROUP BY wo.production_plan, jc.production_item
			""",
            {"pp_list": list(pp_names)},
            as_dict=True,
        )
        for jr in jc_rows:
            job_card_end_cutting_map[(jr.production_plan, jr.item_code)] = flt(
                jr.end_cutting_weight
            )

    # ── 2.c  Batch-fetch custom_category_name from Item ──────────────
    all_item_codes_bright = set()
    for row in bright_data:
        if row.rm:
            all_item_codes_bright.add(row.rm)
        if row.finished_item:
            all_item_codes_bright.add(row.finished_item)

    category_map_bright = {}
    if all_item_codes_bright:
        item_cat_rows = frappe.db.sql(
            """SELECT name, custom_category_name FROM `tabItem` WHERE name IN %(items)s""",
            {"items": list(all_item_codes_bright)},
            as_dict=True,
        )
        for ir in item_cat_rows:
            category_map_bright[ir.name] = ir.custom_category_name or ""

    # ── 3.  Assemble final rows ────────────────────────────────────
    rows = []
    total_production = 0
    total_rm_consumption = 0
    total_fg_weight = 0.0
    total_end_cutting_weight = 0.0
    total_rm_for_wastage = 0.0

    for row in bright_data:
        pp = row.production_plan or ""
        pp_planning = row.production_planning or ""
        fi = row.finished_item or ""

        # Source priority: legacy `Production Plan` first, then fall back to
        # `Production Planning` if the legacy mapping has no entry for this row.
        old_key = (pp, fi)
        new_key = (pp_planning, fi)
        if pp and fi and old_key in planned_qty_map:
            fg_planned_qty = planned_qty_map[old_key]
        elif pp_planning and fi and new_key in planning_qty_map:
            fg_planned_qty = planning_qty_map[new_key]
        else:
            fg_planned_qty = 0

        # Source priority: Job Card first, then fall back to the value entered on
        # Bright Bar Production itself when no Job Card matches this row.
        if pp and fi and old_key in job_card_end_cutting_map:
            end_cutting_weight = job_card_end_cutting_map[old_key]
        else:
            end_cutting_weight = flt(row.end_cutting_weight)

        rm_consumption = flt(row.rm_consumption)
        actual_qty = flt(row.actual_qty)
        fg_weight = flt(row.fg_weight)

        total_production += actual_qty
        total_rm_consumption += rm_consumption
        total_fg_weight += fg_weight
        total_end_cutting_weight += flt(end_cutting_weight)
        total_rm_for_wastage += rm_consumption

        rows.append(
            {
                # Show legacy Production Plan if present, otherwise fall back
                # to Production Planning — same response key so the UI is unchanged.
                "production_plan": pp or pp_planning,
                "production_plan_doctype": (
                    "Production Plan" if pp else ("Production Planning" if pp_planning else "")
                ),
                "production_date": (
                    str(row.production_date) if row.production_date else ""
                ),
                "finished_item": fi,
                "fg_planned_qty": flt(fg_planned_qty),
                "actual_qty": actual_qty,
                "fg_weight": fg_weight,
                "end_cutting_weight": flt(end_cutting_weight),
                "fg_length": row.fg_length or "",
                "rm": row.rm or "",
                "rm_consumption": rm_consumption,
                "wastage": flt(row.wastage, 2),
                "machine_name": row.machine_name or "",
                "finish_length": row.finish_length or "",
                "tolerance": row.tolerance or "",
                "rm_category_name": category_map_bright.get(row.rm or "", ""),
                "finished_item_category_name": category_map_bright.get(fi, ""),
            }
        )

    # ── 4.  NEW SOURCE: Work Order + Job Card ──────────────────────
    # Bright Bar Production above stays exactly as it was (old data must
    # remain visible). This block adds rows sourced from the new Work Order +
    # Job Card flow on top, and folds their totals into the same KPI
    # aggregates computed below.
    # A Work Order only counts as real production once there's a submitted
    # Manufacture Stock Entry actually linked to it — submitted or cancelled
    # Work Orders are both eligible, but only when that linkage exists.
    wo_conditions = (
        "wo.docstatus IN (1, 2) AND wo.custom_bright_production = 1"
        " AND EXISTS ("
        "   SELECT 1 FROM `tabStock Entry` wose"
        "   WHERE wose.work_order = wo.name"
        "     AND wose.stock_entry_type = 'Manufacture'"
        "     AND wose.docstatus = 1"
        " )"
    )
    wo_params = {}

    if from_date:
        wo_conditions += " AND DATE(wo.actual_start_date) >= %(from_date)s"
        wo_params["from_date"] = from_date
    if to_date:
        wo_conditions += " AND DATE(wo.actual_start_date) <= %(to_date)s"
        wo_params["to_date"] = to_date
    if item_code:
        wo_conditions += (
            " AND (wo.production_item = %(item_code)s"
            " OR EXISTS ("
            "   SELECT 1 FROM `tabWork Order Item` woii"
            "   WHERE woii.parent = wo.name AND woii.item_code = %(item_code)s"
            " ))"
        )
        wo_params["item_code"] = item_code
    if production_plan:
        wo_conditions += (
            " AND (wo.name = %(production_plan)s OR wo.production_plan = %(production_plan)s)"
        )
        wo_params["production_plan"] = production_plan
    if machine_name:
        wo_conditions += (
            " AND EXISTS ("
            "   SELECT 1 FROM `tabJob Card` jcm"
            "   WHERE jcm.work_order = wo.name AND jcm.docstatus = 1"
            "     AND jcm.workstation = %(machine_name)s"
            " )"
        )
        wo_params["machine_name"] = machine_name
    if category_name:
        cat_items_wo = frappe.db.sql(
            """SELECT name FROM `tabItem` WHERE custom_category_name = %(cat)s""",
            {"cat": category_name},
            as_dict=True,
        )
        cat_item_codes_wo = [r.name for r in cat_items_wo]
        if cat_item_codes_wo:
            wo_conditions += (
                " AND (wo.production_item IN %(wo_cat_items)s"
                " OR EXISTS ("
                "   SELECT 1 FROM `tabWork Order Item` woic"
                "   WHERE woic.parent = wo.name AND woic.item_code IN %(wo_cat_items)s"
                " ))"
            )
            wo_params["wo_cat_items"] = cat_item_codes_wo
        else:
            wo_conditions += " AND 1=0"

    work_order_data = frappe.db.sql(
        f"""
		SELECT
			wo.name                    AS work_order_name,
			wo.production_plan         AS production_plan,
			DATE(wo.actual_start_date)  AS production_date,
			wo.production_item         AS finished_item,
			wo.qty                     AS fg_planned_qty,
			wo.produced_qty            AS actual_qty,
			(SELECT jcw.workstation
			 FROM `tabJob Card` jcw
			 WHERE jcw.work_order = wo.name AND jcw.docstatus = 1
			   AND jcw.workstation IS NOT NULL AND jcw.workstation != ''
			 ORDER BY jcw.creation DESC LIMIT 1)                      AS machine_name,
			(SELECT woi.item_code
			 FROM `tabWork Order Item` woi
			 WHERE woi.parent = wo.name
			 ORDER BY woi.idx ASC LIMIT 1)                            AS rm,
			(SELECT woi.consumed_qty
			 FROM `tabWork Order Item` woi
			 WHERE woi.parent = wo.name
			 ORDER BY woi.idx ASC LIMIT 1)                            AS rm_consumption,
			(SELECT jcf.custom_finish_length
			 FROM `tabJob Card` jcf
			 WHERE jcf.work_order = wo.name AND jcf.docstatus = 1
			   AND jcf.custom_finish_length IS NOT NULL AND jcf.custom_finish_length != ''
			 ORDER BY jcf.creation DESC LIMIT 1)                      AS finish_length,
			(SELECT jct.custom_tolerance
			 FROM `tabJob Card` jct
			 WHERE jct.work_order = wo.name AND jct.docstatus = 1
			   AND jct.custom_tolerance IS NOT NULL AND jct.custom_tolerance != ''
			 ORDER BY jct.creation DESC LIMIT 1)                      AS tolerance,
			wo.custom_wastage                                         AS wastage,
			SUM(COALESCE(jc.custom_melting_weight, 0))                AS melting_weight,
			SUM(COALESCE(jc.custom_end_cutting_weight, 0))            AS end_cutting_weight
		FROM `tabWork Order` wo
		LEFT JOIN `tabJob Card` jc ON jc.work_order = wo.name AND jc.docstatus = 1
		WHERE {wo_conditions}
		GROUP BY wo.name
		ORDER BY wo.actual_start_date DESC, wo.name DESC
		""",
        wo_params,
        as_dict=True,
    )

    if work_order_data:
        # Batch-fetch custom_category_name for any items not already covered above.
        # (FG Planned Qty for these rows comes straight from wo.qty — no Production
        # Plan Item / Production Planning FG Table lookup needed here.)
        extra_item_codes = set()
        for r in work_order_data:
            if r.rm:
                extra_item_codes.add(r.rm)
            if r.finished_item:
                extra_item_codes.add(r.finished_item)
        extra_item_codes -= set(category_map_bright.keys())
        if extra_item_codes:
            extra_item_cat_rows = frappe.db.sql(
                """SELECT name, custom_category_name FROM `tabItem` WHERE name IN %(items)s""",
                {"items": list(extra_item_codes)},
                as_dict=True,
            )
            for ir in extra_item_cat_rows:
                category_map_bright[ir.name] = ir.custom_category_name or ""

        for row in work_order_data:
            fi = row.finished_item or ""

            # FG Planned Qty is the Work Order's own Qty To Manufacture field
            # for the new flow — no Production Plan Item lookup needed.
            fg_planned_qty = flt(row.fg_planned_qty)

            actual_qty = flt(row.actual_qty)
            rm_consumption = flt(row.rm_consumption)
            # "Melting Weight" column is sourced from the linked Job Card,
            # not from produced_qty (that's Actual Qty, a separate figure).
            fg_weight = flt(row.melting_weight)
            # These rows link to their Job Cards directly, so End Cutting Weight
            # is summed straight off them — no Production Plan matching needed.
            end_cutting_weight = flt(row.end_cutting_weight)

            total_production += actual_qty
            total_rm_consumption += rm_consumption
            total_fg_weight += fg_weight
            total_end_cutting_weight += end_cutting_weight
            total_rm_for_wastage += rm_consumption

            rows.append(
                {
                    "production_plan": row.work_order_name,
                    "production_plan_doctype": "Work Order",
                    "production_date": (
                        str(row.production_date) if row.production_date else ""
                    ),
                    "finished_item": fi,
                    "fg_planned_qty": flt(fg_planned_qty),
                    "actual_qty": actual_qty,
                    "fg_weight": fg_weight,
                    "end_cutting_weight": flt(end_cutting_weight),
                    "fg_length": "",
                    "rm": row.rm or "",
                    "rm_consumption": rm_consumption,
                    "wastage": flt(row.wastage, 2),
                    "machine_name": row.machine_name or "",
                    "finish_length": row.finish_length or "",
                    "tolerance": row.tolerance or "",
                    "rm_category_name": category_map_bright.get(row.rm or "", ""),
                    "finished_item_category_name": category_map_bright.get(fi, ""),
                }
            )

    # Old rows and new (Work Order-sourced) rows were built as two separate
    # blocks above and are otherwise each already date-sorted individually —
    # re-sort the combined list so they interleave by date instead of the new
    # ones always trailing at the very end regardless of how recent they are.
    rows.sort(key=lambda r: r.get("production_date") or "", reverse=True)

    # Average Wastage % for KPI card
    avg_wastage_per = 0.0
    wastage_values = [
        flt(row.get("wastage", 0))
        for row in bright_data
        if row.get("wastage") is not None
    ]
    wastage_values.extend(
        flt(r.wastage) for r in work_order_data if r.wastage is not None
    )
    if wastage_values:
        avg_wastage_per = sum(wastage_values) / len(wastage_values)

    return {
        "rows": rows,
        "totals": {
            "total_production": flt(total_production),
            "rm_consumption": flt(total_rm_consumption),
            "total_fg_weight": flt(total_fg_weight),
            "total_end_cutting_weight": flt(total_end_cutting_weight),
            "wastage_per": flt(avg_wastage_per, 2),
        },
    }


@frappe.whitelist()
def get_bend_weight_details(
    from_date=None,
    to_date=None,
    item_code=None,
    production_plan=None,
    machine_name=None,
    category_name=None,
) -> dict | list:
    """
    Fetch Bend Weight Details for the Production Dashboard.

    Source: Finish Weight (submitted)
    """
    if not frappe.has_permission("Finish Weight", "read"):
        frappe.throw(_("Not permitted to access bend weight details data."), frappe.PermissionError)

    conditions = "fw.docstatus = 1"
    params = {}

    if from_date:
        conditions += " AND fw.posting_date >= %(from_date)s"
        params["from_date"] = from_date
    if to_date:
        conditions += " AND fw.posting_date <= %(to_date)s"
        params["to_date"] = to_date
    if item_code:
        conditions += " AND fw.item_code = %(item_code)s"
        params["item_code"] = item_code
    if production_plan:
        # Match legacy `Production Plan` link OR new `Production Planning` link.
        # Legacy values take priority implicitly (same SQL row is returned either way).
        conditions += (
            " AND (fw.production_plan = %(production_plan)s"
            " OR fw.production_planning = %(production_plan)s)"
        )
        params["production_plan"] = production_plan
    if category_name:
        cat_items = frappe.db.sql(
            """SELECT name FROM `tabItem` WHERE custom_category_name = %(cat)s""",
            {"cat": category_name},
            as_dict=True,
        )
        cat_item_codes = [r.name for r in cat_items]
        if cat_item_codes:
            conditions += " AND fw.item_code IN %(cat_items)s"
            params["cat_items"] = cat_item_codes
        else:
            # No legacy items match this category — that only rules out the
            # old Finish Weight rows, not the new Job Card block below, so
            # don't return early here.
            conditions += " AND 1=0"

    rows = frappe.db.sql(
        f"""
		SELECT
			fw.name AS finish_weight_id,
			fw.bend_material_weight,
			fw.item_code
		FROM `tabFinish Weight` fw
		WHERE {conditions}
		ORDER BY fw.posting_date DESC, fw.name DESC
		""",
        params,
        as_dict=True,
    )

    all_item_codes_bend = set(r.item_code for r in rows if r.item_code)
    category_map_bend = {}
    if all_item_codes_bend:
        item_cat_rows = frappe.db.sql(
            """SELECT name, custom_category_name FROM `tabItem` WHERE name IN %(items)s""",
            {"items": list(all_item_codes_bend)},
            as_dict=True,
        )
        for ir in item_cat_rows:
            category_map_bend[ir.name] = ir.custom_category_name or ""

    result_rows = []
    for r in rows:
        result_rows.append(
            {
                "bend_material_weight": flt(r.bend_material_weight),
                "item_code": r.item_code,
                "id": r.finish_weight_id,
                "id_doctype": "Finish Weight",
                "category_name": category_map_bend.get(r.item_code or "", ""),
            }
        )

    # ── NEW SOURCE: Job Card (linked via Work Order) ────────────────
    # Finish Weight above stays exactly as it was (old data must remain
    # visible). This block adds rows sourced from the new Job Card flow
    # (custom_bend_material_weight), item code taken from the linked Work
    # Order's production_item.
    # A Work Order only counts as real production once there's a submitted
    # Manufacture Stock Entry actually linked to it — submitted or cancelled
    # Work Orders are both eligible, but only when that linkage exists.
    jc_conditions = (
        "jc.docstatus = 1 AND jc.custom_rolled_production = 1"
        " AND wo.docstatus IN (1, 2)"
        " AND EXISTS ("
        "   SELECT 1 FROM `tabStock Entry` wose"
        "   WHERE wose.work_order = wo.name"
        "     AND wose.stock_entry_type = 'Manufacture'"
        "     AND wose.docstatus = 1"
        " )"
    )
    jc_params = {}

    if from_date:
        jc_conditions += " AND DATE(wo.actual_start_date) >= %(from_date)s"
        jc_params["from_date"] = from_date
    if to_date:
        jc_conditions += " AND DATE(wo.actual_start_date) <= %(to_date)s"
        jc_params["to_date"] = to_date
    if item_code:
        jc_conditions += " AND wo.production_item = %(item_code)s"
        jc_params["item_code"] = item_code
    if production_plan:
        jc_conditions += (
            " AND (wo.name = %(production_plan)s OR wo.production_plan = %(production_plan)s)"
        )
        jc_params["production_plan"] = production_plan
    if category_name:
        cat_items_jc = frappe.db.sql(
            """SELECT name FROM `tabItem` WHERE custom_category_name = %(cat)s""",
            {"cat": category_name},
            as_dict=True,
        )
        cat_item_codes_jc = [r.name for r in cat_items_jc]
        if cat_item_codes_jc:
            jc_conditions += " AND wo.production_item IN %(jc_cat_items)s"
            jc_params["jc_cat_items"] = cat_item_codes_jc
        else:
            jc_conditions += " AND 1=0"

    job_card_bend_data = frappe.db.sql(
        f"""
		SELECT
			jc.name                  AS job_card_id,
			wo.production_item       AS item_code,
			jc.custom_bend_material_weight AS bend_material_weight
		FROM `tabJob Card` jc
		INNER JOIN `tabWork Order` wo ON wo.name = jc.work_order
		WHERE {jc_conditions}
		ORDER BY wo.actual_start_date DESC, jc.name DESC
		""",
        jc_params,
        as_dict=True,
    )

    if job_card_bend_data:
        extra_item_codes_bend = {
            r.item_code for r in job_card_bend_data if r.item_code
        } - set(category_map_bend.keys())
        if extra_item_codes_bend:
            extra_item_cat_rows = frappe.db.sql(
                """SELECT name, custom_category_name FROM `tabItem` WHERE name IN %(items)s""",
                {"items": list(extra_item_codes_bend)},
                as_dict=True,
            )
            for ir in extra_item_cat_rows:
                category_map_bend[ir.name] = ir.custom_category_name or ""

        for r in job_card_bend_data:
            result_rows.append(
                {
                    "bend_material_weight": flt(r.bend_material_weight),
                    "item_code": r.item_code,
                    "id": r.job_card_id,
                    "id_doctype": "Job Card",
                    "category_name": category_map_bend.get(r.item_code or "", ""),
                }
            )

    return {
        "rows": result_rows,
        "totals": {},
    }


@frappe.whitelist()
def get_coal_consumption_data(
    from_date=None,
    to_date=None,
    item_code=None,
    production_plan=None,
    machine_name=None,
    category_name=None,
) -> dict:
    """
    Fetch Coal Consumption for the Production Dashboard.

    Source: submitted Stock Entry of type Material Issue, for items in the
    Item Group "Coal", excluding the item "Coal Feeding".

    Columns: Date, Item, Qty, UOM.
    """
    if not frappe.has_permission("Stock Entry", "read"):
        frappe.throw(_("Not permitted to access coal consumption data."), frappe.PermissionError)

    conditions = (
        "se.docstatus = 1"
        " AND se.stock_entry_type = 'Material Issue'"
        " AND i.item_group = 'Coal'"
        " AND sed.item_code != 'Coal Feeding'"
    )
    params = {}

    if from_date:
        conditions += " AND se.posting_date >= %(from_date)s"
        params["from_date"] = from_date
    if to_date:
        conditions += " AND se.posting_date <= %(to_date)s"
        params["to_date"] = to_date
    if item_code:
        conditions += " AND sed.item_code = %(item_code)s"
        params["item_code"] = item_code

    rows = frappe.db.sql(
        f"""
		SELECT
			se.posting_date AS date,
			sed.item_code AS item,
			sed.qty AS qty,
			sed.uom AS uom
		FROM `tabStock Entry` se
		INNER JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
		INNER JOIN `tabItem` i ON i.name = sed.item_code
		WHERE {conditions}
		ORDER BY se.posting_date DESC, se.name DESC, sed.idx ASC
		""",
        params,
        as_dict=True,
    )

    result_rows = []
    total_qty = 0.0
    for r in rows:
        qty = flt(r.qty)
        total_qty += qty
        result_rows.append(
            {
                "date": r.date,
                "item": r.item,
                "qty": qty,
                "uom": r.uom or "",
            }
        )

    return {
        "rows": result_rows,
        "totals": {"total_qty": flt(total_qty)},
    }


def _format_month_label(month_key: str) -> str:
    """Convert a 'YYYY-MM' key into a 'Mon-YYYY' label, e.g. '2025-04' -> 'Apr-2025'."""
    try:
        year, month = month_key.split("-")
        return _date(int(year), int(month), 1).strftime("%b-%Y")
    except Exception:
        return month_key


def _fiscal_sort_key(month_key: str):
    """Sort key for a 'YYYY-MM' key so months run April → March within each
    fiscal year (Apr-2025, May-2025, ..., Mar-2026, Apr-2026, ...)."""
    year, month = (int(p) for p in month_key.split("-"))
    fiscal_year = year if month >= 4 else year - 1
    fiscal_month_index = (month - 4) % 12
    return (fiscal_year, fiscal_month_index)


@frappe.whitelist()
def get_monthly_production_with_coal_consumption_data(
    from_date=None,
    to_date=None,
    item_code=None,
    production_plan=None,
    machine_name=None,
    category_name=None,
) -> dict:
    """
    Month-wise Total Production vs Total Coal Consumption for the Production
    Dashboard, with the derived Per Ton Coal Consumption (In KG).

    Sources:
      - Rolled Production (Total Production) via get_rolled_production_data
      - Coal Consumption (Total Coal Consumption) via get_coal_consumption_data

    Per Ton Coal Consumption (In KG) = (Total Coal Consumption / Total Production) * 1000
    """
    production_data = get_rolled_production_data(from_date=from_date, to_date=to_date)
    coal_data = get_coal_consumption_data(from_date=from_date, to_date=to_date)

    production_by_month: dict[str, float] = {}
    for row in production_data.get("rows", []):
        prod_date = row.get("production_date")
        if not prod_date:
            continue
        month_key = str(prod_date)[:7]
        production_by_month[month_key] = production_by_month.get(month_key, 0.0) + flt(
            row.get("actual_qty")
        )

    coal_by_month: dict[str, float] = {}
    for row in coal_data.get("rows", []):
        coal_date = row.get("date")
        if not coal_date:
            continue
        month_key = str(coal_date)[:7]
        coal_by_month[month_key] = coal_by_month.get(month_key, 0.0) + flt(row.get("qty"))

    month_keys = sorted(set(production_by_month.keys()) | set(coal_by_month.keys()), key=_fiscal_sort_key)

    rows = []
    total_production_overall = 0.0
    total_coal_overall = 0.0
    for month_key in month_keys:
        month_production = flt(production_by_month.get(month_key, 0.0))
        month_coal = flt(coal_by_month.get(month_key, 0.0))
        per_ton_coal = flt((month_coal / month_production) * 1000, 2) if month_production else 0.0

        total_production_overall += month_production
        total_coal_overall += month_coal

        rows.append(
            {
                "month": _format_month_label(month_key),
                "total_production": month_production,
                "total_coal_consumption": month_coal,
                "per_ton_coal_consumption": per_ton_coal,
            }
        )

    overall_per_ton = (
        flt((total_coal_overall / total_production_overall) * 1000, 2)
        if total_production_overall
        else 0.0
    )

    return {
        "rows": rows,
        "totals": {
            "total_production": flt(total_production_overall),
            "total_coal_consumption": flt(total_coal_overall),
            "per_ton_coal_consumption": overall_per_ton,
        },
    }


# Cutting Category master names carry a "@<rate>" suffix (e.g. "Half_Cutting@50")
# that changes whenever the rate changes, so buckets are matched by prefix
# rather than an exact name. The RM+NG variant is checked first because its
# name also starts with "Finish_Cutting".
_CUTTING_CATEGORY_BUCKETS = (
    ("Finish_Cutting(RM+NG)", "fcn"),
    ("Finish_Cutting", "fc"),
    ("Half_Cutting", "hf"),
    ("General_Cutting", "gc"),
)

_CUTTING_CATEGORY_BUCKET_KEYS = ("fc", "hf", "gc", "fcn")


def _classify_cutting_category(category_name: str):
    """Map a Cutting Category master name to one of the four billet-cutting
    buckets shown on the dashboard ('fc' / 'hf' / 'gc' / 'fcn'), or None."""
    if not category_name:
        return None
    for prefix, bucket in _CUTTING_CATEGORY_BUCKETS:
        if category_name.startswith(prefix):
            return bucket
    return None


def _empty_billet_cutting_month_totals() -> dict:
    totals = {"total_qty": 0.0, "total_amount": 0.0}
    for bucket in _CUTTING_CATEGORY_BUCKET_KEYS:
        totals[f"{bucket}_qty"] = 0.0
        totals[f"{bucket}_amount"] = 0.0
    return totals


@frappe.whitelist()
def get_billet_cutting_amount_data(
    from_date=None,
    to_date=None,
    item_code=None,
    production_plan=None,
    machine_name=None,
    category_name=None,
) -> dict:
    """
    Month-wise Billet Cutting Qty/Amount for the Production Dashboard's
    "Monthly Billet Cutting Amount" tab, split by Cutting Category — Full
    Cutting (FC), Half Cutting (HF), General Cutting (GC), Full Cutting-NG
    (FC-N) — each with its own Qty and Amount.

    Source: submitted Billet Cutting Rate Calculation rows, dated by their
    linked Work Order's Actual Start Date (same date source used for Rolled
    Production, so this tab lines up month-for-month with that one).

    Qty ← billet_weight, Amount ← amount.
    """
    if not frappe.has_permission("Billet Cutting Rate Calculation", "read"):
        frappe.throw(
            _("Not permitted to access billet cutting amount data."), frappe.PermissionError
        )

    conditions = "bcrc.docstatus = 1"
    params = {}
    if from_date:
        conditions += " AND DATE(wo.actual_start_date) >= %(from_date)s"
        params["from_date"] = from_date
    if to_date:
        conditions += " AND DATE(wo.actual_start_date) <= %(to_date)s"
        params["to_date"] = to_date

    rows = frappe.db.sql(
        f"""
		SELECT
			DATE(wo.actual_start_date) AS production_date,
			bcrc.cutting_category       AS cutting_category,
			bcrc.billet_weight          AS qty,
			bcrc.amount                 AS amount
		FROM `tabBillet Cutting Rate Calculation` bcrc
		INNER JOIN `tabWork Order` wo ON wo.name = bcrc.work_order
		WHERE {conditions}
		""",
        params,
        as_dict=True,
    )

    by_month: dict[str, dict] = {}
    for row in rows:
        if not row.production_date:
            continue
        month_key = str(row.production_date)[:7]
        month_totals = by_month.setdefault(month_key, _empty_billet_cutting_month_totals())

        qty = flt(row.qty)
        amount = flt(row.amount)
        bucket = _classify_cutting_category(row.cutting_category)
        if bucket:
            month_totals[f"{bucket}_qty"] += qty
            month_totals[f"{bucket}_amount"] += amount
        month_totals["total_qty"] += qty
        month_totals["total_amount"] += amount

    month_keys = sorted(by_month.keys(), key=_fiscal_sort_key)

    rows_out = []
    grand_totals = _empty_billet_cutting_month_totals()
    for month_key in month_keys:
        month_totals = by_month[month_key]
        row_out = {"month": _format_month_label(month_key)}
        for key, value in month_totals.items():
            row_out[key] = flt(value, 2)
            grand_totals[key] += value
        rows_out.append(row_out)

    for key in grand_totals:
        grand_totals[key] = flt(grand_totals[key], 2)

    return {"rows": rows_out, "totals": grand_totals}


def _parse_production_date(value):
    """Coerce SQL DATE / datetime / string into a datetime.date."""
    if value is None:
        return None
    if isinstance(value, _date):
        return value
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            pass
    try:
        return _date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def _week_monday(d: _date) -> _date:
    """Return the Monday that starts the ISO week containing ``d``."""
    return d - timedelta(days=d.weekday())


def _format_week_day_label(d: _date) -> str:
    """e.g. date(2025, 3, 31) → 'Monday - 31/03/2025'."""
    return d.strftime("%A - %d/%m/%Y")


@frappe.whitelist()
def get_weekly_billet_cutting_amount_data(
    from_date=None,
    to_date=None,
    item_code=None,
    production_plan=None,
    machine_name=None,
    category_name=None,
) -> dict:
    """
    Week-wise Billet Cutting Qty/Amount for the Production Dashboard's
    "Weekly Billet Cutting Amount" tab.

    Same Cutting Category buckets and Qty/Amount fields as the monthly tab,
    but rows are Monday→Sunday weeks. First columns are Weeks from / Weeks to
    (e.g. 'Monday - 31/03/2025' / 'Sunday - 06/04/2025').

    Source: submitted Billet Cutting Rate Calculation rows, dated by their
    linked Work Order's Actual Start Date.

    Qty ← billet_weight, Amount ← amount.
    """
    if not frappe.has_permission("Billet Cutting Rate Calculation", "read"):
        frappe.throw(
            _("Not permitted to access weekly billet cutting amount data."),
            frappe.PermissionError,
        )

    conditions = "bcrc.docstatus = 1"
    params = {}
    if from_date:
        conditions += " AND DATE(wo.actual_start_date) >= %(from_date)s"
        params["from_date"] = from_date
    if to_date:
        conditions += " AND DATE(wo.actual_start_date) <= %(to_date)s"
        params["to_date"] = to_date

    rows = frappe.db.sql(
        f"""
		SELECT
			DATE(wo.actual_start_date) AS production_date,
			bcrc.cutting_category       AS cutting_category,
			bcrc.billet_weight          AS qty,
			bcrc.amount                 AS amount
		FROM `tabBillet Cutting Rate Calculation` bcrc
		INNER JOIN `tabWork Order` wo ON wo.name = bcrc.work_order
		WHERE {conditions}
		""",
        params,
        as_dict=True,
    )

    by_week: dict[str, dict] = {}
    for row in rows:
        prod_date = _parse_production_date(row.production_date)
        if not prod_date:
            continue
        monday = _week_monday(prod_date)
        week_key = monday.isoformat()
        week_totals = by_week.setdefault(week_key, _empty_billet_cutting_month_totals())

        qty = flt(row.qty)
        amount = flt(row.amount)
        bucket = _classify_cutting_category(row.cutting_category)
        if bucket:
            week_totals[f"{bucket}_qty"] += qty
            week_totals[f"{bucket}_amount"] += amount
        week_totals["total_qty"] += qty
        week_totals["total_amount"] += amount

    week_keys = sorted(by_week.keys())

    rows_out = []
    grand_totals = _empty_billet_cutting_month_totals()
    for week_key in week_keys:
        monday = _date.fromisoformat(week_key)
        sunday = monday + timedelta(days=6)
        week_totals = by_week[week_key]
        row_out = {
            "weeks_from": _format_week_day_label(monday),
            "weeks_to": _format_week_day_label(sunday),
            "week_start": week_key,
            "week_end": sunday.isoformat(),
        }
        for key, value in week_totals.items():
            row_out[key] = flt(value, 2)
            grand_totals[key] += value
        rows_out.append(row_out)

    for key in grand_totals:
        grand_totals[key] = flt(grand_totals[key], 2)

    return {"rows": rows_out, "totals": grand_totals}


def _time_value_to_seconds(value) -> int:
    """Convert a Time / timedelta / HH:MM:SS string to seconds since midnight (seconds ignored)."""
    if value is None or value == "":
        return 0
    if isinstance(value, timedelta):
        total_minutes = int(value.total_seconds()) // 60
        return total_minutes * 60
    if hasattr(value, "hour"):
        return value.hour * 3600 + value.minute * 60
    parts = str(value).split(":")
    if len(parts) >= 2:
        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            return hours * 3600 + minutes * 60
        except (TypeError, ValueError):
            return 0
    return 0


def _interval_seconds(time_from, time_to) -> tuple[int, int]:
    """Return (start, end) in seconds; add 24h when the window crosses midnight."""
    start = _time_value_to_seconds(time_from)
    end = _time_value_to_seconds(time_to)
    if end < start:
        end += 86400
    return start, end


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping/adjacent intervals."""
    if not intervals:
        return []
    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_intervals[0]]
    for start, end in sorted_intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _merged_hours_from_intervals(intervals: list[tuple[int, int]]) -> float:
    merged = _merge_intervals(intervals)
    total_seconds = sum(end - start for start, end in merged)
    return flt(total_seconds / 3600.0, 2)


@frappe.whitelist()
def get_hourly_production_data(
    from_date=None,
    to_date=None,
    item_code=None,
    production_plan=None,
    machine_name=None,
    category_name=None,
) -> dict:
    """
    Fetch date-wise production hours for the Hourly Production dashboard tab.

    Hours are deduplicated per date: overlapping time windows on the same date
    count once (e.g. three 07:00–08:00 entries on one date = 1 hour, not 3).

    Sources:
      - submitted Hourly Production (time_from / time_to)
      - submitted Job Card Time Log on rolled Work Orders (from_time / to_time)
    """
    if not frappe.has_permission("Hourly Production", "read"):
        frappe.throw(_("Not permitted to access hourly production data."), frappe.PermissionError)

    intervals_by_date: dict[str, list[tuple[int, int]]] = {}

    def add_interval(production_date, time_from, time_to):
        if not production_date or time_from is None or time_to is None:
            return
        date_key = str(production_date)
        intervals_by_date.setdefault(date_key, []).append(_interval_seconds(time_from, time_to))

    # ── Legacy: Hourly Production ───────────────────────────────────
    hp_conditions = "hp.docstatus = 1"
    hp_params: dict = {}

    if from_date:
        hp_conditions += " AND hp.production_date >= %(from_date)s"
        hp_params["from_date"] = from_date
    if to_date:
        hp_conditions += " AND hp.production_date <= %(to_date)s"
        hp_params["to_date"] = to_date
    if item_code:
        hp_conditions += " AND hp.finish_item = %(item_code)s"
        hp_params["item_code"] = item_code
    if production_plan:
        hp_conditions += (
            " AND (hp.production_plan = %(production_plan)s"
            " OR hp.production_planning = %(production_plan)s"
            " OR hp.billet_cutting_id = %(production_plan)s)"
        )
        hp_params["production_plan"] = production_plan
    if category_name:
        hp_conditions += (
            " AND EXISTS ("
            "   SELECT 1 FROM `tabItem` i"
            "   WHERE i.name = hp.finish_item"
            "     AND i.custom_category_name = %(category_name)s"
            " )"
        )
        hp_params["category_name"] = category_name

    hourly_rows = frappe.db.sql(
        f"""
        SELECT
            hp.production_date,
            hp.time_from,
            hp.time_to
        FROM `tabHourly Production` hp
        WHERE {hp_conditions}
        ORDER BY hp.production_date DESC
        """,
        hp_params,
        as_dict=True,
    )
    for row in hourly_rows:
        add_interval(row.production_date, row.time_from, row.time_to)

    # ── New flow: Job Card Time Log on rolled Work Orders ───────────
    jc_conditions = (
        "jc.docstatus = 1"
        " AND wo.custom_rolled_production = 1"
        " AND jctl.from_time IS NOT NULL"
        " AND jctl.to_time IS NOT NULL"
    )
    jc_params: dict = {}

    if from_date:
        jc_conditions += " AND DATE(jctl.from_time) >= %(from_date)s"
        jc_params["from_date"] = from_date
    if to_date:
        jc_conditions += " AND DATE(jctl.from_time) <= %(to_date)s"
        jc_params["to_date"] = to_date
    if item_code:
        jc_conditions += " AND wo.production_item = %(item_code)s"
        jc_params["item_code"] = item_code
    if production_plan:
        jc_conditions += (
            " AND (wo.name = %(production_plan)s OR wo.production_plan = %(production_plan)s)"
        )
        jc_params["production_plan"] = production_plan
    if category_name:
        jc_conditions += (
            " AND EXISTS ("
            "   SELECT 1 FROM `tabItem` i"
            "   WHERE i.name = wo.production_item"
            "     AND i.custom_category_name = %(category_name)s"
            " )"
        )
        jc_params["category_name"] = category_name

    job_card_rows = frappe.db.sql(
        f"""
        SELECT
            DATE(jctl.from_time) AS production_date,
            TIME(jctl.from_time) AS time_from,
            TIME(jctl.to_time)   AS time_to
        FROM `tabJob Card Time Log` jctl
        INNER JOIN `tabJob Card` jc ON jc.name = jctl.parent
        INNER JOIN `tabWork Order` wo ON wo.name = jc.work_order
        WHERE {jc_conditions}
        ORDER BY DATE(jctl.from_time) DESC
        """,
        jc_params,
        as_dict=True,
    )
    for row in job_card_rows:
        add_interval(row.production_date, row.time_from, row.time_to)

    result_rows = []
    total_hours = 0.0
    for date_key in sorted(intervals_by_date.keys(), reverse=True):
        hours = _merged_hours_from_intervals(intervals_by_date[date_key])
        total_hours += hours
        result_rows.append({"date": date_key, "hours": hours})

    return {
        "rows": result_rows,
        "totals": {"total_hours": flt(total_hours, 2)},
    }


def _fmt_date(date_val) -> str:
    """Return a Python date object so Excel treats the cell as a real date."""
    if not date_val:
        return ""
    try:
        if isinstance(date_val, _date):
            return date_val
        parts = str(date_val).split("-")
        if len(parts) == 3:
            return _date(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        pass
    return str(date_val)


# ── Per-tab column definitions: key, label, extractor ──────────────────────
_ROLLED_COLS = [
    {"key": "production_plan",               "label": "Production Plan",               "get": lambda r: r.get("production_plan") or ""},
    {"key": "production_date",               "label": "Production Date",               "get": lambda r: _fmt_date(r.get("production_date"))},
    {"key": "rm",                            "label": "RM",                            "get": lambda r: r.get("rm") or ""},
    {"key": "rm_category_name",              "label": "RM Category Name",              "get": lambda r: r.get("rm_category_name") or ""},
    {"key": "rm_consumption",                "label": "Actual RM Consumption",         "get": lambda r: flt(r.get("rm_consumption"))},
    {"key": "billet_pcs",                    "label": "Total Billet Pcs",              "get": lambda r: flt(r.get("billet_pcs"))},
    {"key": "description_of_cutting_billet", "label": "Description of Cutting Billet", "get": lambda r: r.get("description_of_cutting_billet") or ""},
    {"key": "total_raw_material_pcs",        "label": "Total Raw Material Pcs",        "get": lambda r: flt(r.get("total_raw_material_pcs"))},
    {"key": "total_rm_weight",               "label": "Total RM Weight",               "get": lambda r: flt(r.get("rm_consumption")) + flt(r.get("miss_billet_weight"))},
    {"key": "miss_billet_pcs",               "label": "Miss Billet Pcs",               "get": lambda r: flt(r.get("miss_billet_pcs"))},
    {"key": "miss_billet_weight",            "label": "Miss Billet Weight",            "get": lambda r: flt(r.get("miss_billet_weight"))},
    {"key": "heat_no",                       "label": "Heat No",                       "get": lambda r: r.get("heat_no") or ""},
    {"key": "finished_item",                 "label": "Finished Item",                 "get": lambda r: r.get("finished_item") or ""},
    {"key": "finished_item_category_name",   "label": "Finished Item Category Name",   "get": lambda r: r.get("finished_item_category_name") or ""},
    {"key": "fg_planned_qty",                "label": "FG Planned Qty",                "get": lambda r: flt(r.get("fg_planned_qty"))},
    {"key": "actual_qty",                    "label": "Actual Qty",                    "get": lambda r: flt(r.get("actual_qty"))},
    {"key": "finish_pcs",                    "label": "Finish Pcs",                    "get": lambda r: flt(r.get("finish_pcs"))},
    {"key": "fg_length",                     "label": "FG Length",                     "get": lambda r: r.get("fg_length") or ""},
    {"key": "total_miss_roll_pcs",           "label": "Total Miss Roll (Pcs)",         "get": lambda r: flt(r.get("total_miss_roll_pcs"))},
    {"key": "total_miss_roll_weight",        "label": "Total Miss Roll Weight",        "get": lambda r: flt(r.get("total_miss_roll_weight"))},
    {"key": "total_miss_ingot_pcs",          "label": "Total Miss Ingot",              "get": lambda r: flt(r.get("total_miss_ingot_pcs"))},
    {"key": "total_miss_ingot_weight",       "label": "Total Miss Ingot / Billet Weight", "get": lambda r: flt(r.get("total_miss_ingot_weight"))},
    {"key": "melting_weight",                "label": "Melting Weight",                "get": lambda r: flt(r.get("melting_weight"))},
    {"key": "burning_loss",                  "label": "Wastage %",                     "get": lambda r: flt(r.get("burning_loss"))},
    {"key": "melting_wastage",               "label": "Melting Wastage %",             "get": lambda r: flt(r.get("melting_wastage"))},
    {"key": "finish_goods",                  "label": "Finish Goods %",                "get": lambda r: flt(r.get("finish_goods"))},
    {"key": "total_hr_consumed",             "label": "Total Hr Consumed",             "get": lambda r: flt(r.get("total_hr_consumed"))},
]

_BRIGHT_COLS = [
    {"key": "production_plan",             "label": "Production Plan",             "get": lambda r: r.get("production_plan") or ""},
    {"key": "production_date",             "label": "Production Date",             "get": lambda r: _fmt_date(r.get("production_date"))},
    {"key": "rm",                          "label": "RM",                          "get": lambda r: r.get("rm") or ""},
    {"key": "rm_category_name",            "label": "RM Category Name",            "get": lambda r: r.get("rm_category_name") or ""},
    {"key": "machine_name",                "label": "Machine Name",                "get": lambda r: r.get("machine_name") or ""},
    {"key": "finished_item",               "label": "Finished Item",               "get": lambda r: r.get("finished_item") or ""},
    {"key": "finished_item_category_name", "label": "Finished Item Category Name", "get": lambda r: r.get("finished_item_category_name") or ""},
    {"key": "fg_planned_qty",              "label": "FG Planned Qty",              "get": lambda r: flt(r.get("fg_planned_qty"))},
    {"key": "rm_consumption",              "label": "Actual RM Consumption",       "get": lambda r: flt(r.get("rm_consumption"))},
    {"key": "actual_qty",                  "label": "Actual Qty",                  "get": lambda r: flt(r.get("actual_qty"))},
    {"key": "finish_length",               "label": "Finish Length",               "get": lambda r: r.get("finish_length") or ""},
    {"key": "tolerance",                   "label": "Tolerance",                   "get": lambda r: r.get("tolerance") or ""},
    {"key": "end_cutting_weight",          "label": "End Cutting Weight",          "get": lambda r: flt(r.get("end_cutting_weight"))},
    {"key": "wastage",                     "label": "Wastage %",                   "get": lambda r: flt(r.get("wastage"))},
]

_BEND_COLS = [
    {"key": "id",                   "label": "ID",                   "get": lambda r: r.get("id") or r.get("name") or ""},
    {"key": "item_code",            "label": "Item Code",            "get": lambda r: r.get("item_code") or ""},
    {"key": "category_name",        "label": "Category Name",        "get": lambda r: r.get("category_name") or ""},
    {"key": "bend_material_weight", "label": "Bend Material Weight", "get": lambda r: flt(r.get("bend_material_weight"))},
]

_COAL_COLS = [
    {"key": "date", "label": "Date", "get": lambda r: _fmt_date(r.get("date"))},
    {"key": "item", "label": "Item", "get": lambda r: r.get("item") or ""},
    {"key": "qty",  "label": "Qty",  "get": lambda r: flt(r.get("qty"))},
    {"key": "uom",  "label": "UOM",  "get": lambda r: r.get("uom") or ""},
]

_HOURLY_PRODUCTION_COLS = [
    {"key": "date", "label": "Date", "get": lambda r: _fmt_date(r.get("date"))},
    {"key": "hours", "label": "Hours", "get": lambda r: flt(r.get("hours"))},
]

_MONTHLY_PRODUCTION_COAL_COLS = [
    {"key": "month", "label": "Month", "get": lambda r: r.get("month") or ""},
    {"key": "total_production", "label": "Total Production", "get": lambda r: flt(r.get("total_production"))},
    {
        "key": "total_coal_consumption",
        "label": "Total Coal Consumption",
        "get": lambda r: flt(r.get("total_coal_consumption")),
    },
    {
        "key": "per_ton_coal_consumption",
        "label": "Per Ton Coal Consumption (In KG)",
        "get": lambda r: flt(r.get("per_ton_coal_consumption")),
    },
]

_BILLET_CUTTING_AMOUNT_COLS = [
    {"key": "month", "label": "Month", "get": lambda r: r.get("month") or ""},
    {"key": "fc_qty", "label": "Full Cutting (FC) (MT) — Qty", "get": lambda r: flt(r.get("fc_qty"))},
    {"key": "fc_amount", "label": "Full Cutting (FC) (MT) — Amount", "get": lambda r: flt(r.get("fc_amount"))},
    {"key": "hf_qty", "label": "Half Cutting (HF) (MT) — Qty", "get": lambda r: flt(r.get("hf_qty"))},
    {"key": "hf_amount", "label": "Half Cutting (HF) (MT) — Amount", "get": lambda r: flt(r.get("hf_amount"))},
    {"key": "gc_qty", "label": "General Cutting (GC) (MT) — Qty", "get": lambda r: flt(r.get("gc_qty"))},
    {"key": "gc_amount", "label": "General Cutting (GC) (MT) — Amount", "get": lambda r: flt(r.get("gc_amount"))},
    {
        "key": "fcn_qty",
        "label": "Full Cutting-NG (FC-N) (MT) — Qty",
        "get": lambda r: flt(r.get("fcn_qty")),
    },
    {
        "key": "fcn_amount",
        "label": "Full Cutting-NG (FC-N) (MT) — Amount",
        "get": lambda r: flt(r.get("fcn_amount")),
    },
    {"key": "total_qty", "label": "Total (MT) — Qty", "get": lambda r: flt(r.get("total_qty"))},
    {"key": "total_amount", "label": "Total (MT) — Amount", "get": lambda r: flt(r.get("total_amount"))},
]

_WEEKLY_BILLET_CUTTING_AMOUNT_COLS = [
    {"key": "weeks_from", "label": "Weeks from", "get": lambda r: r.get("weeks_from") or ""},
    {"key": "weeks_to", "label": "Weeks to", "get": lambda r: r.get("weeks_to") or ""},
    {"key": "fc_qty", "label": "Full Cutting (FC) (MT) — Qty", "get": lambda r: flt(r.get("fc_qty"))},
    {"key": "fc_amount", "label": "Full Cutting (FC) (MT) — Amount", "get": lambda r: flt(r.get("fc_amount"))},
    {"key": "hf_qty", "label": "Half Cutting (HF) (MT) — Qty", "get": lambda r: flt(r.get("hf_qty"))},
    {"key": "hf_amount", "label": "Half Cutting (HF) (MT) — Amount", "get": lambda r: flt(r.get("hf_amount"))},
    {"key": "gc_qty", "label": "General Cutting (GC) (MT) — Qty", "get": lambda r: flt(r.get("gc_qty"))},
    {"key": "gc_amount", "label": "General Cutting (GC) (MT) — Amount", "get": lambda r: flt(r.get("gc_amount"))},
    {
        "key": "fcn_qty",
        "label": "Full Cutting-NG (FC-N) (MT) — Qty",
        "get": lambda r: flt(r.get("fcn_qty")),
    },
    {
        "key": "fcn_amount",
        "label": "Full Cutting-NG (FC-N) (MT) — Amount",
        "get": lambda r: flt(r.get("fcn_amount")),
    },
    {"key": "total_qty", "label": "Total (MT) — Qty", "get": lambda r: flt(r.get("total_qty"))},
    {"key": "total_amount", "label": "Total (MT) — Amount", "get": lambda r: flt(r.get("total_amount"))},
]

_TAB_COLS = {
    "rolled_production": _ROLLED_COLS,
    "hourly_production": _HOURLY_PRODUCTION_COLS,
    "bright_production": _BRIGHT_COLS,
    "bend_weight_details": _BEND_COLS,
    "coal_consumption": _COAL_COLS,
    "monthly_production_coal": _MONTHLY_PRODUCTION_COAL_COLS,
    "billet_cutting_amount": _BILLET_CUTTING_AMOUNT_COLS,
    "weekly_billet_cutting_amount": _WEEKLY_BILLET_CUTTING_AMOUNT_COLS,
}


@frappe.whitelist()
def export_production_dashboard(
    tab_id,
    from_date=None,
    to_date=None,
    item_code=None,
    production_plan=None,
    machine_name=None,
    category_name=None,
    selected_columns=None,
) -> dict:
    """
    Build an Excel file (XLSX) for the Production Dashboard tables.
    selected_columns: comma-separated list of column keys; if empty, all columns are included.
    """
    if tab_id == "rolled_production":
        if not frappe.has_permission("Billet Cutting", "report") and not frappe.has_permission("Billet Cutting", "read"):
            frappe.throw(_("Not permitted to export rolled production dashboard."), frappe.PermissionError)
        data = get_rolled_production_data(
            from_date, to_date, item_code, production_plan, machine_name, category_name
        )
    elif tab_id == "bright_production":
        if not frappe.has_permission("Bright Bar Production", "read"):
            frappe.throw(_("Not permitted to export bright production dashboard."), frappe.PermissionError)
        data = get_bright_production_data(
            from_date, to_date, item_code, production_plan, machine_name, category_name
        )
    elif tab_id == "bend_weight_details":
        if not frappe.has_permission("Finish Weight", "read"):
            frappe.throw(_("Not permitted to export bend weight details."), frappe.PermissionError)
        data = get_bend_weight_details(
            from_date, to_date, item_code, production_plan, category_name=category_name
        )
    elif tab_id == "coal_consumption":
        if not frappe.has_permission("Stock Entry", "read"):
            frappe.throw(_("Not permitted to export coal consumption."), frappe.PermissionError)
        data = get_coal_consumption_data(
            from_date, to_date, item_code, production_plan, machine_name, category_name
        )
    elif tab_id == "hourly_production":
        if not frappe.has_permission("Hourly Production", "read"):
            frappe.throw(_("Not permitted to export hourly production."), frappe.PermissionError)
        data = get_hourly_production_data(
            from_date, to_date, item_code, production_plan, machine_name, category_name
        )
    elif tab_id == "monthly_production_coal":
        if not frappe.has_permission("Billet Cutting", "report") and not frappe.has_permission(
            "Billet Cutting", "read"
        ):
            frappe.throw(
                _("Not permitted to export monthly production with coal consumption."),
                frappe.PermissionError,
            )
        data = get_monthly_production_with_coal_consumption_data(from_date, to_date)
    elif tab_id == "billet_cutting_amount":
        if not frappe.has_permission("Billet Cutting Rate Calculation", "read"):
            frappe.throw(
                _("Not permitted to export monthly billet cutting amount."), frappe.PermissionError
            )
        data = get_billet_cutting_amount_data(from_date, to_date)
    elif tab_id == "weekly_billet_cutting_amount":
        if not frappe.has_permission("Billet Cutting Rate Calculation", "read"):
            frappe.throw(
                _("Not permitted to export weekly billet cutting amount."), frappe.PermissionError
            )
        data = get_weekly_billet_cutting_amount_data(from_date, to_date)
    else:
        frappe.throw(_("Invalid tab selected for export."))

    rows = data.get("rows", [])

    # Resolve which columns to include
    all_cols = _TAB_COLS.get(tab_id, [])
    if selected_columns:
        keys = [k.strip() for k in selected_columns.split(",") if k.strip()]
        key_set = set(keys)
        # Preserve original column order
        cols = [c for c in all_cols if c["key"] in key_set]
    else:
        cols = all_cols

    if not cols:
        cols = all_cols

    header = [_(c["label"]) for c in cols]
    data_rows = [[c["get"](r) for c in cols] for r in rows]
    table_data = [header] + data_rows

    file_name = f"{tab_id}_export.xlsx"
    xlsx_file = make_xlsx(table_data, _("Production Dashboard"))

    # Post-process: apply DD-MM-YYYY number format to the Production Date column
    # Find the date column index dynamically (1-indexed for openpyxl)
    date_col_idx = None
    if tab_id in ("rolled_production", "bright_production", "coal_consumption", "hourly_production"):
        date_key = "date" if tab_id in ("coal_consumption", "hourly_production") else "production_date"
        for i, c in enumerate(cols, start=1):
            if c["key"] == date_key:
                date_col_idx = i
                break

    if date_col_idx:
        wb = openpyxl.load_workbook(BytesIO(xlsx_file.getvalue()))
        ws = wb.active
        for row in ws.iter_rows(min_row=2, min_col=date_col_idx, max_col=date_col_idx):
            for cell in row:
                if cell.value:
                    cell.number_format = "DD-MM-YYYY"
        out = BytesIO()
        wb.save(out)
        out.seek(0)
        xlsx_file = out

    frappe.response["filename"] = file_name
    frappe.response["filecontent"] = xlsx_file.getvalue()
    frappe.response["type"] = "binary"
    frappe.response["content_type"] = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
