frappe.query_reports["Planning Engine RM Production"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 1,
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "category_name",
			label: __("Category Name"),
			fieldtype: "Data",
		},
		{
			fieldname: "production_plan",
			label: __("Production Plan"),
			fieldtype: "Link",
			options: "Production Plan",
		},
		{
			fieldname: "production_planning",
			label: __("Production Planning"),
			fieldtype: "Link",
			options: "Production Planning",
		},
	],
};
