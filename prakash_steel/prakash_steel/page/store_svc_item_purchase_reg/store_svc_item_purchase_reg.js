frappe.pages["store-svc-item-purchase-reg"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Store & Service Item Purchase Register"),
		single_column: true,
	});

	let _ready = false;
	let _dt = null;
	let _active_tab = "regular";
	let _row_count = 0;

	const today = frappe.datetime.get_today();
	const default_from = frappe.datetime.month_start(today);

	if (!$("#ssipr-page-style").length) {
		$("head").append(`
			<style id="ssipr-page-style">
				#ssipr-hbar {
					width: 100%;
					padding: 4px 0 8px;
				}
				#ssipr-hbar .ssipr-hbar-row {
					display: grid;
					grid-template-columns: var(--ssipr-label-w, 300px) minmax(0, 1fr);
					gap: 20px;
					align-items: center;
					margin-bottom: 16px;
				}
				#ssipr-hbar .ssipr-hbar-label {
					font-size: 12px;
					font-weight: 700;
					color: #333;
					line-height: 1.4;
					text-align: left;
					padding-right: 4px;
					min-width: 0;
					white-space: normal;
					word-break: break-word;
					overflow-wrap: break-word;
				}
				#ssipr-hbar .ssipr-hbar-track {
					display: flex;
					align-items: center;
					gap: 10px;
					min-height: 28px;
					min-width: 0;
					background: transparent;
				}
				#ssipr-hbar .ssipr-hbar-bar {
					height: 28px;
					flex: 0 0 auto;
					min-width: 2px;
					max-width: calc(100% - 90px);
					background: #1e3a5f;
					border-radius: 2px;
					box-sizing: border-box;
					transition: width 0.35s ease;
				}
				#ssipr-hbar .ssipr-hbar-amount {
					color: #333;
					font-size: 12px;
					font-weight: 500;
					white-space: nowrap;
					font-variant-numeric: tabular-nums;
					flex-shrink: 0;
				}
				#ssipr-hbar .ssipr-hbar-axis {
					display: grid;
					grid-template-columns: var(--ssipr-label-w, 300px) minmax(0, 1fr);
					gap: 20px;
					margin-top: 4px;
					padding-top: 6px;
					border-top: 1px solid #e8e8e8;
				}
				#ssipr-hbar .ssipr-hbar-axis-spacer {}
				#ssipr-hbar .ssipr-hbar-ticks {
					display: flex;
					justify-content: space-between;
					font-size: 11px;
					color: #888;
					font-variant-numeric: tabular-nums;
				}
				#ssipr-hbar .ssipr-hbar-empty {
					padding: 40px;
					text-align: center;
					color: #888;
					font-size: 14px;
				}
			</style>
		`);
	}

	const from_date_field = page.add_field({
		fieldname: "from_date",
		label: __("From Date"),
		fieldtype: "Date",
		default: default_from,
		reqd: 1,
		change() {
			if (_ready) load_data();
		},
	});

	const to_date_field = page.add_field({
		fieldname: "to_date",
		label: __("To Date"),
		fieldtype: "Date",
		default: today,
		reqd: 1,
		change() {
			if (_ready) load_data();
		},
	});

	const supplier_field = page.add_field({
		fieldname: "supplier",
		label: __("Supplier"),
		fieldtype: "Link",
		options: "Supplier",
		change() {
			if (_ready) load_data();
		},
	});

	const item_code_field = page.add_field({
		fieldname: "item_code",
		label: __("Item Code"),
		fieldtype: "Link",
		options: "Item",
		get_query() {
			if (_active_tab === "regular") {
				return { filters: { custom_store_item: 1 } };
			}
			return { filters: { item_group: "Services" } };
		},
		change() {
			if (_ready) load_data();
		},
	});

	page.add_inner_button(__("Refresh"), () => load_data());

	function export_register(fmt) {
		if (!filters_ready()) {
			frappe.show_alert({
				message: __("Please select From Date and To Date."),
				indicator: "orange",
			});
			return;
		}
		if (!_row_count) {
			frappe.show_alert({
				message: __("Nothing to export — no data for the selected filters."),
				indicator: "orange",
			});
			return;
		}
		open_url_post(
			`/api/method/prakash_steel.prakash_steel.page.store_svc_item_purchase_reg.store_svc_item_purchase_reg.export_${fmt}`,
			Object.fromEntries(
				Object.entries(get_filters()).filter(([, v]) => v !== undefined && v !== "")
			)
		);
	}


	$(`<div id="ssipr-root" style="padding:16px 4px 40px;"></div>`).appendTo(page.main);

	function esc(v) {
		return frappe.utils.escape_html(String(v ?? ""));
	}

	function fmt_currency(v) {
		if (v === null || v === undefined || v === "") return "—";
		const n = parseFloat(v);
		if (isNaN(n)) return "—";
		return format_currency(n, frappe.boot.sysdefaults.currency || "INR");
	}

	function fmt_amount_plain(v) {
		const n = parseFloat(v);
		if (isNaN(n)) return "0";
		return Math.round(n).toLocaleString("en-IN");
	}

	function fmt_date(v) {
		if (!v) return "—";
		return frappe.datetime.str_to_user(v) || v;
	}

	function fmt_num(v) {
		if (v === null || v === undefined || v === "") return "—";
		const n = parseFloat(v);
		if (isNaN(n)) return "—";
		return n.toLocaleString(undefined, { maximumFractionDigits: 6 });
	}

	function get_filters() {
		return {
			from_date: from_date_field.get_value() || undefined,
			to_date: to_date_field.get_value() || undefined,
			supplier: supplier_field.get_value() || undefined,
			item_code: item_code_field.get_value() || undefined,
			party_type: _active_tab,
		};
	}

	function filters_ready() {
		const f = get_filters();
		return Boolean(f.from_date && f.to_date);
	}

	function tab_style(id) {
		return `cursor:pointer;padding:8px 20px;font-size:13px;font-weight:600;
			border-bottom:3px solid ${_active_tab === id ? "#1a7a3f" : "transparent"};
			color:${_active_tab === id ? "#1a7a3f" : "#888"};user-select:none;`;
	}

	function chart_title() {
		return _active_tab === "service"
			? __("Top 5 Service Parties by Amount (₹)")
			: __("Top 5 Regular Parties by Amount (₹)");
	}

	function init_layout() {
		$("#ssipr-root").html(`
			<div id="ssipr-tab-bar" style="display:flex;gap:0;border-bottom:1px solid #e0e0e0;margin-bottom:16px;">
				<span id="ssipr-tab-regular" style="${tab_style("regular")}">${__("Regular Party Details")}</span>
				<span id="ssipr-tab-service" style="${tab_style("service")}">${__("Service Party Details")}</span>
			</div>
			<div id="ssipr-chart-card" style="background:#fff;border:1px solid #e8e8e8;border-radius:6px;padding:16px;margin-bottom:16px;">
				<div style="font-size:14px;font-weight:600;color:#666;margin-bottom:12px;" id="ssipr-chart-title">${esc(chart_title())}</div>
				<div id="ssipr-chart" style="min-height:200px;"></div>
			</div>
			<div id="ssipr-table-wrap"></div>
		`);

		$(document)
			.off("click", "#ssipr-tab-regular")
			.on("click", "#ssipr-tab-regular", () => switch_tab("regular"));
		$(document)
			.off("click", "#ssipr-tab-service")
			.on("click", "#ssipr-tab-service", () => switch_tab("service"));
	}

	function switch_tab(tab) {
		_active_tab = tab;
		$("#ssipr-tab-regular").attr("style", tab_style("regular"));
		$("#ssipr-tab-service").attr("style", tab_style("service"));
		$("#ssipr-chart-title").text(chart_title());
		// Clear item when switching tabs — store vs Services item sets differ.
		if (item_code_field.get_value()) {
			item_code_field.set_value("");
		}
		load_data();
	}

	function show_loading() {
		destroy_dt();
		_row_count = 0;
		$("#ssipr-chart").html(`
			<div style="padding:48px;text-align:center;color:#888;">
				<div style="display:inline-block;width:24px;height:24px;
					border:3px solid #ddd;border-top-color:#1a7a3f;border-radius:50%;
					animation:ssipr-spin 0.8s linear infinite;"></div>
				<span style="margin-left:10px;font-size:14px;">${__("Loading…")}</span>
			</div>
			<style>@keyframes ssipr-spin { to { transform:rotate(360deg); } }</style>
		`);
		$("#ssipr-table-wrap").html("");
	}

	function show_filter_prompt() {
		destroy_dt();
		$("#ssipr-chart").html(`
			<div style="padding:48px;text-align:center;color:#888;font-size:14px;">
				${__("Please select From Date and To Date.")}
			</div>`);
		$("#ssipr-table-wrap").html("");
	}

	function destroy_dt() {
		if (_dt) {
			try {
				_dt.destroy();
			} catch (_) {}
			_dt = null;
		}
	}

	function nice_axis_max(maxVal) {
		if (!maxVal || maxVal <= 0) return 1;
		const padded = maxVal * 1.05;
		const magnitude = Math.pow(10, Math.floor(Math.log10(padded)));
		const normalized = padded / magnitude;
		let nice;
		if (normalized <= 1) nice = 1;
		else if (normalized <= 2) nice = 2;
		else if (normalized <= 5) nice = 5;
		else nice = 10;
		return nice * magnitude;
	}

	function axis_ticks(axisMax, count = 6) {
		const ticks = [];
		for (let i = 0; i < count; i++) {
			ticks.push(Math.round((axisMax * i) / (count - 1)));
		}
		return ticks;
	}

	function label_column_width(parties) {
		const maxLen = Math.max(
			...parties.map((p) => (p.supplier_name || p.supplier || "").length),
			12
		);
		// ~7px per character at 12px; keep room for long party names without overlapping bars.
		return Math.min(420, Math.max(260, Math.ceil(maxLen * 7.2) + 28));
	}

	function render_chart(parties) {
		const mount = document.getElementById("ssipr-chart");
		if (!mount) return;

		if (!parties || !parties.length) {
			mount.innerHTML = `<div class="ssipr-hbar-empty">${__("No party data for the selected filters.")}</div>`;
			return;
		}

		// Already ranked highest→lowest from server; keep that order (top = highest).
		const maxAmount = Math.max(...parties.map((p) => parseFloat(p.amount) || 0), 0);
		const axisMax = nice_axis_max(maxAmount);
		const ticks = axis_ticks(axisMax);

		const labelWidth = label_column_width(parties);

		const rowsHtml = parties
			.map((p) => {
				const amount = parseFloat(p.amount) || 0;
				const pct = axisMax ? Math.max((amount / axisMax) * 100, amount > 0 ? 1.5 : 0) : 0;
				const name = p.supplier_name || p.supplier || "";
				return `
					<div class="ssipr-hbar-row">
						<div class="ssipr-hbar-label" title="${esc(name)}">${esc(name)}</div>
						<div class="ssipr-hbar-track">
							<div class="ssipr-hbar-bar" style="width:${pct}%;" title="${esc(name)}: ${esc(fmt_currency(amount))}"></div>
							<span class="ssipr-hbar-amount">${esc(fmt_amount_plain(amount))}</span>
						</div>
					</div>
				`;
			})
			.join("");

		const ticksHtml = ticks.map((t) => `<span>${esc(t.toLocaleString("en-IN"))}</span>`).join("");

		mount.innerHTML = `
			<div id="ssipr-hbar" style="--ssipr-label-w: ${labelWidth}px;">
				${rowsHtml}
				<div class="ssipr-hbar-axis">
					<div class="ssipr-hbar-axis-spacer"></div>
					<div class="ssipr-hbar-ticks">${ticksHtml}</div>
				</div>
			</div>
		`;
	}

	function table_columns() {
		const cols = [
			{
				name: __("Posting Date"),
				id: "posting_date",
				width: 120,
				align: "left",
				editable: false,
				format: (val) => fmt_date(val),
			},
			{
				name: __("Supplier Name"),
				id: "supplier_name",
				width: 200,
				align: "left",
				editable: false,
				format: (val, _r, _c, d) => {
					const name = d && d.supplier ? d.supplier : val;
					return name
						? `<a href="/app/supplier/${encodeURIComponent(name)}" target="_blank">${esc(val || name)}</a>`
						: "—";
				},
			},
			{
				name: __("Item Code"),
				id: "item_code",
				width: 160,
				align: "left",
				editable: false,
				format: (val) =>
					val
						? `<a href="/app/item/${encodeURIComponent(val)}" target="_blank">${esc(val)}</a>`
						: "—",
			},
			{
				name: _active_tab === "service" ? __("Qty") : __("Stock Qty"),
				id: "stock_qty",
				width: 110,
				align: "right",
				editable: false,
				format: (val) => fmt_num(val),
			},
			{
				name: _active_tab === "service" ? __("UOM") : __("Stock UOM"),
				id: "stock_uom",
				width: 100,
				align: "left",
				editable: false,
				format: (val) => esc(val || "—"),
			},
			{
				name: __("Rate"),
				id: "rate",
				width: 120,
				align: "right",
				editable: false,
				format: (val) => fmt_currency(val),
			},
		];

		if (_active_tab === "regular") {
			cols.push({
				name: __("Set Accepted Warehouse"),
				id: "set_accepted_warehouse",
				width: 180,
				align: "left",
				editable: false,
				format: (val) =>
					val
						? `<a href="/app/warehouse/${encodeURIComponent(val)}" target="_blank">${esc(val)}</a>`
						: "—",
			});
		}

		cols.push({
			name: __("Amount"),
			id: "amount",
			width: 130,
			align: "right",
			editable: false,
			format: (val) => fmt_currency(val),
		});

		return cols;
	}

	function render_table(rows) {
		destroy_dt();
		_row_count = (rows || []).length;

		if (!rows || !rows.length) {
			$("#ssipr-table-wrap").html(`
				<div style="padding:48px;text-align:center;color:#888;font-size:14px;">
					${__("No data found for the selected filters.")}
				</div>`);
			return;
		}

		$("#ssipr-table-wrap").html(`
			<div style="display:flex;justify-content:flex-end;gap:8px;margin-bottom:8px;">
				<button class="btn btn-default btn-xs" id="ssipr-export-xlsx">${__("Export Excel")}</button>
				<button class="btn btn-default btn-xs" id="ssipr-export-pdf">${__("Export PDF")}</button>
			</div>
			<div id="ssipr-dt" style="overflow-x:auto;"></div>`);
		$("#ssipr-export-xlsx").on("click", () => export_register("xlsx"));
		$("#ssipr-export-pdf").on("click", () => export_register("pdf"));

		_dt = new DataTable(document.getElementById("ssipr-dt"), {
			columns: table_columns(),
			data: rows,
			serialNoColumn: true,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: true,
			noDataMessage: __("No data found."),
			layout: "fixed",
		});
	}

	function load_data() {
		if (!filters_ready()) {
			show_filter_prompt();
			return;
		}

		show_loading();
		frappe.call({
			method:
				"prakash_steel.prakash_steel.page.store_svc_item_purchase_reg.store_svc_item_purchase_reg.get_register_data",
			args: get_filters(),
			callback(r) {
				const payload = r.message || {};
				render_chart(payload.chart || []);
				render_table(payload.rows || []);
			},
			error() {
				destroy_dt();
				$("#ssipr-chart").html(`
					<div style="padding:40px;text-align:center;color:#c00;font-size:14px;">
						${__("Failed to load data.")}
					</div>`);
				$("#ssipr-table-wrap").html("");
			},
		});
	}

	init_layout();
	_ready = true;
	load_data();
};
