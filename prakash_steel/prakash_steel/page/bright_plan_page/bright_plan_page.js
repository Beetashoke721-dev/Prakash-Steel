frappe.pages["bright-plan-page"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Bright Plan",
        single_column: true,
    });

    page.add_inner_button(__("Refresh"), () => load_data());
    page.add_inner_button(__("Execute"), () => {
        const selected = _get_selected_rows();
        // Logic to be added
        console.log("Execute with:", selected);
        frappe.show_alert({ message: `${selected.length} row(s) ready for execution.`, indicator: "blue" });
    });

    $(`<div id="bp-view-plan" style="padding-bottom:40px;"></div>`).appendTo(page.main);

    // ── State ─────────────────────────────────────────────────────────────────
    let _all_data = [];
    let _machine_map = {};      // { machine_name: { no_of_machines } }
    let _machine_groups = {};   // { item_code: [machine_group_name, ...] }
    let _dt = null;
    let _selected = new Set();  // source of truth for row selection

    // ── Colour helpers ────────────────────────────────────────────────────────
    const COLOUR_STYLES = {
        BLACK: { bg: "#1a1a1a", fg: "#ffffff" },
        RED:   { bg: "#e74c3c", fg: "#ffffff" },
        YELLOW:{ bg: "#f1c40f", fg: "#000000" },
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

    function esc(v)  { return frappe.utils.escape_html(String(v ?? "")); }
    function dash()  { return '<span style="color:#ccc;">—</span>'; }
    function fmtr(v) { return (v === null || v === undefined) ? dash() : esc(v); }

    // ── Column definitions ────────────────────────────────────────────────────
    const COLS = [
        { label: "Item Code",                                key: "item_code",                                    link: "item", width: 140 },
        { label: "SKU Type",                                 key: "sku_type",                                                   width: 100 },
        { label: "Open SO",                                  key: "open_so",                          right: true,              width: 80  },
        { label: "Last 3 Month Sale",                        key: "last_3month_sale",                 right: true,              width: 130 },
        { label: "On Hand Stock",                            key: "on_hand_stock",                    right: true,              width: 100 },
        { label: "Order Recommendation Colour",              key: "on_hand_colour_priority",          badge: true,              width: 180 },
        { label: "Production Order Recommendation",          key: "or_with_moq_batch_size",           right: true,              width: 200 },
        { label: "Priority",                                 key: "priority_colour",                  badge: true,              width: 100 },
        { label: "Priority Sequence",                        key: "priority_sequence",                right: true,              width: 120 },
        { label: "OP/CP",                                    key: "op_cp",                            op_cp: true,              width: 70  },
        { label: "MOQ",                                      key: "moq",                              right: true,              width: 70  },
        { label: "Order Multiple Qty",                       key: "batch_size",                       right: true,              width: 130 },
        { label: "Child Item Code",                          key: "child_item_code",                  link: "item", width: 140 },
        { label: "Child Requirement",                        key: "child_requirement",                right: true,              width: 130 },
        { label: "Child Stock",                              key: "child_stock",                      right: true,              width: 100 },
        { label: "Child Stock Soft Allocation",              key: "child_stock_soft_allocation_qty",  right: true,              width: 180 },
        { label: "Child Stock Shortage",                     key: "child_stock_shortage",             right: true,              width: 150 },
        { label: "Child SKU Type",                           key: "child_sku_type",                                             width: 110 },
        { label: "Prod Qty based on Child Stock",            key: "production_qty_based_on_child_stock",              right: true, width: 200 },
        { label: "Process Time based on Child Stock",        key: "process_time_based_on_child_stock",               right: true, width: 210 },
        { label: "Prod Qty based on Child Stock+WIP/Open PO",key: "production_qty_based_on_child_stock_wip_open_po", right: true, width: 260 },
        { label: "Per Hour Production",                      key: "per_hour_production",              right: true,              width: 140 },
        { label: "Process Time",                             key: "process_time",                     right: true,              width: 110 },
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
			<option value="">— none —</option>
			${options}
		</select>`;
    }

    // ── Summary panel ─────────────────────────────────────────────────────────
    function update_summary_panel() {
        const count = _selected.size;
        const $panel = $("#bp-summary-panel");

        if (count === 0) {
            $panel.slideUp(200);
            return;
        }

        // Group selected rows by machine, sum Time(Stock) h
        const grouped = {};
        _get_selected_rows().forEach(row => {
            const machine = row.machine || "— none —";
            if (!grouped[machine]) grouped[machine] = { no_of_machines: 0, time_stock_h: 0 };
            grouped[machine].time_stock_h += (parseFloat(row.process_time_based_on_child_stock) || 0);
            if (row.machine && _machine_map[row.machine]) {
                grouped[machine].no_of_machines = _machine_map[row.machine].no_of_machines;
            }
        });

        let rows_html = "";
        Object.entries(grouped).forEach(([machine, vals]) => {
            rows_html += `<tr>
				<td style="padding:6px 12px;border-bottom:1px solid #dce8fb;">${esc(machine)}</td>
				<td style="padding:6px 12px;border-bottom:1px solid #dce8fb;text-align:right;">${vals.no_of_machines || "—"}</td>
				<td style="padding:6px 12px;border-bottom:1px solid #dce8fb;text-align:right;">${vals.time_stock_h.toFixed(2)}</td>
			</tr>`;
        });

        $("#bp-summary-count").text(
            `${count} row${count !== 1 ? "s" : ""} selected for tomorrow's plan`
        );
        $("#bp-summary-tbody").html(rows_html);

        if (!$panel.is(":visible")) $panel.slideDown(220);
    }

    // ── Build DataTable ───────────────────────────────────────────────────────
    function build_datatable(data) {
        if (_dt) { try { _dt.destroy(); } catch (_) {} _dt = null; }

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
                if (c.key === "production_qty_based_on_child_stock") {
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
			<div id="bp-summary-panel" style="display:none;background:#f8fbff;border:1px solid #c5d8f5;
				border-radius:6px;margin-bottom:12px;overflow:hidden;">
				<div style="display:flex;align-items:center;justify-content:space-between;
					padding:8px 14px;background:#e8f0fe;border-bottom:1px solid #c5d8f5;">
					<span id="bp-summary-count"
						style="font-size:12px;font-weight:600;color:#1a73e8;"></span>
					<button id="bp-summary-close"
						style="border:none;background:none;cursor:pointer;font-size:18px;
						color:#888;line-height:1;padding:0 4px;">&times;</button>
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

        $(document).off("click", "#bp-summary-close").on("click", "#bp-summary-close", function () {
            _selected.clear();
            $(".bp-row-check").prop("checked", false);
            $("#bp-select-all").prop("checked", false).prop("indeterminate", false);
            $("#bp-summary-panel").slideUp(200);
        });

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
                frappe.db.get_list("Bright Machine", { fields: ["name", "no_of_machines"], limit: 500 })
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
            machine_rows.forEach(r => { _machine_map[r.name] = { no_of_machines: r.no_of_machines || 0 }; });
            _machine_groups = result.machine_groups || {};
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
