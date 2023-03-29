# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for WordPress charm unit tests."""

import typing
import unittest
import unittest.mock

import ops.pebble
import ops.testing
import pytest

from charm import WordpressCharm
from tests.unit.wordpress_mock import WordpressPatch


@pytest.fixture(scope="function", name="patch")
def patch_fixture():
    """Enable WordPress patch system, used in combine with :class:`ops.testing.Harness`.

    Yields:
        The instance of :class:`tests.unit.wordpress_mock.WordpressPatch`, which can be used to
        inspect the WordPress mocking system (mocking db, mocking file system, etc).
    """
    patch = WordpressPatch()
    patch.start()
    yield patch
    patch.stop()


@pytest.fixture(scope="function", name="harness")
def harness_fixture(patch: WordpressPatch):  # pylint: disable=unused-argument
    """Enable ops test framework harness."""
    harness = ops.testing.Harness(WordpressCharm)
    yield harness
    harness.cleanup()


@pytest.fixture(scope="function", name="app_name")
def app_name_fixture():
    """The name of the charm application."""
    return "wordpress-k8s"


@pytest.fixture(scope="function", name="setup_replica_consensus")
def setup_replica_consensus_fixture(harness: ops.testing.Harness, app_name: str):
    """Yields a function that can be used to set up peer relation.

    After calling the yielded function, the replica consensus including WordPress salt keys and
    secrets will be populated. The unit will become a leader unit in this process.
    """

    def _setup_replica_consensus():
        """Function to set up peer relation. See fixture docstring for more information.

        Returns:
            Relation data for WordPress peers. Includes WordPress salt keys and secrets.
        """
        replica_relation_id = harness.add_relation("wordpress-replica", app_name)
        harness.add_storage("uploads")
        harness.set_leader()
        harness.begin_with_initial_hooks()
        harness.framework.reemit()
        consensus = harness.get_relation_data(replica_relation_id, app_name)
        return consensus

    return _setup_replica_consensus


@pytest.fixture(scope="function", name="example_db_info")
def example_db_info_fixture():
    """An example db connection info."""
    return {
        "host": "test_database_host",
        "database": "test_database_name",
        "user": "test_database_user",
        "password": "test_database_password",
        "port": "3306",
        "root_password": "test_root_password",
    }


@pytest.fixture(scope="function", name="example_database_endpoints")
def example_database_endpoints_fixture():
    """Example database endpoints."""
    return ("test_database_host:3306", "another_database_host:3306")


@pytest.fixture(scope="function", name="example_database_info")
def example_database_info_fixture(example_database_endpoints: tuple[str, str]):
    """An example database connection info from mysql_client interface."""
    return {
        "endpoints": ",".join(example_database_endpoints),
        "database": "test_database_name",
        "username": "test_database_user",
        "password": "test_database_password",
    }


@pytest.fixture(scope="function", name="example_invalid_database_info")
def example_invalid_database_info_fixture():
    """An example database connection info from mysql_client interface."""
    return {
        "endpoints": "test_database_host:1234,another_database_host:4321",
        "database": "test_database_name",
        "username": "test_database_user",
        "password": "test_database_password",
    }


@pytest.fixture(scope="function")
def setup_db_relation(harness: ops.testing.Harness, example_db_info: dict[str, str]):
    """Yields a function that can be used to set up db relation.

    After calling the yielded function, a db relation will be set up. example_db_info will be used
    as the relation data. Return a tuple of relation id and the relation data.
    """

    def _setup_db_relation():
        """Function to set up db relation. See fixture docstring for more information.

        Returns:
            Tuple of relation id and relation data.
        """
        db_relation_id = harness.add_relation("db", "mysql")
        harness.add_relation_unit(db_relation_id, "mysql/0")
        harness.update_relation_data(db_relation_id, "mysql/0", example_db_info)
        return db_relation_id, example_db_info

    return _setup_db_relation


@pytest.fixture(scope="function")
def setup_database_relation(harness: ops.testing.Harness, example_database_info: dict[str, str]):
    """Yields a function that can be used to set up database relation.

    After calling the yielded function, a database relation will be set up. example_database_info
    will be used as the relation data. Return a tuple of relation id and the relation data.
    """

    def _setup_database_relation():
        """Function to set up database relation. See fixture docstring for more information.

        Returns:
            Tuple of relation id and relation data.
        """
        db_relation_id = harness.add_relation("database", "mysql")
        harness.add_relation_unit(db_relation_id, "mysql/0")
        harness.update_relation_data(db_relation_id, "mysql", example_database_info)
        return db_relation_id, example_database_info

    return _setup_database_relation


@pytest.fixture(scope="function")
def setup_database_relation_invalid_port(
    harness: ops.testing.Harness, example_invalid_database_info: dict[str, str]
):
    """Yields a function that can be used to set up database relation with a non 3306 port.

    After calling the yielded function, a database relation will be set up. example_database_info
    will be used as the relation data. Return a tuple of relation id and the relation data.
    """

    def _setup_database_relation():
        """Function to set up database relation. See fixture docstring for more information.

        Returns:
            Tuple of relation id and relation data.
        """
        db_relation_id = harness.add_relation("database", "mysql")
        harness.add_relation_unit(db_relation_id, "mysql/0")
        harness.update_relation_data(db_relation_id, "mysql", example_invalid_database_info)
        return db_relation_id, example_invalid_database_info

    return _setup_database_relation


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
        plugin: str,
        plugin_config: dict[str, str],
        excepted_options: dict[str, typing.Any],
        excepted_options_after_removed: dict[str, str] | None = None,
        additional_check_after_install: typing.Callable | None = None,
    ):
        """Function to perform standard plugins test.

        Args:
            plugin: Name of WordPress standard plugin to test.
            plugin_config: Configurable parameters for WordPress plugins. See config.yaml for
                configuration details.
            excepted_options: Expected configurations of a given plugin.
            excepted_options_after_removed: Remaining options after plugin deactivation.
            additional_check_after_install: Callback to additional checks to perform after
                installation.
        """
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
        assert database_instance
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


@pytest.fixture(scope="function")
def attach_storage(
    patch: WordpressPatch,
):
    """Attach the "upload" storage to the mock container."""
    patch.container.fs["/proc/mounts"] = "/var/www/html/wp-content/uploads"
    yield
    patch.container.fs["/proc/mounts"] = ""
