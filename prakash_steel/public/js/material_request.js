
function set_last_rate_for_row(frm, cdt, cdn, item_code) {
    if (!item_code) {
        frappe.model.set_value(cdt, cdn, "custom_last_rate", 0);
        return;
    }

    frappe.call({
        method: "prakash_steel.api.get_last_purchase_invoice_rate.get_last_purchase_order_rate",
        args: {
            item_code: item_code,
            company: frm.doc.company || ""
        },
        callback: function (r) {
            frappe.model.set_value(cdt, cdn, "custom_last_rate", r.message || 0);
        }
    });
}

// "Qty to Deliver" total from the Open SO page for the Finished Size item
function set_open_so_qty_for_row(frm, cdt, cdn, finished_size) {
    frappe.call({
        method: "prakash_steel.api.get_open_so_qty.get_open_so_qty",
        args: {
            item_code: finished_size,
            company: frm.doc.company || ""
        },
        callback: function (r) {
            frappe.model.set_value(cdt, cdn, "custom_open_so_qty", r.message || 0);
        },
        error: function () {
            frappe.model.set_value(cdt, cdn, "custom_open_so_qty", 0);
        }
    });
}

frappe.ui.form.on("Material Request", {
    refresh: function (frm) {
        // Clear cancel reason on amended drafts
        if (frm.doc.amended_from && frm.doc.docstatus === 0 && frm.doc.custom_cancel_reason) {
            frm.set_value("custom_cancel_reason", "");
        }

    },
    company: function (frm) {
        // Recompute last rate for all existing rows when company changes.
        (frm.doc.items || []).forEach(function (row) {
            if (row.item_code) {
                set_last_rate_for_row(frm, row.doctype, row.name, row.item_code);
            }
            if (row.custom_finished_size) {
                set_open_so_qty_for_row(frm, row.doctype, row.name, row.custom_finished_size);
            }
        });
        frm.refresh_field("items");
    },

    before_cancel: function (frm) {
        // If a cancel reason is already set, allow normal cancellation
        if (frm.doc.custom_cancel_reason && frm.doc.custom_cancel_reason.trim()) {
            return;
        }

        // First dialog: Show 4 options
        const reasonOptionsDialog = new frappe.ui.Dialog({
            title: __("Select Cancel Reason"),
            fields: [
                {
                    fieldname: "cancel_reason_option",
                    label: __("Cancel Reason"),
                    fieldtype: "Select",
                    options: [
                        "Rate Mistake",
                        "Size Mistake",
                        "Data Entry Mistake",
                        "Others",
                    ],
                    reqd: 1,
                },
            ],
            primary_action_label: __("Continue"),
            primary_action(values) {
                if (!values || !values.cancel_reason_option) {
                    return;
                }

                const selectedOption = values.cancel_reason_option;

                // If "Others" is selected, show the text input dialog
                if (selectedOption === "Others") {
                    reasonOptionsDialog.hide();
                    showCustomReasonDialog(frm);
                } else {
                    // For options A, B, C: Save the reason directly and cancel
                    reasonOptionsDialog.hide();
                    frappe.call({
                        method: "prakash_steel.utils.material_request_cancel.cancel_material_request_with_reason",
                        args: {
                            name: frm.doc.name,
                            reason: selectedOption,
                        },
                        freeze: true,
                        freeze_message: __("Cancelling Material Request..."),
                        callback() {
                            frm.reload_doc();
                        },
                    });
                }
            },
        });

        // Function to show the custom reason dialog (for "Others" option)
        function showCustomReasonDialog(frm) {
            const customReasonDialog = new frappe.ui.Dialog({
                title: __("Cancel Reason Required"),
                fields: [
                    {
                        fieldname: "cancel_reason",
                        label: __("Cancel Reason"),
                        fieldtype: "Small Text",
                        reqd: 1,
                    },
                ],
                primary_action_label: __("Cancel Material Request"),
                primary_action(values) {
                    if (!values || !values.cancel_reason) {
                        return;
                    }

                    frappe.call({
                        method: "prakash_steel.utils.material_request_cancel.cancel_material_request_with_reason",
                        args: {
                            name: frm.doc.name,
                            reason: values.cancel_reason,
                        },
                        freeze: true,
                        freeze_message: __("Cancelling Material Request..."),
                        callback() {
                            customReasonDialog.hide();
                            frm.reload_doc();
                        },
                    });
                },
            });

            customReasonDialog.show();
        }

        reasonOptionsDialog.show();

        // Prevent the standard cancel; our server method will perform the cancel
        frappe.validated = false;
    },
});

frappe.ui.form.on("Material Request Item", {
    item_code: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (!row.item_code) {
            frappe.model.set_value(cdt, cdn, 'custom_quantity_available_in_kg', 0);
            // Also reset total stock field when no item is selected
            frappe.model.set_value(cdt, cdn, 'custom_item_size', 0);
            // Reset last purchase/production info
            frappe.model.set_value(cdt, cdn, 'custom_last_purchase_or_production', null);
            frappe.model.set_value(cdt, cdn, 'custom_purchase_or_production_quantity_in_kg', 0);
            frm.refresh_field("items");
            return;
        }

        // Fetch company-wise latest purchase invoice rate.
        set_last_rate_for_row(frm, cdt, cdn, row.item_code);

        // Fetch latest purchase or production date & quantity for this item
        frappe.call({
            method: "prakash_steel.api.get_last_purchase_or_production.get_last_purchase_or_production",
            args: {
                item_code: row.item_code
            },
            callback: function (r) {
                const data = r.message || {};
                // Date field on child row
                frappe.model.set_value(
                    cdt,
                    cdn,
                    "custom_last_purchase_or_production",
                    data.date || null
                );
                // Quantity field on child row
                frappe.model.set_value(
                    cdt,
                    cdn,
                    "custom_purchase_or_production_quantity_in_kg",
                    data.qty || 0
                );
            },
            error: function () {
                frappe.model.set_value(cdt, cdn, "custom_last_purchase_or_production", null);
                frappe.model.set_value(cdt, cdn, "custom_purchase_or_production_quantity_in_kg", 0);
            },
        });

        frappe.call({
            method: "prakash_steel.api.get_available_stock.get_available_stock",
            args: {
                item_code: row.item_code
            },
            callback: function (res) {
                if (res.message !== undefined) {
                    frappe.model.set_value(cdt, cdn, 'custom_quantity_available_in_kg', res.message);
                    frappe.model.set_value(cdt, cdn, 'custom_item_size', res.message);
                } else {
                    frappe.model.set_value(cdt, cdn, 'custom_quantity_available_in_kg', 0);
                    frappe.model.set_value(cdt, cdn, 'custom_item_size', 0);
                }
                frm.refresh_field("items");
            },
            error: function () {
                frappe.model.set_value(cdt, cdn, 'custom_quantity_available_in_kg', 0);
                frappe.model.set_value(cdt, cdn, 'custom_item_size', 0);
                frm.refresh_field("items");
            }
        });
    },

    custom_finished_size: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (!row.custom_finished_size) {
            frappe.model.set_value(cdt, cdn, 'custom_quantity_available_finished_size', 0);
            frappe.model.set_value(cdt, cdn, 'custom_open_so_qty', 0);
            return;
        }

        // Same planning-warehouse stock as "Quantity Available", but for the Finished Size item
        frappe.call({
            method: "prakash_steel.api.get_available_stock.get_available_stock",
            args: {
                item_code: row.custom_finished_size
            },
            callback: function (res) {
                frappe.model.set_value(cdt, cdn, 'custom_quantity_available_finished_size', res.message || 0);
            },
            error: function () {
                frappe.model.set_value(cdt, cdn, 'custom_quantity_available_finished_size', 0);
            }
        });

        set_open_so_qty_for_row(frm, cdt, cdn, row.custom_finished_size);
    }
});