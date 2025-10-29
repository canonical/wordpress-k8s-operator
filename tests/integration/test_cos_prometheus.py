# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for WordPress charm COS integration."""

import pytest
import requests
from juju.client._definitions import FullStatus

from cos import APACHE_PROMETHEUS_SCRAPE_PORT
from tests.integration.helper import WordpressApp


@pytest.mark.abort_on_fail
@pytest.mark.usefixtures("prepare_mysql", "prepare_prometheus")
async def test_prometheus_integration(
    wordpress: WordpressApp,
):
    """
    arrange: none.
    act: deploy the WordPress charm and relations established with prometheus.
    assert: prometheus metrics endpoint for prometheus is active and prometheus has active scrape
        targets.
    """
    for unit_ip in await wordpress.get_unit_ips():
        res = requests.get(f"http://{unit_ip}:{APACHE_PROMETHEUS_SCRAPE_PORT}", timeout=10)
        assert res.status_code == 200
    status: FullStatus = await wordpress.model.get_status(filters=["prometheus-k8s"])
    for unit in status.applications["prometheus-k8s"].units.values():
        query_targets = requests.get(
            f"http://{unit.address}:9090/api/v1/targets", timeout=10
        ).json()
        assert len(query_targets["data"]["activeTargets"])
