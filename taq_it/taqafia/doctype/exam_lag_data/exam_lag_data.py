import frappe
from frappe.model.document import Document
from datetime import datetime

class exam_lag_data(Document):

    def autoname(self):

        now = datetime.now()
        year = now.strftime("%Y")
        month = now.strftime("%m")

        # prefix ثابت للسنة
        prefix = f"Committee-{year}"

        # جلب آخر رقم داخل السنة فقط
        last = frappe.db.sql("""
            SELECT name
            FROM `tabexam_lag_data`
            WHERE name LIKE %s
            ORDER BY CAST(SUBSTRING_INDEX(name, '-', -1) AS UNSIGNED) DESC
            LIMIT 1
        """, (f"{prefix}-%",))

        if last:
            try:
                last_number = int(last[0][0].split("-")[-1])
                new_number = last_number + 1
            except:
                new_number = 1
        else:
            new_number = 1

        self.name = f"{prefix}-{month}-{str(new_number).zfill(2)}"