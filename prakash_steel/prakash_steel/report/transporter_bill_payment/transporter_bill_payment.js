function syncDateFiltersInUrl(report) {
	var fromDate = report.get_filter_value("from_date");
	var toDate = report.get_filter_value("to_date");
	var supplierInvoiceFromDate = report.get_filter_value("supplier_invoice_from_date");
	var supplierInvoiceToDate = report.get_filter_value("supplier_invoice_to_date");
	var url = new URL(window.location.href);

	if (!fromDate) {
		url.searchParams.delete("from_date");
	}
	if (!toDate) {
		url.searchParams.delete("to_date");
	}
	if (!supplierInvoiceFromDate) {
		url.searchParams.delete("supplier_invoice_from_date");
	}
	if (!supplierInvoiceToDate) {
		url.searchParams.delete("supplier_invoice_to_date");
	}

	var newUrl = url.pathname + (url.search ? url.search : "");
	window.history.replaceState(null, null, newUrl);
}

frappe.query_reports["Transporter Bill Payment"] = {
	filters: [
		{
			fieldname: "invoice_type",
			label: __("Type"),
			fieldtype: "Select",
			options: "\nPurchase\nSale\nSubcontracting Receipt\nSubcontracting Delivery\nInternal Transfer",
			default: "Purchase",
			reqd: 1,
			on_change: function (report) {
				// Ensure columns/data are rebuilt immediately when switching mode.
				report.refresh();
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 0,
			on_change: function (report) {
				syncDateFiltersInUrl(report);
				report.refresh();
			},
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 0,
			on_change: function (report) {
				syncDateFiltersInUrl(report);
				report.refresh();
			},
		},
		{
			fieldname: "supplier_invoice_from_date",
			label: __("Supplier Invoice From Date"),
			fieldtype: "Date",
			reqd: 0,
			on_change: function (report) {
				syncDateFiltersInUrl(report);
				report.refresh();
			},
		},
		{
			fieldname: "supplier_invoice_to_date",
			label: __("Supplier Invoice To Date"),
			fieldtype: "Date",
			reqd: 0,
			on_change: function (report) {
				syncDateFiltersInUrl(report);
				report.refresh();
			},
		},
		{
			fieldname: "transporter_name",
			label: __("Transporter Name"),
			fieldtype: "Link",
			options: "Supplier",
			reqd: 0,
			get_query: function () {
				return {
					filters: {
						is_transporter: 1,
					},
				};
			},
		},
	],

	// Force the DataTable's fixed footer total row for this report only,
	// independent of the "Add Total Row" report field. The footer renders
	// outside the scrollable/sortable body, so it stays pinned to the
	// bottom regardless of sorting, scrolling, or pagination.
	get_datatable_options: function (datatable_options) {
		datatable_options.showTotalRow = true;
		return datatable_options;
	},

	formatter: function (value, row, column, data, default_formatter) {
		// The Total row has no data object; suppress the forced "0.00" that
		// Frappe's default formatter renders for Currency/Float columns we
		// intentionally excluded from the total (via disable_total).
		if (!data && column.disable_total) {
			return "";
		}

		value = default_formatter(value, row, column, data);

		if (column.fieldname === "approval_status" && value === "Approved") {
			value =
				"<div style='text-align:center;color:green;'>" + value + "</div>";
		}

		return value;
	},

	onload: function (report) {
		syncDateFiltersInUrl(report);

		// Frappe sets title / Bootstrap tooltip attributes after render.
		// Strip all tooltip-related attributes with a generous delay.
		function removeTransporterTooltip() {
			var $input = report.page.wrapper
				.find('[data-fieldname="transporter_name"], input[data-fieldname="transporter_name"]');

			$input
				.removeAttr("title")
				.removeAttr("data-original-title")
				.removeAttr("data-bs-original-title")
				.attr("title", "")
				.attr("data-original-title", "")
				.attr("data-bs-original-title", "");

			// Also destroy any Bootstrap tooltip instance attached to it
			try {
				$input.tooltip("dispose");
			} catch (e) { /* ignore if tooltip plugin not active */ }
		}

		// Run at multiple intervals to catch Frappe's late attribute injection
		setTimeout(removeTransporterTooltip, 200);
		setTimeout(removeTransporterTooltip, 600);
		setTimeout(removeTransporterTooltip, 1500);
	},
};

