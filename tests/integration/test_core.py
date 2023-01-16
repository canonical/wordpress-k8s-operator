# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=protected-access,too-many-locals

"""Integration tests for WordPress charm."""

import io
import json
import secrets
import socket
import tempfile
import typing
import unittest.mock
import urllib.parse

import kubernetes
import ops.model
import PIL.Image
import pytest
import pytest_operator.plugin
import requests

from charm import WordpressCharm
from tests.integration.wordpress_client_for_test import WordpressClient


@pytest.mark.usefixtures("build_and_deploy")
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: pytest_operator.plugin.OpsTest, application_name):
    """
    arrange: no pre-condition.
    act: build charm using charmcraft and deploy charm to test juju model.
    assert: building and deploying should success and status should be "blocked" since the
        database info hasn't been provided yet.
    """
    assert ops_test.model
    for unit in ops_test.model.applications[application_name].units:
        assert (
            # mypy has trouble to inferred types for variables that are initialized in subclasses,
            # same for all status name down below.
            unit.workload_status
            == ops.model.BlockedStatus.name  # type: ignore
        ), "status should be 'blocked' since the default database info is empty"

        assert (
            "Waiting for db" in unit.workload_status_message
        ), "status message should contain the reason why it's blocked"


@pytest.mark.abort_on_fail
async def test_mysql_config(
    db_from_config,
    ops_test: pytest_operator.plugin.OpsTest,
    application_name,
    kube_core_client,
    pod_db_database,
    pod_db_user,
    pod_db_password,
):
    """
    arrange: after WordPress charm has been deployed, and a mysql pod is deployed in kubernetes.
    act: config the WordPress charm with the database configuration from a mysql pod.
    assert: WordPress should be active.
    """
    if not db_from_config:
        pytest.skip()
    assert ops_test.model
    application = ops_test.model.applications[application_name]
    await application.set_config(
        {
            "db_host": kube_core_client.read_namespaced_pod(
                name="mysql", namespace=ops_test.model_name
            ).status.pod_ip,
            "db_name": pod_db_database,
            "db_user": pod_db_user,
            "db_password": pod_db_password,
        }
    )
    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore
    app_status = ops_test.model.applications[application_name].status
    assert app_status == ops.model.ActiveStatus.name, (  # type: ignore
        "application status should be active once correct database connection info "
        "being provided via config"
    )


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_mysql_relation(request, ops_test: pytest_operator.plugin.OpsTest, application_name):
    """
    arrange: after WordPress charm has been deployed.
    act: deploy a mariadb charm and add a relation between WordPress and mariadb.
    assert: WordPress should be active.
    """
    if request.config.getoption("--test-db-from-config"):
        pytest.skip()
    assert ops_test.model
    await ops_test.model.add_relation("wordpress", "mariadb:mysql")
    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore
    app_status = ops_test.model.applications[application_name].status
    assert app_status == ops.model.ActiveStatus.name, (  # type: ignore
        "application status should be active once correct database connection info "
        "being provided via relation"
    )


@pytest.mark.asyncio
async def test_openstack_object_storage_plugin(
    ops_test: pytest_operator.plugin.OpsTest,
    application_name,
    default_admin_password,
    unit_ip_list,
    swift_conn,
    swift_config,
):
    """
    arrange: after charm deployed, db relation established and openstack swift server ready.
    act: update charm configuration for openstack object storage plugin.
    assert: openstack object storage plugin should be installed after the config update and
        WordPress openstack swift object storage integration should be set up properly.
        After openstack swift plugin activated, an image file uploaded to one unit through
        WordPress media uploader should be accessible from all units.
    """
    if swift_config is None:
        pytest.skip("no openstack configuration provided, skip openstack swift plugin setup")
    assert ops_test.model
    application = ops_test.model.applications[application_name]
    await application.set_config(
        {"wp_plugin_openstack-objectstorage_config": json.dumps(swift_config)}
    )
    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore

    container = swift_config["bucket"]
    for idx, unit_ip in enumerate(unit_ip_list):
        image = PIL.Image.new("RGB", (500, 500), color=(idx, 0, 0))
        nonce = secrets.token_hex(8)
        filename = f"{nonce}.{unit_ip}.{idx}.jpg"
        image_buf = io.BytesIO()
        image.save(image_buf, format="jpeg")
        image = image_buf.getvalue()
        wordpress_client = WordpressClient(
            host=unit_ip, username="admin", password=default_admin_password, is_admin=True
        )
        image_urls = wordpress_client.upload_media(filename=filename, content=image)["urls"]
        swift_object_list = [
            o["name"] for o in swift_conn.get_container(container, full_listing=True)[1]
        ]
        assert any(
            nonce in f for f in swift_object_list
        ), "media files uploaded should be stored in swift object storage"
        source_url = min(image_urls, key=len)
        for image_url in image_urls:
            assert (
                requests.get(image_url, timeout=10).status_code == 200
            ), "the original image and resized images should be accessible from the WordPress site"
        for host in unit_ip_list:
            url_components = list(urllib.parse.urlsplit(source_url))
            url_components[1] = host
            url = urllib.parse.urlunsplit(url_components)
            assert (
                requests.get(url, timeout=10).content == image
            ), "image downloaded from WordPress should match the image uploaded"


@pytest.mark.asyncio
async def test_default_wordpress_themes_and_plugins(unit_ip_list, default_admin_password):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: test default installed themes and plugins.
    assert: default plugins and themes should match default themes and plugins defined in charm.py.
    """
    for unit_ip in unit_ip_list:
        wordpress_client = WordpressClient(
            host=unit_ip, username="admin", password=default_admin_password, is_admin=True
        )
        assert set(wordpress_client.list_themes()) == set(
            WordpressCharm._WORDPRESS_DEFAULT_THEMES
        ), "themes installed on WordPress should match default themes defined in charm.py"
        assert set(wordpress_client.list_plugins()) == set(
            WordpressCharm._WORDPRESS_DEFAULT_PLUGINS
        ), "plugins installed on WordPress should match default plugins defined in charm.py"


@pytest.mark.asyncio
async def test_wordpress_functionality(unit_ip_list, default_admin_password):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: test WordPress basic functionality (login, post, comment).
    assert: WordPress works normally as a blog site.
    """
    for unit_ip in unit_ip_list:
        WordpressClient.run_wordpress_functionality_test(
            host=unit_ip, admin_username="admin", admin_password=default_admin_password
        )


@pytest.mark.asyncio
async def test_wordpress_default_themes(unit_ip_list, get_theme_list_from_ip):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: check installed WordPress themes.
    assert: all default themes should be installed.
    """
    for unit_ip in unit_ip_list:
        assert set(WordpressCharm._WORDPRESS_DEFAULT_THEMES) == set(
            get_theme_list_from_ip(unit_ip)
        ), "default themes installed should match default themes defined in WordpressCharm"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_wordpress_install_uninstall_themes(
    ops_test: pytest_operator.plugin.OpsTest,
    application_name,
    unit_ip_list,
    get_theme_list_from_ip,
):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: change themes setting in config.
    assert: themes should be installed and uninstalled accordingly.
    """
    assert ops_test.model
    theme_change_list: typing.List[typing.Set[str]] = [
        {"twentyfifteen", "classic"},
        {"tt1-blocks", "twentyfifteen"},
        {"tt1-blocks"},
        {"twentyeleven"},
        set(),
    ]
    for themes in theme_change_list:
        application = ops_test.model.applications[application_name]
        await application.set_config({"themes": ",".join(themes)})
        await ops_test.model.wait_for_idle()

        for unit_ip in unit_ip_list:
            expected_themes = themes
            expected_themes.update(WordpressCharm._WORDPRESS_DEFAULT_THEMES)
            assert expected_themes == set(
                get_theme_list_from_ip(unit_ip)
            ), f"theme installed {themes} should match themes setting in config"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_wordpress_theme_installation_error(
    ops_test: pytest_operator.plugin.OpsTest, application_name
):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: install a nonexistent theme.
    assert: charm should switch to blocked state and the reason should be included in the status
        message.
    """
    assert ops_test.model
    invalid_theme = "invalid-theme-sgkeahrgalejr"
    await ops_test.model.applications[application_name].set_config({"themes": invalid_theme})
    await ops_test.model.wait_for_idle()

    for unit in ops_test.model.applications[application_name].units:
        assert (
            unit.workload_status == ops.model.BlockedStatus.name  # type: ignore
        ), "status should be 'blocked' since the theme in themes config does not exist"

        assert (
            invalid_theme in unit.workload_status_message
        ), "status message should contain the reason why it's blocked"

    await ops_test.model.applications[application_name].set_config({"themes": ""})
    await ops_test.model.wait_for_idle()
    for unit in ops_test.model.applications[application_name].units:
        assert (
            unit.workload_status == ops.model.ActiveStatus.name  # type: ignore
        ), "status should back to active after invalid theme removed from config"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_wordpress_install_uninstall_plugins(
    ops_test: pytest_operator.plugin.OpsTest,
    application_name,
    unit_ip_list,
    get_plugin_list_from_ip,
):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: change plugins setting in config.
    assert: plugins should be installed and uninstalled accordingly.
    """
    assert ops_test.model
    plugin_change_list: typing.List[typing.Set[str]] = [
        {"classic-editor", "classic-widgets"},
        {"classic-editor"},
        {"classic-widgets"},
        set(),
    ]
    for plugins in plugin_change_list:
        application = ops_test.model.applications[application_name]
        await application.set_config({"plugins": ",".join(plugins)})
        await ops_test.model.wait_for_idle()

        for unit_ip in unit_ip_list:
            expected_plugins = plugins
            expected_plugins.update(WordpressCharm._WORDPRESS_DEFAULT_PLUGINS)
            assert expected_plugins == set(
                get_plugin_list_from_ip(unit_ip)
            ), f"plugin installed {plugins} should match plugins setting in config"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_wordpress_plugin_installation_error(
    ops_test: pytest_operator.plugin.OpsTest, application_name
):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: install a nonexistent plugin.
    assert: charm should switch to blocked state and the reason should be included in the status
        message.
    """
    assert ops_test.model
    invalid_plugin = "invalid-plugin-sgkeahrgalejr"
    await ops_test.model.applications[application_name].set_config({"plugins": invalid_plugin})
    await ops_test.model.wait_for_idle()

    for unit in ops_test.model.applications[application_name].units:
        assert (
            unit.workload_status == ops.model.BlockedStatus.name  # type: ignore
        ), "status should be 'blocked' since the plugin in plugins config does not exist"

        assert (
            invalid_plugin in unit.workload_status_message
        ), "status message should contain the reason why it's blocked"

    await ops_test.model.applications[application_name].set_config({"plugins": ""})
    await ops_test.model.wait_for_idle()

    for unit in ops_test.model.applications[application_name].units:
        assert (
            unit.workload_status == ops.model.ActiveStatus.name  # type: ignore
        ), "status should back to active after invalid plugin removed from config"


@pytest.mark.asyncio
async def test_ingress(
    ops_test: pytest_operator.plugin.OpsTest,
    application_name: str,
    create_self_signed_tls_secret,
):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: deploy the nginx-ingress-integrator charm and create the relation between ingress charm
        and wordpress charm. After that, update some ingress related configuration of the
        wordpress charm.
    assert: A Kubernetes ingress should be created and the ingress should accept HTTPS connections
        after configuration tls_secret_name be set.
    """

    def gen_patch_getaddrinfo(host, resolve_to):
        original_getaddrinfo = socket.getaddrinfo

        def patched_getaddrinfo(*args):
            if args[0] == host:
                return original_getaddrinfo(resolve_to, *args[1:])
            return original_getaddrinfo(*args)

        return patched_getaddrinfo

    assert ops_test.model
    await ops_test.model.add_relation(application_name, "ingress:ingress")
    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore

    response = requests.get("http://127.0.0.1", headers={"Host": application_name}, timeout=5)
    assert (
        response.status_code == 200 and "wordpress" in response.text.lower()
    ), "Ingress should accept requests to WordPress and return correct contents"

    tls_secret_name, tls_cert = create_self_signed_tls_secret(application_name)
    application = ops_test.model.applications[application_name]
    await application.set_config({"tls_secret_name": tls_secret_name})
    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore

    with tempfile.NamedTemporaryFile(mode="wb+") as file:
        with unittest.mock.patch.multiple(
            socket, getaddrinfo=gen_patch_getaddrinfo(application_name, "127.0.0.1")
        ):
            file.write(tls_cert)
            file.flush()
            response = requests.get(f"https://{application_name}", verify=file.name, timeout=5)
            assert (
                response.status_code == 200 and "wordpress" in response.text.lower()
            ), "Ingress should accept HTTPS requests after tls_secret_name being set"

    new_hostname = "wordpress.test"
    tls_secret_name, tls_cert = create_self_signed_tls_secret(new_hostname)
    application = ops_test.model.applications[application_name]
    await application.set_config(
        {"tls_secret_name": tls_secret_name, "blog_hostname": new_hostname}
    )
    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore
    with tempfile.NamedTemporaryFile(mode="wb+") as file:
        with unittest.mock.patch.multiple(
            socket, getaddrinfo=gen_patch_getaddrinfo(new_hostname, "127.0.0.1")
        ):
            file.write(tls_cert)
            file.flush()
            response = requests.get(f"https://{new_hostname}", verify=file.name, timeout=5)
            assert (
                response.status_code == 200 and "wordpress" in response.text.lower()
            ), "Ingress should update the server name indication based routing after blog_hostname updated"


@pytest.mark.asyncio
async def test_ingress_modsecurity(
    ops_test: pytest_operator.plugin.OpsTest,
    application_name: str,
    kube_config: str,
):
    """
    arrange: after WordPress charm is up and running and Nginx ingress integrator charm is deployed
        and related to the WordPress charm.
    act: update the use_nginx_ingress_modsec WordPress charm config.
    assert: A Kubernetes ingress modsecurity should be enabled and proper rules should be set up
        for WordPress.
    """
    assert ops_test.model
    application = ops_test.model.applications[application_name]
    await application.set_config({"use_nginx_ingress_modsec": "true"})
    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore

    kubernetes.config.load_kube_config(config_file=kube_config)
    kube = kubernetes.client.NetworkingV1Api()

    def get_ingress_annotation():
        ingress_list = kube.list_namespaced_ingress(namespace=ops_test.model_name).items
        return ingress_list[0].metadata.annotations

    ingress_annotations = get_ingress_annotation()
    assert ingress_annotations["nginx.ingress.kubernetes.io/enable-modsecurity"] == "true"
    assert (
        ingress_annotations["nginx.ingress.kubernetes.io/enable-owasp-modsecurity-crs"] == "true"
    )
    assert (
        'SecAction "id:900130,phase:1,nolog,pass,t:none,setvar:tx.crs_exclusions_wordpress=1"\n'
        in ingress_annotations["nginx.ingress.kubernetes.io/modsecurity-snippet"]
    )


@pytest.mark.requires_secret
@pytest.mark.asyncio
async def test_akismet_plugin(
    ops_test: pytest_operator.plugin.OpsTest,
    application_name,
    default_admin_password,
    unit_ip_list,
    akismet_api_key,
):
    """
    arrange: after WordPress charm has been deployed, db relation established.
    act: update charm configuration for Akismet plugin.
    assert: Akismet plugin should be activated and spam detection function should be working.
    """
    assert ops_test.model
    application = ops_test.model.applications[application_name]
    await application.set_config({"wp_plugin_akismet_key": akismet_api_key})
    await ops_test.model.wait_for_idle()

    for unit_ip in unit_ip_list:
        wordpress_client = WordpressClient(
            host=unit_ip, username="admin", password=default_admin_password, is_admin=True
        )
        post = wordpress_client.create_post(secrets.token_hex(8), secrets.token_hex(8))
        wordpress_client.create_comment(
            post_id=post["id"], post_link=post["link"], content="akismet-guaranteed-spam"
        )
        wordpress_client.create_comment(
            post_id=post["id"], post_link=post["link"], content="test comment"
        )
        assert (
            len(wordpress_client.list_comments(status="spam", post_id=post["id"])) == 1
        ), "Akismet plugin should move the triggered spam comment to the spam section"
        assert (
            len(wordpress_client.list_comments(post_id=post["id"])) == 1
        ), "Akismet plugin should keep the normal comment"


@pytest.mark.requires_secret
@pytest.mark.asyncio
async def test_openid_plugin(
    ops_test: pytest_operator.plugin.OpsTest,
    application_name,
    unit_ip_list,
    openid_username,
    openid_password,
    launchpad_team,
):
    """
    arrange: after WordPress charm has been deployed, db relation established.
    act: update charm configuration for OpenID plugin.
    assert: A WordPress user should be created with correct roles according to the config.
    """
    assert ops_test.model
    application = ops_test.model.applications[application_name]
    await application.set_config({"wp_plugin_openid_team_map": f"{launchpad_team}=administrator"})
    await ops_test.model.wait_for_idle()

    for idx, unit_ip in enumerate(unit_ip_list):
        # wordpress-teams-integration has a bug causing desired roles not to be assigned to
        # the user when first-time login. Login twice by creating the WordPressClient client twice
        # for the very first time.
        for _ in range(2 if idx == 0 else 1):
            wordpress_client = WordpressClient(
                host=unit_ip,
                username=openid_username,
                password=openid_password,
                is_admin=True,
                use_launchpad_login=True,
            )
        assert (
            "administrator" in wordpress_client.list_roles()
        ), "An launchpad OpenID account should be associated with the WordPress admin user"
