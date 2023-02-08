# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for commonly used internal helpers for integration tests."""

from typing import cast

from juju.action import Action
from juju.application import Application
from juju.client._definitions import ApplicationStatus, DetailedStatus, FullStatus, UnitStatus
from juju.unit import Unit
from kubernetes import kubernetes
from kubernetes.client import CoreV1Api, V1Pod, V1PodStatus

from .types_ import DatabaseConfig


def assert_active_status(status: FullStatus, app: Application):
    """Assert application active status from latest model status.

    Args:
        status: latest model status.
        app: target application to check representative status.
    """
    app_state = cast(ApplicationStatus, status.applications[app.name])
    detailed_status = cast(DetailedStatus, app_state.status)
    assert detailed_status.status == "active"


def get_unit_ips(status: FullStatus, app: Application) -> tuple[str, ...]:
    """Get application unit ips from latest model status.

    Args:
        status: latest model status.
        app: target application to get deployed unit ips.

    Returns:
        Application unit address.
    """
    app_state = cast(ApplicationStatus, status.applications[app.name])
    return tuple(
        cast(str, unit.address) for unit in cast(dict[str, UnitStatus], app_state.units).values()
    )


async def get_admin_password(app: Application) -> str:
    """Get default WordPress admin password from get-initial-password action.

    Args:
        app: WordPress application with active units.

    Returns:
        Default WordPress admin password.
    """
    unit: Unit = app.units[0]
    action: Action = await unit.run_action("get-initial-password")
    await action.wait()
    return action.results["password"]


def deploy_mysql_pod(kube_client: CoreV1Api, db_config: DatabaseConfig, namespace: str) -> V1Pod:
    """Deploy mysql database as a kubernetes pod.

    Args:
        kube_client: Kubernetes API client.
        db_config: database configuration for mysql.
        namespace: namespace to deploy mysql pod to.

    Returns:
        Kubernetes V1Pod.
    """
    pod = kube_client.create_namespaced_pod(
        namespace=namespace,
        body=kubernetes.client.V1Pod(
            metadata=kubernetes.client.V1ObjectMeta(name="mysql", namespace=namespace),
            kind="Pod",
            api_version="v1",
            spec=kubernetes.client.V1PodSpec(
                containers=[
                    kubernetes.client.V1Container(
                        name="mysql",
                        image="mysql:latest",
                        readiness_probe=kubernetes.client.V1Probe(
                            kubernetes.client.V1ExecAction(
                                ["mysqladmin", "ping", "-h", "localhost"]
                            ),
                            initial_delay_seconds=10,
                            period_seconds=5,
                        ),
                        liveness_probe=kubernetes.client.V1Probe(
                            kubernetes.client.V1ExecAction(
                                ["mysqladmin", "ping", "-h", "localhost"]
                            ),
                            initial_delay_seconds=10,
                            period_seconds=5,
                        ),
                        env=[
                            kubernetes.client.V1EnvVar("MYSQL_ROOT_PASSWORD", "root-password"),
                            kubernetes.client.V1EnvVar("MYSQL_DATABASE", db_config.name),
                            kubernetes.client.V1EnvVar("MYSQL_USER", db_config.user),
                            kubernetes.client.V1EnvVar("MYSQL_PASSWORD", db_config.password),
                        ],
                    )
                ]
            ),
        ),
    )

    return cast(V1Pod, pod)


def get_mysql_pod(kube_client: CoreV1Api, namespace: str):
    """Get instance of deployed mysql pod.

    Args:
        kube_client: kubernetes API client.
        namespace: namespace to search pysql pod from.

    Returns:
        Mysql pod instance.
    """
    pod = cast(V1Pod, kube_client.read_namespaced_pod(name="mysql", namespace=namespace))
    return pod


def is_mysql_ready(kube_client: CoreV1Api, namespace: str) -> bool:
    """Check ready status of mysql pod.

    Args:
        kube_client: Kubernetes API client.
        namespace: namespace to deploy mysql pod to.

    Returns:
        True if ready, False otherwise.
    """
    pod = get_mysql_pod(kube_client=kube_client, namespace=namespace)
    pod_status = cast(V1PodStatus, pod.status)
    if pod_status.conditions is None:
        return False
    for condition in pod_status.conditions:
        if condition.type == "Ready" and condition.status == "True":
            return True
    return False
