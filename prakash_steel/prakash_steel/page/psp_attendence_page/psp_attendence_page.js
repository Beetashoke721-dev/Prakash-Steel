frappe.pages['psp-attendence-page'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'PSP Attendance Summary',
		single_column: true,
	});

	new PspAttendancePage(page);
};

class PspAttendancePage {
	constructor(page) {
		this.page = page;
		this.data = null;
		this.from_date = null;
		this.to_date = null;

		this._inject_styles();
		this._setup_fields();
		this._setup_actions();
		this._setup_table_area();
		this.load_data();
	}

	_inject_styles() {
		if ($('#psp-att-styles').length) return;
		$(`<style id="psp-att-styles">
			.psp-att-wrapper {
				overflow: auto;
				max-height: calc(100vh - 220px);
				border: 1px solid #dee2e6;
				border-radius: 4px;
				margin-top: 12px;
			}
			.psp-att-table {
				border-collapse: collapse;
				white-space: nowrap;
				font-size: 12px;
				width: max-content;
			}
			.psp-att-table th,
			.psp-att-table td {
				border: 1px solid #dee2e6;
				padding: 5px 9px;
				text-align: center;
				vertical-align: middle;
			}
			.psp-att-table thead th {
				position: sticky;
				top: 0;
				background: #f1f3f5;
				z-index: 2;
				font-size: 11px;
				font-weight: 600;
			}
			/* sticky employee columns */
			.psp-att-table .sc-1 { position: sticky; left: 0;    min-width: 130px; background: #fff; z-index: 1; }
			.psp-att-table .sc-2 { position: sticky; left: 130px; min-width: 170px; background: #fff; z-index: 1; text-align: left; }
			.psp-att-table .sc-3 { position: sticky; left: 300px; min-width: 110px; background: #fff; z-index: 1; border-right: 2px solid #adb5bd !important; }
			.psp-att-table thead .sc-1,
			.psp-att-table thead .sc-2,
			.psp-att-table thead .sc-3 { background: #f1f3f5; z-index: 3; }
			.psp-att-table tbody tr:hover td { background: #f8f9fa; }
			.psp-att-table tbody tr:hover .sc-1,
			.psp-att-table tbody tr:hover .sc-2,
			.psp-att-table tbody tr:hover .sc-3 { background: #f8f9fa; }
			.psp-att-table .date-hdr { background: #e2e8f0 !important; font-weight: 700; }
			.psp-att-table .sun { background: #fff5f5 !important; }
			.psp-att-present  { color: #2f9e44; font-weight: 600; }
			.psp-att-absent   { color: #e03131; font-weight: 600; }
			.psp-att-halfday  { color: #e67700; font-weight: 600; }
		</style>`).appendTo('head');
	}

	_month_bounds(idx) {
		var year = new Date().getFullYear();
		var month = String(idx + 1).padStart(2, '0');
		var first = `${year}-${month}-01`;
		var last_day = new Date(year, idx + 1, 0).getDate();
		var last = `${year}-${month}-${String(last_day).padStart(2, '0')}`;
		return { first, last };
	}

	_setup_fields() {
		var me = this;
		var month_names = [
			'January','February','March','April','May','June',
			'July','August','September','October','November','December',
		];
		var now = new Date();

		this.month_names = month_names;

		this.month_field = this.page.add_field({
			fieldtype: 'Select',
			fieldname: 'month',
			label: 'Month',
			options: '\n' + month_names.join('\n'),
			default: month_names[now.getMonth()],
			change() { me._on_month_change(); },
		});

		this.from_date_field = this.page.add_field({
			fieldtype: 'Date',
			fieldname: 'from_date',
			label: 'From',
			default: frappe.datetime.month_start(),
			change() { me._validate_date_in_month('from'); },
		});

		this.to_date_field = this.page.add_field({
			fieldtype: 'Date',
			fieldname: 'to_date',
			label: 'To',
			default: frappe.datetime.month_end(),
			change() { me._validate_date_in_month('to'); },
		});

		this.employee_field = this.page.add_field({
			fieldtype: 'Link',
			fieldname: 'employee',
			label: 'Employee (Optional)',
			options: 'Employee',
		});
	}

	_on_month_change() {
		var idx = this.month_names.indexOf(this.month_field.get_value());
		if (idx === -1) return;
		var { first, last } = this._month_bounds(idx);
		this.from_date_field.set_value(first);
		this.to_date_field.set_value(last);
	}

	_validate_date_in_month(which) {
		var idx = this.month_names.indexOf(this.month_field.get_value());
		if (idx === -1) return;
		var { first, last } = this._month_bounds(idx);
		var field = which === 'from' ? this.from_date_field : this.to_date_field;
		var val = field.get_value();
		if (!val) return;

		if (val < first || val > last) {
			frappe.show_alert({
				message: __(`Date must be within ${this.month_names[idx]} (${first} to ${last})`),
				indicator: 'red',
			});
			field.set_value(which === 'from' ? first : last);
		}
	}

	_setup_actions() {
		var me = this;
		var $bar = $('<div style="display:inline-flex; gap:8px; align-items:flex-end; padding-bottom:2px; margin-left:8px;"></div>')
			.appendTo(this.page.page_form);
		$('<button class="btn btn-primary btn-sm">Refresh</button>')
			.appendTo($bar)
			.on('click', () => me.load_data());
		$('<button class="btn btn-success btn-sm">Export to Excel</button>')
			.appendTo($bar)
			.on('click', () => me.export_to_excel());
	}

	_setup_table_area() {
		this.$wrapper = $('<div class="psp-att-wrapper"><div class="text-center text-muted p-4">Click <strong>Refresh</strong> to load data.</div></div>').appendTo(this.page.main);
	}

	load_data() {
		var me = this;
		var from_date = this.from_date_field.get_value();
		var to_date   = this.to_date_field.get_value();
		var employee  = this.employee_field.get_value();

		if (!from_date || !to_date) {
			frappe.msgprint(__('Please select From and To dates.'));
			return;
		}

		this.from_date = from_date;
		this.to_date   = to_date;

		this.$wrapper.html('<div class="text-center p-4"><i class="fa fa-spinner fa-spin fa-2x"></i><br><span class="text-muted mt-2 d-block">Loading attendance data...</span></div>');

		frappe.call({
			method: 'prakash_steel.prakash_steel.page.psp_attendence_page.psp_attendence_page.get_attendance_data',
			args: { from_date, to_date, employee: employee || '' },
			callback(r) {
				if (r.message) {
					me.data = r.message;
					me.render_table();
				}
			},
		});
	}

	// Extract HH:MM:SS from "YYYY-MM-DD HH:MM:SS" or return "HH:MM:SS" as-is
	_fmt_time(val) {
		if (!val || val === 'None') return '';
		var parts = String(val).split(' ');
		return parts.length > 1 ? parts[1] : parts[0];
	}

	render_table() {
		var data = this.data;
		if (!data || !data.employees || !data.employees.length) {
			this.$wrapper.html('<div class="text-center text-muted p-4">No data found for the selected period.</div>');
			return;
		}

		var dates = data.dates;
		var employees = data.employees;
		var me = this;
		var dow_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

		// ── Header row 1: static labels + date spans ──────────────────────────
		var h1 = '<tr>';
		h1 += '<th class="sc-1" rowspan="2">Employee ID</th>';
		h1 += '<th class="sc-2" rowspan="2">Employee Name</th>';
		h1 += '<th class="sc-3" rowspan="2">ESSL Biometric ID</th>';
		dates.forEach(function (d) {
			var day_num = d.split('-')[2].replace(/^0/, '');
			var dow = dow_names[new Date(d).getDay()];
			var sun_cls = dow === 'Sun' ? ' sun' : '';
			h1 += `<th colspan="4" class="date-hdr${sun_cls}">${day_num} <span style="font-weight:400;">${dow}</span></th>`;
		});
		h1 += '</tr>';

		// ── Header row 2: sub-column labels per date ──────────────────────────
		var h2 = '<tr>';
		dates.forEach(function (d) {
			var dow = dow_names[new Date(d).getDay()];
			var sun_cls = dow === 'Sun' ? ' sun' : '';
			['Status', 'In', 'Out', 'Hours'].forEach(function (lbl) {
				h2 += `<th class="${sun_cls}">${lbl}</th>`;
			});
		});
		h2 += '</tr>';

		// ── Body rows ─────────────────────────────────────────────────────────
		var tbody = '';
		employees.forEach(function (emp) {
			tbody += '<tr>';
			tbody += `<td class="sc-1">${frappe.utils.escape_html(emp.employee)}</td>`;
			tbody += `<td class="sc-2">${frappe.utils.escape_html(emp.employee_name)}</td>`;
			tbody += `<td class="sc-3">${frappe.utils.escape_html(emp.essl_id)}</td>`;

			dates.forEach(function (d) {
				var att = emp.attendance[d] || {};
				var status = att.status || '';
				var dow = dow_names[new Date(d).getDay()];
				var sun_cls = dow === 'Sun' ? ' sun' : '';
				var s_cls = '';
				if (status === 'Present')   s_cls = 'psp-att-present';
				else if (status === 'Absent') s_cls = 'psp-att-absent';
				else if (status === 'Half Day') s_cls = 'psp-att-halfday';

				tbody += `<td class="${s_cls}${sun_cls}">${status}</td>`;
				tbody += `<td class="${sun_cls}">${me._fmt_time(att.punch_in)}</td>`;
				tbody += `<td class="${sun_cls}">${me._fmt_time(att.punch_out)}</td>`;
				tbody += `<td class="${sun_cls}">${me._fmt_time(att.work_hours)}</td>`;
			});
			tbody += '</tr>';
		});

		var html = `<table class="psp-att-table">
			<thead>${h1}${h2}</thead>
			<tbody>${tbody}</tbody>
		</table>`;
		this.$wrapper.html(html);
	}

	export_to_excel() {
		var me = this;
		var from_date = this.from_date_field.get_value();
		var to_date   = this.to_date_field.get_value();
		var employee  = this.employee_field.get_value();

		if (!from_date || !to_date) {
			frappe.msgprint(__('Please select From and To dates.'));
			return;
		}

		frappe.show_alert({ message: __('Generating Excel file…'), indicator: 'blue' });

		frappe.call({
			method: 'prakash_steel.prakash_steel.page.psp_attendence_page.psp_attendence_page.download_attendance_excel',
			args: { from_date, to_date, employee: employee || '' },
			callback(r) {
				if (!r.message) return;

				// Decode base64 → Uint8Array → Blob → download
				var binary = atob(r.message);
				var bytes  = new Uint8Array(binary.length);
				for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

				var blob = new Blob([bytes], {
					type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
				});
				var a = document.createElement('a');
				a.href = URL.createObjectURL(blob);
				a.download = `PSP_Attendance_${from_date}_to_${to_date}.xlsx`;
				document.body.appendChild(a);
				a.click();
				document.body.removeChild(a);
			},
		});
	}
}
