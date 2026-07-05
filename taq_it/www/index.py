import frappe

def get_context(context):
    context.no_cache = 1

    context.upcoming = frappe.get_all(
        "active_taq",
        filters={"is_published": 1},
        fields=["name", "en", "da", "loc_mak"],
        limit=6,
        order_by="da desc"
    )

    context.ongoing = frappe.get_all(
        "active_taq",
        filters={"is_published": 1},
        fields=["name", "en", "da", "loc_mak"],
        limit=3
    )

    context.latest = frappe.get_all(
        "active_taq",
        filters={"is_published": 1},
        fields=["name", "en", "da", "loc_mak"],
        limit=6
    )

    return context