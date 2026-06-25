// Copyright (c) 2025, beetashoke chakraborty and contributors
// For license information, please see license.txt

// Ensure the page is registered before adding event handlers
if (!frappe.pages['sales-summary-dashboard']) {
    frappe.pages['sales-summary-dashboard'] = {};
}

frappe.pages['sales-summary-dashboard'].on_page_load = function (wrapper) {

    // Build page shell
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Sales Summary Dashboard'),
        single_column: true,
    });

    // Hide Frappe's default page head/title - SCOPED to this page container only
    $(page.page_container).find('.page-head').hide();

    // Hide title elements within this page container only (not globally)
    setTimeout(function () {
        // Only hide elements within this page's container
        $(page.page_container).find('.page-title, .page-header h1, .page-title-wrapper').hide();
        $(page.page_container).find('h1, .page-title, .title').not('.dashboard-title').hide();
        if (page.page_title) {
            $(page.page_title).hide();
        }
        // Hide breadcrumbs within this page container
        $(page.page_container).find('.page-header, .page-breadcrumbs').hide();
    }, 100);

    // Also check after a longer delay in case elements load later - SCOPED
    setTimeout(function () {
        $(page.page_container).find('.page-title, .page-header h1, .page-title-wrapper, .page-head').hide();
        $(page.page_container).find('h1').not('.dashboard-title').hide();
    }, 500);

    // Initialize dashboard state
    const state = {
        page,
        wrapper,
        filters: {},
        $cards: null,
        $tabs: null,
        controls: {},
        currentTab: 'overview'
    };

    // Initialize dashboard components
    initializeDashboard(state);
};

frappe.pages['sales-summary-dashboard'].on_page_show = function () {
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

    // Set initial refresh button visibility (show for overview tab by default)
    if (state.currentTab === 'overview') {
        state.controls.refreshBtn.show();
    } else {
        state.controls.refreshBtn.hide();
    }

    // Load initial data
    refreshDashboard(state);
}

function createFilterBar(state) {
    // Main filter container
    const $filterBar = $('<div class="sales-filters" style="display:flex;gap:12px;align-items:end;flex-wrap:wrap;margin-bottom:16px;justify-content:space-between;background:#f8f9fa;padding:16px;border-radius:8px;"></div>');

    // Filter controls container
    const $filterControls = $('<div style="display:flex;gap:12px;align-items:end;flex-wrap:wrap;"></div>');

    // Individual filter wrappers
    const $fromWrap = $('<div style="min-width:200px;"></div>');
    const $toWrap = $('<div style="min-width:200px;"></div>');
    const $customerWrap = $('<div style="min-width:220px;"></div>');
    const $btnWrap = $('<div style="display:flex;align-items:end;gap:8px;"></div>');

    // Assemble filter controls
    $filterControls.append($fromWrap).append($toWrap).append($customerWrap);
    $filterBar.append($filterControls).append($btnWrap);
    $(state.page.main).append($filterBar);

    // Create filter controls
    createFilterControls(state, $fromWrap, $toWrap, $customerWrap, $btnWrap);
}

function createFilterControls(state, $fromWrap, $toWrap, $customerWrap, $btnWrap) {
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

    // Customer control
    state.controls.customer = frappe.ui.form.make_control({
        parent: $customerWrap.get(0),
        df: {
            fieldtype: 'Link',
            label: __('Customer'),
            fieldname: 'customer',
            options: 'Customer',
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
        $(state.controls.customer.$input).css({
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
    const $tabContainer = $('<div class="sales-tabs" style="margin-bottom:20px;"></div>');
    const $tabList = $('<ul class="nav nav-tabs" role="tablist" style="border-bottom:2px solid #dee2e6;"></ul>');

    // Tab content container
    const $tabContent = $('<div class="tab-content" style="margin-top:20px;"></div>');

    // Create tabs
    const tabs = [
        { id: 'overview', label: __('Overview'), icon: 'fa fa-tachometer' },
        { id: 'sales_order', label: __('Sales Order'), icon: 'fa fa-shopping-cart' },
        { id: 'sales_invoice', label: __('Sales Invoice'), icon: 'fa fa-file-invoice' }
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
    const inner = `
        <div id="${tabId}-status-filter" style="min-width:350px;width:350px;flex-shrink:0;"></div>
        <div id="${tabId}-id-filter" style="min-width:180px;"></div>
        <div id="${tabId}-item-filter" style="min-width:200px;"></div>
        <div id="${tabId}-refresh-btn" style="min-width:120px;display:flex;flex-direction:column;justify-content:end;"></div>
    `;

    const $sectionFilters = $(`
        <div class="section-filters" style="background:#f1f3f4;padding:12px;border-radius:6px;margin-bottom:16px;">
            <div style="display:flex;gap:12px;align-items:end;flex-wrap:wrap;overflow:visible;">
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
    // Status filter
    const statusField = getStatusFieldName(tabId);
    const statusOptions = getStatusOptions(tabId);
    state.controls[`${tabId}_status`] = frappe.ui.form.make_control({
        parent: $(`#${tabId}-status-filter`).get(0),
        df: {
            fieldtype: 'Select',
            label: __('Status'),
            fieldname: `${tabId}_status`,
            options: statusOptions,
            reqd: 0,
        },
        render_input: true,
    });

    // Add CSS to ensure proper width and text display
    setTimeout(() => {
        const $statusControl = $(`#${tabId}-status-filter`);
        $statusControl.find('select').css({
            'width': '100%',
            'min-width': '260px',
            'max-width': 'none',
            'padding': '8px 12px',
            'height': '36px',
            'line-height': '1.4',
            'text-overflow': 'ellipsis',
            'white-space': 'nowrap',
            'overflow': 'hidden'
        });
        $statusControl.find('.form-control').css({
            'width': '100%',
            'min-width': '260px',
            'max-width': 'none',
            'padding': '8px 12px',
            'height': '36px',
            'line-height': '1.4'
        });
        // Also ensure the parent container doesn't constrain the width
        $statusControl.css({
            'width': '280px',
            'min-width': '280px',
            'max-width': 'none',
            'flex-shrink': '0'
        });
    }, 100);

    // ID filter - use Autocomplete so we can feed it suggestions
    const idField = getIdFieldName(tabId);
    state.controls[`${tabId}_id`] = frappe.ui.form.make_control({
        parent: $(`#${tabId}-id-filter`).get(0),
        df: {
            fieldtype: 'Autocomplete',
            label: __('ID'),
            fieldname: `${tabId}_id`,
            reqd: 0,
            options: ''
        },
        render_input: true,
    });

    // Item name filter
    state.controls[`${tabId}_item_name`] = frappe.ui.form.make_control({
        parent: $(`#${tabId}-item-filter`).get(0),
        df: {
            fieldtype: 'Link',
            options: 'Item',
            label: __('Item'),
            fieldname: `${tabId}_item_name`,
            reqd: 0
        },
        render_input: true,
    });

    // Refresh button
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
        const $formControl = $(`#${tabId}-refresh-btn .form-control`);
        const $button = $(`#${tabId}-refresh-btn button`);
        const $input = $(`#${tabId}-refresh-btn input`);

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
}

function getStatusFieldName(tabId) {
    const statusFields = {
        'sales_order': 'so_status',
        'sales_invoice': 'si_status'
    };
    return statusFields[tabId] || 'status';
}

function getIdFieldName(tabId) {
    const idFields = {
        'sales_order': 'so_id',
        'sales_invoice': 'si_id'
    };
    return idFields[tabId] || 'id';
}

function getItemFieldName(tabId) {
    const itemFields = {
        'sales_order': 'so_item_name',
        'sales_invoice': 'si_item_name'
    };
    return itemFields[tabId] || 'item_name';
}

function getSectionTitle(tabId) {
    const titles = {
        'overview': __('Sales Overview'),
        'sales_order': __('Sales Order Details'),
        'sales_invoice': __('Sales Invoice Details')
    };
    return titles[tabId] || __('Details');
}

function setDefaultFilters(state) {
    // Set default date range
    state.controls.from_date.set_value(frappe.datetime.month_start());
    state.controls.to_date.set_value(frappe.datetime.month_end());
}

function bindEventHandlers(state) {
    // Main filter change events
    $(state.controls.from_date.$input).on('change', () => refreshDashboard(state));
    $(state.controls.to_date.$input).on('change', () => refreshDashboard(state));
    $(state.controls.customer.$input).on('change', () => refreshDashboard(state));

    // Section filter change events
    Object.keys(state.$tabs).forEach(tabId => {
        if (tabId !== 'overview') {
            $(state.controls[`${tabId}_status`].$input).on('change', () => refreshDashboard(state));
            $(state.controls[`${tabId}_id`].$input).on('change', () => refreshDashboard(state));
            $(state.controls[`${tabId}_item_name`].$input).on('change', () => refreshDashboard(state));
            $(state.controls[`${tabId}_refresh`].$input).on('click', () => refreshDashboard(state));
        }
    });

    // Button events
    state.controls.refreshBtn.on('click', () => refreshDashboard(state));

    // Tab change events
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

    // Check if date controls exist and have values
    const fromDate = state.controls.from_date ? state.controls.from_date.get_value() : null;
    const toDate = state.controls.to_date ? state.controls.to_date.get_value() : null;

    if (!fromDate || !toDate) {
        showError(state, __('Please select both From Date and To Date'));
        return;
    }

    // Show loading state
    state.page.set_indicator(__('Loading dashboard data...'), 'blue');

    // Fetch data for all sections
    Promise.all([
        fetchSalesOverviewData(filters),
        fetchSalesOrderData(filters, state),
        fetchSalesInvoiceData(filters, state)
    ]).then(([overviewData, salesOrderData, salesInvoiceData]) => {
        state.page.clear_indicator();

        // Render all sections
        renderDashboardData(state, {
            overview: overviewData,
            sales_order: salesOrderData,
            sales_invoice: salesInvoiceData
        });
    }).catch((error) => {
        state.page.clear_indicator();
        console.error('Dashboard refresh error:', error);
        showError(state, __('An error occurred while loading data'));
    });
}

function fetchSalesOverviewData(filters) {
    return new Promise((resolve, reject) => {
        // Get data from both reports
        Promise.all([
            fetchSalesOrderData(filters, {}),
            fetchSalesInvoiceData(filters, {})
        ]).then(([salesOrderData, salesInvoiceData]) => {
            // Consider only "submitted" documents for overview metrics
            // i.e. exclude Draft and Cancelled records from both SO & SI datasets
            const filteredSalesOrders = (salesOrderData.raw_data || []).filter(so =>
                (so.status || '').toLowerCase() !== 'draft' &&
                (so.status || '').toLowerCase() !== 'cancelled'
            );

            const filteredSalesInvoices = (salesInvoiceData.raw_data || []).filter(si =>
                (si.status || '').toLowerCase() !== 'draft' &&
                (si.status || '').toLowerCase() !== 'cancelled'
            );

            // Calculate totals - count unique documents, not line items
            const uniqueOrders = new Set(filteredSalesOrders.map(so => so.sales_order));
            const uniqueInvoices = new Set(filteredSalesInvoices.map(si => si.sales_invoice));
            const totalOrders = uniqueOrders.size;
            const totalInvoices = uniqueInvoices.size;

            // Calculate total values - sum unique document totals
            const orderTotals = {};
            filteredSalesOrders.forEach(so => {
                if (so.sales_order && !orderTotals[so.sales_order]) {
                    orderTotals[so.sales_order] = parseFloat(so.grand_total) || 0;
                }
            });
            const totalOrderValue = Object.values(orderTotals).reduce((sum, total) => sum + total, 0);

            const invoiceTotals = {};
            filteredSalesInvoices.forEach(si => {
                if (si.sales_invoice && !invoiceTotals[si.sales_invoice]) {
                    invoiceTotals[si.sales_invoice] = parseFloat(si.grand_total) || 0;
                }
            });
            const totalInvoiceValue = Object.values(invoiceTotals).reduce((sum, total) => sum + total, 0);

            // Create summary cards
            const summary = [
                {
                    value: totalOrders,
                    label: __('Total Sales Orders (Submitted)'),
                    datatype: 'Int',
                    indicator: 'Blue',
                    description: __('Total submitted sales orders in the period (excluding Draft and Cancelled)')
                },
                {
                    value: totalInvoices,
                    label: __('Total Sales Invoices (Submitted)'),
                    datatype: 'Int',
                    indicator: 'Green',
                    description: __('Total submitted sales invoices in the period (excluding Draft and Cancelled)')
                },
                {
                    value: totalOrderValue,
                    label: __('Total Order Value (Submitted)'),
                    datatype: 'Currency',
                    indicator: 'Orange',
                    description: __('Total value of submitted sales orders (excluding Draft and Cancelled)'),
                    prefix: '₹'
                },
                {
                    value: totalInvoiceValue,
                    label: __('Total Invoice Value (Submitted)'),
                    datatype: 'Currency',
                    indicator: 'Purple',
                    description: __('Total value of submitted sales invoices (excluding Draft and Cancelled)'),
                    prefix: '₹'
                }
            ];

            resolve({ summary: summary, raw_data: [] });
        }).catch(reject);
    });
}

function fetchSalesOrderData(filters, state) {
    return new Promise((resolve, reject) => {
        frappe.call({
            method: 'frappe.desk.query_report.run',
            args: {
                report_name: 'Sales Order Tracker',
                filters: {
                    from_date: filters.from_date,
                    to_date: filters.to_date,
                    customer: filters.customer || '',
                    status: filters.so_status || '',
                    item_code: filters.so_item_name || ''
                },
                ignore_prepared_report: 1,
            },
            callback: (r) => {
                if (r.message && r.message.result) {
                    let rawData = r.message.result;

                    // Filter by ID if specified
                    if (filters.so_id) {
                        rawData = rawData.filter(so => so.sales_order.toLowerCase().includes(filters.so_id.toLowerCase()));
                    }

                    // Create status summary - count unique documents, not line items
                    const statusCounts = {};
                    const documentTotals = {};

                    // Group by unique sales order and count by status
                    rawData.forEach(so => {
                        const salesOrder = so.sales_order;
                        const status = so.status || 'Draft';

                        if (salesOrder) {
                            // Count unique documents by status
                            if (!statusCounts[status]) {
                                statusCounts[status] = new Set();
                            }
                            statusCounts[status].add(salesOrder);

                            // Store unique document totals
                            if (!documentTotals[salesOrder]) {
                                documentTotals[salesOrder] = parseFloat(so.grand_total) || 0;
                            }
                        }
                    });

                    // Convert Sets to counts
                    const summary = Object.keys(statusCounts).map(status => ({
                        value: statusCounts[status].size,
                        label: `${status} Sales Orders`,
                        datatype: 'Int',
                        indicator: getStatusIndicator(status),
                        description: `Sales orders with ${status} status`
                    }));

                    // Add total value card - sum unique document totals
                    const totalValue = Object.values(documentTotals).reduce((sum, total) => sum + total, 0);
                    if (totalValue > 0) {
                        summary.push({
                            value: totalValue,
                            label: __('Total Order Value'),
                            datatype: 'Currency',
                            indicator: 'Orange',
                            description: __('Sum of grand total for selected date range'),
                            prefix: '₹'
                        });
                    }

                    // Update status options based on actual data
                    updateStatusOptions('sales_order', rawData, state);

                    // Update ID autocomplete options based on actual data
                    updateIdOptions('sales_order', rawData, state);

                    resolve({ summary: summary, raw_data: rawData });
                } else {
                    resolve({ summary: [], raw_data: [] });
                }
            },
            error: reject
        });
    });
}

function fetchSalesInvoiceData(filters, state) {
    return new Promise((resolve, reject) => {
        frappe.call({
            method: 'frappe.desk.query_report.run',
            args: {
                report_name: 'Sales Invoice Tracker',
                filters: {
                    from_date: filters.from_date,
                    to_date: filters.to_date,
                    customer: filters.customer || '',
                    status: filters.si_status || '',
                    item_code: filters.si_item_name || ''
                },
                ignore_prepared_report: 1,
            },
            callback: (r) => {
                if (r.message && r.message.result) {
                    let rawData = r.message.result;

                    // Filter by ID if specified
                    if (filters.si_id) {
                        rawData = rawData.filter(si => si.sales_invoice.toLowerCase().includes(filters.si_id.toLowerCase()));
                    }

                    // Create status summary - count unique documents, not line items
                    const statusCounts = {};
                    const documentTotals = {};

                    // Group by unique sales invoice and count by status
                    rawData.forEach(si => {
                        const salesInvoice = si.sales_invoice;
                        const status = si.status || 'Draft';

                        if (salesInvoice) {
                            // Count unique documents by status
                            if (!statusCounts[status]) {
                                statusCounts[status] = new Set();
                            }
                            statusCounts[status].add(salesInvoice);

                            // Store unique document totals
                            if (!documentTotals[salesInvoice]) {
                                documentTotals[salesInvoice] = parseFloat(si.grand_total) || 0;
                            }
                        }
                    });

                    // Convert Sets to counts
                    const summary = Object.keys(statusCounts).map(status => ({
                        value: statusCounts[status].size,
                        label: `${status} Sales Invoices`,
                        datatype: 'Int',
                        indicator: getStatusIndicator(status),
                        description: `Sales invoices with ${status} status`
                    }));

                    // Add total value card - sum unique document totals
                    const totalValue = Object.values(documentTotals).reduce((sum, total) => sum + total, 0);
                    if (totalValue > 0) {
                        summary.push({
                            value: totalValue,
                            label: __('Total Invoice Value'),
                            datatype: 'Currency',
                            indicator: 'Purple',
                            description: __('Sum of grand total for selected date range'),
                            prefix: '₹'
                        });
                    }

                    // Update status options based on actual data
                    updateStatusOptions('sales_invoice', rawData, state);

                    // Update ID autocomplete options based on actual data
                    updateIdOptions('sales_invoice', rawData, state);

                    resolve({ summary: summary, raw_data: rawData });
                } else {
                    resolve({ summary: [], raw_data: [] });
                }
            },
            error: reject
        });
    });
}

function getStatusOptions(tabId) {
    // Start empty; options will be updated dynamically from data
    return [''];
}

function updateStatusOptions(tabId, data, state) {
    const statusSet = new Set();

    if (data && data.length > 0) {
        data.forEach(row => {
            if (row.status) {
                statusSet.add(row.status);
            }
            if (row.workflow_state) {
                statusSet.add(row.workflow_state);
            }
        });
    }

    const statusOptions = ['', ...Array.from(statusSet).sort()];

    // Update the dropdown options - check if state and controls exist
    if (state && state.controls) {
        const statusControl = state.controls[`${tabId}_status`];
        if (statusControl) {
            statusControl.df.options = statusOptions;
            statusControl.refresh();
        }
    }

    return statusOptions;
}

function updateIdOptions(tabId, data, state) {
    const idFieldName = getIdFieldName(tabId);
    const idSet = new Set();

    if (data && data.length > 0) {
        data.forEach(row => {
            if (row.sales_order && tabId === 'sales_order') {
                idSet.add(row.sales_order);
            }
            if (row.sales_invoice && tabId === 'sales_invoice') {
                idSet.add(row.sales_invoice);
            }
            // Fallback: use generic id field name if present
            if (row[idFieldName]) {
                idSet.add(row[idFieldName]);
            }
        });
    }

    const idOptions = Array.from(idSet).sort();

    if (state && state.controls) {
        const idControl = state.controls[`${tabId}_id`];
        if (idControl) {
            // Frappe Autocomplete works best with an array of options
            idControl.df.options = idOptions;

            // If the control exposes set_data (v13+), use it
            if (typeof idControl.set_data === 'function') {
                idControl.set_data(idOptions);
            }

            // Refresh the input UI to bind the new dataset
            if (typeof idControl.refresh_input === 'function') {
                idControl.refresh_input();
            } else if (typeof idControl.refresh === 'function') {
                idControl.refresh();
            }
        }
    }

    return idOptions;
}

function getStatusIndicator(status) {
    const statusIndicators = {
        'Draft': 'Blue',
        'Submitted': 'Orange',
        'To Deliver': 'Yellow',
        'To Bill': 'Purple',
        'Completed': 'Green',
        'Cancelled': 'Red',
        'Closed': 'Grey',
        'Overdue': 'Red',
        'Unpaid': 'Orange',
        'Paid': 'Green',
        'Partially Paid': 'Yellow'
    };
    return statusIndicators[status] || 'Blue';
}

function getFilters(state) {
    const filters = {
        from_date: state.controls.from_date ? state.controls.from_date.get_value() : null,
        to_date: state.controls.to_date ? state.controls.to_date.get_value() : null,
        customer: state.controls.customer ? state.controls.customer.get_value() : null
    };

    // Add section-specific filters for all tabs
    if (state.$tabs) {
        Object.keys(state.$tabs).forEach(tabId => {
            if (tabId !== 'overview') {
                const statusField = getStatusFieldName(tabId);
                const idField = getIdFieldName(tabId);
                const itemField = getItemFieldName(tabId);

                if (state.controls[`${tabId}_status`]) {
                    filters[statusField] = state.controls[`${tabId}_status`].get_value();
                }
                if (state.controls[`${tabId}_id`]) {
                    filters[idField] = state.controls[`${tabId}_id`].get_value();
                }
                if (state.controls[`${tabId}_item_name`]) {
                    filters[itemField] = state.controls[`${tabId}_item_name`].get_value();
                }
            }
        });
    }

    return filters;
}

function renderDashboardData(state, data) {
    // Render data for each tab
    renderTabData(state, 'overview', data.overview);
    renderTabData(state, 'sales_order', data.sales_order);
    renderTabData(state, 'sales_invoice', data.sales_invoice);
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
    if (tabId === 'sales_order') {
        renderSalesOrderTable($container, rawData);
    } else if (tabId === 'sales_invoice') {
        renderSalesInvoiceTable($container, rawData);
    } else if (tabId === 'overview') {
        renderOverviewTables($container, rawData);
    }
}

function renderSalesOrderTable($container, data) {
    if (!data || data.length === 0) {
        $container.append(`
            <div class="no-data-message">
                <div>${__('No sales order data available for selected criteria')}</div>
            </div>
        `);
        return;
    }

    // Deduplicate to show only unique Sales Orders
    const uniqueOrders = {};
    data.forEach((row) => {
        if (row.sales_order && !uniqueOrders[row.sales_order]) {
            uniqueOrders[row.sales_order] = row;
        }
    });
    const uniqueData = Object.values(uniqueOrders);

    const $table = $(`
        <div class="data-table" style="width: 100%; margin-bottom: 30px;">
            <h4>${__('Sales Orders')}</h4>
            <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 6px; overflow: hidden; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                <thead>
                    <tr>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Sales Order')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Date')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Status')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Customer')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: right; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Grand Total')}</th>
                    </tr>
                </thead>
                <tbody>
                </tbody>
            </table>
        </div>
    `);

    const $tbody = $table.find('tbody');

    uniqueData.forEach((row) => {
        const $tr = $(`
            <tr style="border-bottom: 1px solid #e9ecef;">
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;"><a href="/app/sales-order/${row.sales_order}" class="link-cell" style="color: #007bff; text-decoration: none; cursor: pointer;">${row.sales_order}</a></td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${frappe.format(row.transaction_date, { fieldtype: 'Date' })}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;"><span class="badge badge-${getStatusClass(row.status)}">${row.status || 'Draft'}</span></td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${row.customer || ''}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: right;">${frappe.format(row.grand_total || 0, { fieldtype: 'Currency' })}</td>
            </tr>
        `);
        $tbody.append($tr);
    });

    $container.append($table);
}

function renderSalesInvoiceTable($container, data) {
    if (!data || data.length === 0) {
        $container.append(`
            <div class="no-data-message">
                <div>${__('No sales invoice data available for selected criteria')}</div>
            </div>
        `);
        return;
    }

    // Deduplicate to show only unique Sales Invoices
    const uniqueInvoices = {};
    data.forEach((row) => {
        if (row.sales_invoice && !uniqueInvoices[row.sales_invoice]) {
            uniqueInvoices[row.sales_invoice] = row;
        }
    });
    const uniqueData = Object.values(uniqueInvoices);

    const $table = $(`
        <div class="data-table" style="width: 100%; margin-bottom: 30px;">
            <h4>${__('Sales Invoices')}</h4>
            <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 6px; overflow: hidden; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                <thead>
                    <tr>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Sales Invoice')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Date')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Due Date')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Status')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Customer')}</th>
                        <th style="background: #f8f9fa; padding: 12px; text-align: right; font-weight: 600; color: #495057; border-bottom: 2px solid #dee2e6;">${__('Grand Total')}</th>
                    </tr>
                </thead>
                <tbody>
                </tbody>
            </table>
        </div>
    `);

    const $tbody = $table.find('tbody');

    uniqueData.forEach((row) => {
        const $tr = $(`
            <tr style="border-bottom: 1px solid #e9ecef;">
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;"><a href="/app/sales-invoice/${row.sales_invoice}" class="link-cell" style="color: #007bff; text-decoration: none; cursor: pointer;">${row.sales_invoice}</a></td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${frappe.format(row.posting_date, { fieldtype: 'Date' })}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${frappe.format(row.due_date, { fieldtype: 'Date' })}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;"><span class="badge badge-${getStatusClass(row.status)}">${row.status || 'Draft'}</span></td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: left;">${row.customer || ''}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; color: #495057; text-align: right;">${frappe.format(row.grand_total || 0, { fieldtype: 'Currency' })}</td>
            </tr>
        `);
        $tbody.append($tr);
    });

    $container.append($table);
}

function renderOverviewTables($container, overviewData) {
    // For overview, we'll show a summary of all sales data
    $container.append(`
        <div class="overview-summary" style="background:#f8f9fa;padding:20px;border-radius:8px;margin-bottom:20px;">
            <h4>${__('Sales Summary')}</h4>
            <p>${__('This overview provides a high-level view of all sales activities across Sales Orders and Sales Invoices.')}</p>
            <p>${__('Use the individual tabs to view detailed information and apply specific filters for each sales stage.')}</p>
        </div>
    `);
}

function getStatusClass(status) {
    const statusClasses = {
        'Draft': 'secondary',
        'Submitted': 'info',
        'To Deliver': 'warning',
        'To Bill': 'primary',
        'Completed': 'success',
        'Cancelled': 'danger',
        'Closed': 'dark',
        'Overdue': 'danger',
        'Unpaid': 'warning',
        'Paid': 'success',
        'Partially Paid': 'info'
    };
    return statusClasses[status] || 'secondary';
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
