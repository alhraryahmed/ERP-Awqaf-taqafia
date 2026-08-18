const GRADING_ROLE = "مشرف رصد الامتحانات";
const APPROVAL_ROLE = "معتمد نتائج الامتحانات";

frappe.pages['exam_tool'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'اداة رصد الدرجات',
		single_column: true
	});
	    new ExamGradingTool(wrapper);

}

class ExamGradingTool {

    constructor(wrapper) {

        this.wrapper = $(wrapper);

        this.page = this.wrapper.find(".layout-main-section");

        this.exam_group_date = null;

        this.grading_stage = "Written";

        this.loaded_exam_form = null;

        this.grading_data = {
            columns: [],
            rows: []
        };

        this.init();

    }


    init() {

        this.setup_controls();

        this.bind_events();

        this.update_permissions();

        this.update_summary();

    }


    setup_controls() {

        const date_parent =
            this.wrapper.find(
                '[data-field="exam_group_date"]'
            );


        const stage_parent =
            this.wrapper.find(
                '[data-field="grading_stage"]'
            );


        this.exam_group_date_control =
            frappe.ui.form.make_control({

                parent: date_parent,

                df: {

                    fieldname:
                        "exam_group_date",

                    fieldtype:
                        "Link",

                    options:
                        "exam_group_date",

                    label:
                        "جلسة الامتحان",

                    reqd: 1

                },

                render_input: true

            });


        this.exam_group_date_control.make();


        this.grading_stage_control =
            frappe.ui.form.make_control({

                parent: stage_parent,

                df: {

                    fieldname:
                        "grading_stage",

                    fieldtype:
                        "Select",

                    label:
                        "مرحلة الرصد",

                    options:
                        "Written\nOral",

                    default:
                        "Written"

                },

                render_input: true

            });


        this.grading_stage_control.make();


        this.grading_stage_control.set_value(
            "Written"
        );


        this.exam_group_date_control.$input.on(
            "change",
            () => {

                this.exam_group_date =
                    this.exam_group_date_control.get_value();

                this.loaded_exam_form = null;

                this.load_group_exam_form();

                this.reset_table();

            }
        );


        this.grading_stage_control.$input.on(
            "change",
            () => {

                this.grading_stage =
                    this.grading_stage_control.get_value();

                this.loaded_exam_form = null;

                this.load_group_exam_form();

                this.reset_table();

            }
        );

    }


    bind_events() {

        this.wrapper.on(
            "click",
            ".eg-load-btn",
            () => {

                this.load_preachers();

            }
        );


        this.wrapper.on(
            "click",
            ".eg-save-btn",
            () => {

                this.save_grades();

            }
        );


        this.wrapper.on(
            "click",
            ".eg-approve-btn",
            () => {

                this.approve_stage();

            }
        );

    }


    can_grade() {

        return (

            frappe.user.has_role(
                "System Manager"
            )

            ||

            frappe.user.has_role(
                GRADING_ROLE
            )

        );

    }


    can_approve() {

        return (

            frappe.user.has_role(
                "System Manager"
            )

            ||

            frappe.user.has_role(
                APPROVAL_ROLE
            )

        );

    }


    update_permissions() {

        this.wrapper
            .find(".eg-save-btn")
            .toggle(
                this.can_grade()
            );


        this.wrapper
            .find(".eg-approve-btn")
            .toggle(
                this.can_approve()
            );

    }


    get_stage() {

        return (
            this.grading_stage ||
            "Written"
        );

    }


    get_stage_label() {

        return this.get_stage() === "Written"
            ? "التحريري"
            : "الشفوي";

    }


    load_group_exam_form() {

        if (!this.exam_group_date) {

            this.loaded_exam_form = null;

            this.update_summary();

            return;

        }


        frappe.call({

            method:
                "taq_it.taqafia.doctype.exam_group_date.exam_group_date.get_group_exam_forms",

            args: {

                exam_group_date:
                    this.exam_group_date

            },

            callback: (r) => {

                const forms =
                    r.message || {};


                this.loaded_exam_form =
                    this.get_stage() === "Written"
                        ? forms.written_exam
                        : forms.oral_exam;


                this.update_summary();

            }

        });

    }


    load_preachers() {

        if (!this.exam_group_date) {

            frappe.msgprint(
                "اختر جلسة الامتحان أولا"
            );

            return;

        }


        frappe.call({

            method:
                "taq_it.taqafia.doctype.exam_grading_tool.exam_grading_tool.load_preachers",

            args: {

                exam_group_date:
                    this.exam_group_date,

                grading_stage:
                    this.get_stage()

            },

            freeze: true,

            freeze_message:
                "جاري تحميل الوعاظ...",

            callback: (r) => {

                this.grading_data =
                    r.message || {
                        columns: [],
                        rows: []
                    };


                this.loaded_exam_form =
                    this.grading_data.exam_form || null;


                this.render_grading_table();

                this.update_summary();


                const count =
                    this.grading_data.rows.length;


                frappe.show_alert({

                    message:
                        `تم تحميل ${count} واعظ`,

                    indicator:
                        count
                            ? "green"
                            : "orange"

                });

            }

        });

    }


    reset_table() {

        this.grading_data = {
            columns: [],
            rows: []
        };


        this.update_summary();


        this.wrapper
            .find("[data-table-stage]")
            .text("لم يتم التحميل");


        this.wrapper
            .find("[data-table-container]")
            .html(`

                <div class="eg-empty-state">

                    <div class="eg-empty-icon">
                        ✓
                    </div>

                    <h3>
                        جاهز لبدء الرصد
                    </h3>

                    <p>
                        اختر جلسة الامتحان ومرحلة الرصد ثم اضغط
                        <strong>تحميل الوعاظ</strong>.
                    </p>

                </div>

            `);

    }


    update_summary() {

        const count =
            (
                this.grading_data.rows ||
                []
            ).length;


        const stage =
            this.get_stage_label();


        this.wrapper
            .find('[data-stat="count"]')
            .text(count);


        this.wrapper
            .find('[data-stat="stage"]')
            .text(stage);


        this.wrapper
            .find('[data-stat="exam-form"]')
            .text(
                this.loaded_exam_form ||
                "—"
            );

    }

}