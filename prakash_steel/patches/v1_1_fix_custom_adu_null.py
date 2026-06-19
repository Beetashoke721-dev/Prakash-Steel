"""Set NULL Item.custom_adu values to 0 so ADU starts at 0 for all items."""

import frappe


def execute() -> tuple[list, list]:
	"""Update NULL values in custom_adu to 0 if the column exists."""
	try:
		db_name = frappe.conf.db_name
		column_exists = frappe.db.sql(
			"""
			SELECT COUNT(*)
			FROM information_schema.COLUMNS
			WHERE TABLE_SCHEMA = %s
			  AND TABLE_NAME = 'tabItem'
			  AND COLUMN_NAME = 'custom_adu'
			""",
			(db_name,),
		)

		if column_exists and column_exists[0][0] > 0:
			frappe.db.sql(
				"""
				UPDATE `tabItem`
				SET `custom_adu` = 0
				WHERE `custom_adu` IS NULL
				"""
			)
			frappe.db.commit()
	except Exception:
		# If the column or table doesn't exist yet, just skip quietly
		pass








