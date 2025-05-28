# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=protected-access,too-many-locals

"""Integration tests for WordPress charm COS integration."""
import fnmatch
import functools
from typing import Iterable

import kubernetes
import pytest
import requests
from juju.client._definitions import FullStatus

from tests.integration.helper import WordpressApp, wait_for


def log_files_exist(unit_address: str, application_name: str, filenames: Iterable[str]) -> bool:
    """Returns whether log filenames exist in Loki logs query.

    Args:
        unit_address: Loki unit ip address.
        application_name: Application name to query logs for.
        filenames: Expected filenames to be present in logs collected by Loki.

    Returns:
        True if log files with logs exists. False otherwise.
    """
    series = requests.get(f"http://{unit_address}:3100/loki/api/v1/series", timeout=10).text
    assert application_name in series
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
                ("/var/log/apache2/error.*.log", "/var/log/apache2/access.*.log"),
            ),
            timeout=10 * 60,
        )
    kubernetes.config.load_kube_config(config_file=kube_config)
    kube_core_client = kubernetes.client.CoreV1Api()

    kube_log = kube_core_client.read_namespaced_pod_log(
        name=f"{wordpress.name}-0", namespace=wordpress.model.name, container="wordpress"
    )
    assert kube_log
