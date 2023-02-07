# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=protected-access,too-many-locals

"""Integration tests for WordPress charm."""

import asyncio
import io
import json
import secrets
import socket
import typing
import unittest.mock
import urllib.parse
from functools import partial

import ops.model
import PIL.Image
import pytest
import requests
import swiftclient
from juju.application import Application
from juju.client._definitions import FullStatus
from juju.unit import Unit
from kubernetes.client import CoreV1Api, NetworkingV1Api, V1PodStatus
from kubernetes.config import load_kube_config
from pytest_operator.plugin import OpsTest

from charm import WordpressCharm

from .helpers import (
    assert_active_status,
    deploy_mysql_pod,
    get_admin_password,
    get_mysql_pod,
    get_unit_ips,
    is_mysql_ready,
)
from .types_ import DatabaseConfig
from .wordpress_client_for_test import WordpressClient


@pytest.mark.abort_on_fail
@pytest.mark.parametrize("num_units", (1, 3))
async def test_mysql_relation(
    ops_test: OpsTest,
    deploy_app_num_units: typing.Callable[[int, str], typing.Awaitable[Application]],
    num_units: int,
    nginx: Application,
):
    """
    arrange: A WordPress charm and it's relations except database.
    act: maria-db charm is related
    assert: WordPress charm becomes active and WordPress responds correctly.
    """
    assert ops_test.model
    app_name = "wordpress-relation"
    db_app_name = "mariadb-relation"
    app = await deploy_app_num_units(num_units, app_name)
    await ops_test.model.deploy("charmed-osm-mariadb-k8s", application_name=db_app_name)
    await ops_test.model.add_relation(app.name, nginx.name)

    await ops_test.model.add_relation(app.name, f"{db_app_name}:mysql")
    await ops_test.model.wait_for_idle(status="active")

    status: FullStatus = await ops_test.model.get_status()
    assert_active_status(status=status, app=app)
    admin_password = await get_admin_password(app=app)
    for unit_ip in get_unit_ips(status, app):
        WordpressClient.run_wordpress_functionality_test(
            host=unit_ip, admin_username="admin", admin_password=admin_password
        )
    # cleanup
    # force is used since juju's cleanup actions are quite flaky and sometimes hangs.
    await asyncio.gather(
        ops_test.model.remove_application(app_name, force=True, block_until_done=True),
        ops_test.model.remove_application(db_app_name, force=True, block_until_done=True),
    )


@pytest.mark.abort_on_fail
@pytest.mark.parametrize("num_units", (1, 3))
async def test_mysql_config(
    ops_test: OpsTest,
    deploy_app_num_units: typing.Callable[[int, str], typing.Awaitable[Application]],
    num_units: int,
    kube_core_client: CoreV1Api,
    pod_db_config: DatabaseConfig,
    nginx: Application,
):
    """
    arrange: after WordPress charm has been deployed, and a mysql pod is deployed in kubernetes.
    act: config the WordPress charm with the database configuration from a mysql pod.
    assert: WordPress should be active.
    """
    assert ops_test.model
    app_name = "wordpress-config"
    app_namespace = typing.cast(str, ops_test.model_name)
    app = await deploy_app_num_units(num_units, app_name)
    await ops_test.model.add_relation(app.name, nginx.name)
    deploy_mysql_pod(
        kube_client=kube_core_client, db_config=pod_db_config, namespace=app_namespace
    )
    mysql_ready = partial(is_mysql_ready, kube_client=kube_core_client, namespace=app_namespace)
    await ops_test.model.block_until(mysql_ready, timeout=300, wait_period=3)

    pod = get_mysql_pod(kube_client=kube_core_client, namespace=app_namespace)
    pod_status = typing.cast(V1PodStatus, pod.status)
    await app.set_config(
        {
            "db_host": pod_status.pod_ip,
            "db_name": pod_db_config.name,
            "db_user": pod_db_config.user,
            "db_password": pod_db_config.password,
        }
    )
    await ops_test.model.wait_for_idle(apps=[app_name])

    status: FullStatus = await ops_test.model.get_status()
    assert_active_status(status=status, app=app)
    admin_password = await get_admin_password(app=app)
    for unit_ip in get_unit_ips(status, app):
        WordpressClient.run_wordpress_functionality_test(
            host=unit_ip, admin_username="admin", admin_password=admin_password
        )
    # cleanup
    # force is used since juju's cleanup actions are quite flaky and sometimes hangs.
    await asyncio.gather(
        ops_test.model.remove_application(app_name, force=True, block_until_done=True),
    )
    kube_core_client.delete_namespaced_pod(name="mysql", namespace=ops_test.model_name)


@pytest.mark.asyncio
async def test_openstack_object_storage_plugin(
    ops_test: OpsTest,
    app: Application,
    swift_conn: swiftclient.Connection,
    swift_config: dict[str, str],
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
    await app.set_config({"wp_plugin_openstack-objectstorage_config": json.dumps(swift_config)})
    # mypy has trouble to inferred types for variables that are initialized in subclasses.
    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore

    container = swift_config["bucket"]
    status: FullStatus = await ops_test.model.get_status()
    admin_password = await get_admin_password(app=app)
    unit_ips = get_unit_ips(status=status, app=app)
    for idx, unit_ip in enumerate(unit_ips):
        image = PIL.Image.new("RGB", (500, 500), color=(idx, 0, 0))
        nonce = secrets.token_hex(8)
        filename = f"{nonce}.{unit_ip}.{idx}.jpg"
        image_buf = io.BytesIO()
        image.save(image_buf, format="jpeg")
        image = image_buf.getvalue()
        wordpress_client = WordpressClient(
            host=unit_ip, username="admin", password=admin_password, is_admin=True
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
        for host in unit_ips:
            url_components = list(urllib.parse.urlsplit(source_url))
            url_components[1] = host
            url = urllib.parse.urlunsplit(url_components)
            assert (
                requests.get(url, timeout=10).content == image
            ), "image downloaded from WordPress should match the image uploaded"


@pytest.mark.asyncio
async def test_default_wordpress_themes_and_plugins(ops_test: OpsTest, app: Application):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: test default installed themes and plugins.
    assert: default plugins and themes should match default themes and plugins defined in charm.py.
    """
    assert ops_test.model
    status: FullStatus = await ops_test.model.get_status()
    unit_ips = get_unit_ips(status=status, app=app)
    admin_password = await get_admin_password(app=app)
    for unit_ip in unit_ips:
        wordpress_client = WordpressClient(
            host=unit_ip, username="admin", password=admin_password, is_admin=True
        )
        assert set(wordpress_client.list_themes()) == set(
            WordpressCharm._WORDPRESS_DEFAULT_THEMES
        ), "themes installed on WordPress should match default themes defined in charm.py"
        assert set(wordpress_client.list_plugins()) == set(
            WordpressCharm._WORDPRESS_DEFAULT_PLUGINS
        ), "plugins installed on WordPress should match default plugins defined in charm.py"


@pytest.mark.asyncio
async def test_wordpress_default_themes(ops_test: OpsTest, app: Application):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: check installed WordPress themes.
    assert: all default themes should be installed.
    """
    assert ops_test.model
    status: FullStatus = await ops_test.model.get_status()
    unit_ips = get_unit_ips(status=status, app=app)
    admin_password = await get_admin_password(app=app)
    for unit_ip in unit_ips:
        wordpress_client = WordpressClient(
            host=unit_ip, username="admin", password=admin_password, is_admin=True
        )
        assert set(WordpressCharm._WORDPRESS_DEFAULT_THEMES) == set(
            wordpress_client.list_themes()
        ), "default themes installed should match default themes defined in WordpressCharm"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_wordpress_install_uninstall_themes(
    ops_test: OpsTest,
    app: Application,
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
        await app.set_config({"themes": ",".join(themes)})
        await ops_test.model.wait_for_idle()

        status: FullStatus = await ops_test.model.get_status()
        unit_ips = get_unit_ips(status=status, app=app)
        admin_password = await get_admin_password(app=app)
        for unit_ip in unit_ips:
            wordpress_client = WordpressClient(
                host=unit_ip, username="admin", password=admin_password, is_admin=True
            )
            expected_themes = themes
            expected_themes.update(WordpressCharm._WORDPRESS_DEFAULT_THEMES)
            assert expected_themes == set(
                wordpress_client.list_themes()
            ), f"theme installed {themes} should match themes setting in config"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_wordpress_theme_installation_error(ops_test: OpsTest, app: Application):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: install a nonexistent theme.
    assert: charm should switch to blocked state and the reason should be included in the status
        message.
    """
    assert ops_test.model
    invalid_theme = "invalid-theme-sgkeahrgalejr"
    await app.set_config({"themes": invalid_theme})
    await ops_test.model.wait_for_idle()

    for unit in app.units:
        assert (
            # mypy has trouble to inferred types for variables that are initialized in subclasses.
            unit.workload_status
            == ops.model.BlockedStatus.name  # type: ignore
        ), "status should be 'blocked' since the theme in themes config does not exist"

        assert (
            invalid_theme in unit.workload_status_message
        ), "status message should contain the reason why it's blocked"

    await app.set_config({"themes": ""})
    await ops_test.model.wait_for_idle()
    for unit in app.units:
        assert (
            # mypy has trouble to inferred types for variables that are initialized in subclasses.
            unit.workload_status
            == ops.model.ActiveStatus.name  # type: ignore
        ), "status should back to active after invalid theme removed from config"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_wordpress_install_uninstall_plugins(
    ops_test: OpsTest,
    app: Application,
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
        await app.set_config({"plugins": ",".join(plugins)})
        await ops_test.model.wait_for_idle()

        status: FullStatus = await ops_test.model.get_status()
        admin_password = await get_admin_password(app=app)
        for unit_ip in get_unit_ips(status=status, app=app):
            wordpress_client = WordpressClient(
                host=unit_ip, username="admin", password=admin_password, is_admin=True
            )
            expected_plugins = plugins
            expected_plugins.update(WordpressCharm._WORDPRESS_DEFAULT_PLUGINS)
            assert expected_plugins == set(
                wordpress_client.list_plugins()
            ), f"plugin installed {plugins} should match plugins setting in config"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_wordpress_plugin_installation_error(ops_test: OpsTest, app: Application):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: install a nonexistent plugin.
    assert: charm should switch to blocked state and the reason should be included in the status
        message.
    """
    assert ops_test.model
    invalid_plugin = "invalid-plugin-sgkeahrgalejr"
    await app.set_config({"plugins": invalid_plugin})
    await ops_test.model.wait_for_idle()

    for unit in typing.cast(list[Unit], app.units):
        assert (
            # mypy has trouble to inferred types for variables that are initialized in subclasses.
            unit.workload_status
            == ops.model.BlockedStatus.name  # type: ignore
        ), "status should be 'blocked' since the plugin in plugins config does not exist"

        assert (
            invalid_plugin in unit.workload_status_message
        ), "status message should contain the reason why it's blocked"

    await app.set_config({"plugins": ""})
    await ops_test.model.wait_for_idle()

    for unit in app.units:
        assert (
            # mypy has trouble to inferred types for variables that are initialized in subclasses.
            unit.workload_status
            == ops.model.ActiveStatus.name  # type: ignore
        ), "status should back to active after invalid plugin removed from config"


@pytest.mark.asyncio
async def test_ingress(ops_test: OpsTest, app: Application):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: deploy the nginx-ingress-integrator charm and create the relation between ingress charm
        and WordPress charm.
    assert: A Kubernetes ingress should be created and the ingress should accept HTTPS connections.
    """

    def gen_patch_getaddrinfo(host: str, resolve_to: str):
        """Generate patched getaddrinfo function.

        This function is used to generate a patched getaddrinfo function that will resolve to the
        resolve_to address without having to actually register a host.

        Args:
            host: intended hostname of a given application.
            resolve_to: destination address for host to resolve to.

        Returns:
            A patching function for getaddrinfo.
        """
        original_getaddrinfo = socket.getaddrinfo

        def patched_getaddrinfo(*args):
            """Patch getaddrinfo to point to desired ip address.

            Args:
                args: original arguments to getaddrinfo when creating network connection.

            Returns:
                Patched getaddrinfo function.
            """
            if args[0] == host:
                return original_getaddrinfo(resolve_to, *args[1:])
            return original_getaddrinfo(*args)

        return patched_getaddrinfo

    response = requests.get("http://127.0.0.1", headers={"Host": app.name}, timeout=5)
    assert (
        response.status_code == 200 and "wordpress" in response.text.lower()
    ), "Ingress should accept requests to WordPress and return correct contents"

    new_hostname = "wordpress.test"
    await app.set_config({"blog_hostname": new_hostname})
    # mypy has trouble to inferred types for variables that are initialized in subclasses.
    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore
    with unittest.mock.patch.multiple(
        socket, getaddrinfo=gen_patch_getaddrinfo(new_hostname, "127.0.0.1")
    ):
        response = requests.get(f"https://{new_hostname}", timeout=5, verify=False)  # nosec
        assert (
            response.status_code == 200 and "wordpress" in response.text.lower()
        ), "Ingress should update the server name indication based routing after blog_hostname updated"


@pytest.mark.asyncio
async def test_ingress_modsecurity(
    ops_test: OpsTest,
    app: Application,
    kube_config: str,
):
    """
    arrange: WordPress charm is running and Nginx ingress integrator deployed and related to it.
    act: update the use_nginx_ingress_modsec WordPress charm config.
    assert: A Kubernetes ingress modsecurity should be enabled and proper rules should be set up
        for WordPress.
    """
    assert ops_test.model
    await app.set_config({"use_nginx_ingress_modsec": "true"})
    # mypy has trouble to inferred types for variables that are initialized in subclasses.
    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore

    load_kube_config(config_file=kube_config)
    kube = NetworkingV1Api()

    def get_ingress_annotation():
        """Get ingress annotations from kubernetes.

        Returns:
            Nginx ingress annotations.
        """
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
    ops_test: OpsTest,
    app: Application,
    akismet_api_key: str,
):
    """
    arrange: after WordPress charm has been deployed, db relation established.
    act: update charm configuration for Akismet plugin.
    assert: Akismet plugin should be activated and spam detection function should be working.
    """
    assert ops_test.model
    # mypy has trouble to inferred types for variables that are initialized in subclasses.
    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore

    await app.set_config({"wp_plugin_akismet_key": akismet_api_key})
    await ops_test.model.wait_for_idle()

    status: FullStatus = await ops_test.model.get_status()
    admin_password = await get_admin_password(app=app)
    for unit_ip in get_unit_ips(status=status, app=app):
        wordpress_client = WordpressClient(
            host=unit_ip, username="admin", password=admin_password, is_admin=True
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
@pytest.mark.skip
async def test_openid_plugin(
    ops_test: OpsTest,
    app: Application,
    openid_username: str,
    openid_password: str,
    launchpad_team: str,
):
    """
    arrange: after WordPress charm has been deployed, db relation established.
    act: update charm configuration for OpenID plugin.
    assert: A WordPress user should be created with correct roles according to the config.
    """
    assert ops_test.model
    await app.set_config({"wp_plugin_openid_team_map": f"{launchpad_team}=administrator"})
    await ops_test.model.wait_for_idle()

    status: FullStatus = await ops_test.model.get_status()
    unit_ips = get_unit_ips(status=status, app=app)
    for idx, unit_ip in enumerate(unit_ips):
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
