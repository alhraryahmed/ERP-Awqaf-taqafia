# Copyright (c) 2026, ahmeed and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.file_manager import save_file

WRITTEN_STAGE = "Written"
ORAL_STAGE = "Oral"

STATUS_DRAFT = "Draft"
STATUS_WRITTEN_GRADED = "Written Graded"
STATUS_WRITTEN_APPROVED = "Written Approved"
STATUS_ORAL_GRADED = "Oral Graded"
STATUS_FINAL_APPROVED = "Final Approved"

STAGE_NOT_REQUIRED = "Not Required"
STAGE_NOT_GRADED = "Not Graded"
STAGE_GRADED = "Graded"
STAGE_APPROVED = "Approved"

PASS_PENDING = "Pending"
PASS_PASSED = "Passed"
PASS_FAILED = "Failed"
PASS_NOT_REQUIRED = "Not Required"

FINAL_FAILED_WRITTEN = "Failed Written"
FINAL_FAILED_ORAL = "Failed Oral"
FINAL_PASSED = "Passed"


class exam_result(Document):
    def validate(self):
        self.prevent_changes_after_final_approval()
        self.validate_unique_candidate_in_group()
        self.validate_question_scores()
        self.calculate_all_totals()
        self.set_final_status()

    def prevent_changes_after_final_approval(self):
        previous = self.get_doc_before_save()
        if not previous:
            return

        if previous.docstatus == 1:
            frappe.throw("Final approved exam results cannot be modified.")

        if previous.status == STATUS_FINAL_APPROVED and self.docstatus == previous.docstatus:
            frappe.throw("Final approved exam results cannot be modified.")

    def validate_unique_candidate_in_group(self):
        if not self.exam_group_date or not self.waed:
            return

        existing = frappe.db.exists(
            "exam_result",
            {
                "exam_group_date": self.exam_group_date,
                "waed": self.waed,
                "name": ["!=", self.name],
            },
        )
        if existing:
            frappe.throw(
                "Exam Result already exists for preacher {0} in exam group {1}.".format(
                    self.waed, self.exam_group_date
                )
            )

    def validate_question_scores(self):
        for table_field in ("written_questions", "oral_questions"):
            for row in self.get(table_field) or []:
                if row.score is None:
                    continue

                if row.score < 0:
                    frappe.throw(
                        "Score for question {0} cannot be less than zero.".format(
                            row.question_number
                        )
                    )

                if row.score > row.max_grade:
                    frappe.throw(
                        "Score for question {0} cannot exceed max grade ({1}).".format(
                            row.question_number, row.max_grade
                        )
                    )

    def calculate_all_totals(self):
        self.calculate_stage_totals(WRITTEN_STAGE)
        self.calculate_stage_totals(ORAL_STAGE)

        self.total_score = (self.written_total or 0) + (self.oral_total or 0)
        self.max_total = (self.written_max_total or 0) + (self.oral_max_total or 0)
        self.percentage = (
            (self.total_score / self.max_total) * 100 if self.max_total else 0
        )

    def calculate_stage_totals(self, stage):
        table_field = get_stage_table_field(stage)
        form_field = get_stage_form_field(stage)
        total_field = get_stage_total_field(stage)
        max_total_field = get_stage_max_total_field(stage)
        percentage_field = get_stage_percentage_field(stage)

        rows = self.get(table_field) or []
        total = sum(row.score or 0 for row in rows)
        max_total = self.get_exam_max_score(self.get(form_field), rows)

        self.set(total_field, total)
        self.set(max_total_field, max_total)
        self.set(percentage_field, (total / max_total) * 100 if max_total else 0)

    def get_exam_max_score(self, exam_form, rows):
        if exam_form:
            max_score = frappe.db.get_value("exam_form", exam_form, "max_score")
            if max_score:
                return max_score

        return sum(row.max_grade or 0 for row in rows)

    def set_final_status(self):
        if self.written_status == STAGE_APPROVED and self.written_pass_status == PASS_FAILED:
            self.pass_status = FINAL_FAILED_WRITTEN
            return

        if (
            self.oral_status == STAGE_APPROVED
            and self.oral_pass_status == PASS_FAILED
        ):
            self.pass_status = FINAL_FAILED_ORAL
            return

        if self.status == STATUS_FINAL_APPROVED:
            self.pass_status = FINAL_PASSED
            return

        self.pass_status = self.pass_status or PASS_PENDING

    def approve_stage(self, stage):
        if stage == WRITTEN_STAGE:
            self.approve_written()
        elif stage == ORAL_STAGE:
            self.approve_oral()
        else:
            frappe.throw("Invalid grading stage.")

        self.save()

    def approve_written(self):
        if self.written_status != STAGE_GRADED:
            frappe.throw("Written grades must be saved before approval.")

        self.written_status = STAGE_APPROVED
        self.written_pass_status = self.get_stage_pass_status(WRITTEN_STAGE)

        if self.written_pass_status == PASS_PASSED:
            self.status = STATUS_WRITTEN_APPROVED
            self.prepare_oral_questions()
        else:
            self.status = STATUS_WRITTEN_APPROVED
            self.oral_status = STAGE_NOT_REQUIRED
            self.oral_pass_status = PASS_NOT_REQUIRED

    def approve_oral(self):
        if self.written_status != STAGE_APPROVED:
            frappe.throw("Written grades must be approved before oral approval.")

        if self.written_pass_status != PASS_PASSED:
            frappe.throw("Only candidates who passed the written exam can be orally approved.")

        if self.oral_status != STAGE_GRADED:
            frappe.throw("Oral grades must be saved before approval.")

        self.oral_status = STAGE_APPROVED
        self.oral_pass_status = self.get_stage_pass_status(ORAL_STAGE)
        self.status = STATUS_FINAL_APPROVED

    def get_stage_pass_status(self, stage):
        percentage = self.get(get_stage_percentage_field(stage)) or 0
        success_rate = self.get_success_rate(self.get(get_stage_form_field(stage)))
        return PASS_PASSED if percentage >= success_rate else PASS_FAILED

    def get_success_rate(self, exam_form):
        if not exam_form:
            return 0

        return frappe.db.get_value("exam_form", exam_form, "success_rate") or 0

    def prepare_oral_questions(self):
        if self.oral_status == STAGE_APPROVED:
            frappe.throw("Approved oral grades cannot be regenerated.")

        if not self.oral_exam_form:
            self.oral_status = STAGE_NOT_REQUIRED
            self.oral_pass_status = PASS_NOT_REQUIRED
            return

        if self.oral_questions:
            self.oral_status = self.oral_status or STAGE_NOT_GRADED
            return

        oral_form = frappe.get_doc("exam_form", self.oral_exam_form)
        for question in oral_form.questions:
            self.append(
                "oral_questions",
                {
                    "aspect": question.aspect,
                    "question_number": question.question_number,
                    "max_grade": question.max_grade,
                    "score": 0,
                },
            )

        self.oral_status = STAGE_NOT_GRADED
        self.oral_pass_status = PASS_PENDING

    def on_submit(self):
        if self.status != STATUS_FINAL_APPROVED:
            frappe.throw("Only final approved exam results can be submitted.")


def get_stage_table_field(stage):
    return "written_questions" if stage == WRITTEN_STAGE else "oral_questions"


def get_stage_form_field(stage):
    return "written_exam_form" if stage == WRITTEN_STAGE else "oral_exam_form"


def get_stage_status_field(stage):
    return "written_status" if stage == WRITTEN_STAGE else "oral_status"


def get_stage_total_field(stage):
    return "written_total" if stage == WRITTEN_STAGE else "oral_total"


def get_stage_max_total_field(stage):
    return "written_max_total" if stage == WRITTEN_STAGE else "oral_max_total"


def get_stage_percentage_field(stage):
    return "written_percentage" if stage == WRITTEN_STAGE else "oral_percentage"


@frappe.whitelist()
def generate_score_sheet(waed):
    if not waed:
        frappe.throw("Preacher is required.")

    frappe.has_permission("waed_info", "read", doc=waed, throw=True)
    frappe.has_permission("exam_result", "read", throw=True)

    result_name = frappe.db.get_value(
        "exam_result",
        {"waed": waed},
        "name",
        order_by="creation desc",
    )

    if not result_name:
        frappe.throw("لا توجد نتيجة امتحان لهذا الواعظ.")

    result_status = frappe.db.get_value("exam_result", result_name, "status")
    if result_status == STATUS_DRAFT:
        frappe.throw("لا يمكن إصدار كشف الدرجات قبل رصد أي درجات لهذا الواعظ.")

    pdf_content = frappe.get_print(
        "exam_result",
        result_name,
        print_format="result",
        as_pdf=True,
    )

    waed_name = frappe.db.get_value("waed_info", waed, "namee") or waed
    file_name = "كشف درجات - {0}.pdf".format(waed_name)

    file_doc = save_file(
        file_name,
        pdf_content,
        "waed_info",
        waed,
        is_private=1,
    )

    return {"file_url": file_doc.file_url}