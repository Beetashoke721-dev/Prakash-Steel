frappe.ui.form.on("Delivery Note", {
    onload(frm) {
        prakash_steel.item_row_restriction.apply(frm);
    },
    refresh(frm) {
        prakash_steel.item_row_restriction.apply(frm);
    },
});
