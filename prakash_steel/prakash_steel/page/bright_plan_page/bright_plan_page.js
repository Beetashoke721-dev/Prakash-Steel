frappe.pages["bright-plan-page"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Bright Plan",
        single_column: true,
    });

    page.add_inner_button(__("Refresh"), () => load_data());
    page.add_inner_button(__("Execute"), () => {
        const selected = _get_selected_rows();
        if (!selected.length) {
            frappe.show_alert({ message: __("No rows selected."), indicator: "orange" });
            return;
        }
        const valid = selected.filter(r => r.production_qty_based_on_child_stock > 0);
        if (!valid.length) {
            frappe.show_alert({ message: __("Selected rows have no production qty."), indicator: "orange" });
            return;
        }
        frappe.confirm(
            __(`Create Work Orders for <b>${valid.length}</b> item(s)?`),
            () => {
                frappe.call({
                    method: "prakash_steel.prakash_steel.page.bright_plan_page.bright_plan_page.execute_work_orders",
                    args: { rows: valid },
                    freeze: true,
                    freeze_message: __("Creating Work Orders…"),
                    callback(r) {
                        if (!r.message) return;
                        const { created, errors } = r.message;
                        if (errors.length) {
                            frappe.msgprint({
                                title: __("Some items failed"),
                                message: errors.join("<br><br>"),
                                indicator: "red",
                            });
                        }
                        if (created.length) {
                            frappe.show_alert({
                                message: __(`${created.length} Work Order(s) created. Refreshing data…`),
                                indicator: "green",
                            });
                            load_data();
                        }
                    },
                });
            }
        );
    });

    $(`<div id="bp-view-plan" style="padding-bottom:40px;"></div>`).appendTo(page.main);

    // ── State ─────────────────────────────────────────────────────────────────
    let _all_data = [];
    let _machine_map = {};      // { machine_name: { no_of_machines } }
    let _machine_groups = {};   // { item_code: [machine_group_name, ...] }
    let _child_options = {};    // { item_code: [{child_item_code, child_bom_qty, ...}] }
    let _dt = null;
    let _dt_observer = null;    // MutationObserver to keep checkboxes in sync
    let _selected = new Set();  // source of truth for row selection

    // ── Colour helpers ────────────────────────────────────────────────────────
    const COLOUR_STYLES = {
        BLACK: { bg: "#1a1a1a", fg: "#ffffff" },
        RED: { bg: "#e74c3c", fg: "#ffffff" },
        YELLOW: { bg: "#f1c40f", fg: "#000000" },
        GREEN: { bg: "#2ecc71", fg: "#000000" },
        WHITE: { bg: "#f0f0f0", fg: "#000000" },
    };

    function get_colour_style(val) {
        const upper = (val || "").toUpperCase();
        for (const c of ["BLACK", "RED", "YELLOW", "GREEN", "WHITE"]) {
            if (upper.endsWith(c)) return COLOUR_STYLES[c];
        }
        return null;
    }

    function colour_badge(val) {
        if (!val) return dash();
        const s = get_colour_style(val);
        if (!s) return esc(val);
        return `<span style="display:inline-block;padding:2px 10px;border-radius:3px;
			background:${s.bg};color:${s.fg};font-weight:600;font-size:11px;
			white-space:nowrap;">${esc(val)}</span>`;
    }

    function op_cp_badge(val) {
        if (!val) return dash();
        const bg = val === "OP" ? "#27ae60" : val === "CP" ? "#5dade2" : "";
        if (!bg) return esc(val);
        return `<span style="display:inline-block;padding:2px 10px;border-radius:3px;
			background:${bg};color:#fff;font-weight:600;font-size:11px;">${esc(val)}</span>`;
    }

    function esc(v) { return frappe.utils.escape_html(String(v ?? "")); }
    function dash() { return '<span style="color:#ccc;">—</span>'; }
    function fmtr(v) { return (v === null || v === undefined) ? dash() : esc(v); }

    // ── Column definitions ────────────────────────────────────────────────────
    const COLS = [
        { label: "Item Code", key: "item_code", link: "item", width: 140 },
        { label: "SKU Type", key: "sku_type", width: 100 },
        { label: "Open SO", key: "open_so", right: true, width: 80 },
        { label: "Last 3 Month Sale", key: "last_3month_sale", right: true, width: 130 },
        { label: "On Hand Stock", key: "on_hand_stock", right: true, width: 100 },
        { label: "Order Recommendation Colour", key: "on_hand_colour_priority", badge: true, width: 180 },
        { label: "Production Order Recommendation", key: "or_with_moq_batch_size", right: true, width: 200 },
        { label: "Priority", key: "priority_colour", badge: true, width: 100 },
        { label: "Priority Sequence", key: "priority_sequence", right: true, width: 120 },
        { label: "OP/CP", key: "op_cp", op_cp: true, width: 70 },
        { label: "MOQ", key: "moq", right: true, width: 70 },
        { label: "Order Multiple Qty", key: "batch_size", right: true, width: 130 },
        { label: "Child Item Code", key: "child_item_code", link: "item", width: 140 },
        { label: "Child Requirement", key: "child_requirement", right: true, width: 130 },
        { label: "Child Stock", key: "child_stock", right: true, width: 100 },
        { label: "Child Stock Soft Allocation", key: "child_stock_soft_allocation_qty", right: true, width: 180 },
        { label: "Child Stock Shortage", key: "child_stock_shortage", right: true, width: 150 },
        { label: "Child SKU Type", key: "child_sku_type", width: 110 },
        { label: "Prod Qty based on Child Stock", key: "production_qty_based_on_child_stock", right: true, width: 200 },
        { label: "Process Time based on Child Stock", key: "process_time_based_on_child_stock", right: true, width: 210 },
        { label: "Prod Qty based on Child Stock+WIP/Open PO", key: "production_qty_based_on_child_stock_wip_open_po", right: true, width: 260 },
        { label: "Per Hour Production", key: "per_hour_production", right: true, width: 140 },
        { label: "Process Time", key: "process_time", right: true, width: 110 },
    ];

    // ── th helper (used in summary panel table) ───────────────────────────────
    function th(label, right) {
        return `<th style="padding:7px 12px;background:#e8f0fe;border-bottom:2px solid #c5d8f5;
			white-space:nowrap;font-size:11px;font-weight:600;color:#1a73e8;
			${right ? "text-align:right;" : ""}">${label}</th>`;
    }

    // ── Machine select HTML ───────────────────────────────────────────────────
    function machine_select_html(row_idx, item_code, current) {
        const allowed = _machine_groups[item_code] || [];
        const options = allowed.map(m =>
            `<option value="${esc(m)}" ${m === current ? "selected" : ""}>${esc(m)}</option>`
        ).join("");
        return `<select class="bp-machine-select" data-idx="${row_idx}"
			style="border:1px solid #d1d8e0;border-radius:3px;padding:3px 6px;font-size:12px;
			background:#fff;width:100%;min-width:130px;">
			<option value=""></option>
			${options}
		</select>`;
    }

    // ── Child item select HTML ────────────────────────────────────────────────
    function child_select_html(row_idx, item_code, current) {
        const opts = _child_options[item_code] || [];
        if (opts.length <= 1) {
            return current
                ? `<a href="/app/item/${encodeURIComponent(current)}" target="_blank"
					style="font-weight:500;">${esc(current)}</a>`
                : dash();
        }
        const options_html = opts.map(o =>
            `<option value="${esc(o.child_item_code)}" ${o.child_item_code === current ? "selected" : ""}>${esc(o.child_item_code)}</option>`
        ).join("");
        return `<select class="bp-child-select" data-idx="${row_idx}"
			style="border:1px solid #d1d8e0;border-radius:3px;padding:3px 6px;font-size:12px;
			background:#fff;width:100%;min-width:120px;">${options_html}</select>`;
    }

    // ── Recalculate child-dependent fields ────────────────────────────────────
    function recalculate_child_fields(idx, child_opt) {
        const row = _all_data[idx];
        const net_order_rec = Math.ceil(parseFloat(row.or_with_moq_batch_size) || 0);
        const per_hour = parseFloat(row.per_hour_production) || 0;

        const child_bom_qty = child_opt.child_bom_qty;
        const child_bom_quantity = child_opt.child_bom_quantity || 1.0;
        const child_stock = child_opt.child_stock;
        const child_wip_open_po = child_opt.child_wip_open_po;

        const normalized_qty = child_bom_qty / child_bom_quantity;
        const child_requirement = Math.ceil(net_order_rec * normalized_qty);

        const stock_allocated = Math.min(child_requirement, child_stock);
        const stock_shortage = child_requirement - stock_allocated;
        const wip_open_po_allocated = Math.min(stock_shortage, child_wip_open_po);
        const total_allocated = stock_allocated + wip_open_po_allocated;

        const parent_per_child = child_bom_qty > 0 ? child_bom_quantity / child_bom_qty : 0;
        const prod_qty_child_stock = Math.min(Math.ceil(stock_allocated * parent_per_child), net_order_rec);
        const prod_qty_wip = Math.min(Math.ceil(total_allocated * parent_per_child), net_order_rec);
        const process_time = per_hour > 0 ? prod_qty_child_stock / per_hour : null;

        // Update state
        row.child_item_code = child_opt.child_item_code;
        row.child_sku_type = child_opt.child_sku_type;
        row.child_requirement = child_requirement;
        row.child_stock = child_stock;
        row.child_stock_soft_allocation_qty = Math.ceil(stock_allocated);
        row.child_stock_shortage = Math.ceil(stock_shortage);
        row.production_qty_based_on_child_stock = prod_qty_child_stock;
        row.process_time_based_on_child_stock = process_time !== null ? parseFloat(process_time.toFixed(2)) : null;
        row.production_qty_based_on_child_stock_wip_open_po = prod_qty_wip;
        row.child_bom_qty = child_bom_qty;
        row.child_bom_quantity = child_bom_quantity;

        // Update DOM
        $(`.bp-child-req[data-idx="${idx}"]`).text(child_requirement);
        $(`.bp-child-stock[data-idx="${idx}"]`).text(child_stock);
        $(`.bp-child-alloc[data-idx="${idx}"]`).text(Math.ceil(stock_allocated));
        $(`.bp-child-shortage[data-idx="${idx}"]`).text(Math.ceil(stock_shortage));
        $(`.bp-child-sku[data-idx="${idx}"]`).text(child_opt.child_sku_type || "—");
        $(`.bp-prod-qty-input[data-idx="${idx}"]`).val(prod_qty_child_stock);
        $(`.bp-time-stock-cell[data-idx="${idx}"]`).text(process_time !== null ? process_time.toFixed(2) : "—");
        $(`.bp-prod-wip[data-idx="${idx}"]`).text(prod_qty_wip);

        if (_selected.has(idx)) update_summary_panel();
    }

    // ── Summary panel ─────────────────────────────────────────────────────────
    function update_summary_panel() {
        // Sum process time per machine from selected rows
        const time_by_machine = {};
        _get_selected_rows().forEach(row => {
            if (row.machine) {
                time_by_machine[row.machine] = (time_by_machine[row.machine] || 0)
                    + (parseFloat(row.process_time_based_on_child_stock) || 0);
            }
        });

        // Render a row for every machine in _machine_map
        let rows_html = "";
        Object.entries(_machine_map).forEach(([machine, info]) => {
            const total_time = time_by_machine[machine] || 0;
            const no_of_machines = info.no_of_machines || 1;
            const time = no_of_machines > 0 ? total_time / no_of_machines : total_time;
            const runtime = info.runtime || 0;
            const t1 = Math.ceil(runtime / 3);        // 1/3 of runtime
            const t2 = Math.ceil(2 * runtime / 3);    // 2/3 of runtime

            let bg = "#1a1a1a", fg = "#ffffff";       // BLACK (0)
            if (time > 0) {
                if (time <= t1) { bg = "#e74c3c"; fg = "#ffffff"; }  // RED
                else if (time <= t2) { bg = "#f1c40f"; fg = "#000000"; }  // YELLOW
                else if (time <= runtime) { bg = "#2ecc71"; fg = "#000000"; }  // GREEN
                else { bg = "#f0f0f0"; fg = "#000000"; }  // WHITE (over)
            }

            rows_html += `<tr>
				<td style="padding:6px 12px;border-bottom:1px solid #dce8fb;">${esc(machine)}</td>
				<td style="padding:6px 12px;border-bottom:1px solid #dce8fb;text-align:right;">${info.no_of_machines || "—"}</td>
				<td style="padding:6px 12px;border-bottom:1px solid #dce8fb;text-align:right;">
					<span style="display:inline-block;padding:2px 10px;border-radius:3px;
						background:${bg};color:${fg};font-weight:600;min-width:50px;text-align:right;">
						${time.toFixed(2)}
					</span>
				</td>
			</tr>`;
        });

        const count = _selected.size;
        $("#bp-summary-count").text(
            count ? `${count} row${count !== 1 ? "s" : ""} selected for tomorrow's plan` : "Tomorrow's Plan"
        );
        $("#bp-summary-tbody").html(rows_html);
    }

    // ── Build DataTable ───────────────────────────────────────────────────────
    function build_datatable(data) {
        if (_dt_observer) { _dt_observer.disconnect(); _dt_observer = null; }
        if (_dt) { try { _dt.destroy(); } catch (_) { } _dt = null; }

        const dt_data = data.map((row, idx) => ({ ...row, _idx: idx }));

        const dt_columns = [
            {
                name: "Tomorrow's Plan",
                id: "_select",
                width: 90,
                editable: false,
                resizable: false,
                sortable: false,
                align: "center",
                format: (_val, _row, _col, d) =>
                    `<input type="checkbox" class="bp-row-check" data-idx="${d._idx}" ${_selected.has(d._idx) ? "checked" : ""}>`
            },
            {
                name: "Machine",
                id: "machine",
                width: 160,
                editable: false,
                format: (val, _row, _col, d) => machine_select_html(d._idx, d.item_code, val || "")
            },
            ...COLS.map(c => {
                const dt_col = {
                    name: c.label,
                    id: c.key,
                    editable: false,
                    width: c.width || 100,
                    align: c.right ? "right" : (c.badge || c.op_cp) ? "center" : "left",
                };
                if (c.key === "child_item_code") {
                    dt_col.format = (val, _row, _col, d) => child_select_html(d._idx, d.item_code, val || "");
                } else if (c.key === "child_requirement") {
                    dt_col.format = (val, _row, _col, d) =>
                        `<span class="bp-child-req" data-idx="${d._idx}">${val !== null && val !== undefined ? val : "—"}</span>`;
                } else if (c.key === "child_stock") {
                    dt_col.format = (val, _row, _col, d) =>
                        `<span class="bp-child-stock" data-idx="${d._idx}">${val !== null && val !== undefined ? val : "—"}</span>`;
                } else if (c.key === "child_stock_soft_allocation_qty") {
                    dt_col.format = (val, _row, _col, d) =>
                        `<span class="bp-child-alloc" data-idx="${d._idx}">${val !== null && val !== undefined ? val : "—"}</span>`;
                } else if (c.key === "child_stock_shortage") {
                    dt_col.format = (val, _row, _col, d) =>
                        `<span class="bp-child-shortage" data-idx="${d._idx}">${val !== null && val !== undefined ? val : "—"}</span>`;
                } else if (c.key === "child_sku_type") {
                    dt_col.format = (val, _row, _col, d) =>
                        `<span class="bp-child-sku" data-idx="${d._idx}">${val !== null && val !== undefined ? esc(val) : "—"}</span>`;
                } else if (c.key === "production_qty_based_on_child_stock_wip_open_po") {
                    dt_col.format = (val, _row, _col, d) =>
                        `<span class="bp-prod-wip" data-idx="${d._idx}">${val !== null && val !== undefined ? val : "—"}</span>`;
                } else if (c.key === "production_qty_based_on_child_stock") {
                    dt_col.format = (val, _row, _col, d) =>
                        `<input type="number" class="bp-prod-qty-input" data-idx="${d._idx}" min="0"
						value="${val !== null && val !== undefined ? val : ""}"
						style="border:1px solid #d1d8e0;border-radius:3px;padding:3px 6px;
						font-size:12px;width:80px;text-align:right;background:#fffbe6;">`;
                } else if (c.key === "process_time_based_on_child_stock") {
                    dt_col.format = (val, _row, _col, d) =>
                        `<span class="bp-time-stock-cell" data-idx="${d._idx}">${val !== null && val !== undefined ? val : "—"}</span>`;
                } else if (c.badge) {
                    dt_col.format = (val) => colour_badge(val);
                } else if (c.op_cp) {
                    dt_col.format = (val) => op_cp_badge(val);
                } else if (c.link) {
                    dt_col.format = (val) => val
                        ? `<a href="/app/${c.link}/${encodeURIComponent(val)}" target="_blank"
							style="font-weight:500;">${esc(val)}</a>`
                        : dash();
                } else {
                    dt_col.format = (val) => fmtr(val);
                }
                return dt_col;
            }),
        ];

        $("#bp-view-plan").html(`
			<div id="bp-summary-panel" style="background:#f8fbff;border:1px solid #c5d8f5;
				border-radius:6px;margin-bottom:12px;overflow:hidden;">
				<div style="padding:8px 14px;background:#e8f0fe;border-bottom:1px solid #c5d8f5;">
					<span id="bp-summary-count"
						style="font-size:12px;font-weight:600;color:#1a73e8;">Tomorrow's Plan</span>
				</div>
				<div style="padding:10px 14px;overflow-x:auto;">
					<table style="border-collapse:collapse;font-size:12px;min-width:380px;">
						<thead><tr>
							${th("Machine Name")}
							${th("No of Machines", true)}
							${th("Process Time based on Child Stock", true)}
						</tr></thead>
						<tbody id="bp-summary-tbody"></tbody>
					</table>
				</div>
			</div>

			<div style="padding:6px 4px 8px;display:flex;align-items:center;gap:12px;">
				<label style="font-size:12px;color:#555;cursor:pointer;
					display:flex;align-items:center;gap:6px;">
					<input type="checkbox" id="bp-select-all">
					<span>Select all for Tomorrow's Plan</span>
				</label>
			</div>
			<div id="bp-plan-dt" style="overflow-x:auto;"></div>
		`);

        _dt = new DataTable(document.getElementById("bp-plan-dt"), {
            columns: dt_columns,
            data: dt_data,
            serialNoColumn: false,
            checkboxColumn: false,
            inlineFilters: true,
            clusterize: false,
            noDataMessage: __("No data"),
            layout: "fixed",
        });

        update_summary_panel();

        // Re-sync checkboxes whenever DataTable re-renders rows (clusterize scroll swap)
        let _obs_timer = null;
        const dt_el = document.getElementById("bp-plan-dt");
        _dt_observer = new MutationObserver(() => {
            clearTimeout(_obs_timer);
            _obs_timer = setTimeout(() => {
                dt_el.querySelectorAll(".bp-row-check").forEach(cb => {
                    cb.checked = _selected.has(parseInt(cb.dataset.idx));
                });
            }, 30);
        });
        _dt_observer.observe(dt_el, { childList: true, subtree: true });
    }

    // ── Selection helpers ─────────────────────────────────────────────────────
    function _get_selected_rows() {
        return _all_data.filter((_, i) => _selected.has(i));
    }

    // ── Load ─────────────────────────────────────────────────────────────────
    function load_data() {
        $("#bp-view-plan").html(`<p class="text-muted" style="padding:12px;">Loading…</p>`);

        Promise.all([
            new Promise(resolve => {
                frappe.db.get_list("Bright Machine", { fields: ["name", "no_of_machines", "runtime"], limit: 500 })
                    .then(rows => resolve(rows));
            }),
            new Promise(resolve => {
                frappe.call({
                    method: "prakash_steel.prakash_steel.page.bright_plan_page.bright_plan_page.get_bright_plan_data",
                    freeze: true,
                    freeze_message: "Loading Bright Plan…",
                    callback(r) { resolve(r.message || {}); },
                });
            }),
        ]).then(([machine_rows, result]) => {
            _machine_map = {};
            machine_rows.forEach(r => { _machine_map[r.name] = { no_of_machines: r.no_of_machines || 0, runtime: r.runtime || 0 }; });
            _machine_groups = result.machine_groups || {};
            _child_options = result.child_options || {};
            _all_data = result.data || [];
            _selected.clear();
            build_datatable(_all_data);
            bind_events();
        });
    }

    // ── Events ────────────────────────────────────────────────────────────────
    function bind_events() {
        $(document).off("change", "#bp-select-all").on("change", "#bp-select-all", function () {
            if (this.checked) {
                _all_data.forEach((_, i) => _selected.add(i));
            } else {
                _selected.clear();
            }
            $(".bp-row-check").prop("checked", this.checked);
            update_summary_panel();
        });

        $(document).off("change", ".bp-row-check").on("change", ".bp-row-check", function () {
            const idx = parseInt($(this).data("idx"));
            if (this.checked) {
                _selected.add(idx);
            } else {
                _selected.delete(idx);
            }
            const total = _all_data.length;
            $("#bp-select-all").prop("indeterminate", _selected.size > 0 && _selected.size < total);
            $("#bp-select-all").prop("checked", _selected.size === total);
            update_summary_panel();
        });

        $(document).off("change", ".bp-machine-select").on("change", ".bp-machine-select", function () {
            _all_data[parseInt($(this).data("idx"))].machine = $(this).val();
            if (_selected.size > 0) update_summary_panel();
        });

        $(document).off("change", ".bp-child-select").on("change", ".bp-child-select", function () {
            const idx = parseInt($(this).data("idx"));
            const selected_child = $(this).val();
            const item_code = _all_data[idx].item_code;
            const opts = _child_options[item_code] || [];
            const child_opt = opts.find(o => o.child_item_code === selected_child);
            if (!child_opt) return;
            recalculate_child_fields(idx, child_opt);
        });

        $(document).off("input", ".bp-prod-qty-input").on("input", ".bp-prod-qty-input", function () {
            const idx = parseInt($(this).data("idx"));
            const val = $(this).val();
            let qty = val === "" ? null : parseFloat(val);
            if (qty !== null && qty < 0) { qty = 0; $(this).val(0); }
            _all_data[idx].production_qty_based_on_child_stock = qty;

            const per_hr = parseFloat(_all_data[idx].per_hour_production) || 0;
            const new_time = (qty !== null && per_hr > 0) ? qty / per_hr : null;
            _all_data[idx].process_time_based_on_child_stock = new_time;

            $(`.bp-time-stock-cell[data-idx="${idx}"]`).text(
                new_time !== null ? new_time.toFixed(2) : "—"
            );

            if (_selected.has(idx)) update_summary_panel();
        });
    }

    load_data();
};
