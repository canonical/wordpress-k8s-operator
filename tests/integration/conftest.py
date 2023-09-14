# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for the wordpress integration tests."""

import configparser
import json
import re
import secrets
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional

import kubernetes
import pytest
import pytest_asyncio
import swiftclient
import swiftclient.exceptions
import swiftclient.service
from juju.controller import Controller
from juju.model import Model
from pytest import Config
from pytest_operator.plugin import OpsTest

from tests.integration.helper import WordpressApp


@pytest.fixture(scope="module")
def model(ops_test: OpsTest) -> Model:
    """Return the juju model object created by pytest-operator."""
    model = ops_test.model
    assert model
    return model


@pytest.fixture(scope="module", name="kube_config")
def kube_config_fixture(pytestconfig: Config):
    """The Kubernetes cluster configuration file."""
    kube_config = pytestconfig.getoption("--kube-config")
    assert kube_config, (
        "The Kubernetes config file path should not be empty, "
        "please include it in the --kube-config parameter"
    )
    return kube_config


@pytest_asyncio.fixture(scope="module", name="machine_controller")
async def machine_controller_fixture() -> AsyncGenerator[Controller, None]:
    """The lxd controller."""
    controller = Controller()
    await controller.connect_controller("localhost")

    yield controller

    await controller.disconnect()


@pytest_asyncio.fixture(scope="module", name="machine_model")
async def machine_model_fixture(machine_controller: Controller) -> AsyncGenerator[Model, None]:
    """The machine model for jenkins agent machine charm."""
    machine_model_name = f"mysql-machine-{secrets.token_hex(2)}"
    model = await machine_controller.add_model(machine_model_name)

    yield model

    await model.disconnect()


@pytest_asyncio.fixture(scope="module", name="wordpress")
async def wordpress_fixture(
    pytestconfig: Config, ops_test: OpsTest, model: Model, kube_config: str
) -> WordpressApp:
    """Prepare the wordpress charm for integration tests."""
    charm = pytestconfig.getoption("--charm-file")
    charm_dir = Path(__file__).parent.parent.parent
    if not charm:
        charm = await ops_test.build_charm(charm_dir)
    else:
        charm = Path(charm).absolute()
    wordpress_image = pytestconfig.getoption("--wordpress-image")
    if not wordpress_image:
        raise ValueError("--wordpress-image is required to run integration test")
    app = await model.deploy(
        charm,
        resources={
            "wordpress-image": wordpress_image,
            "apache-prometheus-exporter-image": "bitnami/apache-exporter:0.11.0",
        },
        num_units=1,
        series="focal",
    )
    await model.wait_for_idle(status="blocked", apps=[app.name], timeout=30 * 60)
    return WordpressApp(app, ops_test=ops_test, kube_config=kube_config)


@pytest_asyncio.fixture(scope="module")
async def prepare_mysql(wordpress: WordpressApp, model: Model):
    """Deploy and relate the mysql-k8s charm for integration tests."""
    await model.deploy("mysql-k8s", channel="8.0/candidate", trust=True)
    await model.wait_for_idle(status="active", apps=["mysql-k8s"], timeout=30 * 60, idle_period=10)
    await model.add_relation(f"{wordpress.name}:database", "mysql-k8s:database")
    await model.wait_for_idle(
        status="active", apps=["mysql-k8s", wordpress.name], timeout=30 * 60, idle_period=10
    )


@pytest_asyncio.fixture(scope="module")
async def prepare_machine_mysql(
    wordpress: WordpressApp, machine_controller: Controller, machine_model: Model, model: Model
):
    """Deploy and relate the mysql-k8s charm for integration tests."""
    await machine_model.deploy("mysql", channel="8.0/candidate", trust=True)
    await machine_model.create_offer("mysql:database")
    await machine_model.wait_for_idle(status="active", apps=["mysql"], timeout=30 * 60)
    await model.add_relation(
        f"{wordpress.name}:database",
        f"{machine_controller.controller_name}:admin/{machine_model.name}.mysql",
    )


@pytest.fixture(scope="module", name="openstack_environment")
def openstack_environment_fixture(pytestconfig: Config):
    """Parse the openstack rc style configuration file from the --openstack-rc argument.

    Returns: a dictionary of environment variables and values, or None if --openstack-rc isn't
        provided.
    """
    rc_file = pytestconfig.getoption("--openstack-rc")
    if not rc_file:
        raise ValueError("--openstack-rc is required to run this test")
    with open(rc_file, encoding="utf-8") as rc_fo:
        rc_file = rc_fo.read()
    rc_file = re.sub("^export ", "", rc_file, flags=re.MULTILINE)
    openstack_conf = configparser.ConfigParser()
    openstack_conf.read_string("[DEFAULT]\n" + rc_file)
    return {k.upper(): v for k, v in openstack_conf["DEFAULT"].items()}


@pytest.fixture(scope="module", name="swift_conn")
def swift_conn_fixture(openstack_environment) -> Optional[swiftclient.Connection]:
    """Create a swift connection client."""
    return swiftclient.Connection(
        authurl=openstack_environment["OS_AUTH_URL"],
        auth_version="3",
        user=openstack_environment["OS_USERNAME"],
        key=openstack_environment["OS_PASSWORD"],
        os_options={
            "user_domain_name": openstack_environment["OS_USER_DOMAIN_ID"],
            "project_domain_name": openstack_environment["OS_PROJECT_DOMAIN_ID"],
            "project_name": openstack_environment["OS_PROJECT_NAME"],
        },
    )


@pytest.fixture(scope="module", name="swift_config")
def swift_config_fixture(
    ops_test: OpsTest,
    swift_conn: swiftclient.Connection,
    openstack_environment: Dict[str, str],
) -> Dict[str, str]:
    """Create a swift config dict that can be used for wp_plugin_openstack-objectstorage_config."""
    swift_service = swiftclient.service.SwiftService(
        options={
            "auth_version": "3",
            "os_auth_url": openstack_environment["OS_AUTH_URL"],
            "os_username": openstack_environment["OS_USERNAME"],
            "os_password": openstack_environment["OS_PASSWORD"],
            "os_project_name": openstack_environment["OS_PROJECT_NAME"],
            "os_project_domain_name": openstack_environment["OS_PROJECT_DOMAIN_ID"],
        }
    )
    container = f"wordpress_{ops_test.model_name}"
    # if the container exists, remove the container
    swift_service.delete(container=container)
    # create a swift container for our test
    swift_conn.put_container(container)
    # change container ACL to allow us getting an object by HTTP request without any authentication
    # the swift server will act as a static HTTP server after this
    swift_service.post(container=container, options={"read_acl": ".r:*,.rlistings"})

    return {
        "auth-url": openstack_environment["OS_AUTH_URL"] + "/v3",
        "bucket": container,
        "password": openstack_environment["OS_PASSWORD"],
        "object-prefix": "wp-content/uploads/",
        "region": openstack_environment["OS_REGION_NAME"],
        "tenant": openstack_environment["OS_PROJECT_NAME"],
        "domain": openstack_environment["OS_PROJECT_DOMAIN_ID"],
        "swift-url": swift_conn.url,
        "username": openstack_environment["OS_USERNAME"],
        "copy-to-swift": "1",
        "serve-from-swift": "1",
        "remove-local-file": "0",
    }


@pytest_asyncio.fixture(scope="module")
async def prepare_swift(wordpress: WordpressApp, swift_config: Dict[str, str]):
    """Configure the wordpress charm to use openstack swift object storage."""
    await wordpress.set_config(
        {"wp_plugin_openstack-objectstorage_config": json.dumps(swift_config)}
    )
    await wordpress.model.wait_for_idle(status="active", apps=[wordpress.name], timeout=30 * 60)


@pytest_asyncio.fixture(scope="module")
async def prepare_nginx_ingress(wordpress: WordpressApp, prepare_mysql):
    """Deploy and relate nginx-ingress-integrator charm for integration tests."""
    await wordpress.model.deploy("nginx-ingress-integrator", series="focal", trust=True)
    await wordpress.model.wait_for_idle(
        status="active", apps=["nginx-ingress-integrator"], timeout=30 * 60
    )
    await wordpress.model.add_relation(f"{wordpress.name}:nginx-route", "nginx-ingress-integrator")
    await wordpress.model.wait_for_idle(status="active")


@pytest_asyncio.fixture(scope="module")
async def prepare_prometheus(wordpress: WordpressApp, prepare_mysql):
    """Deploy and relate prometheus-k8s charm for integration tests."""
    prometheus = await wordpress.model.deploy("prometheus-k8s", channel="1.0/stable", trust=True)
    await wordpress.model.wait_for_idle(
        status="active", apps=[prometheus.name], raise_on_error=False, timeout=30 * 60
    )
    await wordpress.model.add_relation(f"{wordpress.name}:metrics-endpoint", prometheus.name)
    await wordpress.model.wait_for_idle(
        status="active",
        apps=[prometheus.name, wordpress.name],
        timeout=20 * 60,
        idle_period=10,
        raise_on_error=False,
    )


@pytest_asyncio.fixture(scope="module")
async def prepare_loki(wordpress: WordpressApp, prepare_mysql):
    """Deploy and relate loki-k8s charm for integration tests."""
    loki = await wordpress.model.deploy("loki-k8s", channel="1.0/stable", trust=True)
    await wordpress.model.wait_for_idle(
        apps=[loki.name], status="active", timeout=20 * 60, idle_period=10
    )
    await wordpress.model.add_relation(f"{wordpress.name}:logging", loki.name)
    await wordpress.model.wait_for_idle(
        apps=[loki.name, wordpress.name], status="active", timeout=40 * 60, idle_period=10
    )


@pytest_asyncio.fixture(scope="module", name="mysql_pod_config")
async def mysql_pod_config_fixture(kube_config: str, ops_test: OpsTest, model: Model):
    """Deploy a mysql pod in k8s and return the mysql configuration for wordpress charm."""
    kubernetes.config.load_kube_config(config_file=kube_config)
    kube_core_client = kubernetes.client.CoreV1Api()
    namespace = ops_test.model_name
    kube_core_client.create_namespaced_pod(
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
                            kubernetes.client.V1EnvVar("MYSQL_DATABASE", "wordpress"),
                            kubernetes.client.V1EnvVar("MYSQL_USER", "wordpress"),
                            kubernetes.client.V1EnvVar("MYSQL_PASSWORD", "wordpress"),
                        ],
                    )
                ]
            ),
        ),
    )

    def is_mysql_ready() -> bool:
        """Check the status of mysql pod.

        Returns:
            True if ready, False otherwise.
        """
        mysql_status = kube_core_client.read_namespaced_pod(
            name="mysql", namespace=namespace
        ).status
        if mysql_status.conditions is None:
            return False
        for condition in mysql_status.conditions:
            if condition.type == "Ready" and condition.status == "True":
                return True
        return False

    await model.block_until(is_mysql_ready, timeout=300, wait_period=3)
    return {
        "db_host": kube_core_client.read_namespaced_pod(
            name="mysql", namespace=namespace
        ).status.pod_ip,
        "db_name": "wordpress",
        "db_user": "wordpress",
        "db_password": "wordpress",
    }


@pytest_asyncio.fixture(scope="module")
async def prepare_mysql_pod(wordpress: WordpressApp, mysql_pod_config: Dict[str, str]):
    """Deploy mysql pod and config wordpress charm to use that."""
    await wordpress.set_config(mysql_pod_config)
    await wordpress.wait_for_wordpress_idle(status="active")
