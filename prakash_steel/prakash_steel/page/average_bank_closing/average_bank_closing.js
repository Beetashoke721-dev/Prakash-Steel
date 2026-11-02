frappe.pages["average-bank-closing"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Average Bank Closing"),
		single_column: true,
	});

	let _ready = false;
	let _dt = null;
	let _active_tab = "details";

	const today = frappe.datetime.get_today();
	const default_from = frappe.datetime.add_months(today, -1);

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

	const bank_account_field = page.add_field({
		fieldname: "bank_account",
		label: __("Bank Account"),
		fieldtype: "Link",
		options: "Account",
		reqd: 1,
		get_query() {
			const filters = {
				account_type: "Bank",
				is_group: 0,
				disabled: 0,
			};
			const company = frappe.defaults.get_user_default("Company");
			if (company) filters.company = company;
			return { filters };
		},
		change() {
			if (_ready) load_data();
		},
	});

	page.add_inner_button(__("Refresh"), () => load_data());

	$(`<div id="abc-root" style="padding:16px 4px 40px;"></div>`).appendTo(page.main);

	function esc(v) {
		return frappe.utils.escape_html(String(v ?? ""));
	}

	function fmt_currency(v) {
		if (v === null || v === undefined || v === "") return "—";
		const n = parseFloat(v);
		if (isNaN(n)) return "—";
		return format_currency(n, frappe.boot.sysdefaults.currency || "INR");
	}

	function fmt_date(v) {
		if (!v) return "—";
		return frappe.datetime.str_to_user(v) || v;
	}

	function is_footer(d) {
		return d && (d.row_type === "Average" || d.row_type === "Total");
	}

	function fmt_footer_label(d) {
		return `<strong>${esc(__(d.row_type))}</strong>`;
	}

	function fmt_footer_currency(val) {
		return `<strong>${fmt_currency(val)}</strong>`;
	}

	function get_filters() {
		return {
			from_date: from_date_field.get_value() || undefined,
			to_date: to_date_field.get_value() || undefined,
			bank_account: bank_account_field.get_value() || undefined,
		};
	}

	function filters_ready() {
		const f = get_filters();
		return Boolean(f.from_date && f.to_date && f.bank_account);
	}

	function show_filter_prompt() {
		$("#abc-tab-content").html(`
			<div style="padding:48px;text-align:center;color:#888;font-size:14px;">
				${__("Please select")} <strong>${__("Bank Account")}</strong> ${__("to load data.")}
			</div>`);
	}

	function show_loading() {
		$("#abc-tab-content").html(`
			<div style="padding:32px;text-align:center;color:#888;">
				<div style="display:inline-block;width:24px;height:24px;
					border:3px solid #ddd;border-top-color:#1a7a3f;border-radius:50%;
					animation:abc-spin 0.8s linear infinite;"></div>
				<span style="margin-left:10px;font-size:14px;">${__("Loading…")}</span>
			</div>
			<style>@keyframes abc-spin { to { transform:rotate(360deg); } }</style>
		`);
	}

	function show_empty() {
		$("#abc-tab-content").html(`
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

	function tab_style(id) {
		return `cursor:pointer;padding:8px 20px;font-size:13px;font-weight:600;
			border-bottom:3px solid ${_active_tab === id ? "#1a7a3f" : "transparent"};
			color:${_active_tab === id ? "#1a7a3f" : "#888"};user-select:none;`;
	}

	function init_tabs() {
		$("#abc-root").html(`
			<div id="abc-tab-bar" style="display:flex;gap:0;border-bottom:1px solid #e0e0e0;margin-bottom:16px;">
				<span id="abc-tab-summary" style="${tab_style("summary")}">${__("Month-wise Summary")}</span>
				<span id="abc-tab-details" style="${tab_style("details")}">${__("Transaction Details")}</span>
			</div>
			<div id="abc-tab-content"></div>
		`);
		$(document)
			.off("click", "#abc-tab-summary")
			.on("click", "#abc-tab-summary", () => switch_tab("summary"));
		$(document)
			.off("click", "#abc-tab-details")
			.on("click", "#abc-tab-details", () => switch_tab("details"));
	}

	function switch_tab(tab) {
		_active_tab = tab;
		$("#abc-tab-summary").attr("style", tab_style("summary"));
		$("#abc-tab-details").attr("style", tab_style("details"));
		load_data();
	}

	function render_month_wise(rows) {
		destroy_dt();

		if (!rows.length) {
			show_empty();
			return;
		}

		$("#abc-tab-content").html(`<div id="abc-dt" style="overflow-x:auto;"></div>`);

		_dt = new DataTable(document.getElementById("abc-dt"), {
			columns: [
				{
					name: __("Month"),
					id: "month",
					width: 180,
					align: "left",
					editable: false,
					format: (val, _r, _c, d) =>
						is_footer(d) ? fmt_footer_label(d) : `<span>${esc(val)}</span>`,
				},
				{
					name: __("Account Head"),
					id: "account_head",
					width: 320,
					align: "left",
					editable: false,
					format: (val, _r, _c, d) => (is_footer(d) ? "" : esc(val || "")),
				},
				{
					name: __("Avg Closing Balance"),
					id: "closing_balance",
					width: 180,
					align: "right",
					editable: false,
					format: (val, _r, _c, d) =>
						is_footer(d) ? fmt_footer_currency(val) : fmt_currency(val),
				},
			],
			data: rows,
			serialNoColumn: false,
			checkboxColumn: false,
			inlineFilters: false,
			clusterize: false,
			noDataMessage: __("No data found."),
			layout: "fixed",
		});
	}

	function render_details(rows) {
		destroy_dt();

		if (!rows.length) {
			show_empty();
			return;
		}

		$("#abc-tab-content").html(`<div id="abc-dt" style="overflow-x:auto;"></div>`);

		_dt = new DataTable(document.getElementById("abc-dt"), {
			columns: [
				{
					name: __("Date"),
					id: "detail_date",
					width: 160,
					align: "left",
					editable: false,
					format: (val, _r, _c, d) => (is_footer(d) ? fmt_footer_label(d) : fmt_date(val)),
				},
				{
					name: __("Account Head"),
					id: "account_head",
					width: 320,
					align: "left",
					editable: false,
					format: (val, _r, _c, d) => (is_footer(d) ? "" : esc(val || "")),
				},
				{
					name: __("Closing Balance"),
					id: "closing_balance",
					width: 180,
					align: "right",
					editable: false,
					format: (val, _r, _c, d) =>
						is_footer(d) ? fmt_footer_currency(val) : fmt_currency(val),
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
	}

	function load_month_wise() {
		if (!filters_ready()) {
			show_filter_prompt();
			return;
		}

		show_loading();
		frappe.call({
			method:
				"prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing.get_month_wise_summary",
			args: get_filters(),
			callback(r) {
				render_month_wise(r.message || []);
			},
			error() {
				show_empty();
			},
		});
	}

	function load_details() {
		if (!filters_ready()) {
			show_filter_prompt();
			return;
		}

		show_loading();
		frappe.call({
			method:
				"prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing.get_transaction_details",
			args: get_filters(),
			callback(r) {
				render_details(r.message || []);
			},
			error() {
				show_empty();
			},
		});
	}

	function load_data() {
		if (_active_tab === "summary") {
			load_month_wise();
		} else {
			load_details();
		}
	}

	_active_tab = "details";
	init_tabs();
	_ready = true;
	load_data();
};
