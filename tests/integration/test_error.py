# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for WordPress charm in error."""

import ops.model
import pytest
import pytest_operator.plugin


@pytest.mark.usefixtures("build_and_deploy")
@pytest.mark.asyncio
@pytest.mark.usefixtures("app_config")
@pytest.mark.parametrize(
    "app_config",
    [
        {
            "db_host": "test_db_host",
            "db_name": "test_db_name",
            "db_user": "test_db_user",
            "db_password": "test_db_password",
        }
    ],
    indirect=True,
    scope="function",
)
async def test_incorrect_db_config(ops_test: pytest_operator.plugin.OpsTest, application_name):
    """
    arrange: after WordPress charm has been deployed.
    act: provide incorrect database info via config.
    assert: charm should be blocked by WordPress installation errors, instead of lacking
        of database connection info.
    """
    # Database configuration can retry for up to 60 seconds before giving up and showing an error.
    # Default wait_for_idle 15 seconds in ``app_config`` fixture is too short for incorrect
    # db config.
    assert ops_test.model
    await ops_test.model.wait_for_idle(
        idle_period=60, status=ops.model.BlockedStatus.name, apps=[application_name]  # type: ignore
    )

    for unit in ops_test.model.applications[application_name].units:
        assert (
            unit.workload_status == ops.model.BlockedStatus.name  # type: ignore
        ), "unit status should be blocked"
        msg = unit.workload_status_message
        assert ("MySQL error" in msg and ("2003" in msg or "2005" in msg)) or (
            "leader unit failed" in msg
        ), "unit status message should show detailed installation failure"
