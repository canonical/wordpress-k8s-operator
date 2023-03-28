# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for WordPress charm integration tests."""

import asyncio
import configparser
import json
import logging
import pathlib
import re
import typing

import kubernetes
import pytest
import pytest_asyncio
import swiftclient
import swiftclient.exceptions
import swiftclient.service
from juju.action import Action
from juju.application import Application
from juju.model import Model
from pytest import FixtureRequest
from pytest_operator.plugin import OpsTest

from lib.charms.grafana_k8s.v0.grafana_dashboard import (
    DEFAULT_RELATION_NAME as GRAFANA_RELATION_NAME,
)
from lib.charms.loki_k8s.v0.loki_push_api import DEFAULT_RELATION_NAME as LOKI_RELATION_NAME
from lib.charms.prometheus_k8s.v0.prometheus_scrape import (
    DEFAULT_RELATION_NAME as PROMETHEUS_RELATION_NAME,
)
from tests.integration.wordpress_client_for_test import WordpressClient

logger = logging.getLogger()


@pytest.fixture(scope="module", name="model")
def model_fixture(ops_test: OpsTest) -> Model:
    """Get current valid model created for integraion testing with module scope."""
    assert ops_test.model
    return ops_test.model


@pytest_asyncio.fixture(scope="function", name="app_config")
async def app_config_fixture(request, model: Model):
    """Change the charm config to specific values and revert that after test."""
    config = request.param
    application: Application = model.applications["wordpress"]
    original_config: dict = await application.get_config()
    original_config = {k: v["value"] for k, v in original_config.items() if k in config}
    await application.set_config(config)
    await model.wait_for_idle()

    yield config

    await application.set_config(original_config)
    await model.wait_for_idle()


@pytest.fixture(scope="module", name="application_name")
def fixture_application_name():
    """Default application name."""
    return "wordpress"


@pytest_asyncio.fixture(scope="module", name="get_default_admin_password")
async def fixture_get_default_admin_password(model: Model, application_name: str):
    """Create a function to get the default admin password using get-initial-password action."""

    async def _get_default_admin_password() -> str:
        """Get default admin password using get-initial-password action.

        Returns:
            WordPress admin account password
        """
        application: Application = model.applications[application_name]
        action: Action = await application.units[0].run_action("get-initial-password")
        await action.wait()
        return action.results["password"]

    return _get_default_admin_password


@pytest_asyncio.fixture(scope="function", name="default_admin_password")
async def fixture_default_admin_password(get_default_admin_password):
    """Get the default admin password using the get-initial-password action."""
    return await get_default_admin_password()


@pytest_asyncio.fixture(scope="module", name="get_unit_ip_list")
async def fixture_get_unit_ip_list(ops_test: OpsTest, application_name: str):
    """Retrieve unit ip addresses, similar to fixture_get_unit_status_list."""

    async def _get_unit_ip_list():
        """Retrieve unit ip addresses, similar to fixture_get_unit_status_list.

        Returns:
            list of WordPress units ip addresses.
        """
        _, status, _ = await ops_test.juju("status", "--format", "json")
        status = json.loads(status)
        units = status["applications"][application_name]["units"]
        ip_list = []
        for key in sorted(units.keys(), key=lambda n: int(n.split("/")[-1])):
            ip_list.append(units[key]["address"])
        return ip_list

    yield _get_unit_ip_list


@pytest_asyncio.fixture(scope="function", name="unit_ip_list")
async def fixture_unit_ip_list(get_unit_ip_list: typing.Callable[[], typing.Awaitable[list[str]]]):
    """A fixture containing ip addresses of current units.

    Yields:
        ip addresses of current WordPress units.
    """
    yield await get_unit_ip_list()


@pytest_asyncio.fixture(scope="function", name="get_theme_list_from_ip")
async def fixture_get_theme_list_from_ip(default_admin_password: str):
    """Retrieve installed themes from the WordPress instance."""

    def _get_theme_list_from_ip(unit_ip: str):
        """Retrieve installed themes from the WordPress instance.

        Args:
            unit_ip: target WordPress unit ip address

        Returns:
            list of installed WordPress themes in given instance
        """
        wordpress_client = WordpressClient(
            host=unit_ip, username="admin", password=default_admin_password, is_admin=True
        )
        return wordpress_client.list_themes()

    return _get_theme_list_from_ip


@pytest_asyncio.fixture(scope="function", name="get_plugin_list_from_ip")
async def fixture_get_plugin_list_from_ip(default_admin_password: str):
    """Retrieve installed plugins from the WordPress instance."""

    def _get_plugin_list_from_ip(unit_ip: str):
        """Retrieve installed plugins from the Wordpress instance.

        Args:
            unit_ip: target WordPress unit ip address

        Returns:
            list of installed WordPress plugins in given instance
        """
        wordpress_client = WordpressClient(
            host=unit_ip, username="admin", password=default_admin_password, is_admin=True
        )
        return wordpress_client.list_plugins()

    return _get_plugin_list_from_ip


@pytest.fixture(scope="module", name="openstack_environment")
def openstack_environment_fixture(request: FixtureRequest, num_units: int):
    """Parse the openstack rc style configuration file from the --openstack-rc argument.

    Returns: a dictionary of environment variables and values, or None if --openstack-rc isn't
        provided.
    """
    rc_file = request.config.getoption("--openstack-rc")
    assert num_units == 1 or rc_file, (
        "swift plugin is required for multi-unit deployment, "
        "please include an openstack configuration in the --openstack-rc parameter "
    )
    if not rc_file:
        return None
    with open(rc_file, encoding="utf-8") as rc_fo:
        rc_file = rc_fo.read()
    rc_file = re.sub("^export ", "", rc_file, flags=re.MULTILINE)
    openstack_conf = configparser.ConfigParser()
    openstack_conf.read_string("[DEFAULT]\n" + rc_file)
    return {k.upper(): v for k, v in openstack_conf["DEFAULT"].items()}


@pytest.fixture
def akismet_api_key(request: FixtureRequest):
    """The Akismet API key, in str."""
    api_key = request.config.getoption("--akismet-api-key")
    assert (
        api_key
    ), "Akismet API key should not be empty, please include it in the --akismet-api-key parameter"
    return api_key


@pytest.fixture(name="openid_username")
def openid_username_fixture(request: FixtureRequest):
    """The OpenID username for testing the OpenID plugin."""
    openid_username = request.config.getoption("--openid-username")
    assert (
        openid_username
    ), "OpenID username should not be empty, please include it in the --openid-username parameter"
    return openid_username


@pytest.fixture(name="openid_password")
def openid_password_fixture(request: FixtureRequest):
    """The OpenID username for testing the OpenID plugin."""
    openid_password = request.config.getoption("--openid-password")
    assert (
        openid_password
    ), "OpenID password should not be empty, please include it in the --openid-password parameter"
    return openid_password


@pytest.fixture(scope="module", name="launchpad_team")
def launchpad_team_fixture(request: FixtureRequest):
    """The launchpad team for the OpenID account."""
    launchpad_team = request.config.getoption("--launchpad-team")
    assert (
        launchpad_team
    ), "Launchpad team should not be empty, please include it in the --launchpad-team parameter"
    return launchpad_team


@pytest.fixture(scope="module", name="kube_config")
def kube_config_fixture(request: FixtureRequest):
    """The Kubernetes cluster configuration file."""
    kube_config = request.config.getoption("--kube-config")
    assert kube_config, (
        "The Kubernetes config file path should not be empty, "
        "please include it in the --kube-config parameter"
    )
    return kube_config


@pytest.fixture(scope="module", name="num_units")
def num_units_fixture(request: FixtureRequest):
    """Number of units to be deployed in tests."""
    return request.config.getoption("--num-units")


@pytest.fixture(scope="module", name="db_from_config")
def db_from_config_fixture(request: FixtureRequest):
    """Whether to use database configuration config file or from relation."""
    return request.config.getoption("--test-db-from-config")


@pytest.fixture(scope="module", name="screenshot_dir")
def screenshot_dir_fixture(request: FixtureRequest):
    """A directory to store screenshots generated by test_upgrade."""
    screenshot_dir = request.config.getoption("--screenshot-dir")
    assert screenshot_dir, (
        "Screenshot directory should not be empty, "
        "please include it in the --screenshot-dir parameter"
    )
    return pathlib.Path(screenshot_dir)


@pytest.fixture(scope="module", name="wordpress_image")
def wordpress_image_fixture(request: FixtureRequest):
    """Wordpress docker image built for the WordPress charm."""
    return request.config.getoption("--wordpress-image")


@pytest.fixture(scope="module", name="kube_core_client")
def kube_core_client_fixture(kube_config):
    """Create a kubernetes client for core API v1."""
    kubernetes.config.load_kube_config(config_file=kube_config)
    kubernetes_client_v1 = kubernetes.client.CoreV1Api()
    return kubernetes_client_v1


@pytest.fixture(name="kube_networking_client")
def kube_networking_client_fixture(kube_config):
    """Create a kubernetes client for networking API v1."""
    kubernetes.config.load_kube_config(config_file=kube_config)
    kubernetes_client_v1 = kubernetes.client.NetworkingV1Api()
    return kubernetes_client_v1


@pytest.fixture(scope="module", name="pod_db_database")
def pod_db_database_fixture():
    """MYSQL database name for create the test database pod."""
    return "wordpress"


@pytest.fixture(scope="module", name="pod_db_user")
def pod_db_user_fixture():
    """MYSQL database username for create the test database pod."""
    return "wordpress"


@pytest.fixture(scope="module", name="pod_db_password")
def pod_db_password_fixture():
    """MYSQL database password for create the test database pod."""
    return "wordpress-password"


@pytest.fixture(scope="module", name="deploy_and_wait_for_mysql_pod")
def deploy_and_wait_for_mysql_pod_fixture(
    ops_test, kube_core_client, pod_db_database, pod_db_user, pod_db_password
):
    """Return an async function that deploy and wait for a mysql pod ready in current namespace.

    This is used for testing WordPress charm's capability of interacting with an external non-charm
    MySQL database.
    """

    async def wait_mysql_pod_ready() -> None:
        """Create a mysql pod and wait for it to become ready."""
        # create a pod to test the capability of the WordPress charm to interactive with an
        # external MYSQL database via charm db configurations.
        kube_core_client.create_namespaced_pod(
            namespace=ops_test.model_name,
            body=kubernetes.client.V1Pod(
                metadata=kubernetes.client.V1ObjectMeta(
                    name="mysql", namespace=ops_test.model_name
                ),
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
                                kubernetes.client.V1EnvVar("MYSQL_DATABASE", pod_db_database),
                                kubernetes.client.V1EnvVar("MYSQL_USER", pod_db_user),
                                kubernetes.client.V1EnvVar("MYSQL_PASSWORD", pod_db_password),
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
                name="mysql", namespace=ops_test.model_name
            ).status
            if mysql_status.conditions is None:
                return False
            for condition in mysql_status.conditions:
                if condition.type == "Ready" and condition.status == "True":
                    return True
            return False

        await ops_test.model.block_until(is_mysql_ready, timeout=300, wait_period=3)

    return wait_mysql_pod_ready


@pytest_asyncio.fixture(scope="module", name="build_and_deploy")
async def build_and_deploy_fixture(
    num_units,
    ops_test: OpsTest,
    model: Model,
    application_name: str,
    deploy_and_wait_for_mysql_pod,
    wordpress_image,
):
    """Deploy all required charms and kubernetes pods for tests."""

    async def build_and_deploy_wordpress():
        """Build wordpress charm from source and deploy to current testing model."""
        my_charm = await ops_test.build_charm(".")
        await model.deploy(
            my_charm,
            resources={
                "wordpress-image": wordpress_image,
                "apache-prometheus-exporter-image": "bitnami/apache-exporter:0.11.0",
            },
            application_name=application_name,
            series="jammy",
            num_units=num_units,
        )

    await asyncio.gather(
        build_and_deploy_wordpress(),
        deploy_and_wait_for_mysql_pod(),
        model.deploy("charmed-osm-mariadb-k8s", application_name="mariadb"),
        # temporary fix for the CharmHub problem
        ops_test.juju(
            "deploy",
            "nginx-ingress-integrator",
            "ingress",
            "--channel",
            "edge",
            "--series",
            "focal",
            "--trust",
            check=True,
        ),
    )
    await model.wait_for_idle()


@pytest_asyncio.fixture(scope="module", name="mysql")
async def mysql_fixture(model: Model):
    """Deploy mysql-k8s application fixture."""
    mysql = await model.deploy("mysql-k8s", channel="edge")
    return mysql


@pytest_asyncio.fixture(scope="module", name="prometheus")
async def prometheus_fixture(
    model: Model, application_name: str
) -> typing.AsyncGenerator[Application, None]:
    """Deploy and yield prometheus charm application with relation to WordPress charm."""
    prometheus = await model.deploy("prometheus-k8s", channel="stable", trust=True)
    await prometheus.relate(
        PROMETHEUS_RELATION_NAME, f"{application_name}:{PROMETHEUS_RELATION_NAME}"
    )
    yield prometheus
    await prometheus.remove_relation(
        PROMETHEUS_RELATION_NAME, f"{application_name}:{PROMETHEUS_RELATION_NAME}"
    )


@pytest_asyncio.fixture(scope="module", name="loki")
async def loki_fixture(
    model: Model, application_name: str
) -> typing.AsyncGenerator[Application, None]:
    """Deploy and return loki charm application with relation to WordPress charm."""
    loki = await model.deploy("loki-k8s", channel="stable", trust=True)
    await loki.relate(LOKI_RELATION_NAME, f"{application_name}:{LOKI_RELATION_NAME}")
    yield loki
    await loki.remove_relation(LOKI_RELATION_NAME, f"{application_name}:{LOKI_RELATION_NAME}")


@pytest_asyncio.fixture(scope="module", name="grafana")
async def grafana_fixture(
    model: Model, application_name: str
) -> typing.AsyncGenerator[Application, None]:
    """Deploy and return grafana charm application with relation to WordPress charm."""
    grafana = await model.deploy("grafana-k8s", channel="stable", trust=True)
    await grafana.relate(GRAFANA_RELATION_NAME, f"{application_name}:{GRAFANA_RELATION_NAME}")
    yield grafana
    await grafana.remove_relation(
        GRAFANA_RELATION_NAME, f"{application_name}:{GRAFANA_RELATION_NAME}"
    )


@pytest.fixture(scope="module", name="test_image")
def image_fixture() -> bytes:
    """A JPG image that can be used in tests."""
    return open("tests/integration/files/canonical_aubergine_hex.jpg", "rb").read()


@pytest.fixture(scope="module", name="swift_conn")
def swift_conn_fixture(openstack_environment) -> swiftclient.Connection | None:
    """Create a swift connection client."""
    if openstack_environment is None:
        return None
    swift_conn = swiftclient.Connection(
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
    return swift_conn


@pytest.fixture(scope="module", name="swift_config")
def swift_config_fixture(
    request: pytest.FixtureRequest,
    swift_conn: swiftclient.Connection,
    openstack_environment: typing.Optional[typing.Dict[str, str]],
) -> typing.Optional[typing.Dict[str, str]]:
    """Create a swift config dict that can be used for wp_plugin_openstack-objectstorage_config."""
    if openstack_environment is None:
        return None
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
    container = f"wordpress_{request.module.__name__.split('.')[-1]}"
    logger.info("Use container %s", container)
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
