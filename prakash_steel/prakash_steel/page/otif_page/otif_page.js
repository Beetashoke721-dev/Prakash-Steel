frappe.pages["otif-page"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("OTIF"),
		single_column: true,
	});

	const add = (df) => page.add_field(df);
	const filters = {
		company: add({
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_default("company"),
		}),
		from_date: add({ fieldname: "from_date", label: __("From Date"), fieldtype: "Date" }),
		to_date: add({ fieldname: "to_date", label: __("To Date"), fieldtype: "Date" }),
		customer: add({ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" }),
		item_code: add({ fieldname: "item_code", label: __("Item Code"), fieldtype: "Link", options: "Item" }),
		sales_order: add({ fieldname: "sales_order", label: __("Sales Order"), fieldtype: "Link", options: "Sales Order" }),
		status: add({
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "To Pay", "To Bill", "To Deliver", "To Deliver and Bill", "Completed", "Closed"].join("\n"),
		}),
	};

	$(`<style>
		.otif-table .dt-header .dt-cell { background: #eef2ff; color: #3730a3; font-weight: 600; }
		.otif-badge { display: inline-block; padding: 1px 10px; border-radius: 999px; font-weight: 600; font-size: 11.5px; }
		.otif-good { background: #dcfce7; color: #166534; }
		.otif-bad { background: #fee2e2; color: #991b1b; }
		.otif-warn { background: #fef3c7; color: #92400e; }
		.otif-info { background: #dbeafe; color: #1e40af; }
		.otif-summary { width: auto; margin-bottom: 15px; border-collapse: collapse; }
		.otif-summary th, .otif-summary td { border: 1px solid #d1d5db; padding: 6px 16px; }
		.otif-summary th { background: #eef2ff; color: #3730a3; }
		.otif-clr-black { background: #111827; color: #fff; }
		.otif-clr-red { background: #fee2e2; color: #991b1b; }
		.otif-clr-yellow { background: #fef3c7; color: #92400e; }
		.otif-clr-green { background: #dcfce7; color: #166534; }
		.otif-clr-white { background: #f8fafc; color: #334155; border: 1px solid #cbd5e1; }
	</style>`).appendTo(page.main);
	const $summary = $('<table class="otif-summary"><thead><tr>'
		+ `<th>${__("Business Measures")}</th><th>${__("Percentage")}</th>`
		+ '</tr></thead><tbody>'
		+ `<tr><td>${__("OTIF")}</td><td class="otif-summary-all"></td></tr>`
		+ `<tr><td>${__("Bright OTIF")}</td><td class="otif-summary-bb"></td></tr>`
		+ `<tr><td>${__("Rolled OTIF")}</td><td class="otif-summary-rb"></td></tr>`
		+ '</tbody></table>').appendTo(page.main);
	const $table = $('<div class="otif-table"></div>').appendTo(page.main);

	// Colour bands come from OTIF Colour Master (child table: colour, from_percent, to_percent).
	// A row matches when from_percent <= pct < to_percent; a row whose to_percent is <= its
	// from_percent (e.g. Green 90-0) has no upper bound and matches pct >= from_percent.
	let colour_bands = [];
	const colour_bands_ready = frappe.call({ method: "frappe.client.get", args: { doctype: "OTIF Colour Master" } }).then((r) => {
		colour_bands = ((r.message && r.message.table_igke) || []).map((row) => ({
			colour: row.colour,
			from_percent: flt(row.from_percent),
			to_percent: flt(row.to_percent),
		}));
	});

	const colour_class = (pct) => {
		for (const band of colour_bands) {
			const open_ended = band.to_percent <= band.from_percent;
			if (pct >= band.from_percent && (open_ended || pct < band.to_percent)) {
				return `otif-clr-${band.colour.toLowerCase()}`;
			}
		}
		return "otif-info";
	};

	// Same logic as the report's per-week line percentage (see add_week_percentages
	// in otif_report.py), grouped by item_type over the whole period instead of by week.
	const compute_pct = (rows, item_type) => {
		let book_total = 0;
		let line_total = 0;
		for (const row of rows) {
			if (item_type && row.item_type !== item_type) continue;
			book_total += flt(row.book_value);
			if (row.line_otif === 100) line_total += flt(row.sales_value);
		}
		return book_total ? flt((line_total / book_total) * 100) : 0;
	};
	const pct_badge = (pct) => badge(colour_class(pct), `${pct.toFixed(2)}%`);

	const badge = (cls, text) => `<span class="otif-badge ${cls}">${frappe.utils.escape_html(text ?? "")}</span>`;
	const status_class = {
		Completed: "otif-good",
		"To Deliver": "otif-warn",
		"To Deliver and Bill": "otif-warn",
		"To Bill": "otif-info",
		"To Pay": "otif-bad",
	};

	const format = (column) => (value) => {
		if (value === null || value === undefined || value === "") return "";
		switch (column.fieldname) {
			case "line_otif":
			case "order_otif":
				return badge(value === 100 ? "otif-good" : "otif-bad", `${value}%`);
			case "status":
				return badge(status_class[value] || "", value);
			case "pending_qty":
				return badge(value > 0 ? "otif-bad" : "otif-good", value);
		}
		if (column.fieldtype === "Date") return frappe.datetime.str_to_user(value);
		return frappe.utils.escape_html(value);
	};

	let datatable;
	let last_rows = [];
	let last_summary = [];
	const load = () => {
		const values = {};
		for (const [key, field] of Object.entries(filters)) {
			const v = field.get_value();
			if (v) values[key] = key === "status" || key === "sales_order" ? [v] : v;
		}
		if (!values.company) return frappe.msgprint(__("Please select a Company"));

		frappe.call({
			method: "frappe.desk.query_report.run",
			args: { report_name: "OTIF Report", filters: values },
			freeze: true,
			freeze_message: __("Loading OTIF..."),
			callback: (r) => {
				const res = r.message || {};
				const columns = (res.columns || [])
					.filter((c) => !c.hidden && !["line_percentage", "order_percentage"].includes(c.fieldname))
					.map((c) => ({
						id: c.fieldname,
						name: __(c.label),
						width: c.width || 120,
						editable: false,
						format: format(c),
					}));
				const data = res.result || [];
				last_rows = data;
				const otif_pct = compute_pct(data, null);
				const bb_pct = compute_pct(data, "BB");
				const rb_pct = compute_pct(data, "RB");
				last_summary = [
					{ label: __("OTIF"), percentage: otif_pct.toFixed(2) },
					{ label: __("Bright OTIF"), percentage: bb_pct.toFixed(2) },
					{ label: __("Rolled OTIF"), percentage: rb_pct.toFixed(2) },
				];
				$summary.find(".otif-summary-all").html(pct_badge(otif_pct));
				$summary.find(".otif-summary-bb").html(pct_badge(bb_pct));
				$summary.find(".otif-summary-rb").html(pct_badge(rb_pct));
				if (datatable) return datatable.refresh(data, columns);
				datatable = new frappe.DataTable($table[0], {
					columns,
					data,
					inlineFilters: true,
					layout: "fixed",
					cellHeight: 34,
					noDataMessage: __("No data"),
				});
			},
		});
	};

	page.add_inner_button(__("Export to Excel"), () => {
		if (!last_rows.length) {
			frappe.show_alert({ message: __("Nothing to export — load the report first."), indicator: "orange" });
			return;
		}
		open_url_post(
			"/api/method/prakash_steel.prakash_steel.page.otif_page.otif_page.export_otif_xlsx",
			{
				rows: JSON.stringify(last_rows),
				summary: JSON.stringify(last_summary),
			}
		);
	});

	page.set_primary_action(__("Refresh"), load, "refresh");
	colour_bands_ready.then(load);
};
