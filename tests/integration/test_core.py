# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for WordPress charm core functionality."""

import io
import secrets
import urllib.parse

import PIL.Image
import pytest
import requests

from charm import WordpressCharm
from tests.integration.helper import WordpressApp, WordpressClient


@pytest.mark.usefixtures("prepare_mysql")
@pytest.mark.abort_on_fail
async def test_wordpress_up(wordpress: WordpressApp):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: test wordpress server is up.
    assert: wordpress service is up.
    """
    await wordpress.model.wait_for_idle(status="active")
    for unit_ip in await wordpress.get_unit_ips():
        assert requests.get(f"http://{unit_ip}", timeout=10).status_code == 200


@pytest.mark.usefixtures("prepare_mysql", "prepare_swift")
async def test_wordpress_functionality(wordpress: WordpressApp):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: test WordPress basic functionality (login, post, comment).
    assert: WordPress works normally as a blog site.
    """
    for unit_ip in await wordpress.get_unit_ips():
        WordpressClient.run_wordpress_functionality_test(
            host=unit_ip,
            admin_username="admin",
            admin_password=await wordpress.get_default_admin_password(),
        )


@pytest.mark.usefixtures("prepare_mysql", "prepare_swift")
async def test_openstack_object_storage_plugin(
    wordpress: WordpressApp,
    swift_conn,
):
    """
    arrange: after charm deployed, db relation established and openstack swift server ready.
    act: update charm configuration for openstack object storage plugin.
    assert: openstack object storage plugin should be installed after the config update and
        WordPress openstack swift object storage integration should be set up properly.
        After openstack swift plugin activated, an image file uploaded to one unit through
        WordPress media uploader should be accessible from all units.
    """
    container = await wordpress.get_swift_bucket()
    for idx, unit_ip in enumerate(await wordpress.get_unit_ips()):
        image = PIL.Image.new("RGB", (500, 500), color=(idx, 0, 0))
        nonce = secrets.token_hex(8)
        filename = f"{nonce}.{unit_ip}.{idx}.jpg"
        image_buf = io.BytesIO()
        image.save(image_buf, format="jpeg")
        image = image_buf.getvalue()
        wordpress_client = WordpressClient(
            host=unit_ip,
            username="admin",
            password=await wordpress.get_default_admin_password(),
            is_admin=True,
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
        for host in await wordpress.get_unit_ips():
            url_components = list(urllib.parse.urlsplit(source_url))
            url_components[1] = host
            url = urllib.parse.urlunsplit(url_components)
            assert (
                requests.get(url, timeout=10).content == image
            ), "image downloaded from WordPress should match the image uploaded"


@pytest.mark.usefixtures("prepare_mysql", "prepare_swift")
async def test_default_wordpress_themes_and_plugins(wordpress: WordpressApp):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: test default installed themes and plugins.
    assert: default plugins and themes should match default themes and plugins defined in charm.py.
    """
    for unit_ip in await wordpress.get_unit_ips():
        wordpress_client = WordpressClient(
            host=unit_ip,
            username="admin",
            password=await wordpress.get_default_admin_password(),
            is_admin=True,
        )
        assert set(wordpress_client.list_themes()) == set(
            WordpressCharm._WORDPRESS_DEFAULT_THEMES
        ), "themes installed on WordPress should match default themes defined in charm.py"
        assert set(wordpress_client.list_plugins()) == set(
            WordpressCharm._WORDPRESS_DEFAULT_PLUGINS
        ), "plugins installed on WordPress should match default plugins defined in charm.py"
