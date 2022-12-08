# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for WordPress charm integration tests."""

import asyncio
import base64
import configparser
import datetime
import re
import secrets

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

from tests.integration.wordpress_client_for_test import WordpressClient


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


@pytest.fixture
def openstack_environment(request):
    """Parse the openstack rc style configuration file from the --openstack-rc argument

    Return a dictionary of environment variables and values.
    """
    rc_file = request.config.getoption("--openstack-rc")
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


@pytest.fixture(name="launchpad_team")
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


@pytest_asyncio.fixture(scope="module", name="build_and_deploy")
async def build_and_deploy_fixture(
    request, ops_test: pytest_operator.plugin.OpsTest, application_name, kube_core_client
):
    """Deploy all required charms and kubernetes pods for tests."""
    assert ops_test.model
    num_units = request.config.getoption("--num-units")

    async def build_and_deploy_wordpress():
        my_charm = await ops_test.build_charm(".")
        await ops_test.model.deploy(
            my_charm,
            resources={"wordpress-image": "localhost:32000/wordpress:test"},
            application_name=application_name,
            series="jammy",
            num_units=num_units,
        )

    kube_core_client.create_namespaced_pod(
        namespace=ops_test.model_name,
        body=kubernetes.client.V1Pod(
            metadata=kubernetes.client.V1ObjectMeta(name="mysql", namespace=ops_test.model_name),
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
                        env=[
                            kubernetes.client.V1EnvVar("MYSQL_ROOT_PASSWORD", "root-password"),
                            kubernetes.client.V1EnvVar("MYSQL_DATABASE", "wordpress"),
                            kubernetes.client.V1EnvVar("MYSQL_USER", "wordpress"),
                            kubernetes.client.V1EnvVar("MYSQL_PASSWORD", "wordpress-password"),
                        ],
                    )
                ]
            ),
        ),
    )

    async def wait_mysql_pod_ready():
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

    await asyncio.gather(
        build_and_deploy_wordpress(),
        wait_mysql_pod_ready(),
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
            check=True,
        ),
    )
    await ops_test.model.wait_for_idle()
