frappe.pages["open-so-page"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Open SO Analysis",
		single_column: true,
	});

	// ── styles ────────────────────────────────────────────────────────────────
	if (!document.getElementById("open-so-page-style")) {
		let style = document.createElement("style");
		style.id = "open-so-page-style";
		style.textContent = `
			.so-page-wrap { padding: 0 16px 24px; }

			/* colour filter bar */
			.so-filter-bar {
				display: flex; gap: 10px; flex-wrap: wrap;
				align-items: center; margin-bottom: 16px;
			}
			.so-filter-bar .so-filter-label {
				font-size: 12px; font-weight: 700;
				color: #555; margin-right: 4px; text-transform: uppercase;
				letter-spacing: .5px;
			}
			.so-btn {
				display: inline-flex; align-items: center; gap: 6px;
				padding: 6px 16px; border-radius: 20px; border: 2px solid transparent;
				font-size: 12px; font-weight: 700; cursor: pointer;
				transition: all .15s; user-select: none;
				box-shadow: 0 2px 6px rgba(0,0,0,.12);
			}
			.so-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 10px rgba(0,0,0,.18); }
			.so-btn.active { border-color: #333 !important; box-shadow: 0 0 0 3px rgba(0,0,0,.15); }
			.so-btn .so-btn-count {
				background: rgba(0,0,0,.18); border-radius: 10px;
				padding: 1px 7px; font-size: 11px;
			}

			/* table wrapper */
			.so-table-wrap {
				width: 100%; overflow-x: auto;
				border-radius: 10px;
				box-shadow: 0 3px 12px rgba(0,0,0,.1);
				background: #fff;
			}
			.so-table-wrap .dt-scrollable { border-radius: 10px; }
			.so-table-wrap .dt-cell--header {
				background: linear-gradient(135deg,#dce8f5,#c5d9ee) !important;
				color: #000 !important;
				font-size: 12px !important;
				font-weight: 700 !important;
				border-right: 1px solid rgba(0,0,0,.1) !important;
			}
			.so-table-wrap .dt-row:hover .dt-cell { background: #eef4ff !important; }
		`;
		document.head.appendChild(style);
	}

	// ── page filters ──────────────────────────────────────────────────────────
	let company_field = page.add_field({
		fieldname: "company", label: __("Company"),
		fieldtype: "Link", options: "Company",
		default: frappe.defaults.get_default("company"),
		change() { refresh(); },
	});
	let from_date_field = page.add_field({
		fieldname: "from_date", label: __("From Date"),
		fieldtype: "Date",
		default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		change() { refresh(); },
	});
	let to_date_field = page.add_field({
		fieldname: "to_date", label: __("To Date"),
		fieldtype: "Date", default: frappe.datetime.get_today(),
		change() { refresh(); },
	});
	let sales_order_field = page.add_field({
		fieldname: "sales_order", label: __("Sales Order"),
		fieldtype: "MultiSelectList", options: "Sales Order",
		change() { refresh(); },
	});
	let warehouse_field = page.add_field({
		fieldname: "warehouse", label: __("Warehouse"),
		fieldtype: "Link", options: "Warehouse",
		change() { refresh(); },
	});
	let status_field = page.add_field({
		fieldname: "status", label: __("Status"),
		fieldtype: "MultiSelectList",
		get_data(txt) {
			return ["To Pay","To Bill","To Deliver","To Deliver and Bill","Completed","Closed"]
				.filter(s => !txt || s.toLowerCase().includes(txt.toLowerCase()))
				.map(s => ({ value: s, label: __(s), description: "" }));
		},
		change() { refresh(); },
	});
	let line_fullkit_field = page.add_field({
		fieldname: "line_fullkit_status", label: __("Line Full Kit Status"),
		fieldtype: "MultiSelectList",
		get_data(txt) {
			return ["Pending","Partial","Full-kit"]
				.filter(s => !txt || s.toLowerCase().includes(txt.toLowerCase()))
				.map(s => ({ value: s, label: __(s), description: "" }));
		},
		change() { refresh(); },
	});
	let group_by_field = page.add_field({
		fieldname: "group_by_so", label: __("Group by Sales Order"),
		fieldtype: "Check", default: 0,
		change() { refresh(); },
	});

	page.set_primary_action(__("Refresh"), () => refresh(), "octicon octicon-sync");

	// ── layout ────────────────────────────────────────────────────────────────
	let $wrap       = $(`<div class="so-page-wrap"></div>`).appendTo(page.main);
	let $filter_bar = $(`<div class="so-filter-bar"></div>`).appendTo($wrap);
	let $table_wrap = $(`<div class="so-table-wrap"></div>`).appendTo($wrap);

	// ── colour filter buttons config ──────────────────────────────────────────
	const COLOR_FILTERS = [
		{ key: "ALL",    label: "All",     bg: "#607d8b", fg: "#fff"    },
		{ key: "GREEN",  label: "Green",   bg: "#00c853", fg: "#003300" },
		{ key: "YELLOW", label: "Yellow",  bg: "#ffd600", fg: "#3d2f00" },
		{ key: "RED",    label: "Red",     bg: "#e53935", fg: "#fff"    },
		{ key: "BLACK",  label: "Black",   bg: "#212121", fg: "#fff"    },
		{ key: "WHITE",  label: "White",   bg: "#e0e0e0", fg: "#333"    },
	];

	let active_filter = "ALL";
	let all_data      = [];
	let datatable;

	function build_filter_bar(data) {
		// count per status
		let counts = { ALL: data.length, GREEN:0, YELLOW:0, RED:0, BLACK:0, WHITE:0 };
		data.forEach(r => {
			let k = (r.order_status || "").toUpperCase();
			if (counts[k] !== undefined) counts[k]++;
		});

		$filter_bar.empty();
		$filter_bar.append(`<span class="so-filter-label">Order Status:</span>`);

		COLOR_FILTERS.forEach(f => {
			let $btn = $(`
				<div class="so-btn ${active_filter === f.key ? "active" : ""}"
					style="background:${f.bg};color:${f.fg};">
					${f.label}
					<span class="so-btn-count">${counts[f.key]}</span>
				</div>
			`);
			$btn.on("click", () => {
				active_filter = f.key;
				build_filter_bar(all_data);   // re-render buttons with updated active state
				render_table(filtered_data());
			});
			$filter_bar.append($btn);
		});
	}

	function filtered_data() {
		if (active_filter === "ALL") return all_data;
		return all_data.filter(r => (r.order_status || "").toUpperCase() === active_filter);
	}

	// ── column formatter ──────────────────────────────────────────────────────
	function formatter(value, column) {
		if (value === null || value === undefined || value === "") return "";

		if ((column.fieldname === "delivered_qty" || column.fieldname === "billed_amount") && value > 0)
			return `<span style="color:#2e7d32;font-weight:600;">${value}</span>`;

		if (column.fieldname === "delay" && value > 0)
			return `<span style="color:#c62828;font-weight:600;">${value}</span>`;

		if (column.fieldname === "order_status") {
			let s = String(value).toLowerCase();
			let bg = "", fg = "#000";
			if      (s === "black")  { bg = "#212121"; fg = "#fff"; }
			else if (s === "white")  { bg = "#e0e0e0"; fg = "#333"; }
			else if (s === "green")  { bg = "#00c853"; fg = "#003300"; }
			else if (s === "yellow") { bg = "#ffd600"; fg = "#3d2f00"; }
			else if (s === "red")    { bg = "#e53935"; fg = "#fff"; }
			if (bg)
				return `<div style="background:${bg};color:${fg};border-radius:4px;padding:3px 6px;text-align:center;font-weight:700;font-size:11px;">${String(value).toUpperCase()}</div>`;
		}

		if (column.fieldname === "line_fullkit" || column.fieldname === "order_fullkit") {
			let lf = String(value).toLowerCase();
			let bg = "", fg = "#000";
			if      (lf === "full-kit") { bg = "#00c853"; fg = "#003300"; }
			else if (lf === "partial")  { bg = "#ffd600"; fg = "#3d2f00"; }
			else if (lf === "pending")  { bg = "#e53935"; fg = "#fff"; }
			if (bg)
				return `<div style="background:${bg};color:${fg};border-radius:4px;padding:3px 6px;text-align:center;font-weight:700;font-size:11px;">${value}</div>`;
		}

		if (column.fieldname === "shortage" && value > 0)
			return `<span style="color:#c62828;font-weight:700;">${value}</span>`;

		if (column.fieldname === "remaining_days") {
			let n = parseFloat(value);
			if (!isNaN(n)) {
				let color = n < 0 ? "#c62828" : n <= 5 ? "#e65100" : "#2e7d32";
				return `<span style="color:${color};font-weight:600;">${value}</span>`;
			}
		}

		if (column.fieldname === "buffer_status") {
			let num = parseInt(value);
			let color = isNaN(num) ? "#333" : num <= 34 ? "#c62828" : num <= 67 ? "#f57f17" : "#2e7d32";
			return `<span style="color:${color};font-weight:700;">${value}</span>`;
		}

		return value;
	}

	// ── visible columns ───────────────────────────────────────────────────────
	const VISIBLE_COLUMNS = [
		{ fieldname: "date",                   label: "Sales Order Date",   width: 110 },
		{ fieldname: "customer",               label: "Customer Name",      width: 150 },
		{ fieldname: "item_code",              label: "Item Code",          width: 120 },
		{ fieldname: "qty",                    label: "Order Qty",          width: 90  },
		{ fieldname: "rate",                   label: "Rate",               width: 100 },
		{ fieldname: "payment_terms_template", label: "Payment Terms",      width: 140 },
		{ fieldname: "lead_time",              label: "Lead Time",          width: 90  },
		{ fieldname: "special_condition",      label: "Special Conditions", width: 130 },
		{ fieldname: "status",                 label: "Status",             width: 130 },
		{ fieldname: "sales_order",            label: "Sales Order",        width: 160 },
		{ fieldname: "delivered_qty",          label: "Delivered Qty",      width: 110 },
		{ fieldname: "delivery_date",          label: "Delivery Date",      width: 110 },
		{ fieldname: "pending_qty",            label: "Qty to Deliver",     width: 110 },
		{ fieldname: "item_type",              label: "Item Type",          width: 90  },
		{ fieldname: "sku_type",               label: "SKU Type",           width: 110 },
		{ fieldname: "remaining_days",         label: "Remaining Days",     width: 110 },
		{ fieldname: "buffer_status",          label: "Buffer Status",      width: 110 },
		{ fieldname: "order_status",           label: "Order Status",       width: 110 },
		{ fieldname: "stock",                  label: "Stock",              width: 90  },
		{ fieldname: "stock_allocation",       label: "Stock Allocation",   width: 120 },
		{ fieldname: "shortage",               label: "Shortage",           width: 90  },
		{ fieldname: "line_fullkit",           label: "Line Fullkit",       width: 110 },
		{ fieldname: "order_fullkit",          label: "Order Fullkit",      width: 110 },
		{ fieldname: "amount",                 label: "Amount",             width: 110 },
		{ fieldname: "pending_amount",         label: "Pending Amount",     width: 120 },
	];

	function render_table(data) {
		let dt_columns = VISIBLE_COLUMNS.map(col => ({
			name: __(col.label),
			id: col.fieldname,
			editable: false,
			width: col.width,
			format: (value) => formatter(value, col),
		}));

		let dt_rows = data.map(row =>
			VISIBLE_COLUMNS.map(col => {
				let val = row[col.fieldname];
				return (val === null || val === undefined) ? "" : val;
			})
		);

		$table_wrap.empty();
		let $table_div = $(`<div></div>`).appendTo($table_wrap);

		if (datatable) { datatable.destroy && datatable.destroy(); datatable = null; }

		if (!dt_rows.length) {
			$table_wrap.html(`<div style="text-align:center;padding:60px;color:#888;">No rows match this filter.</div>`);
			return;
		}

		datatable = new frappe.DataTable($table_div[0], {
			columns: dt_columns,
			data: dt_rows,
			layout: "fixed",
			enableClusterize: true,
			noDataMessage: __("No data"),
			serialNoColumn: false,
			checkboxColumn: false,
		});
	}

	// ── fetch ─────────────────────────────────────────────────────────────────
	function refresh() {
		let filters = {
			company:             company_field.get_value(),
			from_date:           from_date_field.get_value(),
			to_date:             to_date_field.get_value(),
			sales_order:         sales_order_field.get_value(),
			warehouse:           warehouse_field.get_value(),
			status:              status_field.get_value(),
			line_fullkit_status: line_fullkit_field.get_value() || ["Partial", "Full-kit"],
			group_by_so:         group_by_field.get_value(),
		};

		if (!filters.company || !filters.from_date || !filters.to_date) {
			frappe.msgprint(__("Please select Company, From Date and To Date."));
			return;
		}

		$filter_bar.empty();
		$table_wrap.html(`<div style="text-align:center;padding:60px;color:#888;">Loading…</div>`);
		active_filter = "ALL";

		frappe.call({
			method: "frappe.desk.query_report.run",
			args: { report_name: "Open SO Analysis", filters, ignore_prepared_report: 1 },
			callback(r) {
				if (!r || !r.message) return;
				let { result } = r.message;

				if (!result || !result.length) {
					$filter_bar.empty();
					$table_wrap.html(`<div style="text-align:center;padding:60px;color:#888;">No data found.</div>`);
					return;
				}

				all_data = result;
				build_filter_bar(all_data);
				render_table(all_data);
			},
		});
	}

	line_fullkit_field.set_value(["Partial", "Full-kit"]);
	refresh();
};
