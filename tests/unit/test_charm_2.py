import re
import json
import unittest
import collections
import unittest.mock

import ops.pebble
import ops.testing
import mysql.connector

from charm import WordpressCharm
from exceptions import *


class WordpressMock:
    """WordPress wp-cli command run and database simulation system for unit tests"""
    def __init__(self):
        self._database = {}
        self._container_fs = {}
        self._database_credentials = {}
        self._themes = set(WordpressCharm._WORDPRESS_DEFAULT_THEMES)
        self._plugins = set(WordpressCharm._WORDPRESS_DEFAULT_PLUGINS)
        self._patch = None

    def _get_current_database_config(self):
        wp_config = self._container_fs.get(WordpressCharm._WP_CONFIG_PATH)
        if wp_config is None:
            return None
        db_info = {}
        for db_key in ('db_host', 'db_name', 'db_user', 'db_password'):
            db_value = re.findall(f"define\\( '{db_key.upper()}', '([^']+)' \\);", wp_config)
            if not db_value:
                raise ValueError(f"{db_key} is missing in wp-config.php")
            if len(db_value) > 1:
                raise ValueError(f"multiple {db_key} definitions")
            db_info[db_key] = db_value[0]
        return db_info

    def _mock_database_connect(self, db_info):
        credential_key = db_info["db_host"], db_info["db_name"]
        if credential_key not in self._database_credentials:
            raise mysql.connector.Error(
                msg=f"Can't connect to MySQL server on '{db_info['db_host']}:3306' (2003)",
                errno=2003
            )
        for credential in self._database_credentials[credential_key]:
            if (
                    credential["db_user"] == db_info["db_user"] and
                    credential["db_password"] == db_info["db_password"]
            ):
                return
        raise mysql.connector.Error(
            msg=f"Access denied for user '{db_info['db_user']}'@* (using password: *)",
            errno=1045
        )

    def _simulate_run_wp_cli(self, cmd):
        Result = collections.namedtuple("WordpressCliExecResult", "return_code stdout stderr")

        cmd_prefix = cmd[:3]
        db_info = self._get_current_database_config()
        database_key = db_info["db_host"], db_info["db_name"]
        try:
            self._mock_database_connect(db_info)
        except mysql.connector.Error:
            raise ValueError("attempt to run wp cli before database is ready")
        database = self._database.get(database_key)
        if cmd_prefix == ["wp", "core", "is-installed"]:
            return Result(return_code=1 if database is None else 0, stdout="", stderr="")
        elif cmd_prefix == ["wp", "core", "install"]:
            self._database[database_key] = {}
            return Result(return_code=0, stdout="", stderr="")
        elif cmd_prefix == ["wp", "theme", "list"]:
            return Result(return_code=0,
                          stdout=json.dumps([{"name": t} for t in self._themes]),
                          stderr="")
        elif cmd_prefix == ["wp", "theme", "install"]:
            self._themes.add(cmd[3])
            return Result(return_code=0, stdout="", stderr="")
        elif cmd_prefix == ["wp", "theme", "delete"]:
            theme = cmd[3]
            if theme not in self._themes:
                return Result(
                    return_code=1,
                    stdout="",
                    stderr=f"Error, try to delete a non-existent theme {repr(theme)}"
                )
            self._themes.remove(cmd[3])
            return Result(return_code=0, stdout="", stderr="")
        elif cmd_prefix == ["wp", "plugin", "list"]:
            return Result(return_code=0,
                          stdout=json.dumps([{"name": t} for t in self._plugins]),
                          stderr="")
        elif cmd_prefix == ["wp", "plugin", "install"]:
            self._plugins.add(cmd[3])
            return Result(return_code=0, stdout="", stderr="")
        elif cmd_prefix == ["wp", "plugin", "uninstall"]:
            plugin = cmd[3]
            if plugin not in self._plugins:
                return Result(
                    return_code=1,
                    stdout="",
                    stderr=f"Error, try to delete a non-existent plugin {repr(plugin)}"
                )
            self._plugins.remove(plugin)
            return Result(return_code=0, stdout="", stderr="")
        raise ValueError(f"matrix breached, running an unknown cmd {cmd}")

    def start(self):
        def mock_current_wp_config(_self):
            return self._container_fs.get(WordpressCharm._WP_CONFIG_PATH)

        def mock_push_wp_config(_self, wp_config):
            self._container_fs[WordpressCharm._WP_CONFIG_PATH] = wp_config

        def mock_remove_wp_config(_self):
            del self._container_fs[WordpressCharm._WP_CONFIG_PATH]

        def mock_run_wp_cli(_self, cmd, timeout=60, combine_stderr=False):
            return self._simulate_run_wp_cli(cmd)

        def mock_test_database_connectivity(_self):
            try:
                self._mock_database_connect(self._get_current_database_config())
                return True, ""
            except mysql.connector.Error as err:
                return False, f"MySQL error {err.errno}"

        self._patch = unittest.mock.patch.multiple(
            WordpressCharm,
            _current_wp_config=mock_current_wp_config,
            _push_wp_config=mock_push_wp_config,
            _remove_wp_config=mock_remove_wp_config,
            _run_wp_cli=mock_run_wp_cli,
            _test_database_connectivity=mock_test_database_connectivity,
            _DB_CHECK_INTERVAL=0
        )
        self._patch.start()

    def stop(self):
        self._patch.stop()

    def allow_database(self, db_info):
        database_key = db_info["db_host"], db_info["db_name"]
        if database_key in self._database_credentials:
            self._database_credentials[database_key].append(db_info)
        else:
            self._database_credentials[database_key] = [db_info]

    def installed_themes(self):
        return self._themes

    def installed_plugins(self):
        return self._plugins

    def check_database_installed(self, db_host, db_name):
        return (db_host, db_name) in self._database


class TestWordpressK8s(unittest.TestCase):
    def setUp(self):
        self.patch = WordpressMock()
        self.patch.start()
        self.harness = ops.testing.Harness(WordpressCharm)
        self.addCleanup(self.harness.cleanup)
        self._leadership_data = {}
        self.leadership_patch = unittest.mock.patch.multiple(
            "leadership.LeadershipSettings",
            __getitem__=self._leadership_data.get,
            __setitem__=lambda this, key, value: self._leadership_data.update({key: value}),
            setdefault=self._leadership_data.setdefault
        )
        self.leadership_patch.start()

        self.app_name = "wordpress-k8s"

    def tearDown(self) -> None:
        self.leadership_patch.stop()
        self.patch.stop()

    def test_generate_wp_secret_keys(self):
        """
        arrange: no pre-condition
        act: generate a group of WordPress secrets from scratch.
        assert: generated secrets should be safe .
        """
        self.harness.begin()

        secrets = self.harness.charm._generate_wp_secret_keys()
        self.assertIn(
            "default_admin_password",
            secrets,
            "wordpress should generate a default admin password"
        )
        del secrets["default_admin_password"]
        key_values = list(secrets.values())
        self.assertSetEqual(
            set(secrets.keys()),
            set(self.harness.charm._wordpress_secret_key_fields()),
            "generated wordpress secrets should contain all required fields"
        )
        self.assertEqual(
            len(key_values),
            len(set(key_values)),
            "no two secret values should be the same"
        )
        for value in key_values:
            self.assertFalse(
                value.isalnum() or len(value) < 64,
                "secret values should not be too simple"
            )

    def _setup_replica_consensus(self):
        replica_relation_id = self.harness.add_relation("wordpress-replica", self.app_name)
        self.harness.set_leader()
        self.harness.begin_with_initial_hooks()
        consensus = self.harness.get_relation_data(replica_relation_id, self.app_name)
        return consensus

    def test_replica_consensus(self):
        """
        arrange: deploy a new wordpress-k8s application
        act: simulate peer relation creating and leader electing during the start of deployment
        assert: units should reach consensus after leader elected
        """
        self._setup_replica_consensus()

        self.assertTrue(
            self.harness.charm._replica_consensus_reached(),
            "units in application should reach consensus once leadership established"
        )

    def test_replica_consensus_stable_after_leader_reelection(self):
        """
        arrange: deploy a new wordpress-k8s application
        act: simulate a leader re-election after application deployed
        assert: consensus should not change
        """
        replica_relation_id = self.harness.add_relation("wordpress-replica", self.app_name)
        non_leader_peer_name = "wordpress-k8s/1"
        self.harness.add_relation_unit(replica_relation_id, non_leader_peer_name)
        self.harness.begin_with_initial_hooks()

        self.assertFalse(
            self.harness.charm._replica_consensus_reached(),
            "units in application should not reach consensus before leadership established"
        )
        self.harness.set_leader()
        self.assertTrue(
            self.harness.charm._replica_consensus_reached(),
            "units in application should reach consensus once leadership established"
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
            "consensus once established should not change after leadership changed"
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
        arrange: no pre-condition
        act: add and remove the database relation between WordPress application and mysql
        assert: database info in charm state should change accordingly
        """

        def get_db_info_from_state():
            return {
                "host": self.harness.charm.state.relation_db_host,
                "database": self.harness.charm.state.relation_db_name,
                "user": self.harness.charm.state.relation_db_user,
                "password": self.harness.charm.state.relation_db_password
            }

        self.harness.begin_with_initial_hooks()

        self.assertSetEqual(
            {None},
            set(get_db_info_from_state().values()),
            "database info in charm state should not exist before database relation created"
        )

        db_info = self._example_db_info()
        db_relation_id = self._setup_db_relation(db_info)

        db_info_in_state = get_db_info_from_state()
        for db_info_key in db_info_in_state:
            self.assertEqual(
                db_info_in_state[db_info_key],
                db_info[db_info_key],
                "database info {} in charm state should be updated after database relation changed"
                .format(db_info_key)
            )

        self.harness.remove_relation(db_relation_id)

        db_info_in_state = get_db_info_from_state()
        for db_info_key in db_info_in_state:
            self.assertIsNone(
                db_info_in_state[db_info_key],
                "database info {} should be reset to None after database relation broken"
                .format(db_info_key)
            )

    def test_wp_config(self):
        """
        arrange: after WordPress application unit consensus has been reached
        act: generate wp-config.php
        assert: generated wp-config.php should be valid
        """

        def in_same_line(content, *matches):
            for line in content.splitlines():
                if all(match in line for match in matches):
                    return True
            return False

        self.assertRaises(
            Exception,
            lambda _: self.harness.charm._gen_wp_config(),
            "generating a config before consensus should raise an exception for security reasons"
        )

        replica_consensus = self._setup_replica_consensus()
        wp_config = self.harness.charm._gen_wp_config()

        for secret_key in self.harness.charm._wordpress_secret_key_fields():
            secret_value = replica_consensus[secret_key]
            self.assertTrue(
                in_same_line(wp_config, "define(", secret_key.upper(), secret_value),
                "wp-config.php should contain a valid {}".format(secret_key)
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
                    "define(", db_info_field.upper(), db_info[db_field_conversion[db_info_field]]
                ),
                "wp-config.php should contain database setting {} from the db relation"
                .format(db_info_field)
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
                    wp_config,
                    "define(", db_info_field.upper(), db_info_in_config[db_info_field]
                ),
                "db info in config should takes precedence over the db relation"
            )

    def test_wp_install_cmd(self):
        """
        arrange: no pre-condition
        act: generate wp-cli command to install WordPress
        assert: generated command should match current config and status
        """
        consensus = self._setup_replica_consensus()
        install_cmd = self.harness.charm._wp_install_cmd()

        self.assertIn(
            "--admin_user=admin",
            install_cmd,
            "admin user should be \"admin\" with the default configuration"
        )
        self.assertIn(
            "--admin_password={}".format(consensus["default_admin_password"]),
            install_cmd,
            "admin password should be the same as the default_admin_password in peer relation data"
        )

        self.harness.update_config({
            "initial_settings": """\
            user_name: test_admin_username
            admin_email: test@test.com
            admin_password: test_admin_password
            """
        })
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
                WordPressWaitingStatusException,
                msg="core reconciliation should fail"
        ):
            self.harness.charm._core_reconciliation()
        self.assertIsInstance(
            self.harness.model.unit.status,
            ops.charm.model.WaitingStatus,
            "unit should be in WaitingStatus"
        )
        self.assertIn(
            "unit consensus",
            self.harness.model.unit.status.message,
            "unit should wait for peer relation establishment right now"
        )

    def test_core_reconciliation_before_database_ready(self):
        """
        arrange: before database connection info ready but after peer relation established
        act: run core reconciliation
        assert: core reconciliation should "fail" and status should be waiting
        """
        self._setup_replica_consensus()

        with self.assertRaises(
                WordPressBlockedStatusException,
                msg="core reconciliation should fail"
        ):
            self.harness.charm._core_reconciliation()
        self.assertIsInstance(
            self.harness.model.unit.status,
            ops.charm.model.BlockedStatus,
            "unit should be in WaitingStatus"
        )
        self.assertIn(
            "db relation",
            self.harness.model.unit.status.message,
            "unit should wait for database connection info"
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
        self.patch.allow_database(db_info=db_config)
        self.harness.update_config(db_config)

        self.assertTrue(
            self.patch.check_database_installed(db_config["db_host"], db_config["db_name"]),
            "wordpress should be installed after core reconciliation"
        )

        db_config.update({"db_host": "config_db_host_2"})
        self.patch.allow_database(db_config)
        self.harness.update_config({"db_host": "config_db_host_2"})

        self.assertTrue(
            self.patch.check_database_installed("config_db_host_2", db_config["db_name"]),
            "wordpress should be installed after database config changed"
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

        self.assertEqual(
            len(event.set_results.mock_calls), 0
        )
        self.assertEqual(
            len(event.fail.mock_calls), 1
        )

    def test_get_initial_password_action(self):
        """
        arrange: after peer relation established
        act: run get-initial-password action
        assert: get-initial-password action should success and return default admin password
        """
        consensus = self._setup_replica_consensus()
        event = self._gen_action_event_mock()
        self.harness.charm._on_get_initial_password_action(event)

        self.assertEqual(
            len(event.fail.mock_calls), 0
        )
        self.assertSequenceEqual(
            event.set_results.mock_calls,
            [unittest.mock.call({"password": consensus["default_admin_password"]})]
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
        self.patch.allow_database(db_config)
        self.harness.update_config(db_config)

        self.assertEqual(
            self.patch.installed_themes(),
            set(self.harness.charm._WORDPRESS_DEFAULT_THEMES),
            "installed themes should match the default installed themes "
            "with the default themes config"
        )

        self.harness.update_config({
            "themes": "123, abc"
        })

        self.assertEqual(
            self.patch.installed_themes(),
            set(self.harness.charm._WORDPRESS_DEFAULT_THEMES + ["abc", "123"]),
            "adding themes to themes config should install trigger theme installation"
        )

        self.harness.update_config({
            "themes": "123"
        })

        self.assertEqual(
            self.patch.installed_themes(),
            set(self.harness.charm._WORDPRESS_DEFAULT_THEMES + ["123"]),
            "removing themes from themes config should trigger theme deletion"
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
        self.patch.allow_database(db_config)
        self.harness.update_config(db_config)

        self.assertEqual(
            self.patch.installed_plugins(),
            set(self.harness.charm._WORDPRESS_DEFAULT_PLUGINS),
            "installed plugins should match the default installed plugins "
            "with the default plugins config"
        )

        self.harness.update_config({
            "plugins": "123, abc"
        })

        self.assertEqual(
            self.patch.installed_plugins(),
            set(self.harness.charm._WORDPRESS_DEFAULT_PLUGINS + ["abc", "123"]),
            "adding plugins to plugins config should install trigger plugin installation"
        )

        self.harness.update_config({
            "plugins": "123"
        })

        self.assertEqual(
            self.patch.installed_plugins(),
            set(self.harness.charm._WORDPRESS_DEFAULT_PLUGINS + ["123"]),
            "removing plugins from plugins config should trigger plugin deletion"
        )
