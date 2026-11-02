frappe.pages['rolled-product-hbt'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Rolled Product HBT',
		single_column: true
	});

	const view_by_field = page.add_field({
		fieldname: "view_by",
		label: __("View By"),
		fieldtype: "Select",
		options: ["Sale Quantity", "Sale Value", "Throughput"],
		default: "Sale Quantity",
		reqd: 1,
		change() { load_data(); },
	});

	page.add_inner_button(__("Refresh"), () => load_data());

	const $chart_card = $(`
		<div style="
			background:#fff;
			border-radius:8px;
			padding:16px;
			margin:16px auto 0;
			max-width:360px;
			box-shadow:0 2px 8px rgba(0,0,0,0.08);
		">
			<h3 style="margin:0 0 8px 0;font-size:0.95rem;font-weight:600;color:#2c3e50;text-align:center;">${__("HBT Split")}</h3>
			<div style="position:relative;height:200px;">
				<canvas id="rolled-product-hbt-pie"></canvas>
			</div>
		</div>
	`).appendTo(page.main);

	const $root = $(`<div id="rolled-product-hbt-root" style="padding:16px 4px 40px;"></div>`).appendTo(page.main);

	const HBT_COLOURS = { H: "#1a7a3f", B: "#d4a000", T: "#c0152a" };
	let hbt_chart = null;

	function render_hbt_pie(data) {
		const canvas = document.getElementById("rolled-product-hbt-pie");
		if (!canvas || typeof Chart === "undefined") return;

		const counts = { H: 0, B: 0, T: 0 };
		data.forEach((row) => { if (counts[row.hbt] !== undefined) counts[row.hbt]++; });

		if (hbt_chart) { hbt_chart.destroy(); hbt_chart = null; }

		hbt_chart = new Chart(canvas.getContext("2d"), {
			type: "pie",
			data: {
				labels: ["H", "B", "T"],
				datasets: [{
					data: [counts.H, counts.B, counts.T],
					backgroundColor: [HBT_COLOURS.H, HBT_COLOURS.B, HBT_COLOURS.T],
					borderColor: "#fff",
					borderWidth: 2,
				}],
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: {
						position: "bottom",
						labels: {
							font: { weight: "bold", size: 13 },
							generateLabels(chart) {
								const { labels, datasets } = chart.data;
								return labels.map((label, i) => ({
									text: `${label}: ${datasets[0].data[i]}`,
									fillStyle: datasets[0].backgroundColor[i],
									strokeStyle: datasets[0].backgroundColor[i],
									index: i,
								}));
							},
						},
					},
					tooltip: {
						callbacks: {
							label(ctx) {
								const label = ctx.label || "";
								const value = ctx.parsed || 0;
								const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
								const pct = total ? Math.round((value / total) * 100) : 0;
								return `${label}: ${value} (${pct}%)`;
							},
						},
					},
				},
			},
		});
	}

	function esc(v) { return frappe.utils.escape_html(String(v ?? "")); }
	function strip_html(v) { return String(v ?? "").replace(/<[^>]*>/g, ""); }

	function hbt_badge(value) {
		if (!value) return "";
		let bg, textColor;
		if (value === "H") { bg = "#1a7a3f"; textColor = "#ffffff"; }
		else if (value === "B") { bg = "#d4a000"; textColor = "#ffffff"; }
		else if (value === "T") { bg = "#c0152a"; textColor = "#ffffff"; }
		else return esc(value);

		return `<span style="
			background-color:${bg};
			color:${textColor};
			padding: 2px 10px;
			border-radius: 4px;
			font-weight: bold;
			display: inline-block;
		">${esc(value)}</span>`;
	}

	function item_code_link(value) {
		if (!value) return "";
		return `<a href="/app/item/${encodeURIComponent(value)}" target="_blank">${esc(value)}</a>`;
	}

	const HEADER_COLOUR = {
		h: { bg: "#1a7a3f", fg: "#ffffff" },
		b: { bg: "#d4a000", fg: "#ffffff" },
		t: { bg: "#c0152a", fg: "#ffffff" },
	};

	function fmt_value(value, col) {
		if (value === null || value === undefined || value === "") return "";
		if (col.fieldtype === "Percent") {
			return `${parseFloat(value).toFixed(col.precision || 1)}%`;
		}
		if (col.fieldtype === "Currency") {
			return parseFloat(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
		}
		if (col.fieldtype === "Int" || col.fieldtype === "Float") {
			return parseFloat(value).toLocaleString(undefined, { maximumFractionDigits: col.precision || 0 });
		}
		return esc(value);
	}

	let dt = null;
	let cols = [];

	function build_columns(backend_columns) {
		cols = backend_columns.map((col) => {
			let format;
			if (col.fieldname === "hbt") {
				format = (value) => hbt_badge(value);
			} else if (col.fieldname === "item_code") {
				format = (value) => item_code_link(value);
			} else {
				format = (value) => fmt_value(value, col);
			}
			return {
				name: strip_html(col.label),
				id: col.fieldname,
				width: col.width || 120,
				editable: false,
				format,
			};
		});
		return cols;
	}

	function apply_header_colours(root_id) {
		// +1 accounts for the serial-number column DataTable inserts at position 0
		// (serialNoColumn: true), which shifts every real column's DOM index by one.
		cols.forEach((col, idx) => {
			const colour = HEADER_COLOUR[col.id];
			if (!colour) return;
			document.querySelectorAll(`#${root_id} .dt-row-header .dt-cell--col-${idx + 1}`).forEach((cell) => {
				cell.style.backgroundColor = colour.bg;
				cell.querySelectorAll(".dt-cell__content, .content").forEach((el) => {
					el.style.backgroundColor = colour.bg;
					el.style.color = colour.fg;
					el.style.fontWeight = "700";
				});
			});
		});
	}

	function load_data() {
		$root.html(`<div style="padding:24px;text-align:center;color:#888;">${__("Loading...")}</div>`);

		frappe.call({
			method: "prakash_steel.prakash_steel.page.rolled_product_hbt.rolled_product_hbt.get_rolled_product_hbt_data",
			args: { view_by: view_by_field.get_value() || "Sale Quantity" },
			callback(r) {
				if (!r.message) return;
				const { columns } = r.message;
				const data = (r.message.data || []).filter((row) => row.hbt !== "NS");

				render_hbt_pie(data);

				if (dt) { try { dt.destroy(); } catch (e) {} dt = null; }
				$root.empty();

				if (!data || !data.length) {
					$root.html(`<div style="padding:32px;text-align:center;color:#888;">${__("No data found.")}</div>`);
					return;
				}

				const $dt_el = $(`<div id="rolled-product-hbt-dt"></div>`).appendTo($root);
				dt = new frappe.DataTable($dt_el[0], {
					columns: build_columns(columns),
					data,
					layout: "fixed",
					serialNoColumn: true,
					checkboxColumn: false,
					inlineFilters: true,
					noDataMessage: __("No Data"),
				});

				setTimeout(() => apply_header_colours("rolled-product-hbt-dt"), 50);
			},
		});
	}

	if (typeof Chart === "undefined") {
		frappe.require("https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js", () => load_data());
	} else {
		load_data();
	}
};
