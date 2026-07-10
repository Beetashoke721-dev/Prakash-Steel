frappe.ui.form.on("Bright Machine Load Snapshot", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Run Manual Snapshot"), () => {
				frappe.call({
					method: "prakash_steel.po_recommendation_history.doctype.bright_machine_load_snapshot.bright_machine_load_snapshot.run_manual_snapshot",
					freeze: true,
					freeze_message: __("Capturing Bright Machine Load data..."),
					callback(r) {
						if (r.message) {
							frappe.set_route("Form", "Bright Machine Load Snapshot", r.message);
						}
					},
				});
			});
		}
	},
});
