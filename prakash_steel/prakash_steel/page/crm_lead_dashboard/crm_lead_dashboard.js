// Copyright (c) 2026, Prakash Steel and contributors
// For license information, please see license.txt

if (!frappe.pages['crm-lead-dashboard']) {
	frappe.pages['crm-lead-dashboard'] = {};
}

frappe.pages['crm-lead-dashboard'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('CRM Lead Dashboard'),
		single_column: true,
	});

	const state = {
		page,
		wrapper,
		controls: {},
		_refreshGen: 0,
	};
	wrapper._crmLeadState = state;

	initializeDashboard(state);
};

frappe.pages['crm-lead-dashboard'].on_page_show = function (wrapper) {
	fitPageHeight(wrapper && wrapper._crmLeadState);
};

function initializeDashboard(state) {
	state.page.main.empty();
	state._debouncedRefresh = frappe.utils.debounce(() => refreshDashboard(state), 300);
	injectStyles();
	createFilterBar(state);
	createLayout(state);
	bindEvents(state);
	fitPageHeight(state);
	refreshDashboard(state);
}

// The page shell height varies with navbar/breadcrumb/filter wrapping, so the
// scroll area is sized from its measured position instead of a fixed offset.
function fitPageHeight(state) {
	if (!state || !state.$page || !state.$page.length) {
		return;
	}
	const el = state.$page.get(0);
	if (!el.isConnected) {
		return;
	}
	const top = el.getBoundingClientRect().top;
	const height = Math.max(420, window.innerHeight - top - 12);
	state.$page.css('height', `${height}px`);
}

function injectStyles() {
	const css = `
		.crm-lead-page {
			display: flex; flex-direction: column;
			height: calc(100vh - 130px); min-height: 420px;
			padding: 0 4px 4px;
		}
		.crm-lead-filters {
			display: flex; gap: 10px; align-items: end; flex-wrap: nowrap;
			justify-content: flex-start; background: var(--bg-color, #f8f9fa);
			padding: 10px 14px; border-radius: 8px; margin-bottom: 10px;
			border: 1px solid var(--border-color, #e3e6eb);
			position: sticky; top: 0; z-index: 30; flex-shrink: 0;
			box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
			overflow-x: auto;
		}
		.crm-lead-filters .filter-controls {
			display: flex; gap: 10px; align-items: end; flex-wrap: nowrap;
			flex: 1 1 auto; min-width: 0;
		}
		.crm-lead-filters .filter-wrap {
			flex: 1 1 0; min-width: 120px; max-width: 200px;
		}
		.crm-lead-filters .filter-wrap .frappe-control,
		.crm-lead-filters .filter-wrap .form-group {
			margin-bottom: 0;
		}
		.crm-lead-filters .filter-btns {
			display: flex; gap: 8px; align-items: center; flex-shrink: 0;
			margin-left: auto; align-self: flex-end;
			height: 32px;
		}
		.crm-lead-filters .filter-btns .btn {
			height: 32px; line-height: 1; padding: 0 12px;
			display: inline-flex; align-items: center;
		}
		.crm-lead-dash {
			flex: 1; min-height: 0; display: flex; flex-direction: column;
		}
		.crm-panel {
			background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e3e6eb);
			border-radius: 8px; padding: 10px 12px;
			flex: 1; min-height: 0; display: flex; flex-direction: column;
		}
		.crm-panel h4 {
			margin: 0 0 8px; font-size: 14px; font-weight: 600; color: var(--text-color, #1f272e);
			flex-shrink: 0;
		}
		.crm-table-panel { margin-bottom: 0; }
		.crm-table-scroll {
			flex: 1; min-height: 0; max-height: 100%;
			overflow: auto; position: relative;
			border: 1px solid var(--border-color, #e3e6eb);
			border-radius: 6px;
		}
		.crm-table-scroll table {
			width: 100%; margin: 0;
			table-layout: fixed;
			border-collapse: separate; border-spacing: 0;
		}
		.crm-table-scroll thead th {
			position: sticky; top: 0; z-index: 10;
			background: var(--subtle-fg, #f8f9fa);
			font-size: 12px; text-transform: uppercase; letter-spacing: 0.03em;
			color: var(--text-muted, #6c7680); font-weight: 600; white-space: nowrap;
			border-bottom: 1px solid var(--border-color, #e3e6eb);
			box-shadow: 0 1px 0 var(--border-color, #e3e6eb);
		}
		.crm-table-scroll tbody td { font-size: 13px; vertical-align: middle; background: var(--card-bg, #fff); }
		.crm-col-lead-date { width: 110px; white-space: nowrap; }
		.crm-col-product { width: 28%; white-space: normal; word-break: break-word; }
		.crm-col-assigned { width: 140px; white-space: nowrap; }
		.crm-status-pill {
			display: inline-block; padding: 2px 8px; border-radius: 10px;
			font-size: 11px; font-weight: 500; background: var(--bg-light-gray, #f0f4f7);
			color: var(--text-color, #1f272e);
		}
		.crm-status-pill.converted { background: #e8f8ef; color: #1e7e34; }
		.crm-empty {
			padding: 40px 16px; text-align: center; color: var(--text-muted, #6c7680);
		}
	`;
	const existing = document.getElementById('crm-lead-dashboard-styles');
	if (existing) {
		existing.textContent = css;
	} else {
		$('<style id="crm-lead-dashboard-styles">').text(css).appendTo('head');
	}
}

function createFilterBar(state) {
	const $page = $('<div class="crm-lead-page"></div>');
	$(state.page.main).append($page);
	state.$page = $page;

	const $bar = $(`
		<div class="crm-lead-filters">
			<div class="filter-controls">
				<div class="filter-wrap" data-lead></div>
				<div class="filter-wrap" data-owner></div>
				<div class="filter-wrap" data-status></div>
				<div class="filter-wrap" data-from-date></div>
				<div class="filter-wrap" data-to-date></div>
			</div>
			<div class="filter-btns" data-btns></div>
		</div>
	`);
	$page.append($bar);

	const onChange = () => onFilterChange(state);

	state.controls.lead = frappe.ui.form.make_control({
		parent: $bar.find('[data-lead]').get(0),
		df: {
			fieldtype: 'Link',
			label: __('Lead'),
			fieldname: 'lead',
			options: 'CRM Lead',
			change: onChange,
		},
		render_input: true,
	});
	state.controls.lead_owner = frappe.ui.form.make_control({
		parent: $bar.find('[data-owner]').get(0),
		df: {
			fieldtype: 'Link',
			label: __('Assigned To'),
			fieldname: 'lead_owner',
			options: 'User',
			change: onChange,
		},
		render_input: true,
	});
	state.controls.status = frappe.ui.form.make_control({
		parent: $bar.find('[data-status]').get(0),
		df: {
			fieldtype: 'Link',
			label: __('Status'),
			fieldname: 'status',
			options: 'CRM Lead Status',
			change: onChange,
		},
		render_input: true,
	});
	state.controls.from_date = frappe.ui.form.make_control({
		parent: $bar.find('[data-from-date]').get(0),
		df: {
			fieldtype: 'Date',
			label: __('From Date'),
			fieldname: 'from_date',
			change: onChange,
		},
		render_input: true,
	});
	state.controls.to_date = frappe.ui.form.make_control({
		parent: $bar.find('[data-to-date]').get(0),
		df: {
			fieldtype: 'Date',
			label: __('To Date'),
			fieldname: 'to_date',
			change: onChange,
		},
		render_input: true,
	});

	const $btns = $bar.find('[data-btns]');
	state.controls.refreshBtn = $(
		`<button class="btn btn-primary">${__('Refresh')}</button>`
	);
	state.controls.resetBtn = $(
		`<button class="btn btn-default">${__('Reset')}</button>`
	);
	$btns.append(state.controls.refreshBtn).append(state.controls.resetBtn);
}

function createLayout(state) {
	const $root = $(`
		<div class="crm-lead-dash">
			<div class="crm-panel crm-table-panel">
				<h4>${__('Recent Leads')}</h4>
				<div class="crm-table-scroll" data-table></div>
			</div>
		</div>
	`);
	(state.$page || $(state.page.main)).append($root);
	state.$root = $root;
}

// A Link control can fire change twice for one selection (awesomplete pick plus
// the input's own change), so filter-driven reloads are debounced.
function onFilterChange(state) {
	if (state._suspendFilterEvents) {
		return;
	}
	state._debouncedRefresh();
}

function bindEvents(state) {
	state.controls.refreshBtn.on('click', () => refreshDashboard(state));
	state.controls.resetBtn.on('click', () => {
		state._suspendFilterEvents = true;
		Promise.all([
			state.controls.lead.set_value(''),
			state.controls.lead_owner.set_value(''),
			state.controls.status.set_value(''),
			state.controls.from_date.set_value(''),
			state.controls.to_date.set_value(''),
		]).finally(() => {
			state._suspendFilterEvents = false;
			refreshDashboard(state);
		});
	});

	$(window)
		.off('resize.crmLeadDashboard')
		.on('resize.crmLeadDashboard', frappe.utils.debounce(() => fitPageHeight(state), 150));
}

function getFilters(state) {
	return {
		lead: state.controls.lead.get_value() || null,
		lead_owner: state.controls.lead_owner.get_value() || null,
		status: state.controls.status.get_value() || null,
		from_date: state.controls.from_date.get_value() || null,
		to_date: state.controls.to_date.get_value() || null,
	};
}

function refreshDashboard(state) {
	const gen = ++state._refreshGen;
	state.$root.find('[data-table]').html(
		`<div class="crm-empty">${__('Loading...')}</div>`
	);

	frappe.call({
		method: 'prakash_steel.api.crm_lead_dashboard.get_crm_lead_dashboard_data',
		args: getFilters(state),
		callback(r) {
			if (gen !== state._refreshGen) {
				return;
			}
			const data = r.message || {};
			renderTable(state, data.recent_leads || []);
		},
		error() {
			if (gen !== state._refreshGen) {
				return;
			}
			state.$root.find('[data-table]').html(
				`<div class="crm-empty">${__('Failed to load dashboard data.')}</div>`
			);
		},
	});
}

function renderTable(state, rows) {
	const $table = state.$root.find('[data-table]').empty();

	if (!rows.length) {
		$table.html(`<div class="crm-empty">${__('No leads found for the selected filters.')}</div>`);
		return;
	}

	const currency = frappe.boot.sysdefaults.currency || 'INR';
	let body = '';
	rows.forEach((r) => {
		const pillCls = r.converted ? 'converted' : '';
		const owner = r.assigned_to || r.lead_owner
			? frappe.utils.escape_html(r.assigned_to || r.lead_owner)
			: `<span class="text-muted">${__('Unassigned')}</span>`;
		const leadDate = r.lead_date
			? frappe.utils.escape_html(frappe.datetime.str_to_user(r.lead_date))
			: '—';
		body += `
			<tr>
				<td>
					<a href="/crm/leads/${encodeURIComponent(r.name)}" target="_blank">
						${frappe.utils.escape_html(r.name)}
					</a>
				</td>
				<td>
					<a href="/crm/leads/${encodeURIComponent(r.name)}" target="_blank">
						${frappe.utils.escape_html(r.lead_name || r.name)}
					</a>
				</td>
				<td class="crm-col-lead-date">${leadDate}</td>
				<td>${frappe.utils.escape_html(r.organization || '—')}</td>
				<td class="crm-col-product">${frappe.utils.escape_html(r.product || '—')}</td>
				<td><span class="crm-status-pill ${pillCls}">${frappe.utils.escape_html(r.status || '—')}</span></td>
				<td class="crm-col-assigned" title="${frappe.utils.escape_html(r.assigned_to || r.lead_owner || '')}">${owner}</td>
				<td class="text-right">${format_currency(r.net_total || 0, currency)}</td>
			</tr>`;
	});

	$table.html(`
		<table class="table table-bordered table-hover mb-0">
			<thead>
				<tr>
					<th>${__('ID')}</th>
					<th>${__('Lead')}</th>
					<th class="crm-col-lead-date">${__('Lead Date')}</th>
					<th>${__('Organization')}</th>
					<th class="crm-col-product">${__('Product')}</th>
					<th>${__('Status')}</th>
					<th class="crm-col-assigned">${__('Assigned to')}</th>
					<th class="text-right">${__('Value')}</th>
				</tr>
			</thead>
			<tbody>${body}</tbody>
		</table>
	`);
}
