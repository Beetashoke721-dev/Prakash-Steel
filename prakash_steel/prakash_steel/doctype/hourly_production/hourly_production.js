
frappe.ui.form.on('Hourly Production', {
    refresh(frm) {
        toggle_miss_roll_fields(frm);
        toggle_miss_ingot_fields(frm);
        calculate_total_pcs(frm);
        // Only fetch total_billet_cutting_pcs for new documents (not yet saved/submitted)
        if (frm.is_new()) {
            fetch_total_billet_cutting_pcs(frm);
        }
    },
    validate(frm) {
        // Ensure hidden fields are not mandatory and cleared
        if (!frm.doc.miss_roll_pcs || frm.doc.miss_roll_pcs <= 0) {
            frm.set_df_property("miss_roll_weight", "reqd", 0);
            frm.set_df_property("remarks_for_miss_roll", "reqd", 0);
            if (frm.doc.miss_roll_weight) {
                frm.doc.miss_roll_weight = null;
            }
            if (frm.doc.remarks_for_miss_roll) {
                frm.doc.remarks_for_miss_roll = null;
            }
        }
        if (!frm.doc.miss_ingot_pcs || frm.doc.miss_ingot_pcs <= 0) {
            frm.set_df_property("miss_ingot__billet_weight", "reqd", 0);
            frm.set_df_property("reason_for_miss_ingot__billet", "reqd", 0);
            if (frm.doc.miss_ingot__billet_weight) {
                frm.doc.miss_ingot__billet_weight = null;
            }
            if (frm.doc.reason_for_miss_ingot__billet) {
                frm.doc.reason_for_miss_ingot__billet = null;
            }
        }

        // Validate that remaining pieces are not negative
        if (frm.doc.billet_cutting_id && frm.doc.total_billet_cutting_pcs !== null && frm.doc.total_billet_cutting_pcs !== undefined) {
            if (frm.doc.total_billet_cutting_pcs < 0) {
                frappe.throw(__('No pieces left! You are trying to use {0} more pieces than available. Please reduce the quantities.', [Math.abs(frm.doc.total_billet_cutting_pcs)]));
            }
        }
    },
    billet_cutting_id(frm) {
        // Only fetch total_billet_cutting_pcs for new documents (not yet saved/submitted)
        if (frm.is_new()) {
            fetch_total_billet_cutting_pcs(frm);
        }
    },
    miss_roll_pcs(frm) {
        toggle_miss_roll_fields(frm);
        calculate_total_pcs(frm);
        // Note: We don't recalculate total_billet_cutting_pcs here because
        // current document's values should not affect its own remaining count
    },
    miss_ingot_pcs(frm) {
        toggle_miss_ingot_fields(frm);
        calculate_total_pcs(frm);
        // Note: We don't recalculate total_billet_cutting_pcs here because
        // current document's values should not affect its own remaining count
    },
    finish_item_pcs(frm) {
        calculate_total_pcs(frm);
        // Note: We don't recalculate total_billet_cutting_pcs here because
        // current document's values should not affect its own remaining count
    }
});

function _toggle_miss_fields(frm, count_field, weight_field, reason_field) {
    const has_pcs = frm.doc[count_field] && frm.doc[count_field] > 0;
    frm.set_df_property(weight_field, "reqd",   has_pcs ? 1 : 0);
    frm.set_df_property(weight_field, "hidden",  has_pcs ? 0 : 1);
    frm.set_df_property(reason_field, "reqd",   has_pcs ? 1 : 0);
    frm.set_df_property(reason_field, "hidden",  has_pcs ? 0 : 1);
    if (!has_pcs) {
        // Direct assignment to avoid marking form as dirty
        frm.doc[weight_field] = null;
        frm.doc[reason_field] = null;
    }
}

function toggle_miss_roll_fields(frm) {
    _toggle_miss_fields(frm, "miss_roll_pcs", "miss_roll_weight", "remarks_for_miss_roll");
}

function toggle_miss_ingot_fields(frm) {
    _toggle_miss_fields(frm, "miss_ingot_pcs", "miss_ingot__billet_weight", "reason_for_miss_ingot__billet");
}

function calculate_total_pcs(frm) {
    let finish = parseFloat(frm.doc.finish_item_pcs) || 0;
    let miss_roll = parseFloat(frm.doc.miss_roll_pcs) || 0;
    let miss_ingot = parseFloat(frm.doc.miss_ingot_pcs) || 0;

    let total = finish + miss_roll + miss_ingot;
    frm.set_value("total_pcs", total);
}

function fetch_total_billet_cutting_pcs(frm) {
    if (!frm.doc.billet_cutting_id) {
        // Clear the field if billet_cutting_id is empty
        frm.set_value("total_billet_cutting_pcs", null);
        return;
    }

    // Fetch total_raw_material_pcs from Billet Cutting document
    frappe.db.get_value('Billet Cutting', frm.doc.billet_cutting_id, 'total_raw_material_pcs')
        .then(r => {
            if (r && r.message && r.message.total_raw_material_pcs !== undefined) {
                const total_from_billet_cutting = parseFloat(r.message.total_raw_material_pcs) || 0;

                // Get current document name (if it exists, exclude it from the sum)
                const current_doc_name = frm.doc.name || null;

                // Build filter to find other Hourly Production documents with same billet_cutting_id
                // Only consider submitted documents (docstatus = 1), not draft documents
                let filters = {
                    'billet_cutting_id': frm.doc.billet_cutting_id,
                    'docstatus': 1 // Only submitted documents
                };

                // Exclude current document if it exists
                if (current_doc_name) {
                    filters['name'] = ['!=', current_doc_name];
                }

                // Fetch all other Hourly Production documents with the same billet_cutting_id
                return frappe.db.get_list('Hourly Production', {
                    filters: filters,
                    fields: ['finish_item_pcs', 'miss_roll_pcs', 'miss_ingot_pcs']
                }).then(other_docs => {
                    // Sum up finish_item_pcs + miss_roll_pcs + miss_ingot_pcs from other submitted documents
                    // Note: Do NOT subtract current document's values - they will only affect the next document
                    let total_used = 0;
                    if (other_docs && other_docs.length > 0) {
                        other_docs.forEach(doc => {
                            const finish = parseFloat(doc.finish_item_pcs) || 0;
                            const miss_roll = parseFloat(doc.miss_roll_pcs) || 0;
                            const miss_ingot = parseFloat(doc.miss_ingot_pcs) || 0;
                            total_used += (finish + miss_roll + miss_ingot);
                        });
                    }

                    // Calculate remaining: total_from_billet_cutting - total_used
                    // Current document's values are NOT subtracted here - they will only affect the next document
                    const remaining = total_from_billet_cutting - total_used;

                    // Set the remaining value
                    frm.set_value("total_billet_cutting_pcs", remaining);

                    // Show error if remaining is 0 or negative
                    if (remaining < 0) {
                        frappe.show_alert({
                            message: __('No pieces left! You are trying to use {0} more pieces than available.', [Math.abs(remaining)]),
                            indicator: 'red'
                        }, 10);
                    } else if (remaining === 0) {
                        frappe.show_alert({
                            message: __('No pieces left! All pieces have been used.'),
                            indicator: 'orange'
                        }, 10);
                    }

                    return remaining;
                });
            } else {
                frm.set_value("total_billet_cutting_pcs", null);
            }
        })
        .catch(err => {
            console.error("Error fetching total_billet_cutting_pcs:", err);
            frappe.show_alert({
                message: __('Error fetching Total Billet Cutting Pcs'),
                indicator: 'red'
            }, 5);
        });
}