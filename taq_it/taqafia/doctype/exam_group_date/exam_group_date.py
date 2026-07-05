import frappe
from frappe.model.document import Document
from frappe.model.workflow import apply_workflow
from frappe.utils import cint, getdate

from taq_it.taqafia.doctype.exam_result.exam_result import (
    PASS_PASSED,
    STAGE_APPROVED,
    STAGE_NOT_GRADED,
    STATUS_DRAFT,
    WRITTEN_STAGE,
)


RESULT_STATUS_NOT_GRADED = "Not Graded"
WAED_STATUS_READY_FOR_APPOINTMENT = "Scheduling an appointment"


class exam_group_date(Document):
    def validate(self):
        self.set_exam_period()
        self.validate_exam_forms()
        self.validate_candidate_limit()

    @frappe.whitelist()
    def get_preachers(self):
        limit = cint(self.count_to_exam or 0)
        if limit <= 0 or limit > 30:
            frappe.throw("Count to exam must be between 1 and 30.")

        preachers = frappe.get_all(
            "waed_info",
            filters={"waed_status": WAED_STATUS_READY_FOR_APPOINTMENT},
            fields=["name", "namee", "phoone", "office", "place"],
            limit=limit,
        )

        self.set("waed_info_to_exam", [])

        for preacher in preachers:
            self.append(
                "waed_info_to_exam",
                {
                    "waed_info": preacher.name,
                    "full_name": preacher.namee,
                    "phone": preacher.phoone,
                    "office": preacher.office,
                    "address": preacher.place,
                },
            )

        self.count_waes_exam = len(preachers)
        return preachers

    @frappe.whitelist()
    def get_exam_forms(self):
        return {
            "written_exam": self.written_exam,
            "oral_exam": self.oral_exam,
        }

    def autoname(self):
        if not self.exam_day:
            frappe.throw("exam_day is required")

        date_str = getdate(self.exam_day).strftime("%Y-%m-%d")
        prefix = f"EX-{date_str}"

        last_number = frappe.db.sql(
            """
            SELECT MAX(CAST(SUBSTRING_INDEX(name, '-', -1) AS UNSIGNED))
            FROM `tabexam_group_date`
            WHERE name LIKE %(prefix)s
        """,
            {"prefix": f"{prefix}-%"},
        )

        new_no = 1
        if last_number and last_number[0][0]:
            new_no = int(last_number[0][0]) + 1

        self.name = f"{prefix}-{str(new_no).zfill(2)}"

    def after_insert(self):
        self.update_preachers_workflow("Appointment")

    def set_exam_period(self):
        if not self.exam_day:
            return

        date_value = getdate(self.exam_day)
        self.exam_period = "{0}-{1}".format(date_value.year, date_value.month)

    def validate_exam_forms(self):
        if not self.written_exam:
            frappe.throw("Written Exam Form is required.")

        if self.written_exam and self.oral_exam and self.written_exam == self.oral_exam:
            frappe.throw("Written and Oral Exam Forms must be different.")

        self.validate_exam_form_has_questions(self.written_exam, "Written")
        if self.oral_exam:
            self.validate_exam_form_has_questions(self.oral_exam, "Oral")

    def validate_exam_form_has_questions(self, exam_form, label):
        if not exam_form:
            return

        has_questions = frappe.db.exists(
            "exam_form_question",
            {
                "parent": exam_form,
                "parenttype": "exam_form",
                "parentfield": "questions",
            },
        )
        if not has_questions:
            frappe.throw("{0} Exam Form must have questions.".format(label))

    def validate_candidate_limit(self):
        limit = cint(self.count_to_exam or 0)
        if limit and (limit < 1 or limit > 30):
            frappe.throw("Count to exam must be between 1 and 30.")

    def start_written_exam(self):
        self.validate_exam_forms()

        exam_form = frappe.get_doc("exam_form", self.written_exam)
        for row in self.waed_info_to_exam:
            if not row.waed_info:
                continue

            result_name, created = self.create_exam_result(row.waed_info, exam_form)
            if created:
                self.update_waed_workflow(row.waed_info, "Grading")

    def create_exam_result(self, waed, written_exam_form):
        existing_result = frappe.db.exists(
            "exam_result",
            {
                "exam_group_date": self.name,
                "waed": waed,
            },
        )
        if existing_result:
            return existing_result, False

        result = frappe.new_doc("exam_result")
        result.exam_group_date = self.name
        result.waed = waed
        result.written_exam_form = written_exam_form.name
        result.oral_exam_form = self.oral_exam
        result.exam_form = written_exam_form.name
        result.status = STATUS_DRAFT
        result.written_status = RESULT_STATUS_NOT_GRADED
        result.oral_status = "Not Required"
        result.written_pass_status = "Pending"
        result.oral_pass_status = "Pending" if self.oral_exam else "Not Required"

        for question in written_exam_form.questions:
            result.append(
                "written_questions",
                {
                    "aspect": question.aspect,
                    "question_number": question.question_number,
                    "max_grade": question.max_grade,
                    "score": 0,
                },
            )

        result.insert()
        return result.name, True

    def prepare_oral_results(self):
        if not self.oral_exam:
            return []

        prepared = []
        results = frappe.get_all(
            "exam_result",
            filters={
                "exam_group_date": self.name,
                "written_status": STAGE_APPROVED,
                "written_pass_status": PASS_PASSED,
                "docstatus": 0,
            },
            pluck="name",
        )

        for result_name in results:
            result = frappe.get_doc("exam_result", result_name)
            if result.oral_status == STAGE_APPROVED:
                continue

            result.oral_exam_form = self.oral_exam
            result.prepare_oral_questions()
            result.save()
            prepared.append(result.name)

        return prepared

    def update_preachers_workflow(self, action):
        for row in self.waed_info_to_exam:
            if row.waed_info:
                self.update_waed_workflow(row.waed_info, action)

    def update_waed_workflow(self, waed, action):
        doc = frappe.get_doc("waed_info", waed)
        apply_workflow(doc, action)


@frappe.whitelist()
def get_group_exam_forms(exam_group_date):
    if not exam_group_date:
        return {}

    group = frappe.get_doc("exam_group_date", exam_group_date)
    return group.get_exam_forms()
