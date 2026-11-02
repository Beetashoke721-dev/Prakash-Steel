// Copyright (c) 2025, beetashoke chakraborty and contributors
// For license information, please see license.txt

function validate_zero_rate_items_po(frm) {
    let zero_rate_rows = (frm.doc.items || []).filter(row => !row.rate || row.rate === 0);
    if (zero_rate_rows.length) {
        let msgs = zero_rate_rows.map(row =>
            __("Row {0}: Item {1} has Rate 0. Please set a valid rate.", [row.idx, row.item_code || row.item_name || ""])
        );
        frappe.msgprint({ title: __("Zero Rate Not Allowed"), message: msgs.join("<br>"), indicator: "red" });
        frappe.validated = false;
    }
}

frappe.ui.form.on("Purchase Order", {
    validate(frm) {
        validate_zero_rate_items_po(frm);
    },

    refresh(frm) {
        // Clear cancel reason on amended drafts
        if (frm.doc.amended_from && frm.doc.docstatus === 0 && frm.doc.custom_cancel_reason) {
            frm.set_value("custom_cancel_reason", "");
        }

        // Optional: existing UI behaviour
        if (frm.doc.status === "Closed") {
            frappe.show_alert(
                {
                    message: __(
                        "Purchase Order status changed to Closed. Quantity validation will be performed."
                    ),
                    indicator: "blue",
                },
                3
            );
        }

        // Refresh-fill is display-only. set_value here would mark a saved draft
        // "Not Saved" again (async callback after the Saved toast).
        fill_missing_last_purchase_details_for_purchase_order(frm, true);

        // Patch cancel behaviour once per form instance
        if (frm.__pspl_po_cancel_patched) return;
        frm.__pspl_po_cancel_patched = true;

        const original_savecancel = frm.savecancel
            ? frm.savecancel.bind(frm)
            : null;

        if (!original_savecancel) return;

        frm.savecancel = function (btn, callback, on_error) {
            // For non-submitted docs, fall back to standard behaviour
            if (frm.doc.docstatus !== 1) {
                return original_savecancel(btn, callback, on_error);
            }

            const proceed_with_standard_cancel = () => {
                original_savecancel(btn, callback, on_error);
            };

            const existing_reason = (frm.doc.custom_cancel_reason || "").trim();
            if (existing_reason) {
                return proceed_with_standard_cancel();
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
                            "Wrong Qty",
                            "Wrong Item",
                            "Wrong Supplier",
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
                        showCustomReasonDialog(frm, proceed_with_standard_cancel, on_error);
                    } else {
                        // For options A, B, C: Save the reason directly and proceed
                        reasonOptionsDialog.hide();
                        frappe.call({
                            method: "prakash_steel.utils.purchase_order_cancel.set_purchase_order_cancel_reason",
                            args: {
                                name: frm.doc.name,
                                reason: selectedOption,
                            },
                            freeze: true,
                            freeze_message: __("Saving Cancel Reason..."),
                            callback() {
                                proceed_with_standard_cancel();
                            },
                            error: on_error,
                        });
                    }
                },
            });

            // Function to show the custom reason dialog (for "Others" option)
            function showCustomReasonDialog(frm, proceedCallback, onError) {
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
                    primary_action_label: __("Continue"),
                    primary_action(values) {
                        if (!values || !values.cancel_reason) {
                            return;
                        }

                        frappe.call({
                            method: "prakash_steel.utils.purchase_order_cancel.set_purchase_order_cancel_reason",
                            args: {
                                name: frm.doc.name,
                                reason: values.cancel_reason,
                            },
                            freeze: true,
                            freeze_message: __("Saving Cancel Reason..."),
                            callback() {
                                customReasonDialog.hide();
                                proceedCallback();
                            },
                            error: onError,
                        });
                    },
                });

                customReasonDialog.show();
            }

            reasonOptionsDialog.show();
        };
    },

    before_workflow_action(frm) {
        // Only intercept the Reject action
        if (frm.selected_workflow_action !== "Reject") {
            return;
        }

        // If reason already present, allow workflow to proceed
        if (frm.doc.custom_cancel_reason && frm.doc.custom_cancel_reason.trim()) {
            return;
        }

        return new Promise((resolve, reject) => {
            // Unfreeze UI so user can type in our dialog
            frappe.dom.unfreeze();

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
                        showCustomReasonDialog(frm, resolve, reject);
                    } else {
                        // For options A, B, C: Save the reason directly and resolve
                        reasonOptionsDialog.hide();
                        frappe.call({
                            method: "prakash_steel.utils.purchase_order_cancel.set_purchase_order_cancel_reason",
                            args: {
                                name: frm.doc.name,
                                reason: selectedOption,
                            },
                            freeze: true,
                            freeze_message: __("Saving Cancel Reason..."),
                            callback() {
                                resolve();
                            },
                            error(err) {
                                frappe.dom.unfreeze();
                                reject(err);
                            },
                        });
                    }
                },
            });

            // Function to show the custom reason dialog (for "Others" option)
            function showCustomReasonDialog(frm, resolveCallback, rejectCallback) {
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
                    primary_action_label: __("Continue"),
                    primary_action(values) {
                        if (!values || !values.cancel_reason) {
                            return;
                        }

                        frappe.call({
                            method: "prakash_steel.utils.purchase_order_cancel.set_purchase_order_cancel_reason",
                            args: {
                                name: frm.doc.name,
                                reason: values.cancel_reason,
                            },
                            freeze: true,
                            freeze_message: __("Saving Cancel Reason..."),
                            callback() {
                                customReasonDialog.hide();
                                resolveCallback();
                            },
                            error(err) {
                                customReasonDialog.hide();
                                frappe.dom.unfreeze();
                                rejectCallback(err);
                            },
                        });
                    },
                });

                customReasonDialog.set_secondary_action(() => {
                    customReasonDialog.hide();
                    frappe.dom.unfreeze();
                    rejectCallback();
                });

                customReasonDialog.show();
            }

            reasonOptionsDialog.set_secondary_action(() => {
                reasonOptionsDialog.hide();
                frappe.dom.unfreeze();
                reject();
            });

            reasonOptionsDialog.show();
        });
    },

    on_update_after_submit(frm) {
        // Client-side notification after update
        if (frm.doc.status === "Closed") {
            frappe.show_alert(
                {
                    message: __(
                        "Purchase Order updated. Quantity validation will be performed."
                    ),
                    indicator: "blue",
                },
                3
            );
        }
    },
});

// Note: Client-side validation for PO quantity is handled server-side
// to avoid permission issues with child doctypes (Purchase Order Item)
// The server-side validation in purchase_order.py will check quantities
// and send email notifications when status is changed to Closed and items have shortfall

function apply_last_purchase_fields_for_purchase_order_item(cdt, cdn, item, skip_dirty) {
    const row = locals[cdt] && locals[cdt][cdn];
    if (!row) return;

    const next_party = item.last_purchase_party || null;
    const next_date = item.last_purchase_date || null;
    const next_qty = flt(item.last_purchase_quantity || 0);

    const same_party = (row.custom_last_purchase_party || null) === next_party;
    const same_date = (row.custom_last_purchase_date || null) === (next_date || null);
    const same_qty = flt(row.custom_last_purchase_quantity) === next_qty;
    if (same_party && same_date && same_qty) return;

    frappe.model.set_value(
        cdt,
        cdn,
        "custom_last_purchase_party",
        next_party,
        null,
        skip_dirty
    );
    frappe.model.set_value(
        cdt,
        cdn,
        "custom_last_purchase_date",
        next_date,
        null,
        skip_dirty
    );
    frappe.model.set_value(
        cdt,
        cdn,
        "custom_last_purchase_quantity",
        next_qty,
        null,
        skip_dirty
    );
}

function set_last_purchase_fields_for_purchase_order_item(cdt, cdn, item_code, skip_dirty) {
    if (!item_code) return;

    frappe.call({
        method: "prakash_steel.api.get_item_insight_data.get_item_insight_data",
        args: { item_code },
        callback: function (r) {
            const items = (r && r.message) ? r.message : [];
            if (!items.length) return;

            apply_last_purchase_fields_for_purchase_order_item(
                cdt,
                cdn,
                items[0] || {},
                skip_dirty
            );
        },
        error: function () {
            // Keep PO entry editable even if insight API fails.
        },
    });
}

function fill_missing_last_purchase_details_for_purchase_order(frm, skip_dirty) {
    // Mapped rows (e.g. from Material Request) never fire item_code, so fill on draft load.
    if (frm.doc.docstatus !== 0) return;

    (frm.doc.items || []).forEach(function (row) {
        if (!row.item_code || row.__pspl_last_purchase_fetched) return;

        if (
            row.custom_last_purchase_party ||
            row.custom_last_purchase_date ||
            flt(row.custom_last_purchase_quantity)
        ) {
            row.__pspl_last_purchase_fetched = true;
            return;
        }

        row.__pspl_last_purchase_fetched = true;
        set_last_purchase_fields_for_purchase_order_item(
            row.doctype,
            row.name,
            row.item_code,
            skip_dirty
        );
    });
}

frappe.ui.form.on("Purchase Order Item", {
    item_code(frm, cdt, cdn) {
        const row = locals[cdt] && locals[cdt][cdn];
        if (!row) return;
        row.__pspl_last_purchase_fetched = false;
        set_last_purchase_fields_for_purchase_order_item(cdt, cdn, row.item_code, false);
    },
});





