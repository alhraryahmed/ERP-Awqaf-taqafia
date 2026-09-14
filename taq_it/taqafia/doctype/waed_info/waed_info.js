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
    const current_status = (frm.doc.waed_status || "").trim().toLowerCase();

    const ALLOWED_STATUSES = [
        "failed oral",
        "failed written",
        "passed the written exam",
        "passed",
        "approved",
        "ongoing",
        "rejected",
        "completed"
    ];

    if (!ALLOWED_STATUSES.includes(current_status)) {
        return;
    }

    frappe.call({
        method: "taq_it.api.get_print_actions",
        callback(r) {
            let actions = r.message || [];
            if (!actions.length) {
                // Fallback default print buttons
                actions = [
                    {
                        title: "بيانات الواعظ",
                        target_doctype: "waed_info",
                        print_format: "waez_data_doc"
                    },
                    {
                        title: "نتيجة الامتحان",
                        target_doctype: "exam_result",
                        print_format: "result"
                    }
                ];
            }

            actions.forEach(action => {
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
        freeze_message: __("جاري تحضير الطباعة..."),
        callback(r) {
            if (!r.message) {
                return;
            }

            let print_url = r.message;
            if (print_url.includes("trigger_print=0")) {
                print_url = print_url.replace("trigger_print=0", "trigger_print=1");
            } else if (!print_url.includes("trigger_print=1")) {
                print_url += "&trigger_print=1";
            }

            // Direct in-page browser print preview via hidden iframe
            let iframe = document.getElementById("waed-silent-print-frame");
            if (!iframe) {
                iframe = document.createElement("iframe");
                iframe.id = "waed-silent-print-frame";
                iframe.style.position = "fixed";
                iframe.style.right = "0";
                iframe.style.bottom = "0";
                iframe.style.width = "0";
                iframe.style.height = "0";
                iframe.style.border = "0";
                iframe.style.opacity = "0";
                iframe.style.pointerEvents = "none";
                document.body.appendChild(iframe);
            }

            iframe.src = print_url;
        }
    });
}