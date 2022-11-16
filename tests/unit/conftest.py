# Copyright 2022 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.
import typing
import unittest
import unittest.mock

import ops.pebble
import ops.testing
import pytest

from charm import WordpressCharm
from tests.unit.wordpress_mock import WordpressPatch


@pytest.fixture(scope="function")
def patch():
    """Enable WordPress patch system, used in combine with :class:`ops.testing.Harness`.

    Yields:
        The instance of :class:`tests.unit.wordpress_mock.WordpressPatch`, which can be used to
        inspect the WordPress mocking system (mocking db, mocking file system, etc).
    """
    patch = WordpressPatch()
    patch.start()
    yield patch
    patch.stop()


@pytest.fixture(scope="function")
def harness(patch: WordpressPatch):
    """Enable ops test framework harness."""
    harness = ops.testing.Harness(WordpressCharm)
    yield harness
    harness.cleanup()


@pytest.fixture(scope="function")
def app_name():
    """The name of the charm application."""
    return "wordpress-k8s"


@pytest.fixture(scope="function")
def setup_replica_consensus(harness: ops.testing.Harness, app_name: str):
    """Yields a function that can be used to set up peer relation.

    After calling the yielded function, the replica consensus including WordPress salt keys and
    secrets will be populated. The unit will become a leader unit in this process.
    """

    def _setup_replica_consensus():
        replica_relation_id = harness.add_relation("wordpress-replica", app_name)
        harness.set_leader()
        harness.begin_with_initial_hooks()
        consensus = harness.get_relation_data(replica_relation_id, app_name)
        return consensus

    return _setup_replica_consensus


@pytest.fixture(scope="function")
def example_db_info():
    """An example database connection info."""
    return {
        "host": "test_database_host",
        "database": "test_database_name",
        "user": "test_database_user",
        "password": "test_database_password",
        "port": "3306",
        "root_password": "test_root_password",
    }


@pytest.fixture(scope="function")
def setup_db_relation(harness: ops.testing.Harness, example_db_info: dict):
    """Yields a function that can be used to set up db relation.

    After calling the yielded function, a db relation will be set up. example_db_info will be used
    as the relation data. Return a tuple of relation id and the relation data.
    """

    def _setup_db_relation():
        db_info = example_db_info
        db_relation_id = harness.add_relation("db", "mysql")
        harness.add_relation_unit(db_relation_id, "mysql/0")
        harness.update_relation_data(db_relation_id, "mysql/0", example_db_info)
        return db_relation_id, db_info

    return _setup_db_relation


@pytest.fixture(scope="function")
def action_event_mock():
    """Creates a mock object for :class:`ops.charm.ActionEvent`."""
    event_mock = unittest.mock.MagicMock()
    event_mock.set_results = unittest.mock.MagicMock()
    event_mock.fail = unittest.mock.MagicMock()
    return event_mock


@pytest.fixture(scope="function")
def run_standard_plugin_test(
    patch: WordpressPatch,
    harness: ops.testing.Harness,
    setup_replica_consensus: typing.Callable[[], dict],
):
    """Yields a function that can be used to perform some general test for different plugins."""

    def _run_standard_plugin_test(
        plugin,
        plugin_config,
        excepted_options,
        excepted_options_after_removed=None,
        additional_check_after_install=None,
    ):
        plugin_config_keys = list(plugin_config.keys())
        harness.set_can_connect(harness.model.unit.containers["wordpress"], True)
        setup_replica_consensus()
        db_config = {
            "db_host": "config_db_host",
            "db_name": "config_db_name",
            "db_user": "config_db_user",
            "db_password": "config_db_password",
        }
        patch.database.prepare_database(
            host=db_config["db_host"],
            database=db_config["db_name"],
            user=db_config["db_user"],
            password=db_config["db_password"],
        )

        harness.update_config(db_config)

        harness.update_config(plugin_config)

        database_instance = patch.database.get_wordpress_database(
            host="config_db_host", database="config_db_name"
        )
        assert (
            database_instance.activated_plugins == {plugin}
            if isinstance(plugin, str)
            else set(plugin)
        ), f"{plugin} should be activated after {plugin_config_keys} being set"
        assert (
            database_instance.options == excepted_options
        ), f"options of plugin {plugin} should be set correctly"

        if additional_check_after_install is not None:
            additional_check_after_install()

        harness.update_config({k: "" for k in plugin_config})
        assert (
            database_instance.activated_plugins == set()
        ), f"{plugin} should be deactivated after {plugin_config_keys} being reset"
        assert (
            database_instance.options == {}
            if excepted_options_after_removed is None
            else excepted_options_after_removed
        ), f"{plugin} options should be removed after {plugin_config_keys} being reset"

    return _run_standard_plugin_test
