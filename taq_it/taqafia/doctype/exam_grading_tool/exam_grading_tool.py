# Copyright (c) 2026, ahmeed and contributors
# For license information, please see license.txt

import frappe
from frappe.model.workflow import apply_workflow
from frappe.model.document import Document
from frappe.utils import flt

from taq_it.taqafia.doctype.exam_result.exam_result import (
    ORAL_STAGE,
    PASS_FAILED,
    PASS_NOT_REQUIRED,
    PASS_PASSED,
    STAGE_APPROVED,
    STAGE_GRADED,
    STAGE_NOT_GRADED,
    STAGE_NOT_REQUIRED,
    STATUS_FINAL_APPROVED,
    STATUS_ORAL_GRADED,
    STATUS_WRITTEN_GRADED,
    WRITTEN_STAGE,
    get_stage_form_field,
    get_stage_status_field,
    get_stage_table_field,
)


GRADING_ROLE = "مشرف رصد الامتحانات"
APPROVAL_ROLE = "معتمد نتائج الامتحانات"
SYSTEM_MANAGER_ROLE = "System Manager"


class exam_grading_tool(Document):
    pass


def has_role(role):
    roles = frappe.get_roles()
    return SYSTEM_MANAGER_ROLE in roles or role in roles


def require_grading_role():
    if not has_role(GRADING_ROLE):
        frappe.throw("You are not allowed to grade exam results.")


def require_approval_role():
    if not has_role(APPROVAL_ROLE):
        frappe.throw("You are not allowed to approve exam results.")


def normalize_stage(stage):
    if stage in {WRITTEN_STAGE, ORAL_STAGE}:
        return stage

    frappe.throw("Invalid grading stage.")


def get_group(exam_group_date):
    if not exam_group_date:
        frappe.throw("Exam Group Date is required.")

    return frappe.get_doc("exam_group_date", exam_group_date)


def get_stage_exam_form(group, stage):
    return group.written_exam if stage == WRITTEN_STAGE else group.oral_exam


def ensure_stage_is_available(group, stage):
    exam_form = get_stage_exam_form(group, stage)
    if not exam_form:
        frappe.throw("{0} Exam Form is not configured on the selected group.".format(stage))

    if stage == ORAL_STAGE:
        group.prepare_oral_results()

    return exam_form


@frappe.whitelist()
def load_preachers(exam_group_date, grading_stage):
    stage = normalize_stage(grading_stage)
    group = get_group(exam_group_date)
    exam_form = ensure_stage_is_available(group, stage)

    frappe.has_permission("exam_result", "read", throw=True)

    table_field = get_stage_table_field(stage)
    rows = []
    question_map = {}

    if stage == WRITTEN_STAGE:
        candidate_rows = get_written_candidate_rows(group, exam_form)
    else:
        candidate_rows = get_oral_candidate_rows(group)

    for candidate in candidate_rows:
        result = candidate.get("result")
        waed = candidate.get("waed")
        waed_name = frappe.db.get_value("waed_info", waed, "namee") or waed
        questions = []

        for question in candidate.get("questions") or []:
            question_key = "{0}::{1}".format(question.aspect, question.question_number)
            question_map[question_key] = {
                "key": question_key,
                "question_number": question.question_number,
                "aspect": question.aspect,
                "max_grade": question.max_grade,
            }
            questions.append(
                {
                    "key": question_key,
                    "name": question_key,
                    "row_name": question.name,
                    "question_number": question.question_number,
                    "aspect": question.aspect,
                    "max_grade": question.max_grade,
                    "score": get_question_score(question),
                }
            )

        rows.append(
            {
                "exam_result": result.name if result else "",
                "waed": waed,
                "waed_name": waed_name,
                "stage_status": result.get(get_stage_status_field(stage)) if result else STAGE_NOT_GRADED,
                "result_status": result.status if result else "Not Created",
                "final_pass_status": result.pass_status if result else "Pending",
                "written_pass_status": result.written_pass_status if result else "Pending",
                "total_score": result.get("{0}_total".format(stage.lower())) if result else 0,
                "max_total": result.get("{0}_max_total".format(stage.lower())) if result else 0,
                "percentage": result.get("{0}_percentage".format(stage.lower())) if result else 0,
                "questions": questions,
            }
        )

    columns = sort_question_columns(question_map)

    return {
        "exam_form": exam_form,
        "stage": stage,
        "columns": columns,
        "rows": rows,
    }


def get_written_candidate_rows(group, exam_form):
    form = frappe.get_doc("exam_form", exam_form)
    rows = []

    for candidate in group.waed_info_to_exam:
        if not candidate.waed_info:
            continue

        result_name = frappe.db.exists(
            "exam_result",
            {
                "exam_group_date": group.name,
                "waed": candidate.waed_info,
            },
        )
        result = frappe.get_doc("exam_result", result_name) if result_name else None
        rows.append(
            {
                "waed": candidate.waed_info,
                "result": result,
                "questions": result.written_questions if result else form.questions,
            }
        )

    return rows


def get_question_score(question):
    score = question.get("score") if hasattr(question, "get") else getattr(question, "score", 0)
    return flt(score or 0)


def get_oral_candidate_rows(group):
    written_results = frappe.get_all(
        "exam_result",
        filters={"exam_group_date": group.name},
        fields=["name", "written_status", "written_pass_status"],
    )

    if not written_results:
        frappe.throw("يجب رصد واعتماد درجات التحريري قبل رصد درجات الشفوي.")

    has_approved_written = any(
        result.written_status == STAGE_APPROVED for result in written_results
    )
    if not has_approved_written:
        frappe.throw("يجب اعتماد درجات التحريري قبل رصد درجات الشفوي.")

    result_names = frappe.get_all(
        "exam_result",
        filters={
            "exam_group_date": group.name,
            "written_status": STAGE_APPROVED,
            "written_pass_status": PASS_PASSED,
        },
        pluck="name",
        order_by="creation asc",
    )

    rows = []
    for result_name in result_names:
        result = frappe.get_doc("exam_result", result_name)
        rows.append(
            {
                "waed": result.waed,
                "result": result,
                "questions": result.oral_questions,
            }
        )

    return rows


def sort_question_columns(question_map):
    aspect_order = []
    for question in question_map.values():
        if question["aspect"] not in aspect_order:
            aspect_order.append(question["aspect"])

    return sorted(
        question_map.values(),
        key=lambda question: (
            aspect_order.index(question["aspect"]),
            question["question_number"] or 0,
        ),
    )


@frappe.whitelist()
def save_grades(exam_group_date, grading_stage, rows):
    require_grading_role()

    stage = normalize_stage(grading_stage)
    group = get_group(exam_group_date)
    ensure_stage_is_available(group, stage)

    frappe.has_permission("exam_result", "write", throw=True)

    if isinstance(rows, str):
        rows = frappe.parse_json(rows)

    updated = []
    for row in rows or []:
        result = get_or_create_editable_result(row, group, stage)
        scores = row.get("scores") or {}

        table_field = get_stage_table_field(stage)
        for question in result.get(table_field) or []:
            question_key = "{0}::{1}".format(question.aspect, question.question_number)
            if question.name in scores:
                question.score = flt(scores.get(question.name))
            elif question_key in scores:
                question.score = flt(scores.get(question_key))

        result.set(get_stage_status_field(stage), STAGE_GRADED)
        result.calculate_all_totals()
        set_stage_pass_status_after_grading(result, stage)
        result.status = STATUS_WRITTEN_GRADED if stage == WRITTEN_STAGE else STATUS_ORAL_GRADED
        result.save()
        updated.append(result.name)

    update_group_status_after_save(group.name, stage)
    frappe.db.commit()
    return {"updated": updated}


def set_stage_pass_status_after_grading(result, stage):
    if stage == WRITTEN_STAGE:
        result.written_pass_status = result.get_stage_pass_status(WRITTEN_STAGE)
        if result.written_pass_status == PASS_PASSED:
            result.prepare_oral_questions()
        else:
            result.oral_status = STAGE_NOT_REQUIRED
            result.oral_pass_status = PASS_NOT_REQUIRED
        return

    result.oral_pass_status = result.get_stage_pass_status(ORAL_STAGE)


def get_or_create_editable_result(row, group, stage):
    result_name = row.get("exam_result")
    if not result_name and stage == WRITTEN_STAGE:
        waed = row.get("waed")
        if not waed:
            frappe.throw("Preacher is required.")

        written_form = frappe.get_doc("exam_form", group.written_exam)
        result_name, created = group.create_exam_result(waed, written_form)
        if created:
            group.update_waed_workflow(waed, "Grading")
            frappe.db.commit()
    elif not result_name:
        frappe.throw("Exam Result is required.")

    result = frappe.get_doc("exam_result", result_name)
    if result.exam_group_date != group.name:
        frappe.throw("Exam Result {0} does not belong to this session.".format(result_name))

    if result.status == STATUS_FINAL_APPROVED or result.docstatus == 1:
        frappe.throw("Final approved result {0} cannot be modified.".format(result.name))

    stage_status = result.get(get_stage_status_field(stage))
    if stage_status == STAGE_APPROVED:
        frappe.throw("{0} grades for {1} are already approved.".format(stage, result.name))

    if stage == ORAL_STAGE:
        if result.written_status != STAGE_APPROVED or result.written_pass_status != PASS_PASSED:
            frappe.throw("يجب اعتماد درجات التحريري قبل رصد درجات الشفوي.")

    return result


@frappe.whitelist()
def approve_stage(exam_group_date, grading_stage):
    require_approval_role()

    stage = normalize_stage(grading_stage)
    group = get_group(exam_group_date)
    ensure_stage_is_available(group, stage)

    frappe.has_permission("exam_result", "write", throw=True)

    filters = {"exam_group_date": group.name}
    if stage == ORAL_STAGE:
        filters.update(
            {
                "written_status": STAGE_APPROVED,
                "written_pass_status": PASS_PASSED,
            }
        )

    results = frappe.get_all(
        "exam_result",
        filters=filters,
        fields=["name", get_stage_status_field(stage)],
        order_by="creation asc",
    )

    if not results:
        if stage == ORAL_STAGE:
            frappe.throw("يجب اعتماد درجات التحريري قبل اعتماد درجات الشفوي.")
        frappe.throw("No Exam Results found for this stage.")

    status_field = get_stage_status_field(stage)
    not_ready = [
        result.name
        for result in results
        if result.get(status_field) not in {STAGE_GRADED, STAGE_APPROVED}
    ]

    if not_ready:
        frappe.throw(
            "Cannot approve before grading all candidates. Pending results: {0}".format(
                ", ".join(not_ready)
            )
        )

    approved = []
    submitted = []
    for result_info in results:
        result = frappe.get_doc("exam_result", result_info.name)
        if result.get(status_field) != STAGE_APPROVED:
            result.approve_stage(stage)
            update_preacher_workflow_after_stage(result, stage)
            approved.append(result.name)

        if stage == ORAL_STAGE and result.status == STATUS_FINAL_APPROVED and result.docstatus == 0:
            result.submit()
            submitted.append(result.name)

    update_group_status_after_approval(group.name, stage)

    frappe.db.commit()
    return {"approved": approved, "submitted": submitted}


def update_preacher_workflow_after_stage(result, stage):
    preacher = frappe.get_doc("waed_info", result.waed)

    if stage == WRITTEN_STAGE:
        if result.written_pass_status == PASS_PASSED:
            apply_workflow(preacher, "Pass written")
            if result.oral_exam_form:
                apply_workflow(preacher, "Transfer to the oral exam")
            else:
                apply_workflow(preacher, "accepted")
        else:
            apply_workflow(preacher, "faild in written")
        return

    if stage == ORAL_STAGE and result.status == STATUS_FINAL_APPROVED:
        if result.oral_pass_status == PASS_PASSED:
            apply_workflow(preacher, "accepted")
        else:
            apply_workflow(preacher, "faild in oral")


def update_group_status_after_save(exam_group_date, stage):
    if not frappe.db.has_column("exam_group_date", "exam_status"):
        return

    next_status = "Written Graded" if stage == WRITTEN_STAGE else "Oral Graded"
    frappe.db.set_value("exam_group_date", exam_group_date, "exam_status", next_status)


def update_group_status_after_approval(exam_group_date, stage):
    if not frappe.db.has_column("exam_group_date", "exam_status"):
        return

    next_status = "Written Approved" if stage == WRITTEN_STAGE else "Oral Approved"
    frappe.db.set_value("exam_group_date", exam_group_date, "exam_status", next_status)
