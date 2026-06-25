frappe.ui.form.on("Item", {
    refresh: function (frm) {
        toggle_fields_visibility(frm);
        toggle_group_for_sub_assemblies_visibility(frm);
        toggle_buffer_fields_visibility(frm);
        update_decoupled_lead_time(frm);
        calculate_sku_type(frm);
        handle_min_order_qty_batch_size_exclusivity(frm);

        // Recalculate ADU on form load so Item ADU always matches current Sales Invoices + ADU Horizon
        // refresh_item_adu(frm);
    },

    custom_store_item: function (frm) {
        toggle_fields_visibility(frm);
        toggle_group_for_sub_assemblies_visibility(frm);
    },

    custom_item_size: function (frm) {
        generate_item_code_and_name(frm);
    },

    custom_shape: function (frm) {
        generate_item_code_and_name(frm);
    },

    custom_grade: function (frm) {
        generate_item_code_and_name(frm);
    },

    custom_category_name: function (frm) {
        generate_item_code_and_name(frm);
    },

    item_group: function (frm) {
        toggle_group_for_sub_assemblies_visibility(frm);
    },

    lead_time_days: function (frm) {
        setTimeout(function () {
            update_decoupled_lead_time(frm, true);
        }, 100);
    },

    custom_buffer_flag: function (frm) {
        toggle_buffer_fields_visibility(frm);

        if (frm.doc.custom_buffer_flag !== 'Buffer') {
            frm.set_value('safety_stock', null);
            frm.set_value('custom_top_of_red', null);
            frm.set_value('custom_top_of_yellow', null);
        } else {
            if (frm.doc.safety_stock !== null && frm.doc.safety_stock !== undefined && frm.doc.safety_stock <= 0) {
                frm.set_value('safety_stock', null);
                frm.set_value('custom_top_of_red', null);
                frm.set_value('custom_top_of_yellow', null);
            }
        }

        calculate_sku_type(frm);
    },

    safety_stock: function (frm) {
        calculate_buffer_fields(frm);
    },

    custom_item_type: function (frm) {
        toggle_buffer_fields_visibility(frm);
        calculate_sku_type(frm);
    },

    validate: function (frm) {
        if (frm.doc.custom_buffer_flag === 'Buffer' && frm.doc.custom_item_type !== 'CS') {
            const safety_stock = frm.doc.safety_stock;

            if (safety_stock === null || safety_stock === undefined || safety_stock === '' || safety_stock <= 0) {
                frappe.throw({
                    title: __('Validation Error'),
                    indicator: 'red',
                    message: __('Safety Stock is required and must be greater than 0 when Buffer Flag is set to Buffer.')
                });
            }
        }

        if (frm.doc.custom_buffer_flag === 'Buffer' && frm.doc.custom_item_type === 'CS') {
            const tog_rows = frm.doc.custom_cs_tog_table || [];

            if (tog_rows.length === 0) {
                frappe.throw({
                    title: __('Validation Error'),
                    indicator: 'red',
                    message: __('CS Tog Table must have at least one row with Top Of Green when Buffer Flag is Buffer and Item Type is CS.')
                });
            }

            for (let i = 0; i < tog_rows.length; i++) {
                const row = tog_rows[i];
                if (!row.top_of_green || row.top_of_green <= 0) {
                    frappe.throw({
                        title: __('Validation Error'),
                        indicator: 'red',
                        message: __(`Row ${i + 1} in CS Tog Table: Top Of Green is required and must be greater than 0.`)
                    });
                }
            }
        }

        const min_order_qty = parseFloat(frm.doc.min_order_qty) || 0;
        const custom_batch_size = parseInt(frm.doc.custom_batch_size) || 0;

        if (min_order_qty > 0 && custom_batch_size > 0) {
            frappe.throw({
                title: __('Validation Error'),
                indicator: 'red',
                message: __('Min Order Qty and Batch Size cannot both have values greater than 0. Please set one field to 0 before setting the other.')
            });
        }
    },

    min_order_qty: function (frm) {
        handle_min_order_qty_batch_size_exclusivity(frm);
    },

    custom_batch_size: function (frm) {
        handle_min_order_qty_batch_size_exclusivity(frm);
    },

    after_save: function (frm) {
        const normalized = (frm.doc.item_group || '').trim().toLowerCase();
        const groupsRequiringBOM = new Set([
            'sub assemblies',
            'sub assembly',
            'finished goods',
            'finished good'
        ]);

        if (groupsRequiringBOM.has(normalized)) {
            frappe.call({
                method: "prakash_steel.api.check_item_has_bom.check_item_has_bom",
                args: {
                    item_code: frm.doc.item_code
                },
                callback: function (r) {
                    if (r.message === false) {
                        frappe.msgprint({
                            title: 'Action Required',
                            message: 'Please create a BOM for this item.',
                            indicator: 'green'
                        });
                    }
                },
                error: function () {
                    frappe.msgprint({
                        title: 'Action Required',
                        message: 'Please create a BOM for this item.',
                        indicator: 'green'
                    });
                }
            });
        }
    }

});

function toggle_fields_visibility(frm) {
    const fields_to_hide = [
        'custom_category_name',
        'custom_item_size',
        'custom_grade',
        'custom_shape',
        'custom_mto_or_mta',
        'custom_item_group_batch_qty',
        'custom_item_sub_group_batch_',
        'custom_box',
        'custom_desc_code',
        'custom_mqp',
        'custom_per_hour_production_qty',
        'custom_group_for_sub_assemblies',
        'custom_item_sub_group_batch_qty'
    ];

    const is_store_item = frm.doc.custom_store_item || 0;

    fields_to_hide.forEach(function (fieldname) {
        if (frm.fields_dict[fieldname]) {
            if (is_store_item) {
                frm.set_df_property(fieldname, 'hidden', 1);
            } else {
                frm.set_df_property(fieldname, 'hidden', 0);
            }
        }
    });
}

function generate_item_code_and_name(frm) {
    if (frm.doc.custom_store_item) {
        return;
    }

    const category_name = frm.doc.custom_category_name || '';
    const item_size = frm.doc.custom_item_size || '';
    const shape = frm.doc.custom_shape || '';
    const grade = frm.doc.custom_grade || '';

    if (item_size && shape && grade) {
        const bright_categories = [
            'Bright Squares',
            'Bright Rounds',
            'Bright Hex',
            'Bright Flats'
        ];

        const is_bright_category = bright_categories.includes(category_name);

        let generated_value = item_size + ' ' + shape + ' ' + grade;

        if (is_bright_category) {
            generated_value = 'B ' + generated_value;
        }

        frm.set_value('item_code', generated_value);
        frm.set_value('item_name', generated_value);
    }
}

function toggle_group_for_sub_assemblies_visibility(frm) {
    if (frm.doc.custom_store_item) {
        return;
    }

    if (frm.fields_dict['custom_group_for_sub_assemblies']) {
        const is_sub_assemblies = frm.doc.item_group === 'Sub Assemblies';

        if (is_sub_assemblies) {
            frm.set_df_property('custom_group_for_sub_assemblies', 'hidden', 0);
        } else {
            frm.set_df_property('custom_group_for_sub_assemblies', 'hidden', 1);
        }
    }
}

function update_decoupled_lead_time(frm, allow_when_dirty) {
    if (!frm.doc.item_code) {
        return;
    }

    if (frm.is_new() || frm.doc.__islocal) {
        if (frm.doc.lead_time_days) {
            frm.doc.custom_decoupled_lead_time = frm.doc.lead_time_days;
            frm.refresh_field('custom_decoupled_lead_time');
        }
        return;
    }

    if (!frm.fields_dict['custom_decoupled_lead_time']) {
        return;
    }

    const original_modified = frm.doc.modified;
    frappe.call({
        method: "prakash_steel.api.get_decoupled_lead_time.get_decoupled_lead_time",
        args: {
            item_code: frm.doc.item_code
        },
        callback: function (r) {
            if (r.message !== undefined && r.message !== null) {
                const current_value = frm.doc.custom_decoupled_lead_time;
                const new_value = r.message;

                if (current_value !== new_value) {
                    const was_dirty = frm.is_dirty();

                    const doc = locals[frm.doctype] && locals[frm.doctype][frm.docname];
                    if (doc) {
                        doc.custom_decoupled_lead_time = new_value;
                    }

                    frm.doc.custom_decoupled_lead_time = new_value;

                    if (original_modified && frm.doc.modified !== original_modified) {
                        frm.doc.modified = original_modified;
                        if (doc) {
                            doc.modified = original_modified;
                        }
                    }

                    frm.refresh_field('custom_decoupled_lead_time');

                    if (!was_dirty) {
                        if (frm._dirty_fields) {
                            const index = frm._dirty_fields.indexOf('custom_decoupled_lead_time');
                            if (index > -1) {
                                frm._dirty_fields.splice(index, 1);
                            }
                        }

                        setTimeout(function () {
                            if (!was_dirty && frm.is_dirty && frm.is_dirty()) {
                                const has_other_changes = frm._dirty_fields && frm._dirty_fields.length > 0;
                                if (!has_other_changes) {
                                    frm.dirty(false);
                                }
                            }
                        }, 100);
                    }
                }
            }
        }
    });
}

function toggle_buffer_fields_visibility(frm) {
    if (!frm.fields_dict['custom_buffer_flag']) {
        return;
    }

    const is_buffer = frm.doc.custom_buffer_flag === 'Buffer';

    if (frm.fields_dict['safety_stock']) {
        frm.set_df_property('safety_stock', 'hidden', !is_buffer);
        frm.set_df_property('safety_stock', 'reqd', is_buffer && frm.doc.custom_item_type !== 'CS');
    }

    if (frm.fields_dict['custom_top_of_red']) {
        frm.set_df_property('custom_top_of_red', 'hidden', !is_buffer);
    }

    if (frm.fields_dict['custom_top_of_yellow']) {
        frm.set_df_property('custom_top_of_yellow', 'hidden', !is_buffer);
    }

}

function calculate_buffer_fields(frm) {
    if (frm.doc.custom_buffer_flag !== 'Buffer') {
        return;
    }

    const safety_stock = frm.doc.safety_stock;

    if (safety_stock !== null && safety_stock !== undefined) {
        if (safety_stock <= 0) {
            frappe.msgprint({
                title: __('Validation Error'),
                indicator: 'red',
                message: __('Safety Stock must be greater than 0.')
            });
            frm.set_value('safety_stock', null);
            frm.set_value('custom_top_of_red', null);
            frm.set_value('custom_top_of_yellow', null);
            return;
        }

        const top_of_red = Math.ceil((1 / 3) * safety_stock);
        const top_of_yellow = Math.ceil((2 / 3) * safety_stock);

        frm.set_value('custom_top_of_red', top_of_red);
        frm.set_value('custom_top_of_yellow', top_of_yellow);
    } else {
        frm.set_value('custom_top_of_red', null);
        frm.set_value('custom_top_of_yellow', null);
    }
}

function calculate_sku_type(frm) {
    if (!frm.fields_dict['custom_sku_type']) {
        return;
    }

    const was_dirty = frm.is_dirty();

    const buffer_flag = frm.doc.custom_buffer_flag || 'Non-Buffer';
    const item_type = frm.doc.custom_item_type;

    let new_sku_type = null;

    if (item_type) {
        const is_buffer = buffer_flag === 'Buffer';

        if (item_type === 'BB') {
            new_sku_type = is_buffer ? 'BBMTA' : 'BBMTO';
        } else if (item_type === 'RB') {
            new_sku_type = is_buffer ? 'RBMTA' : 'RBMTO';
        } else if (item_type === 'BO') {
            new_sku_type = is_buffer ? 'BOTA' : 'BOTO';
        } else if (item_type === 'RM') {
            new_sku_type = is_buffer ? 'PTA' : 'PTO';
        } else if (item_type === 'Traded') {
            new_sku_type = is_buffer ? 'TRMTA' : 'TRMTO';
        }
    }

    const current_sku_type = frm.doc.custom_sku_type;

    if (current_sku_type !== new_sku_type) {
        const doc = locals[frm.doctype] && locals[frm.doctype][frm.docname];
        if (doc) {
            doc.custom_sku_type = new_sku_type;
        }

        frm.doc.custom_sku_type = new_sku_type;

        frm.refresh_field('custom_sku_type');

        if (!was_dirty) {
            if (frm._dirty_fields) {
                const index = frm._dirty_fields.indexOf('custom_sku_type');
                if (index > -1) {
                    frm._dirty_fields.splice(index, 1);
                }
            }

            setTimeout(function () {
                if (!was_dirty && frm.is_dirty && frm.is_dirty()) {
                    const has_other_changes = frm._dirty_fields && frm._dirty_fields.length > 0;
                    if (!has_other_changes) {
                        frm.dirty(false);
                    }
                }
            }, 100);
        }
    }
}


function handle_min_order_qty_batch_size_exclusivity(frm) {
    if (!frm.fields_dict['min_order_qty'] || !frm.fields_dict['custom_batch_size']) {
        return;
    }

    const min_order_qty = parseFloat(frm.doc.min_order_qty) || 0;
    const custom_batch_size = parseInt(frm.doc.custom_batch_size) || 0;

    if (min_order_qty > 0) {
        frm.set_df_property('custom_batch_size', 'read_only', 1);
        if (custom_batch_size > 0) {
            frm.set_value('custom_batch_size', 0);
        }
        frm.set_df_property('min_order_qty', 'read_only', 0);
    }
    else if (custom_batch_size > 0) {
        frm.set_df_property('min_order_qty', 'read_only', 1);
        if (min_order_qty > 0) {
            frm.set_value('min_order_qty', 0);
        }
        frm.set_df_property('custom_batch_size', 'read_only', 0);
    }
    else {
        frm.set_df_property('min_order_qty', 'read_only', 0);
        frm.set_df_property('custom_batch_size', 'read_only', 0);
    }
}


frappe.ui.form.on("CS Tog table", {
    top_of_green: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        const top_of_green = row.top_of_green || 0;

        if (top_of_green > 0) {
            frappe.model.set_value(cdt, cdn, "top_of_yellow", Math.ceil((2 / 3) * top_of_green));
            frappe.model.set_value(cdt, cdn, "top_of_red", Math.ceil((1 / 3) * top_of_green));
        } else {
            frappe.model.set_value(cdt, cdn, "top_of_yellow", null);
            frappe.model.set_value(cdt, cdn, "top_of_red", null);
        }
    }
});

// Override erpnext.item.make_dashboard to use custom method that excludes custom_closed SO items
frappe.provide("erpnext.item");
$.extend(erpnext.item, {
    make_dashboard: function (frm) {
        if (frm.doc.__islocal) return;

        if (frm.doc.is_stock_item) {
            frappe.require("item-dashboard.bundle.js", function () {
                const section = frm.dashboard.add_section("", __("Stock Levels"));
                erpnext.item.item_dashboard = new erpnext.stock.ItemDashboard({
                    parent: section,
                    item_code: frm.doc.name,
                    page_length: 20,
                    method: "prakash_steel.utils.item_dashboard.get_data",
                    template: "item_dashboard_list",
                });
                erpnext.item.item_dashboard.refresh();
            });
        }
    },
});

// function refresh_item_adu(frm) {
//     if (!frm.doc.item_code || frm.is_new() || frm.doc.__islocal) {
//         return;
//     }

//     if (!frm.fields_dict['custom_adu']) {
//         return;
//     }

//     const was_dirty = frm.is_dirty();

//     frappe.call({
//         method: "prakash_steel.prakash_steel.api.adu.update_item_adu",
//         args: {
//             item_code: frm.doc.item_code
//         },
//         callback: function (r) {
//             if (r.message !== undefined && r.message !== null) {
//                 const new_adu = r.message;
//                 const current_adu = frm.doc.custom_adu;

//                 if (current_adu !== new_adu) {
//                     const doc = locals[frm.doctype] && locals[frm.doctype][frm.docname];
//                     if (doc) {
//                         doc.custom_adu = new_adu;
//                     }
//                     frm.doc.custom_adu = new_adu;
//                     frm.refresh_field('custom_adu');

//                     if (!was_dirty) {
//                         if (frm._dirty_fields) {
//                             const idx = frm._dirty_fields.indexOf('custom_adu');
//                             if (idx > -1) {
//                                 frm._dirty_fields.splice(idx, 1);
//                             }
//                         }
//                         setTimeout(function () {
//                             const has_other_changes = frm._dirty_fields && frm._dirty_fields.length > 0;
//                             if (!has_other_changes && frm.is_dirty && frm.is_dirty()) {
//                                 frm.dirty(false);
//                             }
//                         }, 100);
//                     }
//                 }
//             }
//         }
//     });
// }

