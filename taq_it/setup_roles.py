import frappe

ROLES = [
    "مدير إدارة الشؤون الثقافية",
    "رئيس قسم التقويم والقياس",
    "مشرف شؤون الوعاظ",
    "مشرفة شؤون الواعظات",
    "مدخل بيانات الوعاظ",
    "مدخلة بيانات الواعظات",
    "مشرف لجان امتحانات الوعاظ",
    "مشرفة لجان امتحانات الواعظات",
    "مشرف رصد الامتحانات",
    "معتمد نتائج الامتحانات",
    "مفتش مساجد وخطب الجمعة",
    "مفتشة مصليات ومراكز نسائية",
    "مشرف الأنشطة والبرامج الدعوية",
]

@frappe.whitelist()
def setup_custom_roles():
    """
    Safely seeds all required Awqaf Taqafia roles into Frappe DB.
    Works automatically on 'bench migrate' via after_migrate hook,
    and can also be run manually via 'bench execute'.
    """
    created = []
    for role_name in ROLES:
        if not frappe.db.exists("Role", role_name):
            role = frappe.get_doc({
                "doctype": "Role",
                "role_name": role_name,
                "desk_access": 1,
                "is_custom": 1
            })
            role.insert(ignore_permissions=True)
            created.append(role_name)
    
    frappe.db.commit()
    msg = f"Created {len(created)} roles: {', '.join(created)}" if created else "All custom roles already exist in the database."
    print(msg)
    return msg
