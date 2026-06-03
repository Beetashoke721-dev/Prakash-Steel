// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

const COLOUR_STYLES = {
	Black: { bg: "#222", fg: "#fff" },
	Red: { bg: "#e74c3c", fg: "#fff" },
	Yellow: { bg: "#f1c40f", fg: "#333" },
	Green: { bg: "#27ae60", fg: "#fff" },
	White: { bg: "#f0f0f0", fg: "#333" },
};

function get_colour_style(val) {
	const upper = (val || "").toUpperCase();
	for (const c of ["BLACK", "RED", "YELLOW", "GREEN", "WHITE"]) {
		if (upper.endsWith(c)) return COLOUR_STYLES[c.charAt(0) + c.slice(1).toLowerCase()];
	}
	return null;
}

frappe.query_reports["Open Mr(wo) Report"] = {
	filters: [],

	formatter(value, row, column, data, default_formatter) {
		if (column.fieldname === "colour" && value && COLOUR_STYLES[value]) {
			const { bg, fg } = COLOUR_STYLES[value];
			return `<span style="
				background:${bg};
				color:${fg};
				padding:2px 10px;
				border-radius:4px;
				font-weight:bold;
				display:inline-block;
			">${value}</span>`;
		}
		if (column.fieldname === "priority" && value) {
			const s = get_colour_style(value);
			if (s) {
				return `<span style="
					background:${s.bg};
					color:${s.fg};
					padding:2px 10px;
					border-radius:4px;
					font-weight:bold;
					display:inline-block;
				">${value}</span>`;
			}
		}
		return default_formatter(value, row, column, data);
	},

	onload(_report) {},
};
