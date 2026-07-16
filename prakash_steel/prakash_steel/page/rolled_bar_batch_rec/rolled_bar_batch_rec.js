frappe.pages['rolled-bar-batch-rec'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Rolled Bar Batch Recommendation',
		single_column: true
	});

	const item_code_field = page.add_field({
		fieldname: "item_code",
		label: __("Item Code"),
		fieldtype: "Link",
		options: "Item",
		get_query: () => ({ filters: { custom_item_type: ["in", ["RB", "BO", "Traded"]], disabled: 0 } }),
		change() { load_data(); },
	});

	const item_type_field = page.add_field({
		fieldname: "item_type",
		label: __("Item Type"),
		fieldtype: "Select",
		options: ["", "RB", "BO", "Traded"],
		default: "",
		change() { load_data(); },
	});

	const sku_type_field = page.add_field({
		fieldname: "sku_type",
		label: __("SKU Type"),
		fieldtype: "Select",
		options: ["", "RBMTA", "RBMTO", "BOTA", "BOTO", "TRMTA", "TRMTO"],
		default: "",
		change() { load_data(); },
	});

	page.add_inner_button(__("Refresh"), () => load_data());

	$(`<div id="rbbr-root" style="padding:16px 4px 40px;"></div>`).appendTo(page.main);

	$(`<style>
		#rbbr-dt .dt-row-header .dt-cell__content,
		#rbbr-dt .dt-row-header .content { text-align: left !important; }
	</style>`).appendTo(document.head);

	// ── Item Type colour palette ────────────────────────────────────────────
	const ITEM_TYPE = {
		RB: { bg: "#1a7a3f", fg: "#ffffff", light: "#e8f5ee" },
		BO: { bg: "#d4a000", fg: "#ffffff", light: "#fdf7e3" },
		Traded: { bg: "#1a73e8", fg: "#ffffff", light: "#e8f0fe" },
	};

	function esc(v) { return frappe.utils.escape_html(String(v ?? "")); }
	function dash() { return '<span style="color:#ccc;">—</span>'; }

	function fmt_num(v) {
		if (v === null || v === undefined || v === "") return dash();
		const n = parseFloat(v);
		if (isNaN(n)) return dash();
		return Math.ceil(n).toLocaleString();
	}

	function item_type_badge(val) {
		if (!val || !ITEM_TYPE[val]) return dash();
		const c = ITEM_TYPE[val];
		return `<span style="display:inline-block;padding:2px 10px;border-radius:4px;
			background:${c.bg};color:${c.fg};font-weight:700;font-size:12px;
			letter-spacing:.5px;">${esc(val)}</span>`;
	}

	function sku_type_badge(val) {
		if (!val) return dash();
		return `<span style="display:inline-block;padding:1px 8px;border-radius:3px;
			background:#eef1f5;color:#555;font-weight:600;font-size:11px;
			letter-spacing:.3px;">${esc(val)}</span>`;
	}

	function batch_size_badge(val, _r, _c, d) {
		const idx = d ? d._idx : "";
		if (val === null || val === undefined || val === "") {
			return `<span class="rbbr-batch-size" data-idx="${idx}" style="color:#ccc;">—</span>`;
		}
		return `<span class="rbbr-batch-size" data-idx="${idx}" style="display:inline-block;padding:2px 10px;
			border-radius:4px;background:#fff3e0;color:#c0700a;font-weight:700;font-size:13px;">${fmt_num(val)}</span>`;
	}

	function projected_qty_badge(val) {
		if (val === null || val === undefined || val === "") return dash();
		return `<span style="display:inline-block;padding:1px 8px;border-radius:3px;
			background:#e8f0fe;color:#1a73e8;font-weight:600;font-size:12px;">${fmt_num(val)}</span>`;
	}

	function prod_badge(val) {
		if (val === null || val === undefined || val === "") return dash();
		return `<span style="display:inline-block;padding:1px 8px;border-radius:3px;
			background:#f3f0fb;color:#6b3fa0;font-weight:600;font-size:12px;">${fmt_num(val)}</span>`;
	}

	function item_link(val) {
		if (!val) return dash();
		return `<span class="rbbr-item-link" data-item="${esc(val)}"
			style="color:#1a73e8;font-weight:500;cursor:pointer;">${esc(val)}</span>`;
	}

	function no_of_setup_input(val, _r, _c, d) {
		return `<input type="number" class="rbbr-no-of-setup-input" data-idx="${d._idx}" min="0" step="1"
			value="${val !== null && val !== undefined ? val : ""}"
			style="border:1px solid #d1d8e0;border-radius:3px;padding:3px 6px;
			font-size:12px;width:100%;box-sizing:border-box;text-align:center;background:#fffbe6;">`;
	}

	// ── Column builders keyed by fieldname ──────────────────────────────────
	const FORMATTERS = {
		item_code: item_link,
		item_name: val => val ? esc(val) : dash(),
		item_type: item_type_badge,
		sku_type: sku_type_badge,
		sales_qty: fmt_num,
		consumption_qty: fmt_num,
		total: val => `<span style="font-weight:600;">${fmt_num(val)}</span>`,
		projected_qty: projected_qty_badge,
		batch_size: batch_size_badge,
		production_count: fmt_num,
		no_of_setup: no_of_setup_input,
		production_qty: fmt_num,
	};

	function build_columns(backend_columns) {
		return backend_columns.map(col => {
			const formatter = FORMATTERS[col.fieldname]
				|| (col.fieldname.startsWith("prod_") ? prod_badge : fmt_num);
			return {
				name: col.label,
				id: col.fieldname,
				width: col.width || 120,
				align: "center",
				editable: false,
				format: formatter,
			};
		});
	}

	function apply_row_colors(root_id = "rbbr-dt", all_data) {
		const tbody = document.querySelector(`#${root_id} .dt-body`);
		if (!tbody) return;
		tbody.querySelectorAll(".dt-row").forEach(tr => {
			const idx = parseInt(tr.getAttribute("data-row-index"));
			if (isNaN(idx)) return;
			const row = all_data[idx];
			if (!row) return;
			const bg = ITEM_TYPE[row.item_type] ? ITEM_TYPE[row.item_type].light : "";
			tr.querySelectorAll(".dt-cell").forEach(td => {
				td.style.backgroundColor = bg;
			});
		});
	}

	function setup_dt_observer(root_id, all_data) {
		let observer = null;
		let obs_timer = null;
		const dt_el = document.getElementById(root_id);
		if (!dt_el) return null;
		observer = new MutationObserver(() => {
			clearTimeout(obs_timer);
			obs_timer = setTimeout(() => apply_row_colors(root_id, all_data), 30);
		});
		observer.observe(dt_el, { childList: true, subtree: true });
		return observer;
	}

	let _dt = null;
	let _dt_observer = null;
	let _all_data = [];

	function recalc_batch_size(idx) {
		const row = _all_data[idx];
		if (!row) return;
		const no_of_setup = row.no_of_setup;
		const production_qty = row.production_qty || 0;
		const batch_size = (no_of_setup && no_of_setup > 0) ? Math.ceil(production_qty / no_of_setup) : 0;
		row.batch_size = batch_size;
		const html = batch_size_badge(batch_size, null, null, { _idx: idx });
		const $el = $(`.rbbr-batch-size[data-idx="${idx}"]`);
		if ($el.length) $el.replaceWith(html);
	}

	function bind_events() {
		$(document).off("click", ".rbbr-item-link").on("click", ".rbbr-item-link", function () {
			const item = $(this).data("item");
			if (item) window.open(`/app/item/${encodeURIComponent(item)}`, "_blank");
		});

		$(document).off("input", ".rbbr-no-of-setup-input").on("input", ".rbbr-no-of-setup-input", function () {
			const idx = parseInt($(this).data("idx"));
			const raw = $(this).val();
			let num = raw === "" ? null : parseInt(raw, 10);
			if (num !== null && (isNaN(num) || num < 0)) {
				num = 0;
				$(this).val(0);
			}
			if (_all_data[idx]) {
				_all_data[idx].no_of_setup = num;
				recalc_batch_size(idx);
			}
		});
	}

	function build_datatable(backend_columns, data, period_label, fos) {
		if (_dt_observer) { _dt_observer.disconnect(); _dt_observer = null; }
		if (_dt) { try { _dt.destroy(); } catch (_) {} _dt = null; }

		const fos_pct = (parseFloat(fos || 0) * 100).toFixed(0);

		$("#rbbr-root").html(`
			<div style="font-size:12px;color:#888;margin-bottom:10px;padding-left:2px;">
				Period: <strong>${esc(period_label)}</strong>
				&nbsp;·&nbsp; ${data.length} items
				&nbsp;·&nbsp; FOS: <strong style="color:#c0700a;">${fos_pct}%</strong>
			</div>
			<div id="rbbr-dt" style="overflow-x:auto;"></div>
		`);

		const columns = build_columns(backend_columns);
		_all_data = data.map((row, idx) => ({ ...row, _idx: idx }));

		_dt = new DataTable(document.getElementById("rbbr-dt"), {
			columns,
			data: _all_data,
			serialNoColumn: true,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: false,
			noDataMessage: __("No items found."),
			layout: "fixed",
		});

		_dt_observer = setup_dt_observer("rbbr-dt", _all_data);
		apply_row_colors("rbbr-dt", _all_data);
		bind_events();
	}

	function load_data() {
		$("#rbbr-root").html(`
			<div style="padding:24px;text-align:center;color:#888;">
				<div class="spinner" style="display:inline-block;width:20px;height:20px;
					border:3px solid #ddd;border-top-color:#1a7a3f;border-radius:50%;
					animation:rbbr-spin 0.8s linear infinite;"></div>
				<span style="margin-left:10px;">Loading…</span>
			</div>
			<style>@keyframes rbbr-spin { to { transform: rotate(360deg); } }</style>
		`);

		frappe.call({
			method: "prakash_steel.prakash_steel.page.rolled_bar_batch_rec.rolled_bar_batch_rec.get_rolled_bar_batch_rec_data",
			args: {
				item_code: item_code_field.get_value(),
				item_type: item_type_field.get_value(),
				sku_type: sku_type_field.get_value(),
			},
			callback(r) {
				if (!r.message) return;
				const { columns, data, period_label, fos } = r.message;
				if (!data || !data.length) {
					$("#rbbr-root").html(`
						<div style="padding:32px;text-align:center;color:#888;">
							No items found for the configured period.
						</div>`);
					return;
				}
				build_datatable(columns, data, period_label || "", fos);
			},
		});
	}

	load_data();
}
