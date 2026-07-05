import frappe
import re
from frappe.model.document import Document


class waed_info(Document):

    def autoname(self):
        namee = (self.namee or "").strip().lower()
        office = (self.office or "").strip().lower()

        namee = re.sub(r"\s+", "-", namee)
        office = re.sub(r"\s+", "-", office)

        # GLOBAL SERIES FIXED
        series_number = frappe.model.naming.make_autoname(".####")

        self.name = f"{namee}-{office}-{series_number}"