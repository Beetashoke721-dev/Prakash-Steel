// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

// frappe.query_reports["OTIF Report"] = {
// 	filters: [
// 		// {
// 		// 	"fieldname": "my_filter",
// 		// 	"label": __("My Filter"),
// 		// 	"fieldtype": "Data",
// 		// 	"reqd": 1,
// 		// },
// 	],
// };


// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["OTIF Report"] = {
	/* DEBUG (disabled): click a Line/Order Percentage cell to see its calculation.
	onload: function (report) {
		$(report.page.wrapper)
			.off("click.sob-debug")
			.on("click.sob-debug", ".sob-debug", function (e) {
				e.preventDefault();
				show_percentage_debug($(this).data("week"), $(this).data("kind"));
			});
	},
	formatter: function (value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		const fname = column.fieldname || column.id;
		if (["line_percentage", "order_percentage"].includes(fname) && data) {
			const kind = fname === "line_percentage" ? "line" : "order";
			return `<a class="sob-debug" href="#" data-kind="${kind}" data-week="${frappe.utils.escape_html(
				data.week || ""
			)}" title="${__("Click to see how this is calculated")}">${formatted ?? ""}</a>`;
		}
		return formatted;
	},
	*/
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
			reqd: 0,
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
			reqd: 0,
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
					filters["delivery_date"] = ["between", [from_date, to_date]];
				} else if (from_date) {
					filters["delivery_date"] = [">=", from_date];
				} else if (to_date) {
					filters["delivery_date"] = ["<=", to_date];
				}

				return frappe.db.get_link_options("Sales Order", txt, filters);
			},
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
			width: "80",
		},
		{
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
			width: "80",
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
	],
};

/* DEBUG (disabled): dialog behind the percentage cells.
function show_percentage_debug(week, kind) {
	frappe.call({
		method: "prakash_steel.prakash_steel.report.sales_order_booking.sales_order_booking.get_week_breakdown",
		args: { filters: frappe.query_report.get_filter_values(), week: week },
		freeze: true,
		callback: (r) => {
			const d = r.message;
			const otif = kind === "line" ? "line_otif" : "order_otif";
			const num_total = kind === "line" ? d.line_sales_total : d.order_sales_total;
			const pct = kind === "line" ? d.line_percentage : d.order_percentage;
			const money = (v) => format_currency(v || 0);
			const esc = frappe.utils.escape_html;
			const rows = d.rows
				.map((x) => {
					const counted = x[otif] === 100;
					const bg = counted ? "background:var(--green-50, #f0fdf4)" : "";
					const invs = x.invoices.length
						? x.invoices
								.map((i) => {
									const on_time =
										x.delivery_date && i.posting_date <= x.delivery_date;
									return `<tr>
										<td>${esc(i.invoice)}</td>
										<td>${i.posting_date || ""} ${on_time ? "" : `<span class="text-danger">(${__("after delivery date")})</span>`}</td>
										<td class="text-right">${i.qty}</td>
										<td class="text-right">${money(i.rate)}</td>
										<td class="text-right">${money(i.value)}</td>
									</tr>`;
								})
								.join("")
						: `<tr><td colspan="5" class="text-muted">${__("No submitted invoice")}</td></tr>`;
					return `<tr style="${bg}">
						<td>${esc(x.sales_order_number || "")}</td>
						<td>${esc(x.item_code || "")}</td>
						<td>${x.delivery_date || ""}</td>
						<td class="text-right">${x.qty_ordered ?? ""}</td>
						<td class="text-right">${x[otif] ?? ""}</td>
						<td class="text-right">${money(x.book_value)}</td>
						<td style="padding:0">
							<table class="table table-sm mb-0" style="margin:0">
								<thead><tr><th>${__("Invoice")}</th><th>${__("Date")}</th><th>${__("Qty")}</th><th>${__("Rate")}</th><th>${__("Value (Qty x Rate)")}</th></tr></thead>
								<tbody>${invs}</tbody>
							</table>
						</td>
						<td class="text-right">${money(x.sales_value)}</td>
						<td class="text-right">${counted ? money(x.sales_value) : 0}</td>
					</tr>`;
				})
				.join("");

			const dialog = new frappe.ui.Dialog({
				title: __("{0} Percentage - Week {1}", [kind === "line" ? __("Line") : __("Order"), d.week || "-"]),
				size: "extra-large",
				fields: [{ fieldtype: "HTML", fieldname: "body" }],
			});
			dialog.fields_dict.body.$wrapper.html(`
				<p class="text-muted">
					${__("Percentage = sum of Sales Value (invoiced) of lines with {0} = 100, divided by sum of Book Value of ALL lines in this delivery week. Highlighted rows are counted in the numerator.", [kind === "line" ? "Line OTIF" : "Order OTIF"])}
				</p>
				<div style="overflow:auto;max-height:50vh">
				<table class="table table-bordered table-sm">
					<thead><tr>
						<th>${__("Sales Order")}</th><th>${__("Item")}</th><th>${__("Delivery Date")}</th>
						<th>${__("Qty Ordered")}</th>
						<th>${kind === "line" ? "Line OTIF" : "Order OTIF"}</th>
						<th>${__("Book Value (SO Qty x Rate)")}</th><th>${__("Invoices")}</th>
						<th>${__("Sales Value (sum of invoices)")}</th><th>${__("Counted Sales Value")}</th>
					</tr></thead>
					<tbody>${rows}</tbody>
				</table></div>
				<p><b>${__("Numerator (counted sales value)")}:</b> ${money(num_total)}<br>
				<b>${__("Denominator (book value, all lines)")}:</b> ${money(d.book_total)}<br>
				<b>${__("Result")}:</b> ${money(num_total)} / ${money(d.book_total)} = <b>${pct}%</b></p>
			`);
			dialog.show();
		},
	});
}
*/
