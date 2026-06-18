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
			/* ── Wrapper ──────────────────────────────────────────── */
			.psp-att-wrapper {
				overflow: auto;
				max-height: calc(100vh - 270px);
				border: 1px solid #d0d5dd;
				border-radius: 0 0 8px 8px;
				box-shadow: 0 2px 8px rgba(0,0,0,0.07);
			}
			/* ── Table base ───────────────────────────────────────── */
			.psp-att-table {
				border-collapse: collapse;
				white-space: nowrap;
				font-size: 12px;
				width: max-content;
			}
			.psp-att-table th,
			.psp-att-table td {
				border: 1px solid #e2e8f0;
				padding: 5px 8px;
				text-align: center;
				vertical-align: middle;
			}
			/* ── Sticky header rows ───────────────────────────────── */
			.psp-att-table thead th {
				position: sticky;
				top: 0;
				z-index: 2;
			}
			/* Row 1: light slate */
			.psp-att-table thead tr:first-child th {
				background: #f1f5f9;
				color: #1e293b;
				font-size: 11px;
				font-weight: 700;
				letter-spacing: 0.3px;
				border-color: #cbd5e1;
			}
			/* Row 2: lighter slate */
			.psp-att-table thead tr:nth-child(2) th {
				background: #e9eef5;
				color: #475569;
				font-size: 10px;
				font-weight: 600;
				letter-spacing: 0.2px;
				border-color: #d1d9e3;
			}
			/* ── Sticky employee columns ──────────────────────────── */
			.psp-att-table .sc-1 { position: sticky; left: 0;    min-width: 120px; background: #fff; z-index: 1; }
			.psp-att-table .sc-2 { position: sticky; left: 120px; min-width: 165px; background: #fff; z-index: 1; text-align: left; }
			.psp-att-table .sc-3 { position: sticky; left: 285px; min-width: 100px; background: #fff; z-index: 1;
			                       box-shadow: 3px 0 6px -2px rgba(0,0,0,0.13); }
			.psp-att-table thead tr:first-child .sc-1,
			.psp-att-table thead tr:first-child .sc-2,
			.psp-att-table thead tr:first-child .sc-3 { z-index: 3; background: #f1f5f9; }
			.psp-att-table thead tr:nth-child(2) .sc-1,
			.psp-att-table thead tr:nth-child(2) .sc-2,
			.psp-att-table thead tr:nth-child(2) .sc-3 { z-index: 3; background: #e9eef5; }
			/* ── Row striping & hover ─────────────────────────────── */
			.psp-att-table tbody tr:nth-child(even) td { background: #f7fafc; }
			.psp-att-table tbody tr:nth-child(even) .sc-1,
			.psp-att-table tbody tr:nth-child(even) .sc-2,
			.psp-att-table tbody tr:nth-child(even) .sc-3 { background: #f7fafc; }
			.psp-att-table tbody tr:hover td { background: #f1f5f9 !important; }
			.psp-att-table tbody tr:hover .sc-1,
			.psp-att-table tbody tr:hover .sc-2,
			.psp-att-table tbody tr:hover .sc-3 { background: #f1f5f9 !important; }
			/* ── Date column types ────────────────────────────────── */
			.psp-att-table .date-hdr { font-weight: 700; }
			.psp-att-table .sun { background: rgba(254,226,226,0.55) !important; }
			.psp-att-table thead .sun { background: #c53030 !important; color: #fff !important; border-color: #9b2c2c !important; }
			.psp-att-table .today-col { background: rgba(254,249,195,0.55) !important; }
			.psp-att-table thead .today-col { background: #fef08a !important; color: #713f12 !important; border-color: #fcd34d !important; }
			/* ── Summary columns ──────────────────────────────────── */
			.psp-att-table .sum-hdr { background: #e2e8f0 !important; color: #374151 !important; font-size: 10px; border-color: #cbd5e1 !important; }
			.psp-att-table .sum-p { color: #276749; font-weight: 700; background: #f0fff4 !important; }
			.psp-att-table .sum-a { color: #c53030; font-weight: 700; background: #fff5f5 !important; }
			.psp-att-table .sum-h { color: #1a56db; font-weight: 700; background: #ebf5ff !important; }
			.psp-att-table .date-sep { border-right: 2.5px solid #64748b !important; }
			.psp-att-table .date-hdr-sep { border-left: 2.5px solid #64748b !important; }
				/* ── Status badges ────────────────────────────────────── */
			.psp-badge {
				display: inline-block;
				padding: 2px 7px;
				border-radius: 10px;
				font-size: 10px;
				font-weight: 700;
				letter-spacing: 0.2px;
				line-height: 1.6;
			}
			.psp-badge-P { background: #c6f6d5; color: #22543d; }
			.psp-badge-A { background: #fed7d7; color: #742a2a; }
			.psp-badge-H { background: #feebc8; color: #7b341e; }
				/* ── Loading / empty states ───────────────────────────── */
			.psp-loading {
				display: flex; flex-direction: column; align-items: center;
				justify-content: center; padding: 52px 24px; color: #718096; gap: 14px;
			}
			.psp-spinner {
				width: 36px; height: 36px; border: 3px solid #e2e8f0;
				border-top-color: #94a3b8; border-radius: 50%;
				animation: psp-spin 0.7s linear infinite;
			}
			@keyframes psp-spin { to { transform: rotate(360deg); } }
			.psp-empty { text-align: center; padding: 52px 24px; color: #a0aec0; font-size: 13px; }
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
		this.$wrapper = $('<div class="psp-att-wrapper"><div class="psp-empty">Click <strong>Refresh</strong> to load attendance data.</div></div>').appendTo(this.page.main);
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

		this.$wrapper.html('<div class="psp-loading"><div class="psp-spinner"></div><span>Loading attendance data…</span></div>');

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

	// Return HH:MM from "YYYY-MM-DD HH:MM:SS" or "HH:MM:SS"
	_fmt_time(val) {
		if (!val || val === 'None') return '';
		var parts = String(val).split(' ');
		var time = parts.length > 1 ? parts[1] : parts[0];
		var tp = time.split(':');
		return tp.length >= 2 ? tp[0] + ':' + tp[1] : time;
	}

	render_table() {
		var data = this.data;
		if (!data || !data.employees || !data.employees.length) {
			this.$wrapper.html('<div class="psp-empty">No attendance data found for the selected period.</div>');
			return;
		}

		var dates = data.dates;
		var employees = data.employees;
		var me = this;
		var dow_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
		var today = frappe.datetime.get_today();

		// ── Header row 1: static labels + date spans ──────────────────────
		var h1 = '<tr>';
		h1 += '<th class="sc-1" rowspan="2">Employee ID</th>';
		h1 += '<th class="sc-2" rowspan="2">Employee Name</th>';
		h1 += '<th class="sc-3" rowspan="2">ESSL Biometric ID</th>';
		dates.forEach(function (d) {
			var day_num = d.split('-')[2].replace(/^0/, '');
			var dow = dow_names[new Date(d).getDay()];
			var cls = 'date-hdr';
			if (dow === 'Sun') cls += ' sun';
			if (d === today) cls += ' today-col';
			var today_label = d === today ? ' <span style="font-size:9px;opacity:0.85;">(Today)</span>' : '';
			h1 += `<th colspan="4" class="${cls} date-hdr-sep">${day_num} <span style="font-weight:500;opacity:0.85;">${dow}</span>${today_label}</th>`;
		});
		h1 += '<th colspan="3" class="sum-hdr" style="border-left:2.5px solid #64748b !important;">Summary</th>';
		h1 += '</tr>';

		// ── Header row 2: sub-column labels per date ──────────────────────
		var h2 = '<tr>';
		dates.forEach(function (d) {
			var dow = dow_names[new Date(d).getDay()];
			var cls = '';
			if (dow === 'Sun') cls = ' sun';
			if (d === today) cls += ' today-col';
			['Status', 'In', 'Out', 'Hrs'].forEach(function (lbl) {
				var sep = lbl === 'Hrs' ? ' date-sep' : '';
				h2 += `<th class="${cls}${sep}">${lbl}</th>`;
			});
		});
		h2 += '<th class="sum-hdr">P</th><th class="sum-hdr">A</th><th class="sum-hdr">Hrs</th>';
		h2 += '</tr>';

		// ── Body rows ─────────────────────────────────────────────────────
		var tbody = '';
		employees.forEach(function (emp) {
			var emp_p = 0, emp_a = 0, emp_total_mins = 0;
			tbody += '<tr>';
			tbody += `<td class="sc-1">${frappe.utils.escape_html(emp.employee)}</td>`;
			tbody += `<td class="sc-2">${frappe.utils.escape_html(emp.employee_name)}</td>`;
			tbody += `<td class="sc-3">${frappe.utils.escape_html(emp.essl_id)}</td>`;

			dates.forEach(function (d) {
				var att = emp.attendance[d] || {};
				var status = att.status || '';
				var dow = dow_names[new Date(d).getDay()];
				var td_cls = '';
				if (dow === 'Sun') td_cls += ' sun';
				if (d === today)   td_cls += ' today-col';

				// Per-employee summary counts
				if (status === 'Present')      emp_p++;
				else if (status === 'Absent')  emp_a++;

				// Accumulate work hours
				var wh_fmt = me._fmt_time(att.work_hours);
				if (wh_fmt) {
					var wh_tp = wh_fmt.split(':');
					if (wh_tp.length >= 2) emp_total_mins += parseInt(wh_tp[0]) * 60 + parseInt(wh_tp[1]);
				}

				// Status badge
				var badge = '';
				if (status === 'Present') {
					badge = `<span class="psp-badge psp-badge-P">P</span>`;
				} else if (status === 'Absent') {
					badge = `<span class="psp-badge psp-badge-A">A</span>`;
				} else if (status === 'Half Day') {
					badge = `<span class="psp-badge psp-badge-H">HD</span>`;
				}

				tbody += `<td class="${td_cls}">${badge}</td>`;
				tbody += `<td class="${td_cls}" style="font-size:11px;color:#4a5568;">${me._fmt_time(att.punch_in)}</td>`;
				tbody += `<td class="${td_cls}" style="font-size:11px;color:#4a5568;">${me._fmt_time(att.punch_out)}</td>`;
				tbody += `<td class="${td_cls} date-sep" style="font-size:11px;color:#718096;">${me._fmt_time(att.work_hours)}</td>`;
			});

			var total_h = emp_total_mins ? (Math.floor(emp_total_mins / 60) + 'h ' + String(emp_total_mins % 60).padStart(2, '0') + 'm') : '';
			tbody += `<td class="sum-p">${emp_p || ''}</td>`;
			tbody += `<td class="sum-a">${emp_a || ''}</td>`;
			tbody += `<td class="sum-h">${total_h}</td>`;
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
		var from_date = this.from_date || this.from_date_field.get_value();
		var to_date   = this.to_date   || this.to_date_field.get_value();
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
				var url = URL.createObjectURL(blob);
				var a = document.createElement('a');
				a.href = url;
				a.download = `PSP_Attendance_${from_date}_to_${to_date}.xlsx`;
				document.body.appendChild(a);
				a.click();
				document.body.removeChild(a);
				URL.revokeObjectURL(url);
			},
		});
	}
}
