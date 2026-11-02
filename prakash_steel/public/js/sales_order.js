function validate_zero_rate_items(frm) {
    let zero_rate_rows = (frm.doc.items || []).filter(row => !row.rate || row.rate === 0);
    if (zero_rate_rows.length) {
        let msgs = zero_rate_rows.map(row =>
            __("Row {0}: Item {1} has Rate 0. Please set a valid rate.", [row.idx, row.item_code || row.item_name || ""])
        );
        frappe.msgprint({ title: __("Zero Rate Not Allowed"), message: msgs.join("<br>"), indicator: "red" });
        frappe.validated = false;
    }
}

frappe.ui.form.on("Sales Order", {
    validate(frm) {
        validate_zero_rate_items(frm);
    },

    before_submit(frm) {
        return new Promise((resolve) => {
            frappe.call({
                method: "prakash_steel.utils.sales_order_rate_floor.get_rate_floor_warnings",
                args: { sales_order: frm.doc },
                callback(r) {
                    let warnings = (r.message && r.message.warnings) || [];
                    if (!warnings.length) {
                        resolve();
                        return;
                    }
                    frappe.confirm(
                        __("The following item(s) are priced below the minimum rate:") +
                            "<br><br>" + warnings.join("<br>") +
                            "<br><br>" + __("Do you still want to submit?"),
                        () => resolve(),
                        () => {
                            // Cancel: stop the submit, leave the doc in draft
                            frappe.validated = false;
                            resolve();
                        }
                    );
                },
                error() {
                    // don't block submission on a network/server hiccup here -
                    // the real floor check still runs server-side on submit
                    resolve();
                },
            });
        });
    },

    refresh(frm) {
        // Clear cancel reason on amended drafts
        if (frm.doc.amended_from && frm.doc.docstatus === 0 && frm.doc.custom_cancel_reason) {
            frm.set_value("custom_cancel_reason", "");
        }

        // Patch cancel behavior once per form instance
        if (frm.__pspl_cancel_patched) return;
        frm.__pspl_cancel_patched = true;

        const original_savecancel = frm.savecancel.bind(frm);

        frm.savecancel = function (btn, callback, on_error) {
            // For non-submitted docs, fall back to standard behaviour
            if (frm.doc.docstatus !== 1) {
                return original_savecancel(btn, callback, on_error);
            }

            // If reason is already set (e.g. via some other UI), just run our server cancel once
            const run_cancel_with_reason = (reason) => {
                frappe.call({
                    method: "prakash_steel.utils.sales_order_cancel.cancel_sales_order_with_reason",
                    args: {
                        name: frm.doc.name,
                        reason,
                    },
                    freeze: true,
                    freeze_message: __("Cancelling Sales Order..."),
                    callback() {
                        frm.reload_doc();
                    },
                    error: on_error,
                });
            };

            const existing_reason = (frm.doc.custom_cancel_reason || "").trim();
            if (existing_reason) {
                run_cancel_with_reason(existing_reason);
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
                            "Party Name Mistake",
                            "Rate Mistake",
                            "Size Mistake",
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

                    // If "Others" or "Party Name Mistake" is selected, show the text input dialog
                    if (selectedOption === "Others" || selectedOption === "Party Name Mistake") {
                        reasonOptionsDialog.hide();
                        showCustomReasonDialog(frm, run_cancel_with_reason, selectedOption);
                    } else {
                        // For other options: save the reason label directly and cancel
                        reasonOptionsDialog.hide();
                        run_cancel_with_reason(selectedOption);
                    }
                },
            });

            // Function to show the custom reason dialog (for "Others" / Party Name Mistake)
            function showCustomReasonDialog(frm, runCancelCallback, selectedOption) {
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
                    primary_action_label: __("Cancel Sales Order"),
                    primary_action(values) {
                        if (!values || !values.cancel_reason) {
                            return;
                        }

                        customReasonDialog.hide();
                        const finalReason = `${selectedOption}, ${values.cancel_reason}`;
                        runCancelCallback(finalReason);
                    },
                });

                customReasonDialog.show();
            }

            reasonOptionsDialog.show();
        };
    },
});

frappe.ui.form.on("Sales Order Item", {
    item_code: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (row.item_code) {
            frappe.call({
                method: "prakash_steel.api.get_last_sales_invoice_rate.get_last_sales_invoice_rate",
                args: {
                    item_code: row.item_code,
                },
                callback: function (r) {
                    frappe.model.set_value(cdt, cdn, "custom_last_rate", r.message || 0);
                }
            });
            frappe.call({
                method: "prakash_steel.api.get_last_sales_invoice_sold_qty.get_last_sales_invoice_sold_qty",
                args: {
                    item_code: row.item_code,
                },
                callback: function (r) {
                    frappe.model.set_value(cdt, cdn, "custom_last_sold_qty", r.message || 0);
                }
            });
        }
    }
});