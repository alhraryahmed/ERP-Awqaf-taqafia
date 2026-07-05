# Copyright (c) 2025, ahmeed and Contributors
# See license.txt

# import frappe
from frappe.tests import IntegrationTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestloc_taq(IntegrationTestCase):
	"""
	Integration tests for loc_taq.
	Use this class for testing interactions between multiple components.
	"""

	pass
