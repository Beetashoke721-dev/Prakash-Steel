frappe.pages["average-purchase-rat"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Average Purchase Rate",
		single_column: true,
	});

	const from_date_field = page.add_field({
		fieldname: "from_date",
		label: __("From Date"),
		fieldtype: "Date",
		change() { load_data(); },
	});

	const to_date_field = page.add_field({
		fieldname: "to_date",
		label: __("To Date"),
		fieldtype: "Date",
		change() { load_data(); },
	});

	const item_code_field = page.add_field({
		fieldname: "item_code",
		label: __("Item"),
		fieldtype: "Link",
		options: "Item",
		change() { load_data(); },
	});

	const grade_field = page.add_field({
		fieldname: "grade",
		label: __("Grade"),
		fieldtype: "Link",
		options: "Item Grade",
		change() { load_data(); },
	});

	page.add_inner_button(__("Refresh"), () => load_data());

	$(`<div id="apr-root" style="padding:16px 4px 40px;"></div>`).appendTo(page.main);

	// ── Colour palette for grade badges ───────────────────────────────────────
	const GRADE_COLORS = [
		{ bg: "#1a7a3f", fg: "#fff" },
		{ bg: "#1565c0", fg: "#fff" },
		{ bg: "#6a1b9a", fg: "#fff" },
		{ bg: "#c0152a", fg: "#fff" },
		{ bg: "#d4a000", fg: "#fff" },
		{ bg: "#00695c", fg: "#fff" },
		{ bg: "#e65100", fg: "#fff" },
		{ bg: "#37474f", fg: "#fff" },
	];
	const _grade_color_map = {};
	let _grade_color_idx = 0;

	function grade_color(grade) {
		if (!grade) return { bg: "#e0e0e0", fg: "#555" };
		if (!_grade_color_map[grade]) {
			_grade_color_map[grade] = GRADE_COLORS[_grade_color_idx % GRADE_COLORS.length];
			_grade_color_idx++;
		}
		return _grade_color_map[grade];
	}

	function fmt_num(v, dec = 2) {
		if (v === null || v === undefined) return "—";
		return parseFloat(v).toLocaleString(undefined, {
			minimumFractionDigits: dec,
			maximumFractionDigits: dec,
		});
	}

	function fmt_date(v) {
		if (!v) return "—";
		return frappe.datetime.str_to_user(v) || v;
	}

	function esc(v) { return frappe.utils.escape_html(String(v ?? "")); }

	// ── Tabs ──────────────────────────────────────────────────────────────────
	let _dt = null;
	let _active_tab = "details";

	function render(data) {
		// Per-grade average rate
		const grade_rate_sum = {};
		const grade_rate_count = {};
		data.forEach(r => {
			const key = r.item_grade || "";
			const n = parseFloat(r.rate) || 0;
			grade_rate_sum[key] = (grade_rate_sum[key] || 0) + n;
			grade_rate_count[key] = (grade_rate_count[key] || 0) + 1;
		});
		const grade_avg = {};
		Object.keys(grade_rate_sum).forEach(k => {
			grade_avg[k] = grade_rate_sum[k] / grade_rate_count[k];
		});

		const enriched = data.map(r => ({
			...r,
			_item_avg_rate: grade_avg[r.item_grade || ""] ?? null,
		}));

		render_details(enriched);
	}

	function render_details(enriched) {
		const COLS = [
			{
				name: "PO Date", id: "po_date", width: 110, align: "left", editable: false,
				format: val => `<span style="color:#555;font-size:12px;">${fmt_date(val)}</span>`,
			},
			{
				name: "Supplier", id: "party_name", width: 220, align: "left", editable: false,
				format: (val, _r, _c, d) =>
					val
						? `<span class="apr-supplier-link" data-po="${esc(d.purchase_order_no)}"
							style="color:#1565c0;font-weight:500;cursor:pointer;font-size:12px;">
							${esc(val)}</span>`
						: "—",
			},
			{
				name: "Item Name", id: "item_name", width: 200, align: "left", editable: false,
				format: val => val ? `<span style="font-size:12px;">${esc(val)}</span>` : "—",
			},
			{
				name: "Grade", id: "item_grade", width: 110, align: "center", editable: false,
				format: val => {
					if (!val) return `<span style="color:#ccc;">—</span>`;
					const c = grade_color(val);
					return `<span style="
						display:inline-block;padding:2px 10px;border-radius:4px;
						background:${c.bg};color:${c.fg};font-weight:700;
						font-size:11px;letter-spacing:1px;">
						${esc(val)}</span>`;
				},
			},
			{
				name: "Rate (₹)", id: "rate", width: 110, align: "right", editable: false,
				format: val => {
					const n = parseFloat(val);
					if (isNaN(n)) return "—";
					return `<span style="font-weight:600;font-size:12px;">${fmt_num(n)}</span>`;
				},
			},
			{
				name: "Avg Rate (₹)", id: "_item_avg_rate", width: 130, align: "right", editable: false,
				format: val => {
					const n = parseFloat(val);
					if (isNaN(n)) return "—";
					return `<span style="font-weight:600;font-size:12px;">${fmt_num(n)}</span>`;
				},
			},
			{
				name: "Purchase Order", id: "purchase_order_no", width: 160, align: "left", editable: false,
				format: val =>
					val
						? `<span class="apr-po-link" data-po="${esc(val)}"
							style="color:#1a7a3f;font-weight:600;cursor:pointer;font-size:12px;">
							${esc(val)}</span>`
						: "—",
			},
		];

		if (_dt) { try { _dt.destroy(); } catch (_) {} _dt = null; }

		$("#apr-tab-content").html(`
			<div style="display:flex;justify-content:flex-end;margin-bottom:10px;">
				<button id="apr-details-export-btn" style="
					padding:6px 16px;font-size:12px;font-weight:600;
					border:1px solid #d0d0d0;border-radius:4px;
					background:#fff;color:#333;cursor:pointer;">
					⬇ Export
				</button>
			</div>
			<div id="apr-dt" style="overflow-x:auto;"></div>
		`);

		_dt = new DataTable(document.getElementById("apr-dt"), {
			columns: COLS,
			data: enriched,
			serialNoColumn: false,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: false,
			noDataMessage: __("No purchase orders found."),
			layout: "fixed",
		});

		$(document).off("click", ".apr-po-link").on("click", ".apr-po-link", function () {
			const po = $(this).data("po");
			if (po) window.open(`/app/purchase-order/${encodeURIComponent(po)}`, "_blank");
		});
		$(document).off("click", ".apr-supplier-link").on("click", ".apr-supplier-link", function () {
			const po = $(this).data("po");
			if (po) window.open(`/app/purchase-order/${encodeURIComponent(po)}`, "_blank");
		});

		$("#apr-details-export-btn").on("click", () => {
			const csv = [
				[__("PO Date"), __("Supplier"), __("Item Name"), __("Grade"), __("Rate (₹)"), __("Avg Rate (₹)"), __("Purchase Order")],
				...enriched.map(r => [
					r.po_date ? r.po_date.split("-").reverse().join("-") : "",
					r.party_name || "",
					r.item_name || "",
					r.item_grade || "",
					parseFloat(r.rate || 0).toFixed(2),
					r._item_avg_rate != null ? parseFloat(r._item_avg_rate).toFixed(2) : "",
					r.purchase_order_no || "",
				]),
			].map(row => row.map(v => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");

			const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = "Average Purchase Rate.csv";
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		});
	}

	function render_grade_summary() {
		$("#apr-tab-content").html(`
			<div style="padding:24px;text-align:center;color:#888;">
				<div style="display:inline-block;width:20px;height:20px;
					border:3px solid #ddd;border-top-color:#1a7a3f;border-radius:50%;
					animation:apr-spin 0.8s linear infinite;"></div>
				<span style="margin-left:10px;">Loading…</span>
			</div>
			<style>@keyframes apr-spin { to { transform:rotate(360deg); } }</style>
		`);

		frappe.call({
			method: "prakash_steel.prakash_steel.page.average_purchase_rat.average_purchase_rat.get_grade_wise_avg_rate",
			args: {
				from_date: from_date_field.get_value() || undefined,
				to_date: to_date_field.get_value() || undefined,
			},
			callback(r) {
				const rows_data = r.message || [];
				if (!rows_data.length) {
					$("#apr-tab-content").html(`
						<div style="padding:48px;text-align:center;color:#888;font-size:14px;">
							No grade data found.
						</div>`);
					return;
				}

				const rows = rows_data.map(({ grade, avg_rate }, i) => `
						<tr style="background:${i % 2 === 0 ? "#fff" : "#f9f9f9"};">
							<td style="padding:10px 16px;border-bottom:1px solid #e8e8e8;font-size:13px;color:#333;">
								${esc(grade)}
							</td>
							<td style="padding:10px 16px;border-bottom:1px solid #e8e8e8;text-align:right;font-size:13px;font-weight:600;color:#222;">
								${fmt_num(avg_rate)}
							</td>
						</tr>`).join("");

				$("#apr-tab-content").html(`
					<div style="display:flex;justify-content:flex-end;margin-bottom:10px;">
						<button id="apr-export-btn" style="
							padding:6px 16px;font-size:12px;font-weight:600;
							border:1px solid #d0d0d0;border-radius:4px;
							background:#fff;color:#333;cursor:pointer;">
							⬇ Export
						</button>
					</div>
					<table style="border-collapse:collapse;width:800px;border:1px solid #e0e0e0;border-radius:6px;overflow:hidden;">
						<thead>
							<tr style="background:#f4f5f7;">
								<th style="padding:10px 16px;text-align:left;font-size:12px;color:#555;font-weight:700;border-bottom:2px solid #e0e0e0;">Grade</th>
								<th style="padding:10px 16px;text-align:right;font-size:12px;color:#555;font-weight:700;border-bottom:2px solid #e0e0e0;">Avg Rate (₹)</th>
							</tr>
						</thead>
						<tbody>${rows}</tbody>
					</table>
				`);

				$("#apr-export-btn").on("click", () => {
					const csv = [
						[__("Grade"), __("Avg Rate (₹)")],
						...rows_data.map(r => [r.grade, parseFloat(r.avg_rate).toFixed(2)]),
					].map(row => row.map(v => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");

					const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
					const url = URL.createObjectURL(blob);
					const a = document.createElement("a");
					a.href = url;
					a.download = "Grade Wise Summary.csv";
					document.body.appendChild(a);
					a.click();
					document.body.removeChild(a);
					URL.revokeObjectURL(url);
				});
			},
		});
	}

	// ── Tab shell (rendered once on page load) ────────────────────────────────
	function tab_style(id) {
		return `cursor:pointer;padding:8px 20px;font-size:13px;font-weight:600;
			border-bottom:3px solid ${_active_tab === id ? "#1a7a3f" : "transparent"};
			color:${_active_tab === id ? "#1a7a3f" : "#888"};user-select:none;`;
	}

	function init_tabs() {
		$("#apr-root").html(`
			<div id="apr-tab-bar" style="display:flex;gap:0;border-bottom:1px solid #e0e0e0;margin-bottom:16px;">
				<span id="apr-tab-details" style="${tab_style("details")}">Details</span>
				<span id="apr-tab-grade" style="${tab_style("grade")}">Grade Wise Summary</span>
			</div>
			<div id="apr-tab-content"></div>
		`);
		$(document).off("click", "#apr-tab-details").on("click", "#apr-tab-details", () => switch_tab("details"));
		$(document).off("click", "#apr-tab-grade").on("click", "#apr-tab-grade", () => switch_tab("grade"));
	}

	function switch_tab(tab) {
		_active_tab = tab;
		$("#apr-tab-details").attr("style", tab_style("details"));
		$("#apr-tab-grade").attr("style", tab_style("grade"));
		if (tab === "grade") {
			render_grade_summary();
		} else {
			load_details();
		}
	}

	// ── Details tab (requires item/grade filter) ───────────────────────────────
	function load_details() {
		const item_code = item_code_field.get_value();
		const grade = grade_field.get_value();

		if (!item_code && !grade) {
			$("#apr-tab-content").html(`
				<div style="padding:48px;text-align:center;color:#888;font-size:14px;">
					Please select an <strong>Item</strong> or <strong>Grade</strong> to load details.
				</div>`);
			return;
		}

		$("#apr-tab-content").html(`
			<div style="padding:32px;text-align:center;color:#888;">
				<div style="display:inline-block;width:24px;height:24px;
					border:3px solid #ddd;border-top-color:#1a7a3f;border-radius:50%;
					animation:apr-spin 0.8s linear infinite;"></div>
				<span style="margin-left:10px;font-size:14px;">Loading…</span>
			</div>
			<style>@keyframes apr-spin { to { transform:rotate(360deg); } }</style>
		`);

		frappe.call({
			method: "frappe.desk.query_report.run",
			args: {
				report_name: "Average Purchase Rate Report",
				filters: {
					from_date: from_date_field.get_value() || undefined,
					to_date: to_date_field.get_value() || undefined,
					item_code: item_code || undefined,
					grade: grade || undefined,
				},
			},
			callback(r) {
				const result = r.message;
				if (!result || !result.result || !result.result.length) {
					$("#apr-tab-content").html(`
						<div style="padding:48px;text-align:center;color:#888;font-size:14px;">
							No data found for the selected filters.
						</div>`);
					return;
				}

				const col_names = (result.columns || []).map(c =>
					typeof c === "string" ? c : c.fieldname
				);
				const data = result.result.map(row => {
					if (Array.isArray(row)) {
						const obj = {};
						col_names.forEach((key, i) => { obj[key] = row[i]; });
						return obj;
					}
					return row;
				});

				render(data);
			},
		});
	}

	function load_data() {
		if (_active_tab === "grade") {
			render_grade_summary();
		} else {
			load_details();
		}
	}

	// Init: show tabs immediately, default to Details
	_active_tab = "details";
	init_tabs();
	load_details();
};
