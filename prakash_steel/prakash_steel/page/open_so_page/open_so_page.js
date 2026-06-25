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

			/* status badges */
			.badge-status {
				display: inline-block; border-radius: 4px; padding: 2px 8px;
				font-weight: 700; font-size: 11px; text-align: center; min-width: 56px;
			}

			/* tab panels */
			.so-tab-panel { display: none; }
			.so-tab-panel.active { display: block; }

			/* DataTable container */
			.so-table-wrap {
				width: 100%; border-radius: 10px;
				box-shadow: 0 3px 12px rgba(0,0,0,.1); background: #fff;
				overflow: hidden;
			}
			.so-table-wrap .dt-wrapper { font-size: 12px; font-family: inherit; border: none; }
			.so-table-wrap .dt-cell--header { background: linear-gradient(135deg,#dce8f5,#c5d9ee); }
			.so-table-wrap .dt-cell--header .content { font-weight: 700; color: #000; font-size: 12px; }
			.so-table-wrap .dt-row:not(.dt-row--header):not(.dt-row--filter):hover .dt-cell { background: #eef4ff; }
			.so-table-wrap .dt-cell { border-bottom: 1px solid #f0f0f0; border-right: 1px solid #f5f5f5; }
			.so-table-wrap .dt-cell--filter input {
				font-size: 11px; padding: 2px 6px; border-radius: 3px;
				border: 1px solid #d0d7e8; width: 100%;
			}
			.so-table-wrap .delay-select {
				width: 100%; padding: 3px 5px; border: 1px solid #d0d7e8;
				border-radius: 4px; font-size: 12px; background: #fff;
			}
			.so-table-wrap .delay-select:focus { border-color: #1e88e5; outline: none; }
			.so-table-wrap .delay-remarks {
				width: 100%; padding: 3px 5px; border: 1px solid #d0d7e8;
				border-radius: 4px; font-size: 12px; resize: none; height: 30px;
				font-family: inherit;
			}
			.so-table-wrap .delay-remarks:focus { border-color: #1e88e5; outline: none; }
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
		get_data(txt) {
			let filters = { docstatus: 1 };
			const from_date = from_date_field.get_value();
			const to_date = to_date_field.get_value();
			if (from_date && to_date) {
				filters.transaction_date = ["between", [from_date, to_date]];
			}
			return frappe.db.get_link_options("Sales Order", txt, filters);
		},
		change() { refresh(); },
	});
	let customer_field = page.add_field({
		fieldname: "customer", label: __("Customer"),
		fieldtype: "Link", options: "Customer",
		change() { refresh(); },
	});
	let item_code_field = page.add_field({
		fieldname: "item_code", label: __("Item Code"),
		fieldtype: "Link", options: "Item",
		change() { refresh(); },
	});
	let warehouse_field = page.add_field({
		fieldname: "warehouse", label: __("Warehouse"),
		fieldtype: "Link", options: "Warehouse",
		change() { refresh(); },
	});

	// The Link "clear" (×) button only does `$input.val("").focus()` and never
	// fires a native change event, so `change()` above won't run on clear.
	// Bind the clear button explicitly so removing a filter auto-refreshes.
	[customer_field, item_code_field, warehouse_field].forEach((f) => {
		f.$wrapper.find(".btn-clear").on("click", () => setTimeout(() => refresh(), 100));
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
	let $filter_bar_analysis = $(`<div class="so-filter-bar"></div>`).appendTo($panel_analysis);
	let $table_wrap_analysis = $(`<div class="so-table-wrap"></div>`).appendTo($panel_analysis);

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
	let all_data             = [];
	let delay_reasons        = [];
	let changes              = {};
	let active_filter_analysis = "ALL";
	let active_filter_dispatch = "ALL";
	let dt_instances         = { analysis: null, dispatch: null };

	frappe.call({
		method: "prakash_steel.prakash_steel.page.open_so_page.open_so_page.get_delay_reasons",
		callback(r) { delay_reasons = r.message || []; },
	});

	// ── colour filter buttons ─────────────────────────────────────────────────
	const COLOR_FILTERS = [
		{ key: "ALL",    label: "All",    bg: "#607d8b", fg: "#fff"    },
		{ key: "GREEN",  label: "Green",  bg: "#00c853", fg: "#003300", count_fg: "#fff" },
		{ key: "YELLOW", label: "Yellow", bg: "#ffd600", fg: "#3d2f00", count_fg: "#fff" },
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
					${f.label} <span class="so-btn-count"${f.count_fg ? ` style="color:${f.count_fg};"` : ""}>${counts[f.key]}</span>
				</div>
			`);
			$btn.on("click", () => on_click(f.key));
			$bar.append($btn);
		});
	}

	// ── column definitions ────────────────────────────────────────────────────
	const COLS_ANALYSIS = [
		{ fieldname: "date",                   label: "SO Date",          width: 100 },
		{ fieldname: "customer",               label: "Customer Name",    width: 150 },
		{ fieldname: "item_code",              label: "Item Code",        width: 120 },
		{ fieldname: "qty",                    label: "Order Qty",        width: 80  },
		{ fieldname: "rate",                   label: "Rate",             width: 90  },
		{ fieldname: "payment_terms_template", label: "Payment Terms",    width: 130 },
		{ fieldname: "lead_time",              label: "Lead Time",        width: 80  },
		{ fieldname: "special_condition",      label: "Special Cond.",    width: 110 },
		{ fieldname: "status",                 label: "Status",           width: 120 },
		{ fieldname: "sales_order",            label: "Sales Order",      width: 150 },
		{ fieldname: "delivered_qty",          label: "Delivered Qty",    width: 100 },
		{ fieldname: "delivery_date",          label: "Delivery Date",    width: 100 },
		{ fieldname: "pending_qty",            label: "Qty to Deliver",   width: 100 },
		{ fieldname: "item_type",              label: "Item Type",        width: 80  },
		{ fieldname: "sku_type",               label: "SKU Type",         width: 100 },
		{ fieldname: "remaining_days",         label: "Remaining Days",   width: 100 },
		{ fieldname: "buffer_status",          label: "Buffer Status",    width: 100 },
		{ fieldname: "order_status",           label: "Order Status",     width: 100 },
		{ fieldname: "stock",                  label: "Stock",            width: 80  },
		{ fieldname: "stock_allocation",       label: "Stock Alloc.",     width: 100 },
		{ fieldname: "shortage",               label: "Shortage",         width: 80  },
		{ fieldname: "line_fullkit",           label: "Line Fullkit",     width: 100 },
		{ fieldname: "order_fullkit",          label: "Order Fullkit",    width: 100 },
		{ fieldname: "amount",                 label: "Amount",           width: 100 },
		{ fieldname: "pending_amount",         label: "Pending Amount",   width: 110 },
		{ fieldname: "__delay_reason",         label: "Delay Reason",     width: 160 },
		{ fieldname: "__delay_remarks",        label: "Delay Remarks",    width: 200 },
	];

	const COLS_DISPATCH = [
		{ fieldname: "order_status",     label: "Order Status",      width: 110 },
		{ fieldname: "date",             label: "Sales Order Date",  width: 110 },
		{ fieldname: "delivery_date",    label: "Delivery Date",     width: 110 },
		{ fieldname: "sales_order",      label: "Sales Order",       width: 150 },
		{ fieldname: "customer",         label: "Customer Name",     width: 150 },
		{ fieldname: "order_fullkit",    label: "Order Fullkit",     width: 110 },
		{ fieldname: "item_code",        label: "Item Code",         width: 120 },
		{ fieldname: "line_fullkit",     label: "Line Fullkit",      width: 110 },
		{ fieldname: "qty",              label: "Order Qty",         width: 90  },
		{ fieldname: "pending_qty",      label: "Qty to Deliver",    width: 110 },
		{ fieldname: "stock_allocation", label: "Stock Allocation",  width: 120 },
		{ fieldname: "__delay_reason",   label: "Delay Reason",      width: 160 },
		{ fieldname: "__delay_remarks",  label: "Delay Remarks",     width: 200 },
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

	// ── DataTable renderer ────────────────────────────────────────────────────
	function render_table($wrap_el, cols, data, editable, tab_key) {
		if (dt_instances[tab_key]) {
			try { dt_instances[tab_key].destroy(); } catch(e) {}
			dt_instances[tab_key] = null;
		}
		$wrap_el.empty();

		if (!data || !data.length) {
			$wrap_el.html(`<div style="text-align:center;padding:60px;color:#888;">No rows match this filter.</div>`);
			return;
		}

		// Build mutable data array — kept in closure so virtual-scroll re-renders pick up live edits
		let dt_data = data.map(row => {
			let ch = changes[row.name] || {};
			let obj = { __soi: row.name || "" };
			cols.forEach(col => {
				if (col.fieldname === "__delay_reason") {
					obj[col.fieldname] = ch.delay_reason !== undefined ? ch.delay_reason : (row.delay_reasons || "");
				} else if (col.fieldname === "__delay_remarks") {
					obj[col.fieldname] = ch.delay_remarks !== undefined ? ch.delay_remarks : (row.delay_remarks || "");
				} else {
					obj[col.fieldname] = row[col.fieldname] !== undefined ? row[col.fieldname] : "";
				}
			});
			return obj;
		});

		let dt_cols = cols.map(col => ({
			name: __(col.label),
			id: col.fieldname,
			width: col.width || 120,
			editable: false,
			resizable: true,
			format(value, row, column, rowData) {
				let soi = rowData ? (rowData.__soi || "") : "";
				if (col.fieldname === "__delay_reason") {
					if (!editable) return frappe.utils.escape_html(String(value || ""));
					let opts = `<option value=""></option>` + delay_reasons.map(r => {
						let sel = (value && value === r.name) ? " selected" : "";
						return `<option value="${frappe.utils.escape_html(r.name)}"${sel}>${frappe.utils.escape_html(r.name)}</option>`;
					}).join("");
					return `<select class="delay-select" data-soi="${frappe.utils.escape_html(soi)}">${opts}</select>`;
				}
				if (col.fieldname === "__delay_remarks") {
					if (!editable) return frappe.utils.escape_html(String(value || ""));
					return `<textarea class="delay-remarks" data-soi="${frappe.utils.escape_html(soi)}" rows="1">${frappe.utils.escape_html(String(value || ""))}</textarea>`;
				}
				return format_cell(col.fieldname, value) || "";
			},
		}));

		let $dt_el = $(`<div></div>`).appendTo($wrap_el);
		dt_instances[tab_key] = new frappe.DataTable($dt_el[0], {
			columns: dt_cols,
			data: dt_data,
			inlineFilters: true,
			layout: "fixed",
			noDataMessage: __("No Data"),
			serialNoColumn: false,
			checkboxColumn: false,
			cellHeight: 35,
			disableReorderColumn: true,
		});

		// Total row pinned below the DataTable
		let total_pending = data.reduce((sum, r) => sum + (parseFloat(r.pending_qty) || 0), 0);
		let pending_idx = cols.findIndex(c => c.fieldname === "pending_qty");
		if (pending_idx >= 0) {
			let total_pending_str = total_pending % 1 === 0 ? total_pending : total_pending.toFixed(2);
			let $total = $(`
				<div class="so-total-row" style="overflow:hidden;">
					<table style="border-collapse:collapse;background:linear-gradient(135deg,#dce8f5,#c5d9ee);table-layout:fixed;">
						<colgroup></colgroup>
						<tr></tr>
					</table>
				</div>
			`);
			$wrap_el.append($total);

			// Mirror the DataTable's actual rendered column widths so the total value
			// stays aligned under the "Qty to Deliver" column, and keep its horizontal
			// scroll in sync with the table body so it moves together when scrolling.
			let sync_total = () => {
				let $scrollable = $dt_el.find(".dt-scrollable");
				// Measure widths from the first body row (one cell per column, no
				// serial/checkbox columns here); fall back to the header row.
				let $cells = $scrollable.find(".dt-row").first().find(".dt-cell");
				if (!$cells.length) $cells = $dt_el.find(".dt-header .dt-cell--header");
				if (!$cells.length) return;

				let widths = $cells.map((i, el) => $(el).outerWidth()).get();
				let $colgroup = $total.find("colgroup").empty();
				let $tr = $total.find("tr").empty();
				let st = "padding:6px 10px;border-top:2px solid #b0c8df;white-space:nowrap;font-size:12px;overflow:hidden;text-overflow:ellipsis;";

				cols.forEach((c, i) => {
					let w = widths[i] || c.width || 120;
					$colgroup.append(`<col style="width:${w}px;">`);
					if (i === 0) {
						$tr.append(`<td style="${st}font-weight:700;">Total</td>`);
					} else if (i === pending_idx) {
						$tr.append(`<td style="${st}font-weight:700;text-align:right;">${total_pending_str}</td>`);
					} else {
						$tr.append(`<td style="${st}"></td>`);
					}
				});

				let total_width = widths.reduce((a, b) => a + b, 0);
				$total.find("table").css("width", total_width + "px");

				let $scroll = $scrollable.length ? $scrollable : $dt_el.find(".dt-scrollable");
				if ($scroll.length) {
					$scroll.off("scroll.so-total").on("scroll.so-total", function () {
						$total.scrollLeft(this.scrollLeft);
					});
					$total.scrollLeft($scroll.scrollLeft());
				}
			};

			// DataTable finalizes column widths asynchronously after construction.
			sync_total();
			setTimeout(sync_total, 100);
			$(window).off("resize.so-total").on("resize.so-total", sync_total);
		}

		if (!editable) return;

		$wrap_el.off("change.so input.so");

		$wrap_el.on("change.so", ".delay-select", function () {
			let soi = $(this).data("soi");
			let val = $(this).val();
			if (!changes[soi]) changes[soi] = {};
			changes[soi].delay_reason = val;
			// Keep dt_data in sync so virtual-scroll re-renders show the updated value
			let dt_row = dt_data.find(r => r.__soi === soi);
			if (dt_row) dt_row.__delay_reason = val;

			let $remarks = $wrap_el.find(`.delay-remarks[data-soi="${soi}"]`);
			let remarks_val = $remarks.val() || "";
			if (val && !remarks_val) {
				$remarks.css({ "border-color": "#e53935", "background": "#fff5f5" });
			} else {
				$remarks.css({ "border-color": "", "background": "" });
			}
		});

		$wrap_el.on("input.so", ".delay-remarks", function () {
			let soi = $(this).data("soi");
			let val = $(this).val();
			if (!changes[soi]) changes[soi] = {};
			changes[soi].delay_remarks = val;
			let dt_row = dt_data.find(r => r.__soi === soi);
			if (dt_row) dt_row.__delay_remarks = val;

			let reason_val = (changes[soi].delay_reason !== undefined)
				? changes[soi].delay_reason
				: (all_data.find(r => r.name === soi) || {}).delay_reasons || "";
			if (reason_val && val) {
				$(this).css({ "border-color": "", "background": "" });
			} else if (reason_val && !val) {
				$(this).css({ "border-color": "#e53935", "background": "#fff5f5" });
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
		render_table($table_wrap_dispatch, COLS_DISPATCH, fd, false, "dispatch");
	}

	function filter_analysis(data, key) {
		active_filter_analysis = key;
		let fd = key === "ALL" ? data : data.filter(r => (r.order_status || "").toUpperCase() === key);
		build_filter_bar($filter_bar_analysis, data, key, k => filter_analysis(data, k));
		render_table($table_wrap_analysis, COLS_ANALYSIS, fd, true, "analysis");
	}

	function render_all(data) {
		filter_analysis(data, active_filter_analysis);
		filter_dispatch(data, active_filter_dispatch);
	}

	// ── execute save ──────────────────────────────────────────────────────────
	function execute_save() {
		if (!Object.keys(changes).length) {
			frappe.show_alert({ message: __("No changes to save."), indicator: "orange" });
			return;
		}

		let missing_remarks = [];
		Object.entries(changes).forEach(([soi_name, vals]) => {
			let existing = all_data.find(r => r.name === soi_name) || {};
			let reason  = vals.delay_reason  !== undefined ? vals.delay_reason  : existing.delay_reasons  || "";
			let remarks = vals.delay_remarks !== undefined ? vals.delay_remarks : existing.delay_remarks || "";
			if (reason && !remarks.trim()) {
				missing_remarks.push(soi_name);
				$table_wrap_analysis.find(`.delay-remarks[data-soi="${soi_name}"]`)
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
			customer:            customer_field.get_value(),
			item_code:           item_code_field.get_value(),
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
		active_filter_analysis = "ALL";
		active_filter_dispatch = "ALL";

		// Destroy existing DataTable instances before clearing the DOM
		Object.keys(dt_instances).forEach(k => {
			if (dt_instances[k]) {
				try { dt_instances[k].destroy(); } catch(e) {}
				dt_instances[k] = null;
			}
		});

		$filter_bar_analysis.empty();
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
					$filter_bar_analysis.empty();
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
