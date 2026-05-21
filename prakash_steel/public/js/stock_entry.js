// Copyright (c) 2025, beetashoke chakraborty and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stock Entry', {
    refresh: function (frm) {
        // Toggle vehicle_no mandatory status based on stock_entry_type
        toggle_vehicle_no_mandatory(frm);
    },

    stock_entry_type: function (frm) {
        // When stock_entry_type changes, update vehicle_no mandatory status
        toggle_vehicle_no_mandatory(frm);
    },

    purpose: function (frm) {
        // When purpose changes (alternative field name), update vehicle_no mandatory status
        toggle_vehicle_no_mandatory(frm);
    },

    validate: function (frm) {
        // Client-side validation before save
        const stock_entry_type = frm.doc.stock_entry_type || frm.doc.purpose;

        if (stock_entry_type === "Material Transfer") {
            if (!frm.doc.vehicle_no || (typeof frm.doc.vehicle_no === 'string' && !frm.doc.vehicle_no.trim())) {
                frappe.msgprint({
                    title: __('Validation Error'),
                    indicator: 'red',
                    message: __('Vehicle No is mandatory when Stock Entry Type is Material Transfer.')
                });
                frappe.validated = false;
            }
        }
    }
});

function toggle_vehicle_no_mandatory(frm) {
    // Get stock_entry_type (could be stock_entry_type or purpose field)
    const stock_entry_type = frm.doc.stock_entry_type || frm.doc.purpose;

    // Check if vehicle_no field exists
    if (frm.fields_dict.vehicle_no) {
        if (stock_entry_type === "Material Transfer") {
            // Make vehicle_no mandatory
            frm.set_df_property('vehicle_no', 'reqd', 1);
        } else {
            // Make vehicle_no optional
            frm.set_df_property('vehicle_no', 'reqd', 0);
        }
    }
}


