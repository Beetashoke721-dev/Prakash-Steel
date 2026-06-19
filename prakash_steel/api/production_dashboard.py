# Copyright (c) 2025, Prakash Steel and contributors
# For license information, please see license.txt

import frappe
from datetime import date as _date
from io import BytesIO

import openpyxl
from frappe import _
from frappe.utils import flt
from frappe.utils.xlsxutils import make_xlsx


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
            return {"rows": [], "totals": {"total_production": 0, "rm_consumption": 0}}

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

    if not billet_cutting_data:
        return {"rows": [], "totals": {"total_production": 0, "rm_consumption": 0}}

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
					SUM(TIME_TO_SEC(TIMEDIFF(hp.time_to, hp.time_from))) / 3600.0 AS total_hours
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

        rm_c = flt(row.rm_consumption)
        miss_bw = flt(row.miss_billet_weight)
        if rm_c > 0:
            burning_loss = flt(
                ((rm_c + miss_bw - flt(actual_qty) - flt(total_miss_ingot_weight)) / rm_c)
                * 100,
                2,
            )
        else:
            burning_loss = 0.0

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
                "burning_loss": flt(burning_loss, 2),
                "rm_category_name": category_map_rolled.get(row.rm or "", ""),
                "finished_item_category_name": category_map_rolled.get(fi, ""),
            }
        )

    # Dashboard Burning Loss % = ((RM + Miss Billet - Production - Miss Ingot) / RM) × 100
    burning_loss_per_total = 0.0
    if total_rm_consumption > 0:
        burning_loss_per_total = flt(
            (
                (
                    total_rm_consumption
                    + total_miss_billet_weight_overall
                    - total_production
                    - total_miss_ingot_weight_overall
                )
                / total_rm_consumption
            )
            * 100,
            2,
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
            return {"rows": [], "totals": {"total_production": 0, "rm_consumption": 0}}

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

    if not bright_data:
        return {"rows": [], "totals": {"total_production": 0, "rm_consumption": 0}}

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

    # ── 2.b  Batch-fetch custom_category_name from Item ──────────────
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

        rm_consumption = flt(row.rm_consumption)
        actual_qty = flt(row.actual_qty)
        fg_weight = flt(row.fg_weight)

        total_production += actual_qty
        total_rm_consumption += rm_consumption
        total_fg_weight += fg_weight
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

    # Average Wastage % for KPI card
    avg_wastage_per = 0.0
    wastage_values = [
        flt(row.get("wastage", 0))
        for row in bright_data
        if row.get("wastage") is not None
    ]
    if wastage_values:
        avg_wastage_per = sum(wastage_values) / len(wastage_values)

    return {
        "rows": rows,
        "totals": {
            "total_production": flt(total_production),
            "rm_consumption": flt(total_rm_consumption),
            "total_fg_weight": flt(total_fg_weight),
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
            return {"rows": [], "totals": {}}

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
                "category_name": category_map_bend.get(r.item_code or "", ""),
            }
        )

    return {
        "rows": result_rows,
        "totals": {},
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
    {"key": "burning_loss",                  "label": "Burning Loss %",                "get": lambda r: flt(r.get("burning_loss"))},
    {"key": "total_hr_consumed",             "label": "Total Hr Consumed",             "get": lambda r: flt(r.get("total_hr_consumed"))},
]

_BRIGHT_COLS = [
    {"key": "production_plan",             "label": "Production Plan",             "get": lambda r: r.get("production_plan") or ""},
    {"key": "production_date",             "label": "Production Date",             "get": lambda r: _fmt_date(r.get("production_date"))},
    {"key": "rm",                          "label": "RM",                          "get": lambda r: r.get("rm") or ""},
    {"key": "rm_category_name",            "label": "RM Category Name",            "get": lambda r: r.get("rm_category_name") or ""},
    {"key": "rm_consumption",              "label": "Actual RM Consumption",       "get": lambda r: flt(r.get("rm_consumption"))},
    {"key": "machine_name",                "label": "Machine Name",                "get": lambda r: r.get("machine_name") or ""},
    {"key": "finished_item",               "label": "Finished Item",               "get": lambda r: r.get("finished_item") or ""},
    {"key": "finished_item_category_name", "label": "Finished Item Category Name", "get": lambda r: r.get("finished_item_category_name") or ""},
    {"key": "fg_planned_qty",              "label": "FG Planned Qty",              "get": lambda r: flt(r.get("fg_planned_qty"))},
    {"key": "actual_qty",                  "label": "Actual Qty",                  "get": lambda r: flt(r.get("actual_qty"))},
    {"key": "finish_length",               "label": "Finish Length",               "get": lambda r: r.get("finish_length") or ""},
    {"key": "tolerance",                   "label": "Tolerance",                   "get": lambda r: r.get("tolerance") or ""},
    {"key": "melting_weight",              "label": "Melting Weight",              "get": lambda r: flt(r.get("fg_weight"))},
    {"key": "wastage",                     "label": "Wastage %",                   "get": lambda r: flt(r.get("wastage"))},
]

_BEND_COLS = [
    {"key": "id",                   "label": "ID",                   "get": lambda r: r.get("id") or r.get("name") or ""},
    {"key": "item_code",            "label": "Item Code",            "get": lambda r: r.get("item_code") or ""},
    {"key": "category_name",        "label": "Category Name",        "get": lambda r: r.get("category_name") or ""},
    {"key": "bend_material_weight", "label": "Bend Material Weight", "get": lambda r: flt(r.get("bend_material_weight"))},
]

_TAB_COLS = {
    "rolled_production": _ROLLED_COLS,
    "bright_production": _BRIGHT_COLS,
    "bend_weight_details": _BEND_COLS,
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
    if tab_id in ("rolled_production", "bright_production"):
        for i, c in enumerate(cols, start=1):
            if c["key"] == "production_date":
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
