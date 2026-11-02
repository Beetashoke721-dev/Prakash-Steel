// Copyright (c) 2026, Prakash Steel and contributors
// For license information, please see license.txt

if (!frappe.pages['md-dashboard']) {
	frappe.pages['md-dashboard'] = {};
}

frappe.pages['md-dashboard'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('M.D Dashboard (Avinash Bagla)'),
		single_column: true,
	});

	page.main.empty();
	page.main.css({ paddingTop: "8px", paddingBottom: "12px" });
	injectMdDashboardStyles();
	page.main.html(MD_DASHBOARD_HTML);
	initMdDashboard();
};

frappe.pages['md-dashboard'].on_page_show = function () {};

function injectMdDashboardStyles() {
	var style = document.getElementById('md-dashboard-styles');
	if (!style) {
		style = document.createElement('style');
		style.id = 'md-dashboard-styles';
		document.head.appendChild(style);
	}
	style.textContent = MD_DASHBOARD_CSS;
}

const MD_DASHBOARD_HTML = `<div class="md-dash" id="md-dashboard-root">
  <nav class="md-dash__main-tabs" role="tablist">
    <button type="button" class="md-main-tab is-active" data-main="purchase">Purchase</button>
    <button type="button" class="md-main-tab" data-main="sale">Sale</button>
    <button type="button" class="md-main-tab" data-main="inventory">Inventory</button>
    <button type="button" class="md-main-tab" data-main="production">Production</button>
  </nav>
  <section class="md-main-panel is-active" data-main="purchase">
    <div class="md-chart-head-row">
      <h2>Purchase Overview</h2>
      <button type="button" class="md-dash__btn" data-chart-refresh="purchase">Refresh Charts</button>
    </div>
    <div class="md-chart-grid" data-chart-grid="purchase">
      <div class="md-chart-card">
        <div class="md-chart-head"><h3>Purchase Trend in <span class="md-cr-highlight">₹ Cr</span> (Last 6 Months)</h3></div>
        <div class="md-chart" data-chart="purchase_trend">Loading…</div>
      </div>
      <div class="md-chart-card">
        <div class="md-chart-head md-chart-head--amber"><h3>Top 5 Suppliers (based on qty)</h3></div>
        <div class="md-table-wrap md-table-wrap--compact" data-table="purchase_top_suppliers">Loading…</div>
      </div>
    </div>
    <nav class="md-dash__sub-tabs">
      <button type="button" class="md-sub-tab is-active" data-sub="open_mr">Open MR for Purchase</button>
      <button type="button" class="md-sub-tab" data-sub="open_po">Open PO</button>
      <button type="button" class="md-sub-tab" data-sub="pending_pi">Pending Approval PI</button>
      <button type="button" class="md-sub-tab" data-sub="grade_avg_purchase_rate">Grade wise average purchase rate</button>
      <button type="button" class="md-sub-tab" data-sub="accounts_payable">Accounts Payable List</button>
      <button type="button" class="md-sub-tab" data-sub="advance_paid">Advanced Paid list in Purchase</button>
    </nav>

    <div class="md-sub-panel is-active" data-sub="open_mr">
      <div class="md-report-head">
        <div>
          <h2>Open MR for Purchase</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="open_mr">Refresh</button>
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="open_mr">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="open_po">
      <div class="md-report-head">
        <div>
          <h2>Open PO</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="open_po">Refresh</button>
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="open_po">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="pending_pi">
      <div class="md-report-head">
        <div>
          <h2>Pending Approval PI</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="pending_pi">Refresh</button>
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="pending_pi">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="grade_avg_purchase_rate">
      <div class="md-report-head">
        <div>
          <h2>Grade wise average purchase rate</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="grade_avg_purchase_rate">Refresh</button>
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="grade_avg_purchase_rate">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="accounts_payable">
      <div class="md-report-head">
        <div>
          <h2>Accounts Payable List</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="accounts_payable">Refresh</button>
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="accounts_payable">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="advance_paid">
      <div class="md-report-head">
        <div>
          <h2>Advanced Paid list in Purchase</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="advance_paid">Refresh</button>
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="advance_paid">Loading…</div>
    </div>
  </section>
  <section class="md-main-panel" data-main="sale">
    <div class="md-chart-head-row">
      <h2>Sale Overview</h2>
      <button type="button" class="md-dash__btn" data-chart-refresh="sale">Refresh Charts</button>
    </div>
    <div class="md-chart-grid" data-chart-grid="sale">
      <div class="md-chart-card">
        <div class="md-chart-head"><h3>Sales Trend in <span class="md-cr-highlight">₹ Cr</span> (Last 6 Months)</h3></div>
        <div class="md-chart" data-chart="sale_trend">Loading…</div>
      </div>
      <div class="md-chart-card">
        <div class="md-chart-head md-chart-head--teal"><h3>Top 5 Customers (based on qty)</h3></div>
        <div class="md-table-wrap md-table-wrap--compact" data-table="sale_top_customers">Loading…</div>
      </div>
    </div>
    <nav class="md-dash__sub-tabs">
      <button type="button" class="md-sub-tab is-active" data-sub="open_so">Open SO</button>
      <button type="button" class="md-sub-tab" data-sub="cn_dn_pending">Credit Note &amp; Debit Note Pending Approval</button>
      <button type="button" class="md-sub-tab" data-sub="accounts_receivable">Accounts Receivable List</button>
      <button type="button" class="md-sub-tab" data-sub="advance_received">Advanced Received list in Sales</button>
      <button type="button" class="md-sub-tab" data-sub="grade_avg_selling">Grade wise Average Selling Qty &amp; Amount</button>
      <button type="button" class="md-sub-tab" data-sub="weekly_throughput">Weekly Throughput</button>
    </nav>

    <div class="md-sub-panel is-active" data-sub="open_so">
      <div class="md-report-head">
        <div>
          <h2>Open SO</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="open_so">Refresh</button>
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="open_so">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="cn_dn_pending">
      <div class="md-report-head">
        <div>
          <h2>Credit Note &amp; Debit Note Pending Approval</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="cn_dn_pending">Refresh</button>
          
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="cn_dn_pending">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="accounts_receivable">
      <div class="md-report-head">
        <div>
          <h2>Accounts Receivable List</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="accounts_receivable">Refresh</button>
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="accounts_receivable">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="advance_received">
      <div class="md-report-head">
        <div>
          <h2>Advanced Received list in Sales</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="advance_received">Refresh</button>
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="advance_received">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="grade_avg_selling">
      <div class="md-report-head">
        <div>
          <h2>Grade wise Average Selling Qty &amp; Amount</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="grade_avg_selling">Refresh</button>
          
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="grade_avg_selling">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="weekly_throughput">
      <div class="md-report-head">
        <div>
          <h2>Weekly Throughput</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="weekly_throughput">Refresh</button>
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="weekly_throughput">Loading…</div>
    </div>
  </section>
  <section class="md-main-panel" data-main="inventory">
    <div class="md-chart-head-row">
      <h2>Inventory Overview</h2>
      <button type="button" class="md-dash__btn" data-chart-refresh="inventory">Refresh Charts</button>
    </div>
    <div class="md-chart-grid" data-chart-grid="inventory">
      <div class="md-chart-card">
        <div class="md-chart-head md-chart-head--teal"><h3>Top 5 Selling Items (based on qty)</h3></div>
        <div class="md-table-wrap md-table-wrap--compact" data-table="inventory_top_sale_items">Loading…</div>
      </div>
      <div class="md-chart-card">
        <div class="md-chart-head md-chart-head--amber"><h3>Top 5 Purchase Items (based on qty)</h3></div>
        <div class="md-table-wrap md-table-wrap--compact" data-table="inventory_top_purchase_items">Loading…</div>
      </div>
    </div>
    <nav class="md-dash__sub-tabs">
      <button type="button" class="md-sub-tab is-active" data-sub="inventory_ageing">Inventory Ageing (30, 60, 90, 120+)</button>
      <button type="button" class="md-sub-tab" data-sub="grade_wise_inventory">Grade wise Inventory</button>
      <button type="button" class="md-sub-tab" data-sub="bright_shape_wise">Shape wise (Bright Item)</button>
    </nav>

    <div class="md-sub-panel is-active" data-sub="inventory_ageing">
      <div class="md-report-head">
        <div>
          <h2>Inventory Ageing (30, 60, 90, 120+)</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="inventory_ageing">Refresh</button>
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="inventory_ageing">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="grade_wise_inventory">
      <div class="md-report-head">
        <div>
          <h2>Grade wise Inventory</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="grade_wise_inventory">Refresh</button>
          
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="grade_wise_inventory">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="bright_shape_wise">
      <div class="md-report-head">
        <div>
          <h2>Shape wise (Bright Item) — Flat, Sq., Round, Hex</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="bright_shape_wise">Refresh</button>
          
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="bright_shape_wise">Loading…</div>
    </div>
  </section>
  <section class="md-main-panel" data-main="production">
    <nav class="md-dash__sub-tabs">
      <button type="button" class="md-sub-tab is-active" data-sub="rolled_production">Rolled Production</button>
      <button type="button" class="md-sub-tab" data-sub="hourly_production">Hourly Production</button>
      <button type="button" class="md-sub-tab" data-sub="bright_production">Bright Production</button>
      <button type="button" class="md-sub-tab" data-sub="bend_weight_details">Bend Weight Details</button>
      <button type="button" class="md-sub-tab" data-sub="coal_consumption">Coal Consumption</button>
      <button type="button" class="md-sub-tab" data-sub="monthly_production_coal">Monthly Production With Coal Consumption</button>
      <button type="button" class="md-sub-tab" data-sub="billet_cutting_amount">Monthly Billet Cutting Amount</button>
      <button type="button" class="md-sub-tab" data-sub="weekly_billet_cutting_amount">Weekly Billet Cutting Amount</button>
    </nav>

    <div class="md-sub-panel is-active" data-sub="rolled_production">
      <div class="md-report-head">
        <div>
          <h2>Rolled Production</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="rolled_production">Refresh</button>
        </div>
      </div>
      <div class="md-kpi-cards" data-kpi="rolled_production"></div>
      <div class="md-table-wrap" data-table="rolled_production">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="hourly_production">
      <div class="md-report-head">
        <div>
          <h2>Hourly Production</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="hourly_production">Refresh</button>
        </div>
      </div>
      <div class="md-kpi-cards" data-kpi="hourly_production"></div>
      <div class="md-table-wrap" data-table="hourly_production">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="bright_production">
      <div class="md-report-head">
        <div>
          <h2>Bright Production</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="bright_production">Refresh</button>
        </div>
      </div>
      <div class="md-kpi-cards" data-kpi="bright_production"></div>
      <div class="md-table-wrap" data-table="bright_production">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="bend_weight_details">
      <div class="md-report-head">
        <div>
          <h2>Bend Weight Details</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="bend_weight_details">Refresh</button>
        </div>
      </div>
      
      <div class="md-table-wrap" data-table="bend_weight_details">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="coal_consumption">
      <div class="md-report-head">
        <div>
          <h2>Coal Consumption</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="coal_consumption">Refresh</button>
        </div>
      </div>
      <div class="md-table-wrap" data-table="coal_consumption">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="monthly_production_coal">
      <div class="md-report-head">
        <div>
          <h2>Monthly Production With Coal Consumption</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="monthly_production_coal">Refresh</button>
        </div>
      </div>
      <div class="md-table-wrap" data-table="monthly_production_coal">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="billet_cutting_amount">
      <div class="md-report-head">
        <div>
          <h2>Monthly Billet Cutting Amount</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="billet_cutting_amount">Refresh</button>
        </div>
      </div>
      <div class="md-table-wrap" data-table="billet_cutting_amount">Loading…</div>
    </div>
    <div class="md-sub-panel" data-sub="weekly_billet_cutting_amount">
      <div class="md-report-head">
        <div>
          <h2>Weekly Billet Cutting Amount</h2>
        </div>
        <div class="md-report-actions">
          <button type="button" class="md-dash__btn" data-refresh="weekly_billet_cutting_amount">Refresh</button>
        </div>
      </div>
      <div class="md-table-wrap" data-table="weekly_billet_cutting_amount">Loading…</div>
    </div>
  </section>
</div>`;

const MD_DASHBOARD_CSS = `/* =============================================================================
   M.D Dashboard (Avinash Bagla) — Builder Client CSS
   Route: /md-dashboard-avinash-bagla
   ============================================================================= */


/* -----------------------------------------------------------------------------
   Layout shell
   ----------------------------------------------------------------------------- */
.md-dash {
	width: 100%;
	max-width: none;
	margin: 0 auto;
	padding: 0 12px 12px;
	font-family: Inter, system-ui, -apple-system, sans-serif;
	color: #1f2937;
}


/* -----------------------------------------------------------------------------
   Main tabs — Purchase | Sale | Inventory | Production
   ----------------------------------------------------------------------------- */
.md-dash__main-tabs {
	display: flex;
	gap: 6px;
	flex-wrap: wrap;
	border-bottom: 2px solid #e5e7eb;
	margin-bottom: 8px;
}

.md-main-tab {
	border: 0;
	background: transparent;
	padding: 8px 14px;
	font-size: 15px;
	font-weight: 600;
	color: #6b7280;
	cursor: pointer;
	border-bottom: 2px solid transparent;
	margin-bottom: -2px;
}

.md-main-tab.is-active {
	color: #2563eb;
	border-bottom-color: #2563eb;
}

.md-main-panel {
	display: none;
}

.md-main-panel.is-active {
	display: block;
}


/* -----------------------------------------------------------------------------
   Overview charts — one grid per main tab (Purchase / Sale / Inventory / Production)
   ----------------------------------------------------------------------------- */
.md-chart-head-row {
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 8px;
	flex-wrap: wrap;
	margin-bottom: 8px;
}

.md-chart-head-row h2 {
	margin: 0;
	font-size: 16px;
	color: #111827;
}

.md-chart-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
	gap: 10px;
	margin-bottom: 14px;
}

.md-chart-card {
	background: #fff;
	border: 1px solid #e5e7eb;
	border-radius: 10px;
	padding: 12px 14px;
}

.md-chart-head h3 {
	margin: 0 0 8px;
	font-size: 13px;
	font-weight: 600;
	color: #374151;
}

.md-cr-highlight {
	color: #b45309;
	background: #fef3c7;
	padding: 1px 6px;
	border-radius: 4px;
	font-weight: 700;
}

.md-chart {
	min-height: 240px;
}

.md-chart .md-empty,
.md-chart .md-error {
	padding: 60px 12px;
}

.md-table-wrap--compact {
	border: 0;
	border-radius: 0;
}

.md-table-wrap--compact .dt-scrollable {
	max-height: 280px;
}

/* Item/party name cells — wrap onto a 2nd line instead of clipping, so long
   names (e.g. "WASTAGE SCRAP OF STEEL BARS & RODS SCRAP") stay readable. */
.md-cell-wrap {
	display: -webkit-box;
	-webkit-box-orient: vertical;
	-webkit-line-clamp: 2;
	overflow: hidden;
	white-space: normal;
	word-break: break-word;
	line-height: 1.2;
}

/* Inventory Top 5 tables — every row must be tall enough for the one wrapped
   name, so trim the cell padding to keep the table from growing much. */
[data-table="inventory_top_sale_items"] .dt-cell__content,
[data-table="inventory_top_purchase_items"] .dt-cell__content {
	padding-top: 3px;
	padding-bottom: 3px;
}

/* Grade wise average purchase rate, Grade wise Average Selling Qty & Amount,
   Grade wise Inventory, Shape wise (Bright Item), Hourly Production, Coal
   Consumption — force every column to be centered (both header and body
   cells), overriding DataTable's own left/right defaults regardless of
   column order/index. */
[data-table="grade_avg_purchase_rate"] .dt-cell__content,
[data-table="grade_avg_selling"] .dt-cell__content,
[data-table="grade_wise_inventory"] .dt-cell__content,
[data-table="bright_shape_wise"] .dt-cell__content,
[data-table="hourly_production"] .dt-cell__content,
[data-table="coal_consumption"] .dt-cell__content,
[data-table="monthly_production_coal"] .dt-cell__content,
[data-table="billet_cutting_amount"] .dt-cell__content,
[data-table="weekly_billet_cutting_amount"] .dt-cell__content {
	text-align: center !important;
	justify-content: center !important;
}

/* Billet Cutting Amount tables — keep full column headings; scroll sideways. */
[data-table="billet_cutting_amount"],
[data-table="weekly_billet_cutting_amount"] {
	overflow-x: auto;
}

[data-table="billet_cutting_amount"] .datatable,
[data-table="weekly_billet_cutting_amount"] .datatable {
	min-width: max-content;
}

[data-table="billet_cutting_amount"] .dt-cell--header .dt-cell__content,
[data-table="weekly_billet_cutting_amount"] .dt-cell--header .dt-cell__content {
	overflow: visible;
	text-overflow: unset;
	white-space: nowrap;
}

/* Top 5 Purchase/Sale Items — highlighted card heading */
.md-chart-head--amber {
	background: #f59e0b;
	margin: -12px -14px 8px;
	padding: 10px 14px;
	border-radius: 10px 10px 0 0;
}

.md-chart-head--amber h3 {
	color: #fff;
}

.md-chart-head--teal {
	background: #0d9488;
	margin: -12px -14px 8px;
	padding: 10px 14px;
	border-radius: 10px 10px 0 0;
}

.md-chart-head--teal h3 {
	color: #fff;
}


/* -----------------------------------------------------------------------------
   Sub-tabs (pill buttons inside each main section)
   ----------------------------------------------------------------------------- */
.md-dash__sub-tabs {
	display: flex;
	flex-wrap: wrap;
	gap: 6px;
	margin-bottom: 8px;
}

/* Production tab — keep all sub-tabs on one line with a horizontal scrollbar
   instead of wrapping onto multiple rows. */
.md-main-panel[data-main="production"] .md-dash__sub-tabs {
	flex-wrap: nowrap;
	overflow-x: auto;
	overflow-y: hidden;
	-webkit-overflow-scrolling: touch;
	padding-bottom: 6px;
}

.md-main-panel[data-main="production"] .md-sub-tab {
	flex: 0 0 auto;
	white-space: nowrap;
}

.md-sub-tab {
	border: 1px solid #d1d5db;
	background: #fff;
	color: #374151;
	border-radius: 999px;
	padding: 5px 12px;
	font-size: 13px;
	cursor: pointer;
}

.md-sub-tab.is-active {
	background: #2563eb;
	border-color: #2563eb;
	color: #fff;
}


/* -----------------------------------------------------------------------------
   Sub-panels (one per sub-tab — Purchase / Sale / Inventory / Production)
   ----------------------------------------------------------------------------- */
.md-sub-panel {
	display: none;
	min-height: 280px;
	border: 1px solid #e5e7eb;
	border-radius: 10px;
	padding: 12px 14px;
	background: #fff;
}

.md-sub-panel.is-active {
	display: block;
}

.md-sub-panel h2 {
	margin: 0 0 4px;
	font-size: 17px;
}

.md-sub-panel p {
	margin: 0 0 12px;
	color: #6b7280;
	font-size: 14px;
}


/* -----------------------------------------------------------------------------
   Report header — title, row count, Refresh, external link
   ----------------------------------------------------------------------------- */
.md-report-head {
	display: flex;
	justify-content: space-between;
	gap: 8px;
	align-items: center;
	flex-wrap: wrap;
	margin-bottom: 6px;
}

.md-report-actions {
	display: flex;
	gap: 8px;
	align-items: center;
	flex-wrap: wrap;
}

.md-dash__btn {
	border: 1px solid #d1d5db;
	background: #fff;
	color: #111827;
	border-radius: 8px;
	padding: 8px 12px;
	font-size: 13px;
	font-weight: 600;
	cursor: pointer;
}



/* -----------------------------------------------------------------------------
   Data tables (all tabs) — Frappe DataTable with column filters
   ----------------------------------------------------------------------------- */
.md-table-wrap {
	overflow: auto;
	border: 1px solid #e5e7eb;
	border-radius: 8px;
	background: #fff;
}

.md-table-wrap .datatable {
	font-size: 13px;
	min-width: 100%;
}

.md-table-wrap .dt-scrollable {
	max-height: 65vh;
	overflow: auto !important;
}

.md-table-wrap .dt-cell__content {
	white-space: nowrap;
	overflow: hidden;
	text-overflow: clip;
}

.md-table-wrap .dt-cell a {
	color: #2563eb;
	text-decoration: none;
	font-weight: 600;
	white-space: nowrap;
}

.md-table-wrap .dt-row-filter .dt-filter {
	width: 100%;
	min-width: 0;
	box-sizing: border-box;
}


/* -----------------------------------------------------------------------------
   Special cell styles — MR colour badges (Purchase > Open MR)
   ----------------------------------------------------------------------------- */
.md-colour {
	display: inline-block;
	padding: 2px 10px;
	border-radius: 4px;
	font-weight: 700;
}

.md-status-badge {
	display: inline-block;
	min-width: 72px;
	padding: 4px 8px;
	border-radius: 0;
	font-weight: 700;
	text-align: center;
	line-height: 1.2;
}


/* -----------------------------------------------------------------------------
   Rank badges — Purchase/Sale > Top 5 Items table
   ----------------------------------------------------------------------------- */
.md-rank-badge {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	width: 22px;
	height: 22px;
	border-radius: 50%;
	font-weight: 700;
	font-size: 12px;
	line-height: 1;
}


/* -----------------------------------------------------------------------------
   Empty / error / loading states
   ----------------------------------------------------------------------------- */
.md-empty,
.md-error {
	padding: 24px;
	text-align: center;
	color: #6b7280;
}

.md-error {
	color: #b91c1c;
}


/* -----------------------------------------------------------------------------
   Production tab — KPI summary cards
   (Rolled Production, Bright Production, Coal Consumption)
   ----------------------------------------------------------------------------- */
.md-kpi-cards {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
	gap: 8px;
	margin-bottom: 8px;
}

.md-kpi-card {
	position: relative;
	background: #fff;
	border: 1px solid #e5e7eb;
	border-radius: 10px;
	padding: 14px 16px;
	min-height: 88px;
	overflow: hidden;
	box-shadow: none;
}

.md-kpi-card::before,
.md-kpi-card::after {
	content: "";
	position: absolute;
	pointer-events: none;
}

.md-kpi-card::before {
	left: 0;
	top: 0;
	bottom: 0;
	width: 4px;
}

.md-kpi-card::after {
	left: 0;
	top: 0;
	right: 0;
	height: 4px;
}

.md-kpi-card--blue::before {
	background: linear-gradient(180deg, #a8c8f0, #c4d9f5);
}

.md-kpi-card--blue::after {
	background: linear-gradient(90deg, #a8c8f0, #c4d9f5);
}

.md-kpi-card--teal::before {
	background: linear-gradient(180deg, #7dd3c0, #a3e4d4);
}

.md-kpi-card--teal::after {
	background: linear-gradient(90deg, #7dd3c0, #a3e4d4);
}

.md-kpi-card--yellow::before {
	background: linear-gradient(180deg, #d4a574, #e8d5b7);
}

.md-kpi-card--yellow::after {
	background: linear-gradient(90deg, #d4a574, #e8d5b7);
}

.md-kpi-card--red::before {
	background: linear-gradient(180deg, #f5a5a0, #f8b8b3);
}

.md-kpi-card--red::after {
	background: linear-gradient(90deg, #f5a5a0, #f8b8b3);
}

.md-kpi-card--green::before {
	background: linear-gradient(180deg, #85e0a8, #a8ecc4);
}

.md-kpi-card--green::after {
	background: linear-gradient(90deg, #85e0a8, #a8ecc4);
}

.md-kpi-card--orange::before {
	background: linear-gradient(180deg, #fdd085, #fde0a8);
}

.md-kpi-card--orange::after {
	background: linear-gradient(90deg, #fdd085, #fde0a8);
}

.md-kpi-card--purple::before {
	background: linear-gradient(180deg, #c9a5d9, #d9b8e6);
}

.md-kpi-card--purple::after {
	background: linear-gradient(90deg, #c9a5d9, #d9b8e6);
}

.md-kpi-card--pink::before {
	background: linear-gradient(180deg, #f8c8d8, #fce0e8);
}

.md-kpi-card--pink::after {
	background: linear-gradient(90deg, #f8c8d8, #fce0e8);
}

.md-kpi-value {
	font-size: 22px;
	font-weight: 700;
	color: #111827;
	margin-bottom: 6px;
	line-height: 1.1;
	text-align: center;
	position: relative;
	z-index: 1;
}

.md-kpi-label {
	font-size: 13px;
	color: #6b7280;
	font-weight: 600;
	text-align: center;
	position: relative;
	z-index: 1;
}
`;

/**
 * M.D Dashboard (Avinash Bagla) — Builder Client Script
 * Route: /app/md-dashboard
 *
 * Structure:
 *   1. Global state
 *   2. Shared utilities (API, dates, company)
 *   3. Shared UI helpers (table render, loading, errors)
 *   4. Sale tab — custom loaders
 *   5. Inventory tab — custom loaders
 *   6. Production tab — APIs, columns, KPIs
 *   7. TAB_LOADERS — one entry per data-sub id
 *   8. Navigation & init
 */
	// =========================================================================
	// GLOBAL STATE
	// =========================================================================
	var COLOUR_STYLES = {
		Black: { bg: "#222", fg: "#fff" },
		Red: { bg: "#e74c3c", fg: "#fff" },
		Yellow: { bg: "#f1c40f", fg: "#333" },
		Green: { bg: "#27ae60", fg: "#fff" },
		White: { bg: "#e8e8e8", fg: "#333" },
	};

	// Open SO Analysis paints these cells in its own report formatter, which the
	// dashboard bypasses (it reads the report's raw data). Mirror those colours.
	var ORDER_STATUS_STYLES = {
		black: { bg: "#000000", fg: "#ffffff" },
		white: { bg: "#ffffff", fg: "#000000" },
		green: { bg: "#4dff88", fg: "#000000" },
		yellow: { bg: "#ffff99", fg: "#000000" },
		red: { bg: "#ff9999", fg: "#000000" },
	};

	var FULLKIT_STYLES = {
		"full-kit": { bg: "#4dff88", fg: "#000000" },
		partial: { bg: "#ffff99", fg: "#000000" },
		pending: { bg: "#ff9999", fg: "#000000" },
	};

	/** Top 5 Purchase/Sale Items — rank badge colours (gold/silver/bronze, then blue/teal). */
	var RANK_STYLES = {
		1: { bg: "#f59e0b", fg: "#fff" },
		2: { bg: "#94a3b8", fg: "#fff" },
		3: { bg: "#b45309", fg: "#fff" },
		4: { bg: "#2563eb", fg: "#fff" },
		5: { bg: "#0d9488", fg: "#fff" },
		6: { bg: "#7c3aed", fg: "#fff" },
		7: { bg: "#db2777", fg: "#fff" },
		8: { bg: "#16a34a", fg: "#fff" },
		9: { bg: "#0891b2", fg: "#fff" },
		10: { bg: "#64748b", fg: "#fff" },
	};

	/** Tracks which sub-tabs have already loaded (skip re-fetch unless Refresh). */
	var loaded = {};

	/** Active Frappe DataTable instances keyed by sub-tab id. */
	var dataTables = {};

	/** Cached default company name. */
	var companyCache = null;


	// =========================================================================
	// SHARED UTILITIES — used by all tabs
	// =========================================================================
	function getCsrfToken() {
		if (window.csrf_token) return window.csrf_token;
		if (window.frappe && frappe.csrf_token) return frappe.csrf_token;
		var match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
		return match ? decodeURIComponent(match[1]) : "";
	}

	function todayISO() {
		return new Date().toISOString().slice(0, 10);
	}

	function addMonthsISO(months) {
		var d = new Date();
		d.setMonth(d.getMonth() + months);
		return d.toISOString().slice(0, 10);
	}

	function addDaysISO(days) {
		var d = new Date();
		d.setDate(d.getDate() + days);
		return d.toISOString().slice(0, 10);
	}

	function escapeHtml(value) {
		if (value === null || value === undefined) return "";
		return String(value)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	/** POST to /api/method/<method> with CSRF token. */
	function api(method, args) {
		return fetch("/api/method/" + method, {
			method: "POST",
			credentials: "same-origin",
			headers: {
				"Content-Type": "application/json",
				"X-Frappe-CSRF-Token": getCsrfToken(),
				Accept: "application/json",
			},
			body: JSON.stringify(args || {}),
		}).then(function (res) {
			return res.json().then(function (body) {
				return { ok: res.ok, body: body };
			});
		});
	}

	function getCompany() {
		if (companyCache) return Promise.resolve(companyCache);

		return api("frappe.defaults.get_user_default", { key: "Company" }).then(function (result) {
			if (result.ok && result.body.message) {
				companyCache = result.body.message;
				return companyCache;
			}

			return api("frappe.client.get_list", {
				doctype: "Company",
				fields: ["name"],
				limit_page_length: 1,
			}).then(function (r2) {
				companyCache =
					(r2.body.message && r2.body.message[0] && r2.body.message[0].name) || "";
				return companyCache;
			});
		});
	}

	/** Convert query-report array rows into plain objects. */
	function normalizeReportRows(columns, rows) {
		if (!rows || !rows.length) return [];

		if (Array.isArray(rows[0])) {
			return rows.map(function (arr) {
				var obj = {};
				columns.forEach(function (col, idx) {
					var key = (col && col.fieldname) || "col_" + idx;
					obj[key] = arr[idx];
				});
				return obj;
			});
		}

		return rows.filter(function (row) {
			return row && typeof row === "object";
		});
	}

	function formatNum(value) {
		var num = Number(value);
		if (isNaN(num)) return escapeHtml(value);
		return escapeHtml(num.toLocaleString("en-IN", { maximumFractionDigits: 2 }));
	}

	function formatPct(value) {
		var num = Number(value);
		if (isNaN(num)) return escapeHtml(value);
		return escapeHtml(num.toLocaleString("en-IN", { maximumFractionDigits: 2 })) + "%";
	}

	/** Batch-fetch Item fields (grade, shape) in chunks of 100. */
	function fetchItemFields(itemCodes, fields) {
		var unique = Array.from(new Set((itemCodes || []).filter(Boolean)));
		if (!unique.length) return Promise.resolve({});

		var chunks = [];
		for (var i = 0; i < unique.length; i += 100) {
			chunks.push(unique.slice(i, i + 100));
		}

		var map = {};
		var chain = Promise.resolve();

		chunks.forEach(function (chunk) {
			chain = chain.then(function () {
				return api("frappe.client.get_list", {
					doctype: "Item",
					fields: ["name"].concat(fields || []),
					filters: { name: ["in", chunk] },
					limit_page_length: chunk.length,
				}).then(function (result) {
					if (!result.ok) return;
					(result.body.message || []).forEach(function (item) {
						map[item.name] = item;
					});
				});
			});
		});

		return chain.then(function () {
			return map;
		});
	}


	// =========================================================================
	// SHARED UI HELPERS — table render, loading, errors
	// =========================================================================
	function stripHtml(value) {
		if (value === null || value === undefined) return "";
		var text = String(value);
		if (text.indexOf("<") === -1) return text;
		var tmp = document.createElement("div");
		tmp.innerHTML = text;
		return (tmp.textContent || tmp.innerText || "").replace(/\s+/g, " ").trim();
	}

	/** Format API dates (YYYY-MM-DD[ HH:MM:SS]) as dd/mm/yyyy. Returns null if not a date. */
	function formatDateDdMmYy(value, includeTime) {
		if (value === null || value === undefined || value === "") return null;
		var s = String(value).trim();
		var m = s.match(
			/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/
		);
		if (!m) return null;
		var formatted = m[3] + "/" + m[2] + "/" + m[1];
		if (includeTime && m[4] !== undefined) {
			formatted += " " + m[4] + ":" + m[5];
		}
		return formatted;
	}

	function isDateLikeField(column, field) {
		var ft = column && column.fieldtype;
		if (ft === "Date" || ft === "Datetime") return true;
		return typeof field === "string" && /(^|_)date$/i.test(field);
	}

	function displayText(value, column, field) {
		if (value === null || value === undefined) return "";
		if (isDateLikeField(column, field)) {
			var asDate = formatDateDdMmYy(value, column && column.fieldtype === "Datetime");
			if (asDate) return asDate;
		}
		if (typeof value === "number") {
			return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
		}
		return stripHtml(value);
	}

	// Width estimation constants, derived from the DataTable stylesheet at 13px:
	// body cells pad 8px + 2px border per side; headers swap the right pad for
	// 1rem to clear the sort/filter toggle, and render bold (wider per character).
	var CELL_CHROME = 20;
	var HEADER_CHROME = 28;
	var CHAR_PX = 7.6;
	var HEADER_CHAR_PX = 8.1;
	var MIN_COL_WIDTH = 52;
	var MAX_COL_WIDTH = 420;

	/** Longest rendered text in a column, in characters (cheap — avoids the DOM for plain values). */
	function longestCellLength(col, field, rows) {
		var longest = 0;

		(rows || []).forEach(function (row) {
			var raw = row && field ? row[field] : null;
			if (raw === null || raw === undefined || raw === "") return;

			var len;
			if (typeof raw === "string" && raw.indexOf("<") === -1 && !isDateLikeField(col, field)) {
				len = raw.length;
			} else {
				len = displayText(raw, col, field).length;
			}

			if (len > longest) longest = len;
		});

		return longest;
	}

	var scrollbarWidthCache = null;

	/** Width the browser gives a scrollbar (0 on overlay-scrollbar platforms). */
	function scrollbarWidth() {
		if (scrollbarWidthCache !== null) return scrollbarWidthCache;

		var probe = document.createElement("div");
		probe.style.cssText =
			"position:absolute;top:-9999px;width:100px;height:100px;overflow:scroll;";
		document.body.appendChild(probe);
		scrollbarWidthCache = probe.offsetWidth - probe.clientWidth;
		document.body.removeChild(probe);

		return scrollbarWidthCache;
	}

	/**
	 * Grows columns so they span the full table width instead of leaving a gap
	 * on the right. DataTable's own "fluid" layout can't do this for us — it only
	 * stretches columns flagged `resizable`, and ours are locked.
	 *
	 * opts.equalWidths — give every column the same share (e.g. Grade / Avg Rate).
	 * Otherwise the leftover width goes to the last column.
	 */
	function fillRemainingWidth(mount, dtColumns, opts) {
		opts = opts || {};
		if (!dtColumns.length) return;

		// 0 while the panel is still hidden — fall back to natural widths.
		var available = mount.clientWidth;
		if (!available) return;

		// Reserve the vertical scrollbar (the body scrolls once rows overflow) plus
		// a couple of px, so filling the row can never add a horizontal scrollbar.
		var usable = available - scrollbarWidth() - 2;
		if (usable <= 0) return;

		if (opts.equalWidths) {
			var each = Math.floor(usable / dtColumns.length);
			dtColumns.forEach(function (c) {
				c.width = Math.max(MIN_COL_WIDTH, each);
			});
			return;
		}

		var total = dtColumns.reduce(function (sum, c) {
			return sum + c.width;
		}, 0);

		var surplus = usable - total;
		if (surplus <= 0) return;

		dtColumns[dtColumns.length - 1].width += surplus;
	}

	/** Sizes a column to whichever is wider: its heading or its widest value. */
	function estimateColumnWidth(col, rows) {
		var field = col.fieldname || col.key || col.id || "";
		var label = String(col.label || field || "");

		var headerWidth = Math.ceil(label.length * HEADER_CHAR_PX) + HEADER_CHROME;

		// Wrapping columns (e.g. Item Name) hold a fixed width and let long text
		// flow onto a second line instead of stretching the column to fit it.
		if (col.wrap) {
			return Math.max(MIN_COL_WIDTH, headerWidth, col.width || 0);
		}

		var valueWidth =
			Math.ceil(longestCellLength(col, field, rows) * CHAR_PX) + CELL_CHROME;

		// Prefer an explicit width when provided (e.g. long billet-cutting headers).
		return Math.min(
			MAX_COL_WIDTH,
			Math.max(MIN_COL_WIDTH, headerWidth, valueWidth, col.width || 0)
		);
	}

	/** Desk URL for a document, e.g. ("Purchase Invoice", "PI-001") → /app/purchase-invoice/PI-001 */
	function docHref(doctype, name) {
		return (
			"/app/" +
			encodeURIComponent(String(doctype).toLowerCase().replace(/ /g, "-")) +
			"/" +
			encodeURIComponent(String(name))
		);
	}

	function formatCell(column, row) {
		var field = column.fieldname || column.key || column.id || column;
		var value = typeof field === "string" ? row[field] : null;
		var plain = displayText(value, column, field);
		var titleAttr = plain ? ' title="' + escapeHtml(plain) + '"' : "";

		// Purchase > Open MR — colour badge
		if (field === "colour" && value && COLOUR_STYLES[value]) {
			var style = COLOUR_STYLES[value];
			return (
				'<span class="md-colour"' +
				titleAttr +
				' style="background:' +
				style.bg +
				";color:" +
				style.fg +
				';">' +
				escapeHtml(plain) +
				"</span>"
			);
		}

		// Sale > Open SO — Order Status (BLACK / RED / YELLOW / GREEN / WHITE)
		if (field === "order_status" && value) {
			var statusKey = String(value).trim().toLowerCase();
			var statusStyle = ORDER_STATUS_STYLES[statusKey];
			if (statusStyle) {
				return (
					'<span class="md-status-badge"' +
					titleAttr +
					' style="background:' +
					statusStyle.bg +
					";color:" +
					statusStyle.fg +
					';">' +
					escapeHtml(String(value).trim().toUpperCase()) +
					"</span>"
				);
			}
		}

		// Sale > Open SO — Line Fullkit / Order Fullkit (Full-kit / Partial / Pending)
		if ((field === "line_fullkit" || field === "order_fullkit") && value) {
			var fullkitKey = String(value).trim().toLowerCase();
			var fullkitStyle = FULLKIT_STYLES[fullkitKey];
			if (fullkitStyle) {
				return (
					'<span class="md-status-badge"' +
					titleAttr +
					' style="background:' +
					fullkitStyle.bg +
					";color:" +
					fullkitStyle.fg +
					';">' +
					escapeHtml(plain) +
					"</span>"
				);
			}
		}

		// Top 5 Purchase/Sale Items — rank badge
		if (field === "rank" && value && RANK_STYLES[value]) {
			var rankStyle = RANK_STYLES[value];
			return (
				'<span class="md-rank-badge"' +
				titleAttr +
				' style="background:' +
				rankStyle.bg +
				";color:" +
				rankStyle.fg +
				';">' +
				escapeHtml(plain) +
				"</span>"
			);
		}

		if (isDateLikeField(column, field) && value) {
			var dateText =
				formatDateDdMmYy(value, column.fieldtype === "Datetime") || plain;
			return (
				"<span title=\"" +
				escapeHtml(dateText) +
				'">' +
				escapeHtml(dateText) +
				"</span>"
			);
		}

		if (value) {
			var linkDoctype = "";
			var linkName = String(value);

			if (column.fieldtype === "Link") {
				linkDoctype = column.options || "";
			} else if (column.fieldtype === "Dynamic Link") {
				// Target doctype lives in the column named by `options`
				// (Accounts Payable/Receivable: party → party_type, voucher_no → voucher_type).
				linkDoctype = row[column.options] || "";
			} else if (field === "bill_no") {
				// The supplier's own bill number isn't a document — point at the voucher carrying it.
				linkDoctype = row.voucher_type || "";
				linkName = row.voucher_no || "";
			}

			if (linkDoctype && linkName) {
				return (
					'<a href="' +
					docHref(linkDoctype, linkName) +
					'" target="_blank" rel="noopener"' +
					titleAttr +
					">" +
					escapeHtml(plain) +
					"</a>"
				);
			}
		}

		if (column.fieldtype === "Currency" || column.fieldtype === "Float") {
			var num = Number(value);
			if (!isNaN(num)) {
				var formatted = num.toLocaleString("en-IN", { maximumFractionDigits: 2 });
				return (
					'<span title="' +
					escapeHtml(formatted) +
					'">' +
					escapeHtml(formatted) +
					"</span>"
				);
			}
		}

		if (typeof value === "number") {
			var n = value.toLocaleString("en-IN");
			return '<span title="' + escapeHtml(n) + '">' + escapeHtml(n) + "</span>";
		}

		return "<span" + titleAttr + ">" + escapeHtml(plain) + "</span>";
	}

	function destroyDataTable(subId) {
		if (!dataTables[subId]) return;
		try {
			dataTables[subId].destroy();
		} catch (e) {
			/* ignore stale instance cleanup errors */
		}
		dataTables[subId] = null;
	}

	/** Never show Draft / Cancelled rows anywhere on this dashboard. */
	function isDraftOrCancelledRow(row) {
		if (!row || typeof row !== "object") return false;
		if (row.docstatus === 0 || row.docstatus === 2 || row.docstatus === "0" || row.docstatus === "2") {
			return true;
		}
		var blocked = { draft: true, cancelled: true };
		var keys = [
			"status",
			"workflow_state",
			"workflow_status",
			"mr_status",
			"po_status",
			"pi_status",
			"so_status",
		];
		for (var i = 0; i < keys.length; i++) {
			var raw = row[keys[i]];
			if (raw === null || raw === undefined || raw === "") continue;
			if (blocked[String(raw).trim().toLowerCase()]) return true;
		}
		return false;
	}

	function excludeDraftCancelledRows(rows) {
		return (rows || []).filter(function (row) {
			return !isDraftOrCancelledRow(row);
		});
	}

	function renderTable(subId, columns, rows, label, opts) {
		opts = opts || {};
		var mount = document.querySelector('[data-table="' + subId + '"]');
		if (!mount) return;

		destroyDataTable(subId);
		rows = excludeDraftCancelledRows(rows);

		if (!rows.length) {
			mount.innerHTML = '<div class="md-empty">No data found.</div>';
			return;
		}

		mount.innerHTML = "";
		var dtEl = document.createElement("div");
		mount.appendChild(dtEl);

		var dtColumns = (columns || []).map(function (col, idx) {
			var field = col.fieldname || col.key || col.id || "col_" + idx;
			var rightAligned =
				col.fieldtype === "Currency" ||
				col.fieldtype === "Float" ||
				col.fieldtype === "Int" ||
				col.fieldtype === "Percent";

			return {
				name: col.label || field,
				id: field,
				width: estimateColumnWidth(col, rows),
				editable: false,
				resizable: false,
				align: rightAligned ? "right" : "left",
				format: function (_val, _row, _column, data) {
					var cellHtml = formatCell(col, data || {});
					return col.wrap ? '<div class="md-cell-wrap">' + cellHtml + "</div>" : cellHtml;
				},
			};
		});

		fillRemainingWidth(mount, dtColumns, opts);

		var DataTableCtor =
			(window.frappe && frappe.DataTable) || window.DataTable;
		if (!DataTableCtor) {
			mount.innerHTML =
				'<div class="md-error">DataTable is not available on this page.</div>';
			return;
		}

		dataTables[subId] = new DataTableCtor(dtEl, {
			columns: dtColumns,
			data: rows,
			inlineFilters: opts.inlineFilters !== false,
			serialNoColumn: false,
			checkboxColumn: false,
			clusterize: true,
			layout: "fixed",
			noDataMessage: "No data found.",
			cellHeight: opts.cellHeight || 38,
			disableReorderColumn: true,
		});
	}

	function showError(subId, msg) {
		destroyDataTable(subId);
		var mount = document.querySelector('[data-table="' + subId + '"]');
		if (mount) mount.innerHTML = '<div class="md-error">' + escapeHtml(msg) + "</div>";
	}

	function setLoading(subId) {
		destroyDataTable(subId);
		var mount = document.querySelector('[data-table="' + subId + '"]');
		if (mount) mount.innerHTML = '<div class="md-empty">Loading…</div>';
	}


	// =========================================================================
	// CHARTS — shared rendering helpers (frappe.Chart) for the overview grids
	// =========================================================================
	/** Active frappe.Chart instances keyed by chart id. */
	var chartInstances = {};

	function setChartLoading(chartId) {
		var mount = document.querySelector('[data-chart="' + chartId + '"]');
		if (mount) mount.innerHTML = '<div class="md-empty">Loading…</div>';
	}

	function showChartError(chartId, msg) {
		var mount = document.querySelector('[data-chart="' + chartId + '"]');
		if (mount) mount.innerHTML = '<div class="md-error">' + escapeHtml(msg) + "</div>";
	}

	/** config: { type, labels, datasets, colors, height } */
	/** config: { type, labels, datasets, colors, height, legend: [{name, valueLabel}] } */
	function renderChart(chartId, config) {
		var mount = document.querySelector('[data-chart="' + chartId + '"]');
		if (!mount) return;

		chartInstances[chartId] = null;
		mount.innerHTML = "";

		var hasData =
			config &&
			config.labels &&
			config.labels.length &&
			config.datasets &&
			config.datasets.some(function (ds) {
				return (ds.values || []).some(function (v) {
					return Number(v) !== 0;
				});
			});

		if (!hasData) {
			mount.innerHTML = '<div class="md-empty">No data found.</div>';
			return;
		}

		var ChartCtor = window.frappe && frappe.Chart;
		if (!ChartCtor) {
			mount.innerHTML = '<div class="md-error">Chart library not available.</div>';
			return;
		}

		var chartHolder = document.createElement("div");
		mount.appendChild(chartHolder);

		try {
			chartInstances[chartId] = new ChartCtor(chartHolder, {
				data: { labels: config.labels, datasets: config.datasets },
				type: config.type || "bar",
				height: config.height || 240,
				colors: config.colors || ["#2563eb", "#f59e0b", "#10b981"],
				axisOptions: {
					xAxisMode: "tick",
					xIsSeries: config.type === "line",
					shortenYAxisNumbers: true,
				},
				tooltipOptions: {
					formatTooltipY: function (value) {
						return (
							(config.tooltipPrefix || "") +
							formatNum(value) +
							(config.tooltipSuffix || "")
						);
					},
				},
				barOptions: { spaceRatio: 0.3 },
				lineOptions: config.showValuesOnPoints
					? { showDots: true, dotSize: 4, hideDotBorder: true }
					: {},
				valuesOverPoints: config.showValuesOnPoints ? 1 : 0,
				maxLegendPoints: 20,
			});
		} catch (e) {
			mount.innerHTML = '<div class="md-error">Failed to render chart.</div>';
			return;
		}

		// Full item names don't fit in the chart's own x-axis labels (frappe-charts
		// truncates long tick text), so show them as a legend list below the chart.
		if (config.legend && config.legend.length) {
			var legendEl = document.createElement("ol");
			legendEl.className = "md-chart-legend";
			config.legend.forEach(function (item) {
				var li = document.createElement("li");
				li.innerHTML =
					'<span class="md-chart-legend__name" title="' +
					escapeHtml(item.name) +
					'">' +
					escapeHtml(item.name) +
					"</span>" +
					'<span class="md-chart-legend__value">' +
					escapeHtml(item.valueLabel) +
					"</span>";
				legendEl.appendChild(li);
			});
			mount.appendChild(legendEl);
		}
	}

	/** Builds { labels, values } for the trailing `monthsBack` months, summing `amountField` from `rows` grouped by `dateField` (YYYY-MM). */
	function buildMonthlyTrend(rows, dateField, amountField, monthsBack) {
		var months = [];
		var now = new Date();

		for (var i = monthsBack - 1; i >= 0; i--) {
			var d = new Date(now.getFullYear(), now.getMonth() - i, 1);
			var key = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
			var label = d.toLocaleString("en-IN", { month: "short", year: "2-digit" });
			months.push({ key: key, label: label });
		}

		var totals = {};
		months.forEach(function (m) {
			totals[m.key] = 0;
		});

		(rows || []).forEach(function (row) {
			var raw = row[dateField];
			if (!raw) return;
			var key = String(raw).slice(0, 7);
			if (Object.prototype.hasOwnProperty.call(totals, key)) {
				totals[key] += Number(row[amountField] || 0);
			}
		});

		return {
			labels: months.map(function (m) {
				return m.label;
			}),
			values: months.map(function (m) {
				return totals[m.key];
			}),
		};
	}

	/** Converts an amount in rupees to Crores, rounded to 2 decimals (keeps on-chart point labels short). */
	function toCrores(value) {
		return Math.round((Number(value) || 0) / 1e5) / 100;
	}

	/** Sorts `rows` by `field` desc and keeps the top N (rest kept as-is if fewer). */
	function topN(rows, field, n) {
		return (rows || [])
			.slice()
			.sort(function (a, b) {
				return Number(b[field] || 0) - Number(a[field] || 0);
			})
			.slice(0, n);
	}

	/** Shared: fetch top N items (item name, qty, amount) from Purchase/Sales Invoice. */
	function fetchTopItemsByAmount(invoiceDoctype, fromDate, toDate, limitN, orderBy) {
		return api("prakash_steel.api.md_dashboard_charts.get_top_items", {
			doctype: invoiceDoctype,
			from_date: fromDate,
			to_date: toDate,
			limit: limitN,
			order_by: orderBy || "amount",
		}).then(function (result) {
			if (!result.ok || result.body.exc_type) return [];
			return result.body.message || [];
		});
	}

	var TOP_ITEMS_COLUMNS = [
		{ label: "#", fieldname: "rank", fieldtype: "Data", width: 60 },
		{ label: "Item Name", fieldname: "item_name", fieldtype: "Data", width: 200, wrap: true },
		{ label: "Qty", fieldname: "qty", fieldtype: "Float", width: 110 },
		{ label: "Amount", fieldname: "amount", fieldtype: "Currency", width: 140 },
	];

	function renderTopItemsTable(subId, rows) {
		renderTable(
			subId,
			TOP_ITEMS_COLUMNS,
			(rows || []).map(function (r, idx) {
				return {
					rank: idx + 1,
					item_name: r.item_name || r.item_code || "",
					qty: Number(r.qty || 0),
					amount: Number(r.amount || 0),
				};
			}),
			"Top 5 Items",
			{ inlineFilters: false, cellHeight: 44 }
		);
	}

	/** Shared: fetch top N suppliers/customers by invoiced amount from Purchase/Sales Invoice. */
	function fetchTopParties(invoiceDoctype, fromDate, toDate, limitN) {
		return api("prakash_steel.api.md_dashboard_charts.get_top_parties", {
			doctype: invoiceDoctype,
			from_date: fromDate,
			to_date: toDate,
			limit: limitN,
		}).then(function (result) {
			if (!result.ok || result.body.exc_type) return [];
			return result.body.message || [];
		});
	}

	var TOP_PARTIES_COLUMNS = [
		{ label: "#", fieldname: "rank", fieldtype: "Data", width: 60 },
		{ label: "Name", fieldname: "party_name", fieldtype: "Data", width: 260 },
		{ label: "Qty", fieldname: "qty", fieldtype: "Float", width: 110 },
	];

	function renderTopPartiesTable(subId, rows) {
		renderTable(
			subId,
			TOP_PARTIES_COLUMNS,
			(rows || []).map(function (r, idx) {
				return {
					rank: idx + 1,
					party_name: r.party_name || r.party || "",
					qty: Number(r.qty || 0),
				};
			}),
			"Top 5",
			{ inlineFilters: false }
		);
	}

	/** Purchase > Overview charts */
	function loadPurchaseCharts() {
		setChartLoading("purchase_trend");
		setLoading("purchase_top_suppliers");

		var p1 = api("frappe.client.get_list", {
			doctype: "Purchase Invoice",
			fields: ["posting_date", "grand_total"],
			filters: [
				["docstatus", "=", 1],
				["status", "not in", ["Cancelled", "Draft"]],
				["posting_date", ">=", addMonthsISO(-6)],
			],
			limit_page_length: 5000,
		})
			.then(function (result) {
				var rows = result.ok ? result.body.message || [] : [];
				var trend = buildMonthlyTrend(rows, "posting_date", "grand_total", 6);
				renderChart("purchase_trend", {
					type: "line",
					colors: ["#2563eb"],
					labels: trend.labels,
					datasets: [
						{
							name: "Purchase Amount (₹ Cr)",
							values: trend.values.map(toCrores),
						},
					],
					tooltipPrefix: "₹",
					tooltipSuffix: " Cr",
					showValuesOnPoints: true,
				});
			})
			.catch(function () {
				showChartError("purchase_trend", "Failed to load");
			});

		var p2 = fetchTopParties("Purchase Invoice", addMonthsISO(-3), todayISO(), 5)
			.then(function (top) {
				renderTopPartiesTable("purchase_top_suppliers", top);
			})
			.catch(function () {
				showError("purchase_top_suppliers", "Failed to load");
			});

		return Promise.all([p1, p2]);
	}

	/** Sale > Overview charts */
	function loadSaleCharts() {
		setChartLoading("sale_trend");
		setLoading("sale_top_customers");

		var p1 = api("frappe.client.get_list", {
			doctype: "Sales Invoice",
			fields: ["posting_date", "grand_total"],
			filters: [
				["docstatus", "=", 1],
				["status", "not in", ["Cancelled", "Draft"]],
				["posting_date", ">=", addMonthsISO(-6)],
			],
			limit_page_length: 5000,
		})
			.then(function (result) {
				var rows = result.ok ? result.body.message || [] : [];
				var trend = buildMonthlyTrend(rows, "posting_date", "grand_total", 6);
				renderChart("sale_trend", {
					type: "line",
					colors: ["#10b981"],
					labels: trend.labels,
					datasets: [
						{
							name: "Sales Amount (₹ Cr)",
							values: trend.values.map(toCrores),
						},
					],
					tooltipPrefix: "₹",
					tooltipSuffix: " Cr",
					showValuesOnPoints: true,
				});
			})
			.catch(function () {
				showChartError("sale_trend", "Failed to load");
			});

		var p2 = fetchTopParties("Sales Invoice", addMonthsISO(-3), todayISO(), 5)
			.then(function (top) {
				renderTopPartiesTable("sale_top_customers", top);
			})
			.catch(function () {
				showError("sale_top_customers", "Failed to load");
			});

		return Promise.all([p1, p2]);
	}

	/** Inventory > Overview charts */
	function loadInventoryCharts() {
		setLoading("inventory_top_sale_items");
		setLoading("inventory_top_purchase_items");

		var p1 = fetchTopItemsByAmount("Sales Invoice", addMonthsISO(-3), todayISO(), 5, "qty")
			.then(function (top) {
				renderTopItemsTable("inventory_top_sale_items", top);
			})
			.catch(function () {
				showError("inventory_top_sale_items", "Failed to load");
			});

		var p2 = fetchTopItemsByAmount("Purchase Invoice", addMonthsISO(-3), todayISO(), 5, "qty")
			.then(function (top) {
				renderTopItemsTable("inventory_top_purchase_items", top);
			})
			.catch(function () {
				showError("inventory_top_purchase_items", "Failed to load");
			});

		return Promise.all([p1, p2]);
	}

	var MAIN_CHART_LOADERS = {
		purchase: loadPurchaseCharts,
		sale: loadSaleCharts,
		inventory: loadInventoryCharts,
	};

	/** Tracks which main tabs' overview charts have already loaded. */
	var chartsLoaded = {};

	function loadMainCharts(mainId, force) {
		if (!MAIN_CHART_LOADERS[mainId]) return;
		if (chartsLoaded[mainId] && !force) return;
		chartsLoaded[mainId] = true;
		MAIN_CHART_LOADERS[mainId]();
	}

	/** Report columns dropped per sub-tab, by fieldname. */
	var HIDDEN_COLUMNS = {
		open_mr: ["colour"],
		open_po: ["project", "qty_to_bill", "company"],
		open_so: ["company", "time_taken_to_deliver"],
		accounts_payable: ["project", "cost_center", "currency"],
		accounts_receivable: [
			"party_account",
			"customer_primary_contact",
			"cost_center",
			"project",
			"currency",
		],
		inventory_ageing: ["brand"],
	};

	function applyDashboardColumnRules(subId, columns) {
		columns = (columns || []).slice();

		var hidden = HIDDEN_COLUMNS[subId];
		if (hidden) {
			columns = columns.filter(function (c) {
				return hidden.indexOf(c.fieldname || c.key) === -1;
			});
		}

		if (subId === "open_po") {
			var relabel = { qty: "Ordered Qty", cf_lead_time: "Lead Time" };
			var qtyOrder = [
				"received_qty",
				"amount",
				"received_qty_amount",
				"pending_qty",
				"billed_qty",
			];
			var qtyOrderSet = {
				received_qty: true,
				amount: true,
				received_qty_amount: true,
				pending_qty: true,
				billed_qty: true,
			};

			var cols = columns.map(function (c) {
				var copy = Object.assign({}, c);
				if (relabel[copy.fieldname]) {
					copy.label = relabel[copy.fieldname];
				}
				return copy;
			});

			var specialByField = {};
			cols.forEach(function (c) {
				if (qtyOrderSet[c.fieldname]) {
					specialByField[c.fieldname] = c;
				}
			});

			var withoutSpecial = cols.filter(function (c) {
				return !qtyOrderSet[c.fieldname];
			});

			var insertAt = withoutSpecial.findIndex(function (c) {
				return c.fieldname === "qty";
			});
			if (insertAt < 0) {
				insertAt = withoutSpecial.findIndex(function (c) {
					return c.fieldname === "cf_lead_time";
				});
			}
			insertAt = insertAt < 0 ? withoutSpecial.length : insertAt + 1;

			var ordered = withoutSpecial.slice(0, insertAt);
			qtyOrder.forEach(function (field) {
				if (specialByField[field]) ordered.push(specialByField[field]);
			});
			return ordered.concat(withoutSpecial.slice(insertAt));
		}

		return columns;
	}

	function loadQueryReport(subId, reportName, filters, label, opts) {
		setLoading(subId);
		opts = opts || {};

		return api("frappe.desk.query_report.run", {
			report_name: reportName,
			filters: filters || {},
		})
			.then(function (result) {
				if (!result.ok || result.body.exc_type) {
					showError(
						subId,
						(result.body &&
							(result.body._error_message || result.body.exception)) ||
							"Failed to load report"
					);
					return;
				}

				var message = result.body.message || {};
				var columns = (message.columns || []).map(function (c) {
					return typeof c === "string" ? { label: c, fieldname: c } : c;
				});
				var rows = normalizeReportRows(columns, message.result || message.data || []);

				// Optional dashboard-only status exclusion (e.g. hide Completed/Closed
				// rows from "Open PO") — does not touch the underlying report/SQL.
				if (opts.excludeStatuses && opts.excludeStatuses.length) {
					var blockedStatuses = {};
					opts.excludeStatuses.forEach(function (s) {
						blockedStatuses[String(s).trim().toLowerCase()] = true;
					});
					rows = rows.filter(function (row) {
						var statusVal = row.status;
						return !(
							statusVal && blockedStatuses[String(statusVal).trim().toLowerCase()]
						);
					});
				}

				columns = applyDashboardColumnRules(subId, columns);

				renderTable(subId, columns, rows, label || reportName);
				loaded[subId] = true;
			})
			.catch(function (err) {
				showError(subId, err && err.message ? err.message : "Network error");
			});
	}

	function loadList(subId, doctype, fields, filters, columns, label, orderBy) {
		setLoading(subId);

		return api("frappe.client.get_list", {
			doctype: doctype,
			fields: fields,
			filters: filters || {},
			order_by: orderBy || "modified desc",
			limit_page_length: 500,
		})
			.then(function (result) {
				if (!result.ok || result.body.exc_type) {
					showError(
						subId,
						(result.body &&
							(result.body._error_message || result.body.exception)) ||
							"Failed"
					);
					return;
				}

				renderTable(subId, columns, result.body.message || [], label);
				loaded[subId] = true;
			})
			.catch(function (err) {
				showError(subId, err && err.message ? err.message : "Network error");
			});
	}


	// =========================================================================
	// SALE TAB — custom loaders
	// =========================================================================

	/** Sale > CN & DN Pending Approval */
	function loadCnDnPending() {
		var subId = "cn_dn_pending";
		setLoading(subId);

		// Credit/Debit Notes are returns (is_return = 1) that stay submitted while
		// sitting in the "Pending Approval" workflow state — not drafts.
		var pendingFilters = [
			["docstatus", "=", 1],
			["is_return", "=", 1],
			["workflow_state", "=", "Pending Approval"],
			["status", "not in", ["Cancelled", "Draft"]],
			["workflow_state", "not in", ["Cancelled", "Draft"]],
		];

		return Promise.all([
			api("frappe.client.get_list", {
				doctype: "Sales Invoice",
				fields: [
					"name",
					"posting_date",
					"customer",
					"grand_total",
					"workflow_state",
				],
				filters: pendingFilters,
				order_by: "posting_date desc",
				limit_page_length: 500,
			}),
			api("frappe.client.get_list", {
				doctype: "Purchase Invoice",
				fields: [
					"name",
					"posting_date",
					"supplier",
					"grand_total",
					"workflow_state",
				],
				filters: pendingFilters,
				order_by: "posting_date desc",
				limit_page_length: 500,
			}),
		])
			.then(function (results) {
				var rows = [];

				if (results[0].ok) {
					(results[0].body.message || []).forEach(function (row) {
						rows.push({
							type: "Credit Note",
							name: row.name,
							date: row.posting_date,
							party: row.customer,
							amount: row.grand_total,
							status: row.workflow_state,
						});
					});
				}

				if (results[1].ok) {
					(results[1].body.message || []).forEach(function (row) {
						rows.push({
							type: "Debit Note",
							name: row.name,
							date: row.posting_date,
							party: row.supplier,
							amount: row.grand_total,
							status: row.workflow_state,
						});
					});
				}

				renderTable(
					subId,
					[
						{ label: "Type", fieldname: "type", fieldtype: "Data" },
						{ label: "Document", fieldname: "name", fieldtype: "Data" },
						{ label: "Date", fieldname: "date", fieldtype: "Date" },
						{ label: "Party", fieldname: "party", fieldtype: "Data" },
						{ label: "Amount", fieldname: "amount", fieldtype: "Currency" },
						{ label: "Status", fieldname: "status", fieldtype: "Data" },
					],
					rows,
					"Credit Note & Debit Note Pending Approval"
				);
				loaded[subId] = true;
			})
			.catch(function (err) {
				showError(subId, err && err.message ? err.message : "Network error");
			});
	}

	/** Shared: fetch + aggregate Bright/Rolled sales by grade for a date range. */
	function fetchGradeWiseSellingAgg(fromDate, toDate) {
		var filters = { from_date: fromDate, to_date: toDate };

		return Promise.all([
			api("frappe.desk.query_report.run", {
				report_name: "Bright Bar Sales report",
				filters: filters,
			}),
			api("frappe.desk.query_report.run", {
				report_name: "Rolled Bar Sales report",
				filters: filters,
			}),
		]).then(function (results) {
			var rows = [];

			results.forEach(function (result, idx) {
				if (!result.ok || result.body.exc_type) return;
				var message = result.body.message || {};
				var columns = message.columns || [];
				var data = normalizeReportRows(columns, message.result || message.data || []);
				data.forEach(function (row) {
					row._source = idx === 0 ? "Bright" : "Rolled";
					rows.push(row);
				});
			});

			if (!rows.length) return [];

			var itemCodes = rows.map(function (r) {
				return r.item_code;
			});

			return fetchItemFields(itemCodes, ["custom_grade"]).then(function (itemMap) {
				var agg = {};

				rows.forEach(function (row) {
					var grade =
						(itemMap[row.item_code] && itemMap[row.item_code].custom_grade) ||
						"Unknown";
					if (!agg[grade]) agg[grade] = { grade: grade, qty: 0, amount: 0 };
					agg[grade].qty += Number(row.qty || 0);
					agg[grade].amount += Number(row.amount || (row.qty || 0) * (row.rate || 0));
				});

				return Object.keys(agg)
					.sort()
					.map(function (k) {
						return agg[k];
					});
			});
		});
	}

	/** Sale > Grade wise Average Selling Qty & Amount */
	function loadGradeWiseSelling() {
		var subId = "grade_avg_selling";
		setLoading(subId);

		return fetchGradeWiseSellingAgg(addMonthsISO(-3), todayISO())
			.then(function (out) {
				renderTable(
					subId,
					[
						{ label: "Grade", fieldname: "grade", fieldtype: "Data" },
						{ label: "Qty", fieldname: "qty", fieldtype: "Float" },
						{ label: "Amount", fieldname: "amount", fieldtype: "Currency" },
					],
					out,
					"Grade wise Average Selling Qty & Amount",
					{ equalWidths: true, centerAlign: true }
				);
				loaded[subId] = true;
			})
			.catch(function (err) {
				showError(subId, err && err.message ? err.message : "Network error");
			});
	}

	/** Sale > Weekly Throughput */
	function loadWeeklyThroughput() {
		var subId = "weekly_throughput";
		setLoading(subId);

		var filters = { from_date: addDaysISO(-6), to_date: todayISO() };

		return Promise.all([
			api("frappe.desk.query_report.run", {
				report_name: "Weekly Rolled Production",
				filters: filters,
			}),
			api("frappe.desk.query_report.run", {
				report_name: "Weekly Bright Production",
				filters: filters,
			}),
		])
			.then(function (results) {
				var rows = [];

				results.forEach(function (result, idx) {
					if (!result.ok || result.body.exc_type) return;
					var message = result.body.message || {};
					var columns = message.columns || [];
					var data = normalizeReportRows(columns, message.result || message.data || []);
					data.forEach(function (row) {
						row._type = idx === 0 ? "Rolled" : "Bright";
						rows.push(row);
					});
				});

				if (!rows.length) {
					renderTable(subId, [], [], "Weekly Throughput");
					return;
				}

				renderTable(
					subId,
					[
						{ label: "Type", fieldname: "_type", fieldtype: "Data" },
						{ label: "Production Date", fieldname: "production_date", fieldtype: "Date" },
						{ label: "Item Code", fieldname: "item_code", fieldtype: "Link", options: "Item" },
						{ label: "Item Name", fieldname: "item_name", fieldtype: "Data" },
						{ label: "Actual Qty", fieldname: "actual_qty", fieldtype: "Float" },
					],
					rows,
					"Weekly Throughput (Rolled + Bright Production)"
				);
				loaded[subId] = true;
			})
			.catch(function (err) {
				showError(subId, err && err.message ? err.message : "Network error");
			});
	}


	// =========================================================================
	// INVENTORY TAB — custom loaders
	// =========================================================================

	/** Shared: fetch + aggregate Bright/Rolled Free Stock by grade. */
	function fetchGradeWiseInventoryAgg() {
		return Promise.all([
			api("frappe.desk.query_report.run", {
				report_name: "Bright Free Stock",
				filters: {},
			}),
			api("frappe.desk.query_report.run", {
				report_name: "Rolled Free Stock",
				filters: {},
			}),
		]).then(function (results) {
			var rows = [];

			results.forEach(function (result) {
				if (!result.ok || result.body.exc_type) return;
				var message = result.body.message || {};
				var columns = message.columns || [];
				var data = normalizeReportRows(columns, message.result || message.data || []);
				rows = rows.concat(data);
			});

			if (!rows.length) return [];

			var itemCodes = rows.map(function (r) {
				return r.item_code;
			});

			return fetchItemFields(itemCodes, ["custom_grade"]).then(function (itemMap) {
				var agg = {};

				rows.forEach(function (row) {
					var grade =
						(itemMap[row.item_code] && itemMap[row.item_code].custom_grade) ||
						"Unknown";
					if (!agg[grade]) {
						agg[grade] = { grade: grade, on_hand_stock: 0, free_stock: 0 };
					}
					agg[grade].on_hand_stock += Number(row.on_hand_stock || 0);
					agg[grade].free_stock += Number(row.free_stock || 0);
				});

				return Object.keys(agg)
					.sort()
					.map(function (k) {
						return agg[k];
					});
			});
		});
	}

	/** Inventory > Grade wise Inventory */
	function loadGradeWiseInventory() {
		var subId = "grade_wise_inventory";
		setLoading(subId);

		return fetchGradeWiseInventoryAgg()
			.then(function (out) {
				renderTable(
					subId,
					[
						{ label: "Grade", fieldname: "grade", fieldtype: "Data" },
						{ label: "On Hand Stock", fieldname: "on_hand_stock", fieldtype: "Float" },
						{ label: "Free Stock", fieldname: "free_stock", fieldtype: "Float" },
					],
					out,
					"Grade wise Inventory",
					{ equalWidths: true, centerAlign: true }
				);
				loaded[subId] = true;
			})
			.catch(function (err) {
				showError(subId, err && err.message ? err.message : "Network error");
			});
	}

	/** Shared: fetch + aggregate Bright Free Stock by shape (Flat, Sq., Round, Hex). */
	function fetchBrightShapeWiseAgg() {
		return api("frappe.desk.query_report.run", {
			report_name: "Bright Free Stock",
			filters: {},
		}).then(function (result) {
			if (!result.ok || result.body.exc_type) return [];

			var message = result.body.message || {};
			var columns = message.columns || [];
			var rows = normalizeReportRows(columns, message.result || message.data || []);

			if (!rows.length) return [];

			var itemCodes = rows.map(function (r) {
				return r.item_code;
			});

			return fetchItemFields(itemCodes, ["custom_shape"]).then(function (itemMap) {
				// Item.custom_shape stores the full word "Square" (see the
				// field's select options); display it as "Sq." per the tab title.
				var allowed = { Flat: 1, Square: 1, Round: 1, Hex: 1 };
				var displayLabel = { Square: "Sq." };
				var agg = {};

				rows.forEach(function (row) {
					var shape =
						(itemMap[row.item_code] && itemMap[row.item_code].custom_shape) || "";
					if (!allowed[shape]) return;
					if (!agg[shape]) {
						agg[shape] = {
							shape: displayLabel[shape] || shape,
							on_hand_stock: 0,
							free_stock: 0,
						};
					}
					agg[shape].on_hand_stock += Number(row.on_hand_stock || 0);
					agg[shape].free_stock += Number(row.free_stock || 0);
				});

				return Object.keys(agg)
					.sort()
					.map(function (k) {
						return agg[k];
					});
			});
		});
	}

	/** Inventory > Shape wise (Bright Item) — Flat, Sq., Round, Hex */
	function loadBrightShapeWise() {
		var subId = "bright_shape_wise";
		setLoading(subId);

		return fetchBrightShapeWiseAgg()
			.then(function (out) {
				renderTable(
					subId,
					[
						{ label: "Shape", fieldname: "shape", fieldtype: "Data" },
						{ label: "On Hand Stock", fieldname: "on_hand_stock", fieldtype: "Float" },
						{ label: "Free Stock", fieldname: "free_stock", fieldtype: "Float" },
					],
					out,
					"Shape wise (Bright Item)",
					{ equalWidths: true, centerAlign: true }
				);
				loaded[subId] = true;
			})
			.catch(function (err) {
				showError(subId, err && err.message ? err.message : "Network error");
			});
	}


	// =========================================================================
	// PRODUCTION TAB — APIs, column defs, KPI cards
	// =========================================================================

	function getCurrentFinancialYearStart() {
		var d = new Date();
		var year = d.getFullYear();
		var month = d.getMonth() + 1; // 1-12
		return month >= 4 ? year : year - 1;
	}

	function financialYearLabel(startYear) {
		return startYear + "-" + String(startYear + 1).slice(-2);
	}

	function financialYearRange(startYear) {
		return {
			from_date: startYear + "-04-01",
			to_date: (startYear + 1) + "-03-31",
		};
	}

	var PRODUCTION_APIS = {
		rolled_production: "prakash_steel.api.production_dashboard.get_rolled_production_data",
		bright_production: "prakash_steel.api.production_dashboard.get_bright_production_data",
		hourly_production: "prakash_steel.api.production_dashboard.get_hourly_production_data",
		bend_weight_details: "prakash_steel.api.production_dashboard.get_bend_weight_details",
		coal_consumption: "prakash_steel.api.production_dashboard.get_coal_consumption_data",
		monthly_production_coal:
			"prakash_steel.api.production_dashboard.get_monthly_production_with_coal_consumption_data",
		billet_cutting_amount: "prakash_steel.api.production_dashboard.get_billet_cutting_amount_data",
		weekly_billet_cutting_amount:
			"prakash_steel.api.production_dashboard.get_weekly_billet_cutting_amount_data",
	};

	var PRODUCTION_LABELS = {
		rolled_production: "Rolled Production",
		bright_production: "Bright Production",
		hourly_production: "Hourly Production",
		bend_weight_details: "Bend Weight Details",
		coal_consumption: "Coal Consumption",
		monthly_production_coal: "Monthly Production With Coal Consumption",
		billet_cutting_amount: "Monthly Billet Cutting Amount",
		weekly_billet_cutting_amount: "Weekly Billet Cutting Amount",
	};

	var PRODUCTION_COLUMNS = {
		// Production > Rolled Production
		rolled_production: [
			{ key: "production_plan", label: "Production Plan / Work Order" },
			{ key: "production_date", label: "Production Date" },
			{ key: "rm", label: "RM" },
			{ key: "rm_category_name", label: "RM Category Name" },
			{ key: "rm_consumption", label: "Actual RM Consumption" },
			{ key: "billet_pcs", label: "Total Billet Pcs" },
			{ key: "description_of_cutting_billet", label: "Description of Cutting Billet" },
			{ key: "total_raw_material_pcs", label: "Total Raw Material Pcs" },
			{ key: "total_rm_weight", label: "Total RM Weight" },
			{ key: "miss_billet_pcs", label: "Miss Billet Pcs" },
			{ key: "miss_billet_weight", label: "Miss Billet Weight" },
			{ key: "heat_no", label: "Heat No" },
			{ key: "finished_item", label: "Finished Item" },
			{ key: "finished_item_category_name", label: "Finished Item Category Name" },
			{ key: "fg_planned_qty", label: "FG Planned Qty" },
			{ key: "actual_qty", label: "Actual Qty" },
			{ key: "finish_pcs", label: "Finish Pcs" },
			{ key: "fg_length", label: "FG Length" },
			{ key: "total_miss_roll_pcs", label: "Total Miss Roll (Pcs)" },
			{ key: "total_miss_roll_weight", label: "Total Miss Roll Weight" },
			{ key: "total_miss_ingot_pcs", label: "Total Miss Ingot" },
			{ key: "total_miss_ingot_weight", label: "Total Miss Ingot / Billet Weight" },
			{ key: "melting_weight", label: "Melting Weight" },
			{ key: "burning_loss", label: "Burning Loss %" },
			{ key: "total_hr_consumed", label: "Total Hr Consumed" },
		],

		// Production > Bright Production
		bright_production: [
			{ key: "production_plan", label: "Production Plan / Work Order" },
			{ key: "production_date", label: "Production Date" },
			{ key: "rm", label: "RM" },
			{ key: "rm_category_name", label: "RM Category Name" },
			{ key: "rm_consumption", label: "Actual RM Consumption" },
			{ key: "machine_name", label: "Machine Name" },
			{ key: "finished_item", label: "Finished Item" },
			{ key: "finished_item_category_name", label: "Finished Item Category Name" },
			{ key: "fg_planned_qty", label: "FG Planned Qty" },
			{ key: "actual_qty", label: "Actual Qty" },
			{ key: "finish_length", label: "Finish Length" },
			{ key: "tolerance", label: "Tolerance" },
			{ key: "end_cutting_weight", label: "End Cutting Weight" },
			{ key: "wastage", label: "Wastage %" },
		],

		// Production > Hourly Production
		hourly_production: [
			{ key: "date", label: "Date" },
			{ key: "hours", label: "Hours" },
		],

		// Production > Bend Weight Details
		bend_weight_details: [
			{ key: "id", label: "ID" },
			{ key: "item_code", label: "Item Code" },
			{ key: "category_name", label: "Category Name" },
			{ key: "bend_material_weight", label: "Bend Material Weight" },
		],

		// Production > Coal Consumption
		coal_consumption: [
			{ key: "date", label: "Date" },
			{ key: "item", label: "Item" },
			{ key: "qty", label: "Qty" },
			{ key: "uom", label: "UOM" },
		],

		// Production > Monthly Production With Coal Consumption
		monthly_production_coal: [
			{ key: "month", label: "Month" },
			{ key: "total_production", label: "Total Production" },
			{ key: "total_coal_consumption", label: "Total Coal Consumption" },
			{ key: "per_ton_coal_consumption", label: "Per Ton Coal Consumption (In KG)" },
		],

		// Production > Monthly Billet Cutting Amount
		billet_cutting_amount: [
			{ key: "month", label: "Month", width: 110 },
			{ key: "fc_qty", label: "Full Cutting (FC) Qty (MT)", fieldtype: "Float", width: 200 },
			{ key: "fc_amount", label: "Full Cutting (FC) Amount", fieldtype: "Float", width: 190 },
			{ key: "hf_qty", label: "Half Cutting (HF) Qty (MT)", fieldtype: "Float", width: 200 },
			{ key: "hf_amount", label: "Half Cutting (HF) Amount", fieldtype: "Float", width: 190 },
			{ key: "gc_qty", label: "General Cutting (GC) Qty (MT)", fieldtype: "Float", width: 210 },
			{ key: "gc_amount", label: "General Cutting (GC) Amount", fieldtype: "Float", width: 200 },
			{ key: "fcn_qty", label: "Full Cutting-NG (FC-N) Qty (MT)", fieldtype: "Float", width: 230 },
			{ key: "fcn_amount", label: "Full Cutting-NG (FC-N) Amount", fieldtype: "Float", width: 220 },
			{ key: "total_qty", label: "Total Qty (MT)", fieldtype: "Float", width: 130 },
			{ key: "total_amount", label: "Total Amount", fieldtype: "Float", width: 130 },
		],

		// Production > Weekly Billet Cutting Amount
		weekly_billet_cutting_amount: [
			{ key: "weeks_from", label: "Weeks from", width: 190 },
			{ key: "weeks_to", label: "Weeks to", width: 190 },
			{ key: "fc_qty", label: "Full Cutting (FC) Qty (MT)", fieldtype: "Float", width: 200 },
			{ key: "fc_amount", label: "Full Cutting (FC) Amount", fieldtype: "Float", width: 190 },
			{ key: "hf_qty", label: "Half Cutting (HF) Qty (MT)", fieldtype: "Float", width: 200 },
			{ key: "hf_amount", label: "Half Cutting (HF) Amount", fieldtype: "Float", width: 190 },
			{ key: "gc_qty", label: "General Cutting (GC) Qty (MT)", fieldtype: "Float", width: 210 },
			{ key: "gc_amount", label: "General Cutting (GC) Amount", fieldtype: "Float", width: 200 },
			{ key: "fcn_qty", label: "Full Cutting-NG (FC-N) Qty (MT)", fieldtype: "Float", width: 230 },
			{ key: "fcn_amount", label: "Full Cutting-NG (FC-N) Amount", fieldtype: "Float", width: 220 },
			{ key: "total_qty", label: "Total Qty (MT)", fieldtype: "Float", width: 130 },
			{ key: "total_amount", label: "Total Amount", fieldtype: "Float", width: 130 },
		],
	};

	function renderProductionKpis(subId, totals) {
		var mount = document.querySelector('[data-kpi="' + subId + '"]');
		if (!mount) return;

		totals = totals || {};
		var cards = [];

		if (subId === "rolled_production") {
			cards = [
				{ label: "Total Production (kg)", value: totals.total_production, gradient: "blue" },
				{ label: "RM Consumption", value: totals.rm_consumption, gradient: "teal" },
				{ label: "Burning Loss %", value: totals.burning_loss_per, isPct: true, gradient: "red" },
				{ label: "Total Hr", value: totals.total_hr_consumed, gradient: "yellow" },
			];
		} else if (subId === "bright_production") {
			cards = [
				{ label: "Total Production (kg)", value: totals.total_production, gradient: "yellow" },
				{ label: "RM Consumption", value: totals.rm_consumption, gradient: "green" },
				{ label: "End Cutting Weight", value: totals.total_end_cutting_weight, gradient: "teal" },
				{ label: "Wastage %", value: totals.wastage_per, isPct: true, gradient: "orange" },
			];
		} else if (subId === "hourly_production") {
			cards = [
				{ label: "Total Hours", value: totals.total_hours, gradient: "blue" },
			];
		} else if (subId === "coal_consumption") {
			mount.innerHTML = "";
			return;
		} else {
			mount.innerHTML = "";
			return;
		}

		mount.innerHTML = cards
			.map(function (c) {
				var val = c.isPct ? formatPct(c.value) : formatNum(c.value);
				var gradientClass = c.gradient ? " md-kpi-card--" + c.gradient : "";
				return (
					'<div class="md-kpi-card' +
					gradientClass +
					'">' +
					'<div class="md-kpi-value">' +
					val +
					"</div>" +
					'<div class="md-kpi-label">' +
					escapeHtml(c.label) +
					"</div>" +
					"</div>"
				);
			})
			.join("");
	}

	function loadProductionData(subId) {
		setLoading(subId);

		var kpiMount = document.querySelector('[data-kpi="' + subId + '"]');
		if (kpiMount) kpiMount.innerHTML = "";

		var isFinancialYearTab =
			subId === "monthly_production_coal" ||
			subId === "billet_cutting_amount" ||
			subId === "weekly_billet_cutting_amount";
		var dateRange = isFinancialYearTab
			? financialYearRange(getCurrentFinancialYearStart())
			: { from_date: "", to_date: todayISO() };

		return api(PRODUCTION_APIS[subId], {
			from_date: dateRange.from_date,
			to_date: dateRange.to_date,
			item_code: "",
			production_plan: "",
			machine_name: "",
			category_name: "",
		})
			.then(function (result) {
				if (!result.ok || result.body.exc_type) {
					showError(
						subId,
						(result.body &&
							(result.body._error_message || result.body.exception)) ||
							"Failed to load production data"
					);
					return;
				}

				var data = result.body.message || {};
				var rows = data.rows || [];

				var label = isFinancialYearTab
					? PRODUCTION_LABELS[subId] +
					  " (FY " +
					  financialYearLabel(getCurrentFinancialYearStart()) +
					  ")"
					: PRODUCTION_LABELS[subId] +
					  " (up to " +
					  (formatDateDdMmYy(todayISO()) || todayISO()) +
					  ")";

				// Hourly / Coal / Monthly Coal: equal-width compact tables.
				// Billet Cutting Amount tabs: size columns to full header text
				// and allow horizontal scroll when needed.
				var tableOpts;
				var isBilletCuttingTab =
					subId === "billet_cutting_amount" ||
					subId === "weekly_billet_cutting_amount";
				if (isBilletCuttingTab) {
					tableOpts = { centerAlign: true, inlineFilters: false };
				} else if (isFinancialYearTab) {
					tableOpts = { equalWidths: true, centerAlign: true, inlineFilters: false };
				} else if (subId === "hourly_production" || subId === "coal_consumption") {
					tableOpts = { equalWidths: true, centerAlign: true };
				} else {
					tableOpts = undefined;
				}

				renderProductionKpis(subId, data.totals || {});
				renderTable(subId, PRODUCTION_COLUMNS[subId], rows, label, tableOpts);
				loaded[subId] = true;
			})
			.catch(function (err) {
				showError(subId, err && err.message ? err.message : "Network error");
			});
	}


	// =========================================================================
	// TAB_LOADERS — maps HTML data-sub id → loader function
	// =========================================================================
	var TAB_LOADERS = {
		// ---------------------------------------------------------------------
		// PURCHASE TAB
		// ---------------------------------------------------------------------
		/** Purchase > Open MR for Purchase */
		open_mr: function () {
			return loadQueryReport("open_mr", "Open MR for Purchase", {}, "Open MR for Purchase");
		},

		/** Purchase > Open PO — hide Completed/Closed rows (dashboard-only filter) */
		open_po: function () {
			return getCompany().then(function (company) {
				return loadQueryReport(
					"open_po",
					"Open PO Analysis",
					{
						company: company,
						from_date: addMonthsISO(-3),
						to_date: todayISO(),
					},
					"Open PO Analysis",
					{ excludeStatuses: ["Completed", "Closed"] }
				);
			});
		},

		/** Purchase > Pending Approval PI — filter Draft/Cancelled in dashboard only */
		pending_pi: function () {
			setLoading("pending_pi");
			return api("frappe.client.get_list", {
				doctype: "Purchase Invoice",
				fields: [
					"name",
					"status",
					"posting_date",
					"supplier",
					"grand_total",
					"workflow_state",
					"docstatus",
				],
				filters: [
					["docstatus", "=", 1],
					["workflow_state", "=", "Pending Approval"],
					["status", "not in", ["Cancelled", "Draft"]],
					["workflow_state", "not in", ["Cancelled", "Draft"]],
				],
				order_by: "posting_date desc",
				limit_page_length: 500,
			})
				.then(function (result) {
					if (!result.ok || result.body.exc_type) {
						showError(
							"pending_pi",
							(result.body &&
								(result.body._error_message || result.body.exception)) ||
								"Failed to load"
						);
						return;
					}
					var rows = (result.body.message || []).map(function (row) {
						return {
							purchase_invoice_id: row.name,
							status: row.status || row.workflow_state,
							date: row.posting_date,
							supplier: row.supplier,
							grand_total: row.grand_total,
							docstatus: row.docstatus,
							workflow_state: row.workflow_state,
						};
					});
					renderTable(
						"pending_pi",
						[
							{
								label: "Purchase Invoice ID",
								fieldname: "purchase_invoice_id",
								fieldtype: "Link",
								options: "Purchase Invoice",
							},
							{ label: "Date", fieldname: "date", fieldtype: "Date" },
							{ label: "Status", fieldname: "status", fieldtype: "Data" },
							{
								label: "Supplier",
								fieldname: "supplier",
								fieldtype: "Link",
								options: "Supplier",
							},
							{
								label: "Grand Total",
								fieldname: "grand_total",
								fieldtype: "Currency",
							},
						],
						rows,
						"Pending Approval PI"
					);
					loaded.pending_pi = true;
				})
				.catch(function (err) {
					showError("pending_pi", err && err.message ? err.message : "Network error");
				});
		},

		/** Purchase > Grade wise average purchase rate */
		grade_avg_purchase_rate: function () {
			setLoading("grade_avg_purchase_rate");

			return api(
				"prakash_steel.prakash_steel.page.average_purchase_rat.average_purchase_rat.get_grade_wise_avg_rate",
				{ from_date: addMonthsISO(-3), to_date: todayISO() }
			).then(function (result) {
				if (!result.ok || result.body.exc_type) {
					showError(
						"grade_avg_purchase_rate",
						(result.body &&
							(result.body._error_message || result.body.exception)) ||
							"Failed"
					);
					return;
				}

				renderTable(
					"grade_avg_purchase_rate",
					[
						{ label: "Grade", fieldname: "grade", fieldtype: "Data" },
						{ label: "Avg Rate", fieldname: "avg_rate", fieldtype: "Float" },
					],
					result.body.message || [],
					"Grade wise average purchase rate",
					{ equalWidths: true }
				);
				loaded.grade_avg_purchase_rate = true;
			});
		},

		/** Purchase > Accounts Payable List */
		accounts_payable: function () {
			return getCompany().then(function (company) {
				return loadQueryReport(
					"accounts_payable",
					"Accounts Payable",
					{
						company: company,
						report_date: todayISO(),
						ageing_based_on: "Due Date",
						range: "30, 60, 90, 120",
					},
					"Accounts Payable"
				);
			});
		},

		/** Purchase > Advanced Paid list in Purchase */
		advance_paid: function () {
			return loadList(
				"advance_paid",
				"Payment Entry",
				[
					"name",
					"posting_date",
					"party",
					"party_name",
					"paid_amount",
					"unallocated_amount",
					"mode_of_payment",
				],
				{ docstatus: 1, payment_type: "Pay", unallocated_amount: [">", 0], status: ["not in", ["Cancelled", "Draft"]] },
				[
					{
						label: "Payment Entry",
						fieldname: "name",
						fieldtype: "Link",
						options: "Payment Entry",
					},
					{ label: "Date", fieldname: "posting_date", fieldtype: "Date" },
					{ label: "Supplier", fieldname: "party", fieldtype: "Link", options: "Supplier" },
					{ label: "Supplier Name", fieldname: "party_name", fieldtype: "Data" },
					{ label: "Paid Amount", fieldname: "paid_amount", fieldtype: "Currency" },
					{
						label: "Unallocated / Advance",
						fieldname: "unallocated_amount",
						fieldtype: "Currency",
					},
					{ label: "Mode", fieldname: "mode_of_payment", fieldtype: "Data" },
				],
				"Advance Paid (unallocated Payment Entry)",
				"posting_date desc"
			);
		},

		// ---------------------------------------------------------------------
		// SALE TAB
		// ---------------------------------------------------------------------
		/** Sale > Open SO */
		open_so: function () {
			return getCompany().then(function (company) {
				return loadQueryReport(
					"open_so",
					"Open SO Analysis",
					{
						company: company,
						from_date: addMonthsISO(-3),
						to_date: todayISO(),
					},
					"Open SO Analysis"
				);
			});
		},

		/** Sale > Credit Note & Debit Note Pending Approval */
		cn_dn_pending: loadCnDnPending,

		/** Sale > Accounts Receivable List */
		accounts_receivable: function () {
			return getCompany().then(function (company) {
				return loadQueryReport(
					"accounts_receivable",
					"Accounts Receivable",
					{
						company: company,
						report_date: todayISO(),
						ageing_based_on: "Due Date",
						range: "30, 60, 90, 120",
					},
					"Accounts Receivable"
				);
			});
		},

		/** Sale > Advanced Received list in Sales */
		advance_received: function () {
			return loadList(
				"advance_received",
				"Payment Entry",
				[
					"name",
					"posting_date",
					"party",
					"party_name",
					"paid_amount",
					"unallocated_amount",
					"mode_of_payment",
					"company",
				],
				{ docstatus: 1, payment_type: "Receive", unallocated_amount: [">", 0], status: ["not in", ["Cancelled", "Draft"]] },
				[
					{
						label: "Payment Entry",
						fieldname: "name",
						fieldtype: "Link",
						options: "Payment Entry",
					},
					{ label: "Date", fieldname: "posting_date", fieldtype: "Date" },
					{ label: "Customer", fieldname: "party", fieldtype: "Link", options: "Customer" },
					{ label: "Customer Name", fieldname: "party_name", fieldtype: "Data" },
					{ label: "Received Amount", fieldname: "paid_amount", fieldtype: "Currency" },
					{
						label: "Unallocated / Advance",
						fieldname: "unallocated_amount",
						fieldtype: "Currency",
					},
					{ label: "Mode", fieldname: "mode_of_payment", fieldtype: "Data" },
					{ label: "Company", fieldname: "company", fieldtype: "Data" },
				],
				"Advance Received (unallocated Payment Entry)",
				"posting_date desc"
			);
		},

		/** Sale > Grade wise Average Selling Qty & Amount */
		grade_avg_selling: loadGradeWiseSelling,

		/** Sale > Weekly Throughput */
		weekly_throughput: loadWeeklyThroughput,

		// ---------------------------------------------------------------------
		// INVENTORY TAB
		// ---------------------------------------------------------------------
		/** Inventory > Inventory Ageing (30, 60, 90, 120+) */
		inventory_ageing: function () {
			return getCompany().then(function (company) {
				return loadQueryReport(
					"inventory_ageing",
					"Stock Ageing",
					{
						company: company,
						to_date: todayISO(),
						range: "30, 60, 90, 120",
					},
					"Stock Ageing"
				);
			});
		},

		/** Inventory > Grade wise Inventory */
		grade_wise_inventory: loadGradeWiseInventory,

		/** Inventory > Shape wise (Bright Item) */
		bright_shape_wise: loadBrightShapeWise,

		// ---------------------------------------------------------------------
		// PRODUCTION TAB
		// ---------------------------------------------------------------------
		/** Production > Rolled Production */
		rolled_production: function () {
			return loadProductionData("rolled_production");
		},

		/** Production > Bright Production */
		bright_production: function () {
			return loadProductionData("bright_production");
		},

		/** Production > Hourly Production */
		hourly_production: function () {
			return loadProductionData("hourly_production");
		},

		/** Production > Bend Weight Details */
		bend_weight_details: function () {
			return loadProductionData("bend_weight_details");
		},

		/** Production > Coal Consumption */
		coal_consumption: function () {
			return loadProductionData("coal_consumption");
		},

		/** Production > Monthly Production With Coal Consumption */
		monthly_production_coal: function () {
			return loadProductionData("monthly_production_coal");
		},

		/** Production > Monthly Billet Cutting Amount */
		billet_cutting_amount: function () {
			return loadProductionData("billet_cutting_amount");
		},

		/** Production > Weekly Billet Cutting Amount */
		weekly_billet_cutting_amount: function () {
			return loadProductionData("weekly_billet_cutting_amount");
		},
	};


	// =========================================================================
	// NAVIGATION & INIT
	// =========================================================================
	function loadTab(subId, force) {
		if (!TAB_LOADERS[subId]) return;
		if (loaded[subId] && !force) return;
		TAB_LOADERS[subId]();
	}

	function getActiveSub(mainId) {
		var panel = document.querySelector('.md-main-panel[data-main="' + mainId + '"]');
		if (!panel) return null;
		var active = panel.querySelector(".md-sub-tab.is-active");
		return active ? active.getAttribute("data-sub") : null;
	}

	function initMdDashboard() {
		var root = document.getElementById("md-dashboard-root");
		if (!root || root.dataset.bound === "1") return;
		root.dataset.bound = "1";

		// Main tab clicks — Purchase | Sale | Inventory | Production
		root.querySelectorAll(".md-main-tab").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var main = btn.getAttribute("data-main");

				root.querySelectorAll(".md-main-tab").forEach(function (b) {
					b.classList.toggle("is-active", b === btn);
				});
				root.querySelectorAll(".md-main-panel").forEach(function (panel) {
					panel.classList.toggle("is-active", panel.getAttribute("data-main") === main);
				});

				loadTab(getActiveSub(main), false);
				loadMainCharts(main, false);
			});
		});

		// Sub-tab clicks inside each main section
		root.querySelectorAll(".md-main-panel").forEach(function (panel) {
			panel.querySelectorAll(".md-sub-tab").forEach(function (btn) {
				btn.addEventListener("click", function () {
					var sub = btn.getAttribute("data-sub");

					panel.querySelectorAll(".md-sub-tab").forEach(function (b) {
						b.classList.toggle("is-active", b === btn);
					});
					panel.querySelectorAll(".md-sub-panel").forEach(function (p) {
						p.classList.toggle("is-active", p.getAttribute("data-sub") === sub);
					});

					loadTab(sub, false);
				});
			});
		});

		// Refresh buttons — force reload
		root.querySelectorAll("[data-refresh]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				loadTab(btn.getAttribute("data-refresh"), true);
			});
		});


		// Chart "Refresh Charts" buttons — force reload of a main tab's overview charts
		root.querySelectorAll("[data-chart-refresh]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				loadMainCharts(btn.getAttribute("data-chart-refresh"), true);
			});
		});

		// Default: load first Purchase tab and its overview charts on page open
		loadTab("open_mr", true);
		loadMainCharts("purchase", true);
	}
