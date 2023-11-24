# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=protected-access,too-many-locals

"""Integration tests for WordPress charm COS integration."""

import functools

import pytest
import requests
from juju.action import Action
from juju.client._definitions import FullStatus

from tests.integration.helper import WordpressApp, wait_for


def dashboard_exist(loggedin_session: requests.Session, unit_address: str):
    """Checks if the WordPress dashboard is registered in Grafana.

    Args:
        loggedin_session: Requests session that's authorized to make API calls.
        unit_address: Grafana unit address.

    Returns:
        True if all dashboard is found. False otherwise.
    """
    dashboards = loggedin_session.get(
        f"http://{unit_address}:3000/api/search",
        timeout=10,
        params={"query": "Wordpress Operator Overview"},
    ).json()
    return len(dashboards)


@pytest.mark.usefixtures("prepare_mysql")
async def test_grafana_integration(
    wordpress: WordpressApp,
):
    """
    arrange: after WordPress charm has been deployed and relations established among cos.
    act: grafana charm joins relation
    assert: grafana wordpress dashboard can be found
    """
    grafana = await wordpress.model.deploy(
        "grafana-k8s", channel="1.0/stable", revision=82, trust=True
    )
    await wordpress.model.wait_for_idle(status="active", apps=["grafana-k8s"], timeout=20 * 60)
    await wordpress.model.add_relation("wordpress-k8s:grafana-dashboard", "grafana-k8s")
    await wordpress.model.wait_for_idle(
        status="active", apps=["grafana-k8s", "wordpress-k8s"], timeout=30 * 60
    )
    action: Action = await grafana.units[0].run_action("get-admin-password")
    await action.wait()
    password = action.results["admin-password"]

    status: FullStatus = await wordpress.model.get_status(filters=[grafana.name])
    for unit in status.applications[grafana.name].units.values():
        sess = requests.session()
        sess.post(
            f"http://{unit.address}:3000/login",
            json={
                "user": "admin",
                "password": password,
            },
        ).raise_for_status()
        await wait_for(
            functools.partial(dashboard_exist, loggedin_session=sess, unit_address=unit.address),
            timeout=60 * 20,
        )
