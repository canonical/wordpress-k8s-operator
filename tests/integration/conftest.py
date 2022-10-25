import re
import base64
import secrets
import datetime
import configparser

import pytest
import kubernetes
import juju.action
import pytest_asyncio
import juju.application
import cryptography.x509
import pytest_operator.plugin
import cryptography.hazmat.primitives.hashes
import cryptography.hazmat.primitives.serialization
import cryptography.hazmat.primitives.asymmetric.rsa

from wordpress_client import WordpressClient


@pytest_asyncio.fixture(scope="function", name="app_config")
async def fixture_app_config(request, ops_test: pytest_operator.plugin.OpsTest):
    """Change the charm config to specific values and revert that after test"""
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
    return "wordpress"


@pytest_asyncio.fixture(scope="function", name="default_admin_password")
async def fixture_default_admin_password(
    ops_test: pytest_operator.plugin.OpsTest, application_name
):
    application: juju.application = ops_test.model.applications[application_name]
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
    with open(rc_file) as f:
        rc_file = f.read()
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


@pytest.fixture
def openid_username(request):
    """The OpenID username for testing the OpenID plugin"""
    openid_username = request.config.getoption("--openid-username")
    assert (
        openid_username
    ), "OpenID username should not be empty, please include it in the --openid-username parameter"
    return openid_username


@pytest.fixture
def openid_password(request):
    """The OpenID username for testing the OpenID plugin"""
    openid_password = request.config.getoption("--openid-password")
    assert (
        openid_password
    ), "OpenID password should not be empty, please include it in the --openid-password parameter"
    return openid_password


@pytest.fixture
def kube_config(request):
    """The Kubernetes cluster configuration file"""
    openid_password = request.config.getoption("--kube-config")
    assert openid_password, (
        "The Kubernetes config file path should not be empty, "
        "please include it in the --kube-config parameter"
    )
    return openid_password


@pytest.fixture(scope="function", name="create_self_signed_tls_secret")
def create_self_signed_tls_secret_fixture(kube_config, ops_test: pytest_operator.plugin.OpsTest):
    """Create a self-signed TLS certificate as a Kubernetes secret."""
    created_secrets = []
    namespace = ops_test.model.info["name"]
    kubernetes.config.load_kube_config(config_file=kube_config)
    kubernetes_client_v1 = kubernetes.client.CoreV1Api()

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
        kubernetes_client_v1.create_namespaced_secret(
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
        kubernetes_client_v1.delete_namespaced_secret(name=secret, namespace=namespace)
