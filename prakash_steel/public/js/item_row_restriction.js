frappe.provide("prakash_steel.item_row_restriction");

prakash_steel.item_row_restriction = {
	_enabled_promise: null,

	is_enabled() {
		if (!this._enabled_promise) {
			this._enabled_promise = new Promise((resolve) => {
				frappe.call({
					method: "prakash_steel.utils.item_row_restriction.get_item_row_restriction_setting",
					args: {},
					callback(r) {
						resolve(Boolean(r && r.message && r.message.enabled));
					},
					error() {
						resolve(false);
					},
				});
			});
		}
		return this._enabled_promise;
	},

	// Toggle whether the items table's "Add Row" button (and the entry it
	// creates) is available, based on the `Item Row Restriction Setting`
	// single doctype checkbox. When disabled, default grid behaviour applies.
	apply(frm) {
		this.is_enabled().then((enabled) => {
			const grid = frm.get_field("items")?.grid;
			if (!grid) {
				return;
			}

			grid.cannot_add_rows = enabled;

			if (enabled) {
				// Frappe auto-inserts one blank row for mandatory (reqd) Table
				// fields on a new document; that row's Item cell is still
				// editable and lets users pick an item manually, bypassing the
				// "Add Row" restriction above. Drop it.
				if (frm.is_new() && (frm.doc.items || []).length === 1) {
					const [row] = frm.doc.items;
					if (row && !row.item_code && !row.item_name) {
						frm.doc.items = [];
					}
				}
			}

			grid.refresh();
		});
	},
};
