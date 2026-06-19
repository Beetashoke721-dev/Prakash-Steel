# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, add_days
from datetime import datetime, timedelta
from collections import defaultdict


def execute(filters=None) -> tuple[list, list]:
	filters = filters or {}
	
	# Get calculation mode (default to Monthly)
	calculation_mode = filters.get("calculation_mode", "Monthly")
	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))
	
	# Get allowed customers for current user
	allowed_customers = get_allowed_customers_for_user()
	if allowed_customers is not None and len(allowed_customers) == 0:
		# User has no associated customers, return empty result
		columns = get_columns(from_date, to_date, calculation_mode)
		return columns, []
	
	# Get columns based on calculation mode
	columns = get_columns(from_date, to_date, calculation_mode)
	
	# Get data
	data = get_data(from_date, to_date, calculation_mode, allowed_customers)
	
	return columns, data


def get_columns(from_date, to_date, calculation_mode) -> list[dict]:
	"""Generate dynamic columns based on calculation mode and date range"""
	columns = [
		{
			"label": "Item Code",
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": "Item Type",
			"fieldname": "item_type",
			"fieldtype": "Data",
			"width": 120,
		},
	]
	
	if calculation_mode == "Monthly":
		# Generate monthly columns dynamically based on date range
		month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
					   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
		
		# Start from the first month of from_date
		current_date = datetime(from_date.year, from_date.month, 1)
		end_date = datetime(to_date.year, to_date.month, 1)
		
		while current_date <= end_date:
			year = current_date.year
			month = current_date.month
			month_label = f"{month_names[month - 1]} {str(year)[-2:]}"
			fieldname = f"month_{year}_{month:02d}"
			
			columns.append({
				"label": month_label,
				"fieldname": fieldname,
				"fieldtype": "Float",
				"width": 100,
				"precision": 2,
			})
			
			# Move to next month
			if month == 12:
				current_date = datetime(year + 1, 1, 1)
			else:
				current_date = datetime(year, month + 1, 1)
	
	else:  # Weekly
		# Generate weekly columns dynamically based on date range
		# Get all weeks that fall within the date range
		week_info = get_weeks_in_range(from_date, to_date)
		
		for week_label, fieldname in week_info:
			columns.append({
				"label": week_label,
				"fieldname": fieldname,
				"fieldtype": "Float",
				"width": 100,
				"precision": 2,
			})
	
	return columns


def get_allowed_customers_for_user() -> list[str]:
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
		customer_doc = frappe.get_doc("DocType", "Customer")
		portal_users_field = None
		for field in customer_doc.fields:
			if field.fieldname == "portal_users":
				portal_users_field = field
				break
		
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
		frappe.log_error(f"Error getting allowed customers for user {current_user}: {str(e)}", "SKU Sales History Report Error")
		return None


def get_data(from_date, to_date, calculation_mode, allowed_customers=None) -> list[dict]:
	"""Get sales invoice data grouped by item and period"""
	
	# Build query with customer filter if user has restrictions
	query = """
		SELECT
			sii.item_code,
			i.custom_item_type as item_type,
			si.posting_date,
			sii.qty
		FROM
			`tabSales Invoice` si
		INNER JOIN
			`tabSales Invoice Item` sii ON sii.parent = si.name
		LEFT JOIN
			`tabItem` i ON i.name = sii.item_code
		WHERE
			si.docstatus = 1
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
	"""
	
	# Add customer filter if user has restrictions
	query_params = {
		"from_date": from_date,
		"to_date": to_date
	}
	
	if allowed_customers is not None:
		if len(allowed_customers) > 0:
			query += " AND si.customer IN %(allowed_customers)s"
			query_params["allowed_customers"] = allowed_customers
		else:
			# User has no associated customers, return empty result
			return []
	
	query += " ORDER BY sii.item_code, si.posting_date"
	
	sales_data = frappe.db.sql(query, query_params, as_dict=True)
	
	# Get period keys based on calculation mode
	if calculation_mode == "Monthly":
		# Generate period keys for all months in range
		period_keys = []
		current_date = datetime(from_date.year, from_date.month, 1)
		end_date = datetime(to_date.year, to_date.month, 1)
		
		while current_date <= end_date:
			year = current_date.year
			month = current_date.month
			period_keys.append(f"month_{year}_{month:02d}")
			
			if month == 12:
				current_date = datetime(year + 1, 1, 1)
			else:
				current_date = datetime(year, month + 1, 1)
	else:  # Weekly
		# Get period keys for all weeks in range
		week_info = get_weeks_in_range(from_date, to_date)
		period_keys = [fieldname for _, fieldname in week_info]
	
	# Group data by item and period
	item_period_data = defaultdict(lambda: defaultdict(float))
	all_items = set()
	
	for row in sales_data:
		item_code = row.get("item_code")
		if not item_code:
			continue
			
		all_items.add(item_code)
		posting_date = getdate(row.get("posting_date"))
		qty = row.get("qty") or 0
		
		if calculation_mode == "Monthly":
			# Group by month and year - aggregate all quantities in that month
			year = posting_date.year
			month = posting_date.month
			period_key = f"month_{year}_{month:02d}"
			item_period_data[item_code][period_key] += qty
		else:  # Weekly
			# Group by week (Monday to Sunday)
			period_key = get_week_key(posting_date)
			if period_key:
				item_period_data[item_code][period_key] += qty
	
	# Get item types for all items
	item_types = {}
	if all_items:
		items_data = frappe.db.sql("""
			SELECT name, custom_item_type
			FROM `tabItem`
			WHERE name IN %(items)s
		""", {"items": list(all_items)}, as_dict=True)
		
		for item in items_data:
			item_types[item.name] = item.get("custom_item_type") or ""
	
	# Build result data
	result = []
	for item_code in sorted(all_items):
		row_data = {
			"item_code": item_code,
			"item_type": item_types.get(item_code, ""),
		}
		
		# Add period data for all periods in range
		period_data = item_period_data[item_code]
		for period_key in period_keys:
			row_data[period_key] = period_data.get(period_key, 0)
		
		result.append(row_data)
	
	return result


def get_week_number(date) -> int:
	"""
	Get week number for a date within its year (Monday to Sunday weeks)
	Week 1 starts from January 1st and ends on the first Sunday
	Subsequent weeks are Monday to Sunday
	"""
	# Get the first day of the year
	year_start = datetime(date.year, 1, 1)
	year_start_date = getdate(year_start)
	
	# weekday(): 0=Monday, 1=Tuesday, ..., 6=Sunday
	first_day_weekday = year_start.weekday()
	
	# Calculate days until first Sunday
	days_to_first_sunday = (6 - first_day_weekday) % 7
	if days_to_first_sunday == 0 and first_day_weekday != 6:
		days_to_first_sunday = 7
	
	first_sunday = year_start_date + timedelta(days=days_to_first_sunday)
	
	# If date is in Week 1 (Jan 1 to first Sunday, inclusive)
	if date <= first_sunday:
		return 1
	
	# Week 2 starts on the Monday after first Sunday
	week2_start = first_sunday + timedelta(days=1)
	
	# Calculate days from Week 2 start
	days_from_week2 = (date - week2_start).days
	
	# Calculate week number (Week 2 + number of full weeks)
	# Each week is 7 days (Monday to Sunday)
	week_num = 2 + (days_from_week2 // 7)
	
	# Ensure week number doesn't exceed 52
	return min(week_num, 52)


def get_week_key(date) -> str:
	"""
	Get unique week key for a date (includes year and week number)
	Returns format: week_YYYY_WW
	"""
	year = date.year
	week_num = get_week_number(date)
	return f"week_{year}_{week_num:02d}"


def get_weeks_in_range(from_date, to_date) -> list:
	"""
	Get all weeks that fall within the date range
	Returns list of tuples: (label, fieldname)
	"""
	weeks_info = []
	seen_weeks = set()
	
	from_date = getdate(from_date)
	to_date = getdate(to_date)
	
	# Get week boundaries for each year in range
	year_week_map = {}
	
	for year in range(from_date.year, to_date.year + 1):
		year_start = datetime(year, 1, 1)
		year_start_date = getdate(year_start)
		first_day_weekday = year_start.weekday()
		
		days_to_first_sunday = (6 - first_day_weekday) % 7
		if days_to_first_sunday == 0 and first_day_weekday != 6:
			days_to_first_sunday = 7
		
		first_sunday = year_start_date + timedelta(days=days_to_first_sunday)
		week2_start = first_sunday + timedelta(days=1)
		
		year_week_map[year] = {
			"first_sunday": first_sunday,
			"week2_start": week2_start
		}
	
	# Optimized: Iterate week by week instead of day by day
	# Find the start of the first week containing from_date
	start_year = from_date.year
	start_week_num = get_week_number(from_date)
	start_year_info = year_week_map[start_year]
	
	if start_week_num == 1:
		first_week_start = datetime(start_year, 1, 1)
		first_week_end = start_year_info["first_sunday"]
		# Next week starts the day after first Sunday
		next_week_start = add_days(getdate(first_week_end), 1)
	else:
		days_from_week2 = (start_week_num - 2) * 7
		first_week_start = start_year_info["week2_start"] + timedelta(days=days_from_week2)
		first_week_end = getdate(first_week_start) + timedelta(days=6)
		# Next week starts 7 days after current week start
		next_week_start = add_days(getdate(first_week_start), 7)
	
	# Process first week if it overlaps with date range
	if getdate(first_week_end) >= from_date:
		week_key = get_week_key(from_date)
		if week_key not in seen_weeks:
			seen_weeks.add(week_key)
			start_str = getdate(first_week_start).strftime("%d %b")
			end_str = getdate(first_week_end).strftime("%d %b")
			year_short = str(start_year)[-2:]
			
			if getdate(first_week_start).year != getdate(first_week_end).year:
				label = f"Week {start_week_num} ({start_str} {str(getdate(first_week_start).year)[-2:]} - {end_str} {year_short})"
			else:
				label = f"Week {start_week_num} ({start_str} - {end_str} {year_short})"
			weeks_info.append((label, week_key))
	
	# Now iterate week by week (each week is exactly 7 days after week 1)
	current_week_start = next_week_start
	
	while current_week_start <= to_date:
		# Get year and week number for current week start
		year = current_week_start.year
		week_num = get_week_number(current_week_start)
		
		# Ensure year_week_map has info for this year
		if year not in year_week_map:
			year_start = datetime(year, 1, 1)
			year_start_date = getdate(year_start)
			first_day_weekday = year_start.weekday()
			
			days_to_first_sunday = (6 - first_day_weekday) % 7
			if days_to_first_sunday == 0 and first_day_weekday != 6:
				days_to_first_sunday = 7
			
			first_sunday = year_start_date + timedelta(days=days_to_first_sunday)
			week2_start = first_sunday + timedelta(days=1)
			
			year_week_map[year] = {
				"first_sunday": first_sunday,
				"week2_start": week2_start
			}
		
		year_info = year_week_map[year]
		
		# Calculate actual week boundaries
		if week_num == 1:
			# Week 1: Jan 1 to first Sunday
			actual_week_start = datetime(year, 1, 1)
			actual_week_end = year_info["first_sunday"]
			# Next week starts the day after first Sunday
			next_week_start = add_days(getdate(actual_week_end), 1)
		else:
			# Week 2+: Monday to Sunday (7 days)
			actual_week_start = current_week_start
			actual_week_end = current_week_start + timedelta(days=6)
			# Next week starts 7 days later
			next_week_start = add_days(current_week_start, 7)
		
		# Only process if this week overlaps with our date range
		if getdate(actual_week_end) >= from_date and getdate(actual_week_start) <= to_date:
			# Get week key
			week_key = get_week_key(current_week_start)
			
			if week_key not in seen_weeks:
				seen_weeks.add(week_key)
				
				# Format label
				start_str = getdate(actual_week_start).strftime("%d %b")
				end_str = getdate(actual_week_end).strftime("%d %b")
				year_short = str(year)[-2:]
				
				if getdate(actual_week_start).year != getdate(actual_week_end).year:
					# Week spans across years
					label = f"Week {week_num} ({start_str} {str(getdate(actual_week_start).year)[-2:]} - {end_str} {year_short})"
				else:
					label = f"Week {week_num} ({start_str} - {end_str} {year_short})"
				
				weeks_info.append((label, week_key))
		
		# Move to next week
		current_week_start = next_week_start
	
	# Sort by year and week number
	weeks_info.sort(key=lambda x: (int(x[1].split('_')[1]), int(x[1].split('_')[2])))
	
	return weeks_info
