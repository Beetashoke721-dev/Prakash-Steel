// Copyright (c) 2025, beetashoke chakraborty and contributors
// For license information, please see license.txt

function update_total_party_billing_qty(frm) {
    // Submitted/cancelled docs are immutable; re-setting the total here would
    // mark the form dirty and fail with "Not allowed to change ... after submission".
    if (frm.doc.docstatus !== 0) {
        return;
    }

    // Round to the field precision to avoid float noise (3130.3999999999996).
    const precision = frappe.meta.get_field_precision
        ? frappe.meta.get_field_precision(frm.fields_dict.custom_total_party_billing_qty.df, frm.doc)
        : 2;
    const total = flt(
        (frm.doc.items || []).reduce((sum, row) => sum + (flt(row.custom_party_billing_qty) || 0), 0),
        precision
    );

    if (flt(frm.doc.custom_total_party_billing_qty, precision) !== total) {
        frm.set_value("custom_total_party_billing_qty", total);
    }
}

function toggle_transporter_mandatory(frm) {
    if (!frm.fields_dict.transporter) {
        return;
    }

    const is_psp = frm.doc.custom_freight_payable_by === "PSP";
    frm.set_df_property("transporter", "reqd", is_psp ? 1 : 0);
}

function setup_attachment_guard(frm) {
	prakash_steel.attachment_utils.prevent_attachment_deletion(frm);
}

frappe.ui.form.on('Purchase Receipt', {
    onload(frm) {
        update_total_party_billing_qty(frm);
        toggle_transporter_mandatory(frm);
    },

    refresh: function (frm) {
        setup_attachment_guard(frm);

        // Clear cancel reason on amended drafts
        if (frm.doc.amended_from && frm.doc.docstatus === 0 && frm.doc.custom_cancel_reason) {
            frm.set_value("custom_cancel_reason", "");
        }

        update_total_party_billing_qty(frm);
        toggle_transporter_mandatory(frm);
    },

    custom_freight_payable_by(frm) {
        toggle_transporter_mandatory(frm);
    },

    validate(frm) {
        if (frm.doc.custom_freight_payable_by === "PSP") {
            if (!frm.doc.transporter || (typeof frm.doc.transporter === "string" && !frm.doc.transporter.trim())) {
                frappe.msgprint({
                    title: __("Validation Error"),
                    indicator: "red",
                    message: __("Transporter is mandatory when Freight Payable By is PSP."),
                });
                frappe.validated = false;
            }
        }
    },

    on_submit: function (frm) {
        // Client-side notification after submit
        // The server-side hook will handle the email notification
        frappe.show_alert({
            message: __('Purchase Receipt submitted. Quantity validation will be performed.'),
            indicator: 'green'
        }, 3);
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
                        method: "prakash_steel.utils.purchase_receipt_cancel.cancel_purchase_receipt_with_reason",
                        args: {
                            name: frm.doc.name,
                            reason: selectedOption,
                        },
                        freeze: true,
                        freeze_message: __("Cancelling Purchase Receipt..."),
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
                primary_action_label: __("Cancel Purchase Receipt"),
                primary_action(values) {
                    if (!values || !values.cancel_reason) {
                        return;
                    }

                    frappe.call({
                        method: "prakash_steel.utils.purchase_receipt_cancel.cancel_purchase_receipt_with_reason",
                        args: {
                            name: frm.doc.name,
                            reason: values.cancel_reason,
                        },
                        freeze: true,
                        freeze_message: __("Cancelling Purchase Receipt..."),
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

    items_add(frm) {
        update_total_party_billing_qty(frm);
    },

    items_remove(frm) {
        update_total_party_billing_qty(frm);
    },
});

frappe.ui.form.on('Purchase Receipt Item', {
    custom_party_billing_qty(frm) {
        update_total_party_billing_qty(frm);
    },
});

// Note: Client-side validation for PO quantity is handled server-side
// to avoid permission issues with child doctypes (Purchase Order Item)
// The server-side validation in purchase_receipt.py will check quantities
// and send email notifications when threshold is exceeded

