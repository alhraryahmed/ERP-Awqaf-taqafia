# Copyright (c) 2026, ahmeed and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class exam_result_question(Document):
    def validate(self):
        if self.score is None:
            return

        if self.score < 0:
            frappe.throw(
                "Score for question {0} cannot be less than zero.".format(
                    self.question_number
                )
            )

        if self.score > self.max_grade:
            frappe.throw(
                "Score for question {0} cannot exceed max grade ({1}).".format(
                    self.question_number, self.max_grade
                )
            )
