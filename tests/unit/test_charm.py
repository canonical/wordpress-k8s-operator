# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""WordPress charm unit tests."""

# pylint:disable=protected-access

import os
import json
import typing
import unittest.mock

import ops.charm
import ops.pebble
import ops.testing
import pytest
from ops.charm import PebbleReadyEvent
from ops.model import Container
from ops.pebble import Client

import types_
from charm import WordpressCharm
from exceptions import WordPressBlockedStatusException, WordPressWaitingStatusException
from tests.unit.wordpress_mock import WordpressContainerMock, WordpressPatch
from state import CharmConfigInvalidError

BLOCKED_STATUS = "blocked"


def test_generate_wp_secret_keys(harness: ops.testing.Harness):
    """
    arrange: no pre-condition.
    act: generate a group of WordPress secrets from scratch.
    assert: generated secrets should be safe.
    """
    harness.begin()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    secrets = charm._generate_wp_secret_keys()
    assert (
        "default_admin_password" in secrets
    ), "WordPress should generate a default admin password"

    del secrets["default_admin_password"]
    key_values = list(secrets.values())
    assert set(secrets.keys()) == set(
        charm._wordpress_secret_key_fields()
    ), "generated WordPress secrets should contain all required fields"
    assert len(key_values) == len(set(key_values)), "no two secret values should be the same"
    for value in key_values:
        assert not (value.isalnum() or len(value) < 64), "secret values should not be too simple"


@pytest.mark.usefixtures("attach_storage")
def test_replica_consensus(
    harness: ops.testing.Harness, setup_replica_consensus: typing.Callable[[], dict]
):
    """
    arrange: deploy a new wordpress-k8s application.
    act: simulate peer relation creating and leader electing during the start of deployment.
    assert: units should reach consensus after leader elected.
    """
    setup_replica_consensus()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    assert (
        charm._replica_consensus_reached()
    ), "units in application should reach consensus once leadership established"


@pytest.mark.usefixtures("attach_storage")
def test_replica_consensus_stable_after_leader_reelection(
    harness: ops.testing.Harness, app_name: str
):
    """
    arrange: deploy a new wordpress-k8s application.
    act: simulate a leader re-election after application deployed.
    assert: consensus should not change.
    """
    replica_relation_id = harness.add_relation("wordpress-replica", app_name)
    non_leader_peer_name = "wordpress-k8s/1"
    harness.add_relation_unit(replica_relation_id, non_leader_peer_name)
    harness.begin_with_initial_hooks()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)

    assert (
        not charm._replica_consensus_reached()
    ), "units in application should not reach consensus before leadership established"
    harness.set_leader()
    assert (
        charm._replica_consensus_reached()
    ), "units in application should reach consensus once leadership established"
    consensus = harness.get_relation_data(replica_relation_id, app_name)
    # The harness will emit a leader-elected event when calling ``set_leader(True)`` no matter
    # what the situation is, ``set_leader(False)`` does nothing here currently, just for the
    # aesthetic.
    harness.set_leader(False)
    harness.set_leader(True)
    assert (
        harness.get_relation_data(replica_relation_id, app_name) == consensus
    ), "consensus once established should not change after leadership changed"


@pytest.mark.usefixtures("attach_storage")
def test_database_relation(
    harness: ops.testing.Harness,
    setup_database_relation: typing.Callable[[], typing.Tuple[int, dict]],
    example_database_host_port: typing.Tuple[str, str],
):
    """
    arrange: no pre-condition.
    act: add and remove the database relation between WordPress application and mysql.
    assert: database info in charm state should change accordingly.
    """
    harness.begin_with_initial_hooks()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)

    assert (
        charm._current_effective_db_info is None
    ), "database info in charm state should not exist before database relation created"

    db_relation_id, db_info = setup_database_relation()

    effective_db_info = charm._current_effective_db_info

    assert effective_db_info is not None
    assert effective_db_info.hostname == example_database_host_port[0]
    assert effective_db_info.database == db_info["database"]
    assert effective_db_info.username == db_info["username"]
    assert effective_db_info.password == db_info["password"]

    harness.remove_relation(db_relation_id)

    effective_db_info = charm._current_effective_db_info
    assert effective_db_info is None


def test_wp_config_before_consensus(harness: ops.testing.Harness):
    """
    arrange: before WordPress application unit consensus has been reached.
    act: generate wp-config.php.
    assert: an exception should be raised.
    """
    harness.begin()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    # generating a config before consensus should raise an exception for security reasons
    with pytest.raises(WordpressCharm._ReplicaRelationNotReady):
        charm._gen_wp_config()


def test_wp_config(
    harness: ops.testing.Harness,
    setup_replica_consensus: typing.Callable[[], dict],
):
    """
    arrange: after WordPress application unit consensus has been reached.
    act: generate wp-config.php.
    assert: generated wp-config.php should be valid.
    """

    def in_same_line(content: str, *matches: str):
        """Check if all matches are found within the same content line.

        Args:
            content: Target string to check for matches within same line.
            matches: Strings that should belong in the same line.

        Returns:
            True if a line containing all matches is found. False otherwise.
        """
        for line in content.splitlines():
            if all(match in line for match in matches):
                return True
        return False

    replica_consensus = setup_replica_consensus()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    wp_config = charm._gen_wp_config()

    for secret_key in charm._wordpress_secret_key_fields():
        secret_value = replica_consensus[secret_key]
        assert in_same_line(
            wp_config, "define(", secret_key.upper(), secret_value
        ), f"wp-config.php should contain a valid {secret_key}"

    wp_config = charm._gen_wp_config()


@pytest.mark.usefixtures("attach_storage")
def test_wp_install_cmd(
    harness: ops.testing.Harness, setup_replica_consensus: typing.Callable[[], dict]
):
    """
    arrange: no pre-condition.
    act: generate wp-cli command to install WordPress.
    assert: generated command should match current config and status.
    """
    consensus = setup_replica_consensus()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    install_cmd = charm._wp_install_cmd()

    assert (
        "--admin_user=admin" in install_cmd
    ), 'admin user should be "admin" with the default configuration'
    assert (
        f"--admin_password={consensus['default_admin_password']}" in install_cmd
    ), "admin password should be the same as the default_admin_password in peer relation data"

    harness.update_config(
        {
            "initial_settings": """\
        user_name: test_admin_username
        admin_email: test@test.com
        admin_password: test_admin_password
        """
        }
    )
    install_cmd = charm._wp_install_cmd()

    assert "--admin_user=test_admin_username" in install_cmd
    assert "--admin_email=test@test.com" in install_cmd
    assert "--admin_password=test_admin_password" in install_cmd


def test_core_reconciliation_before_storage_ready(harness: ops.testing.Harness):
    """
    arrange: before storage attached.
    act: run core reconciliation.
    assert: core reconciliation should be deferred and status should be waiting.
    """
    harness.set_can_connect(harness.model.unit.containers["wordpress"], True)
    harness.begin_with_initial_hooks()
    harness.framework.reemit()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)

    with pytest.raises(WordPressWaitingStatusException):
        charm._core_reconciliation()
    assert isinstance(
        harness.model.unit.status, ops.charm.model.WaitingStatus
    ), "unit should be in WaitingStatus"
    assert "storage" in harness.model.unit.status.message, "unit should wait for storage"


@pytest.mark.usefixtures("attach_storage")
def test_core_reconciliation_before_peer_relation_ready(harness: ops.testing.Harness):
    """
    arrange: before peer relation established but after charm created.
    act: run core reconciliation.
    assert: core reconciliation should "fail" and status should be waiting.
    """
    harness.set_can_connect(harness.model.unit.containers["wordpress"], True)
    harness.add_storage("uploads")
    harness.begin_with_initial_hooks()
    harness.framework.reemit()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)

    # core reconciliation should fail
    with pytest.raises(WordPressWaitingStatusException):
        charm._core_reconciliation()
    assert isinstance(
        harness.model.unit.status, ops.charm.model.WaitingStatus
    ), "unit should be in WaitingStatus"
    assert (
        "unit consensus" in harness.model.unit.status.message
    ), "unit should wait for peer relation establishment right now"


@pytest.mark.usefixtures("attach_storage")
def test_core_reconciliation_before_database_ready(
    harness: ops.testing.Harness, setup_replica_consensus: typing.Callable[[], dict]
):
    """
    arrange: before database connection info ready but after peer relation established.
    act: run core reconciliation.
    assert: core reconciliation should "fail" and status should be waiting.
    """
    harness.set_can_connect(harness.model.unit.containers["wordpress"], True)
    setup_replica_consensus()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)

    # core reconciliation should fail
    with pytest.raises(WordPressBlockedStatusException):
        charm._core_reconciliation()

    assert isinstance(
        harness.model.unit.status, ops.charm.model.BlockedStatus
    ), "unit should be in WaitingStatus"
    assert (
        "db relation" in harness.model.unit.status.message
    ), "unit should wait for database connection info"


def test_addon_reconciliation_fail(harness: ops.testing.Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched _wp_addon_list that returns an unsuccessful ExecResult.
    act: when _addon_reconciliation is called.
    assert: WordPressBlockedStatusException is raised
    """
    harness.begin()
    harness.set_can_connect(harness.model.unit.containers["wordpress"], True)
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    monkeypatch.setattr(
        charm,
        "_wp_addon_list",
        lambda *_args, **_kwargs: types_.ExecResult(success=False, result=None, message="Failed"),
    )

    with pytest.raises(WordPressBlockedStatusException):
        charm._addon_reconciliation("theme")


@pytest.mark.usefixtures("attach_storage")
def test_prom_exporter_pebble_ready(
    patch: WordpressPatch,
    harness: ops.testing.Harness,
    setup_replica_consensus: typing.Callable[[], dict],
    setup_database_relation_no_port: typing.Callable[[], typing.Tuple[int, dict]],
):
    """
    arrange: after required relations ready but before prometheus exporter pebble ready.
    act: run prometheus exporter pebble ready.
    assert: unit should be active.
    """
    harness.set_can_connect(harness.model.unit.containers["wordpress"], True)
    setup_replica_consensus()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    _, db_info = setup_database_relation_no_port()
    patch.database.prepare_database(
        host=db_info["endpoints"],
        database=db_info["database"],
        user=db_info["username"],
        password=db_info["password"],
    )
    mock_event = unittest.mock.MagicMock(spec=PebbleReadyEvent)
    mock_event.workload = unittest.mock.MagicMock(spec=Container)
    mock_event.workload.name = "apache-prometheus-exporter"
    mock_event.workload.pebble = unittest.mock.MagicMock(spec=Client)

    charm._on_apache_prometheus_exporter_pebble_ready(mock_event)

    assert isinstance(
        harness.model.unit.status, ops.charm.model.ActiveStatus
    ), "unit should be in ActiveStatus"


@pytest.mark.usefixtures("attach_storage")
def test_core_reconciliation(
    patch: WordpressPatch,
    harness: ops.testing.Harness,
    setup_replica_consensus: typing.Callable[[], dict],
    setup_database_relation_no_port: typing.Callable[[], typing.Tuple[int, dict]],
    example_database_info_no_port_diff_host: dict,
):
    """
    arrange: after peer relation established and database configured.
    act: run core reconciliation.
    assert: core reconciliation should update config files to match current config and
        application state.
    """
    harness.set_can_connect(harness.model.unit.containers["wordpress"], True)
    setup_replica_consensus()
    db_relation_id, db_info = setup_database_relation_no_port()
    patch.database.prepare_database(
        host=db_info["endpoints"],
        database=db_info["database"],
        user=db_info["username"],
        password=db_info["password"],
    )
    harness.update_config()

    assert patch.database.is_wordpress_installed(
        db_info["endpoints"], db_info["database"]
    ), "WordPress should be installed after core reconciliation"

    harness.update_relation_data(db_relation_id, "mysql", example_database_info_no_port_diff_host)
    harness.update_config()

    patch.database.prepare_database(
        host=example_database_info_no_port_diff_host["endpoints"],
        database=example_database_info_no_port_diff_host["database"],
        user=example_database_info_no_port_diff_host["username"],
        password=example_database_info_no_port_diff_host["password"],
    )

    assert patch.database.is_wordpress_installed(
        db_info["endpoints"], db_info["database"]
    ), "WordPress should be installed after database config changed"


def test_get_initial_password_action_before_replica_consensus(
    harness: ops.testing.Harness, action_event_mock: unittest.mock.MagicMock
):
    """
    arrange: before peer relation established but after charm created.
    act: run get-initial-password action.
    assert: get-initial-password action should fail.
    """
    harness.begin_with_initial_hooks()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    charm._on_get_initial_password_action(action_event_mock)

    action_event_mock.set_results.assert_not_called()
    action_event_mock.fail.assert_called_once_with(
        "Default admin password has not been generated yet."
    )


def test_get_initial_password_action(
    harness: ops.testing.Harness,
    setup_replica_consensus: typing.Callable[[], dict],
    action_event_mock: unittest.mock.MagicMock,
):
    """
    arrange: after peer relation established.
    act: run get-initial-password action.
    assert: get-initial-password action should success and return default admin password.
    """
    consensus = setup_replica_consensus()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    charm._on_get_initial_password_action(action_event_mock)

    action_event_mock.fail.assert_not_called()
    action_event_mock.set_results.assert_called_once_with(
        {"password": consensus["default_admin_password"]}
    )


def test_rotate_wordpress_secrets_before_pebble_connect(
    harness: ops.testing.Harness, action_event_mock: unittest.mock.MagicMock
):
    """
    arrange: before connection to pebble is established.
    act: run rotate-wordpress-secrets action.
    assert: rotate-wordpress-secrets action should fail.
    """
    harness.set_can_connect(harness.model.unit.containers["wordpress"], False)
    harness.begin_with_initial_hooks()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    charm._on_rotate_wordpress_secrets_action(action_event_mock)

    action_event_mock.set_results.assert_not_called()
    action_event_mock.fail.assert_called_once_with("Secrets have not been initialized yet.")


def test_rotate_wordpress_secrets_before_replica_consensus(
    harness: ops.testing.Harness, action_event_mock: unittest.mock.MagicMock
):
    """
    arrange: before peer relation is established.
    act: run rotate-wordpress-secrets action.
    assert: rotate-wordpress-secrets action should fail.
    """
    harness.set_can_connect(harness.model.unit.containers["wordpress"], True)
    harness.begin_with_initial_hooks()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    charm._on_rotate_wordpress_secrets_action(action_event_mock)

    action_event_mock.set_results.assert_not_called()
    action_event_mock.fail.assert_called_once_with("Secrets have not been initialized yet.")


def test_rotate_wordpress_secrets_as_follower(
    harness: ops.testing.Harness,
    action_event_mock: unittest.mock.MagicMock,
    setup_replica_consensus: typing.Callable[[], dict],
):
    """
    arrange: after peer relation is established, is follower.
    act: run rotate-wordpress-secrets action.
    assert: rotate-wordpress-secrets action should succeed and secrets updated.
    """
    harness.set_can_connect(harness.model.unit.containers["wordpress"], True)
    setup_replica_consensus()
    harness.set_leader(False)
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)

    charm._on_rotate_wordpress_secrets_action(action_event_mock)

    action_event_mock.set_results.assert_not_called()
    action_event_mock.fail.assert_called_once_with(
        "This unit is not leader."
        " Use <application>/leader to specify the leader unit when running action."
    )


def test_rotate_wordpress_secrets(
    harness: ops.testing.Harness,
    action_event_mock: unittest.mock.MagicMock,
    setup_replica_consensus: typing.Callable[[], dict],
):
    """
    arrange: after peer relation is established, is leader.
    act: run rotate-wordpress-secrets action.
    assert: rotate-wordpress-secrets action should succeed and secrets updated.
    """
    harness.set_can_connect(harness.model.unit.containers["wordpress"], True)
    setup_replica_consensus()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)

    relation = harness.model.get_relation("wordpress-replica")
    assert relation
    old_relation_data = dict(relation.data[charm.app])

    charm._on_rotate_wordpress_secrets_action(action_event_mock)

    # Technically possible to generate the same passwords, but extremely unlikely.
    relation = harness.model.get_relation("wordpress-replica")
    assert relation
    assert old_relation_data != relation.data[charm.app], "password are same from before rotate"

    action_event_mock.set_results.assert_called_once_with({"result": "ok"})
    action_event_mock.fail.assert_not_called()


@pytest.mark.usefixtures("attach_storage")
def test_theme_reconciliation(
    patch: WordpressPatch,
    harness: ops.testing.Harness,
    setup_replica_consensus: typing.Callable[[], dict],
    setup_database_relation_no_port: typing.Callable[[], typing.Tuple[int, dict]],
):
    """
    arrange: after peer relation established and database ready.
    act: update themes configuration.
    assert: themes installed in WordPress should update according to the themes config.
    """
    harness.set_can_connect(harness.model.unit.containers["wordpress"], True)
    setup_replica_consensus()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    _, db_info = setup_database_relation_no_port()
    patch.database.prepare_database(
        host=db_info["endpoints"],
        database=db_info["database"],
        user=db_info["username"],
        password=db_info["password"],
    )

    assert patch.container.installed_themes == set(
        charm._WORDPRESS_DEFAULT_THEMES
    ), "installed themes should match the default installed themes with the default themes config"

    harness.update_config({"themes": "123, abc"})

    assert patch.container.installed_themes == set(
        charm._WORDPRESS_DEFAULT_THEMES + ["abc", "123"]
    ), "adding themes to themes config should trigger theme installation"

    harness.update_config({"themes": "123"})

    assert patch.container.installed_themes == set(
        charm._WORDPRESS_DEFAULT_THEMES + ["123"]
    ), "removing themes from themes config should trigger theme deletion"


@pytest.mark.usefixtures("attach_storage")
def test_plugin_reconciliation(
    patch: WordpressPatch,
    harness: ops.testing.Harness,
    setup_replica_consensus: typing.Callable[[], dict],
    setup_database_relation_no_port: typing.Callable[[], typing.Tuple[int, dict]],
):
    """
    arrange: after peer relation established and database ready.
    act: update plugins configuration.
    assert: plugin installed in WordPress should update according to the plugin config.
    """
    harness.set_can_connect(harness.model.unit.containers["wordpress"], True)
    setup_replica_consensus()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    _, db_info = setup_database_relation_no_port()
    patch.database.prepare_database(
        host=db_info["endpoints"],
        database=db_info["database"],
        user=db_info["username"],
        password=db_info["password"],
    )

    assert patch.container.installed_plugins == set(
        charm._WORDPRESS_DEFAULT_PLUGINS
    ), "installed plugins should match the default installed plugins with the default plugins config"

    harness.update_config({"plugins": "123, abc"})

    assert patch.container.installed_plugins == set(
        charm._WORDPRESS_DEFAULT_PLUGINS + ["abc", "123"]
    ), "adding plugins to plugins config should trigger plugin installation"

    harness.update_config({"plugins": "123"})

    assert patch.container.installed_plugins == set(
        charm._WORDPRESS_DEFAULT_PLUGINS + ["123"]
    ), "removing plugins from plugins config should trigger plugin deletion"


def test_team_map():
    """
    arrange: no arrange.
    act: convert the team_map config using _encode_openid_team_map method.
    assert: the converted result should be a valid PHP array with the meaning matching the config.
    """
    team_map = "site-sysadmins=administrator,site-editors=editor,site-executives=editor"
    option = WordpressCharm._encode_openid_team_map(team_map)
    assert (
        option.replace(" ", "").replace("\n", "")
        == """array (
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
        )
    )


def test_swift_config(
    harness: ops.testing.Harness,
    setup_replica_consensus: typing.Callable[[], dict],
):
    """
    arrange: after peer relation established and database ready.
    act: update legacy version of the wp_plugin_openstack-objectstorage_config configuration.
    assert: parsed swift configuration should update all legacy fields.
    """
    harness.set_can_connect(harness.model.unit.containers["wordpress"], True)
    setup_replica_consensus()
    swift_config = {
        "auth-url": "http://swift.test/identity/v3",
        "bucket": "wordpress_tests.integration.test_upgrade",
        "password": "nomoresecret",
        "region": "RegionOne",
        "tenant": "demo",
        "domain": "default",
        "username": "demo",
        "copy-to-swift": "1",
        "serve-from-swift": "1",
        "remove-local-file": "0",
        "url": "http://swift.test:8080/v1/AUTH_fa8326b9fd4f405fb1c5eaafe988f5fd/"
        "wordpress_tests.integration.test_upgrade/wp-content/uploads/",
        "prefix": "wp-content/uploads/",
    }
    harness.update_config({"wp_plugin_openstack-objectstorage_config": json.dumps(swift_config)})
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    del swift_config["url"]
    del swift_config["prefix"]
    swift_config.update(
        {
            "swift-url": "http://swift.test:8080/v1/AUTH_fa8326b9fd4f405fb1c5eaafe988f5fd",
            "object-prefix": "wp-content/uploads/",
        }
    )
    assert charm._swift_config() == swift_config


@pytest.mark.usefixtures("attach_storage")
def test_akismet_plugin(run_standard_plugin_test: typing.Callable):
    """
    arrange: after peer relation established and database ready.
    act: update akismet plugin configuration.
    assert: plugin should be activated with WordPress options being set correctly, and plugin
        should be deactivated with options removed after config being reset.
    """
    run_standard_plugin_test(
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


@pytest.mark.usefixtures("attach_storage")
def test_openid_plugin(patch: WordpressPatch, run_standard_plugin_test: typing.Callable):
    """
    arrange: after peer relation established and database ready.
    act: update openid plugin configuration.
    assert: plugin should be activated with WordPress options being set correctly, and plugin
        should be deactivated with options removed after config being reset.
    """
    run_standard_plugin_test(
        plugin={"openid", "wordpress-launchpad-integration", "wordpress-teams-integration"},
        plugin_config={
            "wp_plugin_openid_team_map": "site-sysadmins=administrator,site-editors=editor,site-executives=editor"
        },
        excepted_options={"openid_required_for_registration": "1", "users_can_register": "1"},
        excepted_options_after_removed={"users_can_register": "0"},
    )
    assert patch.container.wp_eval_history[-1].startswith(
        "update_option('openid_teams_trust_list',"
    ), "PHP function update_option should be invoked after openid plugin enabled"


@pytest.mark.usefixtures("attach_storage")
def test_swift_plugin(patch: WordpressPatch, run_standard_plugin_test: typing.Callable):
    """
    arrange: after peer relation established and database ready.
    act: update openid plugin configuration.
    assert: plugin should be activated with WordPress options being set correctly, and plugin
        should be deactivated with options removed after config being reset. Apache
        configuration for swift integration should be enabled after swift plugin activated
        and configuration should be disabled after swift plugin deactivated.
    """

    def additional_check_after_install():
        """Assert swift proxy configuration file is correctly installed."""
        conf_found = False
        for file in patch.container.fs:
            if file.endswith("docker-php-swift-proxy.conf"):
                conf_found = True
        assert conf_found

    assert not any(file.endswith("docker-php-swift-proxy.conf") for file in patch.container.fs)
    run_standard_plugin_test(
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


def test_ingress(
    harness: ops.testing.Harness,
    setup_replica_consensus: typing.Callable[[], dict],
    app_name: str,
):
    """
    arrange: after peer relation established and database ready.
    act: create a relation between wordpress-k8s and nginx ingress integrator, and update the
        tls_secret_name configuration.
    assert: ingress relation data should be set up according to the configuration and application
        name.
    """
    harness.set_model_name("test-wordpress")
    nginx_route_relation_id = harness.add_relation("nginx-route", "ingress")
    harness.add_relation_unit(nginx_route_relation_id, "ingress/0")
    setup_replica_consensus()

    assert harness.get_relation_data(nginx_route_relation_id, harness.charm.app) == {
        "service-hostname": app_name,
        "service-name": app_name,
        "service-port": "80",
        "service-namespace": "test-wordpress",
        "owasp-modsecurity-crs": "True",
        "owasp-modsecurity-custom-rules": 'SecAction "id:900130,phase:1,nolog,pass,t:none,setvar:tx.crs_exclusions_wordpress=1"\n',
    }

    harness.update_config({"use_nginx_ingress_modsec": False})
    harness.charm._require_nginx_route()

    assert harness.get_relation_data(nginx_route_relation_id, harness.charm.app) == {
        "service-hostname": app_name,
        "service-name": app_name,
        "service-port": "80",
        "service-namespace": "test-wordpress",
    }

    new_hostname = "new-hostname"
    harness.update_config({"blog_hostname": new_hostname})
    harness.charm._require_nginx_route()

    assert harness.get_relation_data(nginx_route_relation_id, harness.charm.app) == {
        "service-hostname": new_hostname,
        "service-name": app_name,
        "service-port": "80",
        "service-namespace": "test-wordpress",
    }


@pytest.mark.parametrize(
    "method,test_args",
    [
        ("_check_addon_type", ("not theme/plugin",)),
        ("_wp_addon_install", ("not theme/plugin", "name")),
        ("_wp_addon_list", ("not theme/plugin",)),
        ("_wp_addon_uninstall", ("not theme/plugin", "name")),
        ("_perform_plugin_activate_or_deactivate", ("name", "not activate/deactivate")),
    ],
)
def test_defensive_programing(harness: ops.testing.Harness, method: str, test_args: list):
    """
    arrange: no arrange.
    act: invoke some method with incorrect arguments.
    assert: ValueError should be raised to prevent further execution.
    """
    harness.begin()
    with pytest.raises(ValueError):
        getattr(harness.charm, method)(*test_args)


def test_missing_peer_relation(harness: ops.testing.Harness):
    """
    arrange: charm peer relation is not ready.
    act: invoke _replica_relation_data method.
    assert: _ReplicaRelationNotReady should be raised to signal peer relation is not ready.
    """
    harness.begin()
    charm: WordpressCharm = typing.cast(WordpressCharm, harness.charm)
    with pytest.raises(WordpressCharm._ReplicaRelationNotReady):
        charm._replica_relation_data()


@pytest.mark.usefixtures("attach_storage")
def test_mysql_connection_error(
    harness: ops.testing.Harness, setup_replica_consensus, setup_database_relation_connection_error
):
    """
    arrange: charm peer relation is ready and the storage is attached.
    act: config the charm to connect to a non-existent database.
    assert: charm should enter blocked state, and the database error should be seen in the status.
    """
    setup_database_relation_connection_error()
    setup_replica_consensus()
    assert isinstance(harness.model.unit.status, ops.charm.model.BlockedStatus)
    assert harness.model.unit.status.message == "MySQL error 2003"


@pytest.mark.usefixtures("attach_storage")
def test_wordpress_version_set(harness: ops.testing.Harness):
    """
    arrange: no arrange.
    act: charm container is ready.
    assert: workload version is set.
    """
    harness.set_can_connect(harness.model.unit.containers["wordpress"], True)
    harness.begin_with_initial_hooks()

    assert harness.get_workload_version() == WordpressContainerMock._WORDPRESS_VERSION


def test_invalid_proxy_config(harness: ops.testing.Harness):
    """
    arrange: no arrange.
    act: charm container is ready.
    assert: workload version is set.
    """
    http_proxy = "http://proxy.internal:3128"
    https_proxy = "http://proxy.internal:3128"
    no_proxy = "127.0.0.1,::1"
    os.environ["JUJU_CHARM_HTTP_PROXY"] = http_proxy
    os.environ["JUJU_CHARM_HTTPS_PROXY"] = https_proxy
    os.environ["JUJU_CHARM_NO_PROXY"] = no_proxy

    harness.begin_with_initial_hooks()
    charm: WordpressCharm = harness.charm
    assert str(charm.state.proxy_config.http_proxy) == http_proxy
    assert str(charm.state.proxy_config.https_proxy) == https_proxy
    assert str(charm.state.proxy_config.no_proxy) == no_proxy


def test_invalid_proxy_config(harness: ops.testing.Harness):
    """
    arrange: no arrange.
    act: charm container is ready.
    assert: workload version is set.
    """
    os.environ["JUJU_CHARM_HTTP_PROXY"] = "invalid"
    harness.begin()
    charm: WordpressCharm = harness.charm
    assert charm.unit.status.name == BLOCKED_STATUS


def test_only_valid_http_proxy_config(harness: ops.testing.Harness):
    """
    arrange: no arrange.
    act: charm container is ready.
    assert: workload version is set.
    """
    http_proxy = "http://proxy.internal:3128"
    os.environ["JUJU_CHARM_HTTP_PROXY"] = http_proxy
    harness.begin_with_initial_hooks()
    charm: WordpressCharm = harness.charm
    assert str(charm.state.proxy_config.http_proxy) == http_proxy


def test_only_valid_https_proxy_config(harness: ops.testing.Harness):
    """
    arrange: no arrange.
    act: charm container is ready.
    assert: workload version is set.
    """
    https_proxy = "http://proxy.internal:3128"
    os.environ["JUJU_CHARM_HTTP_PROXY"] = https_proxy
    harness.begin_with_initial_hooks()
    charm: WordpressCharm = harness.charm
    assert str(charm.state.proxy_config.http_proxy) == https_proxy
