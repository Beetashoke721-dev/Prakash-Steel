# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt


def get_data() -> list[dict]:
	return {
		"fieldname": "production_planning",
		"transactions": [
			{
				"label": "Rolled Production",
				"items": ["Billet Cutting", "Hourly Production", "Finish Weight"],
			},
			{
				"label": "Bright Production",
				"items": ["Bright Bar Production"],
			},
		],
	}
