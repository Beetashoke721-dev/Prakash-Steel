frappe.pages["desc-code-wise-summa"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Desc Code Wise Summary"),
		single_column: true,
	});

	let _ready = false;
	let _dt = null;
	let _active_tab = "hsn_report";
	let _active_subtab = null;

	// Snapshot of whatever table is currently on screen, for "Export to Excel".
	let _export_rows = [];
	let _export_columns = []; // [[fieldname, label], ...]
	let _export_title = "";

	function set_export(columns, rows, title) {
		_export_columns = columns.map((c) => [c.id, c.name]);
		_export_rows = rows;
		_export_title = title;
	}

	function clear_export() {
		_export_rows = [];
		_export_columns = [];
		_export_title = "";
	}

	const TABS = [
		{ id: "hsn_report", label: __("HSN Report"), color: "#2e8b57" },
		{ id: "sale", label: __("Sale"), color: "#0f766e" },
		{ id: "purchase", label: __("Purchase"), color: "#2563eb" },
		{ id: "sales_return", label: __("Sales Return"), color: "#d97706" },
		{ id: "purchase_return", label: __("Purchase Return"), color: "#dc2626" },
		{ id: "stock", label: __("Stock"), color: "#7c3aed" },
	];
	const TAB_BY_ID = Object.fromEntries(TABS.map((t) => [t.id, t]));

	const SUB_TABS_BY_TAB = {
		sales_return: [
			{ id: "debit_note", label: __("Debit Note") },
			{ id: "credit_note", label: __("Credit Note") },
		],
		purchase_return: [
			{ id: "debit_note", label: __("Debit Note") },
			{ id: "credit_note", label: __("Credit Note") },
		],
	};

	function active_color() {
		return (TAB_BY_ID[_active_tab] || {}).color || "#2e8b57";
	}

	function active_subtabs() {
		return SUB_TABS_BY_TAB[_active_tab] || null;
	}

	function content_selector() {
		return active_subtabs() ? "#dcws-subtab-content" : "#dcws-tab-content";
	}

	const from_date_field = page.add_field({
		fieldname: "from_date",
		label: __("From Date"),
		fieldtype: "Date",
		change() {
			if (_ready) load_data();
		},
	});

	const to_date_field = page.add_field({
		fieldname: "to_date",
		label: __("To Date"),
		fieldtype: "Date",
		change() {
			if (_ready) load_data();
		},
	});

	page.add_inner_button(__("Refresh"), () => load_data());

	page.add_inner_button(__("Export to Excel"), () => {
		if (!_export_rows.length) {
			frappe.show_alert({
				message: __("Nothing to export — load data first."),
				indicator: "orange",
			});
			return;
		}
		open_url_post(
			"/api/method/prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa.export_xlsx",
			{
				rows: JSON.stringify(_export_rows),
				columns: JSON.stringify(_export_columns),
				title: _export_title,
			}
		);
	});

	$(`<div id="dcws-root" style="padding:16px 4px 40px;"></div>`).appendTo(page.main);

	function tab_style(id) {
		const color = (TAB_BY_ID[id] || {}).color || "#2e8b57";
		const is_active = _active_tab === id;
		return `cursor:pointer;padding:7px 18px;font-size:13px;font-weight:600;
			border-radius:999px;user-select:none;transition:background 0.15s,color 0.15s;
			background:${is_active ? color : `${color}18`};
			color:${is_active ? "#fff" : color};`;
	}

	function init_tabs() {
		$("#dcws-root").html(`
			<div id="dcws-tab-bar" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px;">
				${TABS.map((t) => `<span class="dcws-tab" data-tab="${t.id}" style="${tab_style(t.id)}">${t.label}</span>`).join("")}
			</div>
			<div id="dcws-tab-content"></div>
		`);
		$(document)
			.off("click", ".dcws-tab")
			.on("click", ".dcws-tab", (e) => switch_tab($(e.currentTarget).data("tab")));
	}

	function switch_tab(tab) {
		_active_tab = tab;
		const subtabs = SUB_TABS_BY_TAB[tab];
		_active_subtab = subtabs ? subtabs[0].id : null;
		$(".dcws-tab").each(function () {
			$(this).attr("style", tab_style($(this).data("tab")));
		});
		load_data();
	}

	function subtab_style(id) {
		const color = active_color();
		const is_active = _active_subtab === id;
		return `cursor:pointer;padding:5px 14px;font-size:12px;font-weight:600;
			border-radius:6px;user-select:none;border:1px solid ${color}55;
			background:${is_active ? color : "transparent"};
			color:${is_active ? "#fff" : color};`;
	}

	function init_subtabs() {
		const subtabs = active_subtabs();
		$("#dcws-tab-content").html(`
			<div id="dcws-subtab-bar" style="display:flex;gap:6px;margin-bottom:14px;">
				${subtabs.map((st) => `<span class="dcws-subtab" data-subtab="${st.id}" style="${subtab_style(st.id)}">${st.label}</span>`).join("")}
			</div>
			<div id="dcws-subtab-content"></div>
		`);
		$(document)
			.off("click", ".dcws-subtab")
			.on("click", ".dcws-subtab", (e) => switch_subtab($(e.currentTarget).data("subtab")));
	}

	function switch_subtab(subtab) {
		_active_subtab = subtab;
		$(".dcws-subtab").each(function () {
			$(this).attr("style", subtab_style($(this).data("subtab")));
		});
		load_subtab_data();
	}

	function load_subtab_data() {
		show_loading();
		frappe.call({
			method:
				"prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa.get_return_summary",
			args: {
				return_type: _active_tab,
				note_type: _active_subtab,
				...get_filters(),
			},
			callback(r) {
				render_return_summary(r.message || []);
			},
			error() {
				show_empty();
			},
		});
	}

	function esc(v) {
		return frappe.utils.escape_html(String(v ?? ""));
	}

	function fmt_currency(v) {
		if (v === null || v === undefined || v === "") return "—";
		const n = parseFloat(v);
		if (isNaN(n)) return "—";
		return format_currency(n, frappe.boot.sysdefaults.currency || "INR");
	}

	function fmt_number(v) {
		if (v === null || v === undefined || v === "") return "—";
		const n = parseFloat(v);
		if (isNaN(n)) return "—";
		return format_number(n);
	}

	function is_footer(d) {
		return d && d.row_type === "Total";
	}

	function footer_badge(html) {
		const color = active_color();
		return `<span style="background:${color}22;color:${color};font-weight:700;
			padding:3px 10px;border-radius:6px;">${html}</span>`;
	}

	function fmt_footer_label(d) {
		return footer_badge(esc(__(d.row_type)));
	}

	function fmt_footer_currency(val) {
		return footer_badge(fmt_currency(val));
	}

	function fmt_footer_int(val) {
		return footer_badge(esc(val ?? ""));
	}

	function fmt_footer_number(val) {
		return footer_badge(fmt_number(val));
	}

	function get_filters() {
		return {
			from_date: from_date_field.get_value() || undefined,
			to_date: to_date_field.get_value() || undefined,
		};
	}

	function show_loading() {
		clear_export();
		$(content_selector()).html(`
			<div style="padding:32px;text-align:center;color:#888;">
				<div style="display:inline-block;width:24px;height:24px;
					border:3px solid #ddd;border-top-color:${active_color()};border-radius:50%;
					animation:dcws-spin 0.8s linear infinite;"></div>
				<span style="margin-left:10px;font-size:14px;">${__("Loading…")}</span>
			</div>
			<style>@keyframes dcws-spin { to { transform:rotate(360deg); } }</style>
		`);
	}

	function show_empty() {
		clear_export();
		$(content_selector()).html(`
			<div style="padding:48px;text-align:center;color:#888;font-size:14px;
				border:1px dashed ${active_color()}55;border-radius:8px;background:${active_color()}0d;">
				${__("No data found for the selected filters.")}
			</div>`);
	}

	function show_placeholder(label) {
		clear_export();
		destroy_dt();
		const color = active_color();
		$(content_selector()).html(`
			<div style="padding:48px;text-align:center;color:#888;font-size:14px;
				border:1px dashed ${color}55;border-radius:8px;background:${color}0d;">
				<strong style="color:${color};">${esc(label)}</strong> ${__("logic will be added soon.")}
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

	function money_fmt(val, _r, _c, d) {
		return is_footer(d) ? fmt_footer_currency(val) : fmt_currency(val);
	}

	// Qty + the value columns shared by every summary/detail table.
	function metric_columns() {
		return [
			{
				name: __("Qty"),
				id: "qty",
				width: 100,
				align: "right",
				editable: false,
				format: (val, _r, _c, d) => (is_footer(d) ? fmt_footer_int(val) : esc(val ?? "")),
			},
			{
				name: __("Taxable Value"),
				id: "taxable_value",
				width: 130,
				align: "right",
				editable: false,
				format: money_fmt,
			},
			{
				name: __("CGST Amt"),
				id: "cgst_amt",
				width: 120,
				align: "right",
				editable: false,
				format: money_fmt,
			},
			{
				name: __("SGST Amt"),
				id: "sgst_amt",
				width: 120,
				align: "right",
				editable: false,
				format: money_fmt,
			},
			{
				name: __("IGST Amt"),
				id: "igst_amt",
				width: 120,
				align: "right",
				editable: false,
				format: money_fmt,
			},
			{
				name: __("Total Taxes and Charges"),
				id: "total_taxes_and_charges",
				width: 150,
				align: "right",
				editable: false,
				format: money_fmt,
			},
			{
				name: __("Gross Total"),
				id: "gross_total",
				width: 130,
				align: "right",
				editable: false,
				format: money_fmt,
			},
		];
	}

	function render_return_summary(rows) {
		destroy_dt();

		if (!rows.length) {
			show_empty();
			return;
		}

		const color = active_color();
		const tab = TAB_BY_ID[_active_tab];
		const subtabs = active_subtabs();
		const subtab_label = subtabs
			? (subtabs.find((st) => st.id === _active_subtab) || {}).label
			: null;
		const title = subtab_label ? `${tab.label} — ${subtab_label}` : tab ? tab.label : "";
		const is_purchase = _active_tab === "purchase_return";
		const invoice_col_label = is_purchase
			? __("Purchase Invoice ID")
			: __("Sales Invoice ID");
		const note_col_label =
			_active_subtab === "credit_note" ? __("Credit Note No") : __("Debit Note No");
		const party_col_label = is_purchase ? __("Supplier") : __("Customer");

		$(content_selector()).html(`
			<div style="border-left:4px solid ${color};padding:6px 0 6px 12px;margin-bottom:12px;">
				<span style="color:${color};font-weight:700;font-size:14px;">${esc(title)} ${__("Summary")}</span>
			</div>
			<div id="dcws-dt" style="overflow-x:auto;"></div>
		`);

		const columns = [
			{
				name: __("Item Code"),
				id: "item_code",
				width: 170,
				align: "left",
				editable: false,
				format: (val, _r, _c, d) =>
					is_footer(d) ? fmt_footer_label(d) : esc(val || ""),
			},
			{
				name: note_col_label,
				id: "note_no",
				width: 150,
				align: "left",
				editable: false,
				format: (val, _r, _c, d) => (is_footer(d) ? "" : esc(val || "")),
			},
			{
				name: invoice_col_label,
				id: "return_against",
				width: 150,
				align: "left",
				editable: false,
				format: (val, _r, _c, d) => (is_footer(d) ? "" : esc(val || "")),
			},
			{
				name: __("Date"),
				id: "posting_date",
				width: 110,
				align: "left",
				editable: false,
				format: (val, _r, _c, d) =>
					is_footer(d) || !val ? "" : esc(frappe.datetime.str_to_user(val)),
			},
			{
				name: party_col_label,
				id: "party_name",
				width: 190,
				align: "left",
				editable: false,
				format: (val, _r, _c, d) => (is_footer(d) ? "" : esc(val || "")),
			},
			{
				name: __("HSN Code"),
				id: "hsn_code",
				width: 120,
				align: "left",
				editable: false,
				format: (val, _r, _c, d) => (is_footer(d) ? "" : esc(val || "")),
			},
			...metric_columns(),
		];

		set_export(columns, rows, `${title} ${__("Summary")}`);

		_dt = new DataTable(document.getElementById("dcws-dt"), {
			columns,
			data: rows,
			serialNoColumn: true,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: true,
			noDataMessage: __("No data found."),
			layout: "fixed",
		});
	}

	function render_summary(rows) {
		destroy_dt();

		if (!rows.length) {
			show_empty();
			return;
		}

		const color = active_color();
		const tab = TAB_BY_ID[_active_tab];
		const subtabs = active_subtabs();
		const subtab_label = subtabs
			? (subtabs.find((st) => st.id === _active_subtab) || {}).label
			: null;
		const title = subtab_label ? `${tab.label} — ${subtab_label}` : tab ? tab.label : "";
		$(content_selector()).html(`
			<div style="border-left:4px solid ${color};padding:6px 0 6px 12px;margin-bottom:12px;">
				<span style="color:${color};font-weight:700;font-size:14px;">${esc(title)} ${__("Summary")}</span>
			</div>
			<div id="dcws-dt" style="overflow-x:auto;"></div>
		`);

		const columns = [
			{
				name: __("Desc Code"),
				id: "desc_code",
				width: 150,
				align: "left",
				editable: false,
				format: (val, _r, _c, d) => (is_footer(d) ? fmt_footer_label(d) : esc(val || "")),
			},
			{
				name: __("HSN Code"),
				id: "hsn_code",
				width: 120,
				align: "left",
				editable: false,
				format: (val, _r, _c, d) => (is_footer(d) ? "" : esc(val || "")),
			},
			...metric_columns(),
		];

		set_export(columns, rows, `${title} ${__("Summary")}`);

		_dt = new DataTable(document.getElementById("dcws-dt"), {
			columns,
			data: rows,
			serialNoColumn: false,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: true,
			noDataMessage: __("No data found."),
			layout: "fixed",
		});
	}

	function render_stock_summary(rows) {
		destroy_dt();

		if (!rows.length) {
			show_empty();
			return;
		}

		const color = active_color();
		const tab = TAB_BY_ID[_active_tab];
		const as_of = to_date_field.get_value() || frappe.datetime.get_today();
		$(content_selector()).html(`
			<div style="border-left:4px solid ${color};padding:6px 0 6px 12px;margin-bottom:12px;">
				<span style="color:${color};font-weight:700;font-size:14px;">${esc(tab ? tab.label : "")} ${__("Summary")}</span>
				<span style="color:#888;font-size:12px;margin-left:8px;">${__("as of")} ${esc(frappe.datetime.str_to_user(as_of))}</span>
			</div>
			<div id="dcws-dt" style="overflow-x:auto;"></div>
		`);

		const columns = [
			{
				name: __("Desc Code"),
				id: "desc_code",
				width: 260,
				align: "left",
				editable: false,
				format: (val, _r, _c, d) => (is_footer(d) ? fmt_footer_label(d) : esc(val || "")),
			},
			{
				name: __("On Hand Stock"),
				id: "on_hand_stock",
				width: 160,
				align: "right",
				editable: false,
				format: (val, _r, _c, d) =>
					is_footer(d) ? fmt_footer_number(val) : fmt_number(val),
			},
			{
				name: __("Valuation"),
				id: "stock_value",
				width: 160,
				align: "right",
				editable: false,
				format: money_fmt,
			},
		];

		set_export(
			columns,
			rows,
			`${tab ? tab.label : "Stock"} ${__("Summary")} (${__("as of")} ${frappe.datetime.str_to_user(as_of)})`
		);

		_dt = new DataTable(document.getElementById("dcws-dt"), {
			columns,
			data: rows,
			serialNoColumn: false,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: true,
			noDataMessage: __("No data found."),
			layout: "fixed",
		});
	}

	const TRANSACTION_TYPE_BY_TAB = {
		hsn_report: "Sale",
		sale: "Sale",
		purchase: "Purchase",
	};

	function load_stock_data() {
		show_loading();
		frappe.call({
			method:
				"prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa.get_stock_summary",
			args: get_filters(),
			callback(r) {
				render_stock_summary(r.message || []);
			},
			error() {
				show_empty();
			},
		});
	}

	function load_data() {
		const transaction_type = TRANSACTION_TYPE_BY_TAB[_active_tab];
		if (transaction_type) {
			show_loading();
		} else if (active_subtabs()) {
			init_subtabs();
			load_subtab_data();
			return;
		} else if (_active_tab === "stock") {
			load_stock_data();
			return;
		} else {
			const tab = TAB_BY_ID[_active_tab];
			show_placeholder(tab ? tab.label : _active_tab);
			return;
		}

		frappe.call({
			method:
				"prakash_steel.prakash_steel.page.desc_code_wise_summa.desc_code_wise_summa.get_summary",
			args: {
				transaction_type,
				exclude_returns: _active_tab === "sale" || _active_tab === "purchase" ? 1 : 0,
				...get_filters(),
			},
			callback(r) {
				render_summary(r.message || []);
			},
			error() {
				show_empty();
			},
		});
	}

	init_tabs();
	_ready = true;
	load_data();
};
