frappe.pages["basic-rate"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Basic Rate Structure"),
		single_column: true,
	});

	let _active_tab = "ms_round";
	let _dt = null;

	// tab = custom_grade + custom_shape on Item
	const TABS = [
		{ id: "ms_round", label: __("MS Round"), grade: "MS", shape: "Round", color: "#2e8b57" },
		{ id: "c4_round", label: __("C4 Round"), grade: "C4", shape: "Round", color: "#2563eb" },
		{ id: "ms_flat", label: __("MS Flat"), grade: "MS", shape: "Flat", color: "#d97706" },
		{ id: "c4_flat", label: __("C4 Flat"), grade: "C4", shape: "Flat", color: "#dc2626" },
		{ id: "ms_square", label: __("MS Square"), grade: "MS", shape: "Square", color: "#7c3aed" },
		{ id: "c4_square", label: __("C4 Square"), grade: "C4", shape: "Square", color: "#0891b2" },
		{ id: "c4_hex", label: __("C4 HEX"), grade: "C4", shape: "Hex", color: "#65a30d" },
		{ id: "bright_round", label: __("Bright Round"), grade: "", shape: "Round", color: "#db2777" },
		{ id: "bright_flat", label: __("Bright Flat"), grade: "", shape: "Flat", color: "#ea580c" },
		{ id: "c4_round_bright", label: __("C4 Round Bright"), grade: "C4", shape: "Round", color: "#0d9488" },
	];
	const TAB_BY_ID = Object.fromEntries(TABS.map((t) => [t.id, t]));

	function active_tab() {
		return TAB_BY_ID[_active_tab] || TABS[0];
	}

	function active_color() {
		return active_tab().color;
	}

	page.add_inner_button(__("Refresh"), () => load_data());

	$(`<div id="brs-root" style="padding:16px 4px 40px;"></div>`).appendTo(page.main);

	function esc(v) {
		return frappe.utils.escape_html(String(v ?? ""));
	}

	function tab_style(id) {
		const color = (TAB_BY_ID[id] || {}).color || "#2e8b57";
		const is_active = _active_tab === id;
		return `cursor:pointer;padding:7px 18px;font-size:13px;font-weight:600;
			border-radius:999px;user-select:none;transition:background 0.15s,color 0.15s;
			background:${is_active ? color : `${color}18`};
			color:${is_active ? "#fff" : color};`;
	}

	function init_tabs() {
		$("#brs-root").html(`
			<div id="brs-tab-bar" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px;">
				${TABS.map((t) => `<span class="brs-tab" data-tab="${t.id}" style="${tab_style(t.id)}">${t.label}</span>`).join("")}
			</div>
			<div id="brs-tab-content"></div>
		`);
		$(document)
			.off("click", ".brs-tab")
			.on("click", ".brs-tab", (e) => switch_tab($(e.currentTarget).data("tab")));
	}

	function switch_tab(tab) {
		_active_tab = tab;
		$(".brs-tab").each(function () {
			$(this).attr("style", tab_style($(this).data("tab")));
		});
		load_data();
	}

	function destroy_dt() {
		if (_dt) {
			try {
				_dt.destroy();
			} catch (_) {}
			_dt = null;
		}
	}

	function show_loading() {
		destroy_dt();
		$("#brs-tab-content").html(`
			<div style="padding:32px;text-align:center;color:#888;">
				<div style="display:inline-block;width:24px;height:24px;
					border:3px solid #ddd;border-top-color:${active_color()};border-radius:50%;
					animation:brs-spin 0.8s linear infinite;"></div>
				<span style="margin-left:10px;font-size:14px;">${__("Loading…")}</span>
			</div>
			<style>@keyframes brs-spin { to { transform:rotate(360deg); } }</style>
		`);
	}

	function grade_shape_label(t) {
		return [t.grade, t.shape].filter(Boolean).join(" ");
	}

	function show_empty() {
		destroy_dt();
		const t = active_tab();
		const color = active_color();
		$("#brs-tab-content").html(`
			<div style="padding:48px;text-align:center;color:#888;font-size:14px;
				border:1px dashed ${color}55;border-radius:8px;background:${color}0d;">
				${__("No rate components found for")}
				<strong style="color:${color};">${esc(grade_shape_label(t))}</strong>
				${__("items.")}
			</div>`);
	}

	function fmt_rate(v) {
		if (v === null || v === undefined || v === "") return "—";
		const n = parseFloat(v);
		return isNaN(n) ? "—" : format_number(n);
	}

	function render(res) {
		destroy_dt();

		const rows = (res && res.rows) || [];
		if (!rows.length) {
			show_empty();
			return;
		}

		const t = active_tab();
		const color = active_color();
		const src = res.rate_date
			? `${__("Rate as on")} ${esc(frappe.datetime.str_to_user(res.rate_date))}`
			: __("No Basic Rate Structure found");
		$("#brs-tab-content").html(`
			<div style="border-left:4px solid ${color};padding:6px 0 6px 12px;margin-bottom:12px;">
				<span style="color:${color};font-weight:700;font-size:14px;">${esc(t.label)}</span>
				<span style="color:#888;font-size:12px;margin-left:8px;">
					${t.grade ? `${__("Grade")}: ${esc(t.grade)} · ` : ""}${__("Shape")}: ${esc(t.shape)}
				</span>
				<span style="color:#888;font-size:12px;margin-left:8px;">${src}</span>
			</div>
			<div id="brs-dt" style="overflow-x:auto;"></div>
		`);

		_dt = new DataTable(document.getElementById("brs-dt"), {
			columns: [
				{
					name: __("Rate Component"),
					id: "rate_component",
					width: 320,
					align: "left",
					editable: false,
					format: (val) => esc(val || ""),
				},
				{
					name: __("Rate"),
					id: "rate",
					width: 160,
					align: "right",
					editable: false,
					format: (val) => fmt_rate(val),
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

	function load_data() {
		const t = active_tab();
		show_loading();
		frappe.call({
			method: "prakash_steel.prakash_steel.page.basic_rate.basic_rate.get_rate_components",
			args: { tab: t.id, grade: t.grade, shape: t.shape },
			callback(r) {
				render(r.message || {});
			},
			error() {
				show_empty();
			},
		});
	}

	init_tabs();
	load_data();
};
