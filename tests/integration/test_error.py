# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for WordPress charm in error."""

from tests.integration.helper import WordpressApp


async def test_incorrect_db_config(wordpress: WordpressApp):
    """
    arrange: after WordPress charm has been deployed.
    act: provide incorrect database info via config.
    assert: charm should be blocked by WordPress installation errors, instead of lacking
        of database connection info.
    """
    # Database configuration can retry for up to 300 seconds before giving up and showing an error.
    # Default wait_for_idle 15 seconds in ``app_config`` fixture is too short for incorrect
    # db config.
    await wordpress.set_config(
        {
            "db_host": "test_db_host",
            "db_name": "test_db_name",
            "db_user": "test_db_user",
            "db_password": "test_db_password",
        }
    )
    await wordpress.model.wait_for_idle(
        idle_period=360, status="blocked", apps=[wordpress.name], timeout=45 * 60
    )

    for unit in wordpress.get_units():
        assert unit.workload_status == "blocked", "unit status should be blocked"
        msg = unit.workload_status_message
        assert ("MySQL error" in msg and ("2003" in msg or "2005" in msg)) or (
            "leader unit failed" in msg
        ), "unit status message should show detailed installation failure"
