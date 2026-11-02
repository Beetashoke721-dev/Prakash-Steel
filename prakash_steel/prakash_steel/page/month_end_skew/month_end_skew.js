frappe.pages['month-end-skew'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Month End Skew',
		single_column: true
	});

	// ── styles ────────────────────────────────────────────────────────────────
	let style = document.getElementById("month-end-skew-style");
	if (!style) {
		style = document.createElement("style");
		style.id = "month-end-skew-style";
		document.head.appendChild(style);
	}
	style.textContent = `
		.mes-page-wrap { padding: 0 4px 24px; }

		.mes-tab-bar {
			display: flex; gap: 0; border-bottom: 2px solid #d0d7e8;
			margin-bottom: 16px;
		}
		.mes-tab {
			padding: 10px 24px; font-size: 13px; font-weight: 700;
			cursor: pointer; border-bottom: 3px solid transparent;
			margin-bottom: -2px; color: #666; transition: color .15s, border-color .15s;
			user-select: none;
		}
		.mes-tab:hover { color: #1565c0; }
		.mes-tab.active { color: #1565c0; border-bottom-color: #1565c0; }

		.mes-tab-panel { display: none; }
		.mes-tab-panel.active { display: block; }

		.mes-chart-box {
			border: 1px solid #e0e5ee; border-radius: 6px; padding: 16px;
			margin-bottom: 20px; background: #fff;
		}

		.mes-tables-row {
			display: flex; gap: 20px; flex-wrap: wrap; align-items: flex-start;
		}
		.mes-table-col { flex: 1 1 0; min-width: 320px; }
		.mes-table-title {
			font-size: 13px; font-weight: 700; color: #333; margin-bottom: 8px;
		}
		.mes-table-wrap { overflow-x: auto; border: 1px solid #e0e5ee; border-radius: 6px; }
		.mes-table {
			width: 100%; border-collapse: collapse; font-size: 12px;
		}
		.mes-table th, .mes-table td {
			padding: 6px 10px; border-bottom: 1px solid #eef0f5; text-align: right;
			white-space: nowrap;
		}
		.mes-table th:first-child, .mes-table td:first-child { text-align: left; }
		.mes-table thead th {
			background: linear-gradient(135deg,#dce8f5,#c5d9ee); font-weight: 700;
			color: #000;
		}
		.mes-table tbody tr.mes-summary-row { font-weight: 700; background: #f5f7fb; }
		.mes-table .mes-dash { color: #bbb; }
	`;

	page.add_inner_button(__("Refresh"), () => load_tab(active_tab, true));

	const $wrap = $(`<div class="mes-page-wrap"></div>`).appendTo(page.main);

	const TABS = [
		{ key: "total", label: __("Total") },
		{ key: "bright", label: __("Bright") },
		{ key: "rolling", label: __("Rolling") },
	];

	const $tab_bar = $(`<div class="mes-tab-bar"></div>`).appendTo($wrap);
	TABS.forEach((t, i) => {
		$(`<div class="mes-tab${i === 0 ? " active" : ""}" data-tab="${t.key}">${t.label}</div>`).appendTo($tab_bar);
	});

	const $panels = {};
	TABS.forEach((t, i) => {
		const $panel = $(`<div class="mes-tab-panel${i === 0 ? " active" : ""}" data-panel="${t.key}"></div>`).appendTo($wrap);
		$(`
			<div class="mes-chart-box">
				<div style="position:relative;height:220px;">
					<canvas id="mes-chart-${t.key}"></canvas>
				</div>
			</div>
		`).appendTo($panel);

		const $tables_row = $(`<div class="mes-tables-row"></div>`).appendTo($panel);
		const $skew_col = $(`
			<div class="mes-table-col">
				<div class="mes-table-title">${__("Month End Skew")}</div>
				<div class="mes-table-wrap mes-skew-table"></div>
			</div>
		`).appendTo($tables_row);
		const $pct_col = $(`
			<div class="mes-table-col">
				<div class="mes-table-title">${__("Percentage")}</div>
				<div class="mes-table-wrap mes-pct-table"></div>
			</div>
		`).appendTo($tables_row);

		$panels[t.key] = {
			$panel,
			$skew: $skew_col.find(".mes-skew-table"),
			$pct: $pct_col.find(".mes-pct-table"),
		};
	});

	let active_tab = TABS[0].key;
	const loaded = {};

	function esc(v) { return frappe.utils.escape_html(String(v ?? "")); }

	function fmt_amount(v) {
		if (v === null || v === undefined || v === "") return `<span class="mes-dash">—</span>`;
		const n = parseFloat(v);
		if (!n) return "0";
		return n.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
	}

	function fmt_pct(v) {
		if (v === null || v === undefined || v === "") return `<span class="mes-dash">—</span>`;
		return `${parseFloat(v).toFixed(1)}%`;
	}

	const SUMMARY_LABELS = new Set([__("Total"), __("Avg")]);

	function render_table($el, columns, data, formatter) {
		if (!data || !data.length) {
			$el.html(`<div style="padding:20px;text-align:center;color:#888;">${__("No data found.")}</div>`);
			return;
		}
		const thead = `<thead><tr>${columns.map(c => `<th>${esc(c.label)}</th>`).join("")}</tr></thead>`;
		const rows = data.map(row => {
			const is_summary = SUMMARY_LABELS.has(row.month);
			const cells = columns.map(c => {
				if (c.fieldname === "month") return `<td>${esc(row[c.fieldname])}</td>`;
				return `<td>${formatter(row[c.fieldname])}</td>`;
			}).join("");
			return `<tr${is_summary ? ' class="mes-summary-row"' : ""}>${cells}</tr>`;
		}).join("");
		$el.html(`<table class="mes-table">${thead}<tbody>${rows}</tbody></table>`);
	}

	const _charts = {};

	function render_chart(tab_key, columns, avg_row) {
		const canvas = document.getElementById(`mes-chart-${tab_key}`);
		if (!canvas || typeof Chart === "undefined") return;

		const bucket_cols = columns.filter(c => c.fieldname !== "month");
		const labels = bucket_cols.map(c => c.label);
		const values = bucket_cols.map(c => parseFloat(avg_row ? avg_row[c.fieldname] : 0) || 0);

		if (_charts[tab_key]) { _charts[tab_key].destroy(); _charts[tab_key] = null; }

		_charts[tab_key] = new Chart(canvas.getContext("2d"), {
			type: "line",
			data: {
				labels,
				datasets: [{
					label: __("Avg %"),
					data: values,
					borderColor: "#1565c0",
					backgroundColor: "rgba(21,101,192,0.1)",
					borderWidth: 2,
					tension: 0,
					fill: false,
					pointRadius: 3,
					pointBackgroundColor: "#1565c0",
				}],
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				layout: { padding: { top: 20 } },
				plugins: {
					legend: { display: false },
					title: { display: true, text: __("MonthEnd Skew"), font: { size: 13, weight: "600" } },
					tooltip: {
						callbacks: {
							label: ctx => `${__("Avg")}: ${ctx.parsed.y.toFixed(1)}%`,
						},
					},
					datalabels: {
						display: true,
						align: "top",
						anchor: "end",
						offset: 6,
						color: "#1565c0",
						font: { size: 11, weight: "600" },
						formatter: v => `${parseFloat(v).toFixed(1)}%`,
					},
				},
				scales: {
					y: {
						beginAtZero: true,
						ticks: { callback: v => `${v}%` },
					},
				},
			},
		});
	}

	const TAB_METHODS = {
		total: "prakash_steel.prakash_steel.page.month_end_skew.month_end_skew.get_total_month_end_skew",
		bright: "prakash_steel.prakash_steel.page.month_end_skew.month_end_skew.get_bright_month_end_skew",
		rolling: "prakash_steel.prakash_steel.page.month_end_skew.month_end_skew.get_rolling_month_end_skew",
	};

	function load_tab(tab_key, force) {
		const panel = $panels[tab_key];
		if (loaded[tab_key] && !force) return;

		panel.$skew.html(`<div style="padding:20px;text-align:center;color:#888;">${__("Loading...")}</div>`);
		panel.$pct.html(`<div style="padding:20px;text-align:center;color:#888;">${__("Loading...")}</div>`);

		frappe.call({
			method: TAB_METHODS[tab_key],
			callback(r) {
				if (!r.message) return;
				loaded[tab_key] = true;
				const { skew, percentage } = r.message;
				render_table(panel.$skew, skew.columns, skew.data, fmt_amount);
				render_table(panel.$pct, percentage.columns, percentage.data, fmt_pct);
				const avg_row = percentage.data.find(row => row.month === __("Avg"));
				// Load sequentially, not as a single frappe.require([...]) batch: dynamically
				// created <script> tags execute as soon as each finishes downloading (not in
				// insertion order), and the datalabels plugin reads the global `Chart` at the
				// moment IT executes. Loading both in parallel lets that race go either way
				// depending on cache state, so datalabels can silently fail to attach.
				frappe.require("https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js", () => {
					frappe.require("https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js", () => {
						if (typeof Chart !== "undefined" && typeof ChartDataLabels !== "undefined" && !Chart.registry.plugins.get("datalabels")) {
							Chart.register(ChartDataLabels);
						}
						render_chart(tab_key, percentage.columns, avg_row);
					});
				});
			},
		});
	}

	$tab_bar.on("click", ".mes-tab", function () {
		const tab = $(this).data("tab");
		if (tab === active_tab) return;
		active_tab = tab;
		$tab_bar.find(".mes-tab").removeClass("active");
		$(this).addClass("active");
		$wrap.find(".mes-tab-panel").removeClass("active");
		$wrap.find(`.mes-tab-panel[data-panel="${tab}"]`).addClass("active");
		load_tab(tab);
	});

	load_tab(active_tab);
};
