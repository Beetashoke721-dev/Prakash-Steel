// Copyright (c) 2025, beetashoke chakraborty and contributors
// For license information, please see license.txt

// Ensure the page is registered before adding event handlers
if (!frappe.pages['procurement-tracker-dashboard']) {
    frappe.pages['procurement-tracker-dashboard'] = {};
}

frappe.pages['procurement-tracker-dashboard'].on_page_load = function (wrapper) {

    // Build page shell
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Procurement Tracker Dashboard'),
        single_column: true,
    });

    // Initialize dashboard state
    const state = {
        page,
        wrapper,
        filters: {},
        $cards: null,
        $tabs: null,
        controls: {},
        currentTab: 'overview',
        // Debounce / stale-response infrastructure
        _refreshTimer: null,   // setTimeout handle for debounce
        _refreshGen: 0         // monotonic counter – stale responses are discarded
    };

    // Initialize dashboard components
    initializeDashboard(state);
};

frappe.pages['procurement-tracker-dashboard'].on_page_show = function () {
};

function initializeDashboard(state) {
    // Clear main content
    state.page.main.empty();

    // Create filter bar
    createFilterBar(state);

    // Create tabbed interface
    createTabbedInterface(state);

    // Create content containers
    createContentContainers(state);

    // Set default values
    setDefaultFilters(state);

    // Bind event handlers
    bindEventHandlers(state);

    // Set initial refresh button and supplier visibility for the default tab
    if (state.currentTab === 'overview') {
        state.controls.refreshBtn.show();
    } else {
        state.controls.refreshBtn.hide();
    }
    updateSupplierVisibility(state);

    // Load initial data
    refreshDashboard(state);
}

function createFilterBar(state) {
    // Main filter container
    const $filterBar = $('<div class="procurement-filters" style="display:flex;gap:12px;align-items:end;flex-wrap:wrap;margin-bottom:16px;justify-content:space-between;background:#f8f9fa;padding:16px;border-radius:8px;"></div>');

    // Filter controls container
    const $filterControls = $('<div style="display:flex;gap:12px;align-items:end;flex-wrap:wrap;"></div>');

    // Individual filter wrappers
    const $fromWrap = $('<div style="min-width:200px;"></div>');
    const $toWrap = $('<div style="min-width:200px;"></div>');
    const $supplierWrap = $('<div style="min-width:220px;"></div>');
    const $btnWrap = $('<div style="display:flex;align-items:end;gap:8px;"></div>');

    // Assemble filter controls
    $filterControls.append($fromWrap).append($toWrap).append($supplierWrap);
    $filterBar.append($filterControls).append($btnWrap);
    $(state.page.main).append($filterBar);

    // Create filter controls
    createFilterControls(state, $fromWrap, $toWrap, $supplierWrap, $btnWrap);

    // Keep a reference to the supplier wrapper so we can hide/show it per tab
    state.controls.supplierWrapper = $supplierWrap;
}

function createFilterControls(state, $fromWrap, $toWrap, $supplierWrap, $btnWrap) {
    // Date controls
    state.controls.from_date = frappe.ui.form.make_control({
        parent: $fromWrap.get(0),
        df: {
            fieldtype: 'Date',
            label: __('From Date'),
            fieldname: 'from_date',
            reqd: 1,
        },
        render_input: true,
    });

    state.controls.to_date = frappe.ui.form.make_control({
        parent: $toWrap.get(0),
        df: {
            fieldtype: 'Date',
            label: __('To Date'),
            fieldname: 'to_date',
            reqd: 1,
        },
        render_input: true,
    });

    // Supplier control
    state.controls.supplier = frappe.ui.form.make_control({
        parent: $supplierWrap.get(0),
        df: {
            fieldtype: 'Link',
            label: __('Supplier'),
            fieldname: 'supplier',
            options: 'Supplier',
            reqd: 0,
        },
        render_input: true,
    });


    // Buttons
    const $refreshBtn = $('<button class="btn btn-primary">' + __('Refresh') + '</button>');

    $btnWrap.append($refreshBtn);

    // Store button references
    state.controls.refreshBtn = $refreshBtn;

    // Apply black outline borders to main filter fields
    setTimeout(() => {
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
        $(state.controls.supplier.$input).css({
            'border': '1px solid #000000',
            'border-radius': '4px',
            'padding': '8px 12px',
            'height': '36px',
            'line-height': '1.4'
        });
    }, 100);
}

function createTabbedInterface(state) {
    // Tab container
    const $tabContainer = $('<div class="procurement-tabs" style="margin-bottom:20px;"></div>');
    const $tabList = $('<ul class="nav nav-tabs" role="tablist" style="border-bottom:2px solid #dee2e6;"></ul>');

    // Tab content container
    const $tabContent = $('<div class="tab-content" style="margin-top:20px;"></div>');

    // Create tabs
    const tabs = [
        { id: 'overview', label: __('Overview'), icon: 'fa fa-tachometer' },
        { id: 'material_request', label: __('Material Request'), icon: 'fa fa-file-text' },
        { id: 'purchase_order', label: __('Purchase Order'), icon: 'fa fa-shopping-cart' },
        { id: 'purchase_receipt', label: __('Purchase Receipt'), icon: 'fa fa-truck' },
        { id: 'purchase_invoice', label: __('Purchase Invoice'), icon: 'fa fa-file-invoice' },
        { id: 'item_wise', label: __('Item Wise Tracker'), icon: 'fa fa-list' }
    ];

    tabs.forEach((tab, index) => {
        const $tabItem = $(`
            <li class="nav-item" role="presentation">
                <button class="nav-link ${index === 0 ? 'active' : ''}" 
                        id="${tab.id}-tab" 
                        data-bs-toggle="tab" 
                        data-bs-target="#${tab.id}-content" 
                        type="button" 
                        role="tab" 
                        style="border:none;background:none;padding:12px 20px;color:#6c757d;font-weight:500;cursor:pointer;">
                    <i class="${tab.icon}" style="margin-right:8px;"></i>${tab.label}
                </button>
            </li>
        `);

        const $tabPane = $(`
            <div class="tab-pane fade ${index === 0 ? 'show active' : ''}" 
                 id="${tab.id}-content" 
                 role="tabpanel" 
                 style="min-height:400px;">
            </div>
        `);

        $tabList.append($tabItem);
        $tabContent.append($tabPane);

        // Store references
        if (!state.$tabs) state.$tabs = {};
        state.$tabs[tab.id] = { $item: $tabItem, $content: $tabPane };
    });

    $tabContainer.append($tabList).append($tabContent);
    $(state.page.main).append($tabContainer);
}

function createContentContainers(state) {
    // Create cards containers for each tab
    Object.keys(state.$tabs).forEach(tabId => {
        const $cardsContainer = $('<div class="number-cards-container" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-bottom:16px;"></div>');
        state.$tabs[tabId].$content.append($cardsContainer);

        if (!state.$cards) state.$cards = {};
        state.$cards[tabId] = $cardsContainer;

        // Create section-specific filters for non-overview tabs
        if (tabId !== 'overview') {
            createSectionFilters(state, tabId);
        }

        // Create table containers
        const $tablesContainer = $(`
            <div class="detailed-data-section">
                <h3>${getSectionTitle(tabId)}</h3>
                <div class="data-tables-container" id="${tabId}-tables"></div>
            </div>
        `);
        state.$tabs[tabId].$content.append($tablesContainer);
    });
}

function createSectionFilters(state, tabId) {
    let inner = '';
    if (tabId === 'item_wise') {
        // Item-wise tracker: only PO No and Item filters with refresh button
        inner = `
            <div id="${tabId}-po-filter" style="min-width:200px;"></div>
            <div id="${tabId}-item-filter" style="min-width:220px;"></div>
            <div id="${tabId}-refresh-btn" style="min-width:120px;display:flex;flex-direction:column;justify-content:end;"></div>
        `;
    } else {
        inner = `
            <div id="${tabId}-status-filter" style="min-width:180px;"></div>
            <div id="${tabId}-id-filter" style="min-width:180px;"></div>
            <div id="${tabId}-item-filter" style="min-width:200px;"></div>
            <div id="${tabId}-refresh-btn" style="min-width:120px;display:flex;flex-direction:column;justify-content:end;"></div>
        `;
    }

    const $sectionFilters = $(`
        <div class="section-filters" style="background:#f1f3f4;padding:12px;border-radius:6px;margin-bottom:16px;">
            <div style="display:flex;gap:12px;align-items:end;flex-wrap:wrap;">
                ${inner}
            </div>
        </div>
    `);

    // Insert before cards container
    state.$tabs[tabId].$content.find('.number-cards-container').before($sectionFilters);

    // Create section-specific filter controls
    createSectionFilterControls(state, tabId);
}

function createSectionFilterControls(state, tabId) {
    if (tabId === 'item_wise') {
        // PO No filter
        state.controls[`${tabId}_po_no`] = frappe.ui.form.make_control({
            parent: $(`#${tabId}-po-filter`).get(0),
            df: {
                fieldtype: 'Data',
                label: __('PO No'),
                fieldname: `${tabId}_po_no`,
                reqd: 0,
            },
            render_input: true,
        });

        // Item code filter
        state.controls[`${tabId}_item_code`] = frappe.ui.form.make_control({
            parent: $(`#${tabId}-item-filter`).get(0),
            df: {
                fieldtype: 'Link',
                options: 'Item',
                label: __('Item'),
                fieldname: `${tabId}_item_code`,
                reqd: 0,
            },
            render_input: true,
        });

        // Refresh button for item-wise tab - create as a proper input field
        state.controls[`${tabId}_refresh`] = frappe.ui.form.make_control({
            parent: $(`#${tabId}-refresh-btn`).get(0),
            df: {
                fieldtype: 'Button',
                label: __('Action'),
                fieldname: `${tabId}_refresh`,
                reqd: 0,
            },
            render_input: true,
        });

        // Customize the button after creation
        setTimeout(() => {
            // Find all possible button elements
            const $formControl = $(`#${tabId}-refresh-btn .form-control`);
            const $button = $(`#${tabId}-refresh-btn button`);
            const $input = $(`#${tabId}-refresh-btn input`);

            // Try to find the actual button element
            let $targetElement = $button.length ? $button : $formControl.length ? $formControl : $input;

            if ($targetElement.length) {
                $targetElement.removeClass('form-control').addClass('btn btn-primary');
                $targetElement.attr('style', `
                    background-color: #007bff !important;
                    border-color: #007bff !important;
                    color: white !important;
                    height: 32px !important;
                    padding: 6px 12px !important;
                    width: 100% !important;
                    border: 1px solid #007bff !important;
                    border-radius: 4px !important;
                `);
                $targetElement.html(__('Refresh'));
            } else {
            }
        }, 300);

        setTimeout(() => {
            $(`#${tabId}-po-filter .form-control, #${tabId}-item-filter .form-control`).css({
                'border': '1px solid #000000',
                'border-radius': '4px',
                'padding': '8px 12px',
                'height': '36px',
                'line-height': '1.4'
            });
        }, 100);
    } else {
        // Status filter
        const statusField = getStatusFieldName(tabId);
        const statusOptions = getStatusOptions(tabId);
        state.controls[`${tabId}_status`] = frappe.ui.form.make_control({
            parent: $(`#${tabId}-status-filter`).get(0),
            df: {
                fieldtype: 'Select',
                // For Material Request we show plain "Status" label, for others keep "Workflow Status"
                label: tabId === 'material_request' ? __('Status') : __('Workflow Status'),
                fieldname: `${tabId}_status`,
                options: statusOptions, reqd: 0,
            },
            render_input: true,
        });
        // Refresh button for other tabs - create as a proper input field
        state.controls[`${tabId}_refresh`] = frappe.ui.form.make_control({
            parent: $(`#${tabId}-refresh-btn`).get(0),
            df: {
                fieldtype: 'Button',
                label: __('Action'),
                fieldname: `${tabId}_refresh`,
                reqd: 0,
            },
            render_input: true,
        });

        // Customize the button after creation
        setTimeout(() => {
            // Find all possible button elements
            const $formControl = $(`#${tabId}-refresh-btn .form-control`);
            const $button = $(`#${tabId}-refresh-btn button`);
            const $input = $(`#${tabId}-refresh-btn input`);

            // Try to find the actual button element
            let $targetElement = $button.length ? $button : $formControl.length ? $formControl : $input;

            if ($targetElement.length) {
                $targetElement.removeClass('form-control').addClass('btn btn-primary');
                $targetElement.attr('style', `
                    background-color: #007bff !important;
                    border-color: #007bff !important;
                    color: white !important;
                    height: 36px !important;
                    padding: 8px 12px !important;
                    width: 100% !important;
                    border: 1px solid #007bff !important;
                    border-radius: 4px !important;
                `);
                $targetElement.html(__('Refresh'));
            } else {
            }
        }, 300);

        setTimeout(() => {
            $(`#${tabId}-status-filter .form-control, #${tabId}-id-filter .form-control, #${tabId}-item-filter .form-control`).css({
                'border': '1px solid #000000',
                'border-radius': '4px',
                'padding': '8px 12px',
                'height': '36px',
                'line-height': '1.4'
            });
        }, 100);

        // ID filter - use Link fieldtype for autocomplete suggestions
        const idField = getIdFieldName(tabId);
        const idDoctype = getIdFieldDoctype(tabId);
        
        if (idDoctype) {
            // Create Link field with get_query to filter by docstatus and date range
            const df = {
                fieldtype: 'Link',
                options: idDoctype,
                label: __('ID'),
                fieldname: `${tabId}_id`,
                reqd: 0,
                get_query: function() {
                    // Get current main filter values from state
                    const fromDate = state.controls.from_date ? state.controls.from_date.get_value() : null;
                    const toDate = state.controls.to_date ? state.controls.to_date.get_value() : null;
                    const supplier = state.controls.supplier ? state.controls.supplier.get_value() : null;
                    
                    // Determine date field based on doctype
                    let dateField = 'transaction_date';
                    if (idDoctype === 'Purchase Receipt' || idDoctype === 'Purchase Invoice') {
                        dateField = 'posting_date';
                    }
                    
                    const filters = {
                        'docstatus': 1  // Only submitted documents
                    };
                    
                    // Add date range filter if dates are available
                    if (fromDate && toDate) {
                        filters[dateField] = ['between', [fromDate, toDate]];
                    }
                    
                    // Add supplier filter if applicable (PO, PR, PI have supplier field)
                    if (supplier && (idDoctype === 'Purchase Order' || idDoctype === 'Purchase Receipt' || idDoctype === 'Purchase Invoice')) {
                        filters['supplier'] = supplier;
                    }
                    
                    return {
                        filters: filters
                    };
                }
            };
            
            state.controls[`${tabId}_id`] = frappe.ui.form.make_control({
                parent: $(`#${tabId}-id-filter`).get(0),
                df: df,
                render_input: true,
            });
        } else {
            // Fallback to Data field for unknown tab types
            state.controls[`${tabId}_id`] = frappe.ui.form.make_control({
                parent: $(`#${tabId}-id-filter`).get(0),
                df: { fieldtype: 'Data', label: __('ID'), fieldname: `${tabId}_id`, reqd: 0 },
                render_input: true,
            });
        }

        // Item name filter
        state.controls[`${tabId}_item_name`] = frappe.ui.form.make_control({
            parent: $(`#${tabId}-item-filter`).get(0),
            df: { fieldtype: 'Link', options: 'Item', label: __('Item'), fieldname: `${tabId}_item_name`, reqd: 0 },
            render_input: true,
        });
    }
}

function getStatusFieldName(tabId) {
    const statusFields = {
        'material_request': 'mr_status',
        'purchase_order': 'po_status',
        'purchase_receipt': 'pr_status',
        'purchase_invoice': 'pi_status'
    };
    return statusFields[tabId] || 'status';
}

function getIdFieldName(tabId) {
    const idFields = {
        'material_request': 'mr_id',
        'purchase_order': 'po_id',
        'purchase_receipt': 'pr_id',
        'purchase_invoice': 'pi_id'
    };
    return idFields[tabId] || 'id';
}

function getIdFieldDoctype(tabId) {
    const doctypeMap = {
        'material_request': 'Material Request',
        'purchase_order': 'Purchase Order',
        'purchase_receipt': 'Purchase Receipt',
        'purchase_invoice': 'Purchase Invoice'
    };
    return doctypeMap[tabId] || null;
}

function getItemFieldName(tabId) {
    const itemFields = {
        'material_request': 'mr_item_name',
        'purchase_order': 'po_item_name',
        'purchase_receipt': 'pr_item_name',
        'purchase_invoice': 'pi_item_name'
    };
    return itemFields[tabId] || 'item_name';
}

function getSectionTitle(tabId) {
    const titles = {
        'overview': __('Procurement Overview'),
        'material_request': __('Material Request Details'),
        'purchase_order': __('Purchase Order Details'),
        'purchase_receipt': __('Purchase Receipt Details'),
        'purchase_invoice': __('Purchase Invoice Details'),
        'item_wise': __('Item Wise Tracker')
    };
    return titles[tabId] || __('Details');
}

function fetchItemWiseTrackerData(filters) {
    return new Promise((resolve, reject) => {
        frappe.call({
            method: 'frappe.desk.query_report.run',
            args: {
                report_name: 'Item Wise Procurement Tracker',
                filters: {
                    from_date: filters.from_date,
                    to_date: filters.to_date,
                    supplier: filters.supplier || '',
                    item_code: filters.item_code || '',
                    po_no: filters.po_no || ''
                },
                ignore_prepared_report: 1,
            },
            callback: (r) => {
                if (r.message && r.message.result) {
                    resolve({
                        summary: [{ value: r.message.result.length, label: __('Tracked Items'), datatype: 'Int', indicator: 'Blue' }],
                        raw_data: r.message.result
                    });
                } else {
                    resolve({ summary: [], raw_data: [] });
                }
            },
            error: reject
        });
    });
}

function renderItemWiseTable($container, data) {
    if (!data || data.length === 0) {
        $container.append(`
            <div class="no-data-message">
                <div>${__('No item-wise data available for selected criteria')}</div>
            </div>
        `);
        return;
    }

    const $table = $(`
        <div class="data-table" style="width: 100%; margin-bottom: 30px;">
            <h4>${__('Item Wise Tracker')}</h4>
            <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 6px; overflow: hidden; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                <thead>
                    <tr>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('PO No')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Item Name')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Due Date')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: right; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Qty')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('UOM')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: right; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Received Qty')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: right; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Received %')}</th>
                    </tr>
                </thead>
                <tbody>
                </tbody>
            </table>
        </div>
    `);

    const $tbody = $table.find('tbody');

    data.forEach((row) => {
        const receivedPct = row.received_pct || 0;
        const $tr = $(`
            <tr style="border-bottom: 1px solid #e9ecef;">
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;"><a href="/app/purchase-order/${row.po_no}" class="link-cell" style="color: #007bff; text-decoration: none; cursor: pointer;">${row.po_no}</a></td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${row.item_name || ''}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${frappe.format(row.required_by, { fieldtype: 'Date' })}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: right;">${frappe.format(row.qty || 0, { fieldtype: 'Float', precision: 2 })}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${row.uom || ''}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: right;">${frappe.format(row.received_qty || 0, { fieldtype: 'Float', precision: 2 })}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: right; white-space: nowrap;">${frappe.format(receivedPct, { fieldtype: 'Percent', precision: 2 })}</td>
            </tr>
        `);
        $tbody.append($tr);
    });

    $container.append($table);
}

function setDefaultFilters(state) {
    // Set default date range
    state.controls.from_date.set_value(frappe.datetime.month_start());
    state.controls.to_date.set_value(frappe.datetime.month_end());
}

/**
 * Schedule a dashboard refresh after a short debounce window.
 * Rapid consecutive filter changes collapse into a single API round-trip,
 * preventing duplicate / overlapping requests.
 */
function debouncedRefresh(state, delay) {
    delay = delay || 300;
    if (state._refreshTimer) {
        clearTimeout(state._refreshTimer);
    }
    state._refreshTimer = setTimeout(() => {
        state._refreshTimer = null;
        refreshDashboard(state);
    }, delay);
}

/**
 * Bind a Frappe control so that ANY value change – whether triggered by
 * typing, datepicker click, Link autocomplete select, or the ✕ clear
 * button – routes through the debounced refresh pipeline.
 *
 * Strategy (belt-and-suspenders):
 *   1. Set df.change / df.onchange  → Frappe calls this after set_value()
 *   2. jQuery 'change' on $input    → native DOM fallback
 *   3. 'awesomplete-selectcomplete' → Link autocomplete select
 *   4. 'click' on .btn-clear        → Link field clear button
 */
function bindControlAutoRefresh(control, state) {
    const handler = () => debouncedRefresh(state);

    // Frappe internal callbacks (most reliable for programmatic set_value)
    control.df.change = handler;
    control.df.onchange = handler;

    // Native DOM change (user typing + tab-out / datepicker pick)
    if (control.$input) {
        $(control.$input).on('change', handler);
    }

    // Link-specific: autocomplete selection fires this custom event
    if (control.df.fieldtype === 'Link' && control.$input) {
        $(control.$input).on('awesomplete-selectcomplete', handler);
        // Clear button (✕) inside the Link wrapper
        if (control.$wrapper) {
            $(control.$wrapper).on('click', '.btn-clear', handler);
        }
    }
}

function bindEventHandlers(state) {
    // ── Main filters (From Date, To Date, Supplier) ──────────────
    bindControlAutoRefresh(state.controls.from_date, state);
    bindControlAutoRefresh(state.controls.to_date, state);
    bindControlAutoRefresh(state.controls.supplier, state);

    // ── Section filters (per-tab) ────────────────────────────────
    Object.keys(state.$tabs).forEach(tabId => {
        if (tabId === 'overview') return;

        if (tabId === 'item_wise') {
            bindControlAutoRefresh(state.controls[`${tabId}_po_no`], state);
            bindControlAutoRefresh(state.controls[`${tabId}_item_code`], state);
        } else {
            bindControlAutoRefresh(state.controls[`${tabId}_status`], state);
            bindControlAutoRefresh(state.controls[`${tabId}_id`], state);
            bindControlAutoRefresh(state.controls[`${tabId}_item_name`], state);
        }

        // Per-tab Refresh button – use delegated click on the wrapper
        // so it works regardless of whether Frappe renders <button> or <input>
        $(`#${tabId}-refresh-btn`).on('click', 'button, .btn, .form-control, input', () => {
            refreshDashboard(state);
        });
    });

    // ── Main Refresh button (always works as a manual override) ──
    state.controls.refreshBtn.on('click', () => refreshDashboard(state));

    // ── Tab change events ────────────────────────────────────────
    Object.keys(state.$tabs).forEach(tabId => {
        state.$tabs[tabId].$item.find('button').on('click', () => {
            state.currentTab = tabId;
            updateTabStyles(state);

            // Show/hide tab content
            $('.tab-pane').removeClass('show active');
            $(`#${tabId}-content`).addClass('show active');

            // Update tab buttons
            $('.nav-link').removeClass('active');
            $(`#${tabId}-tab`).addClass('active');

            // Show / hide supplier filter based on current tab
            updateSupplierVisibility(state);

            // Show/hide main refresh button based on current tab
            if (tabId === 'overview') {
                state.controls.refreshBtn.show();
            } else {
                state.controls.refreshBtn.hide();
            }

            // Trigger refresh for the current tab
            refreshDashboard(state);
        });
    });
}

function updateSupplierVisibility(state) {
    const hideTabs = ['overview', 'material_request', 'item_wise'];
    const wrapper = state.controls && state.controls.supplierWrapper;
    if (!wrapper) return;

    if (hideTabs.includes(state.currentTab)) {
        wrapper.hide();
    } else {
        wrapper.show();
    }
}

function updateTabStyles(state) {
    // Update active tab styling
    Object.keys(state.$tabs).forEach(tabId => {
        const $button = state.$tabs[tabId].$item.find('button');
        if (tabId === state.currentTab) {
            $button.addClass('active').css({
                'color': '#007bff',
                'border-bottom': '2px solid #007bff'
            });
        } else {
            $button.removeClass('active').css({
                'color': '#6c757d',
                'border-bottom': 'none'
            });
        }
    });
}

function refreshDashboard(state) {

    const filters = getFilters(state);

    if (!filters.from_date || !filters.to_date) {
        showError(state, __('Please select both From Date and To Date'));
        return;
    }

    // ── Stale-response guard ─────────────────────────────────────
    // Increment the generation counter.  When the Promise.all resolves
    // we compare the counter – if another refresh was triggered in the
    // meantime, this response is stale and we silently discard it.
    state._refreshGen = (state._refreshGen || 0) + 1;
    const thisGen = state._refreshGen;

    // Show loading state
    state.page.set_indicator(__('Loading dashboard data...'), 'blue');

    // Fetch data for all sections – overview uses a dedicated API for
    // accurate counts instead of aggregating from the tab data.
    Promise.all([
        fetchOverviewData(filters),
        fetchProcurementData(filters),
        fetchMaterialRequestData(filters, state),
        fetchPurchaseOrderData(filters, state),
        fetchPurchaseReceiptData(filters, state),
        fetchPurchaseInvoiceData(filters, state),
        fetchItemWiseTrackerData(filters)
    ]).then(([overviewData, procurementData, mrData, poData, prData, piData, itemWiseData]) => {
        // Discard stale response – a newer refresh is already in flight
        if (state._refreshGen !== thisGen) return;

        state.page.clear_indicator();

        // Render all sections
        renderDashboardData(state, {
            overview: overviewData,
            material_request: mrData,
            purchase_order: poData,
            purchase_receipt: prData,
            purchase_invoice: piData,
            item_wise: itemWiseData
        });
    }).catch((error) => {
        // Discard stale error – a newer refresh is already in flight
        if (state._refreshGen !== thisGen) return;

        state.page.clear_indicator();
        console.error('Dashboard refresh error:', error);
        showError(state, __('An error occurred while loading data'));
    });
}

function fetchProcurementData(filters) {
    return new Promise((resolve, reject) => {
        frappe.call({
            method: 'frappe.desk.query_report.run',
            args: {
                report_name: 'New Procurement Tracker',
                filters: {
                    from_date: filters.from_date,
                    to_date: filters.to_date,
                    item_code: filters.item_name || ''
                },
                ignore_prepared_report: 1,
            },
            callback: (r) => {
                if (r.message && r.message.result) {
                    resolve(r.message.result || []);
                } else {
                    resolve([]);
                }
            },
            error: reject
        });
    });
}

function fetchMaterialRequestData(filters, state) {
    return new Promise((resolve, reject) => {
        // Use the procurement tracker report to get data with workflow_state
        frappe.call({
            method: 'frappe.desk.query_report.run',
            args: {
                report_name: 'New Procurement Tracker',
                filters: {
                    from_date: filters.from_date,
                    to_date: filters.to_date,
                    item_code: filters.mr_item_name || ''
                },
                ignore_prepared_report: 1,
            },
            callback: (r) => {
                if (r.message && r.message.result) {
                    let procurementData = r.message.result;

                    // Extract unique Material Requests from procurement data
                    const materialRequests = [];
                    const seenMRs = new Set();

                    procurementData.forEach(row => {
                        if (row.material_request && !seenMRs.has(row.material_request)) {
                            seenMRs.add(row.material_request);
                            materialRequests.push({
                                name: row.material_request,
                                transaction_date: row.indent_date,
                                workflow_state: row.mr_status,
                                status: row.mr_status // Use workflow_state as status for display
                            });
                        }
                    });

                    // Apply additional filters
                    let filteredData = materialRequests;

                    // Apply status filter (treat "All" as no filter)
                    if (filters.mr_status && filters.mr_status !== 'All') {
                        filteredData = filteredData.filter(mr => (mr.workflow_state || '').toLowerCase() === filters.mr_status.toLowerCase());
                    }


                    // Apply ID filter (exact match since Link field returns exact name)
                    if (filters.mr_id) {
                        filteredData = filteredData.filter(mr => mr.name === filters.mr_id);
                    }

                    // Apply item filter if specified - filter the original procurement data first
                    if (filters.item_name) {
                        const itemFilteredProcurementData = procurementData.filter(row =>
                            row.item_code === filters.item_name
                        );

                        // Extract unique Material Requests from item-filtered data
                        const itemFilteredMRs = [];
                        const seenItemFilteredMRs = new Set();

                        itemFilteredProcurementData.forEach(row => {
                            if (row.material_request && !seenItemFilteredMRs.has(row.material_request)) {
                                seenItemFilteredMRs.add(row.material_request);
                                itemFilteredMRs.push({
                                    name: row.material_request,
                                    transaction_date: row.indent_date,
                                    workflow_state: row.mr_status,
                                    status: row.mr_status
                                });
                            }
                        });

                        // Apply other filters to item-filtered data
                        filteredData = itemFilteredMRs;
                    }

                    // ── Build Material Request summary cards ──
                    // Total Material Requests (excluding cancelled – report already enforces docstatus = 1)
                    const totalMR = filteredData.length;

                    // Helper to count by status (case‑insensitive)
                    const countByStatus = (statusName) =>
                        filteredData.filter(mr => (mr.workflow_state || '').toLowerCase() === statusName.toLowerCase()).length;

                    const pendingMR = countByStatus('Pending');
                    const partiallyReceivedMR = countByStatus('Partially Received');
                    const partiallyOrderedMR = countByStatus('Partially Ordered');

                    const summary = [
                        {
                            value: totalMR,
                            label: __('Total Material Requests'),
                            datatype: 'Int',
                            indicator: 'Blue',
                            description: __('Total material requests (excluding cancelled)')
                        },
                        {
                            value: pendingMR,
                            label: __('Pending Material Requests'),
                            datatype: 'Int',
                            indicator: 'Orange',
                            description: __('Material requests with Pending status')
                        },
                        {
                            value: partiallyReceivedMR,
                            label: __('Partially Received MR'),
                            datatype: 'Int',
                            indicator: 'Yellow',
                            description: __('Material requests with Partially Received status')
                        },
                        {
                            value: partiallyOrderedMR,
                            label: __('Partially Ordered MR'),
                            datatype: 'Int',
                            indicator: 'Green',
                            description: __('Material requests with partial order quantity')
                        }
                    ];

                    // Update status options (fixed options for MR tab)
                    updateStatusOptions('material_request', filteredData, state);

                    resolve({
                        summary: summary,
                        raw_data: filteredData
                    });
                } else {
                    resolve({ summary: [], raw_data: [] });
                }
            },
            error: reject
        });
    });
}

function filterMaterialRequestsByItemName(materialRequests, itemName) {
    return new Promise((resolve, reject) => {
        if (!itemName) {
            resolve(materialRequests);
            return;
        }

        // Get all material request names
        const mrNames = materialRequests.map(mr => mr.name);

        if (mrNames.length === 0) {
            resolve([]);
            return;
        }

        // Fetch Material Request Items that match the item name
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Material Request Item',
                filters: [
                    ['Material Request Item', 'parent', 'in', mrNames],
                    ['Material Request Item', 'item_name', 'like', `%${itemName}%`]
                ],
                fields: ['parent'],
                limit_page_length: 1000
            },
            callback: (r) => {
                if (r.message) {
                    // Get unique parent names
                    const filteredParentNames = [...new Set(r.message.map(item => item.parent))];

                    // Filter material requests to only include those with matching items
                    const filteredMRs = materialRequests.filter(mr =>
                        filteredParentNames.includes(mr.name)
                    );

                    resolve(filteredMRs);
                } else {
                    resolve([]);
                }
            },
            error: reject
        });
    });
}

function filterPurchaseOrdersByItemName(purchaseOrders, itemName) {
    return new Promise((resolve, reject) => {
        if (!itemName) {
            resolve(purchaseOrders);
            return;
        }

        const poNames = purchaseOrders.map(po => po.name);

        if (poNames.length === 0) {
            resolve([]);
            return;
        }

        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Purchase Order Item',
                filters: [
                    ['Purchase Order Item', 'parent', 'in', poNames],
                    // Match by item_code so it aligns with the Item link filter on the UI
                    ['Purchase Order Item', 'item_code', '=', itemName]
                ],
                fields: ['parent'],
                limit_page_length: 1000
            },
            callback: (r) => {
                if (r.message) {
                    const filteredParentNames = [...new Set(r.message.map(item => item.parent))];
                    const filteredPOs = purchaseOrders.filter(po =>
                        filteredParentNames.includes(po.name)
                    );
                    resolve(filteredPOs);
                } else {
                    resolve([]);
                }
            },
            error: reject
        });
    });
}

function filterPurchaseReceiptsByItemName(purchaseReceipts, itemName) {
    return new Promise((resolve, reject) => {
        if (!itemName) {
            resolve(purchaseReceipts);
            return;
        }

        const prNames = purchaseReceipts.map(pr => pr.name);

        if (prNames.length === 0) {
            resolve([]);
            return;
        }

        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Purchase Receipt Item',
                filters: [
                    ['Purchase Receipt Item', 'parent', 'in', prNames],
                    // Match item_code so it aligns with the Item link filter on the UI
                    ['Purchase Receipt Item', 'item_code', '=', itemName]
                ],
                fields: ['parent'],
                limit_page_length: 1000
            },
            callback: (r) => {
                if (r.message) {
                    const filteredParentNames = [...new Set(r.message.map(item => item.parent))];
                    const filteredPRs = purchaseReceipts.filter(pr =>
                        filteredParentNames.includes(pr.name)
                    );
                    resolve(filteredPRs);
                } else {
                    resolve([]);
                }
            },
            error: reject
        });
    });
}

function filterPurchaseInvoicesByItemName(purchaseInvoices, itemName) {
    return new Promise((resolve, reject) => {
        if (!itemName) {
            resolve(purchaseInvoices);
            return;
        }

        const piNames = purchaseInvoices.map(pi => pi.name);

        if (piNames.length === 0) {
            resolve([]);
            return;
        }

        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Purchase Invoice Item',
                filters: [
                    ['Purchase Invoice Item', 'parent', 'in', piNames],
                    ['Purchase Invoice Item', 'item_name', 'like', `%${itemName}%`]
                ],
                fields: ['parent'],
                limit_page_length: 1000
            },
            callback: (r) => {
                if (r.message) {
                    const filteredParentNames = [...new Set(r.message.map(item => item.parent))];
                    const filteredPIs = purchaseInvoices.filter(pi =>
                        filteredParentNames.includes(pi.name)
                    );
                    resolve(filteredPIs);
                } else {
                    resolve([]);
                }
            },
            error: reject
        });
    });
}

function fetchPurchaseOrderData(filters, state) {
    return new Promise((resolve, reject) => {
        // Build filters directly on Purchase Order doctype so we include ALL POs,
        // not just those linked via the New Procurement Tracker report.
        const poFilters = {
            docstatus: 1,
            transaction_date: ['between', [filters.from_date, filters.to_date]]
        };

        if (filters.supplier) {
            poFilters.supplier = filters.supplier;
        }
        if (filters.po_status) {
            poFilters.workflow_state = filters.po_status;
        }
        if (filters.po_id) {
            poFilters.name = filters.po_id;
        }

        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Purchase Order',
                filters: poFilters,
                fields: ['name', 'transaction_date', 'workflow_state', 'status', 'supplier', 'grand_total'],
                limit_page_length: 10000
            },
            callback: (r) => {
                let purchaseOrders = (r.message || []).map(po => ({
                    name: po.name,
                    transaction_date: po.transaction_date,
                    workflow_state: po.workflow_state || '',
                    status: po.status || '',
                    supplier: po.supplier || '',
                    grand_total: parseFloat(po.grand_total || 0)
                }));

                const proceedWithData = (data) => {
                    const filteredData = data;

                    // ── Build Purchase Order summary cards (matching the screenshot) ──
                    const totalPOs = filteredData.length;

                    const countByWorkflow = (statusName) =>
                        filteredData.filter(po => (po.workflow_state || '').toLowerCase() === statusName.toLowerCase()).length;

                    const pendingPOs = countByWorkflow('Pending');
                    // Pending Approval – include both 'Waiting For Approval' and 'To Approve'
                    const pendingApprovalPOs =
                        countByWorkflow('Waiting For Approval') + countByWorkflow('To Approve');

                    const totalPOValue = filteredData.reduce((sum, po) => {
                        return sum + (po.grand_total || 0);
                    }, 0);

                    const summary = [
                        {
                            value: totalPOs,
                            label: __('Total Purchase Orders'),
                            datatype: 'Int',
                            indicator: 'Blue',
                            description: __('Total purchase orders (excluding cancelled)')
                        },
                        {
                            value: pendingPOs,
                            label: __('Pending Purchase Orders'),
                            datatype: 'Int',
                            indicator: 'Orange',
                            description: __('Purchase orders with Pending status')
                        },
                        {
                            value: pendingApprovalPOs,
                            label: __('Pending Approval Purchase Orders'),
                            datatype: 'Int',
                            indicator: 'Green',
                            description: __('Purchase orders pending approval')
                        },
                        {
                            value: totalPOValue,
                            label: __('Total Purchase Order Value'),
                            datatype: 'Currency',
                            indicator: 'Purple',
                            description: __('Sum of grand total for selected date range'),
                            prefix: '₹'
                        }
                    ];

                    // Dynamic status dropdown options based on actual workflow_state values
                    updateStatusOptions('purchase_order', purchaseOrders, state);

                    resolve({
                        summary: summary,
                        raw_data: filteredData
                    });
                };

                // Apply item filter via Purchase Order Item if specified
                if (filters.po_item_name && purchaseOrders.length > 0) {
                    filterPurchaseOrdersByItemName(purchaseOrders, filters.po_item_name)
                        .then(filtered => {
                            proceedWithData(filtered);
                        })
                        .catch(err => {
                            console.warn('Error filtering POs by item, falling back to unfiltered list:', err);
                            proceedWithData(purchaseOrders);
                        });
                } else {
                    proceedWithData(purchaseOrders);
                }
            },
            error: reject
        });
    });
}

function fetchPurchaseReceiptData(filters, state) {
    return new Promise((resolve, reject) => {
        // Fetch Purchase Receipts directly so we can build accurate cards:
        // Total Purchase Receipts, Completed Purchase Receipts, Total Receipt Value
        const prFilters = {
            docstatus: 1,
            posting_date: ['between', [filters.from_date, filters.to_date]]
        };

        // Add supplier filter if specified
        if (filters.supplier) {
            prFilters.supplier = filters.supplier;
        }

        // Add ID filter if specified
        if (filters.pr_id) {
            prFilters.name = filters.pr_id;
        }

        const summary = [];

        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Purchase Receipt',
                filters: prFilters,
                fields: ['name', 'posting_date', 'status', 'supplier', 'grand_total'],
                limit_page_length: 10000
            },
            callback: (r) => {
                let receipts = [];

                if (r.message && r.message.length > 0) {
                    receipts = r.message.map(pr => ({
                        name: pr.name,
                        posting_date: pr.posting_date,
                        workflow_state: pr.status || '',
                        status: pr.status || '',
                        supplier: pr.supplier || '',
                        grand_total: parseFloat(pr.grand_total || 0)
                    }));
                }

                const proceedWithData = (data) => {
                    const filteredData = data;

                    const totalReceipts = filteredData.length;
                    const completedReceipts = filteredData.filter(pr =>
                        (pr.status || '').toLowerCase() === 'completed'
                    ).length;

                    const totalReceiptValue = filteredData.reduce((sum, pr) => {
                        return sum + (pr.grand_total || 0);
                    }, 0);

                    // Total Purchase Receipts card
                    summary.push({
                        value: totalReceipts,
                        label: __('Total Purchase Receipts'),
                        datatype: 'Int',
                        indicator: 'Blue',
                        description: __('Total purchase receipts')
                    });

                    // Completed Purchase Receipts card
                    summary.push({
                        value: completedReceipts,
                        label: __('Completed Purchase Receipts'),
                        datatype: 'Int',
                        indicator: 'Green',
                        description: __('Purchase receipts with Completed status')
                    });

                    // Total Receipt Value card
                    summary.push({
                        value: totalReceiptValue,
                        label: __('Total Receipt Value'),
                        datatype: 'Currency',
                        indicator: 'Purple',
                        description: __('Sum of grand total for selected date range'),
                        prefix: '₹'
                    });

                    updateStatusOptions('purchase_receipt', receipts, state);
                    resolve({
                        summary: summary,
                        raw_data: filteredData
                    });
                };

                // Apply item filter via Purchase Receipt Item if specified
                if (filters.pr_item_name && receipts.length > 0) {
                    filterPurchaseReceiptsByItemName(receipts, filters.pr_item_name)
                        .then(filtered => {
                            proceedWithData(filtered);
                        })
                        .catch(err => {
                            console.warn('Error filtering PRs by item, falling back to unfiltered list:', err);
                            proceedWithData(receipts);
                        });
                } else {
                    proceedWithData(receipts);
                }
            },
            error: () => {
                summary.push({
                    value: 0,
                    label: __('Total Purchase Receipts'),
                    datatype: 'Int',
                    indicator: 'Blue',
                    description: __('Total purchase receipts')
                });

                summary.push({
                    value: 0,
                    label: __('Completed Purchase Receipts'),
                    datatype: 'Int',
                    indicator: 'Green',
                    description: __('Purchase receipts with Completed status')
                });

                summary.push({
                    value: 0,
                    label: __('Total Receipt Value'),
                    datatype: 'Currency',
                    indicator: 'Purple',
                    description: __('Sum of grand total for selected date range'),
                    prefix: '₹'
                });

                updateStatusOptions('purchase_receipt', [], state);
                resolve({
                    summary: summary,
                    raw_data: []
                });
            }
        });
    });
}

function fetchPurchaseInvoiceData(filters, state) {
    return new Promise((resolve, reject) => {
        // Use the new Purchase Invoice Tracker report
        frappe.call({
            method: 'frappe.desk.query_report.run',
            args: {
                report_name: 'Purchase Invoice Tracker',
                filters: {
                    from_date: filters.from_date,
                    to_date: filters.to_date,
                    supplier: filters.supplier || '',
                    // Treat "All" (or empty) as no workflow filter
                    workflow_status: (!filters.pi_status || filters.pi_status === 'All') ? '' : filters.pi_status
                },
                ignore_prepared_report: 1,
            },
            callback: (r) => {
                if (r.message && r.message.result) {
                    let piData = r.message.result;

                    // Transform data to match expected format
                    const purchaseInvoices = [];
                    const seenPIs = new Set();
                    let totalGrandTotal = 0; // Calculate sum of grand total

                    piData.forEach(row => {
                        if (row.purchase_invoice_id && !seenPIs.has(row.purchase_invoice_id)) {
                            seenPIs.add(row.purchase_invoice_id);
                            const grandTotal = parseFloat(row.grand_total || 0);
                            totalGrandTotal += grandTotal;

                            purchaseInvoices.push({
                                name: row.purchase_invoice_id,
                                posting_date: row.date,
                                due_date: row.due_date || null, // Will be fetched separately
                                workflow_state: row.status,
                                status: row.status,
                                supplier: row.supplier,
                                grand_total: grandTotal
                            });
                        }
                    });

                    // Fetch due_date from Purchase Invoice documents
                    if (purchaseInvoices.length > 0) {
                        const invoiceNames = purchaseInvoices.map(pi => pi.name);

                        frappe.call({
                            method: 'frappe.client.get_list',
                            args: {
                                doctype: 'Purchase Invoice',
                                filters: [['Purchase Invoice', 'name', 'in', invoiceNames]],
                                fields: ['name', 'due_date'],
                                limit_page_length: 1000
                            },
                            callback: (piDetails) => {
                                if (piDetails.message) {
                                    // Create a map for quick lookup
                                    const piDetailsMap = {};
                                    piDetails.message.forEach(pi => {
                                        piDetailsMap[pi.name] = {
                                            due_date: pi.due_date
                                        };
                                    });

                                    // Update purchase invoices with the fetched data
                                    purchaseInvoices.forEach(pi => {
                                        const details = piDetailsMap[pi.name];
                                        if (details) {
                                            pi.due_date = details.due_date;
                                        }
                                    });
                                }

                                // Continue with the rest of the processing
                                processPurchaseInvoiceData();
                            },
                            error: (error) => {
                                console.warn('Could not fetch Purchase Invoice details:', error);
                                // Continue with the rest of the processing even if this fails
                                processPurchaseInvoiceData();
                            }
                        });
                    } else {
                        processPurchaseInvoiceData();
                    }

                    function processPurchaseInvoiceData() {
                        // Apply additional filters
                        let filteredData = purchaseInvoices;

                        // Apply ID filter (exact match since Link field returns exact name)
                        if (filters.pi_id) {
                            filteredData = filteredData.filter(pi => pi.name === filters.pi_id);
                        }

                        // Apply supplier filter if specified
                        if (filters.supplier) {
                            filteredData = filteredData.filter(pi => pi.supplier === filters.supplier);
                        }

                        // Apply item filter if specified - filter the original procurement data first
                        if (filters.pi_item_name) {
                            const itemFilteredProcurementData = procurementData.filter(row =>
                                row.item_code === filters.pi_item_name
                            );

                            // Extract unique Purchase Invoices from item-filtered data
                            const itemFilteredPIs = [];
                            const seenItemFilteredPIs = new Set();

                            itemFilteredProcurementData.forEach(row => {
                                if (row.purchase_invoice && !seenItemFilteredPIs.has(row.purchase_invoice)) {
                                    seenItemFilteredPIs.add(row.purchase_invoice);
                                    itemFilteredPIs.push({
                                        name: row.purchase_invoice,
                                        posting_date: row.invoice_date,
                                        workflow_state: row.pi_status,
                                        status: row.pi_status,
                                        supplier: row.supplier,
                                        grand_total: 0
                                    });
                                }
                            });

                            // Apply other filters to item-filtered data
                            filteredData = itemFilteredPIs;
                        }

                        // Apply status filter (ignore "All")
                        if (filters.pi_status && filters.pi_status !== 'All') {
                            filteredData = filteredData.filter(pi => pi.workflow_state === filters.pi_status);
                        }

                        // Apply ID filter (exact match since Link field returns exact name)
                        if (filters.pi_id) {
                            filteredData = filteredData.filter(pi => pi.name === filters.pi_id);
                        }

                        // Apply supplier filter
                        if (filters.supplier) {
                            filteredData = filteredData.filter(pi => pi.supplier === filters.supplier);
                        }

                        // Never count cancelled invoices in the dashboard cards / table
                        filteredData = filteredData.filter(pi =>
                            (pi.status || '').toLowerCase() !== 'cancelled'
                        );

                        // ── Build Purchase Invoice summary cards (matching UI) ──
                        const totalInvoices = filteredData.length;

                        const countByStatus = (statusName) =>
                            filteredData.filter(pi => (pi.status || '').toLowerCase() === statusName.toLowerCase()).length;

                        const paidInvoices = countByStatus('Paid');
                        const overdueInvoices = countByStatus('Overdue');

                        const totalInvoiceValue = filteredData.reduce((sum, pi) => {
                            return sum + parseFloat(pi.grand_total || 0);
                        }, 0);

                        const summary = [
                            {
                                value: totalInvoices,
                                label: __('Total Purchase Invoice'),
                                datatype: 'Int',
                                indicator: 'Blue',
                                description: __('Total purchase invoices (excluding cancelled)')
                            },
                            {
                                value: paidInvoices,
                                label: __('Paid Purchase Invoice'),
                                datatype: 'Int',
                                indicator: 'Green',
                                description: __('Purchase invoices with Paid status')
                            },
                            {
                                value: overdueInvoices,
                                label: __('Overdue Purchase Invoices'),
                                datatype: 'Int',
                                indicator: 'Red',
                                description: __('Purchase invoices with Overdue status')
                            },
                            {
                                value: totalInvoiceValue,
                                label: __('Total Invoice Value'),
                                datatype: 'Currency',
                                indicator: 'Purple',
                                description: __('Sum of grand total for selected date range'),
                                prefix: '₹'
                            }
                        ];

                        // Update status options based on actual data
                        updateStatusOptions('purchase_invoice', purchaseInvoices, state);

                        resolve({
                            summary: summary,
                            raw_data: filteredData
                        });
                    }
                } else {
                    resolve({ summary: [], raw_data: [] });
                }
            },
            error: reject
        });
    });
}

function fetchOverviewData(filters) {
    // Calls a dedicated backend API that runs simple COUNT queries
    // against each doctype directly.  This avoids the MR → PO → PR → PI
    // join chain and guarantees accurate, independent counts.
    return new Promise((resolve, reject) => {
        frappe.call({
            method: 'prakash_steel.api.procurement_dashboard.get_overview_data',
            args: {
                from_date: filters.from_date,
                to_date: filters.to_date,
                supplier: filters.supplier || ''
            },
            callback: (r) => {
                if (r.message) {
                    const d = r.message;
                    resolve({
                        summary: [
                            {
                                value: d.total_material_requests || 0,
                                label: __('Total Material Requests'),
                                datatype: 'Int',
                                indicator: 'Blue',
                                description: __('Submitted material requests in the period')
                            },
                            {
                                value: d.total_purchase_orders || 0,
                                label: __('Total Purchase Orders'),
                                datatype: 'Int',
                                indicator: 'Green',
                                description: __('Submitted purchase orders in the period')
                            },
                            {
                                value: d.total_purchase_receipts || 0,
                                label: __('Total Purchase Receipts'),
                                datatype: 'Int',
                                indicator: 'Orange',
                                description: __('Submitted purchase receipts in the period')
                            },
                            {
                                value: d.total_purchase_invoices || 0,
                                label: __('Total Purchase Invoices'),
                                datatype: 'Int',
                                indicator: 'Purple',
                                description: __('Submitted purchase invoices in the period')
                            }
                        ],
                        raw_data: []
                    });
                } else {
                    resolve({ summary: [], raw_data: [] });
                }
            },
            error: reject
        });
    });
}

function getStatusOptions(tabId) {
    // Material Request uses a fixed set of status options; others start empty and
    // are populated dynamically from data.
    if (tabId === 'material_request') {
        return ['All', 'Pending', 'Partially Ordered', 'Partially Received'];
    }
    return [''];
}

function updateStatusOptions(tabId, data, state) {
    const statusSet = new Set();

    if (data && data.length > 0) {
    }

    if (tabId === 'material_request') {
        // For Material Request we keep a fixed set of options matching the UI:
        // All, Pending, Partially Ordered, Partially Received
        ['Pending', 'Partially Ordered', 'Partially Received'].forEach(s => statusSet.add(s));
    } else if (tabId === 'purchase_order') {
        data.forEach(row => {
            if (row.workflow_state) {
                statusSet.add(row.workflow_state);
            }
        });
    } else if (tabId === 'purchase_receipt') {
        data.forEach(row => {
            if (row.workflow_state) {
                statusSet.add(row.workflow_state);
            }
        });
    } else if (tabId === 'purchase_invoice') {
        data.forEach(row => {
            if (row.status) {
                statusSet.add(row.status);
            }
            // Also check workflow_state as fallback
            if (row.workflow_state) {
                statusSet.add(row.workflow_state);
            }
        });
    }

    const statusOptions = ['', ...Array.from(statusSet).sort()];


    // Update the dropdown options
    const statusControl = state.controls[`${tabId}_status`];
    if (statusControl) {
        statusControl.df.options = statusOptions;
        statusControl.refresh();
    }

    return statusOptions;
}

function getStatusIndicator(status) {
    const statusIndicators = {
        // Workflow states from Material Request and Purchase Order images
        'Draft': 'Blue',
        'Waiting For Review': 'Orange',
        'Waiting For Approval': 'Yellow',
        'Approved': 'Green',
        'Rejected': 'Red',
        // Standard status values
        'Submitted': 'Orange',
        'To Approve': 'Yellow',
        'To Receive': 'Teal',
        'To Bill': 'Purple',
        'Completed': 'Green',
        'Cancelled': 'Red',
        'Closed': 'Grey',
        // Additional workflow state values
        'Partially Received': 'Orange',
        'Partially Ordered': 'Yellow',
        'Pending': 'Blue',
        'Ordered': 'Green',
        'Received': 'Green',
        'Invoiced': 'Purple',
        'To Order': 'Yellow',
        'To Receive': 'Teal',
        'To Bill': 'Purple'
    };
    return statusIndicators[status] || 'Blue';
}

function getFilters(state) {
    const filters = {
        from_date: state.controls.from_date.get_value(),
        to_date: state.controls.to_date.get_value(),
        supplier: state.controls.supplier.get_value()
    };

    // Add section-specific filters for all tabs
    Object.keys(state.$tabs).forEach(tabId => {
        if (tabId !== 'overview') {
            if (tabId === 'item_wise') {
                filters.item_code = state.controls[`${tabId}_item_code`].get_value();
                filters.po_no = state.controls[`${tabId}_po_no`].get_value();
            } else {
                const statusField = getStatusFieldName(tabId);
                const idField = getIdFieldName(tabId);
                const itemField = getItemFieldName(tabId);
                filters[statusField] = state.controls[`${tabId}_status`].get_value();
                filters[idField] = state.controls[`${tabId}_id`].get_value();
                filters[itemField] = state.controls[`${tabId}_item_name`].get_value();
            }
        }
    });

    return filters;
}

function renderDashboardData(state, data) {
    // Render data for each tab
    renderTabData(state, 'overview', data.overview);
    renderTabData(state, 'material_request', data.material_request);
    renderTabData(state, 'purchase_order', data.purchase_order);
    renderTabData(state, 'purchase_receipt', data.purchase_receipt);
    renderTabData(state, 'purchase_invoice', data.purchase_invoice);
    renderTabData(state, 'item_wise', data.item_wise);
}

function renderTabData(state, tabId, tabData) {
    const $cardsContainer = state.$cards[tabId];
    const $tablesContainer = $(`#${tabId}-tables`);

    // Clear containers
    $cardsContainer.empty();
    $tablesContainer.empty();

    if (!tabData || !tabData.summary || !tabData.summary.length) {
        $cardsContainer.append(`
            <div class="no-data-message" style="text-align:center;color:#7f8c8d;padding:24px;grid-column:1/-1;">
                <i class="fa fa-info-circle" style="font-size:2rem;margin-bottom:12px;"></i>
                <div>${__('No data available for selected criteria')}</div>
            </div>
        `);
        return;
    }

    // Render cards
    tabData.summary.forEach((card) => {
        const $card = createCard(card);
        $cardsContainer.append($card);
    });

    // Render detailed tables
    if (tabData.raw_data && tabData.raw_data.length > 0) {
        renderDetailedTables($tablesContainer, tabId, tabData.raw_data);
    }
}

function renderDetailedTables($container, tabId, rawData) {
    if (tabId === 'material_request') {
        renderMaterialRequestTable($container, rawData);
    } else if (tabId === 'purchase_order') {
        renderPurchaseOrderTable($container, rawData);
    } else if (tabId === 'purchase_receipt') {
        renderPurchaseReceiptTable($container, rawData);
    } else if (tabId === 'purchase_invoice') {
        renderPurchaseInvoiceTable($container, rawData);
    } else if (tabId === 'item_wise') {
        renderItemWiseTable($container, rawData);
    } else if (tabId === 'overview') {
        renderOverviewTables($container, rawData);
    }
}

function renderMaterialRequestTable($container, data) {
    if (!data || data.length === 0) {
        $container.append(`
            <div class="no-data-message">
                <div>${__('No material request data available for selected criteria')}</div>
            </div>
        `);
        return;
    }

    const $table = $(`
        <div class="data-table" style="width: 100%; margin-bottom: 30px;">
            <h4>${__('Material Requests')}</h4>
            <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 6px; overflow: hidden; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                <thead>
                    <tr>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Material Request')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Date')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Status')}</th>
                    </tr>
                </thead>
                <tbody>
                </tbody>
            </table>
        </div>
    `);

    const $tbody = $table.find('tbody');

    data.forEach((row) => {
        const $tr = $(`
            <tr style="border-bottom: 1px solid #e9ecef;">
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;"><a href="/app/material-request/${row.name}" class="link-cell" style="color: #007bff; text-decoration: none; cursor: pointer;">${row.name}</a></td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${frappe.format(row.transaction_date, { fieldtype: 'Date' })}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;"><span class="badge badge-${getStatusClass(row.status)}">${row.status || 'Draft'}</span></td>
            </tr>
        `);
        $tbody.append($tr);
    });

    $container.append($table);
}

function renderPurchaseOrderTable($container, data) {
    if (!data || data.length === 0) {
        $container.append(`
            <div class="no-data-message">
                <div>${__('No purchase order data available for selected criteria')}</div>
            </div>
        `);
        return;
    }

    const $table = $(`
        <div class="data-table" style="width: 100%; margin-bottom: 30px;">
            <h4>${__('Purchase Orders')}</h4>
            <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 6px; overflow: hidden; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                <thead>
                    <tr>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Purchase Order')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Date')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Status')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Supplier')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: right; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Grand Total')}</th>
                    </tr>
                </thead>
                <tbody>
                </tbody>
            </table>
        </div>
    `);

    const $tbody = $table.find('tbody');

    data.forEach((row) => {
        const rowColor = getPurchaseOrderRowColor(row.workflow_state, row.status);
        const $tr = $(`
            <tr style="border-bottom: 1px solid #e9ecef; background:${rowColor};">
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;"><a href="/app/purchase-order/${row.name}" class="link-cell" style="color: #007bff; text-decoration: none; cursor: pointer;">${row.name}</a></td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${frappe.format(row.transaction_date, { fieldtype: 'Date' })}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;"><span class="badge badge-${getStatusClass(row.workflow_state)}">${row.workflow_state || 'Draft'}</span></td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${row.supplier || ''}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: right;">${frappe.format(row.grand_total || 0, { fieldtype: 'Currency' })}</td>
            </tr>
        `);
        $tbody.append($tr);
    });

    $container.append($table);
}

function renderPurchaseReceiptTable($container, data) {
    if (!data || data.length === 0) {
        $container.append(`
            <div class="no-data-message">
                <div>${__('No purchase receipt data available for selected criteria')}</div>
            </div>
        `);
        return;
    }

    const $table = $(`
        <div class="data-table" style="width: 100%; margin-bottom: 30px;">
            <h4>${__('Purchase Receipts')}</h4>
            <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 6px; overflow: hidden; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                <thead>
                    <tr>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Purchase Receipt')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Date')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Status')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Supplier')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: right; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Grand Total')}</th>
                    </tr>
                </thead>
                <tbody>
                </tbody>
            </table>
        </div>
    `);

    const $tbody = $table.find('tbody');

    data.forEach((row) => {
        const $tr = $(`
            <tr style="border-bottom: 1px solid #e9ecef;">
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;"><a href="/app/purchase-receipt/${row.name}" class="link-cell" style="color: #007bff; text-decoration: none; cursor: pointer;">${row.name}</a></td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${frappe.format(row.posting_date, { fieldtype: 'Date' })}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;"><span class="badge badge-${getStatusClass(row.status)}">${row.status || 'Draft'}</span></td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${row.supplier || ''}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: right;">${frappe.format(row.grand_total || 0, { fieldtype: 'Currency' })}</td>
            </tr>
        `);
        $tbody.append($tr);
    });

    $container.append($table);
}

function renderPurchaseInvoiceTable($container, data) {
    if (!data || data.length === 0) {
        $container.append(`
            <div class="no-data-message">
                <div>${__('No purchase invoice data available for selected criteria')}</div>
            </div>
        `);
        return;
    }

    const $table = $(`
        <div class="data-table" style="width: 100%; margin-bottom: 30px;">
            <h4>${__('Purchase Invoices')}</h4>
            <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 6px; overflow: hidden; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                <thead>
                    <tr>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Purchase Invoice')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Date')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Due Date')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Status')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Supplier')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: right; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Grand Total')}</th>
                    </tr>
                </thead>
                <tbody>
                </tbody>
            </table>
        </div>
    `);

    const $tbody = $table.find('tbody');

    data.forEach((row) => {
        const $tr = $(`
            <tr style="border-bottom: 1px solid #e9ecef;">
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;"><a href="/app/purchase-invoice/${row.name}" class="link-cell" style="color: #007bff; text-decoration: none; cursor: pointer;">${row.name}</a></td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${frappe.format(row.posting_date, { fieldtype: 'Date' })}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${frappe.format(row.due_date, { fieldtype: 'Date' })}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;"><span class="badge badge-${getStatusClass(row.workflow_state)}">${row.workflow_state || 'Draft'}</span></td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${row.supplier || ''}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: right;">${frappe.format(row.grand_total || 0, { fieldtype: 'Currency' })}</td>
            </tr>
        `);
        $tbody.append($tr);
    });

    $container.append($table);
}

function renderOverviewTables($container, overviewData) {
    // For overview, we'll show a summary of all procurement data
    $container.append(`
        <div class="overview-summary" style="background:#f8f9fa;padding:20px;border-radius:8px;margin-bottom:20px;">
            <h4>${__('Procurement Summary')}</h4>
            <p>${__('This overview provides a high-level view of all procurement activities across Material Requests, Purchase Orders, Purchase Receipts, and Purchase Invoices.')}</p>
            <p>${__('Use the individual tabs to view detailed information and apply specific filters for each procurement stage.')}</p>
        </div>
    `);
}

function getStatusClass(status) {
    const statusClasses = {
        'Approved': 'success',
        'Rejected': 'danger',
        'Draft': 'secondary',
        'Submitted': 'info',
        'To Approve': 'warning',
        'To Receive': 'primary',
        'To Bill': 'info',
        'Completed': 'success',
        'Cancelled': 'danger',
        'Closed': 'dark'
    };
    return statusClasses[status] || 'secondary';
}

function getPurchaseOrderRowColor(workflowState, status) {
    // Default no background
    const green = '#eaf7ec';
    const orange = '#fff4e5';
    const red = '#fdecea';

    const ws = (workflowState || '').toLowerCase();
    const st = (status || '').toLowerCase();

    // Rules provided:
    // if status=to bill and workflow_state = approaved -> green
    if (st === 'to bill' && ws === 'approved') return green;

    // if status=to receive and bill and workflow_state = approaved -> orange
    if (st === 'to receive and bill' && ws === 'approved') return orange;

    // if status = to received and bill and workflow_state = waiting for approval -> red
    // Allow minor spelling variants (received/receive)
    if ((st === 'to received and bill' || st === 'to receive and bill') && ws === 'waiting for approval') return red;

    return 'transparent';
}

function createCard(card) {
    const indicator = (card.indicator || 'blue').toString().toLowerCase();

    // Format value based on datatype and precision
    let value;
    if (card.datatype === 'Int') {
        value = format_number(card.value || 0, null, 0);
    } else if (card.datatype === 'Float') {
        const precision = card.precision !== undefined ? card.precision : 2;
        value = format_number(card.value || 0, null, precision);
    } else if (card.datatype === 'Currency') {
        value = format_number(card.value || 0, null, 2);
    } else {
        value = format_number(card.value || 0);
    }

    // Add prefix if specified
    if (card.prefix) {
        value = card.prefix + value;
    }

    // Determine font size based on value length for currency values
    let fontSize = '2.4rem';
    if (card.datatype === 'Currency' && value.length > 12) {
        fontSize = '1.8rem';
    } else if (card.datatype === 'Currency' && value.length > 8) {
        fontSize = '2.1rem';
    }

    const description = card.description ? `<div class="card-description" style="font-size:0.85rem;color:#95a5a6;margin-top:4px;">${frappe.utils.escape_html(card.description)}</div>` : '';

    return $(`
        <div class="number-card" style="background:#fff;border-radius:12px;padding:24px;box-shadow:0 4px 12px rgba(0,0,0,0.1);position:relative;overflow:hidden;transition:transform 0.2s ease,box-shadow 0.2s ease;">
            <div class="card-indicator" style="position:absolute;top:0;left:0;right:0;height:4px;background:${getIndicatorColor(indicator)}"></div>
            <div class="card-content" style="text-align:center;">
                <div class="card-value" style="font-size:${fontSize};font-weight:700;color:#2c3e50;margin-bottom:8px;word-wrap:break-word;overflow-wrap:break-word;line-height:1.1;">${value}</div>
                <div class="card-label" style="font-size:1rem;color:#7f8c8d;font-weight:500;">${frappe.utils.escape_html(card.label || '')}</div>
                ${description}
            </div>
        </div>
    `);
}

function getIndicatorColor(indicator) {
    const colors = {
        'green': 'linear-gradient(90deg,#27ae60,#229954)',
        'black': 'linear-gradient(90deg,#34495e,#2c3e50)',
        'red': 'linear-gradient(90deg,#e74c3c,#c0392b)',
        'orange': 'linear-gradient(90deg,#f39c12,#e67e22)',
        'purple': 'linear-gradient(90deg,#9b59b6,#8e44ad)',
        'teal': 'linear-gradient(90deg,#1abc9c,#16a085)',
        'brown': 'linear-gradient(90deg,#795548,#6d4c41)',
        'blue': 'linear-gradient(90deg,#3498db,#2980b9)'
    };
    return colors[indicator] || colors.blue;
}

function showError(state, message) {
    // Show error in current tab
    const $cardsContainer = state.$cards[state.currentTab];
    $cardsContainer.empty();
    $cardsContainer.append(`
        <div class="alert alert-danger" style="background:#f8d7da;border:1px solid #f5c6cb;color:#721c24;padding:16px;border-radius:8px;grid-column:1/-1;">
            <i class="fa fa-exclamation-triangle" style="margin-right:8px;"></i>
            ${frappe.utils.escape_html(message)}
        </div>
    `);
}

