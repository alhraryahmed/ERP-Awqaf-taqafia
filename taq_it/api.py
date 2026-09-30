# -*- coding: utf-8 -*-
"""
وحدة واجهة برمجة التطبيقات (Whitelisted API Engine) لتطبيق taq_it
تجمع كافة إحصاءات اللوحات في استعلامات SQL مجمعة فائقة الأداء (Single Query Execution)
"""

import frappe
from urllib.parse import quote
from frappe.utils import flt


@frappe.whitelist()
def get_print_actions():
    """
    Returns enabled print actions ordered by sort_order.
    Checks waed_print_action doctype and falls back to standard print actions.
    """
    for dt in ["waed_print_action", "Waed Print Action"]:
        if frappe.db.exists("DocType", dt) or frappe.db.table_exists(dt):
            try:
                actions = frappe.get_all(
                    dt,
                    filters={"enabled": 1},
                    fields=[
                        "title",
                        "target_doctype",
                        "print_format",
                        "sort_order",
                    ],
                    order_by="sort_order asc",
                )
                if actions:
                    return actions
            except Exception:
                pass

    # Default fallback print actions
    return [
        {
            "title": "بيانات الواعظ",
            "target_doctype": "waed_info",
            "print_format": "waez_data_doc",
            "sort_order": 1,
        },
        {
            "title": "نتيجة الامتحان",
            "target_doctype": "exam_result",
            "print_format": "result",
            "sort_order": 2,
        },
    ]


@frappe.whitelist()
def get_print_url(source_doctype, source_name, target_doctype, print_format):
    """
    Build Print Preview URL for any configured print action.
    """
    if not source_doctype or not source_name:
        frappe.throw("Source document is required.")

    if not target_doctype:
        frappe.throw("Target DocType is required.")

    if not print_format:
        frappe.throw("Print Format is required.")

    frappe.has_permission(
        source_doctype,
        "read",
        doc=source_name,
        throw=True,
    )

    target_name = source_name

    if target_doctype == "exam_result":
        frappe.has_permission(
            "exam_result",
            "read",
            throw=True,
        )

        if source_doctype == "waed_info":
            target_name = frappe.db.get_value(
                "exam_result",
                {"waed": source_name, "docstatus": ["!=", 2]},
                "name",
                order_by="creation desc",
            )

            if not target_name:
                frappe.throw("لا توجد نتيجة امتحان لهذا الواعظ.")

    if not frappe.db.exists(target_doctype, target_name):
        frappe.throw("المستند المطلوب غير موجود.")

    return (
        frappe.utils.get_url()
        + "/printview?"
        + f"doctype={quote(str(target_doctype))}"
        + f"&name={quote(str(target_name))}"
        + f"&format={quote(str(print_format))}"
        + "&no_letterhead=0"
        + "&trigger_print=0"
    )


# ==============================================================================
# 1. لوحة قسم الوعاظ والواعظات (Waed & Female Waed Dashboard API)
# ==============================================================================
@frappe.whitelist()
def get_dashboard_stats(gender="Male"):
    """
    استدعاء موحد عالي السرعة للوحة الوعاظ أو الواعظات
    :param gender: 'Male' لقسم الوعاظ أو 'Female' لقسم الواعظات
    """
    try:
        has_gender_field = frappe.db.has_column("waed_info", "gender")

        if has_gender_field and gender:
            if gender in ["Male", "ذكر"]:
                gender_clause = "(gender IS NULL OR gender = '' OR gender IN ('Male', 'ذكر'))"
            elif gender in ["Female", "أنثى"]:
                gender_clause = "gender IN ('Female', 'أنثى')"
            else:
                gender_clause = f"gender = '{frappe.db.escape(gender)}'"

            status_rows = frappe.db.sql(f"""
                SELECT 
                    COALESCE(NULLIF(TRIM(waed_status), ''), 'New') as status,
                    COUNT(name) as total_count
                FROM `tabwaed_info`
                WHERE {gender_clause}
                GROUP BY waed_status
            """, as_dict=True)
        else:
            status_rows = frappe.db.sql("""
                SELECT 
                    COALESCE(NULLIF(TRIM(waed_status), ''), 'New') as status,
                    COUNT(name) as total_count
                FROM `tabwaed_info`
                GROUP BY waed_status
            """, as_dict=True)

        status_counts = {}
        total = 0
        for row in status_rows:
            st = row["status"]
            cnt = int(row["total_count"] or 0)
            status_counts[st] = status_counts.get(st, 0) + cnt
            total += cnt

        # عدد مجموعات الامتحانات المجدولة
        exam_gender_filter = {}
        if frappe.db.has_column("exam_group_date", "target_gender") and gender:
            exam_gender_filter["target_gender"] = ["in", ["Male", "ذكر"]] if gender in ["Male", "ذكر"] else ["in", ["Female", "أنثى"]]

        exam_groups = frappe.db.count("exam_group_date", dict({"exam_status": "Scheduled"}, **exam_gender_filter))

        # إحصاءات المتابعات الميدانية (Followups)
        incomplete_filter = {"waed_status": ["in", ["New", "Scheduling an appointment"]]}
        if has_gender_field and gender:
            incomplete_filter["gender"] = ["in", ["Male", "ذكر"]] if gender in ["Male", "ذكر"] else ["in", ["Female", "أنثى"]]

        incomplete_tasks = frappe.db.count("waed_info", incomplete_filter)
        
        in_progress_exams = frappe.db.count("exam_group_date", dict({
            "exam_status": ["in", ["Written In Progress", "Oral In Progress"]]
        }, **exam_gender_filter))

        # الملفات غير المكتملة (Missing Profile Data)
        missing_count = 0
        meta = frappe.get_meta("waed_info")
        fields = [f.fieldname for f in meta.fields] if meta else []
        
        check_fields = []
        for f in ["phone", "mobile", "national_id", "national", "address"]:
            if f in fields:
                check_fields.append(f"`{f}` IS NULL OR `{f}` = ''")

        if check_fields:
            gender_condition = ""
            if has_gender_field and gender:
                g_clause = "gender IN ('Male', 'ذكر') OR gender IS NULL OR gender = ''" if gender in ["Male", "ذكر"] else "gender IN ('Female', 'أنثى')"
                gender_condition = f"AND ({g_clause})"

            where_clause = " OR ".join(check_fields)
            missing_res = frappe.db.sql(f"""
                SELECT COUNT(name) as cnt 
                FROM `tabwaed_info` 
                WHERE ({where_clause}) {gender_condition}
            """, as_dict=True)
            if missing_res:
                missing_count = int(missing_res[0]["cnt"] or 0)

        return {
            "success": True,
            "total": total,
            "status_counts": status_counts,
            "exam_groups": exam_groups,
            "followups": {
                "incomplete": incomplete_tasks,
                "in_progress_exams": in_progress_exams,
                "missing_profile": missing_count
            }
        }
    except Exception as e:
        frappe.log_error(title="taq_it API Error: get_dashboard_stats", message=str(e))
        return {
            "success": False,
            "error": str(e)
        }


# ==============================================================================
# 2. لوحة قسم الامتحانات (Exams Dashboard API)
# ==============================================================================
@frappe.whitelist()
def get_exam_dashboard_stats(gender=None):
    """
    استدعاء مجمّع واحد عالي الأداء لكافة إحصاءات قسم الامتحانات
    """
    try:
        # 1. عدد نماذج الامتحانات
        forms_count = frappe.db.count("exam_form")

        # 2. فحص وجود عمود target_gender في جدول tabexam_group_date
        has_gender_col = frappe.db.has_column("exam_group_date", "target_gender")
        
        where_clause = "1=1"

        if has_gender_col and gender:
            if gender in ["Male", "ذكر"]:
                where_clause = "(target_gender IS NULL OR target_gender = '' OR target_gender IN ('Male', 'ذكر'))"
            elif gender in ["Female", "أنثى"]:
                where_clause = "target_gender IN ('Female', 'أنثى')"

        # 3. تجميع مجموعات الامتحانات حسب الحالة
        exam_rows = frappe.db.sql(f"""
            SELECT 
                COALESCE(NULLIF(TRIM(exam_status), ''), 'Scheduled') as status,
                COUNT(name) as total_count
            FROM `tabexam_group_date`
            WHERE {where_clause}
            GROUP BY exam_status
        """, as_dict=True)

        exam_counts = {
            "Scheduled": 0,
            "Written In Progress": 0,
            "Oral In Progress": 0,
            "Completed": 0
        }
        total_exams = 0

        for row in exam_rows:
            st = row["status"]
            cnt = int(row["total_count"] or 0)
            exam_counts[st] = cnt
            total_exams += cnt

        # 4. أقرب موعد امتحان قادم (فحص عمود exam_day أو date)
        date_col = "exam_day" if frappe.db.has_column("exam_group_date", "exam_day") else "creation"
        next_exam = frappe.db.sql(f"""
            SELECT `{date_col}` as exam_date 
            FROM `tabexam_group_date`
            WHERE (exam_status = 'Scheduled' OR exam_status = 'مجدول') AND `{date_col}` >= CURDATE() AND {where_clause}
            ORDER BY `{date_col}` ASC 
            LIMIT 1
        """, as_dict=True)

        if not next_exam:
            next_exam = frappe.db.sql(f"""
                SELECT `{date_col}` as exam_date 
                FROM `tabexam_group_date`
                WHERE (exam_status = 'Scheduled' OR exam_status = 'مجدول') AND {where_clause}
                ORDER BY `{date_col}` ASC 
                LIMIT 1
            """, as_dict=True)

        next_date_str = str(next_exam[0]["exam_date"]) if next_exam and next_exam[0].get("exam_date") else None

        return {
            "success": True,
            "forms": forms_count,
            "total": total_exams,
            "scheduled": exam_counts.get("Scheduled", 0),
            "written": exam_counts.get("Written In Progress", 0),
            "oral": exam_counts.get("Oral In Progress", 0),
            "completed": exam_counts.get("Completed", 0),
            "inProgress": exam_counts.get("Written In Progress", 0) + exam_counts.get("Oral In Progress", 0),
            "next_exam_date": next_date_str
        }
    except Exception as e:
        frappe.log_error(title="taq_it API Error: get_exam_dashboard_stats", message=str(e))
        return {
            "success": False,
            "error": str(e)
        }


# ==============================================================================
# 3. لوحة الأنشطة والفاعليات (Activities Dashboard API)
# ==============================================================================
@frappe.whitelist()
def get_active_dashboard_stats():
    """
    استدعاء مجمّع واحد للوحة الأنشطة والمكاتب والوعاظ
    """
    try:
        completed = frappe.db.count("active_taq")
        offices = frappe.db.count("mak_taq")
        preachers_res = frappe.db.sql(
            "SELECT COUNT(DISTINCT naa) as cnt FROM `tabactive_taq` WHERE naa IS NOT NULL AND naa != ''",
            as_dict=True
        )
        preachers = int(preachers_res[0]["cnt"]) if (preachers_res and preachers_res[0].get("cnt")) else frappe.db.count("waed_info")

        # توزيع أعلى المكاتب نشاطاً
        offices_chart = frappe.db.sql("""
            SELECT 
                COALESCE(NULLIF(TRIM(ma), ''), 'غير محدد') as label,
                COUNT(name) as value
            FROM `tabmak_taq`
            GROUP BY ma
            ORDER BY value DESC
            LIMIT 5
        """, as_dict=True)

        # توزيع أعلى الوعاظ نشاطاً
        preachers_chart = frappe.db.sql("""
            SELECT 
                COALESCE(NULLIF(TRIM(naa), ''), 'عام / غير محدد') as label,
                COUNT(name) as value
            FROM `tabactive_taq`
            GROUP BY naa
            ORDER BY value DESC
            LIMIT 5
        """, as_dict=True)

        return {
            "success": True,
            "counts": {
                "completed": completed,
                "offices": offices,
                "preachers": preachers
            },
            "charts": {
                "offices": offices_chart,
                "preachers": preachers_chart
            }
        }
    except Exception as e:
        frappe.log_error(title="taq_it API Error: get_active_dashboard_stats", message=str(e))
        return {
            "success": False,
            "error": str(e)
        }