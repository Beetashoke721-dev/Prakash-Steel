// Copyright (c) 2025, Prakash Steel and contributors
// For license information, please see license.txt

// ================================================================
// Production Dashboard – Rolled, Bright, Bend Weight & Coal Consumption Tabs
// ================================================================

if (!frappe.pages['production-dashboard']) {
    frappe.pages['production-dashboard'] = {};
}

// ────────────────────────────────────────────────────────────────
// Financial Year helpers (April → March) — used by the Monthly
// Production With Coal Consumption tab, which defaults to the
// current financial year instead of the shared date filters.
// ────────────────────────────────────────────────────────────────
function getCurrentFinancialYearStart() {
    const d = new Date();
    const year = d.getFullYear();
    const month = d.getMonth() + 1; // 1-12
    return month >= 4 ? year : year - 1;
}

function financialYearLabel(startYear) {
    return `${startYear}-${String(startYear + 1).slice(-2)}`;
}

function financialYearRange(startYear) {
    return {
        from_date: `${startYear}-04-01`,
        to_date: `${startYear + 1}-03-31`,
    };
}

frappe.pages['production-dashboard'].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Production Dashboard'),
        single_column: true,
    });

    const state = {
        page,
        wrapper,
        $cards: null,
        $tabs: null,
        controls: {},
        currentTab: 'rolled_production',
        selectedColumns: {},
        _refreshTimer: null,
        _refreshGen: 0,
    };

    initializeDashboard(state);
};

frappe.pages['production-dashboard'].on_page_show = function () { };

// ────────────────────────────────────────────────────────────────
// Initialization
// ────────────────────────────────────────────────────────────────
function initializeDashboard(state) {
    state.page.main.empty();

    render_filters(state);
    createTabbedInterface(state);
    createContentContainers(state);
    bindEventHandlers(state);

    // Apply active tab styling on first load
    updateTabStyles(state);

    // Initial data load - fetch data till date (filters remain empty in UI)
    refreshDashboard(state);
}

// ────────────────────────────────────────────────────────────────
// Filters
// ────────────────────────────────────────────────────────────────
function render_filters(state) {
    const $filterBar = $(`
        <div class="production-filters"
             style="display:flex;gap:10px;align-items:end;flex-wrap:wrap;
                    margin-bottom:10px;background:#f8f9fa;padding:10px 12px;
                    border-radius:8px;">
        </div>`);

    const $filterControls = $('<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;width:100%;"></div>');

    const $fromDateWrap = $('<div></div>');
    const $toDateWrap = $('<div></div>');
    const $itemWrap = $('<div></div>');
    const $ppWrap = $('<div></div>');
    const $machineWrap = $('<div></div>');
    const $categoryWrap = $('<div></div>');

    $filterControls
        .append($fromDateWrap)
        .append($toDateWrap)
        .append($itemWrap)
        .append($ppWrap)
        .append($machineWrap)
        .append($categoryWrap);

    $filterBar.append($filterControls);
    $(state.page.main).append($filterBar);

    // ── From Date ──
    state.controls.from_date = frappe.ui.form.make_control({
        parent: $fromDateWrap.get(0),
        df: { fieldtype: 'Date', label: __('From Date'), fieldname: 'from_date', reqd: 0 },
        render_input: true,
    });

    // ── To Date ──
    state.controls.to_date = frappe.ui.form.make_control({
        parent: $toDateWrap.get(0),
        df: { fieldtype: 'Date', label: __('To Date'), fieldname: 'to_date', reqd: 0 },
        render_input: true,
    });

    // ── Item Code ──
    state.controls.item_code = frappe.ui.form.make_control({
        parent: $itemWrap.get(0),
        df: { fieldtype: 'Link', label: __('Item Code'), fieldname: 'item_code', options: 'Item', reqd: 0 },
        render_input: true,
    });

    // ── Production Plan (tab-aware, merged from `Production Plan` + `Production Planning`) ──
    // Autocomplete is used instead of Link because options are sourced from two
    // different doctypes (legacy `Production Plan` and new `Production Planning`).
    state.controls.production_plan = frappe.ui.form.make_control({
        parent: $ppWrap.get(0),
        df: {
            fieldtype: 'Autocomplete',
            label: __('Production Plan / Work Order'),
            fieldname: 'production_plan',
            options: [],
            reqd: 0,
        },
        render_input: true,
    });

    // Populate options from both doctypes on initial render.
    refreshProductionPlanOptions(state);

    // ── Machine Name ──
    state.controls.machine_name = frappe.ui.form.make_control({
        parent: $machineWrap.get(0),
        df: {
            fieldtype: 'Link',
            label: __('Machine Name'),
            fieldname: 'machine_name',
            options: 'Machine Master',
            reqd: 0,
        },
        render_input: true,
    });

    // ── Category Name ──
    state.controls.category_name = frappe.ui.form.make_control({
        parent: $categoryWrap.get(0),
        df: {
            fieldtype: 'Link',
            label: __('Category Name'),
            fieldname: 'category_name',
            options: 'Item Category',
            reqd: 0,
        },
        render_input: true,
    });

    // ── Style inputs ──
    setTimeout(() => {
        [state.controls.from_date, state.controls.to_date,
        state.controls.item_code, state.controls.production_plan,
        state.controls.machine_name, state.controls.category_name].forEach(c => {
            if (c && c.$input) {
                $(c.$input).css({
                    border: '1px solid #000', 'border-radius': '4px',
                    padding: '8px 12px', height: '36px', 'line-height': '1.4',
                });
            }
        });
    }, 100);
}


function getProductionPlanNameFilter(state) {
    // Same tab-aware name pattern used for both legacy and new doctypes because
    // `Production Planning` uses naming series "Rolled Plan - ..." / "Bright Plan - ..."
    // which match the existing %Rolled% / %Bright% patterns.
    if (state.currentTab === 'rolled_production' || state.currentTab === 'hourly_production') return ['like', '%Rolled%'];
    if (state.currentTab === 'bright_production') return ['like', '%Bright%'];
    return null;
}

async function refreshProductionPlanOptions(state) {
    const control = state.controls.production_plan;
    if (!control) return;

    const nameFilter = getProductionPlanNameFilter(state);
    const baseFilters = { docstatus: 1 };
    if (nameFilter) baseFilters.name = nameFilter;

    const fetchList = (doctype) =>
        frappe.db
            .get_list(doctype, {
                filters: baseFilters,
                fields: ['name'],
                limit: 0,
                order_by: 'creation desc',
            })
            .catch(() => []);

    // Work Order is now the primary source (rolled/bright driven by the
    // custom_rolled_production / custom_bright_production flags instead of a
    // name pattern). Old Production Plan / Production Planning options are
    // kept too, so filtering by legacy data still works.
    const woFilters = { docstatus: 1 };
    if (state.currentTab === 'rolled_production' || state.currentTab === 'hourly_production') woFilters.custom_rolled_production = 1;
    else if (state.currentTab === 'bright_production') woFilters.custom_bright_production = 1;
    const fetchWorkOrderList = () =>
        frappe.db
            .get_list('Work Order', {
                filters: woFilters,
                fields: ['name'],
                limit: 0,
                order_by: 'creation desc',
            })
            .catch(() => []);

    try {
        const [workOrderList, legacyList, planningList] = await Promise.all([
            fetchWorkOrderList(),
            fetchList('Production Plan'),
            fetchList('Production Planning'),
        ]);

        // Merge + de-duplicate (Work Order names listed first since that's now
        // the primary source; legacy names kept after so old data stays filterable).
        const merged = [];
        const seen = new Set();
        [...(workOrderList || []), ...(legacyList || []), ...(planningList || [])].forEach((r) => {
            if (r && r.name && !seen.has(r.name)) {
                seen.add(r.name);
                merged.push(r.name);
            }
        });

        control.df.options = merged;
        if (typeof control.set_data === 'function') {
            control.set_data(merged);
        }
        if (typeof control.refresh === 'function') {
            control.refresh();
        }
    } catch (err) {
        // Fail silently — leave existing options intact if the fetch errors.
        console.error('Failed to load Production Plan options:', err);
    }
}

function getFilters(state) {
    return {
        from_date: state.controls.from_date ? state.controls.from_date.get_value() : null,
        to_date: state.controls.to_date ? state.controls.to_date.get_value() : null,
        item_code: state.controls.item_code ? state.controls.item_code.get_value() : null,
        production_plan: state.controls.production_plan ? state.controls.production_plan.get_value() : null,
        machine_name: state.controls.machine_name ? state.controls.machine_name.get_value() : null,
        category_name: state.controls.category_name ? state.controls.category_name.get_value() : null,
    };
}

// ────────────────────────────────────────────────────────────────
// Tabs
// ────────────────────────────────────────────────────────────────
function createTabbedInterface(state) {
    const $tabContainer = $('<div class="production-tabs" style="margin-bottom:8px;"></div>');
    const $tabList = $(`<ul class="nav nav-tabs" role="tablist"
        style="border-bottom:2px solid #dee2e6;margin-bottom:0;display:flex;flex-wrap:nowrap;
               overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;"></ul>`);
    const $tabContent = $('<div class="tab-content" style="margin-top:16px;"></div>');

    const tabs = [
        { id: 'rolled_production', label: __('Rolled Production'), icon: 'fa fa-industry' },
        { id: 'hourly_production', label: __('Hourly Production'), icon: 'fa fa-clock-o' },
        { id: 'bright_production', label: __('Bright Production'), icon: 'fa fa-cog' },
        { id: 'bend_weight_details', label: __('Bend Weight Details'), icon: 'fa fa-balance-scale' },
        { id: 'coal_consumption', label: __('Coal Consumption'), icon: 'fa fa-fire' },
        { id: 'monthly_production_coal', label: __('Monthly Production With Coal Consumption'), icon: 'fa fa-calendar' },
        { id: 'billet_cutting_amount', label: __('Monthly Billet Cutting Amount'), icon: 'fa fa-cut' },
        { id: 'weekly_billet_cutting_amount', label: __('Weekly Billet Cutting Amount'), icon: 'fa fa-calendar-check-o' },
    ];

    tabs.forEach((tab, idx) => {
        const $tabItem = $(`
            <li class="nav-item" role="presentation" style="flex:0 0 auto;">
                <button class="nav-link ${idx === 0 ? 'active' : ''}"
                        id="${tab.id}-tab" type="button" role="tab"
                        style="border:none;background:none;padding:10px 14px;
                               color:#6c757d;font-weight:500;font-size:0.88rem;
                               white-space:nowrap;cursor:pointer;">
                    <i class="${tab.icon}" style="margin-right:6px;"></i>${tab.label}
                </button>
            </li>`);

        const $tabPane = $(`
            <div class="tab-pane fade ${idx === 0 ? 'show active' : ''}"
                 id="${tab.id}-content" role="tabpanel" style="min-height:400px;">
            </div>`);

        $tabList.append($tabItem);
        $tabContent.append($tabPane);

        if (!state.$tabs) state.$tabs = {};
        state.$tabs[tab.id] = { $item: $tabItem, $content: $tabPane };
    });

    $tabContainer.append($tabList).append($tabContent);
    $(state.page.main).append($tabContainer);
}

function createContentContainers(state) {
    // Only these tabs ever render KPI cards — the rest stay permanently empty,
    // so they shouldn't reserve the cards container's bottom margin either.
    const tabsWithCards = ['rolled_production', 'bright_production'];

    Object.keys(state.$tabs).forEach(tabId => {
        // Cards
        const cardsMargin = tabsWithCards.includes(tabId) ? '16px' : '0';
        const $cards = $(`<div class="number-cards-container" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin-bottom:${cardsMargin};"></div>`);
        state.$tabs[tabId].$content.append($cards);
        if (!state.$cards) state.$cards = {};
        state.$cards[tabId] = $cards;

        // Table
        let title;
        if (tabId === 'rolled_production') {
            title = __('Rolled Production Details');
        } else if (tabId === 'hourly_production') {
            title = __('Hourly Production Details');
        } else if (tabId === 'bright_production') {
            title = __('Bright Production Details');
        } else if (tabId === 'bend_weight_details') {
            title = __('Bend Weight Details');
        } else if (tabId === 'coal_consumption') {
            title = __('Coal Consumption');
        } else if (tabId === 'monthly_production_coal') {
            title = __('Monthly Production With Coal Consumption');
        } else if (tabId === 'billet_cutting_amount') {
            title = __('Monthly Billet Cutting Amount');
        } else if (tabId === 'weekly_billet_cutting_amount') {
            title = __('Weekly Billet Cutting Amount');
        } else {
            title = '';
        }

        // Title and the Columns/Export toolbar share one row so the toolbar
        // lines up with the heading instead of sitting on its own row above the table.
        const $tableSection = $(`
            <div class="detailed-data-section">
                <div style="display:flex;justify-content:space-between;align-items:center;
                            flex-wrap:wrap;gap:8px;margin-bottom:10px;">
                    <h3 style="margin:0;color:#495057;font-weight:600;">${title}</h3>
                    <div class="table-toolbar" id="${tabId}-toolbar"></div>
                </div>
                <div class="data-tables-container" id="${tabId}-tables"
                     style="overflow-x:auto;"></div>
            </div>`);
        state.$tabs[tabId].$content.append($tableSection);
    });

    // Initialize with empty states
    render_cards(state, {});
    render_table(state, []);
}

// ────────────────────────────────────────────────────────────────
// Event Handlers
// ────────────────────────────────────────────────────────────────
function bindEventHandlers(state) {
    // ── Auto-refresh on filter change (immediate, no debounce) ──
    const handler = () => refreshDashboard(state);

    [state.controls.from_date, state.controls.to_date,
    state.controls.item_code, state.controls.production_plan,
    state.controls.machine_name, state.controls.category_name].forEach(c => {
        if (!c) return;
        c.df.change = handler;
        c.df.onchange = handler;
        if (c.$input) {
            $(c.$input).on('change', handler);
        }
        if ((c.df.fieldtype === 'Link' || c.df.fieldtype === 'Autocomplete') && c.$input) {
            $(c.$input).on('awesomplete-selectcomplete', handler);
            if (c.$wrapper) $(c.$wrapper).on('click', '.btn-clear', handler);
        }
    });

    // ── Tab switching ──
    Object.keys(state.$tabs).forEach(tabId => {
        state.$tabs[tabId].$item.find('button').on('click', () => {
            state.currentTab = tabId;
            updateTabStyles(state);

            $('.tab-pane').removeClass('show active');
            $(`#${tabId}-content`).addClass('show active');
            $('.nav-link').removeClass('active');
            $(`#${tabId}-tab`).addClass('active');

            // Clear production plan value when switching tabs (different filter context)
            if (state.controls.production_plan) {
                state.controls.production_plan.set_value('');
            }

            // Repopulate Production Plan options for the newly active tab
            // (pulls from both `Production Plan` and `Production Planning`).
            refreshProductionPlanOptions(state);

            // Always refresh on tab switch (will fetch till date if no filters set)
            refreshDashboard(state);
        });
    });
}

function updateTabStyles(state) {
    Object.keys(state.$tabs).forEach(tabId => {
        const $btn = state.$tabs[tabId].$item.find('button');
        if (tabId === state.currentTab) {
            $btn.addClass('active').css({ color: '#007bff', 'border-bottom': '2px solid #007bff' });
        } else {
            $btn.removeClass('active').css({ color: '#6c757d', 'border-bottom': 'none' });
        }
    });
}

// ────────────────────────────────────────────────────────────────
// Data Fetch & Render Orchestrator
// ────────────────────────────────────────────────────────────────
function refreshDashboard(state) {
    const filters = getFilters(state);
    const tabId = state.currentTab;

    // Stale-response guard
    state._refreshGen = (state._refreshGen || 0) + 1;
    const thisGen = state._refreshGen;

    state.page.set_indicator(__('Loading…'), 'blue');

    let apiMethod;
    if (tabId === 'rolled_production') {
        apiMethod = 'prakash_steel.api.production_dashboard.get_rolled_production_data';
    } else if (tabId === 'hourly_production') {
        apiMethod = 'prakash_steel.api.production_dashboard.get_hourly_production_data';
    } else if (tabId === 'bright_production') {
        apiMethod = 'prakash_steel.api.production_dashboard.get_bright_production_data';
    } else if (tabId === 'bend_weight_details') {
        apiMethod = 'prakash_steel.api.production_dashboard.get_bend_weight_details';
    } else if (tabId === 'coal_consumption') {
        apiMethod = 'prakash_steel.api.production_dashboard.get_coal_consumption_data';
    } else if (tabId === 'monthly_production_coal') {
        apiMethod = 'prakash_steel.api.production_dashboard.get_monthly_production_with_coal_consumption_data';
    } else if (tabId === 'billet_cutting_amount') {
        apiMethod = 'prakash_steel.api.production_dashboard.get_billet_cutting_amount_data';
    } else if (tabId === 'weekly_billet_cutting_amount') {
        apiMethod = 'prakash_steel.api.production_dashboard.get_weekly_billet_cutting_amount_data';
    }

    // Monthly / weekly summary tabs ignore the shared date filters — they're
    // always scoped to the current Financial Year (April → March).
    const financialYearTabs = [
        'monthly_production_coal',
        'billet_cutting_amount',
        'weekly_billet_cutting_amount',
    ];
    let from_date, to_date;
    if (financialYearTabs.includes(tabId)) {
        const fyRange = financialYearRange(getCurrentFinancialYearStart());
        from_date = fyRange.from_date;
        to_date = fyRange.to_date;
    } else {
        // If no date filters are set, fetch data till today (but keep UI filters empty)
        from_date = filters.from_date || '';
        to_date = filters.to_date || (filters.from_date ? '' : frappe.datetime.get_today());
    }

    frappe.call({
        method: apiMethod,
        args: {
            from_date: from_date,
            to_date: to_date,
            item_code: filters.item_code || '',
            production_plan: filters.production_plan || '',
            machine_name: filters.machine_name || '',
            category_name: filters.category_name || '',
        },
        callback: function (r) {
            if (state._refreshGen !== thisGen) return; // stale
            state.page.clear_indicator();

            const data = r.message || { rows: [], totals: {} };
            render_cards(state, data.totals);
            render_table(state, data.rows);
        },
        error: function () {
            if (state._refreshGen !== thisGen) return;
            state.page.clear_indicator();
            render_cards(state, { total_production: 0, rm_consumption: 0 });
            render_table(state, []);
            frappe.show_alert({ message: __('Error loading production data'), indicator: 'red' });
        },
    });
}

// ────────────────────────────────────────────────────────────────
// Number formatting helpers
// ────────────────────────────────────────────────────────────────
function format_qty_as_integer(value) {
    if (value === undefined || value === null || value === '') {
        return '--';
    }
    const num = parseFloat(value);
    if (isNaN(num)) {
        return '--';
    }
    const truncated = Math.trunc(num);
    return format_number(truncated, null, 0);
}

function format_number_with_decimals(value) {
    if (value === undefined || value === null || value === '') {
        return '--';
    }
    const num = parseFloat(value);
    if (isNaN(num)) {
        return '--';
    }
    return format_number(num);
}

function format_percentage(value) {
    if (value === undefined || value === null || value === '') {
        return '--';
    }
    const num = parseFloat(value);
    if (isNaN(num)) {
        return '--';
    }
    return num.toFixed(2);
}

function getGradientStyle(gradientClass) {
    const gradients = {
        'card-orange': 'linear-gradient(135deg, #fdd085, #fde0a8)',
        'card-blue': 'linear-gradient(135deg, #a8c8f0, #c4d9f5)',
        'card-green': 'linear-gradient(135deg, #85e0a8, #a8ecc4)',
        'card-purple': 'linear-gradient(135deg, #c9a5d9, #d9b8e6)',
        'card-teal': 'linear-gradient(135deg, #7dd3c0, #a3e4d4)',
        'card-red': 'linear-gradient(135deg, #f5a5a0, #f8b8b3)',
        'card-pink': 'linear-gradient(135deg, #f8c8d8, #fce0e8)',
        'card-yellow': 'linear-gradient(135deg, #d4a574, #e8d5b7)',
    };
    return gradients[gradientClass] || gradients['card-blue'];
}

function buildCardHtml(card) {
    const raw = card.value;
    let display;
    if (card.isQty) {
        display = format_qty_as_integer(raw);
    } else if (card.isPercentage) {
        display = format_percentage(raw);
    } else {
        display = format_number_with_decimals(raw);
    }

    const gradientClass = card.gradientClass || 'card-blue';
    const gradient = getGradientStyle(gradientClass);

    const desc = card.description
        ? `<div style="font-size:0.85rem;color:#000;margin-top:8px;opacity:0.7;">${frappe.utils.escape_html(card.description)}</div>`
        : '';

    return $(`
        <div class="number-card ${gradientClass}"
             style="background:${gradient} !important;background-image:${gradient} !important;
                    border-radius:10px;padding:14px 18px;
                    box-shadow:none;min-height:110px;
                    position:relative;overflow:hidden;
                    transition:transform .2s,box-shadow .2s;
                    color:#000;border:none;">
            <div style="text-align:center;">
                <div style="font-size:1.9rem;font-weight:700;color:#000;
                            margin-bottom:6px;line-height:1.1;">${display}</div>
                <div style="font-size:0.95rem;color:#000;font-weight:500;opacity:0.95;">
                    ${frappe.utils.escape_html(card.label || '')}</div>
                ${desc}
            </div>
        </div>`);
}

// ────────────────────────────────────────────────────────────────
// KPI Cards
// ────────────────────────────────────────────────────────────────
function render_cards(state, totals) {
    const tabId = state.currentTab;
    const $container = state.$cards && state.$cards[tabId];
    if (!$container || !$container.length) {
        return;
    }
    $container.empty();

    totals = totals || {};

    // For Bend Weight Details / Coal Consumption, skip KPI cards for now
    if (tabId === 'bend_weight_details' || tabId === 'coal_consumption' || tabId === 'hourly_production'
        || tabId === 'monthly_production_coal' || tabId === 'billet_cutting_amount'
        || tabId === 'weekly_billet_cutting_amount') {
        return;
    }

    const gradientClasses = tabId === 'rolled_production'
        ? [] // we will assign explicit colors below
        : ['card-yellow', 'card-green', 'card-orange'];

    const cards = [
        {
            value: totals.total_production,
            label: __('Total Production (kg)'),
            gradientClass: tabId === 'rolled_production' ? 'card-blue' : gradientClasses[0],
            description: __('Sum of Actual Qty across all rows'),
            isQty: true,
        },
        {
            value: totals.rm_consumption,
            label: __('RM Consumption'),
            gradientClass: tabId === 'rolled_production' ? 'card-teal' : gradientClasses[1],
            description: __('Sum of RM Consumption across all rows'),
            isQty: true,
        },
    ];

    // Tab-specific KPI cards
    if (tabId === 'rolled_production') {
        const totalProd = parseFloat(totals.total_production) || 0;
        const totalHr = parseFloat(totals.total_hr_consumed) || 0;
        const totalMeltingWeight = parseFloat(totals.total_melting_weight) || 0;
        const totalMissBilletWeight = parseFloat(totals.total_miss_billet_weight) || 0;
        const totalMissRollWeight = parseFloat(totals.total_miss_roll_weight) || 0;
        const totalMissIngotWeight = parseFloat(totals.total_miss_ingot_weight) || 0;

        // Average Production = Total Production / Sum(Total Hr Consumed)
        let avgProduction = 0;
        if (totalHr > 0) {
            avgProduction = totalProd / totalHr;
        }

        cards.push({
            value: avgProduction,
            label: __('Average Production'),
            gradientClass: 'card-red',
            description: __('Total Production / Total Hr Consumed'),
        });

        // Total Melting Weight
        cards.push({
            value: totalMeltingWeight,
            label: __('Total Melting Weight'),
            gradientClass: 'card-green',
            description: __('Sum of Melting Weight across all rows'),
            isQty: true,
        });

        // Total Miss Billet Weight
        cards.push({
            value: totalMissBilletWeight,
            label: __('Total Miss Billet Weight(RM)'),
            gradientClass: 'card-pink',
            description: __('Sum of Miss Billet Weight across all rows'),
            isQty: true,
        });

        // Total Miss Roll Weight
        cards.push({
            value: totalMissRollWeight,
            label: __('Total Miss Roll Weight(FG)'),
            gradientClass: 'card-orange',
            description: __('Sum of Total Miss Roll Weight across all rows'),
            isQty: true,
        });

        // Total Miss Ingot / Billet Weight
        cards.push({
            value: totalMissIngotWeight,
            label: __('Total Miss Ingot / Billet Weight(FG)'),
            gradientClass: 'card-purple',
            description: __('Sum of Total Miss Ingot / Billet Weight across all rows'),
            isQty: true,
        });

        // Wastage % — (Total RM Wt − Miss Ingot − Production) / Total RM Wt × 100 (backend)
        cards.push({
            value: totals.burning_loss_per,
            label: __('Wastage %'),
            gradientClass: 'card-red',
            description: __('Avg Wastage %'),
            isPercentage: true,
        });

    } else if (tabId === 'bright_production') {
        // End Cutting Weight — Sum across all rows (backend calculated)
        cards.push({
            value: totals.total_end_cutting_weight,
            label: __('Total End Cutting Weight'),
            gradientClass: 'card-teal',
            description: __('Sum of End Cutting Weight across all rows'),
            isQty: true,
        });

        // Wastage % — Average from Bright Bar Production records (backend calculated)
        cards.push({
            value: totals.wastage_per,
            label: __('Wastage %'),
            gradientClass: gradientClasses[2],
            description: __('Average Wastage % (from Bright Bar Production)'),
            isPercentage: true,
        });
    }

    cards.forEach(card => {
        $container.append(buildCardHtml(card));
    });
}

// ────────────────────────────────────────────────────────────────
// Table Rendering
// ────────────────────────────────────────────────────────────────
function render_table(state, rows) {
    const tabId = state.currentTab;
    const $container = $(`#${tabId}-tables`);
    if (!$container.length) {
        return;
    }
    $container.empty();

    const columns = getTableColumns(tabId);

    // ── Export toolbar (Excel / PDF) — lives in the header row, next to the title ──
    const $toolbarMount = $(`#${tabId}-toolbar`);
    $toolbarMount.empty();
    const $exportBar = buildExportToolbar(state, tabId, columns, rows || []);
    $toolbarMount.append($exportBar);

    // ── Header ──
    const isBilletCuttingAmount = tabId === 'billet_cutting_amount';
    const isWeeklyBilletCuttingAmount = tabId === 'weekly_billet_cutting_amount';
    const thBase = 'background:#495057;padding:12px;font-weight:600;color:#ffffff;'
        + 'border-bottom:2px solid #343a40;white-space:nowrap;text-align:center !important;'
        + 'position:sticky;top:0;z-index:2;';

    const thCol0 = thBase.replace('z-index:2', 'z-index:3')
        + 'left:0;width:220px;max-width:220px;overflow:hidden;text-overflow:ellipsis;';
    const thCol1 = thBase.replace('z-index:2', 'z-index:3')
        + 'left:220px;width:140px;max-width:140px;overflow:hidden;text-overflow:ellipsis;border-right:2px solid #dee2e6;';

    let theadHtml;
    if (isBilletCuttingAmount || isWeeklyBilletCuttingAmount) {
        // Two-row header: group labels (colspan) + Qty / Amount (or Weeks from/to) sub-columns.
        const thGroup = thBase; // top:0
        const thSub = thBase.replace('top:0', 'top:42px');
        const groupBorder = 'border-left:1px solid rgba(255,255,255,.35);';
        const cuttingGroups = [
            __('Full Cutting (FC) (MT)'),
            __('Half Cutting (HF) (MT)'),
            __('General Cutting (GC) (MT)'),
            __('Full Cutting-NG (FC-N) (MT)'),
            __('Total (MT)'),
        ];

        let topRow;
        let subRow;
        if (isWeeklyBilletCuttingAmount) {
            // Match Monthly table styling: same group/sub header treatment,
            // no sticky fixed-width lead columns.
            topRow = [
                `<th colspan="2" style="${thGroup}">${__('Weekly Billet Cutting Details')}</th>`,
                ...cuttingGroups.map((label) =>
                    `<th colspan="2" style="${thGroup}${groupBorder}">${label}</th>`
                ),
            ].join('');
            const weekSubs = [
                `<th style="${thSub}">${__('Weeks from')}</th>`,
                `<th style="${thSub}">${__('Weeks to')}</th>`,
            ];
            const qtyAmountSubs = [];
            for (let i = 0; i < 5; i++) {
                qtyAmountSubs.push(
                    `<th style="${thSub}${groupBorder}">${__('Qty')}</th>`,
                    `<th style="${thSub}">${__('Amount')}</th>`
                );
            }
            subRow = weekSubs.concat(qtyAmountSubs).join('');
        } else {
            const thMonth = thCol0; // rowspan covers both header rows
            topRow = [
                `<th rowspan="2" style="${thMonth}">${__('Month')}</th>`,
                ...cuttingGroups.map((label) =>
                    `<th colspan="2" style="${thGroup}${groupBorder}">${label}</th>`
                ),
            ].join('');
            const subLabels = [];
            for (let i = 0; i < 5; i++) {
                subLabels.push(__('Qty'), __('Amount'));
            }
            subRow = subLabels
                .map((label, idx) => {
                    const borderLeft = idx % 2 === 0 ? groupBorder : '';
                    return `<th style="${thSub}${borderLeft}">${label}</th>`;
                })
                .join('');
        }
        theadHtml = `<tr>${topRow}</tr><tr>${subRow}</tr>`;
    } else {
        const headerHtml = columns.map((c, idx) => {
            const borderAfterQty =
                (tabId === 'rolled_production' && (idx === 11 || idx === 21)) ||
                (tabId === 'bright_production' && idx === 4);
            const borderRight = borderAfterQty ? ' border-right:2px solid #dee2e6;' : '';
            let style;
            if (idx === 0) style = thCol0;
            else if (idx === 1) style = thCol1;
            else style = thBase;
            return `<th style="${style}${borderRight}">${c.label}</th>`;
        }).join('');
        theadHtml = `<tr>${headerHtml}</tr>`;
    }

    // ── Body ──
    let bodyHtml = '';
    if (!rows || rows.length === 0) {
        bodyHtml = `<tr><td colspan="${columns.length}"
            style="padding:24px;text-align:center;color:#7f8c8d;font-style:italic;">
            ${__('No data available for the selected filters.')}</td></tr>`;
    } else {
        bodyHtml = rows.map((row, idx) => buildTableRow(tabId, row, idx)).join('');
    }

    const $table = $(`
        <div style="width:100%;margin-bottom:30px;overflow:auto;max-height:70vh;
                    border-radius:6px;box-shadow:0 1px 3px rgba(0,0,0,.1);">
            <table style="width:100%;border-collapse:separate;border-spacing:0;
                          background:#fff;min-width:1000px;">
                <thead>${theadHtml}</thead>
                <tbody>${bodyHtml}</tbody>
            </table>
        </div>`);

    $container.append($table);
}

function buildTableRow(tabId, row, rowIndex) {
    const tdStyle = 'padding:12px;border-bottom:1px solid #e9ecef;color:#495057;text-align:center !important;';
    const tdCol0 = tdStyle
        + 'position:sticky;left:0;z-index:1;background:#fff;'
        + 'width:220px;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
    const tdCol1 = tdStyle
        + 'position:sticky;left:220px;z-index:1;background:#fff;'
        + 'width:140px;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;border-right:2px solid #dee2e6;';

    // Production Plan (link)
    const ppRouteMap = {
        'Production Planning': 'production-planning',
        'Work Order': 'work-order',
    };
    const ppRoute = ppRouteMap[row.production_plan_doctype] || 'production-plan';
    const ppLink = row.production_plan
        ? `<a href="/app/${ppRoute}/${encodeURIComponent(row.production_plan)}"
              title="${frappe.utils.escape_html(row.production_plan)}"
              style="color:#007bff;text-decoration:none;">${frappe.utils.escape_html(row.production_plan)}</a>`
        : '';

    // Production Date
    const prodDate = row.production_date
        ? frappe.format(row.production_date, { fieldtype: 'Date' })
        : '';

    // Finished Item
    const finishedItem = row.finished_item
        ? frappe.utils.escape_html(row.finished_item)
        : '';

    // Qty fields
    const fgPlannedQty = format_qty_as_integer(row.fg_planned_qty);
    const actualQty = format_qty_as_integer(row.actual_qty);
    const meltingWeight = format_qty_as_integer(row.melting_weight);
    const finishPcs = format_qty_as_integer(row.finish_pcs);
    const totalMissRollPcs = format_qty_as_integer(row.total_miss_roll_pcs);
    const totalMissRollWeight = format_qty_as_integer(row.total_miss_roll_weight);
    const totalMissIngotPcs = format_qty_as_integer(row.total_miss_ingot_pcs);
    const totalMissIngotWeight = format_qty_as_integer(row.total_miss_ingot_weight);
    const billetPcs = format_qty_as_integer(row.billet_pcs);
    const totalRawMaterialPcs = format_qty_as_integer(row.total_raw_material_pcs);
    const missBilletPcs = format_qty_as_integer(row.miss_billet_pcs);
    const missBilletWeight = format_qty_as_integer(row.miss_billet_weight);
    const totalRMWeight = format_qty_as_integer(
        (parseFloat(row.rm_consumption) || 0) + (parseFloat(row.miss_billet_weight) || 0)
    );
    const heatNo = row.heat_no ? frappe.utils.escape_html(String(row.heat_no)) : '';
    const totalHrConsumed = format_number_with_decimals(row.total_hr_consumed);
    const rmConsumption = format_qty_as_integer(row.rm_consumption);
    const fgLength = row.fg_length ? frappe.utils.escape_html(String(row.fg_length)) : '';
    const rm = row.rm ? frappe.utils.escape_html(row.rm) : '';
    const descriptionOfCuttingBillet = row.description_of_cutting_billet
        ? frappe.utils.escape_html(String(row.description_of_cutting_billet))
        : '';

    // Last column – percentage
    let lastColValue = '';
    if (tabId === 'rolled_production') {
        lastColValue = format_percentage(row.burning_loss);
    } else {
        lastColValue = format_percentage(row.wastage);
    }

    // ── Rolled Production ──
    if (tabId === 'rolled_production') {
        const burningLossVal = parseFloat(row.burning_loss) || 0;
        const rowBg = burningLossVal > 3.5 ? 'background:#ffe5e5;' : '';
        const tdHighlight = rowBg ? tdStyle + rowBg : tdStyle;
        const tdCol0H = tdCol0 + rowBg;
        const tdCol1H = tdCol1 + rowBg;

        const rmCategoryName = row.rm_category_name ? frappe.utils.escape_html(row.rm_category_name) : '';
        const finishedItemCategoryName = row.finished_item_category_name ? frappe.utils.escape_html(row.finished_item_category_name) : '';

        return `<tr style="border-bottom:1px solid #e9ecef;${rowBg}">
            <td style="${tdCol0H}">${ppLink}</td>
            <td style="${tdCol1H}">${prodDate}</td>
            <td style="${tdHighlight}">${rm}</td>
            <td style="${tdHighlight}">${rmCategoryName}</td>
            <td style="${tdHighlight}">${rmConsumption}</td>
            <td style="${tdHighlight}">${billetPcs}</td>
            <td style="${tdHighlight}">${descriptionOfCuttingBillet}</td>
            <td style="${tdHighlight}">${totalRawMaterialPcs}</td>
            <td style="${tdHighlight}">${totalRMWeight}</td>
            <td style="${tdHighlight}">${missBilletPcs}</td>
            <td style="${tdHighlight}">${missBilletWeight}</td>
            <td style="${tdHighlight} border-right:2px solid #dee2e6;">${heatNo}</td>
            <td style="${tdHighlight}">${finishedItem}</td>
            <td style="${tdHighlight}">${finishedItemCategoryName}</td>
            <td style="${tdHighlight}">${fgPlannedQty}</td>
            <td style="${tdHighlight}">${actualQty}</td>
            <td style="${tdHighlight}">${finishPcs}</td>
            <td style="${tdHighlight}">${fgLength}</td>
            <td style="${tdHighlight}">${totalMissRollPcs}</td>
            <td style="${tdHighlight}">${totalMissRollWeight}</td>
            <td style="${tdHighlight}">${totalMissIngotPcs}</td>
            <td style="${tdHighlight} border-right:2px solid #dee2e6;">${totalMissIngotWeight}</td>
            <td style="${tdHighlight}">${meltingWeight}</td>
            <td style="${tdHighlight}">${lastColValue}</td>
            <td style="${tdHighlight}">${format_percentage(row.melting_wastage)}</td>
            <td style="${tdHighlight}">${format_percentage(row.finish_goods)}</td>
            <td style="${tdHighlight}">${totalHrConsumed}</td>
        </tr>`;
    }

    // ── Bend Weight Details ──
    if (tabId === 'bend_weight_details') {
        const id = row.id || row.name || '';
        const idRouteMap = {
            'Finish Weight': 'finish-weight',
            'Job Card': 'job-card',
        };
        const idRoute = idRouteMap[row.id_doctype] || 'finish-weight';
        const idLink = id
            ? `<a href="/app/${idRoute}/${encodeURIComponent(id)}"
                  title="${frappe.utils.escape_html(String(id))}"
                  style="color:#007bff;text-decoration:none;">${frappe.utils.escape_html(String(id))}</a>`
            : '';
        const itemCode = row.item_code ? frappe.utils.escape_html(String(row.item_code)) : '';
        const bendCategoryName = row.category_name ? frappe.utils.escape_html(String(row.category_name)) : '';
        const bendWeight = format_number_with_decimals(row.bend_material_weight);

        return `<tr style="border-bottom:1px solid #e9ecef;">
            <td style="${tdCol0}">${idLink}</td>
            <td style="${tdCol1}">${itemCode}</td>
            <td style="${tdStyle}">${bendCategoryName}</td>
            <td style="${tdStyle}">${bendWeight}</td>
        </tr>`;
    }

    // ── Coal Consumption ──
    if (tabId === 'coal_consumption') {
        const coalDate = row.date
            ? frappe.format(row.date, { fieldtype: 'Date' })
            : '';
        const coalItem = row.item ? frappe.utils.escape_html(String(row.item)) : '';
        const coalQty = format_number_with_decimals(row.qty);
        const coalUom = row.uom ? frappe.utils.escape_html(String(row.uom)) : '';

        return `<tr style="border-bottom:1px solid #e9ecef;">
            <td style="${tdCol0}">${coalDate}</td>
            <td style="${tdCol1}">${coalItem}</td>
            <td style="${tdStyle}">${coalQty}</td>
            <td style="${tdStyle}">${coalUom}</td>
        </tr>`;
    }

    // ── Monthly Production With Coal Consumption ──
    if (tabId === 'monthly_production_coal') {
        const month = row.month ? frappe.utils.escape_html(String(row.month)) : '';
        const totalProduction = format_number_with_decimals(row.total_production);
        const totalCoalConsumption = format_number_with_decimals(row.total_coal_consumption);
        const perTonCoal = format_number_with_decimals(row.per_ton_coal_consumption);

        return `<tr style="border-bottom:1px solid #e9ecef;">
            <td style="${tdCol0}">${month}</td>
            <td style="${tdStyle}">${totalProduction}</td>
            <td style="${tdStyle}">${totalCoalConsumption}</td>
            <td style="${tdStyle}">${perTonCoal}</td>
        </tr>`;
    }

    // ── Hourly Production ──
    if (tabId === 'hourly_production') {
        const hourlyDate = row.date
            ? frappe.format(row.date, { fieldtype: 'Date' })
            : '';
        const hours = format_number_with_decimals(row.hours);

        return `<tr style="border-bottom:1px solid #e9ecef;">
            <td style="${tdCol0}">${hourlyDate}</td>
            <td style="${tdCol1}">${hours}</td>
        </tr>`;
    }

    // ── Monthly Billet Cutting Amount ──
    if (tabId === 'billet_cutting_amount') {
        const month = row.month ? frappe.utils.escape_html(String(row.month)) : '';
        const fcQty = format_number_with_decimals(row.fc_qty);
        const fcAmount = format_number_with_decimals(row.fc_amount);
        const hfQty = format_number_with_decimals(row.hf_qty);
        const hfAmount = format_number_with_decimals(row.hf_amount);
        const gcQty = format_number_with_decimals(row.gc_qty);
        const gcAmount = format_number_with_decimals(row.gc_amount);
        const fcnQty = format_number_with_decimals(row.fcn_qty);
        const fcnAmount = format_number_with_decimals(row.fcn_amount);
        const totalQty = format_number_with_decimals(row.total_qty);
        const totalAmount = format_number_with_decimals(row.total_amount);
        const groupBorder = 'border-left:1px solid #dee2e6;';

        return `<tr style="border-bottom:1px solid #e9ecef;">
            <td style="${tdCol0}">${month}</td>
            <td style="${tdStyle}${groupBorder}">${fcQty}</td>
            <td style="${tdStyle}">${fcAmount}</td>
            <td style="${tdStyle}${groupBorder}">${hfQty}</td>
            <td style="${tdStyle}">${hfAmount}</td>
            <td style="${tdStyle}${groupBorder}">${gcQty}</td>
            <td style="${tdStyle}">${gcAmount}</td>
            <td style="${tdStyle}${groupBorder}">${fcnQty}</td>
            <td style="${tdStyle}">${fcnAmount}</td>
            <td style="${tdStyle}${groupBorder};font-weight:600;">${totalQty}</td>
            <td style="${tdStyle};font-weight:600;">${totalAmount}</td>
        </tr>`;
    }

    // ── Weekly Billet Cutting Amount ──
    if (tabId === 'weekly_billet_cutting_amount') {
        const weeksFrom = row.weeks_from ? frappe.utils.escape_html(String(row.weeks_from)) : '';
        const weeksTo = row.weeks_to ? frappe.utils.escape_html(String(row.weeks_to)) : '';
        const fcQty = format_number_with_decimals(row.fc_qty);
        const fcAmount = format_number_with_decimals(row.fc_amount);
        const hfQty = format_number_with_decimals(row.hf_qty);
        const hfAmount = format_number_with_decimals(row.hf_amount);
        const gcQty = format_number_with_decimals(row.gc_qty);
        const gcAmount = format_number_with_decimals(row.gc_amount);
        const fcnQty = format_number_with_decimals(row.fcn_qty);
        const fcnAmount = format_number_with_decimals(row.fcn_amount);
        const totalQty = format_number_with_decimals(row.total_qty);
        const totalAmount = format_number_with_decimals(row.total_amount);
        const groupBorder = 'border-left:1px solid #dee2e6;';

        // Same cell styling as Monthly (centered tdStyle, group borders on Qty leads).
        return `<tr style="border-bottom:1px solid #e9ecef;">
            <td style="${tdStyle}">${weeksFrom}</td>
            <td style="${tdStyle}">${weeksTo}</td>
            <td style="${tdStyle}${groupBorder}">${fcQty}</td>
            <td style="${tdStyle}">${fcAmount}</td>
            <td style="${tdStyle}${groupBorder}">${hfQty}</td>
            <td style="${tdStyle}">${hfAmount}</td>
            <td style="${tdStyle}${groupBorder}">${gcQty}</td>
            <td style="${tdStyle}">${gcAmount}</td>
            <td style="${tdStyle}${groupBorder}">${fcnQty}</td>
            <td style="${tdStyle}">${fcnAmount}</td>
            <td style="${tdStyle}${groupBorder};font-weight:600;">${totalQty}</td>
            <td style="${tdStyle};font-weight:600;">${totalAmount}</td>
        </tr>`;
    }

    // ── Bright Production ──
    const machineName = row.machine_name ? frappe.utils.escape_html(String(row.machine_name)) : '';
    const finishLength = row.finish_length ? frappe.utils.escape_html(String(row.finish_length)) : '';
    const tolerance = row.tolerance ? frappe.utils.escape_html(String(row.tolerance)) : '';
    const endCuttingWeight = format_qty_as_integer(row.end_cutting_weight);
    const brightRmCategoryName = row.rm_category_name ? frappe.utils.escape_html(String(row.rm_category_name)) : '';
    const brightFiCategoryName = row.finished_item_category_name ? frappe.utils.escape_html(String(row.finished_item_category_name)) : '';

    return `<tr style="border-bottom:1px solid #e9ecef;">
        <td style="${tdCol0}">${ppLink}</td>
        <td style="${tdCol1}">${prodDate}</td>
        <td style="${tdStyle}">${rm}</td>
        <td style="${tdStyle}">${brightRmCategoryName}</td>
        <td style="${tdStyle} border-right:2px solid #dee2e6;">${machineName}</td>
        <td style="${tdStyle}">${finishedItem}</td>
        <td style="${tdStyle}">${brightFiCategoryName}</td>
        <td style="${tdStyle}">${fgPlannedQty}</td>
        <td style="${tdStyle}">${rmConsumption}</td>
        <td style="${tdStyle}">${actualQty}</td>
        <td style="${tdStyle}">${finishLength}</td>
        <td style="${tdStyle}">${tolerance}</td>
        <td style="${tdStyle}">${endCuttingWeight}</td>
        <td style="${tdStyle}">${lastColValue}</td>
    </tr>`;
}

function getTableColumns(tabId) {
    if (tabId === 'rolled_production') {
        return [
            { key: 'production_plan', label: __('Production Plan / Work Order'), align: 'left' },
            { key: 'production_date', label: __('Production Date'), align: 'left' },
            { key: 'rm', label: __('RM'), align: 'left' },
            { key: 'rm_category_name', label: __('RM Category Name'), align: 'left' },
            { key: 'rm_consumption', label: __('Actual RM Consumption'), align: 'left' },
            { key: 'billet_pcs', label: __('Total Billet Pcs'), align: 'left' },
            { key: 'description_of_cutting_billet', label: __('Description of Cutting Billet'), align: 'left' },
            { key: 'total_raw_material_pcs', label: __('Total Raw Material Pcs'), align: 'left' },
            { key: 'total_rm_weight', label: __('Total RM Weight'), align: 'left' },
            { key: 'miss_billet_pcs', label: __('Miss Billet Pcs'), align: 'left' },
            { key: 'miss_billet_weight', label: __('Miss Billet Weight'), align: 'left' },
            { key: 'heat_no', label: __('Heat No'), align: 'left' },
            { key: 'finished_item', label: __('Finished Item'), align: 'left' },
            { key: 'finished_item_category_name', label: __('Finished Item Category Name'), align: 'left' },
            { key: 'fg_planned_qty', label: __('FG Planned Qty'), align: 'left' },
            { key: 'actual_qty', label: __('Actual Qty'), align: 'left' },
            { key: 'finish_pcs', label: __('Finish Pcs'), align: 'left' },
            { key: 'fg_length', label: __('FG Length'), align: 'left' },
            { key: 'total_miss_roll_pcs', label: __('Total Miss Roll (Pcs)'), align: 'left' },
            { key: 'total_miss_roll_weight', label: __('Total Miss Roll Weight'), align: 'left' },
            { key: 'total_miss_ingot_pcs', label: __('Total Miss Ingot'), align: 'left' },
            { key: 'total_miss_ingot_weight', label: __('Total Miss Ingot / Billet Weight'), align: 'left' },
            { key: 'melting_weight', label: __('Melting Weight'), align: 'left' },
            { key: 'burning_loss', label: __('Wastage %'), align: 'left' },
            { key: 'melting_wastage', label: __('Melting Wastage %'), align: 'left' },
            { key: 'finish_goods', label: __('Finish Goods %'), align: 'left' },
            { key: 'total_hr_consumed', label: __('Total Hr Consumed'), align: 'left' },
        ];
    }

    if (tabId === 'bend_weight_details') {
        return [
            { key: 'id', label: __('ID'), align: 'left' },
            { key: 'item_code', label: __('Item Code'), align: 'left' },
            { key: 'category_name', label: __('Category Name'), align: 'left' },
            { key: 'bend_material_weight', label: __('Bend Material Weight'), align: 'left' },
        ];
    }

    if (tabId === 'coal_consumption') {
        return [
            { key: 'date', label: __('Date'), align: 'left' },
            { key: 'item', label: __('Item'), align: 'left' },
            { key: 'qty', label: __('Qty'), align: 'left' },
            { key: 'uom', label: __('UOM'), align: 'left' },
        ];
    }

    if (tabId === 'hourly_production') {
        return [
            { key: 'date', label: __('Date'), align: 'left' },
            { key: 'hours', label: __('Hours'), align: 'left' },
        ];
    }

    if (tabId === 'monthly_production_coal') {
        return [
            { key: 'month', label: __('Month'), align: 'left' },
            { key: 'total_production', label: __('Total Production'), align: 'left' },
            { key: 'total_coal_consumption', label: __('Total Coal Consumption'), align: 'left' },
            { key: 'per_ton_coal_consumption', label: __('Per Ton Coal Consumption (In KG)'), align: 'left' },
        ];
    }

    if (tabId === 'billet_cutting_amount') {
        // Leaf columns for export / column picker. Group headers (FC/HF/GC/FC-N/Total)
        // are rendered separately as a two-row thead with Qty / Amount sub-columns.
        return [
            { key: 'month', label: __('Month'), align: 'left' },
            { key: 'fc_qty', label: __('Full Cutting (FC) (MT) — Qty'), align: 'left' },
            { key: 'fc_amount', label: __('Full Cutting (FC) (MT) — Amount'), align: 'left' },
            { key: 'hf_qty', label: __('Half Cutting (HF) (MT) — Qty'), align: 'left' },
            { key: 'hf_amount', label: __('Half Cutting (HF) (MT) — Amount'), align: 'left' },
            { key: 'gc_qty', label: __('General Cutting (GC) (MT) — Qty'), align: 'left' },
            { key: 'gc_amount', label: __('General Cutting (GC) (MT) — Amount'), align: 'left' },
            { key: 'fcn_qty', label: __('Full Cutting-NG (FC-N) (MT) — Qty'), align: 'left' },
            { key: 'fcn_amount', label: __('Full Cutting-NG (FC-N) (MT) — Amount'), align: 'left' },
            { key: 'total_qty', label: __('Total (MT) — Qty'), align: 'left' },
            { key: 'total_amount', label: __('Total (MT) — Amount'), align: 'left' },
        ];
    }

    if (tabId === 'weekly_billet_cutting_amount') {
        return [
            { key: 'weeks_from', label: __('Weeks from'), align: 'left' },
            { key: 'weeks_to', label: __('Weeks to'), align: 'left' },
            { key: 'fc_qty', label: __('Full Cutting (FC) (MT) — Qty'), align: 'left' },
            { key: 'fc_amount', label: __('Full Cutting (FC) (MT) — Amount'), align: 'left' },
            { key: 'hf_qty', label: __('Half Cutting (HF) (MT) — Qty'), align: 'left' },
            { key: 'hf_amount', label: __('Half Cutting (HF) (MT) — Amount'), align: 'left' },
            { key: 'gc_qty', label: __('General Cutting (GC) (MT) — Qty'), align: 'left' },
            { key: 'gc_amount', label: __('General Cutting (GC) (MT) — Amount'), align: 'left' },
            { key: 'fcn_qty', label: __('Full Cutting-NG (FC-N) (MT) — Qty'), align: 'left' },
            { key: 'fcn_amount', label: __('Full Cutting-NG (FC-N) (MT) — Amount'), align: 'left' },
            { key: 'total_qty', label: __('Total (MT) — Qty'), align: 'left' },
            { key: 'total_amount', label: __('Total (MT) — Amount'), align: 'left' },
        ];
    }

    // bright_production
    return [
        { key: 'production_plan', label: __('Production Plan / Work Order'), align: 'left' },
        { key: 'production_date', label: __('Production Date'), align: 'left' },
        { key: 'rm', label: __('RM'), align: 'left' },
        { key: 'rm_category_name', label: __('RM Category Name'), align: 'left' },
        { key: 'machine_name', label: __('Machine Name'), align: 'left' },
        { key: 'finished_item', label: __('Finished Item'), align: 'left' },
        { key: 'finished_item_category_name', label: __('Finished Item Category Name'), align: 'left' },
        { key: 'fg_planned_qty', label: __('FG Planned Qty'), align: 'left' },
        { key: 'rm_consumption', label: __('Actual RM Consumption'), align: 'left' },
        { key: 'actual_qty', label: __('Actual Qty'), align: 'left' },
        { key: 'finish_length', label: __('Finish Length'), align: 'left' },
        { key: 'tolerance', label: __('Tolerance'), align: 'left' },
        { key: 'end_cutting_weight', label: __('End Cutting Weight'), align: 'left' },
        { key: 'wastage', label: __('Wastage %'), align: 'left' },
    ];
}

// ────────────────────────────────────────────────────────────────
// Export Helpers (Excel & PDF)
// ────────────────────────────────────────────────────────────────
function buildExportToolbar(state, tabId, columns, rows) {
    const $wrapper = $(`
        <div style="display:flex;justify-content:flex-end;align-items:center;gap:8px;flex-shrink:0;">
            <button type="button" class="btn btn-sm btn-default col-picker-btn"
                    style="padding:6px 14px;border-radius:4px;border:1px solid #ced4da;
                           display:flex;align-items:center;gap:6px;">
                <i class="fa fa-columns"></i>
                <span>${__('Columns')}</span>
            </button>
            <div class="export-dropdown" style="position:relative;">
                <button type="button"
                        class="btn btn-sm"
                        style="background-color:#28a745;color:#fff;border:none;
                               padding:6px 14px;border-radius:4px;
                               display:flex;align-items:center;gap:6px;">
                    <span>${__('Export')}</span>
                    <span style="font-size:0.8rem;">▾</span>
                </button>
                <div class="export-menu"
                     style="display:none;position:absolute;right:0;top:100%;
                            background:#fff;border:1px solid #ced4da;
                            border-radius:4px;box-shadow:0 2px 6px rgba(0,0,0,0.15);
                            min-width:160px;z-index:10;">
                    <div class="export-option"
                         data-format="excel"
                         style="padding:8px 12px;cursor:pointer;font-size:0.9rem;">
                        ${__('Export to Excel')}
                    </div>
                    <div class="export-option"
                         data-format="pdf"
                         style="padding:8px 12px;cursor:pointer;font-size:0.9rem;">
                        ${__('Export to PDF')}
                    </div>
                </div>
            </div>
        </div>
    `);

    $wrapper.find('.col-picker-btn').on('click', () => {
        showColumnPickerDialog(state, tabId);
    });

    const $btn = $wrapper.find('.export-dropdown button');
    const $menu = $wrapper.find('.export-menu');

    $btn.on('click', (e) => {
        e.stopPropagation();
        $menu.toggle();
    });

    $menu.find('.export-option[data-format="excel"]').on('click', (e) => {
        e.stopPropagation();
        exportTableToExcel(state, tabId);
        $menu.hide();
    });

    $menu.find('.export-option[data-format="pdf"]').on('click', (e) => {
        e.stopPropagation();
        exportTableToPDF(state, tabId, columns, rows);
        $menu.hide();
    });

    // Hide dropdown when clicking outside
    $(document).on(`click.exportDropdown-${tabId}`, () => {
        $menu.hide();
    });

    return $wrapper;
}

function showColumnPickerDialog(state, tabId) {
    const allColumns = getTableColumns(tabId);
    const selectedKeys = state.selectedColumns[tabId] || allColumns.map(c => c.key);

    const listHtml = allColumns.map(col => `
        <div style="padding:6px 4px;border-bottom:1px solid #f5f5f5;">
            <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin:0;">
                <input type="checkbox"
                       class="col-picker-check"
                       value="${col.key}"
                       ${selectedKeys.includes(col.key) ? 'checked' : ''}
                       style="width:14px;height:14px;cursor:pointer;flex-shrink:0;">
                <span style="font-size:0.9rem;color:#333;">${col.label}</span>
            </label>
        </div>
    `).join('');

    const d = new frappe.ui.Dialog({
        title: __('Pick Columns for Export'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'col_html',
                options: `
                    <div style="margin-bottom:10px;display:flex;gap:8px;">
                        <button class="btn btn-xs btn-default col-select-all"
                                style="padding:4px 10px;">${__('Select All')}</button>
                        <button class="btn btn-xs btn-default col-deselect-all"
                                style="padding:4px 10px;">${__('Deselect All')}</button>
                    </div>
                    <div style="max-height:360px;overflow-y:auto;padding-right:4px;">
                        ${listHtml}
                    </div>
                `
            }
        ],
        primary_action_label: __('Apply'),
        primary_action() {
            const selected = [];
            d.$wrapper.find('.col-picker-check:checked').each(function () {
                selected.push($(this).val());
            });
            if (!selected.length) {
                frappe.show_alert({ message: __('Please select at least one column'), indicator: 'orange' });
                return;
            }
            state.selectedColumns[tabId] = selected;
            d.hide();
            frappe.show_alert({ message: __('Column selection applied'), indicator: 'green' });
        },
    });

    d.show();

    d.$wrapper.find('.col-select-all').on('click', function () {
        d.$wrapper.find('.col-picker-check').prop('checked', true);
    });
    d.$wrapper.find('.col-deselect-all').on('click', function () {
        d.$wrapper.find('.col-picker-check').prop('checked', false);
    });
}

function exportTableToExcel(state, tabId) {
    const filters = getFilters(state);

    let from_date, to_date;
    if (tabId === 'monthly_production_coal' || tabId === 'billet_cutting_amount'
        || tabId === 'weekly_billet_cutting_amount') {
        const fyRange = financialYearRange(getCurrentFinancialYearStart());
        from_date = fyRange.from_date;
        to_date = fyRange.to_date;
    } else {
        from_date = filters.from_date || '';
        to_date = filters.to_date || (filters.from_date ? '' : frappe.datetime.get_today());
    }

    const allColumns = getTableColumns(tabId);
    const selectedKeys = state.selectedColumns[tabId] || allColumns.map(c => c.key);

    const params = {
        tab_id: tabId,
        from_date: from_date,
        to_date: to_date,
        item_code: filters.item_code || '',
        production_plan: filters.production_plan || '',
        machine_name: filters.machine_name || '',
        category_name: filters.category_name || '',
        selected_columns: selectedKeys.join(','),
    };

    const query = Object.keys(params)
        .map(k => `${encodeURIComponent(k)}=${encodeURIComponent(params[k] || '')}`)
        .join('&');

    const url = `/api/method/prakash_steel.api.production_dashboard.export_production_dashboard?${query}`;
    window.open(url, '_blank');
}

function exportTableToPDF(state, tabId, columns, rows) {
    if (!rows || !rows.length) {
        frappe.show_alert({ message: __('No data to export'), indicator: 'orange' });
        return;
    }

    const selectedKeys = state.selectedColumns[tabId] || columns.map(c => c.key);
    const filteredColumns = columns.filter(c => selectedKeys.includes(c.key));

    const header = filteredColumns.map(c => frappe.utils.escape_html(c.label));
    const dataRows = rows.map(r =>
        filteredColumns.map(c => {
            const val = getExportValueByKey(tabId, c.key, r);
            return frappe.utils.escape_html(val == null ? '' : String(val));
        })
    );

    const thead = `<tr>${header.map(h => `<th style="border:1px solid #000;padding:4px;">${h}</th>`).join('')}</tr>`;
    const tbody = dataRows.map(rowArr =>
        `<tr>${rowArr.map(v => `<td style="border:1px solid #000;padding:4px;">${v}</td>`).join('')}</tr>`
    ).join('');

    const title = `${__('Production Dashboard')} - ${__(tabId.replace(/_/g, ' '))}`;
    const html = `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>${title}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 16px; }
        h3 { margin-bottom: 12px; font-size: 14px; }
        table { border-collapse: collapse; width: 100%; font-size: 10px; }
        th { background: #495057; color: #fff; padding: 5px 6px; border: 1px solid #000; text-align: center; white-space: nowrap; }
        td { padding: 4px 6px; border: 1px solid #ccc; text-align: center; }
        tr:nth-child(even) td { background: #f9f9f9; }
        @media print {
            body { margin: 0; }
            button { display: none; }
        }
    </style>
</head>
<body>
    <h3>${title}</h3>
    <table>
        <thead>${thead}</thead>
        <tbody>${tbody}</tbody>
    </table>
    <script>
        window.onload = function () {
            setTimeout(function () { window.print(); }, 250);
        };
    <\/script>
</body>
</html>`;

    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const win = window.open(url, '_blank');
    if (!win) {
        frappe.msgprint(__('Please allow popups to export PDF.'));
        URL.revokeObjectURL(url);
        return;
    }
    // Revoke the object URL after the window has loaded
    win.addEventListener('load', () => URL.revokeObjectURL(url));
}

function buildCSVContent(rows) {
    const escapeCell = (value) => {
        if (value === undefined || value === null) return '';
        const str = String(value);
        if (/[",\n]/.test(str)) {
            return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
    };

    return rows.map(rowArr => rowArr.map(escapeCell).join(',')).join('\n');
}

function getExportValueByKey(tabId, key, row) {
    const fmtDate = (d) => d ? frappe.format(d, { fieldtype: 'Date' }) : '';

    if (tabId === 'rolled_production') {
        const map = {
            production_plan: row.production_plan || '',
            production_date: fmtDate(row.production_date),
            rm: row.rm || '',
            rm_category_name: row.rm_category_name || '',
            rm_consumption: row.rm_consumption || 0,
            billet_pcs: row.billet_pcs || 0,
            description_of_cutting_billet: row.description_of_cutting_billet || '',
            total_raw_material_pcs: row.total_raw_material_pcs || 0,
            total_rm_weight: (parseFloat(row.rm_consumption) || 0) + (parseFloat(row.miss_billet_weight) || 0),
            miss_billet_pcs: row.miss_billet_pcs || 0,
            miss_billet_weight: row.miss_billet_weight || 0,
            heat_no: row.heat_no || '',
            finished_item: row.finished_item || '',
            finished_item_category_name: row.finished_item_category_name || '',
            fg_planned_qty: row.fg_planned_qty || 0,
            actual_qty: row.actual_qty || 0,
            finish_pcs: row.finish_pcs || 0,
            fg_length: row.fg_length || '',
            total_miss_roll_pcs: row.total_miss_roll_pcs || 0,
            total_miss_roll_weight: row.total_miss_roll_weight || 0,
            total_miss_ingot_pcs: row.total_miss_ingot_pcs || 0,
            total_miss_ingot_weight: row.total_miss_ingot_weight || 0,
            melting_weight: row.melting_weight || 0,
            burning_loss: row.burning_loss || 0,
            melting_wastage: row.melting_wastage || 0,
            finish_goods: row.finish_goods || 0,
            total_hr_consumed: row.total_hr_consumed || 0,
        };
        return map[key] !== undefined ? map[key] : '';
    }

    if (tabId === 'bend_weight_details') {
        const map = {
            id: row.id || row.name || '',
            item_code: row.item_code || '',
            category_name: row.category_name || '',
            bend_material_weight: row.bend_material_weight || 0,
        };
        return map[key] !== undefined ? map[key] : '';
    }

    if (tabId === 'coal_consumption') {
        const map = {
            date: fmtDate(row.date),
            item: row.item || '',
            qty: row.qty || 0,
            uom: row.uom || '',
        };
        return map[key] !== undefined ? map[key] : '';
    }

    if (tabId === 'hourly_production') {
        const map = {
            date: fmtDate(row.date),
            hours: row.hours || 0,
        };
        return map[key] !== undefined ? map[key] : '';
    }

    if (tabId === 'monthly_production_coal') {
        const map = {
            month: row.month || '',
            total_production: row.total_production || 0,
            total_coal_consumption: row.total_coal_consumption || 0,
            per_ton_coal_consumption: row.per_ton_coal_consumption || 0,
        };
        return map[key] !== undefined ? map[key] : '';
    }

    if (tabId === 'billet_cutting_amount') {
        const map = {
            month: row.month || '',
            fc_qty: row.fc_qty || 0,
            fc_amount: row.fc_amount || 0,
            hf_qty: row.hf_qty || 0,
            hf_amount: row.hf_amount || 0,
            gc_qty: row.gc_qty || 0,
            gc_amount: row.gc_amount || 0,
            fcn_qty: row.fcn_qty || 0,
            fcn_amount: row.fcn_amount || 0,
            total_qty: row.total_qty || 0,
            total_amount: row.total_amount || 0,
        };
        return map[key] !== undefined ? map[key] : '';
    }

    if (tabId === 'weekly_billet_cutting_amount') {
        const map = {
            weeks_from: row.weeks_from || '',
            weeks_to: row.weeks_to || '',
            fc_qty: row.fc_qty || 0,
            fc_amount: row.fc_amount || 0,
            hf_qty: row.hf_qty || 0,
            hf_amount: row.hf_amount || 0,
            gc_qty: row.gc_qty || 0,
            gc_amount: row.gc_amount || 0,
            fcn_qty: row.fcn_qty || 0,
            fcn_amount: row.fcn_amount || 0,
            total_qty: row.total_qty || 0,
            total_amount: row.total_amount || 0,
        };
        return map[key] !== undefined ? map[key] : '';
    }

    // bright_production
    const map = {
        production_plan: row.production_plan || '',
        production_date: fmtDate(row.production_date),
        rm: row.rm || '',
        rm_category_name: row.rm_category_name || '',
        rm_consumption: row.rm_consumption || 0,
        machine_name: row.machine_name || '',
        finished_item: row.finished_item || '',
        finished_item_category_name: row.finished_item_category_name || '',
        fg_planned_qty: row.fg_planned_qty || 0,
        actual_qty: row.actual_qty || 0,
        finish_length: row.finish_length || '',
        tolerance: row.tolerance || 0,
        end_cutting_weight: row.end_cutting_weight || 0,
        wastage: row.wastage || 0,
    };
    return map[key] !== undefined ? map[key] : '';
}

function mapRowForExport(tabId, row) {
    if (tabId === 'rolled_production') {
        return [
            row.production_plan || '',
            row.production_date
                ? frappe.format(row.production_date, { fieldtype: 'Date' })
                : '',
            row.rm || '',
            row.rm_category_name || '',
            row.rm_consumption || 0,
            row.billet_pcs || 0,
            row.description_of_cutting_billet || '',
            row.total_raw_material_pcs || 0,
            (row.rm_consumption || 0) + (row.miss_billet_weight || 0),
            row.miss_billet_pcs || 0,
            row.miss_billet_weight || 0,
            row.heat_no || '',
            row.finished_item || '',
            row.finished_item_category_name || '',
            row.fg_planned_qty || 0,
            row.actual_qty || 0,
            row.finish_pcs || 0,
            row.fg_length || '',
            row.total_miss_roll_pcs || 0,
            row.total_miss_roll_weight || 0,
            row.total_miss_ingot_pcs || 0,
            row.total_miss_ingot_weight || 0,
            row.melting_weight || 0,
            row.burning_loss || 0,
            row.melting_wastage || 0,
            row.finish_goods || 0,
            row.total_hr_consumed || 0,
        ];
    }

    if (tabId === 'bend_weight_details') {
        return [
            row.id || row.name || '',
            row.item_code || '',
            row.category_name || '',
            row.bend_material_weight || 0,
        ];
    }

    if (tabId === 'coal_consumption') {
        return [
            row.date
                ? frappe.format(row.date, { fieldtype: 'Date' })
                : '',
            row.item || '',
            row.qty || 0,
            row.uom || '',
        ];
    }

    if (tabId === 'hourly_production') {
        return [
            row.date
                ? frappe.format(row.date, { fieldtype: 'Date' })
                : '',
            row.hours || 0,
        ];
    }

    // bright_production
    return [
        row.production_plan || '',
        row.production_date
            ? frappe.format(row.production_date, { fieldtype: 'Date' })
            : '',
        row.rm || '',
        row.rm_category_name || '',
        row.machine_name || '',
        row.finished_item || '',
        row.finished_item_category_name || '',
        row.fg_planned_qty || 0,
        row.rm_consumption || 0,
        row.actual_qty || 0,
        row.finish_length || '',
        row.tolerance || 0,
        row.wastage || 0,
    ];
}