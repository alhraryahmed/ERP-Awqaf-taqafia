const GRADING_ROLE = "مشرف رصد الامتحانات";
const APPROVAL_ROLE = "معتمد نتائج الامتحانات";

frappe.ui.form.on("exam_grading_tool", {
    refresh(frm) {
        setup_role_actions(frm);
        set_default_stage_options(frm);
        render_empty_state(frm);
    },

    exam_group_date(frm) {
        set_default_stage_options(frm);
        load_group_exam_form(frm);

        if (frm.doc.exam_group_date && frm.doc.grading_stage) {
            load_preachers(frm);
        } else {
            render_empty_state(frm);
        }
    },

    grading_stage(frm) {
        load_group_exam_form(frm);

        if (frm.doc.exam_group_date && frm.doc.grading_stage) {
            load_preachers(frm);
        } else {
            render_empty_state(frm);
        }
    },

    load_preachers(frm) {
        load_preachers(frm);
    },

    save_grades(frm) {
        save_grades(frm);
    },

    approve_stage(frm) {
        approve_stage(frm); s
    }
});

function setup_role_actions(frm) {
    frm.toggle_display("save_grades", can_grade());
    frm.toggle_display("approve_stage", can_approve());
}

function can_grade() {
    return frappe.user.has_role("System Manager") || frappe.user.has_role(GRADING_ROLE);
}

function can_approve() {
    return frappe.user.has_role("System Manager") || frappe.user.has_role(APPROVAL_ROLE);
}

function get_stage(frm) {
    return frm.doc.grading_stage || "Written";
}

function set_default_stage_options(frm) {
    frm.set_df_property("grading_stage", "options", "Written\nOral");
}

function load_group_exam_form(frm) {
    if (!frm.doc.exam_group_date) {
        frm.set_value("loaded_exam_form", "");
        return;
    }

    frappe.call({
        method: "taq_it.taqafia.doctype.exam_group_date.exam_group_date.get_group_exam_forms",
        args: {
            exam_group_date: frm.doc.exam_group_date
        },
        callback(r) {
            const forms = r.message || {};
            const exam_form = get_stage(frm) === "Written" ? forms.written_exam : forms.oral_exam;
            frm.set_value("loaded_exam_form", exam_form || "");
        }
    });
}

function load_preachers(frm) {
    if (!frm.doc.exam_group_date) {
        frappe.msgprint("اختر جلسة الامتحان أولا");
        return;
    }

    frappe.call({
        method: "taq_it.taqafia.doctype.exam_grading_tool.exam_grading_tool.load_preachers",
        args: {
            exam_group_date: frm.doc.exam_group_date,
            grading_stage: get_stage(frm)
        },
        freeze: true,
        freeze_message: "جاري تحميل الوعاظ...",
        callback(r) {
            frm.__grading_data = r.message || { columns: [], rows: [] };
            frm.set_value("loaded_exam_form", frm.__grading_data.exam_form || "");
            render_grading_table(frm);

            const count = frm.__grading_data.rows.length;
            frappe.show_alert({
                message: `تم تحميل ${count} واعظ`,
                indicator: count ? "green" : "orange"
            });
        }
    });
}

function save_grades(frm) {
    if (!can_grade()) {
        frappe.msgprint("ليست لديك صلاحية رصد الدرجات");
        return;
    }

    if (!frm.doc.exam_group_date) {
        frappe.msgprint("اختر جلسة الامتحان أولا");
        return;
    }

    const data = collect_grades(frm);
    if (!data.length) {
        frappe.msgprint("لا توجد درجات لحفظها");
        return;
    }

    frappe.call({
        method: "taq_it.taqafia.doctype.exam_grading_tool.exam_grading_tool.save_grades",
        args: {
            exam_group_date: frm.doc.exam_group_date,
            grading_stage: get_stage(frm),
            rows: data
        },
        freeze: true,
        freeze_message: "جاري حفظ الدرجات...",
        callback(r) {
            const count = ((r.message && r.message.updated) || []).length;
            frappe.show_alert({
                message: `تم حفظ درجات ${count} واعظ`,
                indicator: "green"
            });
            load_preachers(frm);
        }
    });
}

function approve_stage(frm) {
    if (!can_approve()) {
        frappe.msgprint("ليست لديك صلاحية اعتماد النتائج");
        return;
    }

    if (!frm.doc.exam_group_date) {
        frappe.msgprint("اختر جلسة الامتحان أولا");
        return;
    }

    const stage_label = get_stage(frm) === "Written" ? "التحريري" : "الشفوي";
    frappe.confirm(
        `سيتم اعتماد درجات ${stage_label}. بعد الاعتماد لا يمكن تعديل درجات هذه المرحلة. هل تريد المتابعة؟`,
        () => {
            frappe.call({
                method: "taq_it.taqafia.doctype.exam_grading_tool.exam_grading_tool.approve_stage",
                args: {
                    exam_group_date: frm.doc.exam_group_date,
                    grading_stage: get_stage(frm)
                },
                freeze: true,
                freeze_message: "جاري اعتماد المرحلة...",
                callback(r) {
                    const approved = ((r.message && r.message.approved) || []).length;
                    const submitted = ((r.message && r.message.submitted) || []).length;
                    frappe.show_alert({
                        message: `تم اعتماد ${approved} نتيجة${submitted ? ` وإرسال ${submitted}` : ""}`,
                        indicator: "green"
                    });
                    load_preachers(frm);
                }
            });
        }
    );
}

function render_empty_state(frm) {
    frm.__grading_data = null;
    const wrapper = frm.fields_dict.grading_html && frm.fields_dict.grading_html.$wrapper;
    if (!wrapper) return;

    wrapper.html(`
        <div class="text-muted" style="padding: 12px 0;">
            اختر جلسة الامتحان ومرحلة الرصد ثم اضغط تحميل الوعاظ.
        </div>
    `);
}

// خريطة ترجمة نصوص الحالة للعرض فقط (لا تُستخدم في أي مقارنة أو منطق برمجي)
const STATUS_LABELS_AR = {
    "Approved": "معتمد",
    "Pending": "قيد الانتظار",
    "Rejected": "مرفوض",
    "Draft": "مسودة",
    "In Progress": "قيد التنفيذ",
    "Passed": "ناجح",
    "Failed": "راسب",
    "Failed Written": "راسب - تحريري",
    "Failed Oral": "راسب - شفوي",
    "Final Approved": "معتمد نهائيًا",
    "Final Rejected": "مرفوض نهائيًا",
    "Not Graded": "لم يتم الرصد",
    "Graded": "تم الرصد",
    "Submitted": "تم الإرسال",
    "Not Submitted": "لم يتم الإرسال"
};

// دالة عرض فقط: تُرجع الترجمة العربية إن وُجدت، وإلا تُعيد القيمة الأصلية كما هي
function translate_status_label(value) {
    if (!value) return "";
    return STATUS_LABELS_AR[value] || value;
}

function render_grading_table(frm) {
    const wrapper = frm.fields_dict.grading_html.$wrapper;
    const data = frm.__grading_data || { columns: [], rows: [] };
    const scores_disabled = !can_grade();
    const stage_label = get_stage(frm) === "Written" ? "التحريري" : "الشفوي";

    if (!data.rows.length) {
        wrapper.html(`
            <div class="text-muted" style="padding: 12px 0;">
                لا توجد نتائج مؤهلة لرصد ${stage_label} في هذه الجلسة.
            </div>
        `);
        return;
    }

    const aspect_groups = group_columns_by_aspect(data.columns);
    const aspect_colors = ["#f7f9fc", "#ffffff"];

    const aspect_header_row = aspect_groups.map((group, index) => `
        <th class="text-center aspect-header" colspan="${group.columns.length}"
            style="background:${aspect_colors[index % 2]};">
            ${frappe.utils.escape_html(group.aspect || "")}
        </th>
    `).join("");

    const question_header_row = aspect_groups.map((group, index) =>
        group.columns.map((column, col_index) => `
            <th class="text-center question-header ${col_index === 0 ? "group-start" : ""}"
                style="background:${aspect_colors[index % 2]};">
                <div>س${frappe.utils.escape_html(column.question_number || "")}</div>
<small class="text-muted">/${safe_number(column.max_grade)}</small>
            </th>
        `).join("")
    ).join("");

    const rows_html = data.rows.map(row => {
        const questions_by_key = {};
        (row.questions || []).forEach(question => {
            questions_by_key[question.key] = question;
        });

        const is_approved = row.stage_status === "Approved" || row.result_status === "Final Approved";
        const grouped_cells = aspect_groups.map((group, index) =>
            group.columns.map((column, col_index) => {
                const question = questions_by_key[column.key] || {};
                const disabled = scores_disabled || is_approved || !question.name;
                const score_value = question.score === undefined || question.score === null ? 0 : question.score;
                return `
                    <td class="${col_index === 0 ? "group-start" : ""}"
                        style="background:${aspect_colors[index % 2]};">
                        <input
                            class="form-control input-sm grading-score"
                            type="number"
                            min="0"
max="${safe_number(column.max_grade)}"
                            step="0.01"
                            data-result="${frappe.utils.escape_html(row.exam_result)}"
                            data-waed="${frappe.utils.escape_html(row.waed || "")}"
                            data-question="${frappe.utils.escape_html(question.name || "")}"
data-max="${safe_number(column.max_grade)}"
value="${safe_number(score_value)}"
                            ${disabled ? "disabled" : ""}
                        >
                    </td>
                `;
            }).join("")
        ).join("");

        return `
            <tr data-result="${frappe.utils.escape_html(row.exam_result)}">
                <td class="waed-cell">
                    <strong>${frappe.utils.escape_html(row.waed_name || row.waed || "")}</strong>
                </td>
                ${grouped_cells}
                <td class="text-center row-total">${safe_number(row.total_score)}</td>
<td class="text-center">${safe_number(row.max_total)}</td>
                <td class="text-center row-percentage">${frappe.utils.escape_html(format_percentage(row.percentage))}</td>
                <td class="text-center">${frappe.utils.escape_html(translate_status_label(row.stage_status))}</td>
                <td class="text-center">${frappe.utils.escape_html(translate_status_label(row.final_pass_status))}</td>
            </tr>
        `;
    }).join("");

    wrapper.html(`
        <style>
            .grading-table-wrap {
                font-family: "Segoe UI", "Tahoma", "Cairo", sans-serif;
                border: 1px solid #dbe2ea;
                border-radius: 10px;
                overflow: hidden;
            }

            .grading-table-wrap table.grading-table {
                min-width: 1100px;
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                background: #fff;
                font-size: 13px;
            }

            /* ===== General cells ===== */
            .grading-table-wrap th,
            .grading-table-wrap td {
                padding: 12px 10px !important;
                vertical-align: middle !important;
                border-color: #e6eaf0 !important;
                border-bottom: 1px solid #e6eaf0 !important;
                height: 52px;
                box-sizing: border-box;
            }

            /* ===== Header ===== */
            .grading-table-wrap thead th {
                background: #eef2f8;
                color: #24344d;
                font-weight: 600;
                border-bottom: 2px solid #c7d2e0 !important;
                position: sticky;
                top: 0;
                z-index: 3;
            }

            .grading-table-wrap .aspect-header {
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0.2px;
                color: #1f3a63;
                padding: 10px 8px !important;
                border-bottom: 1px solid #d7e0ec !important;
            }

            .grading-table-wrap .question-header {
                font-size: 11.5px;
                line-height: 1.7;
                color: #46536b;
                font-weight: 600;
                top: 40px;
            }

            .grading-table-wrap .question-header div {
                font-weight: 700;
                color: #1f3a63;
            }

            .grading-table-wrap .question-header small {
                font-size: 10.5px;
                color: #8a95a8;
            }

            /* ===== Column separators between aspect groups ===== */
            .grading-table-wrap .group-start {
                border-right: 2px solid #cfd8e3 !important;
            }

            /* ===== First (name) column, sticky ===== */
            .grading-table-wrap .waed-cell {
                position: sticky;
                right: 0;
                background: #fff;
                min-width: 220px;
                max-width: 260px;
                text-align: right;
                box-shadow: -3px 0 6px rgba(20, 30, 50, 0.05);
                z-index: 1;
                color: #1c2b3f;
                font-weight: 600;
            }

            .grading-table-wrap thead th:first-child {
                position: sticky;
                right: 0;
                top: 0;
                background: #eef2f8;
                z-index: 4;
                min-width: 220px;
                max-width: 260px;
                text-align: right;
            }

            /* ===== Body rows ===== */
            .grading-table-wrap tbody tr {
                transition: background-color 0.12s ease-in-out;
            }

            .grading-table-wrap tbody tr:nth-child(even) td:not(.group-start):not(.waed-cell) {
                background-image: none;
            }

            .grading-table-wrap tbody tr:hover td {
                background-color: #f2f6fc !important;
            }

            .grading-table-wrap tbody tr:hover .waed-cell {
                background-color: #f2f6fc !important;
            }

            .grading-table-wrap tbody tr:focus-within td {
                background-color: #eaf1fb !important;
            }

            .grading-table-wrap tbody tr:focus-within .waed-cell {
                background-color: #eaf1fb !important;
            }

            /* ===== Score input (highlighted) ===== */
            .grading-table-wrap .grading-score {
                width: 62px;
                margin: 0 auto;
                text-align: center;
                padding: 6px 4px !important;
                border: 1px solid #c7d2e0;
                border-radius: 6px;
                font-weight: 600;
                color: #1f3a63;
                background: #fbfcfe;
                transition: border-color 0.12s ease-in-out, box-shadow 0.12s ease-in-out;
            }

            .grading-table-wrap .grading-score:hover:not(:disabled) {
                border-color: #9fb3cf;
            }

            .grading-table-wrap .grading-score:focus {
                outline: none;
                border-color: #3a6bc4;
                box-shadow: 0 0 0 3px rgba(58, 107, 196, 0.15);
                background: #ffffff;
            }

            .grading-table-wrap .grading-score:disabled {
                background: #f1f3f6;
                color: #9aa4b2;
                border-color: #e3e7ee;
            }

            /* ===== Summary columns ===== */
            .grading-table-wrap .row-total {
                font-weight: 700;
                color: #1f3a63;
                background: #f7faff;
            }

            .grading-table-wrap .row-percentage {
                font-weight: 700;
                color: #21633f;
            }

            /* ===== Scrollable wrapper ===== */
            .grading-table-wrap .table-scroll {
                overflow-x: auto;
                max-height: 70vh;
                overflow-y: auto;
            }

            @media (max-width: 768px) {
                .grading-table-wrap th,
                .grading-table-wrap td {
                    padding: 8px 6px !important;
                    font-size: 12px;
                }
                .grading-table-wrap .grading-score {
                    width: 52px;
                }
            }
        </style>
        <div class="text-muted" style="margin: 10px 0; font-weight: 600; color: #46536b;">
            المرحلة: ${frappe.utils.escape_html(stage_label)}
        </div>
        <div class="grading-table-wrap">
            <div class="table-scroll">
                <table class="table table-bordered table-hover grading-table">
                    <thead>
                        <tr>
                            <th rowspan="2">الواعظ</th>
                            ${aspect_header_row}
                            <th rowspan="2" class="text-center">المجموع</th>
                            <th rowspan="2" class="text-center">الدرجة الكبرى</th>
                            <th rowspan="2" class="text-center">النسبة</th>
                            <th rowspan="2" class="text-center">حالة المرحلة</th>
                            <th rowspan="2" class="text-center">النتيجة النهائية</th>
                        </tr>
                        <tr>${question_header_row}</tr>
                    </thead>
                    <tbody>${rows_html}</tbody>
                </table>
            </div>
        </div>
    `);
    bind_score_validation(wrapper);
}
function bind_score_validation(wrapper) {
    wrapper.off("change.gradingValidation").on("change.gradingValidation", ".grading-score", function () {
        const input = $(this);
        const max = flt(input.data("max"));
        const min = 0;
        let value = flt(input.val());

        if (input.val() === "") {
            return; // اترك الحقل فارغا كما هو، بدون رسالة خطأ
        }

        if (value > max) {
            frappe.msgprint({
                title: "خطأ في الدرجة",
                message: `أعلى درجة لهذا السؤال هي ${max}`,
                indicator: "red"
            });
            input.val("");
            input.trigger("focus");
            return;
        }

        if (value < min) {
            frappe.msgprint({
                title: "خطأ في الدرجة",
                message: `لا يمكن إدخال درجة أقل من ${min}`,
                indicator: "red"
            });
            input.val("");
            input.trigger("focus");
            return;
        }
    });
}

function group_columns_by_aspect(columns) {
    const groups = [];
    const group_map = {};

    (columns || []).forEach(column => {
        const aspect = column.aspect || "";
        if (!group_map[aspect]) {
            group_map[aspect] = {
                aspect,
                columns: []
            };
            groups.push(group_map[aspect]);
        }

        group_map[aspect].columns.push(column);
    });

    return groups;
}

function collect_grades(frm) {
    const wrapper = frm.fields_dict.grading_html.$wrapper;
    const rows = {};

    wrapper.find(".grading-score:not(:disabled)").each(function () {
        const input = $(this);
        const result = input.data("result");
        const waed = input.data("waed");
        const question = input.data("question");

        if ((!result && !waed) || !question) return;

        const row_key = result || waed;
        if (!rows[row_key]) {
            rows[row_key] = {
                exam_result: result,
                waed,
                scores: {}
            };
        }

        rows[row_key].scores[question] = input.val();
    });

    return Object.values(rows);
}

function format_percentage(value) {
    const percentage = flt(value);
    return `${percentage.toFixed(2)}%`;
}
function safe_number(value) {
    if (value === undefined || value === null || value === "") {
        return "0";
    }
    return String(value);
}
