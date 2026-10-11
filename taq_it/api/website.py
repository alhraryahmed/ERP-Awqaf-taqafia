"""Public, read-only API for the external website.

All endpoints allow guests and only return display-safe fields.
Base URL: /api/method/taq_it.api.website.<function>
"""

import frappe
from frappe.utils import cint, getdate, today

CANCELLED_STATE = "نشاط ملغي"
MAX_PAGE_LENGTH = 100


def _page(limit, start):
	return min(cint(limit) or 20, MAX_PAGE_LENGTH), max(cint(start), 0)


def _department_names(names):
	names = {n for n in names if n}
	if not names:
		return {}
	return dict(
		frappe.get_all(
			"Department", filters={"name": ["in", list(names)]}, fields=["name", "department_name"], as_list=True
		)
	)


def _location_coords(loc_json):
	"""Return [lat, lng] from a Geolocation field, or None."""
	try:
		point = frappe.parse_json(loc_json)["features"][0]["geometry"]["coordinates"]
		return [point[1], point[0]]
	except Exception:
		return None


def _activity_filters(category=None, office=None, from_date=None, to_date=None, significant=None):
	filters = [["workflow_state_wa", "!=", CANCELLED_STATE], ["docstatus", "<", 2]]
	if category:
		filters.append(["ty", "=", category])
	if office:
		filters.append(["mak", "=", office])
	if from_date:
		filters.append(["da", ">=", getdate(from_date)])
	if to_date:
		filters.append(["da", "<=", getdate(to_date)])
	if cint(significant):
		filters.append(["significant_event", "=", 1])
	return filters


def _serialize_activities(rows):
	titles = dict(
		frappe.get_all(
			"mak_taq",
			filters={"name": ["in", [r.en for r in rows if r.en] or [""]]},
			fields=["name", "en_mak"],
			as_list=True,
		)
	)
	offices = _department_names(r.mak for r in rows)
	return [
		{
			"id": r.name,
			"title": titles.get(r.en) or r.en,
			"category": r.ty,
			"office": offices.get(r.mak) or r.mak,
			"office_id": r.mak,
			"date": r.da,
			"location": r.locc,
			"status": r.workflow_state_wa,
			"significant": bool(r.significant_event),
			"live_stream_url": r.live_stream_url,
		}
		for r in rows
	]


ACTIVITY_LIST_FIELDS = [
	"name", "en", "ty", "mak", "da", "locc", "workflow_state_wa", "significant_event", "live_stream_url",
]


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_activities(
	limit=20, start=0, category=None, office=None, from_date=None, to_date=None, significant=None, order="desc"
):
	limit, start = _page(limit, start)
	filters = _activity_filters(category, office, from_date, to_date, significant)
	rows = frappe.get_all(
		"active_taq",
		filters=filters,
		fields=ACTIVITY_LIST_FIELDS,
		order_by="da asc" if order == "asc" else "da desc",
		limit_start=start,
		limit_page_length=limit,
	)
	return {
		"data": _serialize_activities(rows),
		"total": frappe.db.count("active_taq", filters),
		"limit": limit,
		"start": start,
	}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_activity(id):
	doc = frappe.db.get_value("active_taq", id, ACTIVITY_LIST_FIELDS + ["target_audience", "over_view"], as_dict=True)
	if not doc or doc.workflow_state_wa == CANCELLED_STATE:
		raise frappe.DoesNotExistError

	activity = _serialize_activities([doc])[0]

	program = frappe.db.get_value("mak_taq", doc.en, ["da", "daa", "over_view", "target_audience"], as_dict=True) or {}
	activity.update(
		{
			"start_date": program.get("da") or doc.da,
			"end_date": program.get("daa"),
			"overview": program.get("over_view") or doc.over_view,
			"target_audience": program.get("target_audience") or doc.target_audience,
		}
	)

	if doc.locc:
		loc = frappe.db.get_value("loc_taq", doc.locc, "loc")
		activity["coordinates"] = _location_coords(loc)

	sessions = frappe.get_all(
		"Active Taq Preachers",
		filters={"parent": id, "parenttype": "active_taq"},
		fields=["preacher", "title", "lecture_time", "lecture_duration"],
		order_by="idx asc",
	)
	preachers = _preacher_cards([s.preacher for s in sessions])
	activity["sessions"] = [
		{
			"preacher": preachers.get(s.preacher),
			"topic": s.title,
			"time": s.lecture_time,
			"duration": s.lecture_duration,
		}
		for s in sessions
	]
	return activity


def _preacher_cards(ids):
	ids = [i for i in set(ids) if i]
	if not ids:
		return {}
	rows = frappe.get_all(
		"waed_info", filters={"name": ["in", ids]}, fields=["name", "namee", "office", "profile_picture"]
	)
	return {
		r.name: {"id": r.name, "name": r.namee, "office": r.office, "photo": r.profile_picture} for r in rows
	}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_preachers(limit=20, start=0, search=None, office=None):
	limit, start = _page(limit, start)
	filters = {"docstatus": ["<", 2]}
	if office:
		filters["office"] = office
	if search:
		filters["namee"] = ["like", f"%{search}%"]
	rows = frappe.get_all(
		"waed_info",
		filters=filters,
		fields=["name", "namee", "office", "profile_picture"],
		order_by="namee asc",
		limit_start=start,
		limit_page_length=limit,
	)
	return {
		"data": [{"id": r.name, "name": r.namee, "office": r.office, "photo": r.profile_picture} for r in rows],
		"total": frappe.db.count("waed_info", filters),
		"limit": limit,
		"start": start,
	}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_categories():
	return frappe.get_all("tyac_taq", fields=["name as id", "na as title"], order_by="na asc")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_offices():
	used = frappe.get_all("active_taq", filters={"mak": ["is", "set"]}, pluck="mak", distinct=True)
	names = _department_names(used)
	return [{"id": k, "title": v} for k, v in sorted(names.items(), key=lambda x: x[1] or "")]


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_locations():
	"""Locations with coordinates, for a map."""
	rows = frappe.get_all("loc_taq", fields=["name", "name_loc", "loc"])
	return [{"id": r.name, "title": r.name_loc, "coordinates": _location_coords(r.loc)} for r in rows]


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_home():
	"""Everything the homepage needs in one request."""
	base = _activity_filters()
	upcoming = frappe.get_all(
		"active_taq",
		filters=base + [["da", ">=", today()]],
		fields=ACTIVITY_LIST_FIELDS,
		order_by="da asc",
		limit_page_length=6,
	)
	latest = frappe.get_all(
		"active_taq",
		filters=base + [["da", "<", today()]],
		fields=ACTIVITY_LIST_FIELDS,
		order_by="da desc",
		limit_page_length=6,
	)
	return {
		"stats": {
			"activities": frappe.db.count("active_taq", base),
			"preachers": frappe.db.count("waed_info", {"docstatus": ["<", 2]}),
			"offices": len(frappe.get_all("active_taq", filters={"mak": ["is", "set"]}, pluck="mak", distinct=True)),
		},
		"upcoming": _serialize_activities(upcoming),
		"latest": _serialize_activities(latest),
	}
