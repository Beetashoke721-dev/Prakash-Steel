frappe.listview_settings["Bright Machine Load Snapshot"] = {
	onload(listview) {
		listview.page.add_action_item(__("Capture Snapshot Now"), function () {
			frappe.confirm(
				__("Capture a fresh Bright Machine Load snapshot now?"),
				function () {
					frappe.show_alert({ message: __("Capturing snapshot..."), indicator: "blue" });
					frappe.call({
						method: "prakash_steel.po_recommendation_history.doctype.bright_machine_load_snapshot.bright_machine_load_snapshot.run_manual_snapshot",
						callback(r) {
							if (r.message) {
								frappe.set_route("Form", "Bright Machine Load Snapshot", r.message);
							}
						},
					});
				}
			);
		});
	},

	get_indicator(doc) {
		if (doc.status === "Success") return [__("Success"), "green", "status,=,Success"];
		if (doc.status === "Failed") return [__("Failed"), "red", "status,=,Failed"];
	},
};
