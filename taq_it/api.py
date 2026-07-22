import frappe


@frappe.whitelist()
def get_print_actions():
    """
    Returns enabled print actions ordered by sort_order.
    """

    return frappe.get_all(
        "Waed Print Action",
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
    import frappe


@frappe.whitelist()
def get_print_actions():

    return [
        {
            "title": "طباعة نموذج الوعد",
            "target_doctype": "waed_info",
            "print_format": "Waed Print Template"
        }
    ]


@frappe.whitelist()
def get_print_url(
    source_doctype,
    source_name,
    target_doctype,
    print_format
):

    return (
        "/api/method/frappe.utils.print_format.download_pdf"
        f"?doctype={target_doctype}"
        f"&name={source_name}"
        f"&format={print_format}"
    )