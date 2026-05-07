// // Parent Doctype: Material Request
// frappe.ui.form.on("Material Request", {
//     refresh: function(frm) {
//         console.log("=== Material Request Form Refreshed ===");
//         console.log("Parent Doc:", frm.doc);

//         // Optional: log existing child table rows on refresh
//         frm.doc.items.forEach(function(row) {
//             console.log("Child row on refresh:", row.item_code, row.name);
//         });
//     }
// });

// // Child Table: Material Request Item
// frappe.ui.form.on('Material Request Item', {
//     item_code: function(frm, cdt, cdn) {
//         const row = locals[cdt][cdn];

//         console.log("=== Material Request Item Code Triggered ===");
//         console.log("Row data:", row);
//         console.log("CDT:", cdt, "CDN:", cdn);

//         // Check if item_code exists
//         if (!row.item_code) {
//             console.log("No Item Code selected. Setting available stock to 0");
//             frappe.model.set_value(cdt, cdn, 'custom_quantity_available_in_kg', 0);
//             frm.refresh_field("items");
//             return;
//         }

//         console.log("Selected Item Code:", row.item_code);
//         console.log("Calling Server Script API: get_available_stock");

//         // Call the whitelisted Python method
//         frappe.call({
//             method: "prakash_steel.api.get_available_stock.get_available_stock", // Only sending item_code
//             args: {
//                 item_code: row.item_code
//             },
//             callback: function(res) {
//                 console.log("Server response:", res);

//                 if (res.message !== undefined) {
//                     console.log("Available stock received:", res.message);
//                     frappe.model.set_value(cdt, cdn, 'custom_quantity_available_in_kg', res.message);
//                 } else {
//                     console.log("No stock returned from server. Setting 0");
//                     frappe.model.set_value(cdt, cdn, 'custom_quantity_available_in_kg', 0);
//                 }

//                 frm.refresh_field("items");
//             },
//             error: function(err) {
//                 console.error("Error fetching stock from server:", err);
//                 frappe.model.set_value(cdt, cdn, 'custom_quantity_available_in_kg', 0);
//                 frm.refresh_field("items");
//             }
//         });
//     }
// });





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

frappe.ui.form.on("Material Request", {
    refresh: function (frm) {
        // Clear cancel reason on amended drafts
        if (frm.doc.amended_from && frm.doc.docstatus === 0 && frm.doc.custom_cancel_reason) {
            frm.set_value("custom_cancel_reason", "");
        }

        console.log("=== Material Request Form Refreshed ===");
        console.log("Parent Doc:", frm.doc);

        // Optional: log existing child table rows on refresh
        frm.doc.items.forEach(function (row) {
            console.log("Child row on refresh:", row.item_code, row.name);
        });
    },
    company: function (frm) {
        // Recompute last rate for all existing rows when company changes.
        (frm.doc.items || []).forEach(function (row) {
            if (row.item_code) {
                set_last_rate_for_row(frm, row.doctype, row.name, row.item_code);
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
        console.log("=== Material Request Item Code Triggered ===");
        console.log("[Step 0] Item Code Changed:", row.item_code);
        console.log("Row data:", row);
        console.log("CDT:", cdt, "CDN:", cdn);

        if (!row.item_code) {
            console.log("[Step 1] No item_code provided, exiting.");
            console.log("No Item Code selected. Setting available stock to 0");
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

        console.log("Calling Server Script API: get_available_stock");
        frappe.call({
            method: "prakash_steel.api.get_available_stock.get_available_stock",
            args: {
                item_code: row.item_code
            },
            callback: function (res) {
                console.log("Server response for stock:", res); // Corrected typo
                if (res.message !== undefined) {
                    console.log("Available stock received:", res.message);
                    frappe.model.set_value(cdt, cdn, 'custom_quantity_available_in_kg', res.message);
                    // Populate TOTAL STOCK across all warehouses into custom_item_size
                    frappe.model.set_value(cdt, cdn, 'custom_item_size', res.message);
                } else {
                    console.log("No stock returned from server. Setting 0");
                    frappe.model.set_value(cdt, cdn, 'custom_quantity_available_in_kg', 0);
                    frappe.model.set_value(cdt, cdn, 'custom_item_size', 0);
                }
                frm.refresh_field("items");
            },
            error: function (err) {
                console.error("Error fetching stock from server:", err);
                frappe.model.set_value(cdt, cdn, 'custom_quantity_available_in_kg', 0);
                frappe.model.set_value(cdt, cdn, 'custom_item_size', 0);
                frm.refresh_field("items");
            }
        });
    }
});