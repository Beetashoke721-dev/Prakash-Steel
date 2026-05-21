frappe.pages["po-history-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "PO History Dashboard",
		single_column: true,
	});

	// ── Filters bar ──────────────────────────────────────────────────────────
	const $filters = $(`
		<div class="po-history-filters" style="display:flex;gap:12px;flex-wrap:wrap;padding:12px 0 16px;">
			<div style="display:flex;flex-direction:column;gap:4px;">
				<label style="font-size:11px;color:#8d99a6">From Date</label>
				<input type="date" id="ph-from-date" class="form-control" style="width:150px"
					value="${frappe.datetime.add_days(frappe.datetime.get_today(), -30)}">
			</div>
			<div style="display:flex;flex-direction:column;gap:4px;">
				<label style="font-size:11px;color:#8d99a6">To Date</label>
				<input type="date" id="ph-to-date" class="form-control" style="width:150px"
					value="${frappe.datetime.get_today()}">
			</div>
			<div style="display:flex;flex-direction:column;gap:4px;">
				<label style="font-size:11px;color:#8d99a6">Item Code</label>
				<input type="text" id="ph-item-code" class="form-control" placeholder="All Items" style="width:200px">
			</div>
			<div style="display:flex;flex-direction:column;gap:4px;">
				<label style="font-size:11px;color:#8d99a6">SKU Type</label>
				<select id="ph-sku-type" class="form-control" style="width:130px">
					<option value="">All</option>
					<option>PTA</option><option>PTO</option>
					<option>BOTA</option><option>BOTO</option>
					<option>TRMTA</option><option>TRMTO</option>
					<option>BBMTA</option><option>BBMTO</option>
					<option>RBMTA</option><option>RBMTO</option>
				</select>
			</div>
			<div style="display:flex;align-items:flex-end;">
				<button id="ph-apply" class="btn btn-primary btn-sm">Apply</button>
			</div>
			<div style="display:flex;align-items:flex-end;margin-left:auto;">
				<button id="ph-run-now" class="btn btn-default btn-sm">
					<i class="fa fa-play"></i> Run Snapshot Now
				</button>
			</div>
		</div>
	`).appendTo(page.main);

	// ── Dashboard layout ─────────────────────────────────────────────────────
	const $body = $(`
		<div class="po-history-body">
			<!-- Row 1: summary cards -->
			<div class="row" id="ph-summary-cards" style="margin-bottom:20px;"></div>

			<!-- Row 2: trend chart + colour distribution -->
			<div class="row" style="margin-bottom:20px;">
				<div class="col-md-8">
					<div class="card" style="padding:16px;">
						<h6 class="text-muted" style="margin-bottom:12px;">Average Stock &amp; Order Recommendation Over Time</h6>
						<div id="ph-trend-chart"></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="card" style="padding:16px;">
						<h6 class="text-muted" style="margin-bottom:12px;">On-Hand Colour Distribution (Latest Snapshot)</h6>
						<div id="ph-colour-chart"></div>
					</div>
				</div>
			</div>

			<!-- Row 3: Top 20 items by order recommendation -->
			<div class="card" style="padding:16px;margin-bottom:20px;">
				<h6 class="text-muted" style="margin-bottom:12px;">Top 20 Items by Max Net Order Recommendation</h6>
				<div id="ph-top-items-chart"></div>
			</div>

			<!-- Row 4: Colour heatmap table -->
			<div class="card" style="padding:16px;margin-bottom:20px;">
				<h6 class="text-muted" style="margin-bottom:12px;">On-Hand Colour Heatmap (Item × Date)</h6>
				<div id="ph-heatmap" style="overflow-x:auto;"></div>
			</div>

			<!-- Quick links -->
			<div class="row" style="margin-bottom:20px;">
				<div class="col-md-12">
					<div class="card" style="padding:16px;">
						<h6 class="text-muted" style="margin-bottom:12px;">Quick Links</h6>
						<div style="display:flex;gap:12px;flex-wrap:wrap;">
							<a href="/app/po-recommendation-snapshot" class="btn btn-default btn-sm">All Snapshots</a>
							<a href="/app/query-report/PO%20Recommendation%20Comparison" class="btn btn-default btn-sm">Comparison Report</a>
							<a href="/app/query-report/PO%20Recommendation%20Trend" class="btn btn-default btn-sm">Trend Report</a>
							<a href="/app/query-report/PO%20Recomendation%20for%20PSP?purchase=1&buffer_flag=1" class="btn btn-default btn-sm">Live PO Recommendation</a>
						</div>
					</div>
				</div>
			</div>
		</div>
	`).appendTo(page.main);

	// ── Data loading ─────────────────────────────────────────────────────────
	function load_dashboard() {
		const from_date = $("#ph-from-date").val();
		const to_date = $("#ph-to-date").val();
		const item_code = $("#ph-item-code").val().trim();
		const sku_type = $("#ph-sku-type").val();

		frappe.call({
			method: "prakash_steel.po_recommendation_history.page.po_history_dashboard.po_history_dashboard.get_dashboard_data",
			args: { from_date, to_date, item_code: item_code || null, sku_type: sku_type || null },
			freeze: true,
			freeze_message: "Loading dashboard...",
			callback(r) {
				if (!r.message) return;
				render_dashboard(r.message);
			},
		});
	}

	// ── Renderers ─────────────────────────────────────────────────────────────
	function render_dashboard(data) {
		render_summary_cards(data);
		render_trend_chart(data.trend_data);
		render_colour_pie(data.colour_distribution || {});
		render_top_items_chart(data.top_order_items || []);
		render_heatmap(data.colour_heatmap || [], data.snapshots || []);
	}

	function render_summary_cards(data) {
		const snaps = data.snapshots || [];
		const dist = data.colour_distribution || {};
		const total_red = dist["RED"] || 0;
		const total_green = dist["GREEN"] || 0;
		const top = (data.top_order_items || [])[0];

		const cards = [
			{ label: "Total Snapshots", value: snaps.length, icon: "fa-database", color: "#4e79a7" },
			{ label: "Latest Snapshot", value: snaps.length ? snaps[snaps.length - 1].date : "—", icon: "fa-calendar", color: "#59a14f" },
			{ label: "RED Items (Latest)", value: total_red, icon: "fa-exclamation-triangle", color: "#e15759" },
			{ label: "GREEN Items (Latest)", value: total_green, icon: "fa-check-circle", color: "#27ae60" },
			{ label: "Top Order Item", value: top ? top.item_code : "—", icon: "fa-arrow-up", color: "#f28e2b" },
		];

		const $row = $("#ph-summary-cards").empty();
		cards.forEach((c) => {
			$row.append(`
				<div class="col-md-2" style="margin-bottom:12px;">
					<div class="card" style="padding:16px;border-left:4px solid ${c.color};">
						<div style="font-size:11px;color:#8d99a6;text-transform:uppercase;letter-spacing:.5px;">${c.label}</div>
						<div style="font-size:20px;font-weight:600;margin-top:4px;color:${c.color};">${c.value}</div>
					</div>
				</div>
			`);
		});
	}

	function render_trend_chart(trend) {
		if (!trend || !trend.dates || !trend.dates.length) {
			$("#ph-trend-chart").html('<p class="text-muted text-center">No data</p>');
			return;
		}
		new frappe.Chart("#ph-trend-chart", {
			data: {
				labels: trend.dates,
				datasets: [
					{ name: "Avg Stock", values: trend.avg_stock, chartType: "line" },
					{ name: "Avg Net Order Rec", values: trend.avg_order_rec, chartType: "line" },
					{ name: "Avg Open PO", values: trend.avg_open_po, chartType: "line" },
				],
			},
			type: "axis-mixed",
			height: 250,
			colors: ["#4e79a7", "#e15759", "#f28e2b"],
			lineOptions: { regionFill: 0, dotSize: 3 },
			axisOptions: { xIsSeries: true },
		});
	}

	function render_colour_pie(dist) {
		const colour_hex = { BLACK: "#2c3e50", RED: "#e74c3c", YELLOW: "#f39c12", GREEN: "#27ae60", WHITE: "#bdc3c7" };
		const labels = Object.keys(dist);
		if (!labels.length) {
			$("#ph-colour-chart").html('<p class="text-muted text-center">No data</p>');
			return;
		}
		new frappe.Chart("#ph-colour-chart", {
			data: {
				labels,
				datasets: [{ values: labels.map((l) => dist[l]) }],
			},
			type: "pie",
			height: 220,
			colors: labels.map((l) => colour_hex[l] || "#aaa"),
		});
	}

	function render_top_items_chart(items) {
		if (!items.length) {
			$("#ph-top-items-chart").html('<p class="text-muted text-center">No data</p>');
			return;
		}
		new frappe.Chart("#ph-top-items-chart", {
			data: {
				labels: items.map((i) => i.item_code),
				datasets: [{ name: "Max Net Order Rec", values: items.map((i) => i.max_net_order) }],
			},
			type: "bar",
			height: 260,
			colors: ["#4e79a7"],
		});
	}

	function render_heatmap(heatmap, snapshots) {
		const $el = $("#ph-heatmap").empty();
		if (!heatmap.length) {
			$el.html('<p class="text-muted">No data</p>');
			return;
		}

		const colour_hex = { BLACK: "#2c3e50", RED: "#e74c3c", YELLOW: "#f39c12", GREEN: "#27ae60", WHITE: "#ecf0f1" };
		const all_dates = [...new Set(snapshots.map((s) => s.date))].sort();

		let html = '<table class="table table-bordered table-condensed" style="font-size:11px;">';
		html += "<thead><tr><th>Item</th>" + all_dates.map((d) => `<th style="min-width:80px">${d}</th>`).join("") + "</tr></thead><tbody>";

		heatmap.forEach((row) => {
			html += `<tr><td style="white-space:nowrap;font-weight:500">${row.item_code}</td>`;
			all_dates.forEach((d) => {
				const colour = row.dates[d] || "";
				const bg = colour_hex[colour] || "#fff";
				const fg = colour === "BLACK" ? "#fff" : "#333";
				html += `<td style="background:${bg};color:${fg};text-align:center;">${colour}</td>`;
			});
			html += "</tr>";
		});

		html += "</tbody></table>";
		$el.html(html);
	}

	// ── Events ───────────────────────────────────────────────────────────────
	$("#ph-apply").on("click", load_dashboard);

	$("#ph-run-now").on("click", function () {
		frappe.confirm(
			"This will run a manual PO Recommendation snapshot right now (Purchase + Buffer). Continue?",
			() => {
				frappe.call({
					method: "prakash_steel.po_recommendation_history.doctype.po_recommendation_snapshot.po_recommendation_snapshot.run_manual_snapshot",
					args: { purchase: 1, sell: 0, buffer_flag: 1 },
					freeze: true,
					freeze_message: "Capturing snapshot...",
					callback(r) {
						if (r.message) {
							frappe.show_alert({ message: `Snapshot created: ${r.message}`, indicator: "green" });
							load_dashboard();
						}
					},
				});
			}
		);
	});

	// Initial load
	load_dashboard();
};
