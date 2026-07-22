import frappe
from frappe.model.workflow import apply_workflow

ACTION_MAP = {
    "تكليف بنشاط": "إحالة نشاط",
    "تكليف معتمد": "إعتماد نشاط",
    "نشاط مكتمل": "مكتمل",
}

EXPECTED_STATE = {
    "تكليف بنشاط": "نشاط محال",
    "تكليف معتمد": "نشاط معتمد",
    "نشاط مكتمل": "نشاط مكتمل",
}


def sync_active_to_maktab(doc, method=None):

   
    # لا تنفذ إذا لم تتغير حالة الـ Workflow
    old_doc = doc.get_doc_before_save()
    if old_doc and old_doc.workflow_state_wa == doc.workflow_state_wa:
        return

    if not doc.en:
        return

    action = ACTION_MAP.get(doc.workflow_state_wa)
    if not action:
        return

    mak_doc = frappe.get_doc("mak_taq", doc.en)

    expected = EXPECTED_STATE.get(doc.workflow_state_wa)

    if mak_doc.workflow_state_makteb == expected:
        return

    apply_workflow(mak_doc, action)