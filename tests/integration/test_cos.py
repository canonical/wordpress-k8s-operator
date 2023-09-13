# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=protected-access,too-many-locals

"""Integration tests for WordPress charm COS integration."""

import functools
from typing import Iterable

import kubernetes
import pytest
import requests
from juju.action import Action
from juju.client._definitions import FullStatus

from cos import APACHE_PROMETHEUS_SCRAPE_PORT
from tests.integration.helper import WordpressApp, wait_for


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


def log_files_exist(unit_address: str, application_name: str, filenames: Iterable[str]) -> bool:
    """Returns whether log filenames exist in Loki logs query.

    Args:
        unit_address: Loki unit ip address.
        application_name: Application name to query logs for.
        filenames: Expected filenames to be present in logs collected by Loki.

    Returns:
        True if log files with logs exists. False otherwise.
    """
    series = requests.get(f"http://{unit_address}:3100/loki/api/v1/series", timeout=10).json()
    log_files = set(series_data["filename"] for series_data in series["data"])
    if not all(filename in log_files for filename in filenames):
        return False
    log_query = requests.get(
        f"http://{unit_address}:3100/loki/api/v1/query",
        timeout=10,
        params={"query": f'{{juju_application="{application_name}"}}'},
    ).json()

    return len(log_query["data"]["result"]) != 0


@pytest.mark.abort_on_fail
@pytest.mark.usefixtures("prepare_mysql", "prepare_loki")
async def test_loki_integration(
    wordpress: WordpressApp,
    kube_config: str,
):
    """
    arrange: after WordPress charm has been deployed and relations established.
    act: loki charm joins relation
    assert: loki joins relation successfully, logs are being output to container and to files for
        loki to scrape.
    """
    status: FullStatus = await wordpress.model.get_status(filters=["loki-k8s"])
    for unit in status.applications["loki-k8s"].units.values():
        await wait_for(
            functools.partial(
                log_files_exist,
                unit.address,
                wordpress.name,
                ("/var/log/apache2/error.log", "/var/log/apache2/access.log"),
            ),
            timeout=10 * 60,
        )
    kubernetes.config.load_kube_config(config_file=kube_config)
    kube_core_client = kubernetes.client.CoreV1Api()

    kube_log = kube_core_client.read_namespaced_pod_log(
        name=f"{wordpress.name}-0", namespace=wordpress.model.name, container="wordpress"
    )
    assert kube_log


def datasources_exist(
    loggedin_session: requests.Session, unit_address: str, datasources: Iterable[str]
):
    """Checks if the datasources are registered in Grafana.

    Args:
        loggedin_session: Requests session that's authorized to make API calls.
        unit_address: Grafana unit address.
        datasources: Datasources to check for.

    Returns:
        True if all datasources are found. False otherwise.
    """
    response = loggedin_session.get(
        f"http://{unit_address}:3000/api/datasources", timeout=10
    ).json()
    datasource_types = set(datasource["type"] for datasource in response)
    return all(datasource in datasource_types for datasource in datasources)


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


@pytest.mark.usefixtures("prepare_mysql", "prepare_loki", "prepare_prometheus")
async def test_grafana_integration(
    wordpress: WordpressApp,
):
    """
    arrange: after WordPress charm has been deployed and relations established among cos.
    act: grafana charm joins relation
    assert: grafana wordpress dashboard can be found
    """
    grafana = await wordpress.model.deploy("grafana-k8s", channel="1.0/stable", trust=True)
    await wordpress.model.wait_for_idle(
        status="active", apps=["grafana-k8s"], timeout=20 * 60, idle_period=60
    )
    await wordpress.model.add_relation(
        "grafana-k8s:grafana-source", "prometheus-k8s:grafana-source"
    )
    await wordpress.model.wait_for_idle(
        status="active", apps=["grafana-k8s", "prometheus-k8s"], timeout=20 * 60, idle_period=60
    )
    await wordpress.model.add_relation("grafana-k8s:grafana-source", "loki-k8s:grafana-source")
    await wordpress.model.wait_for_idle(
        status="active", apps=["grafana-k8s", "loki-k8s"], timeout=20 * 60, idle_period=60
    )
    await wordpress.model.add_relation("wordpress-k8s:grafana-dashboard", "grafana-k8s")
    await wordpress.model.wait_for_idle(
        status="active", apps=["grafana-k8s", "wordpress-k8s"], timeout=30 * 60, idle_period=60
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
            functools.partial(
                datasources_exist,
                loggedin_session=sess,
                unit_address=unit.address,
                datasources=("loki", "prometheus"),
            ),
            timeout=60 * 20,
        )
        await wait_for(
            functools.partial(dashboard_exist, loggedin_session=sess, unit_address=unit.address),
            timeout=60 * 20,
        )
