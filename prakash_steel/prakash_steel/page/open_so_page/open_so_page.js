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

			/* tab bar */
			.so-tab-bar {
				display: flex; gap: 0; border-bottom: 2px solid #d0d7e8;
				margin-bottom: 16px;
			}
			.so-tab {
				padding: 10px 24px; font-size: 13px; font-weight: 700;
				cursor: pointer; border-bottom: 3px solid transparent;
				margin-bottom: -2px; color: #666; transition: color .15s, border-color .15s;
				user-select: none;
			}
			.so-tab:hover { color: #1565c0; }
			.so-tab.active { color: #1565c0; border-bottom-color: #1565c0; }

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
			.so-tbl tr.changed .delay-select,
			.so-tbl tr.changed .delay-remarks { border-color: #f57f17; background: #fffde7; }

			/* status badges */
			.badge-status {
				display: inline-block; border-radius: 4px; padding: 2px 8px;
				font-weight: 700; font-size: 11px; text-align: center; min-width: 56px;
			}

			/* tab panels */
			.so-tab-panel { display: none; }
			.so-tab-panel.active { display: block; }
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
		change() {
			if (all_data.length) filter_dispatch(all_data, active_filter_dispatch);
		},
	});
	let group_by_field = page.add_field({
		fieldname: "group_by_so", label: __("Group by Sales Order"),
		fieldtype: "Check", default: 0,
		change() { refresh(); },
	});

	page.set_primary_action(__("Refresh"), () => refresh(), "octicon octicon-sync");
	page.set_secondary_action(__("Execute"), () => execute_save(), "octicon octicon-check");

	// ── layout ────────────────────────────────────────────────────────────────
	let $wrap = $(`<div class="so-page-wrap"></div>`).appendTo(page.main);

	// tab bar
	let $tab_bar = $(`
		<div class="so-tab-bar">
			<div class="so-tab active" data-tab="analysis">Open SO Analysis</div>
			<div class="so-tab" data-tab="dispatch">Ready to Dispatch</div>
		</div>
	`).appendTo($wrap);

	// tab panels
	let $panel_analysis = $(`<div class="so-tab-panel active" data-panel="analysis"></div>`).appendTo($wrap);
	let $panel_dispatch  = $(`<div class="so-tab-panel" data-panel="dispatch"></div>`).appendTo($wrap);

	// each panel has its own filter bar + table wrap
	let $table_wrap_analysis  = $(`<div class="so-table-wrap"></div>`).appendTo($panel_analysis);

	let $filter_bar_dispatch = $(`<div class="so-filter-bar"></div>`).appendTo($panel_dispatch);
	let $table_wrap_dispatch  = $(`<div class="so-table-wrap"></div>`).appendTo($panel_dispatch);

	// active tab tracking
	let active_tab = "analysis";

	$tab_bar.on("click", ".so-tab", function () {
		let tab = $(this).data("tab");
		if (tab === active_tab) return;
		active_tab = tab;
		$tab_bar.find(".so-tab").removeClass("active");
		$(this).addClass("active");
		$wrap.find(".so-tab-panel").removeClass("active");
		$wrap.find(`.so-tab-panel[data-panel="${tab}"]`).addClass("active");
		$(line_fullkit_field.wrapper).toggle(tab === "dispatch");
	});

	// ── shared state ──────────────────────────────────────────────────────────
	let all_data      = [];
	let delay_reasons = [];
	let changes       = {};
	let active_filter_dispatch  = "ALL";

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

	function build_filter_bar($bar, data, active_key, on_click) {
		let counts = { ALL: data.length, GREEN:0, YELLOW:0, RED:0, BLACK:0, WHITE:0 };
		data.forEach(r => {
			let k = (r.order_status || "").toUpperCase();
			if (counts[k] !== undefined) counts[k]++;
		});
		$bar.empty();
		$bar.append(`<span class="so-filter-label">Order Status:</span>`);
		COLOR_FILTERS.forEach(f => {
			let $btn = $(`
				<div class="so-btn ${active_key === f.key ? "active" : ""}"
					style="background:${f.bg};color:${f.fg};">
					${f.label} <span class="so-btn-count">${counts[f.key]}</span>
				</div>
			`);
			$btn.on("click", () => on_click(f.key));
			$bar.append($btn);
		});
	}

	// ── column definitions ────────────────────────────────────────────────────
	const COLS_ANALYSIS = [
		{ fieldname: "date",                   label: "SO Date",          width: "100px" },
		{ fieldname: "customer",               label: "Customer Name",    width: "150px" },
		{ fieldname: "item_code",              label: "Item Code",        width: "120px" },
		{ fieldname: "qty",                    label: "Order Qty",        width: "80px"  },
		{ fieldname: "rate",                   label: "Rate",             width: "90px"  },
		{ fieldname: "payment_terms_template", label: "Payment Terms",   width: "130px" },
		{ fieldname: "lead_time",              label: "Lead Time",        width: "80px"  },
		{ fieldname: "special_condition",      label: "Special Cond.",    width: "110px" },
		{ fieldname: "status",                 label: "Status",           width: "120px" },
		{ fieldname: "sales_order",            label: "Sales Order",      width: "150px" },
		{ fieldname: "delivered_qty",          label: "Delivered Qty",    width: "100px" },
		{ fieldname: "delivery_date",          label: "Delivery Date",    width: "100px" },
		{ fieldname: "pending_qty",            label: "Qty to Deliver",   width: "100px" },
		{ fieldname: "item_type",              label: "Item Type",        width: "80px"  },
		{ fieldname: "sku_type",               label: "SKU Type",         width: "100px" },
		{ fieldname: "remaining_days",         label: "Remaining Days",   width: "100px" },
		{ fieldname: "buffer_status",          label: "Buffer Status",    width: "100px" },
		{ fieldname: "order_status",           label: "Order Status",     width: "100px" },
		{ fieldname: "stock",                  label: "Stock",            width: "80px"  },
		{ fieldname: "stock_allocation",       label: "Stock Alloc.",     width: "100px" },
		{ fieldname: "shortage",               label: "Shortage",         width: "80px"  },
		{ fieldname: "line_fullkit",           label: "Line Fullkit",     width: "100px" },
		{ fieldname: "order_fullkit",          label: "Order Fullkit",    width: "100px" },
		{ fieldname: "amount",                 label: "Amount",           width: "100px" },
		{ fieldname: "pending_amount",         label: "Pending Amount",   width: "110px" },
		{ fieldname: "__delay_reason",         label: "Delay Reason",     width: "160px", editable: true },
		{ fieldname: "__delay_remarks",        label: "Delay Remarks",    width: "200px", editable: true },
	];

	const COLS_DISPATCH = [
		{ fieldname: "order_status",    label: "Order Status",       width: "110px" },
		{ fieldname: "date",            label: "Sales Order Date",   width: "110px" },
		{ fieldname: "delivery_date",   label: "Delivery Date",      width: "110px" },
		{ fieldname: "sales_order",     label: "Sales Order",        width: "150px" },
		{ fieldname: "customer",        label: "Customer Name",      width: "150px" },
		{ fieldname: "order_fullkit",   label: "Order Fullkit",      width: "110px" },
		{ fieldname: "item_code",       label: "Item Code",          width: "120px" },
		{ fieldname: "line_fullkit",    label: "Line Fullkit",       width: "110px" },
		{ fieldname: "qty",             label: "Order Qty",          width: "90px"  },
		{ fieldname: "pending_qty",     label: "Qty to Deliver",     width: "110px" },
		{ fieldname: "stock_allocation",label: "Stock Allocation",   width: "120px" },
		{ fieldname: "__delay_reason",  label: "Delay Reason",       width: "160px", editable: true },
		{ fieldname: "__delay_remarks", label: "Delay Remarks",      width: "200px", editable: true },
	];

	// ── cell formatter ────────────────────────────────────────────────────────
	function format_cell(fieldname, value) {
		if (value === null || value === undefined || value === "") return "";

		if (fieldname === "order_status") {
			let s = String(value).toLowerCase();
			let cfg = { black:["#212121","#fff"], white:["#e0e0e0","#333"], green:["#00c853","#003300"], yellow:["#ffd600","#3d2f00"], red:["#e53935","#fff"] }[s];
			if (cfg) return `<span class="badge-status" style="background:${cfg[0]};color:${cfg[1]};">${String(value).toUpperCase()}</span>`;
		}

		if (fieldname === "line_fullkit" || fieldname === "order_fullkit") {
			let lf = String(value).toLowerCase();
			let cfg = { "full-kit":["#00c853","#003300"], "partial":["#ffd600","#3d2f00"], "pending":["#e53935","#fff"] }[lf];
			if (cfg) return `<span class="badge-status" style="background:${cfg[0]};color:${cfg[1]};">${value}</span>`;
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

	// ── generic table renderer ────────────────────────────────────────────────
	// editable=true  → delay_reason/remarks are inputs (Analysis tab)
	// editable=false → delay_reason/remarks are read-only text (Dispatch tab)
	function render_table($wrap_el, cols, data, editable) {
		if (!data || !data.length) {
			$wrap_el.html(`<div style="text-align:center;padding:60px;color:#888;">No rows match this filter.</div>`);
			return;
		}

		let reason_options = `<option value=""></option>` +
			delay_reasons.map(r => `<option value="${frappe.utils.escape_html(r.name)}">${frappe.utils.escape_html(r.name)}</option>`).join("");

		let thead = `<thead><tr>` +
			cols.map(c => `<th style="min-width:${c.width};width:${c.width};">${__(c.label)}</th>`).join("") +
			`</tr></thead>`;

		let tbody = `<tbody>` + data.map(row => {
			let soi = row.name || "";
			let saved_reason  = row.delay_reasons  || "";
			let saved_remarks = row.delay_remarks  || "";
			let ch = changes[soi] || {};
			let cur_reason  = ch.delay_reason  !== undefined ? ch.delay_reason  : saved_reason;
			let cur_remarks = ch.delay_remarks !== undefined ? ch.delay_remarks : saved_remarks;
			let is_changed  = ch.delay_reason !== undefined || ch.delay_remarks !== undefined;
			// remarks is mandatory when a reason is selected
			let remarks_required = cur_reason && !cur_remarks;

			let cells = cols.map(col => {
				if (col.fieldname === "__delay_reason") {
					if (!editable) {
						return `<td>${frappe.utils.escape_html(cur_reason)}</td>`;
					}
					let opts = reason_options.replace(
						`value="${frappe.utils.escape_html(cur_reason)}"`,
						`value="${frappe.utils.escape_html(cur_reason)}" selected`
					);
					return `<td><select class="delay-select" data-soi="${soi}">${opts}</select></td>`;
				}
				if (col.fieldname === "__delay_remarks") {
					if (!editable) {
						return `<td>${frappe.utils.escape_html(cur_remarks)}</td>`;
					}
					let req_style = remarks_required
						? "border-color:#e53935;background:#fff5f5;"
						: "";
					let req_title = remarks_required ? "title='Remarks are mandatory when a delay reason is set'" : "";
					return `<td><textarea class="delay-remarks${remarks_required ? " remarks-required" : ""}"
						data-soi="${soi}" rows="1" style="${req_style}" ${req_title}>${frappe.utils.escape_html(cur_remarks)}</textarea></td>`;
				}
				return `<td>${format_cell(col.fieldname, row[col.fieldname])}</td>`;
			}).join("");

			return `<tr class="${is_changed ? "changed" : ""}" data-soi="${soi}">${cells}</tr>`;
		}).join("") + `</tbody>`;

		let total_pending = data.reduce((sum, row) => sum + (parseFloat(row.pending_qty) || 0), 0);
		let pending_idx = cols.findIndex(c => c.fieldname === "pending_qty");
		let tfoot = `<tfoot><tr style="background:linear-gradient(135deg,#dce8f5,#c5d9ee);font-weight:700;font-size:12px;">` +
			cols.map((c, i) => {
				if (i === 0) return `<td style="padding:7px 10px;border-top:2px solid #b0c8df;">Total</td>`;
				if (i === pending_idx) return `<td style="padding:7px 10px;border-top:2px solid #b0c8df;">${frappe.utils.escape_html(String(total_pending % 1 === 0 ? total_pending : total_pending.toFixed(2)))}</td>`;
				return `<td style="border-top:2px solid #b0c8df;"></td>`;
			}).join("") +
			`</tr></tfoot>`;

		$wrap_el.html(`<table class="so-tbl">${thead}${tbody}${tfoot}</table>`);

		if (!editable) return;  // no event listeners needed for read-only tab

		$wrap_el.off("change.so input.so");

		$wrap_el.on("change.so", ".delay-select", function () {
			let soi = $(this).data("soi");
			let val = $(this).val();
			if (!changes[soi]) changes[soi] = {};
			changes[soi]["delay_reason"] = val;
			$(this).closest("tr").addClass("changed");

			// make remarks mandatory if reason selected
			let $remarks = $wrap_el.find(`.delay-remarks[data-soi="${soi}"]`);
			let remarks_val = $remarks.val() || "";
			if (val && !remarks_val) {
				$remarks.addClass("remarks-required")
					.css({ "border-color": "#e53935", "background": "#fff5f5" })
					.attr("title", __("Remarks are mandatory when a delay reason is set"));
			} else {
				$remarks.removeClass("remarks-required")
					.css({ "border-color": "", "background": "" })
					.removeAttr("title");
			}
		});

		$wrap_el.on("input.so", ".delay-remarks", function () {
			let soi = $(this).data("soi");
			let val = $(this).val();
			if (!changes[soi]) changes[soi] = {};
			changes[soi]["delay_remarks"] = val;
			$(this).closest("tr").addClass("changed");

			// clear mandatory indicator once user types
			let reason_val = changes[soi].delay_reason !== undefined
				? changes[soi].delay_reason
				: (all_data.find(r => r.name === soi) || {}).delay_reasons || "";

			if (reason_val && val) {
				$(this).removeClass("remarks-required")
					.css({ "border-color": "", "background": "" })
					.removeAttr("title");
			} else if (reason_val && !val) {
				$(this).addClass("remarks-required")
					.css({ "border-color": "#e53935", "background": "#fff5f5" });
			}
		});
	}

	// ── render both tabs ──────────────────────────────────────────────────────
	function filter_dispatch(data, key) {
		active_filter_dispatch = key;
		let lf_values = line_fullkit_field.get_value() || ["Partial", "Full-kit"];
		let lf_data = (lf_values && lf_values.length)
			? data.filter(r => lf_values.includes(r.line_fullkit))
			: data;
		let fd = key === "ALL" ? lf_data : lf_data.filter(r => (r.order_status || "").toUpperCase() === key);
		build_filter_bar($filter_bar_dispatch, lf_data, key, k => filter_dispatch(data, k));
		render_table($table_wrap_dispatch, COLS_DISPATCH, fd, false);
	}

	function render_all(data) {
		render_table($table_wrap_analysis, COLS_ANALYSIS, data, true);
		filter_dispatch(data, active_filter_dispatch);
	}

	// ── execute save ──────────────────────────────────────────────────────────
	function execute_save() {
		if (!Object.keys(changes).length) {
			frappe.show_alert({ message: __("No changes to save."), indicator: "orange" });
			return;
		}

		// mandatory check: if delay_reason is set, delay_remarks must not be empty
		let missing_remarks = [];
		Object.entries(changes).forEach(([soi_name, vals]) => {
			let existing = all_data.find(r => r.name === soi_name) || {};
			let reason  = vals.delay_reason  !== undefined ? vals.delay_reason  : existing.delay_reasons  || "";
			let remarks = vals.delay_remarks !== undefined ? vals.delay_remarks : existing.delay_remarks || "";
			if (reason && !remarks.trim()) {
				missing_remarks.push(soi_name);
				// highlight the offending textarea
				$table_wrap_analysis.find(`.delay-remarks[data-soi="${soi_name}"]`)
					.addClass("remarks-required")
					.css({ "border-color": "#e53935", "background": "#fff5f5" });
			}
		});

		if (missing_remarks.length) {
			frappe.msgprint({
				title: __("Mandatory Field"),
				message: __(`Delay Remarks is mandatory for ${missing_remarks.length} row(s) where a Delay Reason is selected.`),
				indicator: "red",
			});
			return;
		}

		let rows = Object.entries(changes).map(([soi_name, vals]) => {
			let existing = all_data.find(r => r.name === soi_name) || {};
			return {
				soi_name,
				delay_reason:  vals.delay_reason  !== undefined ? vals.delay_reason  : existing.delay_reasons  || "",
				delay_remarks: vals.delay_remarks !== undefined ? vals.delay_remarks : existing.delay_remarks || "",
			};
		});

		frappe.call({
			method: "prakash_steel.prakash_steel.page.open_so_page.open_so_page.save_delay_info",
			args: { rows: JSON.stringify(rows) },
			callback(r) {
				if (r.message && r.message.status === "ok") {
					frappe.show_alert({ message: __(`Saved ${r.message.updated} row(s).`), indicator: "green" });
					rows.forEach(saved => {
						let row = all_data.find(r => r.name === saved.soi_name);
						if (row) { row.delay_reasons = saved.delay_reason; row.delay_remarks = saved.delay_remarks; }
					});
					changes = {};
					$(".so-tbl tr.changed").removeClass("changed");
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
			line_fullkit_status: ["Partial", "Full-kit", "Pending"],
			group_by_so:         group_by_field.get_value(),
		};

		if (!filters.company || !filters.from_date || !filters.to_date) {
			frappe.msgprint(__("Please select Company, From Date and To Date."));
			return;
		}

		changes = {};
		active_filter_dispatch  = "ALL";
		$filter_bar_dispatch.empty();
		let loading = `<div style="text-align:center;padding:60px;color:#888;">Loading…</div>`;
		$table_wrap_analysis.html(loading);
		$table_wrap_dispatch.html(loading);

		frappe.call({
			method: "frappe.desk.query_report.run",
			args: { report_name: "Open SO Analysis", filters, ignore_prepared_report: 1 },
			callback(r) {
				if (!r || !r.message) return;
				let { result } = r.message;

				if (!result || !result.length) {
					let empty = `<div style="text-align:center;padding:60px;color:#888;">No data found.</div>`;
					$filter_bar_dispatch.empty();
					$table_wrap_analysis.html(empty);
					$table_wrap_dispatch.html(empty);
					return;
				}

				all_data = result;
				render_all(all_data);
			},
		});
	}

	line_fullkit_field.set_value(["Partial", "Full-kit"]);
	$(line_fullkit_field.wrapper).hide();
	refresh();
};
