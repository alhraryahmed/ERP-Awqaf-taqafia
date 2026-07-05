let sync_timeout;

frappe.ui.form.on("exam_form", {
    refresh(frm) {
        frm.__syncing = false;
        frm.__loaded = true;

        frm.set_query("aspect", "aspects", function() {
            return {
                query: "taq_it.taqafia.doctype.exam_form.exam_form.get_filtered_program_aspects",
                filters: {
                    program_name: frm.doc.program
                }
            };
        });

        (frm.doc.aspects || []).forEach(row => {
            row._previous_aspect = row.aspect;
        });
    },

    aspects_add(frm) {
        schedule_sync(frm);
    },

    aspects_remove(frm) {
        trigger_sync(frm);
    },

    program(frm) {
        frm.clear_table("aspects");
        frm.clear_table("questions");
        frm.refresh_field("aspects");
        frm.refresh_field("questions");
    },

    max_score(frm) {
        validate_aspects_max_score(frm);
    },

    validate(frm) {
        validate_aspects_max_score(frm, true);
    }
});

// =========================
// Child Table Events
// =========================
frappe.ui.form.on("exam_form_aspect", {
    aspect(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (frm.__syncing) {
            return;
        }

        if (!frm.doc.program) {
            frappe.msgprint("اختر البرنامج أولاً");
            frappe.model.set_value(cdt, cdn, "aspect", "");
            return;
        }

        let duplicates = (frm.doc.aspects || []).filter(r =>
            r.aspect && row.aspect && r.aspect === row.aspect
        );

        if (duplicates.length > 1) {
            frappe.msgprint("هذا الـ Aspect مضاف مسبقاً");
            frappe.model.set_value(cdt, cdn, "aspect", "");
            return;
        }

        let old_aspect = row._previous_aspect;

        if (old_aspect && old_aspect !== row.aspect) {
            let has_grades = (frm.doc.questions || []).some(
                q => q.aspect === old_aspect && q.max_grade
            );

            if (has_grades) {
                frappe.confirm(
                    "تغيير هذا الجانب سيؤدي لفقدان الدرجات المُدخلة مسبقاً لأسئلته، متابعة؟",
                    () => {
                        row._previous_aspect = row.aspect;
                        schedule_sync(frm);
                    },
                    () => {
                        frappe.model.set_value(cdt, cdn, "aspect", old_aspect);
                    }
                );
                return;
            }
        }

        row._previous_aspect = row.aspect;
        schedule_sync(frm);
    },

    question_count(frm, cdt, cdn) {
        schedule_sync(frm);
    },

    max_grade(frm) {
        validate_aspects_max_score(frm);
    }
});

function validate_aspects_max_score(frm, block_save = false) {
    if (!frm.doc.max_score) return;

    const aspects_total = (frm.doc.aspects || []).reduce((total, row) => {
        return total + flt(row.max_grade);
    }, 0);

    if (aspects_total > flt(frm.doc.max_score)) {
        frappe.msgprint(
            `Total aspects max grades (${aspects_total}) cannot exceed exam Max Score (${frm.doc.max_score}).`
        );
        if (block_save) {
            frappe.validated = false;
        }
    }
}

// =========================
// Debounce Sync
// =========================
function schedule_sync(frm) {
    if (frm.__syncing || !frm.__loaded) return;

    clearTimeout(sync_timeout);

    sync_timeout = setTimeout(() => {
        trigger_sync(frm);
    }, 500);
}

// =========================
// Sync Function
// =========================
function trigger_sync(frm) {
    if (frm.__syncing) return;

    frm.__syncing = true;

    frappe.call({
        method: "taq_it.taqafia.doctype.exam_form.exam_form.sync_exam_form",
        args: {
            doc: frm.doc
        },

        callback(r) {
            if (!r.message) return;

            frappe.model.clear_table(frm.doc, "questions");

            (r.message.questions || []).forEach(q => {
                let row = frappe.model.add_child(
                    frm.doc,
                    "exam_form_question",
                    "questions"
                );

                row.aspect = q.aspect;
                row.question_number = q.question_number;
                row.max_grade = q.max_grade;
            });

            frm.refresh_field("questions");
        },

        always() {
            frm.__syncing = false;
        }
    });
}
