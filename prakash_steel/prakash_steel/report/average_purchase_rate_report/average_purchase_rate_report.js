// Copyright (c) 2026, Prakash Steel and contributors
// For license information, please see license.txt

function setup_average_rate_box(report) {
	if (report.$average_rate_box) {
		return;
	}

	report.$average_rate_box = $(`
		<div class="average-rate-box" style="
			display: inline-block;
			vertical-align: top;
			background-color: #fff3cd;
			border: 2px solid #ffc107;
			border-radius: 6px;
			padding: 8px 16px;
			text-align: center;
			min-width: 120px;
			margin: 4px 0 4px 16px;
		">
			<div class="average-rate-label" style="
				font-size: 12px;
				font-weight: 600;
				color: #856404;
				margin-bottom: 4px;
			">${__("Average Rate")}</div>
			<div class="average-rate-value" style="
				font-size: 20px;
				font-weight: bold;
				color: #007bff;
			">-</div>
		</div>
	`).appendTo(report.page.page_form);
}

function update_average_rate(report) {
	const rates = (report.data || [])
		.map((row) => flt(row.rate))
		.filter((rate) => !isNaN(rate));

	const average_rate = rates.length
		? (rates.reduce((total, rate) => total + rate, 0) / rates.length).toFixed(2)
		: "-";

	report.$average_rate_box?.find(".average-rate-value").text(average_rate);
}

frappe.query_reports["Average Purchase Rate Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "grade",
			label: __("Grade"),
			fieldtype: "Link",
			options: "Item Grade",
		},
	],

	onload(report) {
		setup_average_rate_box(report);

		const original_refresh = report.refresh.bind(report);
		report.refresh = function (...args) {
			return original_refresh(...args).then(() => update_average_rate(report));
		};
	},
};
