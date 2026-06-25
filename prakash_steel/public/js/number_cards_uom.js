// Override Number Card to show UOM after value
// UOM is configured via "Number Card UOM Setting" DocType

(function () {
    // Cache for UOM settings (keyed by Number Card name)
    let uom_settings = {};
    let settings_loaded = false;

    // Fetch UOM settings from server
    function load_uom_settings(callback) {
        if (settings_loaded) {
            callback && callback();
            return;
        }

        frappe.call({
            method: "prakash_steel.api.number_card_uom.get_all_uom_settings",
            async: true,
            callback: function (r) {
                uom_settings = r.message || {};
                settings_loaded = true;
                callback && callback();
            }
        });
    }

    function append_uom_to_number_cards() {
        if (!settings_loaded) return;

        $(".number-widget-box").each(function () {
            const $widget = $(this);
            const widget_name = $widget.attr("data-widget-name");
            const widget_label = $widget.find(".ellipsis").first().text().trim();

            // Skip if already processed
            if ($widget.attr("data-uom-done") === "true") return;

            // Try to find UOM by widget name first, then by label
            let uom = uom_settings[widget_name] || uom_settings[widget_label];

            if (!uom) return;

            // Find the value element
            const $value = $widget.find(".number");
            const current_text = $value.text().trim();

            // Skip if value not loaded yet
            if (!$value.length || !current_text) return;

            // Append UOM if not already there
            if (!current_text.endsWith(uom)) {
                $value.text(current_text + " " + uom);
                $widget.attr("data-uom-done", "true");
            }
        });
    }

    // Polling function - keeps checking for new cards
    function startPolling() {
        setInterval(function () {
            if (settings_loaded) {
                append_uom_to_number_cards();
            }
        }, 1000);
    }

    // Start when DOM is ready
    $(document).ready(function () {
        // Load settings then start polling
        load_uom_settings(function () {
            append_uom_to_number_cards();
            startPolling();
        });

        // Reload settings and reset on page change
        $(document).on("page-change", function () {
            $(".number-widget-box").removeAttr("data-uom-done");
            settings_loaded = false;
            load_uom_settings();
        });
    });
})();
