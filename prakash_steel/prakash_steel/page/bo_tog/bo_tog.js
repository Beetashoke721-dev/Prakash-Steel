frappe.pages["bo-tog"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "BO TOG",
		single_column: true,
	});

	const view_by_field = page.add_field({
		fieldname: "view_by",
		label: __("View By"),
		fieldtype: "Select",
		options: [
			"Sale Quantity",
			// "Sale Value",   // not yet implemented
			// "Throughput",   // not yet implemented
		],
		default: "Sale Quantity",
		change() { load_data(); },
	});

	const sku_type_field = page.add_field({
		fieldname: "sku_type",
		label: __("SKU Type"),
		fieldtype: "Select",
		options: ["", "BOTA", "BOTO"],
		default: "",
		change() { apply_filter(); },
	});

	const item_code_field = page.add_field({
		fieldname: "item_code",
		label: __("Item Code"),
		fieldtype: "Link",
		options: "Item",
		get_query() {
			return {
				filters: {
					custom_item_type: "BO",
					custom_sku_type: ["in", ["BOTA", "BOTO"]],
					disabled: 0,
				},
			};
		},
		change() { apply_filter(); },
	});

	const fos_field = page.add_field({
		fieldname: "global_fos",
		label: __("FOS %"),
		fieldtype: "Int",
		change() {
			const v = parseInt(fos_field.get_value());
			_active_fos = isNaN(v) ? 30 : v;
			apply_global_fos();
		},
	});

	page.add_inner_button(__("Refresh"), () => load_data());
	page.add_inner_button(__("Export to Excel"), () => export_to_xlsx());
	page.add_inner_button(__("Save"), () => save_selected());
	page.add_inner_button(__("Update Buffer & TOG"), () => update_tog_selected());
	page.add_inner_button(__("Reset"), () => reset_selected());

	$(`<div id="bot-root" style="padding:16px 4px 40px;"></div>`).appendTo(page.main);

	$(`<style>
		#bot-dt .dt-row-header .dt-cell__content,
		#bot-dt .dt-row-header .content { text-align: left !important; }
	</style>`).appendTo(document.head);

	// ── HBT colour palette ────────────────────────────────────────────────────
	const HBT = {
		H: { bg: "#1a7a3f", fg: "#ffffff", light: "#e8f5ee" },
		B: { bg: "#d4a000", fg: "#ffffff", light: "#fdf7e3" },
		T: { bg: "#c0152a", fg: "#ffffff", light: "#fdecea" },
	};

	function hbt_badge(val) {
		if (val === "NS") {
			return `<span style="display:inline-block;padding:2px 10px;border-radius:4px;
				background:#9e9e9e;color:#ffffff;font-weight:700;font-size:12px;
				letter-spacing:1px;">NS</span>`;
		}
		if (!val || !HBT[val]) return `<span style="color:#ccc;">—</span>`;
		const c = HBT[val];
		return `<span style="display:inline-block;padding:2px 10px;border-radius:4px;
			background:${c.bg};color:${c.fg};font-weight:700;font-size:12px;
			letter-spacing:1px;">${val}</span>`;
	}

	function num_badge(val, hbt_key) {
		if (val === null || val === undefined) return `<span style="color:#ccc;">—</span>`;
		const n = parseFloat(val);
		if (!n) return `<span style="color:#bbb;">0</span>`;
		const c = HBT[hbt_key];
		return `<span style="display:inline-block;padding:1px 8px;border-radius:3px;
			background:${c.light};color:${c.bg};font-weight:600;font-size:12px;">${fmt_num(n, 0)}</span>`;
	}

	function fmt_num(v, dec = 1) {
		if (v === null || v === undefined) return "—";
		return parseFloat(v).toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec });
	}

	function fmt_pct(v) {
		if (v === null || v === undefined) return "—";
		return parseFloat(v).toFixed(1) + "%";
	}

	function esc(v) { return frappe.utils.escape_html(String(v ?? "")); }
	function dash() { return '<span style="color:#ccc;">—</span>'; }
	function ceil1000(v) { return Math.ceil(v / 1000) * 1000; }
	function new_tog_color(new_tog_val, calc_tog) {
		if (new_tog_val === null || new_tog_val === undefined || new_tog_val === "") return "inherit";
		const nt = parseInt(new_tog_val), ct = parseInt(calc_tog) || 0;
		if (ct > nt) return "#c62828";
		if (nt > ct) return "#2e7d32";
		return "inherit";
	}


	function fmt_change_pct(val, idx) {
		if (val === null || val === undefined) {
			return `<span class="bot-change-pct" data-idx="${idx}" style="color:#ccc;">—</span>`;
		}
		const n = parseFloat(val);
		const color = n > 0 ? "#1a7a3f" : n < 0 ? "#c0152a" : "#888";
		const arrow = n > 0 ? "▲" : n < 0 ? "▼" : "";
		return `<span class="bot-change-pct" data-idx="${idx}"
			style="font-weight:600;color:${color};">${Math.abs(n).toFixed(1)}% ${arrow}</span>`;
	}

	let _active_fos = 30; // current in-effect FOS%, decoupled from the field's async set_value
	let _last_fos = 30; // baseline FOS% from TOG Horizon Setting that Reset reverts to

	function get_global_fos() {
		return _active_fos;
	}

	function apply_global_fos() {
		const fos = get_global_fos();
		_all_data.forEach(row => {
			row.fos = fos;
			row.tog = ceil1000((row.adu || 0) * (row.lt || 0) * (1 + fos / 100));
			const current_tog = row.current_tog || 0;
			row.change_pct = current_tog
				? Math.round((row.tog - current_tog) / current_tog * 1000) / 10
				: null;
		});
		if (_dt) _dt.refresh(_all_data);
	}

	// ── DataTable ─────────────────────────────────────────────────────────────
	let _dt = null;
	let _dt_observer = null;
	let _all_data = [];
	let _raw_data = [];
	let _selected = new Set();

	function update_selected_count() {
		$("#bot-selected-count").text(`${__("Selected")}: ${_selected.size} / ${_all_data.length}`);
	}

	function apply_filter() {
		const sku = sku_type_field.get_value();
		const item = item_code_field.get_value();
		const filtered = _raw_data.filter(r => {
			if (sku && r.sku_type !== sku) return false;
			if (item && r.item_code !== item) return false;
			return true;
		});
		const _gfos = get_global_fos();
		const _new_tog_map = {};
		_all_data.forEach(r => { _new_tog_map[r.item_code] = r.new_tog; });
		_all_data = filtered.map((row, idx) => {
			const fos = _gfos;
			const tog = ceil1000((row.adu || 0) * (row.lt || 0) * (1 + fos / 100));
			const current_tog = row.current_tog || 0;
			const change_pct = current_tog ? Math.round((tog - current_tog) / current_tog * 1000) / 10 : null;
			return { ...row, _idx: idx, fos, tog, change_pct, new_tog: row.item_code in _new_tog_map ? _new_tog_map[row.item_code] : (row.new_tog ?? ((row.buffer_flag || "Non-Buffer") === "Buffer" ? tog : null)) };
		});
		_selected.clear();

		_all_data.forEach((row, i) => { if (row.sku_type === "BOTA") _selected.add(i); });
		update_selected_count();
		if (_dt_observer) { _dt_observer.disconnect(); _dt_observer = null; }
		if (_dt) { try { _dt.destroy(); } catch (_) {} _dt = null; }
		_dt = new DataTable(document.getElementById("bot-dt"), {
			columns: COLS,
			data: _all_data,
			serialNoColumn: false,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: false,
			noDataMessage: __("No items found."),
			layout: "fixed",
		});
		setup_dt_observer("bot-dt");
		apply_table_styles("bot-dt");
		bind_events();
	}

	const COLS = [
		{
			name: "", id: "_select", width: 40, align: "center", editable: false,
			resizable: false, sortable: false,
			format: (_val, _r, _c, d) =>
				`<input type="checkbox" class="bot-row-check" data-idx="${d._idx}" ${_selected.has(d._idx) ? "checked" : ""}>`,
		},
		{
			name: "", id: "_idx", width: 55, align: "center", editable: false,
			format: (_val, _r, _c, d) => `<span style="color:#888;font-size:12px;">${d._idx + 1}</span>`,
		},
		{
			name: "SKU Type", id: "sku_type", width: 110, align: "center", editable: false,
			format: (val, _r, _c, d) => `<span class="bot-sku-type" data-idx="${d._idx}">${val ? esc(val) : '—'}</span>`,
		},
		{
			name: "Item Code", id: "item_code", width: 200, align: "center", editable: false,
			format: val => val
				? `<span class="bot-item-link" data-item="${esc(val)}"
					style="color:#1a73e8;font-weight:500;cursor:pointer;">${esc(val)}</span>`
				: dash(),
		},
		{
			name: "Contr%", id: "contr_pct", width: 90, align: "center", editable: false,
			format: val => fmt_pct(val),
		},
		{
			name: "Cumu%", id: "cumu_pct", width: 90, align: "center", editable: false,
			format: (val, _r, _c, d) => {
				const color = d && d.hbt === "NS" ? "#9e9e9e" : (d && HBT[d.hbt]) ? HBT[d.hbt].bg : "#c0152a";
				return `<span style="font-weight:600;color:${color};">${fmt_pct(val)}</span>`;
			},
		},
		{
			name: "HBT", id: "hbt", width: 80, align: "center", editable: false,
			format: val => hbt_badge(val),
		},
		{
			name: "On Hand Stock", id: "on_hand_stock", width: 120, align: "center", editable: false,
			format: val => (val !== null && val !== undefined) ? fmt_num(val, 0) : dash(),
		},
		{
			name: "Frequency", id: "frequency", width: 100, align: "center", editable: false,
			format: val => (val !== null && val !== undefined) ? String(val) : dash(),
		},
		{
			name: "Sale Qty", id: "sale_qty", width: 120, align: "center", editable: false,
			format: val => `<span style="font-weight:600;">${fmt_num(val, 0)}</span>`,
		},
		{
			name: "Consumption", id: "consumption", width: 130, align: "center", editable: false,
			format: val => `<span style="font-weight:600;">${fmt_num(val, 0)}</span>`,
		},
		{
			name: "Total Value", id: "total", width: 120, align: "center", editable: false,
			format: val => `<span style="font-weight:600;">${fmt_num(val, 0)}</span>`,
		},
		{
			name: "ADU", id: "adu", width: 110, align: "center", editable: false,
			format: val => val !== null && val !== undefined ? fmt_num(val, 0) : dash(),
		},
		{
			name: "LT", id: "lt", width: 90, align: "center", editable: false,
			format: val => val !== null && val !== undefined ? fmt_num(val, 0) : dash(),
		},
		{
			name: "FOS", id: "fos", width: 110, align: "center", editable: false,
			format: val => (val !== null && val !== undefined) ? `${val}%` : dash(),
		},
		{
			name: "Calc TOG", id: "tog", width: 110, align: "center", editable: false,
			format: (val, _r, _c, d) =>
				`<span class="bot-calc-tog" data-idx="${d._idx}" style="font-weight:600;">${val != null ? val : "—"}</span>`,
		},
		{
			name: "Buffer Flag", id: "buffer_flag", width: 130, align: "center", editable: false,
			format: (val, _r, _c, d) => {
				const v = val || "Non-Buffer";
				return `<select class="bot-buffer-flag-select" data-idx="${d._idx}"
					style="border:1px solid #d1d8e0;border-radius:3px;padding:2px 4px;font-size:12px;
					width:100%;box-sizing:border-box;background:${v === "Buffer" ? "#e8f5e9" : "#fff8e1"};">
					<option value="Buffer"${v === "Buffer" ? " selected" : ""}>Buffer</option>
					<option value="Non-Buffer"${v !== "Buffer" ? " selected" : ""}>Non-Buffer</option>
				</select>`;
			},
		},
		{
			name: "New TOG", id: "new_tog", width: 110, align: "center", editable: false,
			format: (val, _r, _c, d) => {
				const is_buffer = (d.buffer_flag || "Non-Buffer") === "Buffer";
				if (!is_buffer) {
					return `<input type="number" class="bot-new-tog-input" data-idx="${d._idx}" min="0" step="1"
						value="" disabled
						style="border:1px solid #e0e0e0;border-radius:3px;padding:3px 6px;
						font-size:12px;width:100%;box-sizing:border-box;text-align:center;
						background:#f5f5f5;color:#aaa;font-weight:600;cursor:not-allowed;">`;
				}
				return `<input type="number" class="bot-new-tog-input" data-idx="${d._idx}" min="0" step="1"
					value="${val !== null && val !== undefined ? val : ""}"
					style="border:1px solid #d1d8e0;border-radius:3px;padding:3px 6px;
					font-size:12px;width:100%;box-sizing:border-box;text-align:center;
					background:#fff;color:${new_tog_color(val, d.tog)};font-weight:600;">`;
			},
		},
		{
			name: "Current TOG", id: "current_tog", width: 120, align: "center", editable: false,
			format: (val, _r, _c, d) => (d.buffer_flag || "Non-Buffer") !== "Buffer" ? dash() : (val ? `<span style="font-weight:600;">${fmt_num(val, 0)}</span>` : dash()),
		},
		{
			name: "Change%", id: "change_pct", width: 110, align: "center", editable: false,
			format: (val, _r, _c, d) => fmt_change_pct(val, d._idx),
		},
		{
			name: "No of Customers", id: "no_of_customer", width: 130, align: "center", editable: false,
			format: val => val != null ? `<span style="font-weight:600;">${val}</span>` : dash(),
		},
		{
			name: "Head Customer", id: "h", width: 150, align: "center", editable: false,
			format: val => num_badge(val, "H"),
		},
		{
			name: "Body Customer", id: "b", width: 150, align: "center", editable: false,
			format: val => num_badge(val, "B"),
		},
		{
			name: "Tail Customer", id: "t", width: 150, align: "center", editable: false,
			format: val => num_badge(val, "T"),
		},
	];

	// frappe-datatable caches each cell's rendered HTML in `cell.html` the first time
	// it's drawn and replays that cache verbatim (rather than re-invoking format())
	// whenever a row is recycled by virtual scroll — so edits made only to `_all_data`
	// are lost the moment a row scrolls out of view and back in. Recompute the cell's
	// HTML now and overwrite that cache so recycled rows pick up the live value.
	function sync_cell(idx, col_id) {
		if (!_dt) return;
		const col_idx = COLS.findIndex(c => c.id === col_id);
		if (col_idx < 0) return;
		const cell = _dt.getCell(col_idx, idx);
		if (!cell) return;
		const value = _all_data[idx][col_id];
		cell.content = value;
		cell.html = COLS[col_idx].format(value, null, null, _all_data[idx]);
	}

	function apply_row_colors(root_id = "bot-dt") {
		const tbody = document.querySelector(`#${root_id} .dt-body`);
		if (!tbody) return;
		tbody.querySelectorAll(".dt-row").forEach(tr => {
			const idx = parseInt(tr.getAttribute("data-row-index"));
			if (isNaN(idx)) return;
			const row = _all_data[idx];
			if (!row) return;
			const bg = HBT[row.hbt] ? HBT[row.hbt].light : "";
			tr.querySelectorAll(".dt-cell").forEach(td => {
				td.style.backgroundColor = bg;
			});
		});
	}

	function apply_hbt_header_colors(root_id = "bot-dt") {
		COLS.forEach((col, idx) => {
			const hbt_key = { h: "H", b: "B", t: "T" }[col.id];
			if (!hbt_key) return;
			const { bg, fg } = HBT[hbt_key];
			document.querySelectorAll(`#${root_id} .dt-row-header .dt-cell--col-${idx}`).forEach(cell => {
				cell.style.backgroundColor = bg;
				cell.querySelectorAll(".dt-cell__content, .content").forEach(el => {
					el.style.backgroundColor = bg;
					el.style.color = fg;
					el.style.fontWeight = "700";
				});
			});
		});
	}

	function apply_table_styles(root_id = "bot-dt") {
		apply_row_colors(root_id);
		apply_hbt_header_colors(root_id);
	}

	function setup_dt_observer(root_id = "bot-dt") {
		if (_dt_observer) { _dt_observer.disconnect(); _dt_observer = null; }
		let _obs_timer = null;
		const dt_el = document.getElementById(root_id);
		if (!dt_el) return;
		_dt_observer = new MutationObserver(() => {
			clearTimeout(_obs_timer);
			_obs_timer = setTimeout(() => {
				apply_table_styles(root_id);
				document.getElementById(root_id).querySelectorAll(".bot-row-check").forEach(cb => {
					cb.checked = _selected.has(parseInt(cb.dataset.idx));
				});
			}, 30);
		});
		_dt_observer.observe(dt_el, { childList: true, subtree: true });
	}

	function _get_selected_rows() {
		return _all_data.filter((_, i) => _selected.has(i));
	}

	function save_selected() {
		const selected = _get_selected_rows();
		if (!selected.length) {
			frappe.show_alert({ message: __("No rows selected."), indicator: "orange" });
			return;
		}
		const items = selected
			.filter(r => r.new_tog != null)
			.map(r => ({ item_code: r.item_code, tog: r.new_tog }));
		if (!items.length) {
			frappe.show_alert({ message: __("No MTA items selected. Only BOTA items can be saved."), indicator: "orange" });
			return;
		}
		frappe.call({
			method: "prakash_steel.prakash_steel.page.bo_tog.bo_tog.save_tog",
			args: { items: JSON.stringify(items), fos: get_global_fos() },
			freeze: true,
			freeze_message: __("Saving TOG values…"),
			callback(r) {
				if (r.message && r.message.last_fos != null) _last_fos = r.message.last_fos;
				if (r.message) {
					frappe.show_alert({
						message: __(`${r.message.saved} item(s) saved successfully.`),
						indicator: "green",
					});
				}
			},
		});
	}
	function update_tog_selected() {
		const selected = _get_selected_rows();
		if (!selected.length) {
			frappe.show_alert({ message: __("No rows selected."), indicator: "orange" });
			return;
		}
		const items = selected
			.filter(r => r.new_tog != null || (r.buffer_flag || "Non-Buffer") === "Non-Buffer")
			.map(r => ({ item_code: r.item_code, tog: r.new_tog ?? 0, buffer_flag: r.buffer_flag || "Non-Buffer", sku_type: r.sku_type || "" }));
		if (!items.length) {
			frappe.show_alert({ message: __("No MTA items selected. Only BOTA items can be updated."), indicator: "orange" });
			return;
		}
		frappe.call({
			method: "prakash_steel.prakash_steel.page.bo_tog.bo_tog.update_tog",
			args: { items: JSON.stringify(items), fos: get_global_fos() },
			freeze: true,
			freeze_message: __("Updating TOG…"),
			callback(r) {
				if (r.message && r.message.last_fos != null) _last_fos = r.message.last_fos;
				if (r.message) {
					frappe.show_alert({
						message: __(`${r.message.updated} item(s) updated successfully.`),
						indicator: "green",
					});
				}
			},
		});
	}
	function reset_selected() {
		_active_fos = _last_fos;
		fos_field.set_value(_last_fos);
		apply_global_fos();

		_all_data.forEach((row, idx) => {
			if ((row.buffer_flag || "Non-Buffer") === "Buffer") {
				row.new_tog = row.tog;
				sync_cell(idx, "new_tog");
			}
		});
		document.querySelectorAll(".bot-new-tog-input").forEach(input => {
			const idx = parseInt(input.dataset.idx);
			const row = _all_data[idx];
			if (!row || (row.buffer_flag || "Non-Buffer") !== "Buffer") return;
			input.value = row.tog != null ? row.tog : "";
			$(input).css({ color: "inherit", "font-weight": "600" });
		});

		const items = _all_data
			.filter(r => (r.buffer_flag || "Non-Buffer") === "Buffer" && r.new_tog != null)
			.map(r => ({ item_code: r.item_code, tog: r.new_tog }));

		frappe.call({
			method: "prakash_steel.prakash_steel.page.bo_tog.bo_tog.save_tog",
			args: { items: JSON.stringify(items), fos: _last_fos },
			freeze: true,
			freeze_message: __("Resetting…"),
			callback(r) {
				if (r.message && r.message.last_fos != null) _last_fos = r.message.last_fos;
				frappe.show_alert({
					message: __(`New TOG reset to Calc TOG and FOS reset to ${_active_fos}% — saved${r.message ? ` for ${r.message.saved} item(s)` : ""}.`),
					indicator: "blue",
				});
			},
		});
	}

	function bind_events() {
		$(document).off("click", ".bot-item-link").on("click", ".bot-item-link", function () {
			const item = $(this).data("item");
			if (item) window.open(`/app/item/${encodeURIComponent(item)}`, "_blank");
		});

		$(document).off("input", ".bot-new-tog-input").on("input", ".bot-new-tog-input", function () {
			const idx = parseInt($(this).data("idx"));
			const val = $(this).val();
			_all_data[idx].new_tog = val === "" ? null : parseInt(val);
			$(this).css({"color": new_tog_color(val, _all_data[idx].tog), "font-weight": "600"});
			sync_cell(idx, "new_tog");
		});

		$(document).off("change", ".bot-buffer-flag-select").on("change", ".bot-buffer-flag-select", function () {
			const idx = parseInt($(this).data("idx"));
			const val = $(this).val();
			_all_data[idx].buffer_flag = val;
			$(this).css("background", val === "Buffer" ? "#e8f5e9" : "#fff8e1");
			const old_sku = _all_data[idx].sku_type || "";
			const new_sku = val === "Non-Buffer" ? old_sku.replace(/A$/, "O") : old_sku.replace(/O$/, "A");
			_all_data[idx].sku_type = new_sku;
			$(`.bot-sku-type[data-idx="${idx}"]`).text(new_sku || "—");
			if (val === "Buffer") { _selected.add(idx); $(`.bot-row-check[data-idx="${idx}"]`).prop("checked", true); }
			const raw_row = _raw_data.find(r => r.item_code === _all_data[idx].item_code);
			if (raw_row) { raw_row.buffer_flag = val; raw_row.sku_type = new_sku; }
			const $nt = $(`.bot-new-tog-input[data-idx="${idx}"]`);
			if (val === "Non-Buffer") {
				_all_data[idx].new_tog = null;
				$nt.val("").prop("disabled", true).css({ background: "#f5f5f5", color: "#aaa", cursor: "not-allowed" });
			} else {
				$nt.prop("disabled", false).css({ background: "#fff", cursor: "" });
				const stored = _all_data[idx].new_tog;
				$nt.val(stored != null ? stored : "").css("color", new_tog_color(stored, _all_data[idx].tog));
			}
			sync_cell(idx, "buffer_flag");
			sync_cell(idx, "sku_type");
			sync_cell(idx, "new_tog");
			sync_cell(idx, "current_tog");
			update_selected_count();
		});

		$(document).off("change", "#bot-select-all").on("change", "#bot-select-all", function () {
			if (this.checked) {
				_all_data.forEach((_, i) => _selected.add(i));
			} else {
				_selected.clear();
			}
			$(".bot-row-check").prop("checked", this.checked);
			update_selected_count();
		});

		$(document).off("change", ".bot-row-check").on("change", ".bot-row-check", function () {
			const idx = parseInt($(this).data("idx"));
			if (this.checked) _selected.add(idx);
			else _selected.delete(idx);
			update_selected_count();
			const total = _all_data.length;
			$("#bot-select-all")
				.prop("indeterminate", _selected.size > 0 && _selected.size < total)
				.prop("checked", _selected.size === total);
		});
	}

	function build_datatable(data, period_label) {
		_raw_data = data;
		const _gfos = get_global_fos();
		_all_data = data.map((row, idx) => {
			const fos = _gfos;
			const tog = ceil1000((row.adu || 0) * (row.lt || 0) * (1 + fos / 100));
			const current_tog = row.current_tog || 0;
			const change_pct = current_tog ? Math.round((tog - current_tog) / current_tog * 1000) / 10 : null;
			return { ...row, _idx: idx, fos, tog, change_pct, new_tog: row.new_tog ?? ((row.buffer_flag || "Non-Buffer") === "Buffer" ? tog : null) };
		});

		_selected.clear();

		_all_data.forEach((row, i) => { if (row.sku_type === "BOTA") _selected.add(i); });
		if (_dt_observer) { _dt_observer.disconnect(); _dt_observer = null; }
		if (_dt) { try { _dt.destroy(); } catch (_) {} _dt = null; }

		$("#bot-root").html(`
			<div style="font-size:12px;color:#888;margin-bottom:4px;padding-left:2px;">
				Period: <strong>${esc(period_label)}</strong>
				&nbsp;·&nbsp; ${data.length} items
			</div>
			<div id="bot-selected-count" style="font-size:12px;color:#1565c0;font-weight:600;margin-bottom:10px;padding-left:2px;"></div>
			<div style="padding:4px 2px 8px;display:flex;align-items:center;gap:8px;">
				<label style="font-size:12px;color:#555;cursor:pointer;display:flex;align-items:center;gap:6px;">
					<input type="checkbox" id="bot-select-all">
					<span>Select All</span>
				</label>
			</div>
			<div id="bot-dt" style="overflow-x:auto;"></div>
		`);

		update_selected_count();

		_dt = new DataTable(document.getElementById("bot-dt"), {
			columns: COLS,
			data: _all_data,
			serialNoColumn: false,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: false,
			noDataMessage: __("No items found for the configured TOG period."),
			layout: "fixed",
		});

		setup_dt_observer("bot-dt");
		apply_table_styles("bot-dt");
		bind_events();
	}

	// ── Export ───────────────────────────────────────────────────────────────
	function export_to_xlsx() {
		if (!_all_data || !_all_data.length) {
			frappe.msgprint(__("No data to export."));
			return;
		}
		const form = document.createElement("form");
		form.method = "POST";
		form.action = "/api/method/prakash_steel.prakash_steel.page.bo_tog.bo_tog.export_bo_tog_xlsx";
		form.style.display = "none";

		const add_field = (name, value) => {
			const input = document.createElement("input");
			input.type = "hidden";
			input.name = name;
			input.value = value;
			form.appendChild(input);
		};

		add_field("data", JSON.stringify(_all_data));
		add_field("filename", "BO_TOG");
		add_field("csrf_token", frappe.csrf_token);

		document.body.appendChild(form);
		form.submit();
		document.body.removeChild(form);
	}

	// ── Load ──────────────────────────────────────────────────────────────────
	function load_data() {
		$("#bot-root").html(`
			<div style="padding:24px;text-align:center;color:#888;">
				<div class="spinner" style="display:inline-block;width:20px;height:20px;
					border:3px solid #ddd;border-top-color:#1a7a3f;border-radius:50%;
					animation:bot-spin 0.8s linear infinite;"></div>
				<span style="margin-left:10px;">Loading…</span>
			</div>
			<style>@keyframes bot-spin { to { transform: rotate(360deg); } }</style>
		`);

		const view_by = view_by_field.get_value() || "Sale Quantity";

		frappe.call({
			method: "prakash_steel.prakash_steel.page.bo_tog.bo_tog.get_bo_tog_data",
			args: { view_by },
			callback(r) {
				if (!r.message) return;
				const { data, period_label, default_fos, last_fos } = r.message;
				_last_fos = last_fos ?? 30;
				_active_fos = default_fos ?? 30;
				fos_field.set_value(_active_fos);
				if (!data || !data.length) {
					$("#bot-root").html(`
						<div style="padding:32px;text-align:center;color:#888;">
							No items found for the configured TOG period.
						</div>`);
					return;
				}
				build_datatable(data, period_label || "");
			},
		});
	}

	load_data();
};
