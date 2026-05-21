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

    // ── Tab bar ───────────────────────────────────────────────────────────────
    $(`
		<div id="bp-tabs" style="display:flex;gap:0;border-bottom:2px solid #d1d8e0;margin-bottom:12px;">
			<button id="bp-tab-plan" class="bp-tab active"
				style="padding:8px 20px;font-size:13px;font-weight:600;border:none;background:none;
				cursor:pointer;border-bottom:3px solid #3498db;color:#3498db;margin-bottom:-2px;">
				Bright Plan
			</button>
			<button id="bp-tab-tomorrow" class="bp-tab" disabled
				style="padding:8px 20px;font-size:13px;font-weight:600;border:none;background:none;
				cursor:not-allowed;border-bottom:3px solid transparent;color:#aaa;margin-bottom:-2px;">
				Tomorrow's Plan <span id="bp-tab-badge" style="display:none;
					background:#e74c3c;color:#fff;border-radius:10px;padding:1px 7px;font-size:11px;
					margin-left:6px;"></span>
			</button>
		</div>

		<div id="bp-view-plan" style="padding-bottom:40px;"></div>

		<div id="bp-view-tomorrow" style="display:none;padding-bottom:40px;">
			<div style="margin-bottom:12px;">
				<span style="font-size:13px;color:#555;" id="bp-tomorrow-count"></span>
			</div>
			<div id="bp-tomorrow-table" style="overflow-x:auto;"></div>
		</div>
	`).appendTo(page.main);

    // ── State ─────────────────────────────────────────────────────────────────
    let _all_data = [];
    let _machines = [];
    let _machine_map = {};      // { machine_name: { no_of_machines } }
    let _machine_groups = {};   // { item_code: [machine_group_name, ...] }
    let _active_tab = "plan";
    let _dt = null;
    let _selected = new Set();  // tracks selected row indices (source of truth)

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
        { label: "Item Code",    key: "item_code",                                    link: "item", width: 140 },
        { label: "SKU Type",     key: "sku_type",                                                   width: 100 },
        { label: "Open SO",      key: "open_so",                          right: true,              width: 80  },
        { label: "3M Sale",      key: "last_3month_sale",                 right: true,              width: 80  },
        { label: "Stock",        key: "on_hand_stock",                    right: true,              width: 80  },
        { label: "Colour",       key: "on_hand_colour_priority",          badge: true,              width: 100 },
        { label: "Prod Rec",     key: "or_with_moq_batch_size",           right: true,              width: 80  },
        { label: "Priority",     key: "priority_colour",                  badge: true,              width: 100 },
        { label: "Seq",          key: "priority_sequence",                right: true,              width: 60  },
        { label: "OP/CP",        key: "op_cp",                            op_cp: true,              width: 70  },
        { label: "MOQ",          key: "moq",                              right: true,              width: 70  },
        { label: "Batch",        key: "batch_size",                       right: true,              width: 70  },
        { label: "Child Item",   key: "child_item_code",                  link: "item", width: 140 },
        { label: "Child Req",    key: "child_requirement",                right: true,              width: 80  },
        { label: "Child Stock",  key: "child_stock",                      right: true,              width: 80  },
        { label: "Alloc",        key: "child_stock_soft_allocation_qty",  right: true,              width: 70  },
        { label: "Shortage",     key: "child_stock_shortage",             right: true,              width: 80  },
        { label: "Child SKU",    key: "child_sku_type",                                             width: 90  },
        { label: "Prod(Stock)",  key: "production_qty_based_on_child_stock",             right: true, width: 100 },
        { label: "Time(Stock) h",key: "process_time_based_on_child_stock",              right: true, width: 100 },
        { label: "Prod(+WIP)",   key: "production_qty_based_on_child_stock_wip_open_po",right: true, width: 100 },
        { label: "Per Hr",       key: "per_hour_production",              right: true,              width: 70  },
        { label: "Process Hr",   key: "process_time",                     right: true,              width: 80  },
    ];

    // ── th helper (used for tomorrow's plan table only) ───────────────────────
    function th(label, right, extra_style) {
        return `<th style="padding:7px 10px;background:#f4f5f7;border-bottom:2px solid #d1d8e0;
			white-space:nowrap;font-size:11px;font-weight:600;color:#555;
			${right ? "text-align:right;" : ""}${extra_style || ""}">${label}</th>`;
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
                        `<input type="number" class="bp-prod-qty-input" data-idx="${d._idx}"
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

        // Toolbar with select-all above the DataTable
        $("#bp-view-plan").html(`
			<div id="bp-plan-toolbar" style="padding:6px 4px 8px;display:flex;align-items:center;gap:12px;">
				<label style="font-size:12px;color:#555;cursor:pointer;display:flex;align-items:center;gap:6px;">
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
    }

    // ── Tab switching ─────────────────────────────────────────────────────────
    function switch_tab(tab) {
        _active_tab = tab;
        if (tab === "plan") {
            $("#bp-view-plan").show();
            $("#bp-view-tomorrow").hide();
            $("#bp-tab-plan")
                .css({ "border-bottom-color": "#3498db", "color": "#3498db", "cursor": "pointer" });
            $("#bp-tab-tomorrow")
                .css({ "border-bottom-color": "transparent", "color": _get_selected_rows().length ? "#555" : "#aaa" });
        } else {
            $("#bp-view-plan").hide();
            $("#bp-view-tomorrow").show();
            $("#bp-tab-tomorrow")
                .css({ "border-bottom-color": "#27ae60", "color": "#27ae60", "cursor": "pointer" });
            $("#bp-tab-plan")
                .css({ "border-bottom-color": "transparent", "color": "#555" });
            render_tomorrow_tab();
        }
    }

    // ── Selection helpers ─────────────────────────────────────────────────────
    function _get_selected_rows() {
        return _all_data.filter((_, i) => _selected.has(i));
    }

    function update_tomorrow_tab_state() {
        const count = _selected.size;
        const $tab = $("#bp-tab-tomorrow");
        if (count > 0) {
            $tab.prop("disabled", false).css({ "cursor": "pointer", "color": "#555" });
            $("#bp-tab-badge").text(count).show();
        } else {
            $tab.prop("disabled", true).css({ "cursor": "not-allowed", "color": "#aaa" });
            $("#bp-tab-badge").hide();
            if (_active_tab === "tomorrow") switch_tab("plan");
        }
    }

    function render_tomorrow_tab() {
        const selected = _get_selected_rows();
        $("#bp-tomorrow-count").text(`${selected.length} row${selected.length !== 1 ? "s" : ""} selected for tomorrow's plan`);

        // Group by machine, sum Time(Stock) h
        const grouped = {};
        selected.forEach(row => {
            const machine = row.machine || "— none —";
            if (!grouped[machine]) grouped[machine] = { no_of_machines: 0, time_stock_h: 0 };
            grouped[machine].time_stock_h += (parseFloat(row.process_time_based_on_child_stock) || 0);
            if (row.machine && _machine_map[row.machine]) {
                grouped[machine].no_of_machines = _machine_map[row.machine].no_of_machines;
            }
        });

        let html = `<table style="width:auto;border-collapse:collapse;font-size:12px;">
            <thead><tr>
                ${th("Machine Name", false, "min-width:160px;")}
                ${th("No of Machines", true)}
                ${th("Time(Stock) h", true)}
            </tr></thead><tbody>`;

        Object.entries(grouped).forEach(([machine, vals]) => {
            html += `<tr onmouseover="this.style.background='#fafbfc'" onmouseout="this.style.background=''">
                <td style="padding:6px 12px;border-bottom:1px solid #eef0f3;">${esc(machine)}</td>
                <td style="padding:6px 12px;border-bottom:1px solid #eef0f3;text-align:right;">${vals.no_of_machines || dash()}</td>
                <td style="padding:6px 12px;border-bottom:1px solid #eef0f3;text-align:right;">${vals.time_stock_h.toFixed(2)}</td>
            </tr>`;
        });

        html += "</tbody></table>";
        $("#bp-tomorrow-table").html(html);
    }

    // ── Load ─────────────────────────────────────────────────────────────────
    function load_data() {
        $("#bp-view-plan").html(`<p class="text-muted" style="padding:12px;">Loading…</p>`);
        switch_tab("plan");
        update_tomorrow_tab_state();

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
            _machines = machine_rows.map(r => r.name);
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
            update_tomorrow_tab_state();
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
            update_tomorrow_tab_state();
        });

        $(document).off("change", ".bp-machine-select").on("change", ".bp-machine-select", function () {
            _all_data[parseInt($(this).data("idx"))].machine = $(this).val();
        });

        $(document).off("input", ".bp-prod-qty-input").on("input", ".bp-prod-qty-input", function () {
            const idx = parseInt($(this).data("idx"));
            const val = $(this).val();
            const qty = val === "" ? null : parseFloat(val);
            _all_data[idx].production_qty_based_on_child_stock = qty;

            const per_hr = parseFloat(_all_data[idx].per_hour_production) || 0;
            const new_time = (qty !== null && per_hr > 0) ? qty / per_hr : null;
            _all_data[idx].process_time_based_on_child_stock = new_time;

            $(`.bp-time-stock-cell[data-idx="${idx}"]`).text(
                new_time !== null ? new_time.toFixed(2) : "—"
            );
        });
    }

    // ── Tab click events ──────────────────────────────────────────────────────
    $("#bp-tab-plan").on("click", () => switch_tab("plan"));
    $("#bp-tab-tomorrow").on("click", function () {
        if (!$(this).prop("disabled")) switch_tab("tomorrow");
    });

    load_data();
};
