// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.pages["psp-amc"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("AMC"),
		single_column: true,
	});

	inject_styles();
	new PSPAmc(page);
};

const METHOD = "prakash_steel.prakash_steel.page.psp_amc.psp_amc";

class PSPAmc {
	constructor(page) {
		this.page = page;
		this.selected = null;
		this.active_tab = "report";
		this.render_shell();
		this.load_list();
	}

	render_shell() {
		this.body = $(`
			<div class="psp-amc">
				<div class="psp-amc-list">
					<div class="psp-amc-list-head">
						<input type="text" class="form-control input-sm psp-amc-search"
							placeholder="${__("Search AMC / item / supplier")}">
					</div>
					<div class="psp-amc-list-body"></div>
				</div>
				<div class="psp-amc-detail">
					<div class="psp-amc-empty text-muted">${__("Select an AMC from the list")}</div>
					<div class="psp-amc-content" hidden></div>
				</div>
			</div>
		`).appendTo(this.page.main);

		this.$list = this.body.find(".psp-amc-list-body");
		this.$empty = this.body.find(".psp-amc-empty");
		this.$content = this.body.find(".psp-amc-content");

		this.body.find(".psp-amc-search").on("input", (e) => {
			this.filter = (e.target.value || "").toLowerCase().trim();
			this.render_list();
		});
	}

	load_list() {
		this.$list.html(`<div class="psp-amc-loading text-muted">${__("Loading…")}</div>`);
		frappe.call({ method: `${METHOD}.get_amc_list` }).then((r) => {
			this.rows = r.message || [];
			this.render_list();
		});
	}

	render_list() {
		const rows = (this.rows || []).filter((row) => {
			if (!this.filter) return true;
			return [row.name, row.item, row.supplier]
				.filter(Boolean)
				.some((v) => v.toLowerCase().includes(this.filter));
		});

		if (!rows.length) {
			this.$list.html(`<div class="psp-amc-loading text-muted">${__("No AMCs")}</div>`);
			return;
		}

		this.$list.empty();
		rows.forEach((row) => {
			const remaining = cint(row.services_remaining);
			const indicator = remaining <= 0 ? "red" : remaining <= 1 ? "orange" : "green";
			const $row = $(`
				<div class="psp-amc-list-row accent-${indicator} ${row.name === this.selected ? "active" : ""}" data-amc="${frappe.utils.escape_html(row.name)}">
					<div class="psp-amc-list-row-title">
						<span>${frappe.utils.escape_html(row.name)}</span>
						<span class="indicator-pill ${indicator}">${remaining}/${cint(row.total_services_available)}</span>
					</div>
					<div class="psp-amc-list-row-sub text-muted">
						${frappe.utils.escape_html(row.item || "—")}<br>
						${frappe.utils.escape_html(row.supplier || "—")}
					</div>
					<div class="psp-amc-list-row-next text-muted">
						${row.next_service_date
							? __("Next: {0}", [frappe.datetime.str_to_user(row.next_service_date)])
							: __("No upcoming service")}
					</div>
				</div>
			`);
			$row.on("click", () => this.select(row.name));
			this.$list.append($row);
		});
	}

	select(amc) {
		this.selected = amc;
		this.body.find(".psp-amc-list-row").removeClass("active");
		this.body
			.find(`.psp-amc-list-row[data-amc="${CSS.escape(amc)}"]`)
			.addClass("active");

		this.$empty.attr("hidden", true);
		this.$content.removeAttr("hidden").html(
			`<div class="psp-amc-loading text-muted">${__("Loading…")}</div>`
		);

		frappe.call({ method: `${METHOD}.get_amc_details`, args: { amc } }).then((r) => {
			if (this.selected !== amc) return; // stale response
			this.details = r.message;
			this.render_detail();
		});
	}

	render_detail() {
		const { header, history, report_lines, upcoming } = this.details;
		const upcoming_count = upcoming.next ? 1 + upcoming.later.length : 0;

		const tabs = [
			{
				key: "report",
				label: __("Report View"),
				count: report_lines.length,
				html: this.render_report_lines(report_lines),
			},
			{
				key: "history",
				label: __("Completed"),
				count: history.length,
				html: this.render_history(history),
			},
			{
				key: "upcoming",
				label: __("Upcoming"),
				count: upcoming_count,
				html: this.render_upcoming(upcoming, header),
			},
		];
		if (!tabs.some((t) => t.key === this.active_tab)) this.active_tab = "report";

		this.$content.html(`
			${this.render_header(header)}
			<div class="psp-amc-tabs">
				${tabs
					.map(
						(t) => `
					<button class="psp-amc-tab ${t.key === this.active_tab ? "active" : ""}" data-tab="${t.key}">
						${t.label} <span class="count">${t.count}</span>
					</button>`
					)
					.join("")}
			</div>
			${tabs
				.map(
					(t) => `
				<div class="psp-amc-tab-body" data-pane="${t.key}" ${t.key === this.active_tab ? "" : "hidden"}>
					${t.html}
				</div>`
				)
				.join("")}
		`);

		this.$content.find(".psp-amc-tab").on("click", (e) => {
			this.active_tab = $(e.currentTarget).data("tab");
			this.$content.find(".psp-amc-tab").removeClass("active");
			$(e.currentTarget).addClass("active");
			this.$content.find("[data-pane]").each((_, el) => {
				$(el).attr("hidden", $(el).data("pane") !== this.active_tab ? true : null);
			});
		});

		this.$content.find("[data-open-visit]").on("click", (e) => {
			const name = $(e.currentTarget).data("open-visit");
			if (name) frappe.set_route("Form", "AMC Service Visit", name);
		});
	}

	render_header(h) {
		const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));
		const d = (v) => (v ? frappe.datetime.str_to_user(v) : "—");
		const money = (v) => format_currency(v || 0);
		const txt = (v) => (v == null || v === "" ? "—" : esc(v));

		const field = (label, value) => `
			<div class="psp-amc-field">
				<div class="psp-amc-field-label">${label}</div>
				<div class="psp-amc-field-value">${value == null || value === "" ? "—" : value}</div>
			</div>`;

		const remaining = cint(h.services_remaining);
		const rem_ind = remaining <= 0 ? "red" : remaining <= 1 ? "orange" : "green";

		return `
			<div class="psp-amc-header">
				<div class="psp-amc-header-top">
					<h4>
						<a href="/app/amc/${encodeURIComponent(h.name)}" target="_blank">${esc(h.name)}</a>
					</h4>
					<div class="psp-amc-counts">
						<span class="psp-amc-count"><b>${cint(h.total_services_available)}</b><small>${__("Total")}</small></span>
						<span class="psp-amc-count"><b>${cint(h.services_availed)}</b><small>${__("Availed")}</small></span>
						<span class="psp-amc-count ${rem_ind}"><b>${remaining}</b><small>${__("Remaining")}</small></span>
					</div>
				</div>
				<div class="psp-amc-fields">
					${field(__("Posting Date"), d(h.posting_date))}
					${field(__("Item Name"), txt(h.item))}
					${field(__("Item Value"), money(h.asset_value))}
					${field(__("Make / Model"), txt(h.make_model))}
					${field(__("Serial No."), txt(h.serial_no))}
					${field(__("Installation Date"), d(h.installation_date))}
					${field(__("Location on Site"), txt(h.location))}
					${field(__("Supplier Name"), txt(h.supplier))}
					${field(__("AMC Applicable"), txt(h.amc_applicable))}
					${field(__("AMC Provided Company Name"), txt(h.amc_provider))}
					${field(__("AMC Charges Amount"), money(h.amc_charges))}
					${field(__("AMC Start Date"), d(h.amc_start_date))}
					${field(__("AMC End Date"), d(h.amc_end_date))}
					${field(__("Contract Period"), txt(h.contract_period))}
					${field(__("Services Provided to us in this Period"), cint(h.services_availed))}
					${field(__("Services available in our hand in this Period"), cint(h.services_remaining))}
					${field(__("Last Service Date"), d(h.last_service_date))}
					${field(__("Next Service Date"), this.render_next_badge(h.next_service_date))}
				</div>
			</div>`;
	}

	render_report_lines(lines) {
		if (!lines.length) {
			return `<div class="psp-amc-none text-muted">${__("No completed service visits yet")}</div>`;
		}

		const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));
		const d = (v) => (v ? frappe.datetime.str_to_user(v) : "");
		const money = (v) => (v == null ? "" : format_currency(v));
		const num = (v) => (v == null ? "" : cint(v));

		const rows = lines
			.map(
				(l) => `
			<tr data-open-visit="${esc(l.visit)}">
				<td class="nowrap">${d(l.service_date)}</td>
				<td>${esc(l.part_change)}</td>
				<td>${esc(l.part_description)}</td>
				<td>${esc(l.part_no)}</td>
				<td class="text-right">${money(l.part_cost)}</td>
				<td class="text-right">${money(l.extra_charges)}</td>
				<td class="text-right">${num(l.qty)}</td>
				<td>${esc(l.overall_equipment_condition)}</td>
			</tr>`
			)
			.join("");

		return `
			<div class="psp-amc-report-scroll">
				<table class="table table-bordered psp-amc-report-table">
					<thead><tr>
						<th class="nowrap">${__("Service Date")}</th>
						<th>${__("Part Change Yes/No")}</th>
						<th>${__("Part / Item Description")}</th>
						<th>${__("Part No.")}</th>
						<th class="text-right">${__("Part Cost")}</th>
						<th class="text-right">${__("Extra Charges")}</th>
						<th class="text-right">${__("Qty")}</th>
						<th>${__("Overall Equipment Condition")}</th>
					</tr></thead>
					<tbody>${rows}</tbody>
				</table>
			</div>`;
	}

	render_next_badge(date) {
		if (!date) return __("None");
		const days = frappe.datetime.get_day_diff(date, frappe.datetime.now_date());
		let cls = "green";
		let note = __("in {0}d", [days]);
		if (days < 0) {
			cls = "red";
			note = __("{0}d overdue", [Math.abs(days)]);
		} else if (days <= 7) {
			cls = "orange";
			note = __("due in {0}d", [days]);
		}
		return `
			<span class="psp-amc-badge-row">
				${frappe.datetime.str_to_user(date)}
				<span class="psp-amc-chip ${cls}">${note}</span>
			</span>`;
	}

	render_history(history) {
		if (!history.length) {
			return `<div class="psp-amc-none text-muted">${__("No completed service visits yet")}</div>`;
		}

		return history
			.map((v) => {
				const esc = (x) => frappe.utils.escape_html(x || "");
				const parts = (v.parts || [])
					.map(
						(p) => `
						<tr>
							<td>${esc(p.part_no)}</td>
							<td>${esc(p.part_description)}</td>
							<td>${esc(p.issue_description)}</td>
							<td class="text-right">${cint(p.qty)}</td>
							<td class="text-right">${format_currency(p.part_cost || 0)}</td>
							<td class="text-right">${format_currency(p.extra_charges || 0)}</td>
						</tr>`
					)
					.join("");

				const parts_table = parts
					? `<table class="table table-bordered psp-amc-parts">
							<thead><tr>
								<th>${__("Part No")}</th><th>${__("Description")}</th><th>${__("Issue")}</th>
								<th class="text-right">${__("Qty")}</th>
								<th class="text-right">${__("Part Cost")}</th>
								<th class="text-right">${__("Extra Charges")}</th>
							</tr></thead>
							<tbody>${parts}</tbody>
						</table>`
					: `<div class="psp-amc-nopart text-muted">${__("No part change")}</div>`;

				const cond_cls = v.overall_equipment_condition
					? condition_class(v.overall_equipment_condition)
					: "gray";

				return `
					<div class="psp-amc-visit cond-${cond_cls}" data-open-visit="${esc(v.name)}">
						<div class="psp-amc-visit-head">
							<span class="psp-amc-visit-date">${
								v.service_date ? frappe.datetime.str_to_user(v.service_date) : __("Date not set")
							}</span>
							<span class="psp-amc-visit-name text-muted">${esc(v.name)}</span>
							${
								v.overall_equipment_condition
									? `<span class="psp-amc-chip ${condition_class(v.overall_equipment_condition)}">${esc(
											v.overall_equipment_condition
									  )}</span>`
									: ""
							}
						</div>
						<div class="psp-amc-visit-meta text-muted">
							${[
								v.service_type ? `${__("Type")}: ${esc(v.service_type)}` : "",
								v.service_engineer ? `${__("Engineer")}: ${esc(v.service_engineer)}` : "",
								v.estimated_service_date
									? `${__("Estimated")}: ${frappe.datetime.str_to_user(v.estimated_service_date)}`
									: "",
							]
								.filter(Boolean)
								.join(" &nbsp;·&nbsp; ")}
						</div>
						${v.remarks ? `<div class="psp-amc-visit-remarks">${esc(v.remarks)}</div>` : ""}
						${parts_table}
					</div>`;
			})
			.join("");
	}

	render_upcoming(upcoming, header) {
		if (!upcoming.next) {
			const done = cint(header.services_remaining) <= 0;
			return `<div class="psp-amc-none text-muted">${
				done ? __("All scheduled services completed") : __("No upcoming service visit")
			}</div>`;
		}

		const card = (v, is_next) => {
			const esc = (x) => frappe.utils.escape_html(x || "");
			const days = v.estimated_service_date
				? frappe.datetime.get_day_diff(v.estimated_service_date, frappe.datetime.now_date())
				: null;
			let chip = "";
			let status = "green";
			if (days != null) {
				if (days < 0) {
					status = "red";
					chip = `<span class="psp-amc-chip red">${__("{0}d overdue", [Math.abs(days)])}</span>`;
				} else if (days <= 7) {
					status = "orange";
					chip = `<span class="psp-amc-chip orange">${__("due in {0}d", [days])}</span>`;
				} else {
					chip = `<span class="psp-amc-chip green">${__("in {0}d", [days])}</span>`;
				}
			}
			return `
				<div class="psp-amc-upcoming-card status-${status} ${is_next ? "is-next" : ""}" data-open-visit="${esc(v.name)}">
					<div class="psp-amc-upcoming-date">
						${
							v.estimated_service_date
								? frappe.datetime.str_to_user(v.estimated_service_date)
								: __("Date not set")
						}
						${chip}
						${
							v.beyond_contract
								? `<span class="psp-amc-chip red">${__("beyond contract end")}</span>`
								: ""
						}
					</div>
					<div class="psp-amc-upcoming-sub text-muted">
						${esc(v.name)}${v.service_type ? ` &nbsp;·&nbsp; ${esc(v.service_type)}` : ""}
					</div>
				</div>`;
		};

		let html = `<div class="psp-amc-upcoming-next-label text-muted">${__("Next service")}</div>`;
		html += card(upcoming.next, true);

		if (upcoming.later.length) {
			html += `<div class="psp-amc-upcoming-later-label text-muted">${__("Later")}</div>`;
			html += upcoming.later.map((v) => card(v, false)).join("");
		}
		return html;
	}
}

function condition_class(condition) {
	return { Good: "green", Satisfactory: "orange", Bad: "red" }[condition] || "gray";
}

function inject_styles() {
	if (document.getElementById("psp-amc-styles")) return;
	$(`<style id="psp-amc-styles">
		.psp-amc {
			--psp-red: var(--red-500, #e24c4c);
			--psp-orange: var(--orange-500, #f5a623);
			--psp-green: var(--green-500, #29a745);
			--psp-blue: var(--blue-500, #2490ef);
			--psp-purple: var(--purple-500, #9b6dde);
			display: flex; gap: 0; border: 1px solid var(--border-color); border-radius: 12px;
			overflow: hidden; min-height: calc(100vh - 180px);
			box-shadow: var(--shadow-md, 0 2px 10px rgba(0,0,0,.06));
		}
		.psp-amc-list { width: 290px; flex: 0 0 290px; border-right: 1px solid var(--border-color); background: var(--fg-color); display: flex; flex-direction: column; }
		.psp-amc-list-head {
			padding: 10px;
			background: linear-gradient(135deg, color-mix(in srgb, var(--psp-blue) 14%, transparent), color-mix(in srgb, var(--psp-purple) 10%, transparent));
			border-bottom: 1px solid var(--border-color);
		}
		.psp-amc-list-body { overflow-y: auto; flex: 1; }
		.psp-amc-list-row {
			padding: 10px 12px; border-bottom: 1px solid var(--border-color); cursor: pointer;
			border-left: 3px solid transparent; transition: background .12s, border-color .12s;
		}
		.psp-amc-list-row.accent-green { border-left-color: color-mix(in srgb, var(--psp-green) 55%, transparent); }
		.psp-amc-list-row.accent-orange { border-left-color: color-mix(in srgb, var(--psp-orange) 55%, transparent); }
		.psp-amc-list-row.accent-red { border-left-color: color-mix(in srgb, var(--psp-red) 55%, transparent); }
		.psp-amc-list-row:hover { background: color-mix(in srgb, var(--psp-blue) 6%, var(--fg-color)); }
		.psp-amc-list-row.active {
			background: color-mix(in srgb, var(--psp-blue) 12%, var(--fg-color));
			border-left-color: var(--primary);
		}
		.psp-amc-list-row-title { display: flex; justify-content: space-between; align-items: center; font-weight: 600; margin-bottom: 2px; }
		.psp-amc-list-row-sub { font-size: 11px; line-height: 1.4; }
		.psp-amc-list-row-next { font-size: 11px; margin-top: 4px; font-weight: 500; }
		.psp-amc-detail { flex: 1; overflow-y: auto; padding: 16px; background: var(--bg-color); }
		.psp-amc-empty, .psp-amc-loading, .psp-amc-none { padding: 24px; text-align: center; }
		.psp-amc-header {
			position: relative; overflow: hidden;
			background: var(--fg-color); border: 1px solid var(--border-color); border-radius: 12px;
			padding: 16px 18px 14px; margin-bottom: 16px;
		}
		.psp-amc-header::before {
			content: ""; position: absolute; top: 0; left: 0; right: 0; height: 4px;
			background: linear-gradient(90deg, var(--psp-blue), var(--psp-purple), var(--psp-green), var(--psp-orange));
		}
		.psp-amc-header-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; margin-top: 4px; }
		.psp-amc-header-top h4 { margin: 0; }
		.psp-amc-header-top h4 a { color: var(--psp-blue); }
		.psp-amc-counts { display: flex; gap: 10px; }
		.psp-amc-count {
			display: flex; flex-direction: column; align-items: center; justify-content: center;
			line-height: 1.15; min-width: 58px; padding: 6px 10px; border-radius: 10px;
			background: color-mix(in srgb, var(--psp-blue) 10%, transparent);
		}
		.psp-amc-count b { font-size: 19px; color: var(--psp-blue); }
		.psp-amc-count small { color: var(--text-muted); font-size: 9px; text-transform: uppercase; letter-spacing: .04em; margin-top: 2px; }
		.psp-amc-count.red { background: color-mix(in srgb, var(--psp-red) 12%, transparent); }
		.psp-amc-count.red b { color: var(--psp-red); }
		.psp-amc-count.orange { background: color-mix(in srgb, var(--psp-orange) 14%, transparent); }
		.psp-amc-count.orange b { color: var(--psp-orange); }
		.psp-amc-count.green { background: color-mix(in srgb, var(--psp-green) 12%, transparent); }
		.psp-amc-count.green b { color: var(--psp-green); }
		.psp-amc-fields { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px 16px; margin-top: 14px; }
		.psp-amc-field-label { font-size: 10px; text-transform: uppercase; letter-spacing: .04em; color: var(--text-muted); }
		.psp-amc-field-value { font-size: 13px; font-weight: 500; }
		.psp-amc-badge-row { display: inline-flex; align-items: center; gap: 6px; flex-wrap: nowrap; white-space: nowrap; }
		.psp-amc-tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--border-color); margin-bottom: 14px; }
		.psp-amc-tab {
			border: none; background: none; padding: 8px 16px; cursor: pointer; color: var(--text-muted);
			border-radius: 8px 8px 0 0; font-weight: 500; transition: background .12s, color .12s;
		}
		.psp-amc-tab:hover { background: color-mix(in srgb, var(--psp-blue) 6%, transparent); }
		.psp-amc-tab.active {
			color: var(--psp-blue); background: color-mix(in srgb, var(--psp-blue) 12%, transparent);
			box-shadow: inset 0 -2px 0 var(--psp-blue);
		}
		.psp-amc-tab .count {
			background: var(--fg-color); border: 1px solid var(--border-color);
			border-radius: 8px; padding: 0 6px; font-size: 11px; margin-left: 4px;
		}
		.psp-amc-tab.active .count { background: var(--psp-blue); border-color: var(--psp-blue); color: #fff; }
		.psp-amc-visit {
			background: var(--fg-color); border: 1px solid var(--border-color); border-left: 4px solid transparent;
			border-radius: 10px; padding: 12px 14px; margin-bottom: 10px; cursor: pointer; transition: box-shadow .12s, border-color .12s;
		}
		.psp-amc-visit:hover { border-color: var(--psp-blue); box-shadow: 0 2px 8px rgba(0,0,0,.06); }
		.psp-amc-visit.cond-green { border-left-color: var(--psp-green); }
		.psp-amc-visit.cond-orange { border-left-color: var(--psp-orange); }
		.psp-amc-visit.cond-red { border-left-color: var(--psp-red); }
		.psp-amc-visit.cond-gray { border-left-color: var(--border-color); }
		.psp-amc-visit-head { display: flex; align-items: center; gap: 10px; }
		.psp-amc-visit-date { font-weight: 600; }
		.psp-amc-visit-meta { font-size: 12px; margin-top: 4px; }
		.psp-amc-visit-remarks {
			font-size: 12px; margin-top: 6px; padding: 6px 8px;
			background: color-mix(in srgb, var(--psp-orange) 8%, var(--bg-color)); border-radius: var(--border-radius);
		}
		.psp-amc-parts { margin-top: 10px; margin-bottom: 0; font-size: 12px; }
		.psp-amc-parts th {
			font-size: 10px; text-transform: uppercase; letter-spacing: .03em;
			background: color-mix(in srgb, var(--psp-purple) 8%, transparent);
		}
		.psp-amc-nopart { font-size: 12px; margin-top: 8px; }
		.psp-amc-chip { font-size: 10px; padding: 2px 8px; border-radius: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: .03em; white-space: nowrap; display: inline-block; }
		.psp-amc-chip.green { background: color-mix(in srgb, var(--psp-green) 18%, transparent); color: var(--green-600, var(--psp-green)); }
		.psp-amc-chip.orange { background: color-mix(in srgb, var(--psp-orange) 20%, transparent); color: var(--orange-600, var(--psp-orange)); }
		.psp-amc-chip.red { background: color-mix(in srgb, var(--psp-red) 18%, transparent); color: var(--red-600, var(--psp-red)); }
		.psp-amc-chip.gray { background: var(--bg-color); color: var(--text-muted); }
		.psp-amc-upcoming-next-label, .psp-amc-upcoming-later-label {
			font-size: 10px; text-transform: uppercase; letter-spacing: .06em; margin: 4px 0 6px; font-weight: 700; color: var(--psp-blue);
		}
		.psp-amc-upcoming-later-label { margin-top: 16px; color: var(--text-muted); }
		.psp-amc-upcoming-card {
			background: var(--fg-color); border: 1px solid var(--border-color); border-left: 4px solid transparent;
			border-radius: 10px; padding: 12px 14px; margin-bottom: 8px; cursor: pointer; transition: box-shadow .12s, border-color .12s;
		}
		.psp-amc-upcoming-card.status-green { border-left-color: var(--psp-green); }
		.psp-amc-upcoming-card.status-orange { border-left-color: var(--psp-orange); }
		.psp-amc-upcoming-card.status-red { border-left-color: var(--psp-red); }
		.psp-amc-upcoming-card:hover { border-color: var(--psp-blue); box-shadow: 0 2px 8px rgba(0,0,0,.06); }
		.psp-amc-upcoming-card.is-next {
			border-color: var(--psp-blue); box-shadow: 0 0 0 1px var(--psp-blue), 0 3px 10px color-mix(in srgb, var(--psp-blue) 20%, transparent);
			background: color-mix(in srgb, var(--psp-blue) 5%, var(--fg-color));
		}
		.psp-amc-upcoming-date { font-weight: 600; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
		.psp-amc-upcoming-sub { font-size: 12px; margin-top: 4px; }
		.psp-amc-report-scroll { overflow-x: auto; border: 1px solid var(--border-color); border-radius: 10px; }
		.psp-amc-report-table { margin: 0; font-size: 12px; background: var(--fg-color); }
		.psp-amc-report-table th {
			font-size: 10px; text-transform: uppercase; letter-spacing: .03em; vertical-align: middle;
			background: color-mix(in srgb, var(--psp-blue) 10%, transparent);
		}
		.psp-amc-report-table tbody tr:nth-child(even) { background: color-mix(in srgb, var(--text-muted) 4%, transparent); }
		.psp-amc-report-table tbody tr { cursor: pointer; }
		.psp-amc-report-table tbody tr:hover { background: color-mix(in srgb, var(--psp-blue) 12%, transparent); }
		.psp-amc-report-table .nowrap { white-space: nowrap; }
	</style>`).appendTo(document.head);
}
