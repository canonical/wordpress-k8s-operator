# Copyright 2022 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

import json
import unittest
import unittest.mock

import ops.pebble
import ops.testing

from charm import WordpressCharm
from exceptions import WordPressBlockedStatusException, WordPressWaitingStatusException
from tests.unit.pebble_mock import WordpressPatch


class TestWordpressK8s(unittest.TestCase):
    def setUp(self):
        self.patch = WordpressPatch()
        self.patch.start()
        self.harness = ops.testing.Harness(WordpressCharm)
        self.addCleanup(self.harness.cleanup)
        self.app_name = "wordpress-k8s"

    def tearDown(self) -> None:
        self.patch.stop()

    def test_generate_wp_secret_keys(self):
        """
        arrange: no pre-condition.
        act: generate a group of WordPress secrets from scratch.
        assert: generated secrets should be safe.
        """
        self.harness.begin()

        secrets = self.harness.charm._generate_wp_secret_keys()
        self.assertIn(
            "default_admin_password", secrets, "wordpress should generate a default admin password"
        )
        del secrets["default_admin_password"]
        key_values = list(secrets.values())
        self.assertSetEqual(
            set(secrets.keys()),
            set(self.harness.charm._wordpress_secret_key_fields()),
            "generated wordpress secrets should contain all required fields",
        )
        self.assertEqual(
            len(key_values), len(set(key_values)), "no two secret values should be the same"
        )
        for value in key_values:
            self.assertFalse(
                value.isalnum() or len(value) < 64, "secret values should not be too simple"
            )

    def _setup_replica_consensus(self):
        replica_relation_id = self.harness.add_relation("wordpress-replica", self.app_name)
        self.harness.set_leader()
        self.harness.begin_with_initial_hooks()
        consensus = self.harness.get_relation_data(replica_relation_id, self.app_name)
        return consensus

    def test_replica_consensus(self):
        """
        arrange: deploy a new wordpress-k8s application.
        act: simulate peer relation creating and leader electing during the start of deployment.
        assert: units should reach consensus after leader elected.
        """
        self._setup_replica_consensus()

        self.assertTrue(
            self.harness.charm._replica_consensus_reached(),
            "units in application should reach consensus once leadership established",
        )

    def test_replica_consensus_stable_after_leader_reelection(self):
        """
        arrange: deploy a new wordpress-k8s application.
        act: simulate a leader re-election after application deployed.
        assert: consensus should not change.
        """
        replica_relation_id = self.harness.add_relation("wordpress-replica", self.app_name)
        non_leader_peer_name = "wordpress-k8s/1"
        self.harness.add_relation_unit(replica_relation_id, non_leader_peer_name)
        self.harness.begin_with_initial_hooks()

        self.assertFalse(
            self.harness.charm._replica_consensus_reached(),
            "units in application should not reach consensus before leadership established",
        )
        self.harness.set_leader()
        self.assertTrue(
            self.harness.charm._replica_consensus_reached(),
            "units in application should reach consensus once leadership established",
        )
        consensus = self.harness.get_relation_data(replica_relation_id, self.app_name)
        # The harness will emit a leader-elected event when calling ``set_leader(True)`` no matter
        # what the situation is, ``set_leader(False)`` does nothing here currently, just for the
        # aesthetic.
        self.harness.set_leader(False)
        self.harness.set_leader(True)
        self.assertDictEqual(
            consensus,
            self.harness.get_relation_data(replica_relation_id, self.app_name),
            "consensus once established should not change after leadership changed",
        )

    @staticmethod
    def _example_db_info():
        return {
            "host": "test_database_host",
            "database": "test_database_name",
            "user": "test_database_user",
            "password": "test_database_password",
            "port": "3306",
            "root_password": "test_root_password",
        }

    def _setup_db_relation(self, db_info):
        db_relation_id = self.harness.add_relation("db", "mysql")
        self.harness.add_relation_unit(db_relation_id, "mysql/0")
        self.harness.update_relation_data(db_relation_id, "mysql/0", db_info)
        return db_relation_id

    def test_mysql_relation(self):
        """
        arrange: no pre-condition.
        act: add and remove the database relation between WordPress application and mysql.
        assert: database info in charm state should change accordingly.
        """

        def get_db_info_from_state():
            return {
                "host": self.harness.charm.state.relation_db_host,
                "database": self.harness.charm.state.relation_db_name,
                "user": self.harness.charm.state.relation_db_user,
                "password": self.harness.charm.state.relation_db_password,
            }

        self.harness.begin_with_initial_hooks()

        self.assertSetEqual(
            {None},
            set(get_db_info_from_state().values()),
            "database info in charm state should not exist before database relation created",
        )

        db_info = self._example_db_info()
        db_relation_id = self._setup_db_relation(db_info)

        db_info_in_state = get_db_info_from_state()
        for db_info_key in db_info_in_state:
            self.assertEqual(
                db_info_in_state[db_info_key],
                db_info[db_info_key],
                "database info {} in charm state should be updated after database relation changed".format(
                    db_info_key
                ),
            )

        self.harness.remove_relation(db_relation_id)

        db_info_in_state = get_db_info_from_state()
        for db_info_key in db_info_in_state:
            self.assertIsNone(
                db_info_in_state[db_info_key],
                "database info {} should be reset to None after database relation broken".format(
                    db_info_key
                ),
            )

    def test_wp_config(self):
        """
        arrange: after WordPress application unit consensus has been reached.
        act: generate wp-config.php.
        assert: generated wp-config.php should be valid.
        """

        def in_same_line(content, *matches):
            for line in content.splitlines():
                if all(match in line for match in matches):
                    return True
            return False

        self.assertRaises(
            Exception,
            lambda _: self.harness.charm._gen_wp_config(),
            "generating a config before consensus should raise an exception for security reasons",
        )

        replica_consensus = self._setup_replica_consensus()
        wp_config = self.harness.charm._gen_wp_config()

        for secret_key in self.harness.charm._wordpress_secret_key_fields():
            secret_value = replica_consensus[secret_key]
            self.assertTrue(
                in_same_line(wp_config, "define(", secret_key.upper(), secret_value),
                "wp-config.php should contain a valid {}".format(secret_key),
            )

        db_info = self._example_db_info()
        self._setup_db_relation(db_info)
        wp_config = self.harness.charm._gen_wp_config()

        db_field_conversion = {
            "db_host": "host",
            "db_name": "database",
            "db_user": "user",
            "db_password": "password",
        }
        for db_info_field in ["db_host", "db_name", "db_user", "db_password"]:
            self.assertTrue(
                in_same_line(
                    wp_config,
                    "define(",
                    db_info_field.upper(),
                    db_info[db_field_conversion[db_info_field]],
                ),
                "wp-config.php should contain database setting {} from the db relation".format(
                    db_info_field
                ),
            )

        db_info_in_config = {
            "db_host": "config_db_host",
            "db_name": "config_db_name",
            "db_user": "config_db_user",
            "db_password": "config_db_password",
        }
        self.harness.update_config(db_info_in_config)
        wp_config = self.harness.charm._gen_wp_config()

        for db_info_field in db_info_in_config.keys():
            self.assertTrue(
                in_same_line(
                    wp_config, "define(", db_info_field.upper(), db_info_in_config[db_info_field]
                ),
                "db info in config should takes precedence over the db relation",
            )

    def test_wp_install_cmd(self):
        """
        arrange: no pre-condition.
        act: generate wp-cli command to install WordPress.
        assert: generated command should match current config and status.
        """
        consensus = self._setup_replica_consensus()
        install_cmd = self.harness.charm._wp_install_cmd()

        self.assertIn(
            "--admin_user=admin",
            install_cmd,
            'admin user should be "admin" with the default configuration',
        )
        self.assertIn(
            "--admin_password={}".format(consensus["default_admin_password"]),
            install_cmd,
            "admin password should be the same as the default_admin_password in peer relation data",
        )

        self.harness.update_config(
            {
                "initial_settings": """\
            user_name: test_admin_username
            admin_email: test@test.com
            admin_password: test_admin_password
            """
            }
        )
        install_cmd = self.harness.charm._wp_install_cmd()

        self.assertIn("--admin_user=test_admin_username", install_cmd)
        self.assertIn("--admin_email=test@test.com", install_cmd)
        self.assertIn("--admin_password=test_admin_password", install_cmd)

    def test_core_reconciliation_before_peer_relation_ready(self):
        """
        arrange: before peer relation established but after charm created
        act: run core reconciliation
        assert: core reconciliation should "fail" and status should be waiting
        """
        self.harness.begin_with_initial_hooks()

        with self.assertRaises(
                WordPressWaitingStatusException, msg="core reconciliation should fail"
        ):
            self.harness.charm._core_reconciliation()
        self.assertIsInstance(
            self.harness.model.unit.status,
            ops.charm.model.WaitingStatus,
            "unit should be in WaitingStatus",
        )
        self.assertIn(
            "unit consensus",
            self.harness.model.unit.status.message,
            "unit should wait for peer relation establishment right now",
        )

    def test_core_reconciliation_before_database_ready(self):
        """
        arrange: before database connection info ready but after peer relation established
        act: run core reconciliation
        assert: core reconciliation should "fail" and status should be waiting
        """
        self._setup_replica_consensus()

        with self.assertRaises(
                WordPressBlockedStatusException, msg="core reconciliation should fail"
        ):
            self.harness.charm._core_reconciliation()
        self.assertIsInstance(
            self.harness.model.unit.status,
            ops.charm.model.BlockedStatus,
            "unit should be in WaitingStatus",
        )
        self.assertIn(
            "db relation",
            self.harness.model.unit.status.message,
            "unit should wait for database connection info",
        )

    def test_core_reconciliation(self):
        """
        arrange: after peer relation established and database configured
        act: run core reconciliation
        assert: core reconciliation should update config files to match current config and
            application state
        """
        self._setup_replica_consensus()
        db_config = {
            "db_host": "config_db_host",
            "db_name": "config_db_name",
            "db_user": "config_db_user",
            "db_password": "config_db_password",
        }
        self.patch.database.prepare_database(
            host=db_config["db_host"],
            database=db_config["db_name"],
            user=db_config["db_user"],
            password=db_config["db_password"]
        )
        self.harness.update_config(db_config)

        self.assertTrue(
            self.patch.database.is_wordpress_installed(db_config["db_host"], db_config["db_name"]),
            "wordpress should be installed after core reconciliation",
        )

        db_config.update({"db_host": "config_db_host_2"})
        self.patch.database.prepare_database(
            host=db_config["db_host"],
            database=db_config["db_name"],
            user=db_config["db_user"],
            password=db_config["db_password"]
        )
        self.harness.update_config({"db_host": "config_db_host_2"})

        self.assertTrue(
            self.patch.database.is_wordpress_installed("config_db_host_2", db_config["db_name"]),
            "wordpress should be installed after database config changed",
        )

    @staticmethod
    def _gen_action_event_mock():
        event_mock = unittest.mock.MagicMock()
        event_mock.set_results = unittest.mock.MagicMock()
        event_mock.fail = unittest.mock.MagicMock()
        return event_mock

    def test_get_initial_password_action_before_replica_consensus(self):
        """
        arrange: before peer relation established but after charm created
        act: run get-initial-password action
        assert: get-initial-password action should fail
        """
        self.harness.begin_with_initial_hooks()
        event = self._gen_action_event_mock()
        self.harness.charm._on_get_initial_password_action(event)

        self.assertEqual(len(event.set_results.mock_calls), 0)
        self.assertEqual(len(event.fail.mock_calls), 1)

    def test_get_initial_password_action(self):
        """
        arrange: after peer relation established
        act: run get-initial-password action
        assert: get-initial-password action should success and return default admin password
        """
        consensus = self._setup_replica_consensus()
        event = self._gen_action_event_mock()
        self.harness.charm._on_get_initial_password_action(event)

        self.assertEqual(len(event.fail.mock_calls), 0)
        self.assertSequenceEqual(
            event.set_results.mock_calls,
            [unittest.mock.call({"password": consensus["default_admin_password"]})],
        )

    def test_theme_reconciliation(self):
        """
        arrange: after peer relation established and database ready
        act: update themes configuration
        assert: themes installed in WordPress should update according to the themes config
        """
        self._setup_replica_consensus()
        db_config = {
            "db_host": "config_db_host",
            "db_name": "config_db_name",
            "db_user": "config_db_user",
            "db_password": "config_db_password",
        }
        self.patch.database.prepare_database(
            host=db_config["db_host"],
            database=db_config["db_name"],
            user=db_config["db_user"],
            password=db_config["db_password"]
        )
        self.harness.update_config(db_config)

        self.assertEqual(
            self.patch.container.installed_themes,
            set(self.harness.charm._WORDPRESS_DEFAULT_THEMES),
            "installed themes should match the default installed themes "
            "with the default themes config",
        )

        self.harness.update_config({"themes": "123, abc"})

        self.assertEqual(
            self.patch.container.installed_themes,
            set(self.harness.charm._WORDPRESS_DEFAULT_THEMES + ["abc", "123"]),
            "adding themes to themes config should install trigger theme installation",
        )

        self.harness.update_config({"themes": "123"})

        self.assertEqual(
            self.patch.container.installed_themes,
            set(self.harness.charm._WORDPRESS_DEFAULT_THEMES + ["123"]),
            "removing themes from themes config should trigger theme deletion",
        )

    def test_plugin_reconciliation(self):
        """
        arrange: after peer relation established and database ready
        act: update plugins configuration
        assert: plugin installed in WordPress should update according to the plugin config
        """
        self._setup_replica_consensus()
        db_config = {
            "db_host": "config_db_host",
            "db_name": "config_db_name",
            "db_user": "config_db_user",
            "db_password": "config_db_password",
        }
        self.patch.database.prepare_database(
            host=db_config["db_host"],
            database=db_config["db_name"],
            user=db_config["db_user"],
            password=db_config["db_password"]
        )
        self.harness.update_config(db_config)

        self.assertEqual(
            self.patch.container.installed_plugins,
            set(self.harness.charm._WORDPRESS_DEFAULT_PLUGINS),
            "installed plugins should match the default installed plugins "
            "with the default plugins config",
        )

        self.harness.update_config({"plugins": "123, abc"})

        self.assertEqual(
            self.patch.container.installed_plugins,
            set(self.harness.charm._WORDPRESS_DEFAULT_PLUGINS + ["abc", "123"]),
            "adding plugins to plugins config should install trigger plugin installation",
        )

        self.harness.update_config({"plugins": "123"})

        self.assertEqual(
            self.patch.container.installed_plugins,
            set(self.harness.charm._WORDPRESS_DEFAULT_PLUGINS + ["123"]),
            "removing plugins from plugins config should trigger plugin deletion",
        )

    def _standard_plugin_test(
            self,
            plugin,
            plugin_config,
            excepted_options,
            excepted_options_after_removed=None,
            additional_check_after_install=None,
    ):
        plugin_config_keys = list(plugin_config.keys())
        self._setup_replica_consensus()
        db_config = {
            "db_host": "config_db_host",
            "db_name": "config_db_name",
            "db_user": "config_db_user",
            "db_password": "config_db_password",
        }
        self.patch.database.prepare_database(
            host=db_config["db_host"],
            database=db_config["db_name"],
            user=db_config["db_user"],
            password=db_config["db_password"]
        )

        self.harness.update_config(db_config)

        self.harness.update_config(plugin_config)

        database_instance = self.patch.database.get_wordpress_database(host="config_db_host",
                                                                       database="config_db_name")
        self.assertEqual(
            database_instance.activated_plugins,
            {plugin} if isinstance(plugin, str) else set(plugin),
            f"{plugin} should be activated after {plugin_config_keys} being set",
        )
        self.assertEqual(
            database_instance.options,
            excepted_options,
            f"options of plugin {plugin} should be set correctly",
        )

        if additional_check_after_install is not None:
            additional_check_after_install()

        self.harness.update_config({k: "" for k in plugin_config})
        self.assertEqual(
            database_instance.activated_plugins,
            set(),
            f"{plugin} should be deactivated after {plugin_config_keys} being reset",
        )
        self.assertEqual(
            database_instance.options,
            {} if excepted_options_after_removed is None else excepted_options_after_removed,
            f"{plugin} options should be removed after {plugin_config_keys} being reset",
        )

    def test_akismet_plugin(self):
        """
        arrange: after peer relation established and database ready
        act: update akismet plugin configuration
        assert: plugin should be activated with WordPress options being set correctly, and plugin
            should be deactivated with options removed after config being reset
        """
        self._standard_plugin_test(
            plugin="akismet",
            plugin_config={"wp_plugin_akismet_key": "test"},
            excepted_options={
                "akismet_strictness": "0",
                "akismet_show_user_comments_approved": "0",
                "wordpress_api_key": "test",
                "users_can_register": "0",
            },
            excepted_options_after_removed={"users_can_register": "0"},
        )

    def test_team_map(self):
        team_map = "site-sysadmins=administrator,site-editors=editor,site-executives=editor"
        option = WordpressCharm._encode_openid_team_map(team_map)
        self.assertEqual(
            option.replace(" ", "").replace("\n", ""),
            """array (
                  1 =>
                  (object) array(
                     'id' => 1,
                     'team' => 'site-sysadmins',
                     'role' => 'administrator',
                     'server' => '0',
                  ),
                  2 =>
                  (object) array(
                     'id' => 2,
                     'team' => 'site-editors',
                     'role' => 'editor',
                     'server' => '0',
                  ),
                  3 =>
                  (object) array(
                     'id' => 3,
                     'team' => 'site-executives',
                     'role' => 'editor',
                     'server' => '0',
                  ),
                )""".replace(
                " ", ""
            ).replace(
                "\n", ""
            ),
        )

    def test_openid_plugin(self):
        """
        arrange: after peer relation established and database ready
        act: update openid plugin configuration
        assert: plugin should be activated with WordPress options being set correctly, and plugin
            should be deactivated with options removed after config being reset
        """
        self._standard_plugin_test(
            plugin={"openid", "wordpress-launchpad-integration", "wordpress-teams-integration"},
            plugin_config={
                "wp_plugin_openid_team_map": "site-sysadmins=administrator,site-editors=editor,site-executives=editor"
            },
            excepted_options={"openid_required_for_registration": "1", "users_can_register": "1"},
            excepted_options_after_removed={"users_can_register": "0"},
        )
        self.assertTrue(
            self.patch.container.wp_eval_history[-1].startswith(
                "update_option('openid_teams_trust_list',"),
            "PHP function update_option should be invoked after openid plugin enabled",
        )

    def test_swift_plugin(self):
        """
        arrange: after peer relation established and database ready
        act: update openid plugin configuration
        assert: plugin should be activated with WordPress options being set correctly, and plugin
            should be deactivated with options removed after config being reset. Apache
            configuration for swift integration should be enabled after swift plugin activated
            and configuration should be disabled after swift plugin deactivated.
        """

        def additional_check_after_install():
            conf_found = False
            for file in self.patch.container.fs:
                if file.endswith("docker-php-swift-proxy.conf"):
                    conf_found = True
            assert conf_found

        self._standard_plugin_test(
            plugin="openstack-objectstorage-k8s",
            plugin_config={
                "wp_plugin_openstack-objectstorage_config": json.dumps(
                    {
                        "auth-url": "http://localhost/v3",
                        "bucket": "wordpress",
                        "password": "password",
                        "object-prefix": "wp-content/uploads/",
                        "region": "region",
                        "tenant": "tenant",
                        "domain": "domain",
                        "swift-url": "http://localhost:8080",
                        "username": "username",
                        "copy-to-swift": "1",
                        "serve-from-swift": "1",
                        "remove-local-file": "0",
                    }
                )
            },
            excepted_options={
                "object_storage": {
                    "auth-url": "http://localhost/v3",
                    "bucket": "wordpress",
                    "password": "password",
                    "object-prefix": "wp-content/uploads/",
                    "region": "region",
                    "tenant": "tenant",
                    "domain": "domain",
                    "swift-url": "http://localhost:8080",
                    "username": "username",
                    "copy-to-swift": "1",
                    "serve-from-swift": "1",
                    "remove-local-file": "0",
                },
                "users_can_register": "0",
            },
            excepted_options_after_removed={"users_can_register": "0"},
            additional_check_after_install=additional_check_after_install,
        )
