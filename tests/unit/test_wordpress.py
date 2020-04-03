import unittest
import string
import sys

sys.path.append("src")

import charm  # noqa: E402


class HelperTest(unittest.TestCase):
    def test_password_generator(self):
        password = charm.password_generator()
        self.assertEqual(len(password), 8)
        alphabet = string.ascii_letters + string.digits
        for char in password:
            self.assertTrue(char in alphabet)
