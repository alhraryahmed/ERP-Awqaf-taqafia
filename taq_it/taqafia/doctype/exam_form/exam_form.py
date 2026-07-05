# Copyright (c) 2026, ahmeed and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class exam_form(Document):
    def validate(self):
        self.validate_program_aspects()
        self.validate_exam_limits()
        self.validate_aspect_totals()

    def validate_program_aspects(self):
        if not self.program:
            return

        allowed_aspects = set(get_program_aspects(self.program))
        selected_aspects = {row.aspect for row in self.aspects if row.aspect}
        invalid_aspects = selected_aspects - allowed_aspects

        if invalid_aspects:
            frappe.throw(
                "These aspects do not belong to the selected program: {0}".format(
                    ", ".join(sorted(invalid_aspects))
                )
            )

    def validate_exam_limits(self):
        if self.max_score is not None and self.max_score < 0:
            frappe.throw("Max Score cannot be less than zero.")

        if self.success_rate is not None and not 0 <= self.success_rate <= 100:
            frappe.throw("Success Rate must be between 0 and 100.")

        if not self.max_score:
            return

        aspects_total = sum(row.max_grade or 0 for row in self.aspects)
        if aspects_total > self.max_score:
            frappe.throw(
                "Total aspects max grades ({0}) cannot exceed exam Max Score ({1}).".format(
                    aspects_total,
                    self.max_score,
                )
            )

    def validate_aspect_totals(self):
        for aspect_row in self.aspects:
            if not aspect_row.aspect:
                continue

            questions = [q for q in self.questions if q.aspect == aspect_row.aspect]

            total_grade = sum(q.max_grade or 0 for q in questions)
            question_count = len(questions)

            if aspect_row.question_count and question_count != aspect_row.question_count:
                frappe.throw(
                    "Question count for aspect '{0}' does not match.".format(
                        aspect_row.aspect
                    )
                )

            if aspect_row.max_grade and total_grade != aspect_row.max_grade:
                frappe.throw(
                    "Question grades total does not match aspect '{0}' max grade.".format(
                        aspect_row.aspect
                    )
                )


@frappe.whitelist()
def sync_exam_form(doc):
    frappe.has_permission("exam_form", "write", throw=True)

    if isinstance(doc, str):
        doc = frappe.parse_json(doc)

    old_questions = doc.get("questions", [])

    old_map = {}
    for q in old_questions:
        key = f"{q.get('aspect')}_{q.get('question_number')}"
        old_map[key] = q

    new_questions = []

    for aspect in doc.get("aspects", []):
        aspect_name = aspect.get("aspect")
        if not aspect_name:
            continue

        count = int(aspect.get("question_count") or 1)

        for i in range(1, count + 1):
            key = f"{aspect_name}_{i}"
            old = old_map.get(key)

            new_questions.append(
                {
                    "doctype": "exam_form_question",
                    "aspect": aspect_name,
                    "question_number": i,
                    "max_grade": old.get("max_grade") if old else 0,
                }
            )

    doc["questions"] = new_questions
    return doc


@frappe.whitelist()
def get_program_aspects(program_name):
    if not program_name:
        return []

    return frappe.get_all(
        "aspect_child",
        filters={
            "parent": program_name,
            "parenttype": "program",
            "parentfield": "table_sats",
        },
        pluck="aspect",
        order_by="idx asc",
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_filtered_program_aspects(doctype, txt, searchfield, start, page_len, filters):
    program_name = filters.get("program_name")

    if not program_name:
        return []

    allowed_aspects = frappe.get_all(
        "aspect_child",
        filters={
            "parent": program_name,
            "parenttype": "program",
            "parentfield": "table_sats",
        },
        pluck="aspect",
    )

    if not allowed_aspects:
        return []

    return frappe.db.sql(
        """
        SELECT name, aspect_name
        FROM `tabexam_aspect`
        WHERE name IN %(allowed_aspects)s
          AND (
              name LIKE %(txt)s
              OR aspect_name LIKE %(txt)s
          )
        ORDER BY aspect_name ASC
        LIMIT %(start)s, %(page_len)s
    """,
        {
            "allowed_aspects": allowed_aspects,
            "txt": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        },
    )
