# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for WordPress charm core functionality with mysql machine charm."""

import functools

import pytest
from helper import get_mysql_primary_unit, wait_for
from juju.application import Application
from juju.model import Model

from tests.integration.helper import WordpressApp


@pytest.mark.usefixtures("prepare_machine_mysql")
async def test_database_endpoints_changed(machine_model: Model, wordpress: WordpressApp):
    """
    arrange: given related mysql charm with 3 units.
    act: when the leader mysql unit is removed and hence the endpoints changed event fired.
    assert: the WordPress correctly connects to the newly elected leader endpoint.
    """
    model: Model = wordpress.model
    mysql: Application = machine_model.applications["mysql"]
    await mysql.add_unit(2)
    await machine_model.wait_for_idle(["mysql"], timeout=30 * 60)
    await model.wait_for_idle(["wordpress-k8s"])

    leader = await get_mysql_primary_unit(mysql.units)
    assert leader, "No leader unit found."
    await mysql.destroy_unit(leader.name)
    await machine_model.wait_for_idle(["mysql"], timeout=30 * 60, idle_period=30)
    await model.wait_for_idle(["wordpress-k8s"])

    leader = await wait_for(functools.partial(get_mysql_primary_unit, mysql.units))

    assert (
        await leader.get_public_address() in await wordpress.get_wordpress_config()
    ), "MySQL leader unit IP not found."
