// Copyright (c) 2025, Prakash Steel and contributors
// For license information, please see license.txt

// Ensure the page is registered before adding event handlers
if (!frappe.pages['item-insight-dashboard']) {
	frappe.pages['item-insight-dashboard'] = {};
}

frappe.pages['item-insight-dashboard'].on_page_load = function (wrapper) {

	// Build page shell
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Item Insight Dashboard'),
		single_column: true,
	});

	// Add custom CSS for fixed table, scrollbar, and sticky columns
	$('<style>')
		.prop('type', 'text/css')
		.html(`
			.item-insight-table-wrapper {
				width: 100%;
				max-width: 100%;
				max-height: calc(100vh - 200px);
				overflow: auto;
				position: relative;
			}
			.item-insight-table-wrapper::-webkit-scrollbar {
				width: 12px;
				height: 12px;
			}
			.item-insight-table-wrapper::-webkit-scrollbar-track {
				background: #f1f1f1;
				border-radius: 6px;
			}
			.item-insight-table-wrapper::-webkit-scrollbar-thumb {
				background: #888;
				border-radius: 6px;
			}
			.item-insight-table-wrapper::-webkit-scrollbar-thumb:hover {
				background: #555;
			}
			.item-insight-table {
				position: relative;
				border-collapse: separate;
				border-spacing: 0;
			}
			.item-insight-table thead {
				position: sticky;
				top: 0;
				z-index: 100;
			}
			.item-insight-table thead th {
				position: sticky;
				top: 0;
			}
			/* Row separation - visible border lines only on last row of each item */
			.item-insight-table tbody tr.item-last-row {
				border-bottom: 1px solid #000000 !important;
			}
			.item-insight-table tbody tr.item-last-row td {
				border-bottom: 1px solid #000000 !important;
			}
			/* Alternating background colors - Cream shades */
			.item-insight-table tbody tr.item-bg-blue {
				background-color:rgb(255, 248, 220) !important;
			}
			.item-insight-table tbody tr.item-bg-green {
				background-color:rgb(250, 240, 230) !important;
			}
			.item-insight-table tbody tr.item-bg-blue:hover,
			.item-insight-table tbody tr.item-bg-green:hover {
				opacity: 0.9;
				transition: opacity 0.2s ease;
			}
			/* Export dropdown styling */
			.item-insight-filters .btn-group .btn-default {
				border: 1px solid #000000;
				border-radius: 4px;
				background-color: #ffffff;
				padding: 6px 14px;
				font-weight: 500;
			}
			.item-insight-filters .btn-group .btn-default:hover,
			.item-insight-filters .btn-group.open .btn-default {
				background-color: #f0f0f0;
			}
			.item-insight-filters .btn-group .dropdown-menu {
				min-width: 130px;
				font-size: 12px;
				z-index: 2000;
				right: 0;
				left: auto;
			}
			.item-insight-filters .btn-group .dropdown-menu > li > a {
				padding: 6px 10px;
				display: flex;
				align-items: center;
				gap: 8px;
				border-radius: 6px;
				margin: 2px 6px;
			}
			.item-insight-filters .btn-group .dropdown-menu > li > a:hover {
				background-color: #f5f5f5;
			}
			.item-insight-filters .export-option-icon {
				width: 22px;
				height: 22px;
				border: 1px solid #d1d8dd;
				border-radius: 6px;
				display: inline-flex;
				align-items: center;
				justify-content: center;
				font-size: 11px;
				color: #6c757d;
				background-color: #ffffff;
			}
			.item-insight-filters .export-option-label {
				font-size: 12px;
				color: #343a40;
			}
			/* Ensure link autocomplete dropdowns for Item Grade / Category appear cleanly above the table */
			.item-insight-filters .awesomplete {
				width: 100%;
			}
			.item-insight-filters .awesomplete ul {
				z-index: 2000;
				max-height: 260px;
				overflow-y: auto;
				box-shadow: 0 2px 8px rgba(0,0,0,0.15);
				border-radius: 4px;
			}
		`)
		.appendTo('head');

	// Initialize dashboard state
	const state = {
		page,
		wrapper,
		filters: {},
		controls: {},
		expandedRows: new Set() // Track expanded rows for warehouse stock
	};

	// Initialize dashboard components
	initializeDashboard(state);
};

frappe.pages['item-insight-dashboard'].on_page_show = function () {
};

function initializeDashboard(state) {
	// Clear main content
	state.page.main.empty();

	// Create filter bar
	createFilterBar(state);

	// Set default date range: last 7 days → today
	// (set BEFORE binding event handlers to avoid premature triggers)
	const today = frappe.datetime.get_today();
	const sevenDaysAgo = frappe.datetime.add_days(today, -7);
	state.controls.from_date.set_value(sevenDaysAgo);
	state.controls.to_date.set_value(today);

	// Create table container
	createTableContainer(state);

	// Bind event handlers (date change → auto-refresh)
	bindEventHandlers(state);

	// Fetch data immediately with the default date range
	fetchData(state);
}

function createFilterBar(state) {
	// Main filter container
	const $filterBar = $('<div class="item-insight-filters" style="display:flex;gap:12px;align-items:end;flex-wrap:wrap;margin-bottom:16px;justify-content:space-between;background:#f8f9fa;padding:16px;border-radius:8px;"></div>');

	// Filter controls container
	const $filterControls = $('<div style="display:flex;gap:12px;align-items:end;flex-wrap:nowrap;flex:1 1 auto;"></div>');

	// Individual filter wrappers
	const $fromWrap = $('<div style="min-width:160px;flex:1 1 0;"></div>');
	const $toWrap = $('<div style="min-width:160px;flex:1 1 0;"></div>');
	const $itemWrap = $('<div style="min-width:180px;flex:1 1 0;"></div>');
	const $gradeWrap = $('<div style="min-width:180px;flex:1 1 0;"></div>');
	const $categoryWrap = $('<div style="min-width:200px;flex:1 1 0;"></div>');
	const $descCodeWrap = $('<div style="min-width:200px;flex:1 1 0;"></div>');
	const $btnWrap = $('<div style="display:flex;align-items:end;gap:8px;margin-left:auto;"></div>');

	// Assemble filter controls
	$filterControls
		.append($fromWrap)
		.append($toWrap)
		.append($itemWrap)
		.append($gradeWrap)
		.append($categoryWrap)
		.append($descCodeWrap);
	$filterBar.append($filterControls).append($btnWrap);
	$(state.page.main).append($filterBar);

	// Create filter controls
	createFilterControls(
		state,
		$fromWrap,
		$toWrap,
		$itemWrap,
		$gradeWrap,
		$categoryWrap,
		$descCodeWrap,
		$btnWrap
	);
}

function createFilterControls(
	state,
	$fromWrap,
	$toWrap,
	$itemWrap,
	$gradeWrap,
	$categoryWrap,
	$descCodeWrap,
	$btnWrap
) {
	// Date controls - Not required, can be empty
	state.controls.from_date = frappe.ui.form.make_control({
		parent: $fromWrap.get(0),
		df: {
			fieldtype: 'Date',
			label: __('From Date'),
			fieldname: 'from_date',
			reqd: 0,
		},
		render_input: true,
	});

	state.controls.to_date = frappe.ui.form.make_control({
		parent: $toWrap.get(0),
		df: {
			fieldtype: 'Date',
			label: __('To Date'),
			fieldname: 'to_date',
			reqd: 0,
		},
		render_input: true,
	});

	// Item Code control - Using Data field with custom autocomplete
	state.controls.item_code = frappe.ui.form.make_control({
		parent: $itemWrap.get(0),
		df: {
			fieldtype: 'Data',
			label: __('Item Code'),
			fieldname: 'item_code',
			reqd: 0,
		},
		render_input: true,
	});

	// Setup custom autocomplete for Item Code field (synchronous — control is already rendered)
	setupItemCodeAutocomplete(state.controls.item_code);

	// Item Grade filter (Link to Item Grade)
	state.controls.item_grade = frappe.ui.form.make_control({
		parent: $gradeWrap.get(0),
		df: {
			fieldtype: 'Link',
			label: __('Item Grade'),
			fieldname: 'item_grade',
			options: 'Item Grade',
			reqd: 0,
		},
		render_input: true,
	});

	// Category Name filter (Link to Item Category)
	state.controls.category_name = frappe.ui.form.make_control({
		parent: $categoryWrap.get(0),
		df: {
			fieldtype: 'Link',
			label: __('Category Name'),
			fieldname: 'category_name',
			options: 'Item Category',
			reqd: 0,
			get_query: () => {
				const grade = state.controls.item_grade
					? state.controls.item_grade.get_value()
					: null;
				return {
					query: 'prakash_steel.api.get_item_insight_data.search_item_categories',
					filters: {
						item_grade: grade || '',
					},
				};
			},
		},
		render_input: true,
	});

	// Description Code filter (Select based on Item.custom_desc_code)
	state.controls.description_code = frappe.ui.form.make_control({
		parent: $descCodeWrap.get(0),
		df: {
			fieldtype: 'Select',
			label: __('Description Code'),
			fieldname: 'description_code',
			reqd: 0,
			options: [
				'',
				'Alloy Steel Bright Bar',
				'Non Alloy Steel Bright Bar',
				'Alloy Steel Bars and Rods',
				'Non Alloy Steel Bars and Rods',
				'Steel Ingot and Billets',
				'Alloy Steel Ingot and Billets',
				'Melting / Scrap',
			].join('\n'),
		},
		render_input: true,
	});

	// Refresh button
	const $refreshBtn = $('<button class="btn btn-primary">' + __('Refresh') + '</button>');
	$btnWrap.append($refreshBtn);
	state.controls.refreshBtn = $refreshBtn;

	// Export dropdown (single button with Excel / PDF options)
	const $exportGroup = $(`
		<div class="btn-group">
			<button class="btn btn-default dropdown-toggle" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
				<i class="fa fa-download" style="margin-right:4px;"></i>${__('Export')} <span class="caret"></span>
			</button>
			<ul class="dropdown-menu dropdown-menu-right">
				<li>
					<a href="javascript:void(0)" class="export-excel-option">
						<span class="export-option-icon"><i class="fa fa-file-o"></i></span>
						<span class="export-option-label">${__('Excel')}</span>
					</a>
				</li>
				<li>
					<a href="javascript:void(0)" class="export-pdf-option">
						<span class="export-option-icon"><i class="fa fa-file-o"></i></span>
						<span class="export-option-label">${__('PDF')}</span>
					</a>
				</li>
			</ul>
		</div>
	`);
	$btnWrap.append($exportGroup);
	state.controls.exportExcelBtn = $exportGroup.find('.export-excel-option');
	state.controls.exportPdfBtn = $exportGroup.find('.export-pdf-option');

	// Apply black outline borders to filter fields (synchronous — inputs exist)
	$(state.controls.from_date.$input).css({
		'border': '1px solid #000000',
		'border-radius': '4px',
		'padding': '8px 12px',
		'height': '36px',
		'line-height': '1.4'
	});
	$(state.controls.to_date.$input).css({
		'border': '1px solid #000000',
		'border-radius': '4px',
		'padding': '8px 12px',
		'height': '36px',
		'line-height': '1.4'
	});
	$(state.controls.item_code.$input).css({
		'border': '1px solid #000000',
		'border-radius': '4px',
		'padding': '8px 12px',
		'height': '36px',
		'line-height': '1.4'
	});

	// Description Code (Select)
	if (state.controls.description_code && state.controls.description_code.$input) {
		$(state.controls.description_code.$input).css({
			'border': '1px solid #000000',
			'border-radius': '4px',
			'padding': '8px 12px',
			'height': '36px',
			'line-height': '1.4'
		});
	}

	// For Link fields, style the wrapper instead of the inner input
	const $gradeWrapper = $(state.controls.item_grade.$input).closest('.control-input');
	$gradeWrapper.css({
		'border': '1px solid #000000',
		'border-radius': '4px',
		'padding': '0'
	});
	$(state.controls.item_grade.$input).css({
		'border': 'none',
		'box-shadow': 'none',
		'height': '36px',
		'line-height': '1.4'
	});

	const $categoryWrapper = $(state.controls.category_name.$input).closest('.control-input');
	$categoryWrapper.css({
		'border': '1px solid #000000',
		'border-radius': '4px',
		'padding': '0'
	});
	$(state.controls.category_name.$input).css({
		'border': 'none',
		'box-shadow': 'none',
		'height': '36px',
		'line-height': '1.4'
	});
}

function setupItemCodeAutocomplete(control) {
	const $input = $(control.$input);
	let searchTimeout = null;
	
	// Add custom CSS for the dropdown
	if (!$('#item-code-autocomplete-style').length) {
		$('<style id="item-code-autocomplete-style">')
			.prop('type', 'text/css')
			.html(`
				.item-code-autocomplete {
					position: relative;
					display: inline-block;
					width: 100%;
				}
				.item-code-clear {
					position: absolute;
					right: 8px;
					top: 50%;
					transform: translateY(-50%);
					cursor: pointer;
					font-size: 20px;
					color: #888;
					font-weight: 600;
					line-height: 1;
					padding: 2px 6px;
					z-index: 10;
					user-select: none;
					transition: color 0.2s;
				}
				.item-code-clear:hover {
					color: #000;
				}
				.item-code-autocomplete input {
					padding-right: 30px !important;
				}
				.item-code-autocomplete ul {
					position: absolute;
					top: 100%;
					left: 0;
					right: 0;
					background: white;
					border: 1px solid #d1d8dd;
					border-radius: 4px;
					box-shadow: 0 2px 8px rgba(0,0,0,0.15);
					max-height: 300px;
					overflow-y: auto;
					z-index: 1000;
					margin-top: 2px;
					padding: 4px 0;
					list-style: none;
				}
				.item-code-autocomplete ul li {
					padding: 8px 12px;
					cursor: pointer;
					line-height: 1.6;
					border-bottom: 1px solid #f0f0f0;
				}
				.item-code-autocomplete ul li:last-child {
					border-bottom: none;
				}
				.item-code-autocomplete ul li:hover,
				.item-code-autocomplete ul li.selected {
					background-color: #f0f0f0;
				}
				.item-code-autocomplete ul li strong {
					display: block;
					margin-bottom: 2px;
					font-weight: 600;
					color: #000;
				}
				.item-code-autocomplete ul li span {
					display: block;
					color: #666;
					font-size: 0.9em;
				}
			`)
			.appendTo('head');
	}
	
	// Wrap input in autocomplete container
	if (!$input.parent().hasClass('item-code-autocomplete')) {
		$input.wrap('<div class="item-code-autocomplete"></div>');
	}
	
	const $container = $input.parent();
	
	// Add clear button
	const $clearBtn = $('<span class="item-code-clear" style="display:none;" title="Clear">&times;</span>').appendTo($container);
	
	const $dropdown = $('<ul style="display:none;"></ul>').appendTo($container);
	
	// Toggle clear button visibility based on input value
	function updateClearButton() {
		if ($input.val()) {
			$clearBtn.show();
		} else {
			$clearBtn.hide();
		}
	}
	
	// Clear button click handler
	$clearBtn.on('click', function(e) {
		e.stopPropagation();
		$input.val('');
		if (control.set_value) {
			control.set_value('');
		}
		$dropdown.hide();
		updateClearButton();
		$input.trigger('change');
	});
	
	// Update clear button on input change
	$input.on('input change', updateClearButton);
	
	// Initial update
	updateClearButton();
	
	// Search function
	function searchItems(query, immediate = false) {
		// Clear previous timeout
		clearTimeout(searchTimeout);
		
		// If no query, show all items (limited)
		if (!query || query.length < 1) {
			query = '';
		}
		
		const searchFn = () => {
			frappe.call({
				method: 'prakash_steel.api.get_item_insight_data.search_items',
				args: {
					query: query,
					limit: 20
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						renderDropdown(r.message, query);
					} else {
						$dropdown.hide().empty();
					}
				},
				error: function(err) {
					console.error('Error fetching items:', err);
					$dropdown.hide().empty();
				}
			});
		};
		
		// If immediate (on focus/click), don't debounce
		if (immediate) {
			searchFn();
		} else {
			// Debounce search for typing
			searchTimeout = setTimeout(searchFn, 300);
		}
	}
	
	// Render dropdown items
	function renderDropdown(items, query) {
		if (!items || items.length === 0) {
			$dropdown.hide().empty();
			return;
		}
		
		$dropdown.empty();
		
		items.forEach((item, index) => {
			const itemCode = item.name || '';
			const itemName = item.item_name || itemCode;
			const itemGroup = item.item_group || '';
			const description = itemGroup ? `${itemCode}, ${itemGroup}` : itemCode;
			
			const $li = $(`
				<li data-value="${frappe.utils.escape_html(itemCode)}" data-index="${index}">
					<strong>${frappe.utils.escape_html(itemName)}</strong>
					<span>${frappe.utils.escape_html(description)}</span>
				</li>
			`);
			
			$li.on('click', function() {
				const selectedValue = $(this).attr('data-value');
				$input.val(selectedValue);
				if (control.set_value) {
					control.set_value(selectedValue);
				}
				$dropdown.hide();
				updateClearButton();
				$input.trigger('change');
			});
			
			$li.on('mouseenter', function() {
				$dropdown.find('li').removeClass('selected');
				$(this).addClass('selected');
			});
			
			$dropdown.append($li);
		});
		
		$dropdown.show();
	}
	
	// Event handlers
	$input.on('input', function() {
		const query = $(this).val();
		searchItems(query, false);
	});
	
	$input.on('focus click', function() {
		const query = $(this).val();
		// Show dropdown immediately on focus/click
		searchItems(query, true);
	});
	
	$input.on('blur', function() {
		// Delay hiding to allow click events
		setTimeout(() => {
			$dropdown.hide();
		}, 200);
	});
	
	// Keyboard navigation
	$input.on('keydown', function(e) {
		const $items = $dropdown.find('li');
		const $selected = $dropdown.find('li.selected');
		
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			if ($selected.length) {
				const next = $selected.next();
				if (next.length) {
					$selected.removeClass('selected');
					next.addClass('selected');
					next[0].scrollIntoView({ block: 'nearest' });
				}
			} else if ($items.length) {
				$items.first().addClass('selected');
			}
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			if ($selected.length) {
				const prev = $selected.prev();
				if (prev.length) {
					$selected.removeClass('selected');
					prev.addClass('selected');
					prev[0].scrollIntoView({ block: 'nearest' });
				}
			}
		} else if (e.key === 'Enter') {
			e.preventDefault();
			if ($selected.length) {
				const selectedValue = $selected.attr('data-value');
				$input.val(selectedValue);
				if (control.set_value) {
					control.set_value(selectedValue);
				}
				$dropdown.hide();
				updateClearButton();
				$input.trigger('change');
			}
		} else if (e.key === 'Escape') {
			$dropdown.hide();
		}
	});
	
	// Hide dropdown when clicking outside
	$(document).on('click', function(e) {
		if (!$container.is(e.target) && $container.has(e.target).length === 0) {
			$dropdown.hide();
		}
	});
}

function createTableContainer(state) {
	const $tableContainer = $('<div class="item-insight-table-container" style="margin-top:20px;"></div>');
	$(state.page.main).append($tableContainer);
	state.$tableContainer = $tableContainer;
}

function fetchData(state) {
	// Single unified data-fetch function used for both initial load and filter changes.
	// Uses a monotonic request counter so stale (slow) responses never overwrite fresh ones.
	state._requestId = (state._requestId || 0) + 1;
	const thisRequest = state._requestId;

	const filters = getFilters(state);

	frappe.call({
		method: 'prakash_steel.api.get_item_insight_data.get_item_insight_data',
		args: {
			from_date: filters.from_date || null,
			to_date: filters.to_date || null,
			item_code: filters.item_code || null,
			item_grade: filters.item_grade || null,
			category_name: filters.category_name || null,
			description_code: filters.description_code || null,
		},
		freeze: false,
		async: true,
		callback: function(r) {
			// Ignore if a newer request has already been fired
			if (thisRequest !== state._requestId) return;

			// Clear old content before rendering
			state.$tableContainer.empty();

			if (r && r.message && r.message.length > 0) {
				renderTable(state, r.message);
			} else {
				showNoData(state);
			}
		},
		error: function(error) {
			if (thisRequest !== state._requestId) return;
			console.error('Data fetch error:', error);
			showError(state, __('Failed to load data'));
		}
	});
}

function bindEventHandlers(state) {
	// Immediate refresh — no debounce. Race conditions are handled by
	// the request-counter inside fetchData().
	function immediateRefresh() {
		fetchData(state);
	}

	// Filter change events - Date fields
	$(state.controls.from_date.$input).on('change', immediateRefresh);
	$(state.controls.to_date.$input).on('change', immediateRefresh);

	// Item Code field
	$(state.controls.item_code.$input).on('change', immediateRefresh);

	// Item Grade
	if (state.controls.item_grade && state.controls.item_grade.$input) {
		const $gradeInput = $(state.controls.item_grade.$input);
		$gradeInput.on('change', function () {
			if (state.controls.category_name) {
				state.controls.category_name.set_value('');
			}
			immediateRefresh();
		});
		$gradeInput.on('awesomplete-selectcomplete', function () {
			if (state.controls.category_name) {
				state.controls.category_name.set_value('');
			}
			immediateRefresh();
		});
	}

	// Category Name
	if (state.controls.category_name && state.controls.category_name.$input) {
		const $categoryInput = $(state.controls.category_name.$input);
		$categoryInput.on('change', immediateRefresh);
		$categoryInput.on('awesomplete-selectcomplete', immediateRefresh);
	}

	// Description Code
	if (state.controls.description_code && state.controls.description_code.$input) {
		$(state.controls.description_code.$input).on('change', immediateRefresh);
	}

	// Refresh button
	state.controls.refreshBtn.on('click', immediateRefresh);

	// Export buttons
	if (state.controls.exportExcelBtn) {
		state.controls.exportExcelBtn.on('click', () => exportTable(state, 'excel'));
	}
	if (state.controls.exportPdfBtn) {
		state.controls.exportPdfBtn.on('click', () => exportTable(state, 'pdf'));
	}
}

function exportTable(state, format) {
	const filters = getFilters(state);

	const payload = {
		from_date: filters.from_date || null,
		to_date: filters.to_date || null,
		item_code: filters.item_code || null,
		item_grade: filters.item_grade || null,
		category_name: filters.category_name || null,
		description_code: filters.description_code || null,
	};

	const method =
		format === 'excel'
			? 'prakash_steel.api.get_item_insight_data.export_item_insight_excel'
			: 'prakash_steel.api.get_item_insight_data.export_item_insight_pdf';

	frappe.call({
		method,
		args: {
			filters: JSON.stringify(payload),
		},
		callback: function (r) {
			if (r && r.message && r.message.file_url) {
				window.open(r.message.file_url);
			} else {
				frappe.msgprint(__('No file generated to download'));
			}
		},
		error: function (err) {
			console.error('Export error:', err);
			frappe.msgprint(__('Failed to export data'));
		},
	});
}

function showNoData(state) {
	state.$tableContainer.empty();
	state.$tableContainer.append(`
		<div class="no-data-message" style="text-align:center;color:#7f8c8d;padding:40px;">
			<i class="fa fa-inbox" style="font-size:3rem;margin-bottom:16px;color:#bdc3c7;"></i>
			<div style="font-size:1.1rem;">${__('No data found for the selected criteria')}</div>
		</div>
	`);
}

function getFilters(state) {
	return {
		from_date: state.controls.from_date.get_value(),
		to_date: state.controls.to_date.get_value(),
		item_code: state.controls.item_code.get_value(),
		item_grade: state.controls.item_grade ? state.controls.item_grade.get_value() : null,
		category_name: state.controls.category_name ? state.controls.category_name.get_value() : null,
		description_code: state.controls.description_code ? state.controls.description_code.get_value() : null,
	};
}

function renderTable(state, data) {
	state.$tableContainer.empty();

	if (!data || data.length === 0) {
		state.$tableContainer.append(`
			<div class="no-data-message" style="text-align:center;color:#7f8c8d;padding:24px;">
				<i class="fa fa-info-circle" style="font-size:2rem;margin-bottom:12px;"></i>
				<div>${__('No data available for selected criteria')}</div>
			</div>
		`);
		return;
	}

	// ── Helpers for fast inline formatting (avoid frappe.format per-cell) ──
	const esc = frappe.utils.escape_html;
	function fmtDate(v) {
		if (!v) return '-';
		// v is "YYYY-MM-DD"; convert to user format cheaply
		return frappe.format(v, {fieldtype: 'Date'});
	}
	function fmtFloat(v) {
		const n = parseFloat(v);
		if (isNaN(n)) {
			return '0';
		}
		// Show only integer quantity (e.g. 8.89 → "8")
		return Math.floor(n).toString();
	}
	function fmtCurrency(v) {
		const n = parseFloat(v) || 0;
		return n.toFixed(2);
	}

	// ── Build entire table HTML as one string (single DOM insertion) ──
	const htmlParts = [];

	// Table wrapper + thead (static — computed once)
	htmlParts.push(
		'<div class="item-insight-table-wrapper" style="background:white;border-radius:8px;border:1px solid #000000;">',
		'<table class="item-insight-table" style="width:100%;border-collapse:separate;border-spacing:0;min-width:1830px;table-layout:fixed;">',
		'<thead>',
		'<tr>',
		'<th colspan="2" style="background:#d2b48c;padding:12px;text-align:center;font-weight:600;color:#000000;border-right:2px solid #000000;border-bottom:1px solid #000000;">', esc(__('Item Details')), '</th>',
		'<th colspan="2" style="background:#d2b48c;padding:12px;text-align:center;font-weight:600;color:#000000;border-right:2px solid #000000;border-bottom:1px solid #000000;">', esc(__('Production')), '</th>',
		'<th colspan="5" style="background:#d2b48c;padding:12px;text-align:center;font-weight:600;color:#000000;border-right:2px solid #000000;border-bottom:1px solid #000000;">', esc(__('Sales')), '</th>',
		'<th colspan="5" style="background:#d2b48c;padding:12px;text-align:center;font-weight:600;color:#000000;border-right:2px solid #000000;border-bottom:1px solid #000000;">', esc(__('Purchase')), '</th>',
		'<th colspan="4" style="background:#d2b48c;padding:12px;text-align:center;font-weight:600;color:#000000;border-right:2px solid #000000;border-bottom:1px solid #000000;">', esc(__('Warehouse Stock')), '</th>',
		'</tr>',
		'<tr>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:1px solid #000000;border-bottom:1px solid #000000;width:150px;min-width:150px;">', esc(__('Item Code')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:2px solid #000000;border-bottom:1px solid #000000;width:150px;min-width:150px;">', esc(__('Category Name')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:1px solid #000000;border-bottom:1px solid #000000;width:140px;min-width:140px;">', esc(__('Last Production Date')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:2px solid #000000;border-bottom:1px solid #000000;width:140px;min-width:140px;">', esc(__('Last Production Qty')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:1px solid #000000;border-bottom:1px solid #000000;width:180px;min-width:180px;overflow:hidden;word-break:break-word;">', esc(__('Last Sales Order Party')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:1px solid #000000;border-bottom:1px solid #000000;width:140px;min-width:140px;">', esc(__('Last Sales Order Date')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:1px solid #000000;border-bottom:1px solid #000000;width:130px;min-width:130px;">', esc(__('Last Sales Order Qty')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:1px solid #000000;border-bottom:1px solid #000000;width:130px;min-width:130px;">', esc(__('Last Sales Order Rate')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:2px solid #000000;border-bottom:1px solid #000000;width:130px;min-width:130px;">', esc(__('Pending Sales Order Qty')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:1px solid #000000;border-bottom:1px solid #000000;width:180px;min-width:180px;overflow:hidden;word-break:break-word;">', esc(__('Last Purchase Party')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:1px solid #000000;border-bottom:1px solid #000000;width:140px;min-width:140px;">', esc(__('Last Purchase Order Date')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:1px solid #000000;border-bottom:1px solid #000000;width:140px;min-width:140px;">', esc(__('Last Purchase Order Qty')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:1px solid #000000;border-bottom:1px solid #000000;width:140px;min-width:140px;">', esc(__('Last Purchase Order Rate')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:2px solid #000000;border-bottom:1px solid #000000;width:140px;min-width:140px;">', esc(__('Pending Purchase Order Qty')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:1px solid #000000;border-bottom:1px solid #000000;width:200px;min-width:200px;">', esc(__('Warehouse')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:1px solid #000000;border-bottom:1px solid #000000;width:120px;min-width:120px;">', esc(__('Stock Qty')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:1px solid #000000;border-bottom:1px solid #000000;width:140px;min-width:140px;">', esc(__('Committed Stock')), '</th>',
		'<th style="background:#faf0e6;padding:10px;text-align:left;font-weight:600;color:#000000;border-right:2px solid #000000;border-bottom:1px solid #000000;width:140px;min-width:140px;">', esc(__('Projected Qty')), '</th>',
		'</tr>',
		'</thead>',
		'<tbody>'
	);

	// ── Body rows — pure string concatenation (no jQuery per row) ──
	const P = 'padding:12px;';                               // reusable style tokens
	const BR1 = 'border-right:1px solid #000000;';
	const BR2 = 'border-right:2px solid #000000;';
	const CLR = 'color:#495057;';
	const LEFT = 'text-align:left;';                          // left alignment for all data cells

	for (let index = 0; index < data.length; index++) {
		const row = data[index];
		const itemBgClass = index % 2 === 0 ? 'item-bg-blue' : 'item-bg-green';
		const hasMultipleWarehouses = row.warehouse_stock && row.warehouse_stock.length > 1;
		const mainLastClass = hasMultipleWarehouses ? '' : ' item-last-row';

		const wh0 = (row.warehouse_stock && row.warehouse_stock.length > 0) ? row.warehouse_stock[0] : null;

		htmlParts.push(
			'<tr class="item-row ', itemBgClass, mainLastClass, '" data-row-id="row-', index, '" data-item-index="', index, '">',
			// Item Details
			'<td style="', P, BR1, CLR, LEFT, 'width:150px;min-width:150px;">', esc(row.item_code || ''), '</td>',
			'<td style="', P, BR2, CLR, LEFT, 'width:150px;min-width:150px;">', esc(row.category_name || '-'), '</td>',
			// Production
			'<td style="', P, BR1, CLR, LEFT, 'width:140px;min-width:140px;">', fmtDate(row.last_production_date), '</td>',
			'<td style="', P, BR2, CLR, LEFT, 'width:140px;min-width:140px;">', fmtFloat(row.last_production_quantity), '</td>',
			// Sales
			'<td style="', P, BR1, CLR, LEFT, 'width:180px;min-width:180px;overflow:hidden;word-break:break-word;">', esc(row.last_sales_party || '-'), '</td>',
			'<td style="', P, BR1, CLR, LEFT, 'width:140px;min-width:140px;">', fmtDate(row.last_sales_date), '</td>',
			'<td style="', P, BR1, CLR, LEFT, 'width:130px;min-width:130px;">', fmtFloat(row.last_sales_quantity), '</td>',
			'<td style="', P, BR1, CLR, LEFT, 'width:130px;min-width:130px;">', fmtCurrency(row.last_sales_rate), '</td>',
			'<td style="', P, BR2, CLR, LEFT, 'width:130px;min-width:130px;">', fmtFloat(row.pending_sales_order_qty), '</td>',
			// Purchase
			'<td style="', P, BR1, CLR, LEFT, 'width:180px;min-width:180px;overflow:hidden;word-break:break-word;">', esc(row.last_purchase_party || '-'), '</td>',
			'<td style="', P, BR1, CLR, LEFT, 'width:140px;min-width:140px;">', fmtDate(row.last_purchase_date), '</td>',
			'<td style="', P, BR1, CLR, LEFT, 'width:140px;min-width:140px;">', fmtFloat(row.last_purchase_quantity), '</td>',
			'<td style="', P, BR1, CLR, LEFT, 'width:140px;min-width:140px;">', fmtCurrency(row.last_purchase_rate), '</td>',
			'<td style="', P, BR2, CLR, LEFT, 'width:140px;min-width:140px;">', fmtFloat(row.pending_purchase_order_qty), '</td>',
			// Warehouse Stock (first warehouse)
			'<td style="', P, BR1, CLR, LEFT, 'width:200px;min-width:200px;">', wh0 ? esc(wh0.warehouse || '-') : '-', '</td>',
			'<td style="', P, BR1, CLR, LEFT, 'width:120px;min-width:120px;">', wh0 ? fmtFloat(wh0.stock_qty) : '-', '</td>',
			'<td style="', P, BR1, CLR, LEFT, 'width:140px;min-width:140px;">', wh0 ? fmtFloat(wh0.committed_stock) : '-', '</td>',
			'<td style="', P, BR2, CLR, LEFT, 'width:140px;min-width:140px;">', wh0 ? fmtFloat(wh0.projected_qty) : '-', '</td>',
			'</tr>'
		);

		// Additional warehouse rows
		if (hasMultipleWarehouses) {
			for (let i = 1; i < row.warehouse_stock.length; i++) {
				const wh = row.warehouse_stock[i];
				const isLast = (i === row.warehouse_stock.length - 1);
				const whClass = isLast
					? 'warehouse-detail-row item-last-row ' + itemBgClass
					: 'warehouse-detail-row ' + itemBgClass;

				htmlParts.push(
					'<tr class="', whClass, '" data-parent-row="row-', index, '" data-item-index="', index, '">',
					'<td style="', P, BR1, LEFT, 'width:150px;min-width:150px;"></td>',
					'<td style="', P, BR2, LEFT, 'width:150px;min-width:150px;"></td>',
					'<td style="', P, BR1, LEFT, '"></td>',
					'<td style="', P, BR2, LEFT, '"></td>',
					'<td style="', P, BR1, LEFT, '"></td>',
					'<td style="', P, BR1, LEFT, '"></td>',
					'<td style="', P, BR1, LEFT, '"></td>',
					'<td style="', P, BR1, LEFT, '"></td>',
					'<td style="', P, BR2, LEFT, '"></td>',
					'<td style="', P, BR1, LEFT, '"></td>',
					'<td style="', P, BR1, LEFT, '"></td>',
					'<td style="', P, BR1, LEFT, '"></td>',
					'<td style="', P, BR1, LEFT, '"></td>',
					'<td style="', P, BR2, LEFT, '"></td>',
					'<td style="', P, BR1, CLR, LEFT, 'width:200px;min-width:200px;">', esc(wh.warehouse || '-'), '</td>',
					'<td style="', P, BR1, CLR, LEFT, 'width:120px;min-width:120px;">', fmtFloat(wh.stock_qty), '</td>',
					'<td style="', P, BR1, CLR, LEFT, 'width:140px;min-width:140px;">', fmtFloat(wh.committed_stock), '</td>',
					'<td style="', P, BR2, CLR, LEFT, 'width:140px;min-width:140px;">', fmtFloat(wh.projected_qty), '</td>',
					'</tr>'
				);
			}
		}
	}

	htmlParts.push('</tbody></table></div>');

	// Single DOM insertion — orders of magnitude faster than per-row append
	state.$tableContainer[0].innerHTML = htmlParts.join('');
}

function showError(state, message) {
	state.$tableContainer.empty();
	state.$tableContainer.append(`
		<div class="alert alert-danger" style="background:#f8d7da;border:1px solid #f5c6cb;color:#721c24;padding:16px;border-radius:8px;">
			<i class="fa fa-exclamation-triangle" style="margin-right:8px;"></i>
			${frappe.utils.escape_html(message)}
		</div>
	`);
}
