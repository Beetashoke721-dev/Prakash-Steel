// Copyright (c) 2025, beetashoke chakraborty and contributors
// For license information, please see license.txt

// frappe.query_reports["Open SO Analysis"] = {
// 	"filters": [
//
// 	]
// };


// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Open SO Analysis"] = {
	onload: function (report) {
		report.set_filter_value("order_fullkit_status", ["Partial", "Full-kit"]);
	},

	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			width: "80",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_default("company"),
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			width: "80",
			reqd: 1,
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			on_change: (report) => {
				report.set_filter_value("sales_order", []);
				report.refresh();
			},
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			width: "80",
			reqd: 1,
			default: frappe.datetime.get_today(),
			on_change: (report) => {
				report.set_filter_value("sales_order", []);
				report.refresh();
			},
		},
		{
			fieldname: "sales_order",
			label: __("Sales Order"),
			fieldtype: "MultiSelectList",
			width: "80",
			options: "Sales Order",
			get_data: function (txt) {
				let filters = { docstatus: 1 };

				const from_date = frappe.query_report.get_filter_value("from_date");
				const to_date = frappe.query_report.get_filter_value("to_date");
				if (from_date && to_date) {
					filters["transaction_date"] = ["between", [from_date, to_date]];
				}

				return frappe.db.get_link_options("Sales Order", txt, filters);
			},
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "MultiSelectList",
			options: ["To Pay", "To Bill", "To Deliver", "To Deliver and Bill", "Completed", "Closed"],
			width: "80",
			get_data: function (txt) {
				let status = [
					"To Pay",
					"To Bill",
					"To Deliver",
					"To Deliver and Bill",
					"Completed",
					"Closed",
				];
				let options = [];
				for (let option of status) {
					options.push({
						value: option,
						label: __(option),
						description: "",
					});
				}
				return options;
			},
		},
		{
			fieldname: "order_fullkit_status",
			label: __("Order Full Kit Status"),
			fieldtype: "MultiSelectList",
			default: ["Partial", "Full-kit"],
			get_data: function (txt) {
				let statuses = ["Pending", "Partial", "Full-kit"];
				let options = [];
				for (let option of statuses) {
					options.push({
						value: option,
						label: __(option),
						description: "",
					});
				}
				return options;
			},
		},
		{
			fieldname: "group_by_so",
			label: __("Group by Sales Order"),
			fieldtype: "Check",
			default: 0,
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		// Keep old logic: green for delivered_qty / billed_amount
		let format_fields = ["delivered_qty", "billed_amount"];
		if (in_list(format_fields, column.fieldname) && data && data[column.fieldname] > 0) {
			value = "<span style='color:green;'>" + value + "</span>";
		}

		// Keep old logic: red for positive delay
		if (column.fieldname === "delay" && data && data[column.fieldname] > 0) {
			value = "<span style='color:red;'>" + value + "</span>";
		}

		// New: background colors for Order Status (BLACK / RED / YELLOW / GREEN / WHITE)
		if (column.fieldname === "order_status" && data && data.order_status) {
			let statusRaw = data.order_status || "";
			let status = statusRaw.toLowerCase();

			// If empty or unknown, just return default
			if (!status) {
				return value;
			}

			let bg = "";
			let textColor = "#000000";
			let statusText = statusRaw.toUpperCase();

			if (status === "black") {
				bg = "#000000";
				textColor = "#ffffff";
			} else if (status === "white") {
				bg = "#ffffff";
				textColor = "#000000";
			} else if (status === "green") {
				bg = "#4dff88"; // Green
				textColor = "#000000";
			} else if (status === "yellow") {
				bg = "#ffff99"; // Yellow
				textColor = "#000000";
			} else if (status === "red") {
				bg = "#ff9999"; // Red
				textColor = "#000000";
			}

			if (bg) {
				return `<div style="
					background-color:${bg};
					border-radius:0px;
					padding:4px;
					text-align:center;
					font-weight:bold;
					color:${textColor};
				">
					${statusText}
				</div>`;
			}
		}

		// Background colors for Line Fullkit and Order Fullkit
		if ((column.fieldname === "line_fullkit" || column.fieldname === "order_fullkit") && data && data[column.fieldname]) {
			let fullkitRaw = data[column.fieldname] || "";
			let fullkit = fullkitRaw.toLowerCase();

			// If empty or unknown, just return default
			if (!fullkit) {
				return value;
			}

			let bg = "";
			let textColor = "#000000";
			let fullkitText = fullkitRaw;

			if (fullkit === "full-kit") {
				bg = "#4dff88"; // Green
				textColor = "#000000";
			} else if (fullkit === "partial") {
				bg = "#ffff99"; // Yellow
				textColor = "#000000";
			} else if (fullkit === "pending") {
				bg = "#ff9999"; // Red
				textColor = "#000000";
			}

			if (bg) {
				return `<div style="
					background-color:${bg};
					border-radius:0px;
					padding:4px;
					text-align:center;
					font-weight:bold;
					color:${textColor};
				">
					${fullkitText}
				</div>`;
			}
		}

		return value;
	},
};