# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=too-many-locals,unused-argument

"""Integration tests for upgrading WordPress charm."""

import copy
import io
import json
import logging
import re
import subprocess  # nosec
import time
import typing
from pathlib import Path

import ops.model
import PIL
import PIL.Image
import pytest
import requests
from juju.client.client import FullStatus
from kubernetes import kubernetes
from kubernetes.client import CoreV1Api, V1ObjectMeta, V1Pod, V1PodList
from playwright.async_api import async_playwright
from pytest_operator.plugin import OpsTest

from .helpers import get_admin_password, get_unit_ips
from .wordpress_client_for_test import WordpressClient

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


def kubernetes_exec(kube_client: CoreV1Api, namespace: str, pod: str, cmd: list[str]):
    """Execute a command in WordPress pod.

    Args:
        kube_client: Kubernetes API client.
        namespace: Kubernetes namespace to look for WordPress pod.
        pod: name of WordPress pod.
        cmd: Command to execute on podspec version of WordPress pod.
    """
    logger.info("exec %s on %s", cmd, pod)
    resp = kubernetes.stream.stream(
        kube_client.connect_get_namespaced_pod_exec,
        name=pod,
        namespace=namespace,
        container="wordpress",
        command=cmd,
        stderr=True,
        stdin=False,
        stdout=True,
        tty=False,
    )
    logger.info("Response: %s", resp)


def wp_cli_exec(kube_client: CoreV1Api, namespace: str, pod: str, cmd: list[str]):
    """Execute WordPress cli command in podspec version WordPress pod.

    Args:
        kube_client: Kubernetes API client.
        namespace: Kubernetes namespace to look for WordPress pod.
        pod: name of WordPress pod.
        cmd: WordPress cli command to execute.
    """
    kubernetes_exec(kube_client, namespace, pod, cmd + ["--allow-root", "--path=/var/www/html"])


def get_wordpress_podspec_pod(
    kube_client: CoreV1Api, namespace: str, application_name: str
) -> str:
    """Get name of podspec version of WordPress.

    Args:
        kube_client: Kubernetes API client.
        namespace: Kubernetes namespace to look for WordPress pod.
        application_name: WordPress charm name.

    Returns:
        Name of pod of podspec version of WordPress.
    """
    podlist: V1PodList = kube_client.list_namespaced_pod(
        namespace=namespace, label_selector=f"app.kubernetes.io/name={application_name}"
    )
    assert podlist.items
    pod: V1Pod = podlist.items[0]
    assert pod.metadata
    meta: V1ObjectMeta = pod.metadata
    assert meta.name
    return meta.name


def check_images(html: str) -> None:
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
        assert image_response.status_code == 200, f"access image {url} should return status 200"
        try:
            PIL.Image.open(
                io.BytesIO(image_response.content),
                formats=(url.split(".")[-1].upper().replace("JPG", "JPEG"),),
            )
        except PIL.UnidentifiedImageError as exc:
            raise AssertionError(f"access image {url} should return a valid image file") from exc


def get_upgrade_charm_config(
    ops_test: OpsTest, swift_config: dict[str, str], kube_core_client: CoreV1Api
):
    """Create a function that generates charm config for upgrading tests.

    Args:
        ops_test: utility class for testing Operator Charms.
        swift_config: configuration parameters for WordPress swift plugin.
        kube_core_client: kubernetes API client.

    Returns:
        Configuration for upgraded sidecar charm.
    """
    swift_url = swift_config["swift-url"]
    swift_config = copy.copy(swift_config)
    swift_config["url"] = f"{swift_url}/{swift_config['bucket']}/wp-content/uploads/"
    del swift_config["swift-url"]
    swift_config["prefix"] = swift_config["object-prefix"]
    del swift_config["object-prefix"]

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


async def create_example_blog(
    namespace: str,
    admin_password: str,
    unit_ips: tuple[str, ...],
    kube_core_client: CoreV1Api,
    swift_config: dict[str, str],
    application_name: str,
):
    """Create WordPress blogpost containing content with images for testing migration.

    Args:
        namespace: kubernetes namespace in which the WordPress k8s charm was deployed to.
        admin_password: credential required to post as WordPress admin.
        unit_ips: WordPress unit IPs.
        kube_core_client: kubernetes API client.
        swift_config: swift config.
        application_name: WordPress charm name.
    """
    wordpress_pod = get_wordpress_podspec_pod(
        kube_client=kube_core_client, namespace=namespace, application_name=application_name
    )
    kubernetes_exec(
        kube_client=kube_core_client,
        namespace=namespace,
        pod=wordpress_pod,
        cmd=[
            "curl",
            "-sSL",
            "https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar",
            "-o",
            "/usr/local/bin/wp",
        ],
    )
    kubernetes_exec(
        kube_client=kube_core_client,
        namespace=namespace,
        pod=wordpress_pod,
        cmd=["chmod", "+x", "/usr/local/bin/wp"],
    )
    wp_cli_exec(
        kube_client=kube_core_client,
        namespace=namespace,
        pod=wordpress_pod,
        cmd=["wp", "plugin", "activate", "openstack-objectstorage-k8s"],
    )
    wp_cli_exec(
        kube_client=kube_core_client,
        namespace=namespace,
        pod=wordpress_pod,
        cmd=[
            "wp",
            "option",
            "update",
            "object_storage",
            json.dumps(swift_config),
            "--format=json",
        ],
    )
    unit_ip = unit_ips[0]
    client = WordpressClient(
        host=unit_ip,
        username="admin",
        password=admin_password,
        is_admin=True,
    )

    with open("tests/integration/files/canonical_aubergine_hex.jpg", "rb") as test_file:
        test_image = test_file.read()
        media_id = client.upload_media(filename="canonical.jpg", content=test_image)["id"]
    post = client.create_post(title=POST_TITLE, content=POST_CONTENT, featured_media=media_id)
    client.create_comment(post_id=post["id"], post_link=post["link"], content=POST_COMMENT)


async def upgrade_wordpress(
    ops_test: OpsTest,
    application_name: str,
    num_units: int,
    wordpress_image: str,
    charm_path: Path,
    charm_config: dict[str, str],
) -> None:
    """Upgrade podspec version of WordPress charm to newer sidecar version.

    Args:
        ops_test: utility class instance for testing operator charms.
        application_name: WordPress charm name.
        num_units: number of units to deploy new WordPress charm.
        wordpress_image: OCI image name.
        charm_path: Path to charm packed by charmcraft.
        charm_config: migrated configuration from old podspec charm to new sidecar charm.
    """
    assert ops_test.model
    await ops_test.model.remove_application(application_name)

    def wordpress_removed() -> bool:
        """Check if WordPress charm was fully removed.

        Returns:
            True if WordPress is removed, False otherwise.
        """
        assert ops_test.model_name  # to let mypy know it's not None
        status = subprocess.check_output(  # nosec
            ["juju", "status", "-m", ops_test.model_name, "--format", "json"]
        )
        return application_name not in json.loads(status)["applications"]

    await ops_test.model.block_until(wordpress_removed, wait_period=5, timeout=600)
    await ops_test.model.deploy(
        charm_path,
        resources={"wordpress-image": wordpress_image},
        application_name=application_name,
        series="jammy",
        num_units=num_units,
        config=charm_config,
    )
    await ops_test.model.wait_for_idle(status=ops.model.ActiveStatus.name)  # type: ignore


@pytest.mark.parametrize("num_units", (1, 3))
async def test_wordpress_upgrade(
    ops_test: OpsTest,
    kube_core_client: CoreV1Api,
    swift_config: dict[str, str],
    screenshot_dir: Path,
    application_name: str,
    wordpress_image: str,
    charm_path: Path,
    num_units: int,
):
    """
    arrange: given an old WordPress podspec charm with content.
    act: when WordPress is upgraded to a new WordPress sidecar charm.
    assert: the website should have the same content as the old one.
    """
    # Deploy Old Version
    assert ops_test.model
    app = await ops_test.model.deploy(
        "wordpress-k8s",
        resources={"wordpress-image": "wordpresscharmers/wordpress:v5.9.4-20.04_edge"},
        application_name=application_name,
        num_units=num_units,
    )
    admin_password = await get_admin_password(app=app)
    status: FullStatus = await ops_test.model.get_status()
    unit_ips = get_unit_ips(status=status, app=app)

    # Create Post
    await create_example_blog(
        namespace=typing.cast(str, ops_test.model_name),
        admin_password=admin_password,
        unit_ips=unit_ips,
        kube_core_client=kube_core_client,
        swift_config=swift_config,
        application_name=application_name,
    )
    for idx, unit_ip in enumerate(unit_ips):
        await screenshot(f"http://{unit_ip}", screenshot_dir / f"wordpress-before-{idx}.png")

    # Upgrade
    config = get_upgrade_charm_config(
        ops_test=ops_test, swift_config=swift_config, kube_core_client=kube_core_client
    )
    await upgrade_wordpress(
        ops_test=ops_test,
        application_name=application_name,
        num_units=num_units,
        wordpress_image=wordpress_image,
        charm_path=charm_path,
        charm_config=config,
    )

    # Compare and check upgraded WordPress content
    for idx, unit_ip in enumerate(unit_ips):
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
