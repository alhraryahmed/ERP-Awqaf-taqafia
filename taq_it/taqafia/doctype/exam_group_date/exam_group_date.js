frappe.ui.form.on("exam-group-data-child", {

    full_name(frm, cdt, cdn) {

        let row = locals[cdt][cdn];

        if (!row.full_name) {
            return;
        }

        let duplicates = (frm.doc.waed_info_to_exam || []).filter(r =>
            r.full_name && r.full_name === row.full_name
        );

        if (duplicates.length > 1) {

            frappe.msgprint({
                title: __("واعظ مكرر"),
                indicator: "red",
                message: __("هذا الواعظ مضاف مسبقاً إلى قائمة الامتحان.")
            });

            frappe.model.set_value(
                cdt,
                cdn,
                "full_name",
                ""
            );
        }
    }

});
frappe.ui.form.on("exam_group_date", {

    refresh(frm) {

        frm.set_query("full_name", "waed_info_to_exam", function() {

            let selected_waeds = (frm.doc.waed_info_to_exam || [])
                .map(row => row.full_name)
                .filter(Boolean);

            return {
                filters: {
                    waed_status: "Scheduling an appointment",
                    name: ["not in", selected_waeds]
                }
            };

        });

    }

});