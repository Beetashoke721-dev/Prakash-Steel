if (!frappe.pages["machine-wise-monthly-dashboard"]) {
    frappe.pages["machine-wise-monthly-dashboard"] = {};
}

frappe.pages["machine-wise-monthly-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Machine-wise Monthly Dashboard"),
        single_column: true,
    });

    const state = { page, controls: {} };
    render_filters(state);
    render_table_shell(state);
    load_data(state);
};

function render_filters(state) {
    const $filterBar = $(`
        <div style="display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap;margin-bottom:16px;background:#f8f9fa;padding:16px;border-radius:8px;">
            <div id="mwm-year-filter" style="min-width:180px;"></div>
            <div id="mwm-machine-filter" style="min-width:220px;"></div>
            <div style="min-width:110px;">
                <div style="height:20px;margin-bottom:6px;"></div>
                <button class="btn btn-primary" id="mwm-refresh-btn" style="height:36px;padding:6px 14px;display:inline-flex;align-items:center;">${__("Refresh")}</button>
            </div>
            <div style="min-width:140px;">
                <div style="height:20px;margin-bottom:6px;"></div>
                <div class="mwm-export-dropdown" style="position:relative;">
                    <button type="button" class="btn btn-default" id="mwm-export-toggle"
                        style="height:36px;padding:6px 14px;display:inline-flex;align-items:center;gap:6px;border:1px solid #000;border-radius:4px;">
                        <i class="fa fa-download"></i>
                        <span>${__("Export")}</span>
                        <span style="font-size:0.75rem;">▾</span>
                    </button>
                    <div id="mwm-export-menu" style="display:none;position:absolute;left:0;top:100%;margin-top:4px;
                        background:#fff;border:1px solid #ced4da;border-radius:4px;box-shadow:0 2px 6px rgba(0,0,0,0.12);
                        min-width:160px;z-index:20;">
                        <div class="mwm-export-option" data-format="excel"
                            style="padding:10px 14px;cursor:pointer;font-size:0.9rem;border-bottom:1px solid #eee;">
                            ${__("Excel")}
                        </div>
                        <div class="mwm-export-option" data-format="pdf"
                            style="padding:10px 14px;cursor:pointer;font-size:0.9rem;">
                            ${__("PDF")}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `);

    $(state.page.main).append($filterBar);

    state.controls.year = frappe.ui.form.make_control({
        parent: $filterBar.find("#mwm-year-filter").get(0),
        df: {
            fieldtype: "Link",
            label: __("Fiscal Year"),
            fieldname: "fiscal_year",
            options: "Fiscal Year",
            reqd: 1,
        },
        render_input: true,
    });
    const defaultFiscalYear =
        frappe.defaults.get_user_default("fiscal_year")
        || (frappe.boot && frappe.boot.sysdefaults && frappe.boot.sysdefaults.fiscal_year)
        || (frappe.sys_defaults && frappe.sys_defaults.fiscal_year);
    if (defaultFiscalYear) {
        state.controls.year.set_value(defaultFiscalYear);
    }

    state.controls.machine_name = frappe.ui.form.make_control({
        parent: $filterBar.find("#mwm-machine-filter").get(0),
        df: {
            fieldtype: "Link",
            label: __("Machine"),
            fieldname: "machine_name",
            options: "Machine Master",
            reqd: 0,
        },
        render_input: true,
    });

    setTimeout(() => {
        if (state.controls.year.$input) {
            $(state.controls.year.$input).css({
                border: "1px solid #000",
                "border-radius": "4px",
                padding: "8px 12px",
                height: "36px",
                "line-height": "1.4",
            });
        }
        if (state.controls.machine_name.$input) {
            $(state.controls.machine_name.$input).css({
                border: "1px solid #000",
                "border-radius": "4px",
                padding: "8px 12px",
                height: "36px",
                "line-height": "1.4",
            });
        }
    }, 100);

    $filterBar.find("#mwm-refresh-btn").on("click", () => load_data(state));

    const $exportMenu = $filterBar.find("#mwm-export-menu");
    $filterBar.find("#mwm-export-toggle").on("click", (e) => {
        e.stopPropagation();
        $exportMenu.toggle();
    });
    $filterBar.find(".mwm-export-option").on("click", (e) => {
        e.stopPropagation();
        const format = $(e.currentTarget).data("format");
        $exportMenu.hide();
        export_machine_wise_monthly(state, format);
    });
    $(document).on("click.mwmExportClose", () => $exportMenu.hide());
}

function render_table_shell(state) {
    const $container = $(`
        <div class="mwm-table-wrapper">
            <div id="mwm-table-container" style="overflow:auto;border:1px solid #ddd;border-radius:8px;background:#fff;"></div>
        </div>
    `);
    state.controls.$table_container = $container.find("#mwm-table-container");
    $(state.page.main).append($container);
}

function load_data(state) {
    const fiscal_year = state.controls.year ? state.controls.year.get_value() : null;
    const machine_name = state.controls.machine_name ? state.controls.machine_name.get_value() : null;

    frappe.call({
        method: "prakash_steel.api.machine_wise_monthly_dashboard.get_machine_wise_monthly_data",
        args: { fiscal_year, machine_name },
        freeze: true,
        freeze_message: __("Loading Machine Wise Monthly Dashboard..."),
        callback: function (r) {
            try {
                const result = r.message || {};
                const machines = Array.isArray(result.machines) ? result.machines : [];
                const rows = Array.isArray(result.rows) ? result.rows : [];
                if (state.controls.year && !state.controls.year.get_value() && result.fiscal_year) {
                    state.controls.year.set_value(result.fiscal_year);
                }
                render_matrix_table(state, machines, rows, result.fiscal_year);
            } catch (e) {
                console.error("Machine wise monthly dashboard render error:", e);
                state.controls.$table_container.html(
                    `<div style="padding:16px;color:#b02a37;">${__("Unable to render dashboard table.")} ${escape_html(e && e.message ? e.message : "")}</div>`
                );
            }
        },
        error: function (err) {
            console.error("Machine wise monthly dashboard API error:", err);
            state.controls.$table_container.html(
                `<div style="padding:16px;color:#b02a37;">${__("Failed to load dashboard data. Check server logs.")}</div>`
            );
        },
    });
}

function render_matrix_table(state, machines, rows, fiscal_year) {
    if (!machines.length) {
        state.controls.$table_container.html(
            `<div style="padding:16px;">${__("No machine records found.")}</div>`
        );
        return;
    }

    const topHeader = [`<th rowspan="2" style="${th_style(true, true)}">${__("Month")}</th>`];
    const subHeader = [];
    machines.forEach((machine, idx) => {
        const isLastMachine = idx === machines.length - 1;
        topHeader.push(`<th colspan="2" style="${th_style(false, !isLastMachine)}">${escape_html(machine)}</th>`);
        subHeader.push(`<th style="${th_style(false)}">${__("FG Weight")}</th>`);
        subHeader.push(`<th style="${th_style(false, !isLastMachine)}">${__("Amount")}</th>`);
    });
    topHeader.push(`<th colspan="2" style="${th_style(false, false, true)}">${__("Total")}</th>`);
    subHeader.push(`<th style="${th_style(false, false, true)}">${__("FG Weight")}</th>`);
    subHeader.push(`<th style="${th_style(false)}">${__("Amount")}</th>`);

    const bodyRows = rows.map((row) => {
        let tr = `<tr><td style="${td_style(true, true)}"><strong>${escape_html(row.month || "")}</strong></td>`;
        let totalFgWeight = 0;
        let totalAmount = 0;
        machines.forEach((machine, idx) => {
            const isLastMachine = idx === machines.length - 1;
            const fgWeight = Number(row[`${machine}__fg_weight`] || 0);
            const amount = Number(row[`${machine}__amount`] || 0);
            totalFgWeight += Number.isFinite(fgWeight) ? fgWeight : 0;
            totalAmount += Number.isFinite(amount) ? amount : 0;
            tr += `<td style="${td_style(false)}">${format_weight(fgWeight)}</td>`;
            tr += `<td style="${td_style(false, !isLastMachine)}">${format_number(amount)}</td>`;
        });
        tr += `<td style="${td_style(false, false, true)}"><strong>${format_weight(totalFgWeight)}</strong></td>`;
        tr += `<td style="${td_style(false)}"><strong>${format_number(totalAmount)}</strong></td>`;
        tr += "</tr>";
        return tr;
    });

    const html = `
        <table class="table table-bordered" style="margin:0;min-width:800px;">
            <thead>
                <tr>
                    ${topHeader.join("")}
                </tr>
                <tr>
                    ${subHeader.join("")}
                </tr>
            </thead>
            <tbody>
                ${bodyRows.join("")}
            </tbody>
        </table>
        <div style="padding:10px 12px;color:#666;font-size:12px;">
            ${__("Values are month-wise totals from Bright Bar Production for Fiscal Year")} ${escape_html(String(fiscal_year || ""))}. ${__("Month order follows selected Fiscal Year.")}
        </div>
    `;

    state.controls.$table_container.html(html);
}

function format_number(value) {
    const num = Number(value || 0);
    if (!Number.isFinite(num)) return "0.00";
    return num.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function format_weight(value) {
    const num = Number(value || 0);
    if (!Number.isFinite(num)) return "0";
    return Math.round(num).toLocaleString();
}

function escape_html(value) {
    return $("<div>").text(value == null ? "" : String(value)).html();
}

function export_machine_wise_monthly(state, format) {
    const fiscal_year = state.controls.year ? state.controls.year.get_value() : null;
    if (!fiscal_year) {
        frappe.show_alert({ message: __("Please select a Fiscal Year before exporting."), indicator: "orange" });
        return;
    }
    const machine_name = state.controls.machine_name ? state.controls.machine_name.get_value() || "" : "";
    const method =
        format === "excel"
            ? "prakash_steel.api.machine_wise_monthly_dashboard.export_machine_wise_monthly_excel"
            : "prakash_steel.api.machine_wise_monthly_dashboard.export_machine_wise_monthly_pdf";
    const params = new URLSearchParams({
        fiscal_year,
        machine_name: machine_name || "",
    });
    const url = `/api/method/${method}?${params.toString()}`;
    window.open(url, "_blank");
}

function th_style(is_month, add_group_separator, add_left_separator) {
    return [
        "background:#f1f3f5",
        "position:sticky",
        "top:0",
        "z-index:1",
        "white-space:nowrap",
        "padding:10px",
        "text-align:center",
        add_group_separator ? "border-right:2px solid #7a7a7a;" : "",
        add_left_separator ? "border-left:2px solid #7a7a7a;" : "",
        is_month ? "left:0;z-index:2;" : "",
    ].join(";");
}

function td_style(is_month, add_group_separator, add_left_separator) {
    return [
        "padding:10px",
        "text-align:center",
        "white-space:nowrap",
        add_group_separator ? "border-right:2px solid #7a7a7a;" : "",
        add_left_separator ? "border-left:2px solid #7a7a7a;" : "",
        is_month ? "text-align:left;position:sticky;left:0;background:#f1f3f5;z-index:1;" : "",
    ].join(";");
}
