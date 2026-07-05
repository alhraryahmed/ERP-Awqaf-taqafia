frappe.ui.form.on("waed_info", {
    refresh(frm) {
        add_exam_result_button(frm);
    }
});

function add_exam_result_button(frm) {
    const ALLOWED_STATUSES = [
        "Failed Oral",
        "Failed Written",
        "Passed the Written Exam",
        "Approved"
    ];

    if (!ALLOWED_STATUSES.includes(frm.doc.waed_status)) {
        return;
    }

    frm.add_custom_button("كشف درجات", () => {
        generate_score_sheet(frm);
    });
}

function generate_score_sheet(frm) {
    frappe.call({
        method: "taq_it.taqafia.doctype.exam_result.exam_result.generate_score_sheet",
        args: {
            waed: frm.doc.name
        },
        freeze: true,
        freeze_message: "جاري إنشاء كشف الدرجات...",
        callback(r) {
            if (!r.message || !r.message.file_url) return;

            frappe.show_alert({
                message: "تم إنشاء كشف الدرجات وإرفاقه بنجاح",
                indicator: "green"
            });

            frm.reload_doc();
            window.open(r.message.file_url, "_blank");
        }
    });
}