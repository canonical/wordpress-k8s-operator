# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=too-many-locals,unused-argument,duplicate-code

"""Integration tests for upgrading WordPress charm."""

import asyncio
import copy
import io
import json
import logging
import re
import time
from pathlib import Path

import juju.application
import ops.model
import PIL.Image
import pytest
import pytest_asyncio
import pytest_operator.plugin
import requests
from playwright.async_api import async_playwright

from tests.integration.wordpress_client_for_test import WordpressClient

logger = logging.getLogger()

POST_CONTENT = """\
WordPress powers more than 39% of the web — a figure that rises every day.
Everything from simple websites, to blogs, to complex portals and enterprise
websites, and even applications, are built with WordPress. WordPress combines
simplicity for users and publishers with under-the-hood complexity for
developers. This makes it flexible while still being easy-to-use."""

POST_CONTENT = POST_CONTENT.replace("\n", " ")

POST_TITLE = "WordPress Post #1"

POST_COMMENT = "I am a comment."


async def screenshot(url: str, path: Path):
    """Create a screenshot of a website.

    Args:
        url: URL of a path to take a screenshot of.
        path: Filepath to save the screenshot to.
    """
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)
        time.sleep(10)
        await page.screenshot(full_page=True, path=path)
        await browser.close()


@pytest.fixture(scope="module", name="gen_upgrade_test_charm_config")
def gen_upgrade_test_charm_config_fixture(ops_test, swift_config, kube_core_client):
    """Create a function that generates charm config for upgrading tests."""
    swift_url = swift_config["swift-url"]
    swift_config = copy.copy(swift_config)
    swift_config["url"] = f"{swift_url}/{swift_config['bucket']}/wp-content/uploads/"
    del swift_config["swift-url"]
    swift_config["prefix"] = swift_config["object-prefix"]
    del swift_config["object-prefix"]

    def _gen_upgrade_test_charm_config():
        """Get WordPress charm config with currently deployed db & swift state.

        Returns:
            Charm config containing currently deployed configurations.
        """
        charm_config = {
            "db_host": kube_core_client.read_namespaced_pod(
                name="mysql", namespace=ops_test.model_name
            ).status.pod_ip,
            "db_name": "wordpress",
            "db_user": "wordpress",
            "db_password": "wordpress-password",
        }
        if swift_config:
            logger.info("deploy with swift: %s", swift_config)
            charm_config["wp_plugin_openstack-objectstorage_config"] = json.dumps(swift_config)
        return charm_config

    return _gen_upgrade_test_charm_config


@pytest_asyncio.fixture(scope="module", name="deploy_old_version")
async def deploy_old_version_fixture(
    num_units,
    ops_test: pytest_operator.plugin.OpsTest,
    application_name,
    deploy_and_wait_for_mysql_pod,
    gen_upgrade_test_charm_config,
):
    """
    arrange: none.
    act: deploy all required charms and kubernetes pods for tests.
    assert: all charms and pods are deployed successfully.
    """
    assert ops_test.model
    await deploy_and_wait_for_mysql_pod()

    async def deploy_wordpress():
        """Deploy WordPress charm to juju."""
        await ops_test.model.deploy(
            "wordpress-k8s",
            application_name=application_name,
            num_units=num_units,
            channel="edge",
            config=gen_upgrade_test_charm_config(),
        )

    await asyncio.gather(
        deploy_wordpress(),
        ops_test.run("playwright", "install", "chromium"),
    )
    await ops_test.model.applications[application_name].set_config(gen_upgrade_test_charm_config())
    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore


@pytest_asyncio.fixture(scope="module", name="create_example_blog")
async def create_example_blog_fixture(
    deploy_old_version,
    get_default_admin_password,
    get_unit_ip_list,
    test_image,
    screenshot_dir,
):
    """
    arrange: all charms and pods are deployed successfully.
    act: enable some plugins and create posts and upload some images to the test WordPress blog.
    assert: all operations finished without error.
    """
    unit_ip_list = await get_unit_ip_list()
    unit_ip = unit_ip_list[0]
    client = WordpressClient(
        host=unit_ip,
        username="admin",
        password=await get_default_admin_password(),
        is_admin=True,
    )
    media_id = client.upload_media(filename="canonical.jpg", content=test_image)["id"]
    post = client.create_post(title=POST_TITLE, content=POST_CONTENT, featured_media=media_id)
    client.create_comment(post_id=post["id"], post_link=post["link"], content=POST_COMMENT)
    for idx, unit_ip in enumerate(unit_ip_list):
        await screenshot(f"http://{unit_ip}", screenshot_dir / f"wordpress-before-{idx}.png")


@pytest_asyncio.fixture(scope="module", name="build_and_upgrade")
async def build_and_upgrade_fixture(
    create_example_blog,
    ops_test: pytest_operator.plugin.OpsTest,
    application_name,
    wordpress_image,
):
    """
    arrange: an old version of the WordPress is deployed.
    act: build WordPress charm from source and upgrade the WordPress charm.
    assert: all operations finished without error.
    """
    assert ops_test.model
    charm = await ops_test.build_charm(".")
    # Most of the times the integration tests will fail due to timeout without the force flag.
    app: juju.application.Application = ops_test.model.applications[application_name]
    await app.refresh(
        path=str(charm),
        resources={
            "apache-prometheus-exporter-image": "bitnami/apache-exporter:0.11.0",
            "wordpress-image": wordpress_image,
        },
    )
    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore


@pytest.mark.usefixtures("build_and_upgrade")
async def test_wordpress_upgrade(get_unit_ip_list, screenshot_dir):
    """
    arrange: the WordPress charm has been upgraded.
    act: browser the WordPress website powered by the new charm.
    assert: the website should have the same content as the old one.
    """

    def check_images(html) -> None:
        """Check image contents of a newly upgraded WordPress.

        Args:
            html: Stringified html contents of a page to check for images.

        Raises:
            AssertionError: if invalid image was found in page.
        """
        image_urls = re.findall('<img[^>]+src="([^"]+)"[^>]*>', html)
        assert image_urls
        for url in image_urls:
            logger.info("check image %s", url)
            image_response = requests.get(url, timeout=10)
            assert (
                image_response.status_code == 200
            ), f"access image {url} should return status 200"
            try:
                PIL.Image.open(
                    io.BytesIO(image_response.content),
                    formats=(url.split(".")[-1].upper().replace("JPG", "JPEG"),),
                )
            except PIL.UnidentifiedImageError as exc:
                raise AssertionError(
                    f"access image {url} should return a valid image file"
                ) from exc

    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore
    unit_ip_list = await get_unit_ip_list()
    for idx, unit_ip in enumerate(unit_ip_list):
        await screenshot(f"http://{unit_ip}", screenshot_dir / f"wordpress-after-{idx}.png")
        # create a side-by-side comparison of the before and after screenshots
        # for now, the comparison image is checked by a human
        after_image = PIL.Image.open(screenshot_dir / f"wordpress-after-{idx}.png")
        before_image = PIL.Image.open(screenshot_dir / f"wordpress-before-{idx}.png")
        comparison_width = before_image.width + after_image.width
        comparison_height = max(before_image.height, after_image.height)
        comparison_image = PIL.Image.new("RGB", (comparison_width, comparison_height))
        comparison_image.paste(before_image, (0, 0))
        comparison_image.paste(after_image, (before_image.width, 0))
        comparison_image.save(screenshot_dir / f"wordpress-comparison-{idx}.png")
        homepage = requests.get(f"http://{unit_ip}", timeout=10).text
        assert POST_TITLE in homepage
        assert POST_CONTENT.split(".", maxsplit=1)[0] in homepage
        check_images(homepage)
        post = requests.get(f"http://{unit_ip}/wordpress-post-1/", timeout=10).text
        assert POST_CONTENT in post
        check_images(post)
        assert POST_COMMENT in post
