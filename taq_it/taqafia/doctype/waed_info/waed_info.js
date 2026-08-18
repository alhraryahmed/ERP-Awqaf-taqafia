frappe.ui.form.on("waed_info", {
    refresh(frm) {
        add_print_menu(frm);
    },
    agee(frm) {
        if (frm.doc.agee && cint(frm.doc.agee) < 25) {
            frappe.msgprint({
                title: __("العمر غير صحيح"),
                indicator: "red",
                message: __("يجب أن يكون العمر 25 سنة أو أكثر.")
            });

            frm.set_value("agee", null);
        }
    },

    validate(frm) {
        if (frm.doc.agee && cint(frm.doc.agee) < 25) {
            frappe.throw({
                title: __("لا يمكن الحفظ"),
                message: __("يجب أن يكون العمر 25 سنة أو أكثر.")
            });
        }
    }
});

function add_print_menu(frm) {

    const ALLOWED_STATUSES = [
        "Failed Oral",
        "Failed Written",
        "Passed the Written Exam",
        "Approved"
    ];

    if (!ALLOWED_STATUSES.includes(frm.doc.waed_status)) {
        return;
    }

    frappe.call({
        method: "taq_it.api.get_print_actions",

        callback(r) {

            if (!r.message || !r.message.length) {
                return;
            }

            r.message.forEach(action => {

                frm.add_custom_button(
                    __(action.title),
                    () => open_print(frm, action),
                    __("طباعة")
                );

            });

        }

    });

}

function open_print(frm, action) {

    frappe.call({

        method: "taq_it.api.get_print_url",

        args: {
            source_doctype: frm.doctype,
            source_name: frm.doc.name,
            target_doctype: action.target_doctype,
            print_format: action.print_format
        },

        freeze: true,
        freeze_message: __("جاري فتح صفحة الطباعة..."),

        callback(r) {

            if (!r.message) {
                return;
            }

            window.open(r.message, "_blank");

        }

    });

}