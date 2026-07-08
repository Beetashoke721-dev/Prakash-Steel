
frappe.pages['prakash-steel-planni'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Prakash Steel Planning Dashboard',
		single_column: true,
	});

	// Main container with charts grid
	const $container = $(`
		<div class="planning-dashboard" style="padding: 15px;">
			<div class="charts-grid" style="
				display: grid;
				grid-template-columns: repeat(3, 1fr);
				gap: 16px;
			"></div>
		</div>
	`);

	page.main.empty();
	page.main.append($container);

	const $chartsContainer = $container.find('.charts-grid');

	page.set_indicator(__('Loading chart data...'), 'blue');

	const afterChartReady = () => load_all_charts(page, $chartsContainer);

	// Ensure Chart.js is available
	if (typeof Chart === 'undefined') {
		frappe.require('https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js', afterChartReady);
	} else {
		afterChartReady();
	}
};

function load_all_charts(page, $chartsContainer) {
	const colorMap = getColorMap();

	Promise.all([
		new Promise((resolve, reject) => {
			frappe.call({
				method: 'prakash_steel.prakash_steel.page.prakash_steel_planni.prakash_steel_planni.get_sku_type_on_hand_status',
				callback: resolve,
				error: reject,
			});
		}),
		new Promise((resolve, reject) => {
			frappe.call({
				method: 'prakash_steel.prakash_steel.page.prakash_steel_planni.prakash_steel_planni.get_pending_so_status',
				callback: resolve,
				error: reject,
			});
		}),
		new Promise((resolve, reject) => {
			frappe.call({
				method: 'prakash_steel.prakash_steel.page.prakash_steel_planni.prakash_steel_planni.get_open_po_status',
				callback: resolve,
				error: reject,
			});
		}),
		new Promise((resolve, reject) => {
			frappe.call({
				method: 'prakash_steel.prakash_steel.page.prakash_steel_planni.prakash_steel_planni.get_bright_cs_on_hand_status',
				callback: resolve,
				error: reject,
			});
		}),
		new Promise((resolve, reject) => {
			frappe.call({
				method: 'prakash_steel.prakash_steel.page.prakash_steel_planni.prakash_steel_planni.get_rolled_cs_on_hand_status',
				callback: resolve,
				error: reject,
			});
		}),
	])
		.then(([skuRes, pendingSoRes, openPoRes, brightCsRes, rolledCsRes]) => {
			page.clear_indicator();

			// 1) BBMTA, RBMTA, BOTA, TRMTA pies (exact order)
			if (skuRes && skuRes.message) {
				const skuData = skuRes.message;
				const skuTypes = ['BBMTA', 'RBMTA', 'BOTA', 'TRMTA'];

				skuTypes.forEach((sku) => {
					if (skuData[sku] && skuData[sku].colours && skuData[sku].colours.length) {
						const $card = createChartCard(sku, skuData[sku], colorMap);
						$chartsContainer.append($card);
						renderPieChart(sku, skuData[sku], colorMap);
					}
				});
			}

			// 2) Bright Critical Spares On Hand Status pie
			if (brightCsRes && brightCsRes.message && brightCsRes.message.colours && brightCsRes.message.colours.length) {
				const $card = createChartCard('Bright Critical Spares On Hand Status', brightCsRes.message, colorMap);
				$chartsContainer.append($card);
				renderPieChart('Bright Critical Spares On Hand Status', brightCsRes.message, colorMap);
			}

			// 3) Rolled Critical Spares On Hand Status pie
			if (rolledCsRes && rolledCsRes.message && rolledCsRes.message.colours && rolledCsRes.message.colours.length) {
				const $card = createChartCard('Rolled Critical Spares On Hand Status', rolledCsRes.message, colorMap);
				$chartsContainer.append($card);
				renderPieChart('Rolled Critical Spares On Hand Status', rolledCsRes.message, colorMap);
			}

			// 4) Pending SO Status pie (Open SO)
			if (pendingSoRes && pendingSoRes.message && pendingSoRes.message.colours && pendingSoRes.message.colours.length) {
				const $card = createChartCard('Pending SO Status', pendingSoRes.message, colorMap);
				$chartsContainer.append($card);
				renderPieChart('Pending SO Status', pendingSoRes.message, colorMap);
			}

			// 5) Open PO Status pie
			if (openPoRes && openPoRes.message) {
				const $card = createChartCard('Open PO Status', openPoRes.message, colorMap);
				$chartsContainer.append($card);
				renderPieChart('Open PO Status', openPoRes.message, colorMap);
			}

			if ($chartsContainer.children().length === 0) {
				$chartsContainer.append(`
					<div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: #7f8c8d;">
						<i class="fa fa-info-circle" style="font-size: 2rem; margin-bottom: 12px;"></i>
						<div>${__('No data available')}</div>
					</div>
				`);
			}
		})
		.catch(() => {
			page.clear_indicator();
			$chartsContainer.append(`
				<div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: #e74c3c;">
					<i class="fa fa-exclamation-triangle" style="font-size: 2rem; margin-bottom: 12px;"></i>
					<div>${__('Error loading data')}</div>
				</div>
			`);
		});
}

function getColorMap() {
	return {
		BLACK: '#000000',
		RED: '#ff0000',
		YELLOW: '#ffcc00', // Deeper yellow color
		GREEN: '#32b84a',
		WHITE: '#d3d3d3', // Grayish white for better visibility
	};
}

const CARD_NAVIGATION = {
	BBMTA: () => frappe.set_route('query-report', 'BBMTA'),
	RBMTA: () => frappe.set_route('query-report', 'RBMTA'),
	BOTA: () => frappe.set_route('query-report', 'BOTA'),
	RMTA: () => frappe.set_route('query-report', 'PTA'),
	PTA: () => frappe.set_route('query-report', 'PTA'),
	'Pending SO Status': () => frappe.set_route('open-so-page'),
};

function navigate_from_card(key) {
	const navigate = CARD_NAVIGATION[key];
	if (navigate) {
		navigate();
	}
}

function createChartCard(key, data, colorMap) {
	const title = key.includes('Status') ? key : `${key} On Hand Status`;
	const chartId = key.replace(/\s+/g, '-');

	const isClickable = Boolean(CARD_NAVIGATION[key]);

	const $card = $(`
		<div class="chart-card" style="
			background:#fff;
			border-radius:8px;
			padding:16px 16px 4px;
			box-shadow:0 2px 8px rgba(0,0,0,0.1);
			position:relative;
			${isClickable ? 'cursor:pointer;transition:box-shadow 0.15s ease, transform 0.15s ease;' : ''}
		" ${isClickable ? `title="${__('Click to open report')}"` : ''}>
			<h3 style="
				margin:0 0 8px 0;
				font-size:1rem;
				font-weight:600;
				color:#2c3e50;
				text-align:center;
			">${title}</h3>
			<div style="position:relative;height:180px;margin-bottom:12px;">
				<canvas id="chart-${chartId}" style="max-height:180px;"></canvas>
			</div>
			<div class="chart-legend-${chartId}" style="
				display:flex;
				justify-content:center;
				margin-top:8px;
			">
				<div class="legend-grid" style="
					display:grid;
					grid-template-columns:repeat(3, 90px);
					column-gap:12px;
					row-gap:8px;
				"></div>
			</div>
			<div class="chart-footer-stats" style="
				display:flex;
				justify-content:center;
				align-items:center;
				gap:24px;
				margin-top:6px;
				padding:8px 0 2px;
				border-top:1px solid #eef1f5;
			">
				<div style="text-align:center;min-width:64px;display:flex;flex-direction:column;justify-content:center;">
					<div style="font-size:0.65rem;color:#7f8c8d;font-weight:500;margin-bottom:1px;line-height:1.1;">${__('Availability')}</div>
					<div class="chart-availability-value" style="font-size:0.85rem;color:#0066cc;font-weight:600;line-height:1.1;">—</div>
				</div>
				<div style="width:1px;align-self:stretch;background:#d8dee9;min-height:28px;"></div>
				<div style="text-align:center;min-width:64px;display:flex;flex-direction:column;justify-content:center;">
					<div style="font-size:0.65rem;color:#7f8c8d;font-weight:500;margin-bottom:1px;line-height:1.1;">${__('Total')}</div>
					<div class="chart-total-value" style="font-size:0.85rem;color:#0066cc;font-weight:600;line-height:1.1;">—</div>
				</div>
			</div>
		</div>
	`);

	// Calculate and display total
	const total = data.total_items ?? data.total_orders ?? (data.colours ? data.colours.reduce((sum, c) => sum + c.count, 0) : 0);

	const $legendGrid = $card.find('.legend-grid');

	// Create a map of existing colors from data
	const colorDataMap = {};
	if (data.colours && data.colours.length) {
		data.colours.forEach((c) => {
			colorDataMap[c.name] = c;
		});
	}

	const blackPct = colorDataMap.BLACK?.percentage ?? 0;
	const redPct = colorDataMap.RED?.percentage ?? 0;
	const availability = Math.max(0, 100 - blackPct - redPct);

	$card.find('.chart-availability-value').text(`${availability}%`);
	$card.find('.chart-total-value').text(total);

	const legendColors = ['BLACK', 'RED', 'WHITE', 'YELLOW', 'GREEN'];

	// Helper function to create legend item
	const createLegendItem = (colorName) => {
		const colorData = colorDataMap[colorName] || { name: colorName, count: 0, percentage: 0 };
		const count = colorData.count ?? 0;
		const percentage = colorData.percentage ?? 0;
		return $(`
			<div style="
				display:flex;
				align-items:center;
				gap:5px;
				width:90px;
				min-height:24px;
				box-sizing:border-box;
			">
				<div style="
					width:12px;
					height:12px;
					flex-shrink:0;
					background:${colorMap[colorName] || '#ccc'};
					border-radius:2px;
					border:1px solid #ddd;
				"></div>
				<span style="
					color:#000000;
					font-size:0.75rem;
					font-weight:bold;
					font-variant-numeric:tabular-nums;
					white-space:nowrap;
				">${count} (${percentage}%)</span>
			</div>
		`);
	};

	legendColors.forEach((colorName) => {
		$legendGrid.append(createLegendItem(colorName));
	});

	if (isClickable) {
		$card.on('mouseenter', function () {
			$(this).css({
				'box-shadow': '0 4px 14px rgba(0,0,0,0.15)',
				transform: 'translateY(-2px)',
			});
		});
		$card.on('mouseleave', function () {
			$(this).css({
				'box-shadow': '0 2px 8px rgba(0,0,0,0.1)',
				transform: 'translateY(0)',
			});
		});
		$card.on('click', () => navigate_from_card(key));
	}

	return $card;
}

function renderPieChart(key, data, colorMap) {
	const chartId = key.replace(/\s+/g, '-');
	const canvas = document.getElementById(`chart-${chartId}`);
	if (!canvas || !data || !data.colours) {
		return;
	}

	if (typeof Chart === 'undefined') {
		return;
	}

	const ctx = canvas.getContext('2d');
	const labels = data.colours.map((c) => c.name);
	const values = data.colours.map((c) => c.count);
	const colors = data.colours.map((c) => colorMap[c.name] || '#ccc');

	if (window[`chart_${chartId}`]) {
		window[`chart_${chartId}`].destroy();
	}

	window[`chart_${chartId}`] = new Chart(ctx, {
		type: 'pie',
		data: {
			labels,
			datasets: [
				{
					data: values,
					backgroundColor: colors,
					borderColor: '#fff',
					borderWidth: 2,
				},
			],
		},
		options: {
			responsive: true,
			maintainAspectRatio: true,
			plugins: {
				legend: { display: false },
				tooltip: {
					callbacks: {
						label: (ctx) => {
							const label = ctx.label || '';
							const value = ctx.parsed || 0;
							const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
							// Show rounded percentage (whole number)
							const pct = total ? Math.round((value / total) * 100) : 0;
							return `${label}: ${value} (${pct}%)`;
						},
					},
				},
			},
		},
	});
}
