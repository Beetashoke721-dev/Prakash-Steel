import frappe


def execute() -> tuple[list, list]:
	if frappe.db.exists("Client Script", "SO Recommendation Snapshot-so-snap-buttons"):
		return

	script = (
		'frappe.ui.form.on("SO Recommendation Snapshot", {\n'
		'	refresh(frm) {\n'
		'		if (!frm.is_new()) {\n'
		'			frm.add_custom_button(__("Run Manual Snapshot"), () => {\n'
		'				frappe.call({\n'
		'					method: "prakash_steel.prakash_steel.doctype.so_recommendation_snapshot.so_recommendation_snapshot.run_manual_snapshot",\n'
		'					freeze: true,\n'
		'					freeze_message: __("Capturing SO Recommendation data..."),\n'
		'					callback(r) {\n'
		'						if (r.message) {\n'
		'							frappe.set_route("Form", "SO Recommendation Snapshot", r.message);\n'
		'						}\n'
		'					},\n'
		'				});\n'
		'			});\n'
		'		}\n'
		'	},\n'
		'});\n'
	)

	doc = frappe.new_doc("Client Script")
	doc.name = "SO Recommendation Snapshot-so-snap-buttons"
	doc.dt = "SO Recommendation Snapshot"
	doc.script = script
	doc.enabled = 1
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
