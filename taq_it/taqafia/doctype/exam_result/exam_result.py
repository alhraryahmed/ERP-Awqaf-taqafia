# Copyright (c) 2026, ahmeed and contributors
# For license information, please see license.txt

from urllib.parse import quote

import frappe
from frappe.model.document import Document

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
STAGE_EXCUSED_ABSENT = "Excused Absent"
STAGE_UNEXCUSED_ABSENT = "Unexcused Absent"

PASS_PENDING = "Pending"
PASS_PASSED = "Passed"
PASS_FAILED = "Failed"
PASS_DEFERRED = "Deferred"
PASS_NOT_REQUIRED = "Not Required"

ATTENDANCE_PRESENT = "Present"
ATTENDANCE_EXCUSED_ABSENT = "Excused Absent"
ATTENDANCE_UNEXCUSED_ABSENT = "Unexcused Absent"

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
        self.set_grade()

    def prevent_changes_after_final_approval(self):
        previous = self.get_doc_before_save()
        if not previous:
            return

        if previous.docstatus == 1:
            frappe.throw("Final approved exam results cannot be modified.")

        if previous.status == STATUS_FINAL_APPROVED and self.docstatus == previous.docstatus:
            frappe.throw("Final approved exam results cannot be modified.")

        if self.attendance_status != previous.attendance_status and (
            previous.written_status == STAGE_APPROVED
            or previous.oral_status == STAGE_APPROVED
        ):
            frappe.throw("Attendance cannot be changed after a stage has been approved.")

        for stage, table_field, status_field in (
            (WRITTEN_STAGE, "written_questions", "written_status"),
            (ORAL_STAGE, "oral_questions", "oral_status"),
        ):
            if previous.get(status_field) != STAGE_APPROVED:
                continue

            if getattr(frappe.flags, "exam_stage_reopen", None) == stage:
                if self.get(status_field) != STAGE_GRADED:
                    frappe.throw("Reopening an approved stage must return it to Graded status.")
                before_rows = [
                    (row.name, row.aspect, row.question_number, row.max_grade, row.score)
                    for row in previous.get(table_field) or []
                ]
                current_rows = [
                    (row.name, row.aspect, row.question_number, row.max_grade, row.score)
                    for row in self.get(table_field) or []
                ]
                if before_rows != current_rows:
                    frappe.throw("Grades cannot be changed as part of reopening a stage.")
                continue

            if self.get(status_field) != STAGE_APPROVED:
                frappe.throw("Approved {0} exam results cannot be reopened.".format(stage))

            before_rows = [
                (row.name, row.aspect, row.question_number, row.max_grade, row.score)
                for row in previous.get(table_field) or []
            ]
            current_rows = [
                (row.name, row.aspect, row.question_number, row.max_grade, row.score)
                for row in self.get(table_field) or []
            ]
            if before_rows != current_rows:
                frappe.throw("Approved {0} grades cannot be modified.".format(stage))

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
        if getattr(self, "attendance_status", None) == ATTENDANCE_EXCUSED_ABSENT:
            self.pass_status = STAGE_EXCUSED_ABSENT
            return

        if getattr(self, "attendance_status", None) == ATTENDANCE_UNEXCUSED_ABSENT:
            self.pass_status = FINAL_FAILED_WRITTEN if self.oral_status == STAGE_NOT_REQUIRED else FINAL_FAILED_ORAL
            return

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

    def set_grade(self):
        """يحسب التقدير (grade) تلقائيا حسب النسبة المئوية النهائية، فقط للناجحين"""
        if self.pass_status != FINAL_PASSED:
            self.grade = ""
            return

        pct = self.percentage or 0

        if pct >= 85:
            self.grade = "ممتاز"
        elif pct >= 75:
            self.grade = "جيد جدا"
        elif pct >= 65:
            self.grade = "جيد"
        elif pct >= 50:
            self.grade = "مقبول"
        else:
            self.grade = ""

    def approve_stage(self, stage):
        if stage == WRITTEN_STAGE:
            self.approve_written()
        elif stage == ORAL_STAGE:
            self.approve_oral()
        else:
            frappe.throw("Invalid grading stage.")

        self.save()

    def approve_written(self):
        if getattr(self, "attendance_status", None) == ATTENDANCE_EXCUSED_ABSENT:
            self.written_status = STAGE_EXCUSED_ABSENT
            self.written_pass_status = PASS_DEFERRED
            self.status = STAGE_EXCUSED_ABSENT
            self.oral_status = STAGE_NOT_REQUIRED
            self.oral_pass_status = PASS_NOT_REQUIRED
            return

        if getattr(self, "attendance_status", None) == ATTENDANCE_UNEXCUSED_ABSENT:
            self.written_status = STAGE_UNEXCUSED_ABSENT
            self.written_pass_status = PASS_FAILED
            self.status = STATUS_WRITTEN_APPROVED
            self.oral_status = STAGE_NOT_REQUIRED
            self.oral_pass_status = PASS_NOT_REQUIRED
            return

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
        if getattr(self, "attendance_status", None) == ATTENDANCE_EXCUSED_ABSENT:
            self.oral_status = STAGE_EXCUSED_ABSENT
            self.oral_pass_status = PASS_DEFERRED
            self.status = STAGE_EXCUSED_ABSENT
            return

        if getattr(self, "attendance_status", None) == ATTENDANCE_UNEXCUSED_ABSENT:
            self.oral_status = STAGE_UNEXCUSED_ABSENT
            self.oral_pass_status = PASS_FAILED
            self.status = STATUS_FINAL_APPROVED
            return

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
def get_exam_result_print_url(waed):
    if not waed:
        frappe.throw("الواعظ مطلوب.")

    frappe.has_permission("waed_info", "read", doc=waed, throw=True)
    frappe.has_permission("exam_result", "read", throw=True)

    result_name = frappe.db.get_value(
        "exam_result",
        {"waed": waed, "docstatus": ["!=", 2]},
        "name",
        order_by="creation desc",
    )

    if not result_name:
        frappe.throw("لا توجد نتيجة امتحان لهذا الواعظ.")

    result_status = frappe.db.get_value(
        "exam_result",
        result_name,
        "status",
    )

    if result_status == STATUS_DRAFT:
        frappe.throw("لا يمكن طباعة كشف الدرجات قبل رصد الدرجات.")

    frappe.has_permission("exam_result", "read", doc=result_name, throw=True)

    url = (
        frappe.utils.get_url()
        + f"/printview?"
        + f"doctype={quote('exam_result')}"
        + f"&name={quote(str(result_name))}"
        + f"&format={quote('result')}"
        + f"&no_letterhead=0"
        + f"&trigger_print=0"
    )

    return url


def _print_view_url(doctype, name, print_format):
    return (
        frappe.utils.get_url()
        + "/printview?"
        + f"doctype={quote(doctype)}"
        + f"&name={quote(str(name))}"
        + f"&format={quote(str(print_format))}"
        + "&no_letterhead=0"
        + "&trigger_print=1"
    )


def _get_waed_license_print_action():
    """Return the active exam_result action whose print format belongs to waed_info."""
    actions = frappe.get_all(
        "waed_print_action",
        filters={"target_doctype": "exam_result", "enabled": 1},
        fields=["title", "print_format", "sort_order"],
        order_by="sort_order asc, modified desc",
    )

    for action in actions:
        if not action.print_format:
            continue
        print_format = frappe.db.get_value(
            "Print Format",
            action.print_format,
            ["doc_type", "disabled"],
            as_dict=True,
        )
        if print_format and print_format.doc_type == "waed_info" and not print_format.disabled:
            return action

    return None


@frappe.whitelist()
def get_successful_exam_result_print_options(result_name=None):
    """Return configured print labels and permission-checked URLs for a passed result."""
    frappe.has_permission("exam_result", "read", throw=True)
    frappe.has_permission("waed_info", "read", throw=True)

    license_action = _get_waed_license_print_action()
    response = {
        "license_title": (
            (license_action.title or license_action.print_format)
            if license_action
            else None
        ),
        "license_available": bool(license_action),
    }
    if not result_name:
        return response

    result = frappe.get_doc("exam_result", result_name)
    frappe.has_permission("exam_result", "read", doc=result, throw=True)
    frappe.has_permission("waed_info", "read", doc=result.waed, throw=True)

    if result.docstatus == 2:
        frappe.throw("لا يمكن طباعة نتيجة ملغاة.")
    if result.status != STATUS_FINAL_APPROVED or result.pass_status != FINAL_PASSED:
        frappe.throw("تتوفر مستندات الطباعة للنتائج الناجحة والمعتمدة فقط.")

    response["urls"] = {
        "form": _print_view_url("exam_result", result.name, "result2"),
        "grades": _print_view_url("exam_result", result.name, "result"),
        "license": (
            _print_view_url("waed_info", result.waed, license_action.print_format)
            if license_action
            else None
        ),
    }
    return response
