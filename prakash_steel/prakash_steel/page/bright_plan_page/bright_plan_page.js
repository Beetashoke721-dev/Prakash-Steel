// frappe.pages["bright-plan-page"].on_page_load = function (wrapper) {
//     const page = frappe.ui.make_app_page({
//         parent: wrapper,
//         title: "Bright Plan",
//         single_column: true,
//     });

//     page.add_inner_button(__("Refresh"), () => load_data());

//     // ── Tab bar ───────────────────────────────────────────────────────────────
//     $(`
// 		<div id="bp-tabs" style="display:flex;gap:0;border-bottom:2px solid #d1d8e0;margin-bottom:12px;">
// 			<button id="bp-tab-plan" class="bp-tab active"
// 				style="padding:8px 20px;font-size:13px;font-weight:600;border:none;background:none;
// 				cursor:pointer;border-bottom:3px solid #3498db;color:#3498db;margin-bottom:-2px;">
// 				Bright Plan
// 			</button>
// 			<button id="bp-tab-tomorrow" class="bp-tab" disabled
// 				style="padding:8px 20px;font-size:13px;font-weight:600;border:none;background:none;
// 				cursor:not-allowed;border-bottom:3px solid transparent;color:#aaa;margin-bottom:-2px;">
// 				Tomorrow's Plan <span id="bp-tab-badge" style="display:none;
// 					background:#e74c3c;color:#fff;border-radius:10px;padding:1px 7px;font-size:11px;
// 					margin-left:6px;"></span>
// 			</button>
// 		</div>

// 		<div id="bp-view-plan" style="overflow-x:auto;padding-bottom:120px;"></div>

// 		<div id="bp-view-tomorrow" style="display:none;padding-bottom:40px;">
// 			<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
// 				<span style="font-size:13px;color:#555;" id="bp-tomorrow-count"></span>
// 				<button id="bp-execute" class="btn btn-primary btn-sm"
// 					style="background:#27ae60;border-color:#27ae60;font-weight:600;padding:6px 20px;">
// 					Execute
// 				</button>
// 			</div>
// 			<div id="bp-tomorrow-table" style="overflow-x:auto;"></div>
// 		</div>
// 	`).appendTo(page.main);

//     // ── State ─────────────────────────────────────────────────────────────────
//     let _all_data = [];
//     let _machines = [];
//     let _active_tab = "plan";

//     // ── Colour helpers ────────────────────────────────────────────────────────
//     const COLOUR_STYLES = {
//         BLACK: { bg: "#1a1a1a", fg: "#ffffff" },
//         RED: { bg: "#e74c3c", fg: "#ffffff" },
//         YELLOW: { bg: "#f1c40f", fg: "#000000" },
//         GREEN: { bg: "#2ecc71", fg: "#000000" },
//         WHITE: { bg: "#f0f0f0", fg: "#000000" },
//     };

//     function get_colour_style(val) {
//         const upper = (val || "").toUpperCase();
//         for (const c of ["BLACK", "RED", "YELLOW", "GREEN", "WHITE"]) {
//             if (upper.endsWith(c)) return COLOUR_STYLES[c];
//         }
//         return null;
//     }

//     function colour_badge(val) {
//         if (!val) return dash();
//         const s = get_colour_style(val);
//         if (!s) return esc(val);
//         return `<span style="display:inline-block;padding:2px 10px;border-radius:3px;
// 			background:${s.bg};color:${s.fg};font-weight:600;font-size:11px;
// 			white-space:nowrap;">${esc(val)}</span>`;
//     }

//     function op_cp_badge(val) {
//         if (!val) return dash();
//         const bg = val === "OP" ? "#27ae60" : val === "CP" ? "#5dade2" : "";
//         if (!bg) return esc(val);
//         return `<span style="display:inline-block;padding:2px 10px;border-radius:3px;
// 			background:${bg};color:#fff;font-weight:600;font-size:11px;">${esc(val)}</span>`;
//     }

//     function esc(v) { return frappe.utils.escape_html(String(v ?? "")); }
//     function dash() { return '<span style="color:#ccc;">—</span>'; }
//     function fmtr(v) { return (v === null || v === undefined) ? dash() : esc(v); }

//     // ── Column definitions ────────────────────────────────────────────────────
//     const COLS = [
//         { label: "Item Code", key: "item_code", link: "item" },
//         { label: "SKU Type", key: "sku_type" },
//         { label: "Open SO", key: "open_so", right: true },
//         { label: "3M Sale", key: "last_3month_sale", right: true },
//         { label: "Stock", key: "on_hand_stock", right: true },
//         { label: "Colour", key: "on_hand_colour_priority", badge: true },
//         { label: "Prod Rec", key: "or_with_moq_batch_size", right: true },
//         { label: "Priority", key: "priority_colour", badge: true },
//         { label: "Seq", key: "priority_sequence", right: true },
//         { label: "OP/CP", key: "op_cp", op_cp: true },
//         { label: "MOQ", key: "moq", right: true },
//         { label: "Batch", key: "batch_size", right: true },
//         { label: "Child Item", key: "child_item_code", link: "item" },
//         { label: "Child Req", key: "child_requirement", right: true },
//         { label: "Child Stock", key: "child_stock", right: true },
//         { label: "Alloc", key: "child_stock_soft_allocation_qty", right: true },
//         { label: "Shortage", key: "child_stock_shortage", right: true },
//         { label: "Child SKU", key: "child_sku_type" },
//         { label: "Prod(Stock)", key: "production_qty_based_on_child_stock", right: true },
//         { label: "Time(Stock) h", key: "process_time_based_on_child_stock", right: true },
//         { label: "Prod(+WIP)", key: "production_qty_based_on_child_stock_wip_open_po", right: true },
//         { label: "Per Hr", key: "per_hour_production", right: true },
//         { label: "Process Hr", key: "process_time", right: true },
//     ];

//     // ── Render helpers ────────────────────────────────────────────────────────
//     function th(label, right, extra_style) {
//         return `<th style="padding:7px 10px;background:#f4f5f7;border-bottom:2px solid #d1d8e0;
// 			white-space:nowrap;font-size:11px;font-weight:600;color:#555;position:sticky;top:0;z-index:1;
// 			${right ? "text-align:right;" : ""}${extra_style || ""}">${label}</th>`;
//     }

//     function machine_select(row_idx, current) {
//         const options = _machines.map(m =>
//             `<option value="${esc(m)}" ${m === current ? "selected" : ""}>${esc(m)}</option>`
//         ).join("");
//         return `<select class="bp-machine-select" data-idx="${row_idx}"
// 			style="border:1px solid #d1d8e0;border-radius:3px;padding:3px 6px;font-size:12px;
// 			background:#fff;width:100%;min-width:130px;">
// 			<option value="">— none —</option>
// 			${options}
// 		</select>`;
//     }

//     function td_cell(col, row, row_idx) {
//         if (col.key === "machine") {
//             return `<td style="padding:4px 8px;border-bottom:1px solid #eef0f3;">
// 				${machine_select(row_idx, row.machine || "")}
// 			</td>`;
//         }
//         if (col.key === "production_qty_based_on_child_stock") {
//             const v = row[col.key];
//             return `<td style="padding:4px 8px;border-bottom:1px solid #eef0f3;text-align:right;">
// 				<input type="number" class="bp-prod-qty-input" data-idx="${row_idx}"
// 					value="${v !== null && v !== undefined ? v : ""}"
// 					style="border:1px solid #d1d8e0;border-radius:3px;padding:3px 6px;font-size:12px;
// 					width:80px;text-align:right;background:#fffbe6;">
// 			</td>`;
//         }
//         const v = row[col.key];
//         let content;
//         if (col.badge) {
//             content = colour_badge(v);
//         } else if (col.op_cp) {
//             content = op_cp_badge(v);
//         } else if (col.link && v) {
//             content = `<a href="/app/${col.link}/${encodeURIComponent(v)}" target="_blank"
// 				style="font-weight:500;">${esc(v)}</a>`;
//         } else {
//             content = fmtr(v);
//         }
//         const align = (col.badge || col.op_cp) ? "text-align:center;" : col.right ? "text-align:right;" : "";
//         return `<td style="padding:5px 10px;border-bottom:1px solid #eef0f3;${align}">${content}</td>`;
//     }

//     function build_table(data, include_checkbox) {
//         const machine_th = th("Machine", false, "min-width:140px;");
//         let header_row = machine_th + COLS.map(c => th(c.label, c.right)).join("");
//         if (include_checkbox) {
//             header_row = th(
//                 `<div style="white-space:nowrap;">Tomorrow's Plan<br>
// 				<input type="checkbox" id="bp-select-all" title="Select all" style="margin-top:4px;"></div>`,
//                 false, "text-align:center;min-width:90px;"
//             ) + header_row;
//         }

//         let html = `<table style="width:100%;border-collapse:collapse;font-size:12px;">
// 			<thead><tr>${header_row}</tr></thead><tbody>`;

//         const machine_col = { label: "Machine", key: "machine" };
//         data.forEach((row, idx) => {
//             let row_html = td_cell(machine_col, row, idx) + COLS.map(c => td_cell(c, row, idx)).join("");
//             if (include_checkbox) {
//                 row_html = `<td style="padding:5px 10px;border-bottom:1px solid #eef0f3;text-align:center;">
// 					<input type="checkbox" class="bp-row-check" data-idx="${idx}">
// 				</td>` + row_html;
//             }
//             html += `<tr onmouseover="this.style.background='#fafbfc'" onmouseout="this.style.background=''">${row_html}</tr>`;
//         });

//         html += "</tbody></table>";
//         return html;
//     }

//     // ── Tab switching ─────────────────────────────────────────────────────────
//     function switch_tab(tab) {
//         _active_tab = tab;
//         if (tab === "plan") {
//             $("#bp-view-plan").show();
//             $("#bp-view-tomorrow").hide();
//             $("#bp-tab-plan")
//                 .css({ "border-bottom-color": "#3498db", "color": "#3498db", "cursor": "pointer" });
//             $("#bp-tab-tomorrow")
//                 .css({ "border-bottom-color": "transparent", "color": _get_selected_rows().length ? "#555" : "#aaa" });
//         } else {
//             $("#bp-view-plan").hide();
//             $("#bp-view-tomorrow").show();
//             $("#bp-tab-tomorrow")
//                 .css({ "border-bottom-color": "#27ae60", "color": "#27ae60", "cursor": "pointer" });
//             $("#bp-tab-plan")
//                 .css({ "border-bottom-color": "transparent", "color": "#555" });
//             render_tomorrow_tab();
//         }
//     }

//     // ── Selection helpers ─────────────────────────────────────────────────────
//     function _get_selected_rows() {
//         const selected = [];
//         $(".bp-row-check:checked").each(function () {
//             selected.push(_all_data[parseInt($(this).data("idx"))]);
//         });
//         return selected;
//     }

//     function update_tomorrow_tab_state() {
//         const count = _get_selected_rows().length;
//         const $tab = $("#bp-tab-tomorrow");
//         if (count > 0) {
//             $tab.prop("disabled", false).css({ "cursor": "pointer", "color": "#555" });
//             $("#bp-tab-badge").text(count).show();
//         } else {
//             $tab.prop("disabled", true).css({ "cursor": "not-allowed", "color": "#aaa" });
//             $("#bp-tab-badge").hide();
//             if (_active_tab === "tomorrow") switch_tab("plan");
//         }
//     }

//     function render_tomorrow_tab() {
//         const selected = _get_selected_rows();
//         $("#bp-tomorrow-count").text(`${selected.length} row${selected.length !== 1 ? "s" : ""} selected for tomorrow's plan`);
//         $("#bp-tomorrow-table").html(build_table(selected, false));
//     }

//     // ── Load ─────────────────────────────────────────────────────────────────
//     function load_data() {
//         $("#bp-view-plan").html(`<p class="text-muted" style="padding:12px;">Loading…</p>`);
//         switch_tab("plan");
//         update_tomorrow_tab_state();

//         Promise.all([
//             new Promise(resolve => {
//                 frappe.db.get_list("Bright Machine", { fields: ["name"], limit: 500 })
//                     .then(rows => resolve(rows.map(r => r.name)));
//             }),
//             new Promise(resolve => {
//                 frappe.call({
//                     method: "prakash_steel.prakash_steel.page.bright_plan_page.bright_plan_page.get_bright_plan_data",
//                     freeze: true,
//                     freeze_message: "Loading Bright Plan…",
//                     callback(r) { resolve((r.message && r.message.data) || []); },
//                 });
//             }),
//         ]).then(([machines, data]) => {
//             _machines = machines;
//             _all_data = data;
//             $("#bp-view-plan").html(build_table(_all_data, true));
//             bind_events();
//         });
//     }

//     // ── Events ────────────────────────────────────────────────────────────────
//     function bind_events() {
//         $(document).off("change", "#bp-select-all").on("change", "#bp-select-all", function () {
//             $(".bp-row-check").prop("checked", this.checked);
//             update_tomorrow_tab_state();
//         });

//         $(document).off("change", ".bp-row-check").on("change", ".bp-row-check", function () {
//             const total = $(".bp-row-check").length;
//             const checked = $(".bp-row-check:checked").length;
//             $("#bp-select-all").prop("indeterminate", checked > 0 && checked < total);
//             $("#bp-select-all").prop("checked", checked === total);
//             update_tomorrow_tab_state();
//         });

//         $(document).off("change", ".bp-machine-select").on("change", ".bp-machine-select", function () {
//             _all_data[parseInt($(this).data("idx"))].machine = $(this).val();
//         });

//         $(document).off("input", ".bp-prod-qty-input").on("input", ".bp-prod-qty-input", function () {
//             const val = $(this).val();
//             _all_data[parseInt($(this).data("idx"))].production_qty_based_on_child_stock =
//                 val === "" ? null : parseFloat(val);
//         });
//     }

//     // ── Tab click events ──────────────────────────────────────────────────────
//     $("#bp-tab-plan").on("click", () => switch_tab("plan"));
//     $("#bp-tab-tomorrow").on("click", function () {
//         if (!$(this).prop("disabled")) switch_tab("tomorrow");
//     });

//     // ── Execute ───────────────────────────────────────────────────────────────
//     $("#bp-execute").on("click", function () {
//         const selected = _get_selected_rows();
//         // Logic to be added
//         console.log("Execute with:", selected);
//         frappe.show_alert({ message: `${selected.length} row(s) ready for execution.`, indicator: "blue" });
//     });

//     load_data();
// };
