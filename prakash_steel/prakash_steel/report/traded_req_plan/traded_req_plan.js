// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Traded Req Plan"] = {
	filters: [],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		// Background colors for On Hand Colour status
		if (column.fieldname === "on_hand_colour" && data && data.on_hand_colour) {
			let colour = data.on_hand_colour;
			let bg = "";
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

			if (bg) {
				return `<div style="
					background-color:${bg};
					border-radius:0px;
					padding:4px;
					text-align:center;
					font-weight:bold;
					color:${textColor};
				">
					${colour}
				</div>`;
			}
		}

		return value;
	},
};
