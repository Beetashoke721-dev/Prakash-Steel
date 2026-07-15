frappe.pages["unsecured-loans-txn"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Unsecured Loans and Transaction"),
		single_column: true,
	});

	const FINANCIAL_YEAR_ORDER = [
		"April",
		"May",
		"June",
		"July",
		"August",
		"September",
		"October",
		"November",
		"December",
		"January",
		"February",
		"March",
	];

	const financial_year_field = page.add_field({
		fieldname: "financial_year",
		label: __("Financial Year"),
		fieldtype: "Link",
		options: "Fiscal Year",
		reqd: 1,
		change() {
			month_field.set_value("");
			account_head_field.set_value("");
			load_data();
		},
	});

	const month_field = page.add_field({
		fieldname: "month",
		label: __("Month"),
		fieldtype: "Select",
		options: ["", ...FINANCIAL_YEAR_ORDER].join("\n"),
		change() {
			load_data();
		},
	});

	const account_head_field = page.add_field({
		fieldname: "account_head",
		label: __("Account Head"),
		fieldtype: "Link",
		options: "Account",
		reqd: 1,
		get_query() {
			return {
				filters: [
					[
						"parent_account",
						"in",
						[
							"Loan From Director - PSPL",
							"Loan From Shareholders - PSPL",
							"Unsecured Loan - PSPL",
						],
					],
					["is_group", "=", 0],
				],
			};
		},
		change() {
			load_data();
		},
	});

	page.add_inner_button(__("Refresh"), () => load_data());

	$(`<div id="ult-root" style="padding:16px 4px 40px;"></div>`).appendTo(page.main);

	let _dt = null;
	let _active_tab = "summary";
	let _cached_details = null;

	function esc(v) {
		return frappe.utils.escape_html(String(v ?? ""));
	}

	function fmt_currency(v) {
		if (v === null || v === undefined || v === "") return "—";
		const n = parseFloat(v);
		if (isNaN(n)) return "—";
		return format_currency(n, frappe.boot.sysdefaults.currency || "INR");
	}

	function fmt_num(v, dec = 6) {
		if (v === null || v === undefined || v === "") return "—";
		const n = parseFloat(v);
		if (isNaN(n)) return "—";
		return n.toLocaleString(undefined, {
			minimumFractionDigits: 0,
			maximumFractionDigits: dec,
		});
	}

	function fmt_date(v) {
		if (!v) return "—";
		return frappe.datetime.str_to_user(v) || v;
	}

	function get_filters() {
		return {
			financial_year: financial_year_field.get_value() || undefined,
			month: month_field.get_value() || undefined,
			account_head: account_head_field.get_value() || undefined,
		};
	}

	function filters_ready() {
		const f = get_filters();
		return Boolean(f.financial_year && f.account_head);
	}

	function show_filter_prompt() {
		$("#ult-tab-content").html(`
			<div style="padding:48px;text-align:center;color:#888;font-size:14px;">
				Please select <strong>Financial Year</strong> and <strong>Account Head</strong> to load data.
			</div>`);
	}

	function show_loading() {
		$("#ult-tab-content").html(`
			<div style="padding:32px;text-align:center;color:#888;">
				<div style="display:inline-block;width:24px;height:24px;
					border:3px solid #ddd;border-top-color:#1a7a3f;border-radius:50%;
					animation:ult-spin 0.8s linear infinite;"></div>
				<span style="margin-left:10px;font-size:14px;">${__("Loading…")}</span>
			</div>
			<style>@keyframes ult-spin { to { transform:rotate(360deg); } }</style>
		`);
	}

	function show_empty() {
		$("#ult-tab-content").html(`
			<div style="padding:48px;text-align:center;color:#888;font-size:14px;">
				${__("No data found for the selected filters.")}
			</div>`);
	}

	function destroy_dt() {
		if (_dt) {
			try {
				_dt.destroy();
			} catch (_) {}
			_dt = null;
		}
	}

	function export_url(method) {
		const url = new URL(
			frappe.urllib.get_full_url(`/api/method/${method}`)
		);
		const f = get_filters();
		if (f.financial_year) url.searchParams.set("financial_year", f.financial_year);
		if (f.month) url.searchParams.set("month", f.month);
		if (f.account_head) url.searchParams.set("account_head", f.account_head);
		return url.toString();
	}

	function bind_export(btn_id, method) {
		$(btn_id)
			.off("click")
			.on("click", () => {
				if (!filters_ready()) {
					frappe.msgprint(__("Please select Financial Year and Account Head."));
					return;
				}
				window.open(export_url(method));
			});
	}

	function tab_style(id) {
		return `cursor:pointer;padding:8px 20px;font-size:13px;font-weight:600;
			border-bottom:3px solid ${_active_tab === id ? "#1a7a3f" : "transparent"};
			color:${_active_tab === id ? "#1a7a3f" : "#888"};user-select:none;`;
	}

	function init_tabs() {
		$("#ult-root").html(`
			<div id="ult-tab-bar" style="display:flex;gap:0;border-bottom:1px solid #e0e0e0;margin-bottom:16px;">
				<span id="ult-tab-summary" style="${tab_style("summary")}">${__("Month-wise Summary")}</span>
				<span id="ult-tab-details" style="${tab_style("details")}">${__("Transaction Details")}</span>
			</div>
			<div id="ult-tab-content"></div>
		`);
		$(document)
			.off("click", "#ult-tab-summary")
			.on("click", "#ult-tab-summary", () => switch_tab("summary"));
		$(document)
			.off("click", "#ult-tab-details")
			.on("click", "#ult-tab-details", () => switch_tab("details"));
	}

	function switch_tab(tab) {
		_active_tab = tab;
		$("#ult-tab-summary").attr("style", tab_style("summary"));
		$("#ult-tab-details").attr("style", tab_style("details"));
		load_data();
	}

	function render_month_wise(rows) {
		destroy_dt();

		if (!rows.length) {
			show_empty();
			return;
		}

		$("#ult-tab-content").html(`
			<div style="display:flex;justify-content:flex-end;margin-bottom:10px;">
				<button id="ult-summary-export-btn" style="
					padding:6px 16px;font-size:12px;font-weight:600;
					border:1px solid #d0d0d0;border-radius:4px;
					background:#fff;color:#333;cursor:pointer;">
					⬇ ${__("Export")}
				</button>
			</div>
			<div id="ult-dt" style="overflow-x:auto;"></div>
		`);

		const data = rows.map((r) => ({
			...r,
			_is_total: r.month === "Total",
		}));

		_dt = new DataTable(document.getElementById("ult-dt"), {
			columns: [
				{
					name: __("Month"),
					id: "month",
					width: 140,
					align: "left",
					editable: false,
					format: (val, _r, _c, d) =>
						d._is_total
							? `<strong>${esc(val)}</strong>`
							: `<span>${esc(val)}</span>`,
				},
				{
					name: __("TDS (10%)"),
					id: "tds_10",
					width: 160,
					align: "right",
					editable: false,
					format: (val, _r, _c, d) =>
						d._is_total
							? `<strong>${fmt_currency(val)}</strong>`
							: fmt_currency(val),
				},
				{
					name: __("Total Amount"),
					id: "total_amount",
					width: 160,
					align: "right",
					editable: false,
					format: (val, _r, _c, d) =>
						d._is_total
							? `<strong>${fmt_currency(val)}</strong>`
							: fmt_currency(val),
				},
			],
			data,
			serialNoColumn: false,
			checkboxColumn: false,
			inlineFilters: false,
			clusterize: false,
			noDataMessage: __("No data found."),
			layout: "fixed",
		});

		bind_export(
			"#ult-summary-export-btn",
			"prakash_steel.prakash_steel.page.unsecured_loans_txn.unsecured_loans_txn.export_month_wise_xlsx"
		);
	}

	function render_details(rows) {
		destroy_dt();

		if (!rows.length) {
			show_empty();
			return;
		}

		$("#ult-tab-content").html(`
			<div style="display:flex;justify-content:flex-end;margin-bottom:10px;">
				<button id="ult-details-export-btn" style="
					padding:6px 16px;font-size:12px;font-weight:600;
					border:1px solid #d0d0d0;border-radius:4px;
					background:#fff;color:#333;cursor:pointer;">
					⬇ ${__("Export")}
				</button>
			</div>
			<div id="ult-dt" style="overflow-x:auto;"></div>
		`);

		_dt = new DataTable(document.getElementById("ult-dt"), {
			columns: [
				{
					name: __("Month"),
					id: "month",
					width: 110,
					align: "left",
					editable: false,
					format: (val, _r, _c, d) =>
						d.name === "Total" || d.month === "Total"
							? `<strong>${__("Total")}</strong>`
							: esc(val),
				},
				{
					name: __("Date"),
					id: "detail_date",
					width: 110,
					align: "left",
					editable: false,
					format: (val, _r, _c, d) =>
						d.name === "Total" || d.month === "Total" ? "" : fmt_date(val),
				},
				{
					name: __("Account Head"),
					id: "unsecured_loan",
					width: 220,
					align: "left",
					editable: false,
					format: (val, _r, _c, d) =>
						d.name === "Total" || d.month === "Total" ? "" : esc(val || ""),
				},
				{
					name: __("Interest % Per Annum"),
					id: "interest_percent",
					width: 140,
					align: "right",
					editable: false,
					format: (val, _r, _c, d) =>
						d.name === "Total" || d.month === "Total" ? "" : fmt_num(val, 3),
				},
				{
					name: __("Closing Balance"),
					id: "closing_balance",
					width: 140,
					align: "right",
					editable: false,
					format: (val, _r, _c, d) =>
						d.name === "Total" || d.month === "Total" ? "" : fmt_currency(val),
				},
				{
					name: __("Interest per Day"),
					id: "day_interest",
					width: 130,
					align: "right",
					editable: false,
					format: (val, _r, _c, d) =>
						d.name === "Total" || d.month === "Total" ? "" : fmt_num(val, 6),
				},
				{
					name: __("Interest Amount"),
					id: "interest_amount",
					width: 140,
					align: "right",
					editable: false,
					format: (val, _r, _c, d) =>
						d.name === "Total" || d.month === "Total"
							? `<strong>${fmt_currency(val)}</strong>`
							: fmt_currency(val),
				},
				{
					name: __("TDS (10%)"),
					id: "tds_10",
					width: 120,
					align: "right",
					editable: false,
					format: (val, _r, _c, d) =>
						d.name === "Total" || d.month === "Total"
							? `<strong>${fmt_currency(val)}</strong>`
							: fmt_currency(val),
				},
				{
					name: __("Total Amount"),
					id: "total_amount",
					width: 140,
					align: "right",
					editable: false,
					format: (val, _r, _c, d) =>
						d.name === "Total" || d.month === "Total"
							? `<strong>${fmt_currency(val)}</strong>`
							: fmt_currency(val),
				},
				{
					name: __("Voucher"),
					id: "name",
					width: 200,
					align: "left",
					editable: false,
					format: (val, _r, _c, d) => {
						if (!val || val === "Total" || d.month === "Total") return "";
						return `<a href="/app/unsecured-loans-and-transaction/${encodeURIComponent(val)}"
							style="color:#1565c0;font-weight:500;">${esc(val)}</a>`;
					},
				},
			],
			data: rows,
			serialNoColumn: false,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: true,
			noDataMessage: __("No data found."),
			layout: "fixed",
		});

		bind_export(
			"#ult-details-export-btn",
			"prakash_steel.prakash_steel.page.unsecured_loans_txn.unsecured_loans_txn.export_details_xlsx"
		);
	}

	function load_month_wise() {
		if (!filters_ready()) {
			show_filter_prompt();
			return;
		}

		show_loading();
		const f = get_filters();

		frappe.call({
			method:
				"prakash_steel.prakash_steel.page.unsecured_loans_txn.unsecured_loans_txn.get_month_wise_summary",
			args: f,
			callback(r) {
				render_month_wise(r.message || []);
			},
			error() {
				show_empty();
			},
		});
	}

	function load_details(force = false) {
		if (!filters_ready()) {
			show_filter_prompt();
			return;
		}

		if (!force && _cached_details) {
			render_details(_cached_details);
			return;
		}

		show_loading();
		const f = get_filters();

		frappe.call({
			method: "frappe.desk.query_report.run",
			args: {
				report_name: "PSP Unsecured Loans and Transaction Report",
				filters: f,
			},
			callback(r) {
				const result = r.message;
				if (!result || !result.result || !result.result.length) {
					_cached_details = [];
					show_empty();
					return;
				}

				const col_names = (result.columns || []).map((c) =>
					typeof c === "string" ? c.split(":")[0] : c.fieldname
				);
				const data = result.result.map((row) => {
					if (Array.isArray(row)) {
						const obj = {};
						col_names.forEach((key, i) => {
							obj[key] = row[i];
						});
						return obj;
					}
					return row;
				});

				_cached_details = data;
				render_details(data);
			},
			error() {
				_cached_details = null;
				show_empty();
			},
		});
	}

	function load_data() {
		_cached_details = null;
		if (_active_tab === "summary") {
			load_month_wise();
		} else {
			load_details(true);
		}
	}

	_active_tab = "summary";
	init_tabs();
	show_filter_prompt();
};
