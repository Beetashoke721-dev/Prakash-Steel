frappe.ui.form.on("Customer", {
	refresh(frm) {
		const field = frm.get_field("customer_name");
		if (!field || !field.$input || field.__pspl_blur_bound) {
			return;
		}

		field.__pspl_blur_bound = true;
		field.$input.on("blur", () => {
			// After leaving Customer Name, copy it into Customer Group Name
			// if that field is still empty. User can change it afterwards.
			if (frm.doc.customer_name && !frm.doc.custom_customer_group_name) {
				frm.set_value("custom_customer_group_name", frm.doc.customer_name);
			}
		});
	},
});
