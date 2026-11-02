app_name = "prakash_steel"
app_title = "Prakash Steel"
app_publisher = "Beetashoke Chakraborty"
app_description = "Prakash Steel Customizations"
app_email = "beetashoke.chakraborty@clapgrow.com"
app_license = "mit"

# ------------------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------------------

fixtures = [
	{"doctype": "Custom Field", "filters": {"module": "Prakash Steel"}},
]

after_migrate = [
	"prakash_steel.utils.backfill_sales_invoice_sales_order_date.run_after_migrate",
	"prakash_steel.utils.backfill_purchase_order_closed_on.run_after_migrate",
	"prakash_steel.utils.backfill_purchase_order_completed_on.run_after_migrate",
]

# ------------------------------------------------------------------------------
# DocType JavaScript
# ------------------------------------------------------------------------------

doctype_list_js = {
	"JOB Work Order": "prakash_steel/doctype/job_work_order/job_work_order_list.js",
}

doctype_js = {
	"Work Order": "public/js/work_order.js",
	"Material Request": "public/js/material_request.js",
	"Sales Order": "public/js/sales_order.js",
	"Purchase Order": "public/js/purchase_order.js",
	"Purchase Invoice": "public/js/purchase_invoice.js",
	"Payment Entry": "public/js/payment_entry.js",
	"Item": "public/js/item.js",
	"Stock Entry": "public/js/stock_entry.js",
	"Stock Reconciliation": "public/js/stock_reconciliation.js",
	"Purchase Receipt": "public/js/purchase_receipt.js",
	"Job Card": "public/js/job_card.js",
	"Sales Invoice": "public/js/sales_invoice.js",
	"Delivery Note": "public/js/delivery_note.js",
	"Production Plan": "public/js/production_plan.js",
	"Salary Slip": "public/js/salary_slip.js",
	"Customer": "public/js/customer.js",
	# "Payment Reconciliation": "public/js/payment_reconciliation.js",
}

# ------------------------------------------------------------------------------
# Page JavaScript
# ------------------------------------------------------------------------------

page_js = {
	"procurement-tracker-dashboard": "prakash_steel/page/procurement_tracker_dashboard/procurement_tracker_dashboard.js",
	"sales-summary-dashboard": "prakash_steel/page/sales_summary_dashboard/sales_summary_dashboard.js",
	"item-insight-dashboard": "prakash_steel/page/item_insight_dashboard/item_insight_dashboard.js",
	"production-dashboard": "prakash_steel/page/production_dashboard/production_dashboard.js",
}

# ------------------------------------------------------------------------------
# App Include JS
# ------------------------------------------------------------------------------

app_include_js = [
	"/assets/prakash_steel/js/number_cards_uom.js",
	"/assets/prakash_steel/js/attachment_utils.js",
	"/assets/prakash_steel/js/item_row_restriction.js",
]

# ------------------------------------------------------------------------------
# Document Events
# ------------------------------------------------------------------------------

doc_events = {
	"Item": {
		"validate": [
			"prakash_steel.utils.item.calculate_sku_type_on_validate",
			"prakash_steel.utils.item.validate_min_order_qty_and_batch_size",
		],
		"on_update": "prakash_steel.utils.item.update_decoupled_lead_time_on_item_save",
	},
	"Sales Invoice": {
		"on_submit": "prakash_steel.utils.job_work_order_utils.update_jwo_on_sales_invoice_submit",
		"on_cancel": "prakash_steel.utils.job_work_order_utils.update_jwo_on_sales_invoice_submit",
	},
	"Delivery Note": {
		"on_submit": "prakash_steel.utils.job_work_order_utils.update_jwo_on_delivery_note_submit",
		"on_cancel": "prakash_steel.utils.job_work_order_utils.update_jwo_on_delivery_note_submit",
	},
	"BOM": {
		"on_submit": "prakash_steel.utils.item.update_decoupled_lead_time_on_bom_save",
		"on_update_after_submit": "prakash_steel.utils.item.update_decoupled_lead_time_on_bom_save",
	},
	"Purchase Receipt": {
		"validate": "prakash_steel.utils.purchase_receipt.validate_transporter_for_psp_freight",
		"before_submit": "prakash_steel.utils.attachment_validation.validate_mandatory_attachment",
		"on_submit": [
			"prakash_steel.utils.purchase_receipt.validate_purchase_receipt_quantity",
			"prakash_steel.utils.job_work_order_utils.update_jwo_on_purchase_receipt_submit",
		],
		"on_cancel": "prakash_steel.utils.job_work_order_utils.update_jwo_on_purchase_receipt_submit",
		"before_cancel": "prakash_steel.utils.purchase_receipt_cancel.validate_cancel_reason",
	},
	"Work Order": {
		"validate": [
			"prakash_steel.utils.work_order.validate_production_type",
			"prakash_steel.utils.work_order.validate_miss_billet_weight",
			"prakash_steel.utils.work_order.calculate_custom_wastage",
			"prakash_steel.utils.work_order.calculate_cutting_weight_for_rolled_production",
			"prakash_steel.utils.work_order.calculate_total_raw_material_pcs",
			"prakash_steel.utils.work_order.calculate_burning_loss_for_rolled_production",
		],
	},
	"Stock Entry": {
		"on_submit": "prakash_steel.utils.work_order.update_custom_wastage_after_stock_entry",
		"on_cancel": "prakash_steel.utils.work_order.update_custom_wastage_after_stock_entry",
	},
	"Stock Reconciliation": {
		"validate": "prakash_steel.utils.stock_reconciliation.set_total_quantity_and_amount",
	},
	"Job Card": {
		"after_insert": "prakash_steel.utils.work_order.copy_production_type_to_job_card",
		"before_validate": "prakash_steel.utils.work_order.prepare_job_card_completed_qty",
		"on_submit": "prakash_steel.utils.work_order.submit_manufacture_stock_entry_for_job_card",
		"validate": [
			"prakash_steel.utils.work_order.lock_production_type_from_work_order",
			"prakash_steel.utils.work_order.validate_job_card_time_log_miss_fields",
			"prakash_steel.utils.work_order.calculate_job_card_total_completed_qty",
			"prakash_steel.utils.work_order.calculate_job_card_finish_pcs",
			"prakash_steel.utils.work_order.calculate_job_card_miss_pcs",
			"prakash_steel.utils.work_order.calculate_job_card_fg_per_pcs_weight",
			"prakash_steel.utils.work_order.set_job_card_colour_code",
			"prakash_steel.utils.work_order.calculate_job_card_billet_weight",
			"prakash_steel.utils.work_order.calculate_job_card_time_log_billet_cutting",
		],
	},
	"Production Plan": {
		"on_submit": "prakash_steel.prakash_steel.utils.production_plan.on_production_plan_submit",
	},
	"Sales Order": {
		"before_cancel": "prakash_steel.utils.sales_order_cancel.validate_cancel_reason",
		"validate": "prakash_steel.utils.order_validation.validate_no_zero_rate_items",
		"before_submit": "prakash_steel.utils.sales_order_rate_floor.validate_item_rate_floor",
		"before_update_after_submit": [
			"prakash_steel.utils.order_validation.validate_no_zero_rate_items",
			"prakash_steel.utils.sales_order_rate_floor.validate_item_rate_floor",
		],
	},
	"Purchase Order": {
		"before_cancel": "prakash_steel.utils.purchase_order_cancel.validate_cancel_reason",
		"validate": "prakash_steel.utils.order_validation.validate_no_zero_rate_items",
		"before_update_after_submit": "prakash_steel.utils.order_validation.validate_no_zero_rate_items",
		"on_change": [
			"prakash_steel.utils.purchase_order.set_custom_closed_on",
			"prakash_steel.utils.purchase_order.set_custom_completed_on",
		],
	},
	"Purchase Invoice": {
		"before_cancel": "prakash_steel.utils.purchase_invoice_cancel.validate_cancel_reason",
		"validate": [
			"prakash_steel.utils.purchase_invoice_cancel.clear_cancel_reason_on_amend",
			"prakash_steel.utils.purchase_invoice_cancel.update_gross_amount_on_items",
			"prakash_steel.utils.purchase_invoice_cancel.update_total_weight_slip_qty",
		],
	},
	"Payment Entry": {
		"validate": "prakash_steel.utils.payment_entry.set_invoice_date_on_references",
		"on_submit": "prakash_steel.utils.payment_entry.set_submitted_time",
	},
	"Material Request": {
		"before_cancel": "prakash_steel.utils.material_request_cancel.validate_cancel_reason",
	},
	"Customer": {
		"validate": "prakash_steel.utils.party.warn_if_party_details_missing",
	},
	"Supplier": {
		"validate": "prakash_steel.utils.party.warn_if_party_details_missing",
	},
	"File": {
		"on_trash": "prakash_steel.utils.attachment_validation.prevent_protected_attachment_deletion",
	},
}

# ------------------------------------------------------------------------------
# Scheduler Events
# ------------------------------------------------------------------------------

scheduler_events = {
	"cron": {
		# Sync ESSL biometric punches daily at 10:30 AM (syncs yesterday's full day).
		"30 10 * * *": ["prakash_steel.utils.essl_biometric.sync_essl_checkins_morning"],
		# Re-sync the same "yesterday" a second time at 6 PM: a shift that
		# checks out well into the next afternoon (e.g. Night Shift 8 PM ->
		# 2 PM next day) hasn't punched OUT yet at the 10:30 AM run, so that
		# run alone would leave the employee marked Absent. This pass picks
		# such punches up and flips the existing Attendance to Present -
		# sync_essl_checkins() with no args always resolves "yesterday"
		# relative to when it runs, so both crons target the same date.
		#
		# This MUST be a different method than the 10:30 AM entry above, even
		# though both just call sync_essl_checkins(). Frappe's scheduler keys
		# "Scheduled Job Type" by method name alone, so the same method under
		# two cron entries collides: whichever migrate runs last overwrites
		# the other's cron_format on the SAME record, and the other time never
		# actually gets scheduled. See the note above
		# sync_essl_checkins_morning/_evening in essl_biometric.py.
		"0 18 * * *": ["prakash_steel.utils.essl_biometric.sync_essl_checkins_evening"],
		# Runs daily at 14:52 server time
		"05 08 * * *": [
			"prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp.save_daily_on_hand_colour"
		],
		# Saves each Non-Buffer (MTO) item's SKU type daily, for the weekly register's MTO inventory
		"27 11 * * *": [
			"prakash_steel.prakash_steel.doctype.item_wise_daily_mto_sku.item_wise_daily_mto_sku.save_daily_mto_sku"
		],
		# Saves each Bright Machine's Net Order Load daily, for the weekly register
		"30 14 * * *": [
			"prakash_steel.prakash_steel.doctype.item_wise_daily_bright_machine_load.item_wise_daily_bright_machine_load.save_daily_bright_machine_load"
		],
		# Saves each Bright and Rolled Critical Spares item's On Hand Colour daily, for the weekly register
		"00 14 * * *": [
			"prakash_steel.prakash_steel.doctype.item_wise_daily_cs_colour.item_wise_daily_cs_colour.save_daily_cs_colour"
		],
		# Sends daily Sales Invoice summary email at 11:58 PM
		"58 23 * * *": ["prakash_steel.utils.daily_sales_invoice_email.send_daily_sales_invoice_email"],
		# Sends yesterday Payment Entry report daily at 1:25 PM
		"01 11 * * *": ["prakash_steel.utils.daily_payment_entry_email.send_daily_payment_entry_email"],
		# Captures PO Recommendation Snapshot daily at 2:06 PM
		"00 04 * * *": [
			"prakash_steel.po_recommendation_history.doctype.po_recommendation_snapshot.po_recommendation_snapshot.capture_daily_po_snapshot"
		],
		# Captures SO Recommendation Snapshot daily at 4:30 PM IST
		"01 04 * * *": [
			"prakash_steel.prakash_steel.doctype.so_recommendation_snapshot.so_recommendation_snapshot.capture_daily_so_snapshot"
		],
		# Captures Stock Balance Snapshot (Item Wise Stock Balance) daily, after SO snapshot
		"02 04 * * *": [
			"prakash_steel.prakash_steel.doctype.stock_balance_snapshot.stock_balance_snapshot.capture_daily_stock_balance_snapshot"
		],
		# Captures Purchase Order Recommendation Snapshot daily at 4:00 PM IST
		"03 04 * * *": ["prakash_steel.utils.po_rec_snapshot.capture_daily_po_rec_snapshot"],
		# Captures Bright Machine Load Snapshot daily at 4:30 AM IST
		"04 04 * * *": [
			"prakash_steel.po_recommendation_history.doctype.bright_machine_load_snapshot.bright_machine_load_snapshot.capture_daily_snapshot"
		],
		# Saves each Bright / Rolled / BO / Traded item's Free Stock daily
		"06 04 * * *": [
			"prakash_steel.prakash_steel.doctype.item_wise_daily_free_stock.item_wise_daily_free_stock.save_daily_free_stock"
		],
		# Sends Rolled Bar / Bright Bar Production Dashboard summary daily at 4:00 PM IST
		# (server local time). Covers yesterday's production, except: Sunday sends nothing
		# (factory closed), and Monday covers Saturday's production instead.
		"00 16 * * *": [
			"prakash_steel.utils.daily_production_dashboard_email.send_daily_production_dashboard_email"
		],
	},
	# Recalculate ADU for all items once per day so Item.custom_adu stays in sync
	"daily": [
		"prakash_steel.prakash_steel.api.adu.recalculate_adu_for_all_items",
		# "prakash_steel.prakash_steel.doctype.unsecured_loans_and_transaction.unsecured_loans_and_transaction.fetch_daily_interest_for_all_active_docs",
		# "prakash_steel.prakash_steel.doctype.unsecured_loans_and_transaction.unsecured_loans_and_transaction.fetch_daily_interest_for_all_active_docs",
	],
}

# ------------------------------------------------------------------------------
# Override DocType Class
# ------------------------------------------------------------------------------

override_doctype_class = {
	"Stock Entry": "prakash_steel.overrides.stock_entry.CustomStockEntry",
	"Payment Reconciliation": "prakash_steel.overrides.payment_reconciliation.CustomPaymentReconciliation",
	"Sales Invoice": "prakash_steel.overrides.sales_invoice.CustomSalesInvoice",
}

# ------------------------------------------------------------------------------
# Override Whitelisted Methods
# ------------------------------------------------------------------------------

override_whitelisted_methods = {
	"erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice": "prakash_steel.utils.sales_order.make_sales_invoice",
	"erpnext.selling.doctype.sales_order.sales_order.make_delivery_note": "prakash_steel.utils.sales_order.make_delivery_note",
	"erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice": "prakash_steel.utils.delivery_note.make_sales_invoice",
	"erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt": "prakash_steel.utils.purchase_order.make_purchase_receipt",
	"erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice": "prakash_steel.utils.purchase_invoice.make_purchase_invoice",
	# Ensure our custom_cancel_reason validation doesn't block e-Invoice cancellation
	"india_compliance.gst_india.utils.e_invoice.cancel_e_invoice": "prakash_steel.utils.e_invoice.cancel_e_invoice",
	# Inject custom_invoice_date (= invoice posting_date) into the reference-details
	# response so it populates alongside due_date when a reference is picked.
	"erpnext.accounts.doctype.payment_entry.payment_entry.get_reference_details": "prakash_steel.utils.payment_entry.get_reference_details",
	# Notify pratikshyagochhayat@clapgrow.com whenever items are edited via the
	# "Update Items" dialog on Sales Order / Purchase Order.
	"erpnext.controllers.accounts_controller.update_child_qty_rate": "prakash_steel.utils.order_item_update_notification.update_child_qty_rate",
}
