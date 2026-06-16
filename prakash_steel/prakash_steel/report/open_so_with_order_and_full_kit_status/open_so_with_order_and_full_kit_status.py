import copy
from collections import OrderedDict

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate


def execute(filters=None):
	if not filters:
		return [], [], None, []

	validate_filters(filters)

	columns = get_columns()
	
	# Get allowed customers for current user
	allowed_customers = get_allowed_customers_for_user()
	if allowed_customers is not None and len(allowed_customers) == 0:
		# User has no associated customers, return empty result
		return columns, [], None, None
	
	# Add customer filter condition if user has restrictions
	if allowed_customers is not None:
		if not filters:
			filters = {}
		filters["allowed_customers"] = allowed_customers
	
	conditions = get_conditions(filters)
	data = get_data(conditions, filters)

	if not data:
		return [], [], None, []

	data = prepare_data(data, filters)

	return columns, data, None, None


def get_allowed_customers_for_user():
	"""
	Get list of customers associated with the current user via portal_users child table.
	Returns None if user has no restrictions (e.g., admin/system user), 
	or list of customer names if user has restrictions.
	"""
	current_user = frappe.session.user
	
	# Skip restriction for system users/admins (optional - you can remove this if you want to restrict everyone)
	if current_user in ("Administrator", "Guest"):
		return None
	
	# Find the child doctype name by querying DocType for Customer's child tables
	# The child table field name in Customer is "portal_users"
	try:
		portal_users_field = frappe.get_meta("Customer").get_field("portal_users")

		if not portal_users_field:
			# Field not found, return None (no restrictions)
			return None

		child_doctype = portal_users_field.options
		child_table = f"tab{child_doctype}"
		
		# Query to find customers where the portal_users child table has the current user
		# Note: Using format for table name is safe here as it comes from DocType definition
		query = f"""
			SELECT DISTINCT parent as customer
			FROM `{child_table}`
			WHERE parenttype = 'Customer' AND user = %s
		"""
		customers = frappe.db.sql(
			query,
			(current_user,),
			as_dict=True,
		)
		
		if customers:
			return [c.customer for c in customers]
		
		# If no results, return empty list (user has no associated customers)
		return []
		
	except Exception as e:
		# If there's any error, log it and return None (no restrictions)
		frappe.log_error(f"Error getting allowed customers for user {current_user}: {str(e)}", "Open SO Report Error")
		return None


def validate_filters(filters):
	from_date, to_date = filters.get("from_date"), filters.get("to_date")

	if not from_date and to_date:
		frappe.throw(_("From and To Dates are required."))
	elif date_diff(to_date, from_date) < 0:
		frappe.throw(_("To Date cannot be before From Date."))


def get_conditions(filters):
	conditions = ""
	if filters.get("from_date") and filters.get("to_date"):
		conditions += " and so.transaction_date between %(from_date)s and %(to_date)s"

	if filters.get("company"):
		conditions += " and so.company = %(company)s"

	if filters.get("sales_order"):
		conditions += " and so.name in %(sales_order)s"
	
	# Handle status filter - check if it exists and is not empty
	status = filters.get("status")
	if status and (isinstance(status, list) and len(status) > 0):
		conditions += " and so.status in %(status)s"
	
	# Handle warehouse filter - check if it exists and is not empty
	warehouse = filters.get("warehouse")
	if warehouse:
		conditions += " and soi.warehouse = %(warehouse)s"
	
	# Filter by allowed customers if user has restrictions
	allowed_customers = filters.get("allowed_customers")
	if allowed_customers is not None:
		if len(allowed_customers) > 0:
			conditions += " and so.customer in %(allowed_customers)s"
		else:
			# User has no associated customers, return no results
			conditions += " and 1=0"

	return conditions


def get_data(conditions, filters):
	# Fetch data from Sales Order and Sales Order Item
	data = frappe.db.sql(
		f"""
        SELECT
            so.transaction_date as date,
            soi.delivery_date as delivery_date,
            so.name as sales_order,
            so.customer,
            soi.item_code,
            soi.qty,
            soi.delivered_qty,
            (soi.qty - soi.delivered_qty) AS pending_qty,
            soi.name as so_detail_name
        FROM
            `tabSales Order` so,
            `tabSales Order Item` soi
        WHERE
            soi.parent = so.name
            and so.status not in ('Stopped', 'On Hold')
            and so.docstatus = 1
            {conditions}
        ORDER BY
            soi.delivery_date ASC,
            so.name,
            soi.item_code
    """,
		filters,
		as_dict=1,
	)

	return data


def prepare_data(data, filters):
	# Filter out rows where pending_qty (qty_to_deliver) is 0 or negative
	# Only show items that still need to be delivered (Open SO items)
	# Also filter out rows where sales order status is "Closed" or "Cancelled"
	data = [
		row
		for row in data
		if flt(row.get("pending_qty") or 0) > 0
	]

	# Build stock map: total actual_qty across all warehouses for each item
	item_codes = {row.get("item_code") for row in data if row.get("item_code")}
	stock_map = {}
	if item_codes:
		bin_rows = frappe.db.sql(
			"""
            SELECT item_code, SUM(actual_qty) as stock
            FROM `tabBin`
            WHERE item_code in %(items)s
            GROUP BY item_code
            """,
			{"items": tuple(item_codes)},
			as_dict=True,
		)
		stock_map = {d.item_code: flt(d.stock) for d in bin_rows}

	# Remaining stock per item for FIFO allocation (start from total stock)
	remaining_stock = dict(stock_map)

	for row in data:
		# Convert quantity fields to integers
		row["qty"] = int(flt(row.get("qty", 0)))
		row["delivered_qty"] = int(flt(row.get("delivered_qty", 0)))
		row["pending_qty"] = int(flt(row.get("pending_qty", 0)))

		# FIFO Stock Allocation and Shortage per item
		# Use pending_qty (qty_to_deliver) instead of order qty
		item_code = row.get("item_code")
		required_qty = flt(row.get("pending_qty") or 0)  # qty_to_deliver
		available_qty = flt(remaining_stock.get(item_code, 0))

		allocated = min(required_qty, available_qty)
		shortage = required_qty - allocated

		# Calculate Line Fullkit for this line/item
		# If shortage = 0 → "Full-kit"
		# Else if stock_allocation = 0 → "Pending"
		# Else → "Partial"
		if flt(shortage) == 0:
			row["line_fullkit"] = "Full-kit"
		elif flt(allocated) == 0:
			row["line_fullkit"] = "Pending"
		else:
			row["line_fullkit"] = "Partial"

		# Reduce remaining stock for this item
		remaining_stock[item_code] = available_qty - allocated

	# Calculate Order Fullkit: Group by sales_order and check line_fullkit values
	# Build a map of sales_order -> list of line_fullkit values
	so_line_fullkit_map = {}
	for row in data:
		so_name = row.get("sales_order")
		if so_name:
			if so_name not in so_line_fullkit_map:
				so_line_fullkit_map[so_name] = []
			line_fullkit_val = row.get("line_fullkit") or ""
			so_line_fullkit_map[so_name].append(line_fullkit_val)

	# For each sales order, determine Order Fullkit based on all line_fullkit values
	so_fullkit_map = {}
	for so_name, line_fullkits in so_line_fullkit_map.items():
		# Remove empty values
		line_fullkits = [lf for lf in line_fullkits if lf]

		if not line_fullkits:
			so_fullkit_map[so_name] = "Pending"
		elif all(lf == "Full-kit" for lf in line_fullkits):
			# All items are Full-kit
			so_fullkit_map[so_name] = "Full-kit"
		elif all(lf == "Pending" for lf in line_fullkits):
			# All items are Pending
			so_fullkit_map[so_name] = "Pending"
		else:
			# Mixed: any combination of Full-kit with Pending/Partial, or any Partial
			so_fullkit_map[so_name] = "Partial"

	# Assign Order Fullkit to each row based on its sales_order
	for row in data:
		so_name = row.get("sales_order")
		row["order_fullkit"] = so_fullkit_map.get(so_name, "Pending")

	return data


def get_columns():
	columns = [
		{"label": _("Sales Order Date"), "fieldname": "date", "fieldtype": "Date", "width": 120},
		{
			"label": _("Sales Order"),
			"fieldname": "sales_order",
			"fieldtype": "Link",
			"options": "Sales Order",
			"width": 160,
		},
		{
			"label": _("Delivery Date"),
			"fieldname": "delivery_date",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{
			"label": _("Ordered Qty"),
			"fieldname": "qty",
			"fieldtype": "Int",
			"width": 120,
			"convertible": "qty",
		},
		{
			"label": _("Delivered Qty"),
			"fieldname": "delivered_qty",
			"fieldtype": "Int",
			"width": 120,
			"convertible": "qty",
		},
		{
			"label": _("Quantity to Deliver"),
			"fieldname": "pending_qty",
			"fieldtype": "Int",
			"width": 140,
			"convertible": "qty",
		},
		{
			"label": _("Line Full Kit Status"),
			"fieldname": "line_fullkit",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Order Full Kit Status"),
			"fieldname": "order_fullkit",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Customer Name"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 150,
		},
	]

	return columns
