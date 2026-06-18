// Copyright (c) 2026, beetashoke chakraborty and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bright Bar Production", {
	refresh(frm) {
		if (typeof frm.doc.production_plan === "string" && frm.doc.production_plan) {
			_load_plan_item_options(frm, "mr_items", "raw_material");
			_load_plan_item_options(frm, "po_items", "finished_good");
		}
		if (frm.doc.production_planning) {
			load_options_from_production_planning(frm);
		}
	},

	production_plan(frm) {
		if (typeof frm.doc.production_plan !== "string" || !frm.doc.production_plan) {
			frm.set_df_property("raw_material", "options", "");
			frm.set_df_property("finished_good", "options", "");
			frm.refresh_field("raw_material");
			frm.refresh_field("finished_good");
			return;
		}
		_load_plan_item_options(frm, "mr_items", "raw_material");
		_load_plan_item_options(frm, "po_items", "finished_good");
	},

	production_planning(frm) {
		if (!frm.doc.production_planning) {
			frm.set_df_property("finished", "options", "");
			frm.set_df_property("material", "options", "");
			frm.refresh_field("finished");
			frm.refresh_field("material");
			return;
		}
		load_options_from_production_planning(frm);
	},

	material(frm) {
		update_stock_available_in_warehouse(frm);
	},

	actual_rm_consumption(frm) {
		update_stock_available_in_warehouse(frm);
		update_wastage_per(frm);
	},

	rm_source_warehouse(frm) {
		update_stock_available_in_warehouse(frm);
	},

	fg_weight(frm) {
		update_wastage_per(frm);
	},
});

function _load_plan_item_options(frm, child_table, field_name) {
	if (typeof frm.doc.production_plan !== "string" || !frm.doc.production_plan) {
		frm.set_df_property(field_name, "options", "");
		frm.refresh_field(field_name);
		return;
	}
	frappe.call({
		method: "frappe.client.get",
		args: { doctype: "Production Plan", name: frm.doc.production_plan },
		callback(r) {
			if (!r.message || !r.message[child_table]) return;
			const item_codes = [...new Set(
				r.message[child_table].filter(row => row.item_code).map(row => row.item_code)
			)];
			frm.set_df_property(field_name, "options", item_codes.join("\n"));
			frm.refresh_field(field_name);
		}
	});
}

function load_options_from_production_planning(frm) {
	if (!frm.doc.production_planning) return;
	frappe.call({
		method: "prakash_steel.prakash_steel.doctype.production_planning.production_planning.get_fg_items_for_production_planning",
		args: { production_planning: frm.doc.production_planning },
		callback(r) {
			const rows = (r && r.message) || [];
			const fg_items      = [...new Set(rows.filter(r => r.fg_item).map(r => r.fg_item))];
			const raw_materials = [...new Set(rows.filter(r => r.raw_material).map(r => r.raw_material))];
			frm.set_df_property("finished", "options", "\n" + fg_items.join("\n"));
			frm.set_df_property("material", "options", "\n" + raw_materials.join("\n"));
			frm.refresh_field("finished");
			frm.refresh_field("material");
		}
	});
}

function update_stock_available_in_warehouse(frm) {
	const item_code   = frm.doc.material;
	const warehouse   = frm.doc.rm_source_warehouse;
	const consumption = flt(frm.doc.actual_rm_consumption) || 0;
	const has_consumption_value =
		frm.doc.actual_rm_consumption !== null &&
		frm.doc.actual_rm_consumption !== undefined &&
		frm.doc.actual_rm_consumption !== "";

	if (!item_code || !warehouse || !has_consumption_value) {
		frm.set_value("stock_available_in_warehouse", null);
		return;
	}

	frappe.call({
		method: "prakash_steel.api.get_available_stock.get_available_stock_for_warehouse",
		args: { item_code, warehouse },
		callback(r) {
			const remaining = ((r && r.message) || 0) - consumption;
			frm.set_value("stock_available_in_warehouse", remaining);
			if (remaining < 0) {
				frm.set_value("stock_consumption_status", "Stock Exceeded");
			} else if (remaining === 0) {
				frm.set_value("stock_consumption_status", "All Stock");
			} else {
				frm.set_value("stock_consumption_status", "Stock Left");
			}
		},
	});
}

function update_wastage_per(frm) {
	const fg_weight = flt(frm.doc.fg_weight) || 0;
	const actual_rm = flt(frm.doc.actual_rm_consumption) || 0;

	if (
		frm.doc.fg_weight == null || frm.doc.fg_weight === "" ||
		frm.doc.actual_rm_consumption == null || frm.doc.actual_rm_consumption === "" ||
		actual_rm === 0
	) {
		frm.set_value("wastage_per", null);
		return;
	}

	frm.set_value("wastage_per", Math.abs((fg_weight / actual_rm) * 100 - 100));
}
