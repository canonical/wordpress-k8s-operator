# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for WordPress charm integration tests."""

import asyncio
import base64
import configparser
import datetime
import logging
import pathlib
import re
import secrets
import typing

import cryptography.hazmat.primitives.asymmetric.rsa
import cryptography.hazmat.primitives.hashes
import cryptography.hazmat.primitives.serialization
import cryptography.x509
import juju.action
import juju.application
import kubernetes
import pytest
import pytest_asyncio
import pytest_operator.plugin
import requests
import swiftclient
import swiftclient.exceptions
import swiftclient.service

from tests.integration.wordpress_client_for_test import WordpressClient

logger = logging.getLogger()


@pytest_asyncio.fixture(scope="function", name="app_config")
async def app_config_fixture(request, ops_test: pytest_operator.plugin.OpsTest):
    """Change the charm config to specific values and revert that after test"""
    assert ops_test.model
    config = request.param
    application: juju.application.Application = ops_test.model.applications["wordpress"]
    original_config: dict = await application.get_config()
    original_config = {k: v["value"] for k, v in original_config.items() if k in config}
    await application.set_config(config)
    await ops_test.model.wait_for_idle()

    yield config

    await application.set_config(original_config)
    await ops_test.model.wait_for_idle()


@pytest.fixture(scope="module", name="application_name")
def fixture_application_name():
    """Default application name."""
    return "wordpress"


@pytest_asyncio.fixture(scope="function", name="default_admin_password")
async def fixture_default_admin_password(
    ops_test: pytest_operator.plugin.OpsTest, application_name
):
    """Get the default admin password using the get-initial-password action."""
    assert ops_test.model
    application: juju.application.Application = ops_test.model.applications[application_name]
    action: juju.action.Action = await application.units[0].run_action("get-initial-password")
    await action.wait()

    yield action.results["password"]


@pytest_asyncio.fixture(scope="function", name="get_unit_ip_list")
async def fixture_get_unit_ip_list(ops_test: pytest_operator.plugin.OpsTest, application_name):
    """Helper function to retrieve unit ip addresses, similar to fixture_get_unit_status_list"""

    async def _get_unit_ip_list():
        status = await ops_test.model.get_status()
        units = status.applications[application_name].units
        ip_list = []
        for key in sorted(units.keys(), key=lambda n: int(n.split("/")[-1])):
            ip_list.append(units[key].address)
        return ip_list

    yield _get_unit_ip_list


@pytest_asyncio.fixture(scope="function", name="unit_ip_list")
async def fixture_unit_ip_list(get_unit_ip_list):
    """A fixture containing ip addresses of current units"""
    yield await get_unit_ip_list()


@pytest_asyncio.fixture(scope="function", name="get_theme_list_from_ip")
async def fixture_get_theme_list_from_ip(default_admin_password):
    """Retrieve installed themes from the WordPress instance"""

    def _get_theme_list_from_ip(unit_ip):
        wordpress_client = WordpressClient(
            host=unit_ip, username="admin", password=default_admin_password, is_admin=True
        )
        return wordpress_client.list_themes()

    return _get_theme_list_from_ip


@pytest_asyncio.fixture(scope="function", name="get_plugin_list_from_ip")
async def fixture_get_plugin_list_from_ip(default_admin_password):
    """Retrieve installed plugins from the WordPress instance"""

    def _get_plugin_list_from_ip(unit_ip):
        wordpress_client = WordpressClient(
            host=unit_ip, username="admin", password=default_admin_password, is_admin=True
        )
        return wordpress_client.list_plugins()

    return _get_plugin_list_from_ip


@pytest.fixture(scope="module", name="openstack_environment")
def openstack_environment_fixture(request, num_units):
    """Parse the openstack rc style configuration file from the --openstack-rc argument

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
def akismet_api_key(request):
    """The Akismet API key, in str"""
    api_key = request.config.getoption("--akismet-api-key")
    assert (
        api_key
    ), "Akismet API key should not be empty, please include it in the --akismet-api-key parameter"
    return api_key


@pytest.fixture(name="openid_username")
def openid_username_fixture(request):
    """The OpenID username for testing the OpenID plugin"""
    openid_username = request.config.getoption("--openid-username")
    assert (
        openid_username
    ), "OpenID username should not be empty, please include it in the --openid-username parameter"
    return openid_username


@pytest.fixture(name="openid_password")
def openid_password_fixture(request):
    """The OpenID username for testing the OpenID plugin"""
    openid_password = request.config.getoption("--openid-password")
    assert (
        openid_password
    ), "OpenID password should not be empty, please include it in the --openid-password parameter"
    return openid_password


@pytest.fixture(scope="module", name="launchpad_team")
def launchpad_team_fixture(request):
    """The launchpad team for the OpenID account"""
    launchpad_team = request.config.getoption("--launchpad-team")
    assert (
        launchpad_team
    ), "Launchpad team should not be empty, please include it in the --launchpad-team parameter"
    return launchpad_team


@pytest.fixture(scope="module", name="kube_config")
def kube_config_fixture(request):
    """The Kubernetes cluster configuration file"""
    openid_password = request.config.getoption("--kube-config")
    assert openid_password, (
        "The Kubernetes config file path should not be empty, "
        "please include it in the --kube-config parameter"
    )
    return openid_password


@pytest.fixture(scope="module", name="num_units")
def num_units_fixture(request):
    """Number of units to be deployed in tests."""
    return request.config.getoption("--num-units")


@pytest.fixture(scope="module", name="screenshot_dir")
def screenshot_dir_fixture(request):
    """A directory to store screenshots generated by test_upgrade."""
    screenshot_dir = request.config.getoption("--screenshot-dir")
    assert screenshot_dir, (
        "Screenshot directory should not be empty, "
        "please include it in the --screenshot-dir parameter"
    )
    return pathlib.Path(screenshot_dir)


@pytest.fixture(scope="module", name="wordpress_image")
def wordpress_image_fixture(request):
    """Wordpress docker image built for the WordPress charm."""
    return request.config.getoption("--wordpress-image")


@pytest.fixture(scope="module", name="kube_core_client")
def kube_core_client_fixture(kube_config):
    """Create a kubernetes client for core API v1"""
    kubernetes.config.load_kube_config(config_file=kube_config)
    kubernetes_client_v1 = kubernetes.client.CoreV1Api()
    return kubernetes_client_v1


@pytest.fixture(name="kube_networking_client")
def kube_networking_client_fixture(kube_config):
    """Create a kubernetes client for networking API v1"""
    kubernetes.config.load_kube_config(config_file=kube_config)
    kubernetes_client_v1 = kubernetes.client.NetworkingV1Api()
    return kubernetes_client_v1


@pytest.fixture(scope="function", name="create_self_signed_tls_secret")
def create_self_signed_tls_secret_fixture(
    kube_core_client, ops_test: pytest_operator.plugin.OpsTest
):
    """Create a self-signed TLS certificate as a Kubernetes secret."""
    assert ops_test.model
    created_secrets = []
    namespace = ops_test.model.info["name"]

    def create_self_signed_tls_secret(host):
        """Function to create a self-signed TLS certificate as a Kubernetes secret.

        Args:
            host: Certificate subject common name.

        Returns:
            (Tuple[str, bytes]) A tuple of the Kubernetes secret name as str, and certificate
            public key in bytes.
        """
        secret_name = f"tls-secret-{host}-{secrets.token_hex(8)}"
        key = cryptography.hazmat.primitives.asymmetric.rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        private_key_pem = key.private_bytes(
            encoding=cryptography.hazmat.primitives.serialization.Encoding.PEM,
            format=cryptography.hazmat.primitives.serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=cryptography.hazmat.primitives.serialization.NoEncryption(),
        )
        issuer = subject = cryptography.x509.Name(
            [
                cryptography.x509.NameAttribute(cryptography.x509.NameOID.COUNTRY_NAME, "UK"),
                cryptography.x509.NameAttribute(
                    cryptography.x509.NameOID.ORGANIZATION_NAME, "Canonical Group Ltd"
                ),
                cryptography.x509.NameAttribute(cryptography.x509.NameOID.COMMON_NAME, host),
            ]
        )
        cert = (
            cryptography.x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(cryptography.x509.random_serial_number())
            .add_extension(
                cryptography.x509.SubjectAlternativeName([cryptography.x509.DNSName(host)]),
                critical=False,
            )
            .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=10))
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=10))
            .sign(key, cryptography.hazmat.primitives.hashes.SHA256())
        )
        public_key_pem = cert.public_bytes(
            cryptography.hazmat.primitives.serialization.Encoding.PEM
        )
        kube_core_client.create_namespaced_secret(
            namespace=namespace,
            body=kubernetes.client.V1Secret(
                metadata={"name": secret_name, "namespace": namespace},
                data={
                    "tls.crt": base64.standard_b64encode(public_key_pem).decode(),
                    "tls.key": base64.standard_b64encode(private_key_pem).decode(),
                },
                type="kubernetes.io/tls",
            ),
        )
        created_secrets.append(secret_name)
        return secret_name, public_key_pem

    yield create_self_signed_tls_secret

    for secret in created_secrets:
        kube_core_client.delete_namespaced_secret(name=secret, namespace=namespace)


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

    async def wait_mysql_pod_ready():
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

        def is_mysql_ready():
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
    ops_test: pytest_operator.plugin.OpsTest,
    application_name,
    deploy_and_wait_for_mysql_pod,
    wordpress_image,
):
    """Deploy all required charms and kubernetes pods for tests."""
    assert ops_test.model

    async def build_and_deploy_wordpress():
        my_charm = await ops_test.build_charm(".")
        await ops_test.model.deploy(
            my_charm,
            resources={"wordpress-image": wordpress_image},
            application_name=application_name,
            series="jammy",
            num_units=num_units,
        )

    await asyncio.gather(
        build_and_deploy_wordpress(),
        deploy_and_wait_for_mysql_pod(),
        ops_test.model.deploy("charmed-osm-mariadb-k8s", application_name="mariadb"),
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
    await ops_test.model.wait_for_idle()


@pytest.fixture(scope="module", name="test_image")
def image_fixture():
    """A PNG image that can be used in tests."""
    image_response = requests.get(
        "https://s.w.org/style/images/about/WordPress-logotype-wmark.png", timeout=10
    )
    assert image_response.status_code == 200
    return image_response.content


@pytest.fixture(scope="module", name="swift_conn")
def swift_conn_fixture(openstack_environment):
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
        options=dict(
            auth_version="3",
            os_auth_url=openstack_environment["OS_AUTH_URL"],
            os_username=openstack_environment["OS_USERNAME"],
            os_password=openstack_environment["OS_PASSWORD"],
            os_project_name=openstack_environment["OS_PROJECT_NAME"],
            os_project_domain_name=openstack_environment["OS_PROJECT_DOMAIN_ID"],
        )
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
