"""Fix NULL values in custom_decoupled_lead_time before schema migration"""

import frappe


def execute():
	"""Update NULL values in custom_decoupled_lead_time to 0 before schema change"""
	try:
		# Check if column exists using information_schema
		db_name = frappe.conf.db_name
		column_exists = frappe.db.sql(
			"""
			SELECT COUNT(*) 
			FROM information_schema.COLUMNS 
			WHERE TABLE_SCHEMA = %s 
			AND TABLE_NAME = 'tabItem' 
			AND COLUMN_NAME = 'custom_decoupled_lead_time'
		""",
			(db_name,),
		)

		if column_exists and column_exists[0][0] > 0:
			# Column exists - update NULL values
			frappe.db.sql("""
				UPDATE `tabItem`
				SET `custom_decoupled_lead_time` = 0
				WHERE `custom_decoupled_lead_time` IS NULL
			""")
			frappe.db.commit()
	except Exception:
		# Column doesn't exist yet or table doesn't exist - that's fine, skip
		pass
