frappe.pages["late-payment-charges"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Late Payment Charges"),
		single_column: true,
	});

	let _dt = null;
	let _ready = false;

	function esc(v) {
		return frappe.utils.escape_html(String(v ?? ""));
	}

	function fmt_currency(v) {
		if (v === null || v === undefined || v === "") return "";
		const n = parseFloat(v);
		if (isNaN(n)) return "";
		return format_currency(n, frappe.boot.sysdefaults.currency || "INR");
	}

	function fmt_date(v) {
		if (!v) return "";
		return frappe.datetime.str_to_user(v) || v;
	}

	function fmt_num(v) {
		if (v === null || v === undefined || v === "") return "";
		const n = parseFloat(v);
		if (isNaN(n)) return "";
		return n.toLocaleString(undefined, { maximumFractionDigits: 6 });
	}

	const COLUMNS = [
		{
			id: "bill_no",
			name: __("Bill No."),
			width: 150,
			align: "left",
			editable: false,
			format: (val, _r, _c, d) => {
				if (!d) return `<strong>${__("Total")}</strong>`;
				return val
					? `<a href="/app/sales-invoice/${encodeURIComponent(val)}" target="_blank">${esc(val)}</a>`
					: "";
			},
		},
		{
			id: "customer",
			name: __("Customer"),
			width: 180,
			align: "left",
			editable: false,
			format: (val) =>
				val
					? `<a href="/app/customer/${encodeURIComponent(val)}" target="_blank">${esc(val)}</a>`
					: "",
		},
		{
			id: "bill_date",
			name: __("Bill Date"),
			width: 110,
			align: "left",
			editable: false,
			format: (val) => fmt_date(val),
		},
		{
			id: "due_date",
			name: __("Due Date"),
			width: 110,
			align: "left",
			editable: false,
			format: (val) => fmt_date(val),
		},
		{
			id: "grace_period",
			name: __("Grace Period"),
			width: 110,
			align: "right",
			editable: false,
			format: (val) => fmt_num(val),
		},
		{
			id: "deposit_date",
			name: __("Deposit Date"),
			width: 110,
			align: "left",
			editable: false,
			format: (val) => fmt_date(val),
		},
		{
			id: "amount",
			name: __("Amount"),
			width: 130,
			align: "right",
			editable: false,
			format: (val) => fmt_currency(val),
		},
		{
			id: "delay_of_payment",
			name: __("Delay Of Payment"),
			width: 130,
			align: "right",
			editable: false,
			format: (val) => fmt_num(val),
		},
		{
			id: "rate",
			name: __("Rate"),
			width: 90,
			align: "right",
			editable: false,
			format: (val) => fmt_num(val),
		},
		{
			id: "interest",
			name: __("Interest"),
			width: 130,
			align: "right",
			editable: false,
			format: (val) => fmt_currency(val),
		},
		{
			id: "gst",
			name: __("GST"),
			width: 130,
			align: "right",
			editable: false,
			format: (val) => fmt_currency(val),
		},
		{
			id: "total",
			name: __("Total"),
			width: 130,
			align: "right",
			editable: false,
			format: (val) => fmt_currency(val),
		},
		{
			id: "late_payment_issued",
			name: __("Late Payment Issued"),
			width: 160,
			align: "center",
			editable: false,
			format: (val, _r, _c, d) => {
				if (!d) return "";
				const bill_no = d && d.bill_no ? d.bill_no : "";
				return `<input type="checkbox" class="lpc-issued-check" data-bill-no="${esc(
					bill_no
				)}" ${val ? "checked" : ""} style="cursor:pointer;">`;
			},
		},
	];

	const today = frappe.datetime.get_today();
	const default_from = frappe.datetime.month_start(today);

	const from_date_field = page.add_field({
		fieldname: "from_date",
		label: __("From Date"),
		fieldtype: "Date",
		default: default_from,
		reqd: 1,
		change() {
			if (_ready) load_data();
		},
	});

	const to_date_field = page.add_field({
		fieldname: "to_date",
		label: __("To Date"),
		fieldtype: "Date",
		default: today,
		reqd: 1,
		change() {
			if (_ready) load_data();
		},
	});

	const customer_field = page.add_field({
		fieldname: "customer",
		label: __("Customer"),
		fieldtype: "Link",
		options: "Customer",
		change() {
			if (_ready) load_data();
		},
	});

	function render_table(rows) {
		if (_dt) {
			try {
				_dt.destroy();
			} catch (_) {}
			_dt = null;
		}

		if (!rows.length) {
			$("#lpc-table").html(`
				<div style="padding:48px;text-align:center;color:#888;font-size:14px;">
					${__("No data found.")}
				</div>`);
			return;
		}

		_dt = new DataTable(document.getElementById("lpc-table"), {
			columns: COLUMNS,
			data: rows,
			serialNoColumn: true,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: true,
			noDataMessage: __("No data found."),
			layout: "fixed",
			showTotalRow: true,
			hooks: {
				columnTotal(columnValues, cell) {
					const id = cell.column && cell.column.id;
					if (!["interest", "gst", "total"].includes(id)) return "";
					return columnValues.reduce((acc, v) => {
						const n = parseFloat(v);
						return acc + (isNaN(n) ? 0 : n);
					}, 0);
				},
			},
		});
	}

	function get_filters() {
		return {
			from_date: from_date_field.get_value() || undefined,
			to_date: to_date_field.get_value() || undefined,
			customer: customer_field.get_value() || undefined,
		};
	}

	function filters_ready() {
		const f = get_filters();
		return Boolean(f.from_date && f.to_date);
	}

	function show_filter_prompt() {
		$("#lpc-table").html(`
			<div style="padding:48px;text-align:center;color:#888;font-size:14px;">
				${__("Please select")} <strong>${__("From Date")}</strong> ${__("and")} <strong>${__("To Date")}</strong> ${__("to load data.")}
			</div>`);
	}

	function load_data() {
		if (!filters_ready()) {
			show_filter_prompt();
			return;
		}

		frappe.call({
			method: "prakash_steel.prakash_steel.page.late_payment_charges.late_payment_charges.get_data",
			args: get_filters(),
			callback(r) {
				render_table(r.message || []);
			},
			error() {
				render_table([]);
			},
		});
	}

	function save_issued() {
		const invoices = [];
		$("#lpc-table .lpc-issued-check:checked").each(function () {
			const bill_no = $(this).attr("data-bill-no");
			if (bill_no) invoices.push(bill_no);
		});

		if (!invoices.length) {
			frappe.msgprint(__("Please select at least one row to save."));
			return;
		}

		frappe.call({
			method: "prakash_steel.prakash_steel.page.late_payment_charges.late_payment_charges.mark_issued",
			args: { invoices },
			callback() {
				frappe.show_alert({ message: __("Saved"), indicator: "green" });
				load_data();
			},
		});
	}

	page.set_primary_action(__("Save"), () => save_issued());
	page.add_inner_button(__("Refresh"), () => load_data());

	$(`<div style="padding:16px 4px 40px;">
		<div id="lpc-table" style="overflow-x:auto;"></div>
	</div>`).appendTo(page.main);

	_ready = true;
	load_data();
};
