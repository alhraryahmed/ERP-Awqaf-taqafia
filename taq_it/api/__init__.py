import frappe


@frappe.whitelist()
def get_print_actions():
    """
    Returns enabled print actions ordered by sort_order.
    """

    return frappe.get_all(
        "waed_print_action",
        filters={"enabled": 1},
        fields=[
            "title",
            "target_doctype",
            "print_format",
            "sort_order",
        ],
        order_by="sort_order asc",
    )


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

    # صلاحيات قراءة المستند الأصلي
    frappe.has_permission(
        source_doctype,
        "read",
        doc=source_name,
        throw=True,
    )

    # --------------------------------------------------
    # إذا كان الهدف هو نفس المستند
    # --------------------------------------------------

    target_name = source_name

    # --------------------------------------------------
    # إذا كانت الطباعة من exam_result
    # --------------------------------------------------

    if target_doctype == "exam_result":

        frappe.has_permission(
            "exam_result",
            "read",
            throw=True,
        )

        target_name = frappe.db.get_value(
            "exam_result",
            {
                "waed": source_name
            },
            "name",
            order_by="creation desc",
        )

        if not target_name:
            frappe.throw("لا توجد نتيجة امتحان لهذا الواعظ.")

    # --------------------------------------------------
    # التأكد أن المستند موجود
    # --------------------------------------------------

    if not frappe.db.exists(target_doctype, target_name):
        frappe.throw("المستند المطلوب غير موجود.")

    # --------------------------------------------------
    # إنشاء رابط Print Preview
    # --------------------------------------------------

    return (
        frappe.utils.get_url()
        + "/printview?"
        + f"doctype={target_doctype}"
        + f"&name={target_name}"
        + f"&format={print_format}"
        + "&no_letterhead=0"
        + "&trigger_print=0"
    )


# ==============================================================================
# 1. لوحة قسم الوعاظ والواعظات (Waed & Female Waed Dashboard API)
# ==============================================================================
@frappe.whitelist()
def get_dashboard_stats(gender="Male"):
    try:
        has_gender_field = frappe.db.has_column("waed_info", "gender")
        if has_gender_field and gender:
            status_rows = frappe.db.sql("""
                SELECT 
                    COALESCE(NULLIF(TRIM(waed_status), ''), 'New') as status,
                    COUNT(name) as total_count
                FROM `tabwaed_info`
                WHERE gender = %s
                GROUP BY waed_status
            """, (gender,), as_dict=True)
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
            status_counts[st] = cnt
            total += cnt
        exam_groups = frappe.db.count("exam_group_date", {"exam_status": "Scheduled"})
        incomplete_filter = {"waed_status": ["in", ["New", "Scheduling an appointment"]]}
        if has_gender_field and gender:
            incomplete_filter["gender"] = gender
        incomplete_tasks = frappe.db.count("waed_info", incomplete_filter)
        in_progress_exams = frappe.db.count("exam_group_date", {
            "exam_status": ["in", ["Written In Progress", "Oral In Progress"]]
        })
        missing_count = 0
        meta = frappe.get_meta("waed_info")
        fields = [f.fieldname for f in meta.fields] if meta else []
        
        check_fields = []
        for f in ["phone", "mobile", "national_id", "national", "address"]:
            if f in fields:
                check_fields.append(f"`{f}` IS NULL OR `{f}` = ''")
        if check_fields:
            gender_condition = f"AND gender = '{gender}'" if (has_gender_field and gender) else ""
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
        frappe.log_error(f"Error in taq_it.api.get_dashboard_stats: {str(e)}", "taq_it API Error")
        return {"success": False, "error": str(e)}
# ==============================================================================
# 2. لوحة قسم الامتحانات (Exams Dashboard API)
# ==============================================================================
@frappe.whitelist()
def get_exam_dashboard_stats():
    try:
        forms_count = frappe.db.count("exam_form")
        exam_rows = frappe.db.sql("""
            SELECT 
                COALESCE(NULLIF(TRIM(exam_status), ''), 'Scheduled') as status,
                COUNT(name) as total_count
            FROM `tabexam_group_date`
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
        # اكتشاف حقل التاريخ ديناميكياً وبأمان
        next_date_str = None
        try:
            meta = frappe.get_meta("exam_group_date")
            date_fields = [f.fieldname for f in meta.fields if f.fieldtype in ("Date", "Datetime")] if meta else []
            
            date_field = None
            for candidate in ["exam_date", "date", "date_of_exam", "start_date", "posting_date"]:
                if candidate in date_fields or frappe.db.has_column("exam_group_date", candidate):
                    date_field = candidate
                    break
            
            if not date_field and date_fields:
                date_field = date_fields[0]
                
            if date_field:
                next_exam = frappe.db.sql(f"""
                    SELECT `{date_field}` as exam_dt 
                    FROM `tabexam_group_date`
                    WHERE exam_status = 'Scheduled' AND `{date_field}` >= CURDATE()
                    ORDER BY `{date_field}` ASC 
                    LIMIT 1
                """, as_dict=True)
                if next_exam and next_exam[0].get("exam_dt"):
                    next_date_str = str(next_exam[0]["exam_dt"])
        except Exception:
            next_date_str = None
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
        frappe.log_error(f"Error in taq_it.api.get_exam_dashboard_stats: {str(e)}", "taq_it API Error")
        return {"success": False, "error": str(e)}
# ==============================================================================
# 3. لوحة الأنشطة والفاعليات (Activities Dashboard API)
# ==============================================================================
@frappe.whitelist()
def get_active_dashboard_stats():
    try:
        completed = frappe.db.count("active_taq")
        offices = frappe.db.count("mak_taq")
        preachers = frappe.db.count("active_taq")
        offices_chart = frappe.db.sql("""
            SELECT 
                COALESCE(NULLIF(TRIM(ma), ''), 'غير محدد') as label,
                COUNT(name) as value
            FROM `tabmak_taq`
            GROUP BY ma
            ORDER BY value DESC
            LIMIT 5
        """, as_dict=True)
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
        frappe.log_error(f"Error in taq_it.api.get_active_dashboard_stats: {str(e)}", "taq_it API Error")
        return {"success": False, "error": str(e)}