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





function update_weight_slip_totals(frm) {
    const totalWeightSlipQty = (frm.doc.items || []).reduce((sum, row) => {
        return sum + (flt(row.custom_weight_slip_qty) || 0);
    }, 0);
    const shortageQty = cint(flt(frm.doc.total_qty) - totalWeightSlipQty);

    // On submitted/cancelled docs, update display only (do not mark form "Not Saved")
    const skip_dirty = frm.doc.docstatus !== 0;

    if (flt(frm.doc.custom_total_weight_slip_qty) !== flt(totalWeightSlipQty)) {
        frm.set_value("custom_total_weight_slip_qty", totalWeightSlipQty, undefined, skip_dirty);
    }

    if (cint(frm.doc.custom_shortage_qty) !== shortageQty) {
        frm.set_value("custom_shortage_qty", shortageQty, undefined, skip_dirty);
    }
}

frappe.ui.form.on("Purchase Invoice", {
    onload(frm) {
        update_weight_slip_totals(frm);
    },

    refresh(frm) {
        // Clear cancel reason on amended drafts — the field is copied from the
        // cancelled doc but should not carry over to the new invoice.
        if (frm.doc.amended_from && frm.doc.docstatus === 0 && frm.doc.custom_cancel_reason) {
            frm.set_value("custom_cancel_reason", "");
        }

        update_weight_slip_totals(frm);
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

function set_purchase_invoice_item_gross(cdt, cdn) {
    const row = locals[cdt] && locals[cdt][cdn];
    if (!row) return;

    const grossAmount = compute_purchase_invoice_item_gross(row);
    if (flt(row.custom_gross_amount || 0) !== flt(grossAmount || 0)) {
        frappe.model.set_value(cdt, cdn, "custom_gross_amount", grossAmount);
    }
}

frappe.ui.form.on("Purchase Invoice Item", {
    custom_weight_slip_qty(frm) {
        update_weight_slip_totals(frm);
    },
    qty(frm) {
        update_weight_slip_totals(frm);
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
    },
});
