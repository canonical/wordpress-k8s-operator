# Copyright 2024 Canonical Ltd.
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
    """Returns a function that can be used to set up peer relation.

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


@pytest.fixture(scope="function", name="example_database_host_port")
def example_database_host_port_fixture():
    """An example database connection host and port tuple."""
    return ("test_database_host", "3306")


@pytest.fixture(scope="function", name="example_database_info")
def example_database_info_fixture(example_database_host_port: typing.Tuple[str, str]):
    """An example database connection info from mysql_client interface."""
    return {
        "endpoints": ":".join(example_database_host_port),
        "database": "test_database_name",
        "username": "test_database_user",
        "password": "test_database_password",
    }


@pytest.fixture(scope="function", name="example_invalid_database_info")
def example_invalid_database_info_fixture():
    """An example database connection info from mysql_client interface."""
    return {
        "endpoints": "test_database_host:1234",
        "database": "test_database_name",
        "username": "test_database_user",
        "password": "test_database_password",
    }


@pytest.fixture(scope="function", name="example_database_info_no_port")
def example_database_info_no_port_fixture():
    """An example database connection info from mysql_client interface."""
    return {
        "endpoints": "test_database_host",
        "database": "test_database_name",
        "username": "test_database_user",
        "password": "test_database_password",
    }


@pytest.fixture(scope="function", name="example_database_info_no_port_diff_host")
def example_database_info_no_port_diff_host_fixture():
    """An example database connection info from mysql_client interface."""
    return {
        "endpoints": "test_database_host2",
        "database": "test_database_name",
        "username": "test_database_user",
        "password": "test_database_password",
    }


@pytest.fixture(scope="function", name="example_database_info_connection_error")
def example_database_info_connection_error_fixture():
    """An example database connection info from mysql_client interface."""
    return {
        "endpoints": "a",
        "database": "b",
        "username": "c",
        "password": "d",
    }


@pytest.fixture(scope="function")
def setup_database_relation(
    harness: ops.testing.Harness, example_database_info: typing.Dict[str, str]
):
    """Returns a function that can be used to set up database relation.

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


@pytest.fixture(scope="function", name="setup_database_relation_no_port")
def setup_database_relation_no_port_fixture(
    harness: ops.testing.Harness, example_database_info_no_port: typing.Dict[str, str]
):
    """Returns a function that can be used to set up database relation.

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
        harness.update_relation_data(db_relation_id, "mysql", example_database_info_no_port)
        return db_relation_id, example_database_info_no_port

    return _setup_database_relation


@pytest.fixture(scope="function")
def setup_database_relation_invalid_port(
    harness: ops.testing.Harness, example_invalid_database_info: typing.Dict[str, str]
):
    """Returns a function that can be used to set up database relation with a non 3306 port.

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
def setup_database_relation_connection_error(
    harness: ops.testing.Harness, example_database_info_connection_error: typing.Dict[str, str]
):
    """Returns a function that can be used to set up database relation with a non 3306 port.

    After calling the yielded function, a database relation will be set up.
    example_database_info_connection_error will be used as the relation data.
    Return a tuple of relation id and the relation data.
    """

    def _setup_database_relation():
        """Function to set up database relation. See fixture docstring for more information.

        Returns:
            Tuple of relation id and relation data.
        """
        db_relation_id = harness.add_relation("database", "mysql")
        harness.add_relation_unit(db_relation_id, "mysql/0")
        harness.update_relation_data(
            db_relation_id, "mysql", example_database_info_connection_error
        )
        return db_relation_id, example_database_info_connection_error

    return _setup_database_relation


@pytest.fixture(scope="function")
def action_event_mock():
    """Creates a mock object for :class:`ops.charm.ActionEvent`."""
    event_mock = unittest.mock.MagicMock()
    event_mock.set_results = unittest.mock.MagicMock()
    event_mock.fail = unittest.mock.MagicMock()
    return event_mock


@pytest.fixture(scope="function")
def attach_storage(
    patch: WordpressPatch,
):
    """Attach the "upload" storage to the mock container."""
    patch.container.fs["/proc/mounts"] = "/var/www/html/wp-content/uploads"
    yield
    patch.container.fs["/proc/mounts"] = ""
