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
				font-size: 12px; font-weight: 700; color: #555;
				margin-right: 4px; text-transform: uppercase; letter-spacing: .5px;
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
				background: rgba(0,0,0,.18); border-radius: 10px; padding: 1px 7px; font-size: 11px;
			}

			/* table */
			.so-table-wrap { width: 100%; overflow-x: auto; border-radius: 10px;
				box-shadow: 0 3px 12px rgba(0,0,0,.1); background:#fff; }
			.so-tbl { border-collapse: collapse; min-width: max-content; width: 100%; font-size: 12px; }
			.so-tbl thead th {
				background: linear-gradient(135deg,#dce8f5,#c5d9ee);
				color: #000; font-weight: 700; font-size: 12px;
				padding: 9px 10px; white-space: nowrap;
				border-bottom: 2px solid #b0c8df;
				border-right: 1px solid rgba(0,0,0,.08);
				position: sticky; top: 0; z-index: 2;
			}
			.so-tbl tbody tr:hover td { background: #eef4ff !important; }
			.so-tbl tbody td {
				padding: 6px 10px; border-bottom: 1px solid #f0f0f0;
				border-right: 1px solid #f5f5f5; white-space: nowrap; vertical-align: middle;
			}
			.so-tbl tbody tr:nth-child(even) td { background: #fafbff; }

			/* editable cells */
			.so-tbl .delay-select {
				width: 140px; padding: 4px 6px; border: 1px solid #d0d7e8;
				border-radius: 4px; font-size: 12px; background: #fff;
			}
			.so-tbl .delay-select:focus { border-color: #1e88e5; outline: none; box-shadow: 0 0 0 2px rgba(30,136,229,.2); }
			.so-tbl .delay-remarks {
				width: 180px; padding: 4px 6px; border: 1px solid #d0d7e8;
				border-radius: 4px; font-size: 12px; resize: none; height: 32px;
				font-family: inherit;
			}
			.so-tbl .delay-remarks:focus { border-color: #1e88e5; outline: none; box-shadow: 0 0 0 2px rgba(30,136,229,.2); }
			.so-tbl .changed .delay-select,
			.so-tbl .changed .delay-remarks { border-color: #f57f17; background: #fffde7; }

			/* status badges */
			.badge-status {
				display: inline-block; border-radius: 4px; padding: 2px 8px;
				font-weight: 700; font-size: 11px; text-align: center; min-width: 56px;
			}
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
		fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
		default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		change() { refresh(); },
	});
	let to_date_field = page.add_field({
		fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
		default: frappe.datetime.get_today(),
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
		fieldname: "status", label: __("Status"), fieldtype: "MultiSelectList",
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
	page.set_secondary_action(__("Execute"), () => execute_save(), "octicon octicon-check");

	// ── layout ────────────────────────────────────────────────────────────────
	let $wrap       = $(`<div class="so-page-wrap"></div>`).appendTo(page.main);
	let $filter_bar = $(`<div class="so-filter-bar"></div>`).appendTo($wrap);
	let $table_wrap = $(`<div class="so-table-wrap"></div>`).appendTo($wrap);

	// ── state ─────────────────────────────────────────────────────────────────
	let all_data      = [];
	let delay_reasons = [];   // [{name, delay_reason}]
	let active_filter = "ALL";
	let changes       = {};   // { soi_name: { delay_reason, delay_remarks } }

	// ── fetch delay reasons once ──────────────────────────────────────────────
	frappe.call({
		method: "prakash_steel.prakash_steel.page.open_so_page.open_so_page.get_delay_reasons",
		callback(r) { delay_reasons = r.message || []; },
	});

	// ── colour filter buttons ─────────────────────────────────────────────────
	const COLOR_FILTERS = [
		{ key: "ALL",    label: "All",    bg: "#607d8b", fg: "#fff"    },
		{ key: "GREEN",  label: "Green",  bg: "#00c853", fg: "#003300" },
		{ key: "YELLOW", label: "Yellow", bg: "#ffd600", fg: "#3d2f00" },
		{ key: "RED",    label: "Red",    bg: "#e53935", fg: "#fff"    },
		{ key: "BLACK",  label: "Black",  bg: "#212121", fg: "#fff"    },
		{ key: "WHITE",  label: "White",  bg: "#e0e0e0", fg: "#333"    },
	];

	function build_filter_bar(data) {
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
				build_filter_bar(all_data);
				render_table(filtered_data());
			});
			$filter_bar.append($btn);
		});
	}

	function filtered_data() {
		if (active_filter === "ALL") return all_data;
		return all_data.filter(r => (r.order_status || "").toUpperCase() === active_filter);
	}

	// ── column definitions ────────────────────────────────────────────────────
	const COLUMNS = [
		{ fieldname: "date",                   label: "SO Date",            width: "100px" },
		{ fieldname: "customer",               label: "Customer Name",      width: "150px" },
		{ fieldname: "item_code",              label: "Item Code",          width: "120px" },
		{ fieldname: "qty",                    label: "Order Qty",          width: "80px"  },
		{ fieldname: "rate",                   label: "Rate",               width: "90px"  },
		{ fieldname: "payment_terms_template", label: "Payment Terms",      width: "130px" },
		{ fieldname: "lead_time",              label: "Lead Time",          width: "80px"  },
		{ fieldname: "special_condition",      label: "Special Cond.",      width: "110px" },
		{ fieldname: "status",                 label: "Status",             width: "120px" },
		{ fieldname: "sales_order",            label: "Sales Order",        width: "150px" },
		{ fieldname: "delivered_qty",          label: "Delivered Qty",      width: "100px" },
		{ fieldname: "delivery_date",          label: "Delivery Date",      width: "100px" },
		{ fieldname: "pending_qty",            label: "Qty to Deliver",     width: "100px" },
		{ fieldname: "item_type",              label: "Item Type",          width: "80px"  },
		{ fieldname: "sku_type",               label: "SKU Type",           width: "100px" },
		{ fieldname: "remaining_days",         label: "Remaining Days",     width: "100px" },
		{ fieldname: "buffer_status",          label: "Buffer Status",      width: "100px" },
		{ fieldname: "order_status",           label: "Order Status",       width: "100px" },
		{ fieldname: "stock",                  label: "Stock",              width: "80px"  },
		{ fieldname: "stock_allocation",       label: "Stock Alloc.",       width: "100px" },
		{ fieldname: "shortage",               label: "Shortage",           width: "80px"  },
		{ fieldname: "line_fullkit",           label: "Line Fullkit",       width: "100px" },
		{ fieldname: "order_fullkit",          label: "Order Fullkit",      width: "100px" },
		{ fieldname: "amount",                 label: "Amount",             width: "100px" },
		{ fieldname: "pending_amount",         label: "Pending Amount",     width: "110px" },
		{ fieldname: "__delay_reason",         label: "Delay Reason",       width: "160px", editable: true },
		{ fieldname: "__delay_remarks",        label: "Delay Remarks",      width: "200px", editable: true },
	];

	// ── cell value formatter ──────────────────────────────────────────────────
	function format_cell(fieldname, value) {
		if (value === null || value === undefined || value === "") return "";

		if (fieldname === "order_status") {
			let s = String(value).toLowerCase();
			let cfg = {
				black:  ["#212121","#fff"],
				white:  ["#e0e0e0","#333"],
				green:  ["#00c853","#003300"],
				yellow: ["#ffd600","#3d2f00"],
				red:    ["#e53935","#fff"],
			}[s];
			if (cfg)
				return `<span class="badge-status" style="background:${cfg[0]};color:${cfg[1]};">${String(value).toUpperCase()}</span>`;
		}

		if (fieldname === "line_fullkit" || fieldname === "order_fullkit") {
			let lf = String(value).toLowerCase();
			let cfg = {
				"full-kit": ["#00c853","#003300"],
				"partial":  ["#ffd600","#3d2f00"],
				"pending":  ["#e53935","#fff"],
			}[lf];
			if (cfg)
				return `<span class="badge-status" style="background:${cfg[0]};color:${cfg[1]};">${value}</span>`;
		}

		if (fieldname === "delivered_qty" && value > 0)
			return `<span style="color:#2e7d32;font-weight:600;">${value}</span>`;

		if (fieldname === "shortage" && value > 0)
			return `<span style="color:#c62828;font-weight:700;">${value}</span>`;

		if (fieldname === "remaining_days") {
			let n = parseFloat(value);
			if (!isNaN(n)) {
				let c = n < 0 ? "#c62828" : n <= 5 ? "#e65100" : "#2e7d32";
				return `<span style="color:${c};font-weight:600;">${value}</span>`;
			}
		}

		if (fieldname === "buffer_status") {
			let num = parseInt(value);
			let c = isNaN(num) ? "#333" : num <= 34 ? "#c62828" : num <= 67 ? "#f57f17" : "#2e7d32";
			return `<span style="color:${c};font-weight:700;">${value}</span>`;
		}

		if (fieldname === "sales_order")
			return `<a href="/app/sales-order/${value}" target="_blank">${value}</a>`;

		return frappe.utils.escape_html(String(value));
	}

	// ── render HTML table ─────────────────────────────────────────────────────
	function render_table(data) {
		if (!data || !data.length) {
			$table_wrap.html(`<div style="text-align:center;padding:60px;color:#888;">No rows match this filter.</div>`);
			return;
		}

		// build options HTML once
		let reason_options = `<option value=""></option>` +
			delay_reasons.map(r => `<option value="${frappe.utils.escape_html(r.name)}">${frappe.utils.escape_html(r.name)}</option>`).join("");

		let thead = `<thead><tr>` +
			COLUMNS.map(c => `<th style="min-width:${c.width};width:${c.width};">${__(c.label)}</th>`).join("") +
			`</tr></thead>`;

		let tbody = `<tbody>` + data.map((row, idx) => {
			let soi = row.name || "";
			// existing saved values (from DB) or pending change
			let saved_reason  = row.delay_reasons  || "";
			let saved_remarks = row.delay_remarks  || "";
			let ch = changes[soi] || {};
			let cur_reason  = ch.delay_reason  !== undefined ? ch.delay_reason  : saved_reason;
			let cur_remarks = ch.delay_remarks !== undefined ? ch.delay_remarks : saved_remarks;
			let is_changed  = ch.delay_reason !== undefined || ch.delay_remarks !== undefined;

			let cells = COLUMNS.map(col => {
				if (col.fieldname === "__delay_reason") {
					let opts = reason_options.replace(
						`value="${frappe.utils.escape_html(cur_reason)}"`,
						`value="${frappe.utils.escape_html(cur_reason)}" selected`
					);
					return `<td><select class="delay-select" data-soi="${soi}" data-field="delay_reason">${opts}</select></td>`;
				}
				if (col.fieldname === "__delay_remarks") {
					return `<td><textarea class="delay-remarks" data-soi="${soi}" data-field="delay_remarks" rows="1">${frappe.utils.escape_html(cur_remarks)}</textarea></td>`;
				}
				return `<td>${format_cell(col.fieldname, row[col.fieldname])}</td>`;
			}).join("");

			return `<tr class="${is_changed ? "changed" : ""}" data-soi="${soi}">${cells}</tr>`;
		}).join("") + `</tbody>`;

		$table_wrap.html(`<table class="so-tbl">${thead}${tbody}</table>`);

		// ── event delegation ──────────────────────────────────────────────────
		$table_wrap.off("change.so input.so");

		$table_wrap.on("change.so", ".delay-select", function () {
			let soi   = $(this).data("soi");
			let field = $(this).data("field");
			if (!changes[soi]) changes[soi] = {};
			changes[soi][field] = $(this).val();
			$(this).closest("tr").addClass("changed");
		});

		$table_wrap.on("input.so", ".delay-remarks", function () {
			let soi   = $(this).data("soi");
			let field = $(this).data("field");
			if (!changes[soi]) changes[soi] = {};
			changes[soi][field] = $(this).val();
			$(this).closest("tr").addClass("changed");
		});
	}

	// ── execute (save) ────────────────────────────────────────────────────────
	function execute_save() {
		if (!Object.keys(changes).length) {
			frappe.show_alert({ message: __("No changes to save."), indicator: "orange" });
			return;
		}

		let rows = Object.entries(changes).map(([soi_name, vals]) => ({
			soi_name,
			delay_reason:  vals.delay_reason  !== undefined ? vals.delay_reason  : (all_data.find(r => r.name === soi_name) || {}).delay_reasons  || "",
			delay_remarks: vals.delay_remarks !== undefined ? vals.delay_remarks : (all_data.find(r => r.name === soi_name) || {}).delay_remarks || "",
		}));

		frappe.call({
			method: "prakash_steel.prakash_steel.page.open_so_page.open_so_page.save_delay_info",
			args: { rows: JSON.stringify(rows) },
			callback(r) {
				if (r.message && r.message.status === "ok") {
					frappe.show_alert({ message: __(`Saved ${r.message.updated} row(s).`), indicator: "green" });

					// update all_data in memory so re-renders show saved values
					rows.forEach(saved => {
						let row = all_data.find(r => r.name === saved.soi_name);
						if (row) {
							row.delay_reasons  = saved.delay_reason;
							row.delay_remarks  = saved.delay_remarks;
						}
					});
					changes = {};

					// remove yellow highlight from changed rows
					$table_wrap.find("tr.changed").removeClass("changed");
					$table_wrap.find(".delay-select, .delay-remarks")
						.css({ "border-color": "", "background": "" });
				}
			},
		});
	}

	// ── fetch report data ─────────────────────────────────────────────────────
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
		changes       = {};
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
