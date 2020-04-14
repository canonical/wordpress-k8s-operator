#!/usr/bin/env python3

import copy
import unittest
import sys

sys.path.append('lib')  # noqa
sys.path.append('src')  # noqa

from charm import WordpressK8sCharm
from ops import testing
from ops.model import BlockedStatus

from test_wordpress import TEST_MODEL_CONFIG


class TestWordpressK8sCharm(unittest.TestCase):

    test_model_config = TEST_MODEL_CONFIG

    def setUp(self):
        self.harness = testing.Harness(
            WordpressK8sCharm,
            meta='''
            name: wordpress
            ''',
        )

        self.harness.begin()
        self.harness.charm.model.config = copy.deepcopy(self.test_model_config)

    def test_is_config_valid(self):
        # Test a valid model config.
        want_true = self.harness.charm.is_valid_config()
        self.assertTrue(want_true)

        # Test for invalid model config.
        want_msg_fmt = "Missing required config: {}"
        want_keys = ("image", "db_host", "db_name", "db_user", "db_password")
        for wanted_key in want_keys:
            self.harness.charm.model.config[wanted_key] = ""
            want_false = self.harness.charm.is_valid_config()
            self.assertFalse(want_false)
            self.assertLogs(want_msg_fmt.format(wanted_key), level="INFO")
            self.harness.charm.model.config = copy.deepcopy(self.test_model_config)

        # Test for missing initial_settings in model config.
        self.harness.charm.model.config["initial_settings"] = ""
        want_false = self.harness.charm.is_valid_config()
        self.assertFalse(want_false)
        self.assertLogs("No initial_setting provided. Skipping first install.", level="INFO")
        self.harness.charm.model.config = copy.deepcopy(self.test_model_config)

        # Test unit status msg.
        for wanted_key in want_keys:
            self.harness.charm.model.config[wanted_key] = ""
        expected_msg = want_msg_fmt.format(" ".join(want_keys))
        self.harness.charm.is_valid_config()
        self.assertIsInstance(self.harness.charm.unit.status, BlockedStatus)
        self.assertEqual(self.harness.charm.unit.status.message, expected_msg)
        self.assertLogs(expected_msg, level="INFO")
