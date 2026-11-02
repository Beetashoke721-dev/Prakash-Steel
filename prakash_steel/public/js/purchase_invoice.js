// frappe.ui.form.on("Purchase Invoice", {
//     before_cancel(frm) {
//         // If a cancel reason is already set, allow normal cancellation
//         if (frm.doc.custom_cancel_reason && frm.doc.custom_cancel_reason.trim()) {
//             return;
//         }

//         // First dialog: Show 4 options
//         const reasonOptionsDialog = new frappe.ui.Dialog({
//             title: __("Select Cancel Reason"),
//             fields: [
//                 {
//                     fieldname: "cancel_reason_option",
//                     label: __("Cancel Reason"),
//                     fieldtype: "Select",
//                     options: [
//                         "Rate Mistake",
//                         "Size Mistake",
//                         "Data Entry Mistake",
//                         "Others",
//                     ],
//                     reqd: 1,
//                 },
//             ],
//             primary_action_label: __("Continue"),
//             primary_action(values) {
//                 if (!values || !values.cancel_reason_option) {
//                     return;
//                 }

//                 const selectedOption = values.cancel_reason_option;

//                 // If "Others" is selected, show the text input dialog
//                 if (selectedOption === "Others") {
//                     reasonOptionsDialog.hide();
//                     showCustomReasonDialog(frm);
//                 } else {
//                     // For options A, B, C: Save the reason directly and cancel
//                     reasonOptionsDialog.hide();
//                     frappe.call({
//                         method: "prakash_steel.utils.purchase_invoice_cancel.cancel_purchase_invoice_with_reason",
//                         args: {
//                             name: frm.doc.name,
//                             reason: selectedOption,
//                         },
//                         freeze: true,
//                         freeze_message: __("Cancelling Purchase Invoice..."),
//                         callback() {
//                             frm.reload_doc();
//                         },
//                     });
//                 }
//             },
//         });

//         // Function to show the custom reason dialog (for "Others" option)
//         function showCustomReasonDialog(frm) {
//             const customReasonDialog = new frappe.ui.Dialog({
//                 title: __("Cancel Reason Required"),
//                 fields: [
//                     {
//                         fieldname: "cancel_reason",
//                         label: __("Cancel Reason"),
//                         fieldtype: "Small Text",
//                         reqd: 1,
//                     },
//                 ],
//                 primary_action_label: __("Cancel Purchase Invoice"),
//                 primary_action(values) {
//                     if (!values || !values.cancel_reason) {
//                         return;
//                     }

//                     frappe.call({
//                         method: "prakash_steel.utils.purchase_invoice_cancel.cancel_purchase_invoice_with_reason",
//                         args: {
//                             name: frm.doc.name,
//                             reason: values.cancel_reason,
//                         },
//                         freeze: true,
//                         freeze_message: __("Cancelling Purchase Invoice..."),
//                         callback() {
//                             customReasonDialog.hide();
//                             frm.reload_doc();
//                         },
//                     });
//                 },
//             });

//             customReasonDialog.show();
//         }

//         reasonOptionsDialog.show();

//         // Prevent the standard cancel; our server method will perform the cancel
//         frappe.validated = false;
//     },
// });





function update_weight_slip_totals(frm, skip_dirty) {
    const totalWeightSlipQty = (frm.doc.items || []).reduce((sum, row) => {
        return sum + (flt(row.custom_weight_slip_qty) || 0);
    }, 0);
    const shortageQty = cint(flt(frm.doc.total_qty) - totalWeightSlipQty);

    // Display-only on load/refresh and on submitted/cancelled docs so Save
    // does not immediately flip the form back to "Not Saved".
    if (skip_dirty === undefined) {
        skip_dirty = frm.doc.docstatus !== 0;
    }

    if (flt(frm.doc.custom_total_weight_slip_qty) !== flt(totalWeightSlipQty)) {
        frm.set_value("custom_total_weight_slip_qty", totalWeightSlipQty, undefined, skip_dirty);
    }

    if (cint(frm.doc.custom_shortage_qty) !== shortageQty) {
        frm.set_value("custom_shortage_qty", shortageQty, undefined, skip_dirty);
    }
}

frappe.ui.form.on("Purchase Invoice", {
    onload(frm) {
        update_weight_slip_totals(frm, true);
    },

    refresh(frm) {
        // Clear cancel reason on amended drafts — the field is copied from the
        // cancelled doc but should not carry over to the new invoice.
        if (frm.doc.amended_from && frm.doc.docstatus === 0 && frm.doc.custom_cancel_reason) {
            frm.set_value("custom_cancel_reason", "");
        }

        update_weight_slip_totals(frm, true);
        // Refresh-fill is display-only. set_value here would mark a saved draft
        // "Not Saved" again (async callback after the Saved toast).
        fill_missing_last_purchase_details_for_invoice(frm, true);
        fill_missing_rate_before_discount_for_invoice(frm, true);
    },

    total_qty(frm) {
        update_weight_slip_totals(frm);
    },

    items_add(frm) {
        update_weight_slip_totals(frm);
    },

    items_remove(frm) {
        update_weight_slip_totals(frm);
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
            frappe.dom.unfreeze();

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
                    if (!values || !values.cancel_reason_option) return;

                    const selectedOption = values.cancel_reason_option;

                    if (selectedOption === "Others") {
                        reasonOptionsDialog.hide();
                        showCustomReasonDialog(frm, resolve, reject);
                    } else {
                        reasonOptionsDialog.hide();
                        frappe.call({
                            method: "prakash_steel.utils.purchase_invoice_cancel.set_purchase_invoice_cancel_reason",
                            args: { name: frm.doc.name, reason: selectedOption },
                            freeze: true,
                            freeze_message: __("Saving Cancel Reason..."),
                            callback() { resolve(); },
                            error(err) { frappe.dom.unfreeze(); reject(err); },
                        });
                    }
                },
            });

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
                        if (!values || !values.cancel_reason) return;

                        frappe.call({
                            method: "prakash_steel.utils.purchase_invoice_cancel.set_purchase_invoice_cancel_reason",
                            args: { name: frm.doc.name, reason: values.cancel_reason },
                            freeze: true,
                            freeze_message: __("Saving Cancel Reason..."),
                            callback() { customReasonDialog.hide(); resolveCallback(); },
                            error(err) { customReasonDialog.hide(); frappe.dom.unfreeze(); rejectCallback(err); },
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

    before_cancel(frm) {
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
                        method: "prakash_steel.utils.purchase_invoice_cancel.cancel_purchase_invoice_with_reason",
                        args: {
                            name: frm.doc.name,
                            reason: selectedOption,
                        },
                        freeze: true,
                        freeze_message: __("Cancelling Purchase Invoice..."),
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
                primary_action_label: __("Cancel Purchase Invoice"),
                primary_action(values) {
                    if (!values || !values.cancel_reason) {
                        return;
                    }

                    frappe.call({
                        method: "prakash_steel.utils.purchase_invoice_cancel.cancel_purchase_invoice_with_reason",
                        args: {
                            name: frm.doc.name,
                            reason: values.cancel_reason,
                        },
                        freeze: true,
                        freeze_message: __("Cancelling Purchase Invoice..."),
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

function compute_purchase_invoice_item_gross(row) {
    const taxableValue = flt(row.taxable_value || row.net_amount || row.amount || 0);
    const igstAmount = flt(row.igst_amount || 0);
    const cgstAmount = flt(row.cgst_amount || 0);
    const sgstAmount = flt(row.sgst_amount || 0);
    const gstComponent = igstAmount ? igstAmount : (cgstAmount + sgstAmount);

    return taxableValue + gstComponent;
}

function set_rate_before_discount(cdt, cdn, skip_dirty) {
    // rate_with_margin (the value before discount_amount is subtracted) equals
    // rate + discount_amount once ERPNext's core handlers finish recalculating the row.
    const row = locals[cdt] && locals[cdt][cdn];
    if (!row) return;

    const rateBeforeDiscount = flt(row.rate) + flt(row.discount_amount);
    if (flt(row.custom_rate_before_discount || 0) !== flt(rateBeforeDiscount || 0)) {
        frappe.model.set_value(cdt, cdn, "custom_rate_before_discount", rateBeforeDiscount, null, skip_dirty);
    }
}

function fill_missing_rate_before_discount_for_invoice(frm, skip_dirty) {
    // Rows mapped in from a Purchase Receipt (or other source doc) never fire the
    // item-level rate/discount triggers, so backfill on load same as last-purchase fields.
    (frm.doc.items || []).forEach(function (row) {
        set_rate_before_discount(row.doctype, row.name, skip_dirty);
    });
}

function set_purchase_invoice_item_gross(cdt, cdn) {
    const row = locals[cdt] && locals[cdt][cdn];
    if (!row) return;

    const grossAmount = compute_purchase_invoice_item_gross(row);
    if (flt(row.custom_gross_amount || 0) !== flt(grossAmount || 0)) {
        frappe.model.set_value(cdt, cdn, "custom_gross_amount", grossAmount);
    }
}

function apply_last_purchase_fields_for_invoice_item(cdt, cdn, item, skip_dirty) {
    const row = locals[cdt] && locals[cdt][cdn];
    if (!row) return;

    const next_party = item.last_purchase_party || null;
    const next_date = item.last_purchase_date || null;
    const next_qty = flt(item.last_purchase_quantity || 0);
    const next_rate = flt(item.last_purchase_rate || 0);

    const same_party = (row.custom_last_purchase_party || null) === next_party;
    const same_date = (row.custom_last_purchase_date || null) === (next_date || null);
    const same_qty = flt(row.custom_last_purchase_quantity) === next_qty;
    const same_rate = flt(row.custom_last_purchase_rate) === next_rate;
    if (same_party && same_date && same_qty && same_rate) return;

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
    frappe.model.set_value(
        cdt,
        cdn,
        "custom_last_purchase_rate",
        next_rate,
        null,
        skip_dirty
    );
}

function set_last_purchase_fields_for_invoice_item(cdt, cdn, item_code, skip_dirty) {
    if (!item_code) return;

    frappe.call({
        method: "prakash_steel.api.get_item_insight_data.get_item_insight_data",
        args: { item_code },
        callback: function (r) {
            const items = (r && r.message) ? r.message : [];
            if (!items.length) return;

            apply_last_purchase_fields_for_invoice_item(
                cdt,
                cdn,
                items[0] || {},
                skip_dirty
            );
        },
        error: function () {
            // Keep row editable; don't block invoice entry if the insight API fails.
        },
    });
}

function fill_missing_last_purchase_details_for_invoice(frm, skip_dirty) {
    // Mapped rows (e.g. from Purchase Receipt) never fire item_code, so fill on draft load.
    if (frm.doc.docstatus !== 0) return;

    (frm.doc.items || []).forEach(function (row) {
        if (!row.item_code || row.__pspl_last_purchase_fetched) return;

        if (
            row.custom_last_purchase_party ||
            row.custom_last_purchase_date ||
            flt(row.custom_last_purchase_quantity) ||
            flt(row.custom_last_purchase_rate)
        ) {
            row.__pspl_last_purchase_fetched = true;
            return;
        }

        row.__pspl_last_purchase_fetched = true;
        set_last_purchase_fields_for_invoice_item(
            row.doctype,
            row.name,
            row.item_code,
            skip_dirty
        );
    });
}

frappe.ui.form.on("Purchase Invoice Item", {
    custom_weight_slip_qty(frm) {
        update_weight_slip_totals(frm);
    },
    item_code(frm, cdt, cdn) {
        const row = locals[cdt] && locals[cdt][cdn];
        if (!row) return;
        row.__pspl_last_purchase_fetched = false;
        set_last_purchase_fields_for_invoice_item(cdt, cdn, row.item_code, false);
    },
    qty(frm) {
        update_weight_slip_totals(frm);
    },
    rate(frm, cdt, cdn) {
        set_rate_before_discount(cdt, cdn);
    },
    price_list_rate(frm, cdt, cdn) {
        set_rate_before_discount(cdt, cdn);
    },
    discount_percentage(frm, cdt, cdn) {
        set_rate_before_discount(cdt, cdn);
    },
    discount_amount(frm, cdt, cdn) {
        set_rate_before_discount(cdt, cdn);
    },
    margin_rate_or_amount(frm, cdt, cdn) {
        set_rate_before_discount(cdt, cdn);
    },
    margin_type(frm, cdt, cdn) {
        set_rate_before_discount(cdt, cdn);
    },
    taxable_value(frm, cdt, cdn) {
        set_purchase_invoice_item_gross(cdt, cdn);
    },
    igst_amount(frm, cdt, cdn) {
        set_purchase_invoice_item_gross(cdt, cdn);
    },
    cgst_amount(frm, cdt, cdn) {
        set_purchase_invoice_item_gross(cdt, cdn);
    },
    sgst_amount(frm, cdt, cdn) {
        set_purchase_invoice_item_gross(cdt, cdn);
    },
    amount(frm, cdt, cdn) {
        set_purchase_invoice_item_gross(cdt, cdn);
    },
    net_amount(frm, cdt, cdn) {
        set_purchase_invoice_item_gross(cdt, cdn);
    },
    items_add(frm, cdt, cdn) {
        set_purchase_invoice_item_gross(cdt, cdn);
        set_rate_before_discount(cdt, cdn);
    },
    custom_show_purchase_history(frm, cdt, cdn) {
        const row = locals[cdt] && locals[cdt][cdn];
        if (!row || !row.item_code) {
            frappe.msgprint(__("Please select an Item first."));
            return;
        }

        // The report defaults to the last month only; widen to a year so the
        // history is actually useful.
        frappe.route_options = {
            item_code: row.item_code,
            company: frm.doc.company,
            from_date: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
            to_date: frappe.datetime.get_today(),
        };
        frappe.set_route("query-report", "Item-wise Purchase Register");
    },
});
