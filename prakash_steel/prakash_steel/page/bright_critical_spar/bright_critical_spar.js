frappe.pages['bright-critical-spar'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Bright Critical Spares',
		single_column: true
	});

	page.add_inner_button(__("Refresh"), () => load_data());
	page.add_inner_button(__("Execute"), () => {
		const selected = _get_selected_rows();
		if (!selected.length) {
			frappe.show_alert({ message: __("No rows selected."), indicator: "orange" });
			return;
		}
		const valid = selected.filter(r => flt(r.net_order_recommendation) > 0);
		if (!valid.length) {
			frappe.show_alert({ message: __("Selected rows have no order recommendation."), indicator: "orange" });
			return;
		}
		frappe.confirm(
			__(`Create Material Requests for <b>${valid.length}</b> item(s)?`),
			() => {
				frappe.call({
					method: "prakash_steel.prakash_steel.page.bright_critical_spar.bright_critical_spar.execute_material_requests",
					args: { rows: valid },
					freeze: true,
					freeze_message: __("Creating Material Requests…"),
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
								message: __(`${created.length} Material Request(s) created. Refreshing data…`),
								indicator: "green",
							});
							load_data();
						}
					},
				});
			}
		);
	});

	const $root = $(`<div id="bright-critical-spar-root" style="padding:16px 4px 40px;"></div>`).appendTo(page.main);

	// ── State ─────────────────────────────────────────────────────────────────
	let _all_data = [];
	let _selected = new Set();

	function flt(v) { return parseFloat(v) || 0; }

	function esc(v) { return frappe.utils.escape_html(String(v ?? "")); }

	function on_hand_colour_badge(value) {
		if (!value) return "";
		let colour = value;
		let bg = "#FFFFFF";
		let textColor = "#000000";

		if (colour === "BLACK") {
			bg = "#000000";
			textColor = "#FFFFFF";
		} else if (colour === "RED") {
			bg = "#FF0000";
			textColor = "#FFFFFF";
		} else if (colour === "YELLOW") {
			bg = "#FFFF00";
			textColor = "#000000";
		} else if (colour === "GREEN") {
			bg = "#00FF00";
			textColor = "#000000";
		} else if (colour === "WHITE") {
			bg = "#FFFFFF";
			textColor = "#000000";
		}

		return `<span style="
			background-color:${bg};
			color:${textColor};
			padding: 2px 10px;
			border-radius: 4px;
			font-weight: bold;
			display: inline-block;
		">${esc(colour)}</span>`;
	}

	function item_code_link(value) {
		if (!value) return "";
		return `<a href="/app/item/${encodeURIComponent(value)}" target="_blank">${esc(value)}</a>`;
	}

	let dt = null;
	let dt_observer = null;

	function _get_selected_rows() {
		return _all_data.filter((_, i) => _selected.has(i));
	}

	function build_columns(backend_columns) {
		const select_col = {
			name: "",
			id: "_select",
			width: 60,
			editable: false,
			resizable: false,
			sortable: false,
			align: "center",
			format: (_val, _row, _col, d) =>
				`<input type="checkbox" class="cs-row-check" data-idx="${d._idx}" ${_selected.has(d._idx) ? "checked" : ""}>`,
		};

		const index_col = {
			name: "",
			id: "_index",
			width: 50,
			editable: false,
			resizable: false,
			sortable: false,
			align: "center",
			format: (_val, _row, _col, d) => d._idx + 1,
		};

		return [
			select_col,
			index_col,
			...backend_columns.map((col) => {
				let format;
				if (col.fieldname === "on_hand_colour") {
					format = (value) => on_hand_colour_badge(value);
				} else if (col.fieldname === "item_code") {
					format = (value) => item_code_link(value);
				} else {
					format = (value) => esc(value ?? "");
				}
				return {
					name: col.label,
					id: col.fieldname,
					width: col.width || 120,
					editable: false,
					format,
				};
			}),
		];
	}

	function bind_events() {
		$(document).off("change", "#cs-select-all").on("change", "#cs-select-all", function () {
			if (this.checked) {
				_all_data.forEach((_, i) => _selected.add(i));
			} else {
				_selected.clear();
			}
			$(".cs-row-check").prop("checked", this.checked);
		});

		$(document).off("change", ".cs-row-check").on("change", ".cs-row-check", function () {
			const idx = parseInt($(this).data("idx"));
			if (this.checked) {
				_selected.add(idx);
			} else {
				_selected.delete(idx);
			}
			const total = _all_data.length;
			$("#cs-select-all").prop("indeterminate", _selected.size > 0 && _selected.size < total);
			$("#cs-select-all").prop("checked", _selected.size === total);
		});
	}

	function load_data() {
		$root.html(`<div style="padding:24px;text-align:center;color:#888;">${__("Loading...")}</div>`);

		frappe.call({
			method: "prakash_steel.prakash_steel.page.bright_critical_spar.bright_critical_spar.get_bright_critical_spar_data",
			callback(r) {
				if (!r.message) return;
				const { columns, data } = r.message;

				if (dt_observer) { dt_observer.disconnect(); dt_observer = null; }
				if (dt) { try { dt.destroy(); } catch (e) {} dt = null; }
				$root.empty();

				_all_data = (data || []).map((row, idx) => ({ ...row, _idx: idx }));
				_selected.clear();

				if (!_all_data.length) {
					$root.html(`<div style="padding:32px;text-align:center;color:#888;">${__("No data found.")}</div>`);
					return;
				}

				$(`<label style="font-size:12px;color:#555;cursor:pointer;
					display:inline-flex;align-items:center;gap:6px;padding:6px 4px 8px;">
					<input type="checkbox" id="cs-select-all">
					<span>${__("Select all")}</span>
				</label>`).appendTo($root);

				const $dt_el = $(`<div></div>`).appendTo($root);
				dt = new frappe.DataTable($dt_el[0], {
					columns: build_columns(columns),
					data: _all_data,
					layout: "fixed",
					serialNoColumn: false,
					checkboxColumn: false,
					inlineFilters: true,
					noDataMessage: __("No Data"),
				});

				let _obs_timer = null;
				dt_observer = new MutationObserver(() => {
					clearTimeout(_obs_timer);
					_obs_timer = setTimeout(() => {
						$dt_el[0].querySelectorAll(".cs-row-check").forEach(cb => {
							cb.checked = _selected.has(parseInt(cb.dataset.idx));
						});
					}, 30);
				});
				dt_observer.observe($dt_el[0], { childList: true, subtree: true });

				bind_events();
			},
		});
	}

	load_data();
};
