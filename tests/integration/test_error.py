# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for WordPress charm in error."""

import ops.model
import pytest
import pytest_operator.plugin
from juju.application import Application


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_config",
    [
        {
            "db_host": "test_db_host",
            "db_name": "test_db_name",
            "db_user": "test_db_user",
            "db_password": "test_db_password",
        }
    ],
)
async def test_incorrect_db_config(
    ops_test: pytest_operator.plugin.OpsTest,
    application_name: str,
    app: Application,
    invalid_config: dict[str, str],
):
    """
    arrange: after WordPress charm has been deployed.
    act: provide incorrect database info via config.
    assert: charm should be blocked by WordPress installation errors, instead of lacking
        of database connection info.
    """
    assert ops_test.model
    await app.set_config(invalid_config)
    await ops_test.model.wait_for_idle(
        idle_period=60, status=ops.model.BlockedStatus.name, apps=[application_name]  # type: ignore
    )

    for unit in app.units:
        assert (
            unit.workload_status == ops.model.BlockedStatus.name  # type: ignore
        ), "unit status should be blocked"
        msg = unit.workload_status_message
        assert ("MySQL error" in msg and ("2003" in msg or "2005" in msg)) or (
            "leader unit failed" in msg
        ), "unit status message should show detailed installation failure"
