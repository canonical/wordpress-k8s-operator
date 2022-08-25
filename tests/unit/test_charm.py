#!/usr/bin/env python3

import copy
import mock
import unittest

from unittest.mock import Mock

from charm import WordpressCharm
from wordpress import WORDPRESS_SECRETS
from ops import testing
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
)

from test_wordpress import (
    TEST_MODEL_CONFIG_MINIMAL,
    TEST_MODEL_CONFIG_FULL,
)


class TestWordpressCharm(unittest.TestCase):

    test_model_config = TEST_MODEL_CONFIG_FULL
    test_model_config_minimal = TEST_MODEL_CONFIG_MINIMAL

    def setUp(self):
        self.harness = testing.Harness(WordpressCharm)
        self.addCleanup(self.harness.cleanup)
        self._leadership_data = {}
        self.leadership_patch = mock.patch.multiple(
            "leadership.LeadershipSettings",
            __getitem__ = self._leadership_data.get,
            __setitem__ = lambda this, key, value: self._leadership_data.update({key: value}),
            setdefault = self._leadership_data.setdefault
        )
        self.leadership_patch.start()
        self.harness.begin()
        self.harness.update_config(copy.deepcopy(self.test_model_config))


    def tearDown(self) -> None:
        self.leadership_patch.stop()

    def setup_db_relation(self):
        # Add a relation and remote unit providing connection details.
        # TODO: ops-lib-mysql should have a helper to set the relation data.
        relid = self.harness.add_relation("db", "mysql")
        self.harness.add_relation_unit(relid, "mysql/0")
        self.harness.update_relation_data(relid, "mysql/0", {
            "database": "wpdbname",
            "host": "hostname.local",
            "port": "3306",
            "user": "wpuser",
            "password": "s3cret",
            "root_password": "sup3r_s3cret",
        })
        return relid

    def test_db_relation(self):
        # Charm starts with no relation, defaulting to using db
        # connection details from the charm config.
        charm = self.harness.charm
        self.assertEqual(charm.state.db_host, TEST_MODEL_CONFIG_FULL["db_host"])
        self.assertEqual(charm.state.db_name, TEST_MODEL_CONFIG_FULL["db_name"])
        self.assertEqual(charm.state.db_user, TEST_MODEL_CONFIG_FULL["db_user"])
        self.assertEqual(charm.state.db_password, TEST_MODEL_CONFIG_FULL["db_password"])

        self.setup_db_relation()

        # charm.db.on.database_changed fires here and is handled, updating state.
        self.assertTrue(charm.state.has_db_relation)
        self.assertEqual(charm.state.db_host, "hostname.local")
        self.assertEqual(charm.state.db_name, "wpdbname")
        self.assertEqual(charm.state.db_user, "wpuser")
        self.assertEqual(charm.state.db_password, "s3cret")


    def test_get_wordpress_secrets(self):
        self.harness.set_leader()
        wp_secrets = self.harness.charm._wordpress_secrets
        for key in WORDPRESS_SECRETS:
            self.assertIsInstance(wp_secrets[key], str)
            self.assertEqual(len(wp_secrets[key]), 64)


    def test_get_initial_password(self):
        self.harness.charm.leader_data = {"initial_password": "supersekrit"}
        self.assertEqual(self.harness.charm._get_initial_password(), "supersekrit")
        # Now test with no password, but not leader.
        self.harness.charm.leader_data = {"initial_password": ""}
        self.harness.set_leader(False)
        self.assertEqual(self.harness.charm._get_initial_password(), "")
        # And with no password, but is leader.
        self.harness.charm.leader_data = {"initial_password": ""}
        self.harness.set_leader(True)
        self.assertEqual(len(self.harness.charm._get_initial_password()), 24)

    def test_on_get_initial_password_action(self):
        action_event = Mock()
        # First test with no initial password set.
        with mock.patch.object(self.harness.charm, "_get_initial_password") as get_initial_password:
            get_initial_password.return_value = ""
            self.harness.charm._on_get_initial_password_action(action_event)
            self.assertEqual(action_event.fail.call_args, mock.call("Initial password has not been set yet."))
        # Now test with initial password set.
        with mock.patch.object(self.harness.charm, "_get_initial_password") as get_initial_password:
            get_initial_password.return_value = "passwd"
            self.harness.charm._on_get_initial_password_action(action_event)
            self.assertEqual(action_event.set_results.call_args, mock.call({"password": "passwd"}))
