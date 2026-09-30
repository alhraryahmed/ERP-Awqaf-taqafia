# Copyright (c) 2026, ahmeed and contributors
# For license information, please see license.txt

import math

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


GRADING_ROLES = {
    "مشرف رصد الامتحانات",
    "مشرف رصد امتحانات الوعاظ",
    "مشرفة رصد امتحانات الواعظات",
    "رئيس قسم التقويم والقياس",
    "مدير إدارة الشؤون الثقافية",
}
APPROVAL_ROLES = {
    "معتمد نتائج الامتحانات",
    "رئيس قسم التقويم والقياس",
    "مدير إدارة الشؤون الثقافية",
}
SYSTEM_MANAGER_ROLE = "System Manager"


class exam_grading_tool(Document):
    pass


def has_any_role(roles_set):
    user_roles = set(frappe.get_roles())
    return bool(user_roles.intersection(roles_set | {SYSTEM_MANAGER_ROLE}))


def require_grading_role():
    if not has_any_role(GRADING_ROLES):
        frappe.throw("ليست لديك صلاحية رصد نتائج الامتحانات.")


def require_approval_role():
    if not has_any_role(APPROVAL_ROLES):
        frappe.throw("ليست لديك صلاحية اعتماد نتائج الامتحانات.")


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

    return exam_form


@frappe.whitelist()
def load_preachers(exam_group_date, grading_stage):
    stage = normalize_stage(grading_stage)
    group = get_group(exam_group_date)
    frappe.has_permission("exam_group_date", "read", doc=group.name, throw=True)
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
                "attendance_status": getattr(result, "attendance_status", "Present") if result else "Present",
                "absence_reason": getattr(result, "absence_reason", "") if result else "",
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
        "success_rate": flt(frappe.db.get_value("exam_form", exam_form, "success_rate") or 0),
        "stage": stage,
        "columns": columns,
        "rows": rows,
    }


def get_written_candidate_rows(group, exam_form):
    form = frappe.get_doc("exam_form", exam_form)
    rows = []

    for waed in get_group_candidate_names(group):
        result_name = frappe.db.exists(
            "exam_result",
            {
                "exam_group_date": group.name,
                "waed": waed,
            },
        )
        result = frappe.get_doc("exam_result", result_name) if result_name else None
        rows.append(
            {
                "waed": waed,
                "result": result,
                "questions": result.written_questions if result else form.questions,
            }
        )

    return rows


def get_group_candidate_names(group):
    names = []
    for candidate in group.waed_info_to_exam or []:
        waed = getattr(candidate, "full_name", None) or getattr(candidate, "waed_info", None)
        if waed and waed not in names:
            names.append(waed)
    return names


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
    frappe.has_permission("exam_group_date", "read", doc=group.name, throw=True)
    ensure_stage_is_available(group, stage)

    frappe.has_permission("exam_result", "write", throw=True)

    if isinstance(rows, str):
        rows = frappe.parse_json(rows)
    if not isinstance(rows, list):
        frappe.throw("Grades must be provided as a list of candidate rows.")
    if not rows:
        frappe.throw("No candidate grades were provided.")

    updated = []
    seen_candidates = set()
    for row in rows or []:
        if not isinstance(row, dict):
            frappe.throw("Each grading row must be an object.")

        result = get_or_create_editable_result(row, group, stage)
        if result.waed in seen_candidates:
            frappe.throw("A candidate can only be included once in a grading request.")
        seen_candidates.add(result.waed)
        attendance = row.get("attendance_status") or "Present"
        if attendance not in {"Present", "Excused Absent", "Unexcused Absent"}:
            frappe.throw("Invalid attendance status.")
        result.attendance_status = attendance
        result.absence_reason = row.get("absence_reason") or ""

        if attendance in {"Excused Absent", "Unexcused Absent"}:
            stage_status_field = get_stage_status_field(stage)
            result.set(stage_status_field, attendance)
            if stage == WRITTEN_STAGE:
                result.written_pass_status = "Deferred" if attendance == "Excused Absent" else "Failed"
                result.oral_status = "Not Required"
                result.oral_pass_status = "Not Required"
                result.status = "Excused Absent" if attendance == "Excused Absent" else STATUS_WRITTEN_GRADED
            else:
                result.oral_pass_status = "Deferred" if attendance == "Excused Absent" else "Failed"
                result.status = "Excused Absent" if attendance == "Excused Absent" else STATUS_ORAL_GRADED
            result.calculate_all_totals()
            result.save()
            updated.append(result.name)
            continue

        scores = row.get("scores") or {}
        if not isinstance(scores, dict):
            frappe.throw("Candidate scores must be provided as an object.")

        table_field = get_stage_table_field(stage)
        question_rows = result.get(table_field) or []
        accepted_score_keys = set()
        for question in question_rows:
            question_key = "{0}::{1}".format(question.aspect, question.question_number)
            accepted_score_keys.update((question.name, question_key))

        unknown_score_keys = set(scores) - accepted_score_keys
        if unknown_score_keys:
            frappe.throw("One or more submitted grades do not match this exam form.")

        for question in question_rows:
            question_key = "{0}::{1}".format(question.aspect, question.question_number)
            if question.name in scores:
                score = scores.get(question.name)
            elif question_key in scores:
                score = scores.get(question_key)
            else:
                continue

            if score in (None, ""):
                question.score = 0
                continue

            try:
                score_value = float(score)
            except (TypeError, ValueError, OverflowError):
                frappe.throw("Each grade must be a valid number.")

            if not math.isfinite(score_value) or score_value < 0 or score_value > flt(question.max_grade):
                frappe.throw(
                    "Score for question {0} must be between zero and {1}.".format(
                        question.question_number, question.max_grade
                    )
                )
            question.score = score_value

        result.set(get_stage_status_field(stage), STAGE_GRADED)
        result.calculate_all_totals()
        set_stage_pass_status_after_grading(result, stage)
        result.status = STATUS_WRITTEN_GRADED if stage == WRITTEN_STAGE else STATUS_ORAL_GRADED
        result.save()
        updated.append(result.name)

    update_group_status_after_save(group.name, stage)
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
        if waed not in set(get_group_candidate_names(group)):
            frappe.throw("This preacher is not assigned to the selected exam session.")

        written_form = frappe.get_doc("exam_form", group.written_exam)
        result_name, created = group.create_exam_result(waed, written_form)
        if created:
            group.update_waed_workflow(waed, "Grading")
    elif not result_name:
        frappe.throw("Exam Result is required.")

    result = frappe.get_doc("exam_result", result_name)
    if result.exam_group_date != group.name:
        frappe.throw("Exam Result {0} does not belong to this session.".format(result_name))
    if result.waed not in set(get_group_candidate_names(group)):
        frappe.throw("This preacher is not assigned to the selected exam session.")

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
    frappe.has_permission("exam_group_date", "read", doc=group.name, throw=True)
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
        if result.get(status_field) not in {STAGE_GRADED, STAGE_APPROVED, "Excused Absent", "Unexcused Absent"}
    ]

    if not_ready:
        frappe.throw(
            "لا يمكن اعتماد المرحلة قبل رصد وحفظ درجات جميع الوعاظ أولاً. الوعاظ الذين لم يتم رصد درجاتهم بعد: {0}".format(
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

    return {"approved": approved, "submitted": submitted}


def update_preacher_workflow_after_stage(result, stage):
    preacher = frappe.get_doc("waed_info", result.waed)

    def try_apply(doc, *actions):
        for act in actions:
            try:
                apply_workflow(doc, act)
                doc.reload()
                return True
            except Exception:
                continue
        return False

    def move_to(target_state, *actions):
        if try_apply(preacher, *actions):
            return
        # Workflow field for WAED_DATA is waed_status. This fallback also
        # handles legacy records whose current state has no matching transition.
        if frappe.db.has_column("waed_info", "waed_status"):
            frappe.db.set_value("waed_info", preacher.name, "waed_status", target_state)
        else:
            frappe.log_error(
                "WAED_DATA has no waed_status field",
                "Failed to update exam workflow for {0}".format(preacher.name),
            )

    if (
        getattr(result, "attendance_status", None) == "Excused Absent"
        or result.get(get_stage_status_field(stage)) == "Excused Absent"
    ):
        # WAED_DATA already defines renew only from Failed Written / Failed Oral.
        # Follow those existing transitions without adding new workflow actions.
        state = getattr(preacher, "waed_status", None)
        if state == "Failed Written":
            move_to("Scheduling an appointment", "renew")
        elif state == "Failed Oral":
            move_to("Scheduling an appointment", "renew")
        elif stage == WRITTEN_STAGE and state == "in the written exam":
            if try_apply(preacher, "Fail Written Exam"):
                move_to("Scheduling an appointment", "renew")
            else:
                frappe.log_error(
                    "Could not move excused candidate through existing WAED_DATA transitions",
                    "Failed to renew preacher {0}".format(preacher.name),
                )
        else:
            frappe.log_error(
                "No existing WAED_DATA renew transition from state {0}".format(state),
                "Failed to renew preacher {0}".format(preacher.name),
            )
        return

    if stage == WRITTEN_STAGE:
        if result.written_pass_status == PASS_PASSED:
            move_to("Passed the Written Exam", "Pass written")
            if result.oral_exam_form:
                move_to("In the oral exam", "Transfer to the oral exam")
            else:
                move_to("Approved", "Approve Candidate", "accepted")
        else:
            move_to("Failed Written", "Fail Written Exam", "faild in written")
        return

    if stage == ORAL_STAGE and result.status == STATUS_FINAL_APPROVED:
        if result.oral_pass_status == PASS_PASSED:
            move_to("Approved", "Approve Candidate", "accepted")
        else:
            move_to("Failed Oral", "Fail Oral Exam", "faild in oral")


def update_group_status_after_save(exam_group_date, stage):
    if not frappe.db.has_column("exam_group_date", "exam_status"):
        return

    next_status = "Written Graded" if stage == WRITTEN_STAGE else "Oral Graded"
    frappe.db.set_value("exam_group_date", exam_group_date, "exam_status", next_status)


def update_group_status_after_approval(exam_group_date, stage):
    if not frappe.db.has_column("exam_group_date", "exam_status"):
        return

    group = frappe.get_doc("exam_group_date", exam_group_date)

    if stage == ORAL_STAGE:
        next_status = "Completed"
    elif not group.oral_exam:
        next_status = "Completed"
    else:
        has_oral_candidates = frappe.db.exists(
            "exam_result",
            {
                "exam_group_date": exam_group_date,
                "written_pass_status": PASS_PASSED,
            },
        )
        next_status = "Written Approved" if has_oral_candidates else "Completed"

    frappe.db.set_value("exam_group_date", exam_group_date, "exam_status", next_status)


@frappe.whitelist()
def get_sessions_overview(gender=None):
    """
    استعلام ذكي لجلب بطاقات الجلسات مع إحصائيات الرصد والاعتماد ومؤشر المرحلة الحالية
    """
    frappe.has_permission("exam_group_date", "read", throw=True)

    has_gender_col = frappe.db.has_column("exam_group_date", "target_gender")
    where_clause = "exam_status NOT IN ('Cancelled', 'ملغي', 'Scheduled', 'من المقرر', 'مجدول')"

    if has_gender_col and gender:
        if gender in ["Male", "ذكر"]:
            where_clause += " AND (target_gender IS NULL OR target_gender = '' OR target_gender IN ('Male', 'ذكر'))"
        elif gender in ["Female", "أنثى"]:
            where_clause += " AND target_gender IN ('Female', 'أنثى')"

    date_col = "exam_day" if frappe.db.has_column("exam_group_date", "exam_day") else "creation"

    sessions = frappe.db.sql(f"""
        SELECT 
            name,
            `{date_col}` as exam_day,
            exam_status,
            written_exam,
            oral_exam,
            {"target_gender" if has_gender_col else "'Male' as target_gender"}
        FROM `tabexam_group_date`
        WHERE {where_clause}
        ORDER BY `{date_col}` DESC, creation DESC
    """, as_dict=True)

    result = []
    for sess in sessions:
        group_name = sess["name"]
        
        total_candidates = frappe.db.count(
            "exam-group-data-child",
            {"parent": group_name, "parenttype": "exam_group_date"}
        )
        if not total_candidates:
            total_candidates = frappe.db.count(
                "exam_result",
                {"exam_group_date": group_name}
            )

        res_rows = frappe.get_all(
            "exam_result",
            filters={"exam_group_date": group_name},
            fields=[
                "name",
                "written_status",
                "written_pass_status",
                "oral_status",
                "oral_pass_status",
                "status",
                "attendance_status"
            ]
        )

        written_graded = sum(1 for r in res_rows if r.written_status in [STAGE_GRADED, STAGE_APPROVED, "Excused Absent", "Unexcused Absent"])
        written_approved = sum(1 for r in res_rows if r.written_status == STAGE_APPROVED)
        written_decided = sum(
            1 for r in res_rows
            if r.written_status in [STAGE_APPROVED, "Excused Absent", "Unexcused Absent"]
        )
        written_passed = sum(1 for r in res_rows if r.written_status == STAGE_APPROVED and r.written_pass_status == PASS_PASSED)
        
        oral_graded = sum(1 for r in res_rows if r.oral_status in [STAGE_GRADED, STAGE_APPROVED, "Excused Absent", "Unexcused Absent"])
        oral_approved = sum(1 for r in res_rows if r.oral_status == STAGE_APPROVED)
        final_approved = sum(1 for r in res_rows if r.status == STATUS_FINAL_APPROVED)

        has_oral = bool(sess.get("oral_exam"))
        written_stage_approved = sess.get("exam_status") in {"Written Approved", "Completed"}
        
        if final_approved >= total_candidates and total_candidates > 0:
            step = "completed"
            step_label = "مكتمل ومعتمد نهائياً"
            step_badge = "success"
        elif written_stage_approved and has_oral and written_decided >= total_candidates and oral_approved >= written_passed and total_candidates > 0:
            step = "completed"
            step_label = "مكتمل ومعتمد نهائياً"
            step_badge = "success"
        elif written_stage_approved and has_oral and written_decided >= total_candidates and oral_graded >= written_passed and written_passed > 0:
            step = "ready_oral_approval"
            step_label = "جاهز لاعتماد الشفوي"
            step_badge = "warning"
        elif written_stage_approved and has_oral and written_decided >= total_candidates and written_passed > 0:
            step = "ready_oral_grading"
            step_label = "جاهز لرصد الشفوي"
            step_badge = "info"
        elif written_stage_approved and written_decided >= total_candidates and total_candidates > 0:
            step = "completed"
            step_label = "مكتمل ومعتمد نهائياً"
            step_badge = "success"
        elif written_graded >= total_candidates and total_candidates > 0:
            step = "ready_written_approval"
            step_label = "جاهز لاعتماد التحريري"
            step_badge = "warning"
        else:
            step = "ready_written_grading"
            step_label = "جاهز لرصد التحريري"
            step_badge = "neutral"

        result.append({
            "name": group_name,
            "exam_day": sess.get("exam_day"),
            "target_gender": sess.get("target_gender") or ("Female" if gender in ["Female", "أنثى"] else "Male"),
            "exam_status": sess.get("exam_status") or "Scheduled",
            "has_oral": has_oral,
            "total_candidates": total_candidates,
            "written_graded": written_graded,
            "written_approved": written_approved,
            "written_decided": written_decided,
            "written_passed": written_passed,
            "oral_graded": oral_graded,
            "oral_approved": oral_approved,
            "final_approved": final_approved,
            "step": step,
            "step_label": step_label,
            "step_badge": step_badge
        })

    return result
