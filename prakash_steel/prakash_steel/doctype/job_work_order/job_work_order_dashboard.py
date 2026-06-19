# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt


def get_data() -> list[dict]:
	return {
		"fieldname": "custom_job_work_order",
		"transactions": [
			{
				"label": "Outward",
				"items": ["Delivery Note"],
			},
			{
				"label": "Inward",
				"items": ["Purchase Receipt"],
			},
		],
	}
