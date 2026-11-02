function setup_attachment_guard(frm) {
	prakash_steel.attachment_utils.prevent_attachment_deletion(frm);
}

frappe.ui.form.on("Sales Invoice", {
    onload(frm) {
        setup_sales_order_row_guard(frm);
        prakash_steel.item_row_restriction.apply(frm);
        toggle_payment_terms_template_mandatory(frm);
        if (frm.is_new() && frm.doc.company) {
            fetch_dispatch_address(frm);
        }
    },
    refresh(frm) {
        setup_attachment_guard(frm);

        setup_sales_order_row_guard(frm);
        prakash_steel.item_row_restriction.apply(frm);
        toggle_payment_terms_template_mandatory(frm);

        if (frm.is_new() && !frm.doc.dispatch_address_name) {
            fetch_dispatch_address(frm);
        }

        // When a new amendment is opened, clear fields that must not carry over
        if (frm.is_new() && frm.doc.amended_from) {
            if (frm.doc.custom_stock_entry_id) {
                frm.set_value("custom_stock_entry_id", "");
            }
            if (frm.doc.custom_cancel_reason) {
                frm.set_value("custom_cancel_reason", "");
            }
        }

        // e-Invoice flow: collect NIC reason + our internal reason, then cancel IRN/e-Waybill & Invoice
        if (frm.doc.docstatus === 1 && frm.doc.irn) {
            frm.add_custom_button(
                __("Cancel IRN/e-Waybill & Invoice (Internal Reason)"),
                () => pspl_cancel_e_invoice_with_internal_reason(frm),
                __("e-Invoice")
            );
        }
    },
    is_return(frm) {
        toggle_payment_terms_template_mandatory(frm);
    },
    is_pos(frm) {
        toggle_payment_terms_template_mandatory(frm);
    },
    before_cancel(frm) {
        // If IRN exists, India Compliance handles the cancellation flow (incl. IRN/e-Waybill cancel dialog).
        // Our custom cancel flow should not run in that case.
        if (frm.doc.irn) {
            return;
        }

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
                    showCustomReasonDialog(frm, selectedOption);
                } else {
                    // For other options: save the reason label directly and cancel
                    reasonOptionsDialog.hide();
                    frappe.call({
                        method: "prakash_steel.utils.sales_invoice_cancel.cancel_sales_invoice_with_reason",
                        args: {
                            name: frm.doc.name,
                            reason: selectedOption,
                        },
                        freeze: true,
                        freeze_message: __("Cancelling Sales Invoice..."),
                        callback() {
                            frm.reload_doc();
                        },
                    });
                }
            },
        });

        // Function to show the custom reason dialog (for "Others" / Party Name Mistake)
        function showCustomReasonDialog(frm, selectedOption) {
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
                primary_action_label: __("Cancel Invoice"),
                primary_action(values) {
                    if (!values || !values.cancel_reason) {
                        return;
                    }

                    frappe.call({
                        method: "prakash_steel.utils.sales_invoice_cancel.cancel_sales_invoice_with_reason",
                        args: {
                            name: frm.doc.name,
                            reason: `${selectedOption}, ${values.cancel_reason}`,
                        },
                        freeze: true,
                        freeze_message: __("Cancelling Sales Invoice..."),
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

async function pspl_cancel_e_invoice_with_internal_reason(frm) {
    const d = new frappe.ui.Dialog({
        title: frm.doc.ewaybill ? __("Cancel e-Invoice and e-Waybill") : __("Cancel e-Invoice"),
        fields: [
            {
                label: __("IRN Number"),
                fieldname: "irn",
                fieldtype: "Data",
                read_only: 1,
                default: frm.doc.irn,
            },
            {
                label: __("e-Waybill Number"),
                fieldname: "ewaybill",
                fieldtype: "Data",
                read_only: 1,
                default: frm.doc.ewaybill || "",
            },
            {
                label: __("Reason (e-Invoice)"),
                fieldname: "reason",
                fieldtype: "Select",
                reqd: 1,
                default: "Data Entry Mistake",
                options: ["Duplicate", "Data Entry Mistake", "Order Cancelled", "Others"],
            },
            {
                label: __("Remark (required if e-Invoice reason is Others)"),
                fieldname: "remark",
                fieldtype: "Data",
                reqd: 0,
                mandatory_depends_on: "eval: doc.reason == 'Others'",
            },
            { fieldtype: "Section Break", label: __("Internal Cancel Reason") },
            {
                fieldname: "internal_reason_option",
                label: __("Cancel Reason"),
                fieldtype: "Select",
                options: ["Party Name Mistake", "Rate Mistake", "Size Mistake", "Others"],
                reqd: 1,
            },
            {
                fieldname: "internal_reason_text",
                label: __("Remark (required for Party Name Mistake / Others)"),
                fieldtype: "Small Text",
                depends_on:
                    "eval: doc.internal_reason_option == 'Others' || doc.internal_reason_option == 'Party Name Mistake'",
            },
        ],
        primary_action_label: frm.doc.ewaybill
            ? __("Cancel IRN, e-Waybill & Invoice")
            : __("Cancel IRN & Invoice"),
        primary_action: async (values) => {
            if (!values?.reason) return;
            if (!values?.internal_reason_option) return;

            const internal_needs_text =
                values.internal_reason_option === "Others" ||
                values.internal_reason_option === "Party Name Mistake";

            const extra_text = (values.internal_reason_text || "").trim();
            if (internal_needs_text && !extra_text) {
                frappe.msgprint({
                    title: __("Cancel Reason Required"),
                    message: __("Please enter remark for selected internal cancel reason."),
                    indicator: "red",
                });
                return;
            }

            const internal_reason = internal_needs_text
                ? `${values.internal_reason_option}, ${extra_text}`
                : values.internal_reason_option;

            await frappe.call({
                method: "prakash_steel.utils.e_invoice.cancel_e_invoice",
                args: {
                    docname: frm.doc.name,
                    values: {
                        reason: values.reason,
                        remark: values.remark,
                        custom_cancel_reason: internal_reason,
                    },
                },
                freeze: true,
                freeze_message: __("Cancelling IRN/e-Waybill and Invoice..."),
            });

            d.hide();
            frm.reload_doc();
        },
    });

    d.show();

    $(`
        <div class="alert alert-warning" role="alert">
            ${__("Sales invoice will be cancelled along with the IRN.")}
        </div>
    `).prependTo(d.wrapper);
}

function toggle_payment_terms_template_mandatory(frm) {
	// Credit notes / POS hide this field; keep it optional there.
	const required = !(cint(frm.doc.is_return) || cint(frm.doc.is_pos));
	frm.toggle_reqd("payment_terms_template", required);
}

function fetch_dispatch_address(frm) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Address",
            filters: [
                ["address_title", "=", "Prakash Steel Products Pvt Ltd"],
                ["is_shipping_address", "=", 1]
            ],
            fields: ["name"],
            limit: 1
        },
        callback: function (r) {
            if (r.message && r.message.length > 0) {
                frm.set_value("dispatch_address_name", r.message[0].name);
            }
        }
    });
}

function setup_sales_order_row_guard(frm) {
    const grid = frm.get_field("items")?.grid;
    if (!grid || grid.__pspl_row_guard_attached) {
        return;
    }

    grid.__pspl_row_guard_attached = true;

    const original_add_new_row = grid.add_new_row.bind(grid);
    grid.add_new_row = function (idx, callback, show) {
        const hasSalesOrderRows = (frm.doc.items || []).some(
            (d) => d.sales_order
        );

        // Only enforce when the invoice is Sales Order–based
        if (!hasSalesOrderRows) {
            return original_add_new_row(idx, callback, show);
        }

        frappe.msgprint({
            title: __("Not Allowed"),
            message: __(
                "Only items linked to Sales Order are allowed in this Sales Invoice."
            ),
            indicator: "red",
        });
    };
}
