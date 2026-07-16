// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.ui.form.on("Unsecured Loans and Transaction", {

    onload: function (frm) {
        load_unsecured_loan_options(frm);
    },

    refresh: function (frm) {
        load_unsecured_loan_options(frm);
    },

    unsecured_loan: function (frm) {
        frm.__unsecured_loan_touched = true;
    },

    financial_year: function (frm) {
        if (!frm.doc.financial_year) {
            frm.set_value("from_date", "");
            frm.set_value("to_date", "");
            return;
        }
        // Automatically fetch start and end dates based on the Fiscal Year
        frappe.db.get_doc("Fiscal Year", frm.doc.financial_year).then(r => {
            frm.set_value("from_date", r.year_start_date);
            frm.set_value("to_date", r.year_end_date);
        });
    }

});

// ----------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------

/**
 * Loads and groups Account options for the 'unsecured_loan' field
 * based on specific parent accounts, plus extra Axis Bank accounts.
 */
async function load_unsecured_loan_options(frm) {
	var EXTRA_UNSECURED_LOAN_ACCOUNTS = [
		"Axis Bank (Loan for Office Property 12 Floor) - PSPL",
		"Axis Bank (Loan for Office Property 14 Floor) - PSPL",
		"Axis Bank CC A/c - PSPL",
		"Axis Bank Current A/c - PSPL",
	];

	var options = [""];

	try {
		var result = await frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Account",
				filters: [
					[
						"parent_account",
						"in",
						[
							"Loan From Director - PSPL",
							"Loan From Shareholders - PSPL",
							"Unsecured Loan - PSPL",
						],
					],
					["is_group", "=", 0],
				],
				fields: ["name", "account_name", "parent_account"],
				order_by: "parent_account asc, account_name asc",
				limit: 500,
			},
		});

		var accounts = (result && result.message) || [];
		accounts
			.filter(function (a) {
				return a.parent_account === "Loan From Director - PSPL";
			})
			.forEach(function (acc) {
				options.push(acc.name);
			});
		accounts
			.filter(function (a) {
				return a.parent_account === "Loan From Shareholders - PSPL";
			})
			.forEach(function (acc) {
				options.push(acc.name);
			});
		accounts
			.filter(function (a) {
				return a.parent_account === "Unsecured Loan - PSPL";
			})
			.forEach(function (acc) {
				options.push(acc.name);
			});
	} catch (err) {
		console.error("Unsecured Loan options load error:", err);
	}

	EXTRA_UNSECURED_LOAN_ACCOUNTS.forEach(function (name) {
		if (options.indexOf(name) === -1) {
			options.push(name);
		}
	});

	frm.set_df_property("unsecured_loan", "options", options.join("\n"));

	// Select fields auto-pick the first option; keep new forms blank until user chooses
	if (frm.is_new() && !frm.__unsecured_loan_touched) {
		frm.doc.unsecured_loan = "";
	}

	frm.refresh_field("unsecured_loan");
}
