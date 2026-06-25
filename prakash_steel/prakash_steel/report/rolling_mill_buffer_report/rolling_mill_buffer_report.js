// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Rolling Mill Buffer Report"] = {
	"filters": [],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "on_hand_colour" && data && data.on_hand_colour) {
			let colour = data.on_hand_colour;
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

			value = `<span style="
				background-color:${bg};
				color:${textColor};
				padding: 2px 10px;
				border-radius: 4px;
				font-weight: bold;
				display: inline-block;
			">${colour}</span>`;
		}

		return value;
	}
};
