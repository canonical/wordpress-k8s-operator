# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=protected-access,too-many-locals

"""Integration tests for WordPress charm."""

import functools
from typing import Iterable, List

import pytest
import requests
from juju.action import Action
from juju.application import Application
from juju.client._definitions import FullStatus
from juju.model import Model
from kubernetes import kubernetes
from pytest_operator.plugin import OpsTest

from cos import APACHE_PROMETHEUS_SCRAPE_PORT

from .helpers import wait_for


@pytest.mark.usefixtures("build_and_deploy")
async def test_prometheus_integration(
    application_name,
    model: Model,
    prometheus: Application,
    unit_ip_list: List[str],
):
    """
    arrange: none.
    act: deploy the WordPress charm and relations established with prometheus.
    assert: prometheus metrics endpoint for prometheus is active and prometheus has active scrape
        targets.
    """
    await model.add_relation(f"{application_name}:database", "mysql-k8s:database")
    await model.wait_for_idle(status="active")

    for unit_ip in unit_ip_list:
        res = requests.get(f"http://{unit_ip}:{APACHE_PROMETHEUS_SCRAPE_PORT}", timeout=10)
        assert res.status_code == 200
    status: FullStatus = await model.get_status(filters=[prometheus.name])
    for unit in status.applications[prometheus.name].units.values():
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


async def test_loki_integration(
    ops_test: OpsTest,
    model: Model,
    loki: Application,
    application_name: str,
    kube_core_client: kubernetes.client.CoreV1Api,
):
    """
    arrange: after WordPress charm has been deployed and relations established.
    act: loki charm joins relation
    assert: loki joins relation successfully, logs are being output to container and to files for
        loki to scrape.
    """
    await model.wait_for_idle(apps=[loki.name], status="active", timeout=20 * 60)

    status: FullStatus = await model.get_status(filters=[loki.name])
    for unit in status.applications[loki.name].units.values():
        await wait_for(
            functools.partial(
                log_files_exist,
                unit.address,
                application_name,
                ("/var/log/apache2/error.log", "/var/log/apache2/access.log"),
            )
        )
    kube_log = kube_core_client.read_namespaced_pod_log(
        name=f"{application_name}-0", namespace=ops_test.model_name, container="wordpress"
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


async def test_grafana_integration(
    model: Model,
    prometheus: Application,
    loki: Application,
    grafana: Application,
):
    """
    arrange: after WordPress charm has been deployed and relations established among cos.
    act: grafana charm joins relation
    assert: grafana wordpress dashboard can be found
    """
    await prometheus.relate("grafana-source", f"{grafana.name}:grafana-source")
    await loki.relate("grafana-source", f"{grafana.name}:grafana-source")
    await model.wait_for_idle(
        apps=[prometheus.name, loki.name, grafana.name], status="active", timeout=20 * 60
    )

    action: Action = await grafana.units[0].run_action("get-admin-password")
    await action.wait()
    password = action.results["admin-password"]

    status: FullStatus = await model.get_status(filters=[grafana.name])
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
            )
        )
        await wait_for(
            functools.partial(dashboard_exist, loggedin_session=sess, unit_address=unit.address)
        )
