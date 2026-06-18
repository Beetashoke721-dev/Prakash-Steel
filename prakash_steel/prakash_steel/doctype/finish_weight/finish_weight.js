frappe.ui.form.on("Finish Weight", {
	billet_cutting_id: function(frm) {
		set_finish_weight_from_billet_cutting(frm).then(function () {
			return calculate_finish_pcs_from_hourly_production(frm);
		}).then(function() {
			_set_per_pcs_weight(frm);
			fetch_colour_code_from_grade(frm);
			calculate_burning_loss_per(frm);
		});
	},
	item_code: function(frm) {
		// Wait for grade to be fetched from item_code, then fetch colour_code
		setTimeout(function() {
			fetch_colour_code_from_grade(frm);
		}, 500);
	},
	grade: function(frm) {
		fetch_colour_code_from_grade(frm);
	},
	finish_weight: function(frm) {
		calculate_finish_pcs_from_hourly_production(frm).then(function() {
			_set_per_pcs_weight(frm);
			calculate_burning_loss_per(frm);
		});
	},
	finish_pcs: function(frm) {
		_set_per_pcs_weight(frm);
	},
	refresh: function(frm) {
		// Only recalculate for new unsaved docs to avoid marking the form dirty.
		if (frm.is_new() && frm.doc.billet_cutting_id) {
			set_finish_weight_from_billet_cutting(frm).then(function () {
				return calculate_finish_pcs_from_hourly_production(frm);
			}).then(function() {
				_set_per_pcs_weight(frm);
				calculate_burning_loss_per(frm);
			});
		}
	},
	melting_weight: function(frm) {
		calculate_burning_loss_per(frm);
	},
	total_miss_ingot_weight: function(frm) {
		calculate_burning_loss_per(frm);
	}
});

frappe.ui.form.on("Finish Weight Item", {
	finish_weight: function(frm, cdt, cdn) {
		calculate_fg_weight(frm, cdt, cdn);
	},
	finish_pcs: function(frm, cdt, cdn) {
		calculate_fg_weight(frm, cdt, cdn);
	}
});

function _set_per_pcs_weight(frm) {
	if (frm.doc.finish_weight && frm.doc.finish_pcs && frm.doc.finish_pcs > 0) {
		frm.set_value("fg_per_pcs_weight", Math.round((frm.doc.finish_weight / frm.doc.finish_pcs) * 100) / 100);
	} else {
		frm.set_value("fg_per_pcs_weight", 0);
	}
}

function calculate_finish_pcs_from_hourly_production(frm) {
	if (!frm.doc.billet_cutting_id) {
		frm.set_value("finish_pcs", 0);
		frm.set_value("total_miss_roll_pcs", 0);
		frm.set_value("total_miss_ingot_pcs", 0);
		frm.set_value("total_miss_roll_weight", 0);
		frm.set_value("total_miss_ingot_weight", 0);
		frm.set_value("item_code", "");
		return Promise.resolve();
	}

	return frappe.db.get_list("Hourly Production", {
		filters: {
			billet_cutting_id: frm.doc.billet_cutting_id,
			docstatus: ["<", 2]
		},
		fields: ["finish_item_pcs", "finish_item", "name", "production_date", "time_from",
			"miss_roll_pcs", "miss_ingot_pcs", "miss_roll_weight", "miss_ingot__billet_weight"],
		order_by: "production_date asc, time_from asc, creation asc"
	}).then(function(docs) {
		let total_finish_pcs = 0;
		let total_miss_roll_pcs = 0;
		let total_miss_ingot_pcs = 0;
		let total_miss_roll_weight = 0;
		let total_miss_ingot_weight = 0;
		let first_doc_finish_item = docs && docs.length > 0 ? docs[0].finish_item : null;

		(docs || []).forEach(function(doc) {
			total_finish_pcs      += parseInt(doc.finish_item_pcs) || 0;
			total_miss_roll_pcs   += parseInt(doc.miss_roll_pcs)   || 0;
			total_miss_ingot_pcs  += parseInt(doc.miss_ingot_pcs)  || 0;
			// Weight fields use parseFloat to preserve decimals
			total_miss_roll_weight   += parseFloat(doc.miss_roll_weight)          || 0;
			total_miss_ingot_weight  += parseFloat(doc.miss_ingot__billet_weight) || 0;
		});

		if (first_doc_finish_item) {
			frm.set_value("item_code", first_doc_finish_item).then(function() {
				setTimeout(function() { fetch_colour_code_from_grade(frm); }, 500);
			});
		} else {
			frm.set_value("item_code", "");
		}

		frm.set_value("finish_pcs",             total_finish_pcs);
		frm.set_value("total_miss_roll_pcs",    total_miss_roll_pcs);
		frm.set_value("total_miss_ingot_pcs",   total_miss_ingot_pcs);
		frm.set_value("total_miss_roll_weight",  total_miss_roll_weight);
		frm.set_value("total_miss_ingot_weight", total_miss_ingot_weight);
		return Promise.resolve();
	}).catch(function(error) {
		console.error("Error calculating totals from Hourly Production:", error);
		frm.set_value("finish_pcs", 0);
		frm.set_value("total_miss_roll_pcs", 0);
		frm.set_value("total_miss_ingot_pcs", 0);
		frm.set_value("total_miss_roll_weight", 0);
		frm.set_value("total_miss_ingot_weight", 0);
		frm.set_value("item_code", "");
		return Promise.reject(error);
	});
}

function set_finish_weight_from_billet_cutting(frm) {
	if (!frm.doc.billet_cutting_id) {
		return Promise.resolve();
	}
	return frappe.db.get_value(
		"Billet Cutting",
		frm.doc.billet_cutting_id,
		["billet_weight", "miss_billet_weight"]
	).then(function(r) {
		const bc = (r && r.message) ? r.message : {};
		const total = (parseFloat(bc.billet_weight) || 0) + (parseFloat(bc.miss_billet_weight) || 0);
		frm.set_value("billet_weight", total);
		return Promise.resolve();
	});
}

function calculate_fg_weight(_frm, cdt, cdn) {
	let row = frappe.get_doc(cdt, cdn);
	if (row.finish_weight && row.finish_pcs) {
		frappe.model.set_value(cdt, cdn, "fg_per_pcs_weight", Math.round((row.finish_weight / row.finish_pcs) * 100) / 100);
	} else {
		frappe.model.set_value(cdt, cdn, "fg_per_pcs_weight", 0);
	}
}

function fetch_colour_code_from_grade(frm) {
	if (!frm.doc.grade) return Promise.resolve();

	return frappe.db.get_list("Item Grade wise Colour Code", {
		filters: { item_grade: frm.doc.grade },
		fields: ["colour_code"],
		limit: 1
	}).then(function(docs) {
		if (docs && docs.length > 0) {
			frm.set_value("colour_code", docs[0].colour_code);
		}
		return Promise.resolve();
	}).catch(function(error) {
		console.error("Error fetching colour_code from grade:", error);
		return Promise.reject(error);
	});
}

function calculate_burning_loss_per(frm) {
	if (!frm.doc.billet_cutting_id) {
		frm.set_value("burning_loss_per", 0);
		return Promise.resolve();
	}

	return frappe.db.get_doc("Billet Cutting", frm.doc.billet_cutting_id).then(function(bc) {
		const billet_weight      = parseFloat(bc.billet_weight) || 0;
		const miss_billet_weight = parseFloat(bc.miss_billet_weight) || 0;
		const finish_weight      = parseFloat(frm.doc.finish_weight) || 0;

		frm.set_value("billet_weight", miss_billet_weight > 0 ? billet_weight + miss_billet_weight : billet_weight);

		if (billet_weight > 0) {
			const burning_loss_per = Math.round(
				((billet_weight - miss_billet_weight - finish_weight) / billet_weight) * 10000
			) / 100;
			frm.set_value("burning_loss_per", burning_loss_per);
		} else {
			frm.set_value("burning_loss_per", 0);
		}
		return Promise.resolve();
	}).catch(function(error) {
		console.error("Error calculating burning_loss_per:", error);
		frm.set_value("burning_loss_per", 0);
		return Promise.reject(error);
	});
}
