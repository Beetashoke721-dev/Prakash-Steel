// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt
//
// Rolling Plan — the Rolled Plan report rendered as a colourful page.
// Same columns, same server-side logic (this page calls the report's execute()
// verbatim); only the presentation differs. Filters below are client-side and
// only narrow which rows are shown — they never change the report calculation.
//
// On top of the report, like the Bright Plan page: rows can be ticked for
// "Tomorrow's Plan" (with an editable Plan Qty / start date / shift), the panel at
// the top shows the resulting Rolling Machine load, and Execute turns the ticked
// rows into draft rolled Work Orders (the user submits them).

frappe.pages["rolling-plan"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Rolling Plan"),
		single_column: true,
	});

	page.add_inner_button(__("Refresh"), () => load_data());

	page.add_inner_button(__("Export to Excel"), () => {
		if (!_shown_data.length) {
			frappe.show_alert({ message: __("Nothing to export."), indicator: "orange" });
			return;
		}
		open_url_post(
			"/api/method/prakash_steel.prakash_steel.page.rolling_plan.rolling_plan.export_rolling_plan_xlsx",
			{ rows: JSON.stringify(_shown_data) }
		);
	});

	page.add_inner_button(__("Execute"), () => {
		const selected = get_selected_rows();
		if (!selected.length) {
			frappe.show_alert({ message: __("No rows selected."), indicator: "orange" });
			return;
		}
		const valid = selected.filter((r) => flt(r.plan_qty) > 0);
		if (!valid.length) {
			frappe.show_alert({ message: __("Selected rows have no plan qty."), indicator: "orange" });
			return;
		}
		frappe.confirm(__("Create draft Work Orders for <b>{0}</b> item(s)?", [valid.length]), () => {
			frappe.call({
				method: "prakash_steel.prakash_steel.page.rolling_plan.rolling_plan.execute_work_orders",
				args: {
					rows: valid.map((r) => ({
						item_code: r.item_code,
						child_item_code: r.child_item_code,
						plan_qty: r.plan_qty,
						planned_start_date: r.planned_start_date,
						shift_type: r.shift_type,
					})),
				},
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
							message: __("{0} draft Work Order(s) created. Refreshing data…", [created.length]),
							indicator: "green",
						});
						load_data();
					}
				},
			});
		});
	});

	// ── Table colours ──────────────────────────────────────────────────────
	$(`
		<style>
			#rp-dt .dt-header {
				background: linear-gradient(180deg, #eef2ff 0%, #e0e7ff 100%) !important;
			}
			#rp-dt .dt-header .dt-cell__content {
				color: #3730a3 !important; font-weight: 700 !important; font-size: 11px;
			}
			#rp-dt .dt-row:nth-child(even) .dt-cell:not(.dt-cell--header) {
				background: #f7f8fc;
			}
			#rp-dt .dt-row:hover .dt-cell:not(.dt-cell--header) {
				background: #fff7ed !important;
			}
			#rp-dt .dt-cell--col-1 .dt-cell__content { font-weight: 600; }
			.rp-chip {
				display: inline-block; padding: 2px 9px; border-radius: 12px;
				font-size: 11px; font-weight: 600; white-space: nowrap;
			}
			.rp-num-hot { color: #b45309; font-weight: 700; }
			#rp-meta { font-size: 12px; color: #6b7280; margin: 4px 2px 10px; }
			#rp-meta b { color: #374151; }
			#rp-filters {
				display: flex; flex-wrap: wrap; gap: 12px 14px;
				margin: 6px 2px 4px;
			}
			.rp-f { display: flex; flex-direction: column; gap: 3px; }
			.rp-f > label {
				font-size: 10px; font-weight: 700; letter-spacing: .4px;
				text-transform: uppercase; color: #6366f1; margin: 0;
			}
			.rp-f > input, .rp-f > select {
				height: 28px; min-width: 150px; font-size: 12px;
				border: 1px solid #d1d5db; border-radius: 5px;
				padding: 0 8px; background: #fff; color: #111827;
			}
			.rp-f > input:focus, .rp-f > select:focus {
				outline: none; border-color: #6366f1;
				box-shadow: 0 0 0 2px rgba(99,102,241,.15);
			}
			#rp-summary-panel {
				background: #f8fbff; border: 1px solid #c5d8f5; border-radius: 6px;
				margin: 6px 2px 12px; overflow: hidden;
			}
			#rp-summary-panel .rp-summary-head {
				padding: 8px 14px; background: #e8f0fe; border-bottom: 1px solid #c5d8f5;
				font-size: 12px; font-weight: 600; color: #1a73e8;
			}
			#rp-summary-panel table { border-collapse: collapse; font-size: 12px; min-width: 380px; }
			#rp-summary-panel th {
				padding: 7px 12px; background: #e8f0fe; border-bottom: 2px solid #c5d8f5;
				white-space: nowrap; font-size: 11px; font-weight: 600; color: #1a73e8;
			}
			#rp-summary-panel td { padding: 6px 12px; border-bottom: 1px solid #dce8fb; }
			.rp-plan-input {
				border: 1px solid #d1d8e0; border-radius: 3px; padding: 3px 6px;
				font-size: 12px; width: 100%; background: #fff;
			}
			.rp-plan-input.rp-qty { text-align: right; background: #fffbe6; }
			#rp-select-all-wrap {
				font-size: 12px; color: #555; cursor: pointer; margin: 0 2px 8px;
				display: inline-flex; align-items: center; gap: 6px;
			}
		</style>
	`).appendTo(page.main);

	$(`
		<div id="rp-summary-panel">
			<div class="rp-summary-head" id="rp-summary-count">${__("Tomorrow's Plan")}</div>
			<div style="padding:10px 14px;overflow-x:auto;">
				<table>
					<thead><tr>
						<th>${__("Machine Name")}</th>
						<th style="text-align:center;">${__("No of Machines")}</th>
						<th style="text-align:right;">${__("Process Time (Hrs)")}</th>
					</tr></thead>
					<tbody id="rp-summary-tbody"></tbody>
				</table>
			</div>
		</div>
		<div id="rp-filters"></div>
		<div id="rp-meta"></div>
		<label id="rp-select-all-wrap">
			<input type="checkbox" id="rp-select-all">
			<span>${__("Select all shown rows for Tomorrow's Plan")}</span>
		</label>
		<div id="rp-view" style="padding-bottom:40px;"></div>
	`).appendTo(page.main);

	// ── Colour helpers ─────────────────────────────────────────────────────
	const COLOUR_STYLES = {
		BLACK: { bg: "#1a1a1a", fg: "#ffffff" },
		RED: { bg: "#e74c3c", fg: "#ffffff" },
		YELLOW: { bg: "#f1c40f", fg: "#000000" },
		GREEN: { bg: "#27ae60", fg: "#ffffff" },
		WHITE: { bg: "#f0f0f0", fg: "#000000" },
	};
	const COLOUR_NAMES = ["BLACK", "RED", "YELLOW", "GREEN", "WHITE"];

	function get_colour_style(val) {
		const upper = (val || "").toUpperCase();
		for (const c of COLOUR_NAMES) if (upper.endsWith(c)) return COLOUR_STYLES[c];
		return null;
	}
	function colour_name(val) {
		const upper = (val || "").toUpperCase();
		for (const c of COLOUR_NAMES) if (upper.endsWith(c)) return c;
		return "";
	}

	function esc(v) {
		return frappe.utils.escape_html(String(v ?? ""));
	}
	function dash() {
		return '<span style="color:#ccc;">—</span>';
	}

	function colour_badge(val) {
		if (!val) return dash();
		const s = get_colour_style(val);
		if (!s) return esc(val);
		return `<span style="display:inline-block;padding:2px 10px;border-radius:3px;
			background:${s.bg};color:${s.fg};font-weight:600;font-size:11px;
			white-space:nowrap;">${esc(val)}</span>`;
	}
	function colour_block(val) {
		if (!val) return dash();
		const s = get_colour_style(val);
		if (!s) return esc(val);
		return `<div style="background:${s.bg};color:${s.fg};border-radius:3px;
			padding:4px 8px;text-align:center;font-weight:600;font-size:11px;
			white-space:nowrap;">${esc(val)}</div>`;
	}

	const CHIP_PALETTE = [
		{ bg: "#ede9fe", fg: "#5b21b6" },
		{ bg: "#dbeafe", fg: "#1e40af" },
		{ bg: "#cffafe", fg: "#155e75" },
		{ bg: "#dcfce7", fg: "#166534" },
		{ bg: "#fef9c3", fg: "#854d0e" },
		{ bg: "#ffe4e6", fg: "#9f1239" },
		{ bg: "#f3e8ff", fg: "#6b21a8" },
	];
	function chip(val) {
		if (!val) return dash();
		let h = 0;
		const s = String(val);
		for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
		const c = CHIP_PALETTE[h % CHIP_PALETTE.length];
		return `<span class="rp-chip" style="background:${c.bg};color:${c.fg};">${esc(val)}</span>`;
	}

	const CHIP_FIELDS = new Set([
		"sku_type",
		"item_type",
		"shape",
		"grp",
		"sub_grp",
		"subgrp_shape",
		"grp_shape",
	]);
	const HOT_FIELDS = new Set(["net_order_recommendation", "net_qty"]);

	function fmt_value(col, val) {
		if (val === null || val === undefined || val === "") return dash();
		if (col.fieldname === "colour" || col.fieldname === "pipeline_priority") return colour_badge(val);
		if (col.fieldname === "on_hand_colour") return colour_block(val);
		if (CHIP_FIELDS.has(col.fieldname)) return chip(val);
		if (HOT_FIELDS.has(col.fieldname)) {
			const n = Math.round(flt(val));
			return n > 0 ? `<span class="rp-num-hot">${esc(n)}</span>` : esc(n);
		}
		if (col.fieldtype === "Link" && col.options) {
			const route = frappe.router.slug(col.options);
			return `<a href="/app/${route}/${encodeURIComponent(val)}" target="_blank"
				style="font-weight:500;">${esc(val)}</a>`;
		}
		if (col.fieldtype === "Float") {
			const p = col.precision ? Number(col.precision) : 2;
			return esc(flt(val, p));
		}
		if (col.fieldtype === "Int") return esc(Math.round(flt(val)));
		if (col.fieldtype === "Date") return esc(frappe.datetime.str_to_user(val));
		return esc(val);
	}

	// ── State ──────────────────────────────────────────────────────────────
	let _dt = null;
	let _columns = [];
	let _all_data = [];
	let _shown_data = [];
	let _filters_built = false;
	let _machine = {};          // Rolling Machine single: { machine_name, no_of_machines, runtime }
	let _selected = new Set();  // _idx of rows ticked for Tomorrow's Plan

	// ── Filters ────────────────────────────────────────────────────────────
	// Each entry becomes one labelled control in #rp-filters. `type` "search"
	// is a text box (substring match); "select" is a dropdown whose options are
	// either fixed (`values`) or the distinct values found in that column.
	const FILTER_DEFS = [
		{ name: "q", label: __("Item Code / Name"), type: "search" },
		{ name: "sku_type", label: __("SKU Type"), type: "select", field: "sku_type" },
		// { name: "priority", label: __("Priority"), type: "select", values: COLOUR_NAMES },
		{ name: "sub_grp", label: __("Sub Grp"), type: "select", field: "sub_grp" },
		{ name: "shape", label: __("Shape"), type: "select", field: "shape" },
	];

	function distinct(field) {
		return [
			...new Set(
				_all_data.map((r) => r[field]).filter((v) => v !== null && v !== undefined && v !== "")
			),
		]
			.map(String)
			.sort();
	}

	function build_filters() {
		if (_filters_built) return;
		_filters_built = true;

		const html = FILTER_DEFS.map((def) => {
			if (def.type === "search") {
				return `<div class="rp-f">
					<label>${def.label}</label>
					<input type="text" data-f="${def.name}" placeholder="${__("Search…")}">
				</div>`;
			}
			const values = def.values || distinct(def.field);
			// Empty option carries the filter name so an unset dropdown still reads
			// as its own label rather than a bare "All".
			const opts = [`<option value="">${def.label}</option>`]
				.concat(values.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`))
				.join("");
			return `<div class="rp-f">
				<label>${def.label}</label>
				<select data-f="${def.name}">${opts}</select>
			</div>`;
		}).join("");

		$("#rp-filters").html(html);
		$("#rp-filters").on("input change", "[data-f]", apply_filters);
	}

	function fval(name) {
		return ($(`#rp-filters [data-f="${name}"]`).val() || "").trim();
	}

	function apply_filters() {
		const ic = fval("q").toLowerCase();
		const sku = fval("sku_type");
		const prio = fval("priority");
		const sg = fval("sub_grp");
		const shp = fval("shape");

		const rows = _all_data.filter((r) => {
			if (ic) {
				const hay = `${r.item_code || ""} ${r.item_name || ""}`.toLowerCase();
				if (!hay.includes(ic)) return false;
			}
			if (sku && String(r.sku_type) !== sku) return false;
			if (prio && colour_name(r.colour) !== prio) return false;
			if (sg && String(r.sub_grp) !== sg) return false;
			if (shp && String(r.shape) !== shp) return false;
			return true;
		});

		_shown_data = rows;
		if (_dt) _dt.refresh(rows);
		render_meta(rows.length);
		sync_select_all();
	}

	function render_meta(shown) {
		$("#rp-meta").html(
			`${__("Showing")} <b>${shown}</b> ${__("of")} <b>${_all_data.length}</b> ${__("rows")}`
		);
	}

	// ── Load + render ──────────────────────────────────────────────────────
	function load_data() {
		$("#rp-view").html(`<p class="text-muted" style="padding:12px;">${__("Loading…")}</p>`);

		frappe.call({
			method: "prakash_steel.prakash_steel.page.rolling_plan.rolling_plan.get_rolling_plan_data",
			freeze: true,
			freeze_message: __("Loading Rolling Plan…"),
			callback(r) {
				const msg = r.message || {};
				_columns = msg.columns || [];
				// Only rows with an actual order recommendation are of interest here —
				// the report still computes every row (subgroup totals etc. unchanged),
				// we just don't display the zero-recommendation ones.
				_all_data = (msg.data || []).filter((r) => flt(r.net_order_recommendation) > 0);
				_machine = msg.machine || {};
				// Planning fields the user edits per row before Execute. _idx is a
				// stable row id (filters reorder/narrow the table, so DataTable's
				// own row index can't be used for selection).
				_all_data.forEach((row, idx) => {
					row._idx = idx;
					const prod = row.prod_qty_based_on_child_stock;
					row.plan_qty = prod === null || prod === undefined ? null : Math.ceil(flt(prod));
					row.plan_time = calc_plan_time(row);
					row.planned_start_date = "";
					row.shift_type = "";
				});
				_selected.clear();
				build_filters();
				build_table();
				apply_filters();
				update_summary_panel();
			},
		});
	}

	// ── Tomorrow's Plan ────────────────────────────────────────────────────
	function calc_plan_time(row) {
		const per_hr = flt(row.per_hour_qty);
		return row.plan_qty !== null && per_hr > 0 ? row.plan_qty / per_hr : null;
	}

	function get_selected_rows() {
		return _all_data.filter((r) => _selected.has(r._idx));
	}

	// Process time = (sum of selected rows' plan time) / no of machines, coloured
	// against the machine runtime in thirds — same bands as the Bright Plan.
	function update_summary_panel() {
		const no_of_machines = flt(_machine.no_of_machines) || 1;
		const runtime = flt(_machine.runtime);
		const total = get_selected_rows().reduce((s, r) => s + (flt(r.plan_time) || 0), 0);
		const time = total / no_of_machines;
		const t1 = Math.ceil(runtime / 3);
		const t2 = Math.ceil((2 * runtime) / 3);

		let style = COLOUR_STYLES.BLACK;
		if (time > 0) {
			if (time <= t1) style = COLOUR_STYLES.RED;
			else if (time <= t2) style = COLOUR_STYLES.YELLOW;
			else if (time <= runtime) style = COLOUR_STYLES.GREEN;
			else style = COLOUR_STYLES.WHITE;
		}

		$("#rp-summary-tbody").html(`<tr>
			<td>${esc(_machine.machine_name || __("Rolling Machine"))}</td>
			<td style="text-align:center;">${esc(_machine.no_of_machines || "—")}</td>
			<td style="text-align:right;">
				<span style="display:inline-block;padding:2px 10px;border-radius:3px;
					background:${style.bg};color:${style.fg};font-weight:600;min-width:50px;
					text-align:right;">${time.toFixed(1)}</span>
			</td>
		</tr>`);

		const count = _selected.size;
		$("#rp-summary-count").text(
			count
				? __("{0} row(s) selected for tomorrow's plan", [count])
				: __("Tomorrow's Plan")
		);
	}

	function sync_select_all() {
		const shown = _shown_data.length;
		const ticked = _shown_data.filter((r) => _selected.has(r._idx)).length;
		$("#rp-select-all")
			.prop("checked", shown > 0 && ticked === shown)
			.prop("indeterminate", ticked > 0 && ticked < shown);
	}

	// DataTable caches each cell's rendered HTML and re-uses it when a row scrolls
	// back into view, so an edited row's cells must be invalidated or the edit
	// appears to revert. Its row index is the position in the shown rows.
	function sync_row_cells(row, col_ids) {
		if (!_dt || !_dt.datamanager) return;
		const rowIndex = _shown_data.indexOf(row);
		if (rowIndex === -1) return;
		col_ids.forEach((col_id) => {
			const colIndex = _dt.datamanager.getColumnIndexById(col_id);
			if (colIndex === -1) return;
			_dt.datamanager.updateCell(colIndex, rowIndex, { content: row[col_id], html: null });
		});
	}

	function row_from(el) {
		return _all_data[parseInt($(el).data("idx"))];
	}

	function plan_columns() {
		const shift_opts = ["", "Day", "Night"];
		return [
			{
				name: __("Tomorrow's Plan"),
				id: "_select",
				width: 90,
				editable: false,
				resizable: false,
				sortable: false,
				dropdown: false,
				align: "center",
				format: (_v, _r, _c, d) =>
					`<input type="checkbox" class="rp-row-check" data-idx="${d._idx}"
						${_selected.has(d._idx) ? "checked" : ""}>`,
			},
			{
				name: __("Plan Qty"),
				id: "plan_qty",
				width: 100,
				editable: false,
				align: "right",
				format: (_v, _r, _c, d) =>
					`<input type="number" min="0" class="rp-plan-input rp-qty rp-plan-qty"
						data-idx="${d._idx}" value="${d.plan_qty ?? ""}">`,
			},
			{
				name: __("Process Time (Hrs)"),
				id: "plan_time",
				width: 130,
				editable: false,
				align: "right",
				format: (_v, _r, _c, d) =>
					`<span class="rp-plan-time" data-idx="${d._idx}">${
						d.plan_time === null ? "—" : flt(d.plan_time).toFixed(1)
					}</span>`,
			},
			{
				name: __("Planned Start Date"),
				id: "planned_start_date",
				width: 150,
				editable: false,
				format: (_v, _r, _c, d) =>
					`<input type="date" class="rp-plan-input rp-plan-date" data-idx="${d._idx}"
						value="${esc(d.planned_start_date)}">`,
			},
			{
				name: __("Shift Type"),
				id: "shift_type",
				width: 110,
				editable: false,
				format: (_v, _r, _c, d) =>
					`<select class="rp-plan-input rp-plan-shift" data-idx="${d._idx}">${shift_opts
						.map((o) => `<option value="${o}" ${o === d.shift_type ? "selected" : ""}>${o}</option>`)
						.join("")}</select>`,
			},
		];
	}

	// Delegated once on the page — the table is rebuilt on every load.
	$(page.main)
		.on("change", "#rp-select-all", function () {
			_shown_data.forEach((r) => (this.checked ? _selected.add(r._idx) : _selected.delete(r._idx)));
			// Block body on purpose: a jQuery .each callback returning false stops the loop.
			$(".rp-row-check").each((_, cb) => {
				cb.checked = _selected.has(parseInt(cb.dataset.idx));
			});
			// Drop the cached checkbox HTML of every shown row so rows scrolled into
			// view later are rendered already ticked (no flash of unticked boxes).
			const colIndex = _dt && _dt.datamanager ? _dt.datamanager.getColumnIndexById("_select") : -1;
			if (colIndex !== -1) {
				_shown_data.forEach((_r, rowIndex) =>
					_dt.datamanager.updateCell(colIndex, rowIndex, { html: null })
				);
			}
			sync_select_all();
			update_summary_panel();
		})
		.on("change", ".rp-row-check", function () {
			const idx = parseInt($(this).data("idx"));
			if (this.checked) _selected.add(idx);
			else _selected.delete(idx);
			sync_row_cells(_all_data[idx], ["_select"]);
			sync_select_all();
			update_summary_panel();
		})
		.on("input", ".rp-plan-qty", function () {
			const row = row_from(this);
			let qty = this.value === "" ? null : flt(this.value);
			if (qty !== null && qty < 0) {
				qty = 0;
				this.value = 0;
			}
			row.plan_qty = qty;
			row.plan_time = calc_plan_time(row);
			$(`.rp-plan-time[data-idx="${row._idx}"]`).text(
				row.plan_time === null ? "—" : row.plan_time.toFixed(1)
			);
			sync_row_cells(row, ["plan_qty", "plan_time"]);
			if (_selected.has(row._idx)) update_summary_panel();
		})
		.on("change", ".rp-plan-date", function () {
			const row = row_from(this);
			row.planned_start_date = this.value;
			sync_row_cells(row, ["planned_start_date"]);
		})
		.on("change", ".rp-plan-shift", function () {
			const row = row_from(this);
			row.shift_type = this.value;
			sync_row_cells(row, ["shift_type"]);
		});

	function build_table() {
		if (_dt) {
			try {
				_dt.destroy();
			} catch (e) {
				/* noop */
			}
			_dt = null;
		}

		const visible_cols = _columns.filter((c) => !c.hidden);
		const dt_columns = visible_cols.map((c) => {
			const right = ["Int", "Float", "Currency", "Percent"].includes(c.fieldtype);
			const centered = ["colour", "pipeline_priority", "on_hand_colour"].includes(c.fieldname);
			return {
				name: c.label,
				id: c.fieldname,
				width: c.width || 120,
				editable: false,
				align: centered ? "center" : right ? "right" : "left",
				format: (val, _row, _col, d) => fmt_value(c, d[c.fieldname]),
			};
		});

		$("#rp-view").html(`<div id="rp-dt" style="overflow-x:auto;"></div>`);

		const dt_el = document.getElementById("rp-dt");
		_dt = new DataTable(dt_el, {
			columns: [...plan_columns(), ...dt_columns],
			data: _all_data,
			serialNoColumn: true,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: true,
			noDataMessage: __("No data"),
			layout: "fixed",
		});
	}

	load_data();
};
