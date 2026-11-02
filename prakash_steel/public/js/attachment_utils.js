frappe.provide("prakash_steel.attachment_utils");

const PROTECTED_ATTACHMENT_DOCTYPES = [
	"Sales Invoice",
	"Purchase Receipt",
	"Stock Entry",
];

prakash_steel.attachment_utils = {
	should_prevent_attachment_deletion(frm) {
		return PROTECTED_ATTACHMENT_DOCTYPES.includes(frm.doctype);
	},

	prevent_attachment_deletion(frm) {
		if (!frm.attachments || !this.should_prevent_attachment_deletion(frm)) {
			return;
		}

		if (frm.attachments.__pspl_delete_guard) {
			return;
		}

		frm.attachments.__pspl_delete_guard = true;
		const original_remove_attachment = frm.attachments.remove_attachment.bind(
			frm.attachments
		);

		frm.attachments.remove_attachment = function (fileid, callback) {
			return frappe.call({
				method: "prakash_steel.utils.attachment_validation.can_delete_protected_attachment",
				args: { file_id: fileid },
				callback(r) {
					if (r.message === false) {
						frappe.msgprint({
							title: __("Attachment Deletion Not Allowed"),
							message: __("Attachments cannot be deleted after 24 hours."),
							indicator: "red",
						});
						return;
					}

					original_remove_attachment(fileid, callback);
				},
			});
		};
	},
};
