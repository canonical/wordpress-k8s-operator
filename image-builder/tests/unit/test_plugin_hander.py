import unittest
from unittest import mock

import plugin_handler


class testWrapper(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    @mock.patch("plugin_handler.logging")
    def test_team_mapper(self, foo):
        given = ",".join(
            [
                "canonical-sysadmins=administrator",
                "canonical-website-editors=editor",
                "canonical-website-admins=administrator",
                "launchpad=editor",
            ]
        )
        want = "".join(
            [
                """a:4:{i:1;O:8:"stdClass":4:{s:2:"id";i:1;s:4:"team";s:19:"canonical-sysadmins";""",
                """s:4:"role";s:13:"administrator";s:6:"server";s:1:"0";}""",
                """i:2;O:8:"stdClass":4:{s:2:"id";i:2;s:4:"team";s:25:"canonical-website-editors";""",
                """s:4:"role";s:6:"editor";s:6:"server";s:1:"0";}""",
                """i:3;O:8:"stdClass":4:{s:2:"id";i:3;s:4:"team";s:24:"canonical-website-admins";""",
                """s:4:"role";s:13:"administrator";s:6:"server";s:1:"0";}""",
                """i:4;O:8:"stdClass":4:{s:2:"id";i:4;s:4:"team";s:9:"launchpad";""",
                """s:4:"role";s:6:"editor";s:6:"server";s:1:"0";}}""",
            ]
        )
        got = plugin_handler.encode_team_map(given)
        self.assertEqual(got, want)
