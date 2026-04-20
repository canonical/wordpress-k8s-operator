# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for WordPress charm external service integration."""

import os
import secrets

import pytest

from tests.integration.helper import WordpressApp, WordpressClient


@pytest.mark.requires_secret
@pytest.mark.usefixtures("prepare_mysql", "prepare_swift")
async def test_akismet_plugin(
    wordpress: WordpressApp,
):
    """
    arrange: after WordPress charm has been deployed, db relation established.
    act: update charm configuration for Akismet plugin.
    assert: Akismet plugin should be activated and spam detection function should be working.
    """
    akismet_api_key = os.environ.get("TEST_AKISMET_API_KEY")
    if not akismet_api_key:
        raise ValueError("TEST_AKISMET_API_KEY env is required for running this test")

    await wordpress.set_config({"wp_plugin_akismet_key": akismet_api_key})
    await wordpress.wait_for_wordpress_idle(status="active")

    for wordpress_client in await wordpress.client_for_units():
        post = wordpress_client.create_post(secrets.token_hex(8), secrets.token_hex(8))
        wordpress_client.create_comment(
            post_id=post["id"], post_link=post["link"], content="akismet-guaranteed-spam"
        )
        wordpress_client.create_comment(
            post_id=post["id"], post_link=post["link"], content="test comment"
        )
        assert len(wordpress_client.list_comments(status="spam", post_id=post["id"])) == 1, (
            "Akismet plugin should move the triggered spam comment to the spam section"
        )
        assert len(wordpress_client.list_comments(post_id=post["id"])) == 1, (
            "Akismet plugin should keep the normal comment"
        )


@pytest.mark.requires_secret
@pytest.mark.usefixtures("prepare_mysql")
async def test_openid_plugin(
    wordpress: WordpressApp,
):
    """
    arrange: after WordPress charm has been deployed, db relation established.
    act: update charm configuration for OpenID plugin.
    assert: A WordPress user should be created with correct roles according to the config.
    """
    openid_username = os.environ.get("TEST_OPENID_USERNAME")
    if not openid_username:
        raise ValueError("TEST_OPENID_USERNAME env is required for running this test")
    openid_password = os.environ.get("TEST_OPENID_PASSWORD")
    if not openid_password:
        raise ValueError("TEST_OPENID_PASSWORD env is required for running this test")
    launchpad_team = os.environ.get("TEST_LAUNCHPAD_TEAM")
    if not launchpad_team:
        raise ValueError("TEST_LAUNCHPAD_TEAM is required for running this test")
    await wordpress.set_config({"wp_plugin_openid_team_map": f"{launchpad_team}=administrator"})
    await wordpress.wait_for_wordpress_idle(status="active")

    for idx, unit_ip in enumerate(await wordpress.get_unit_ips()):
        # wordpress-teams-integration has a bug causing desired roles not to be assigned to
        # the user when first-time login. Login twice by creating the WordPressClient client twice
        # for the very first time.
        for attempt in range(2 if idx == 0 else 1):
            try:
                wordpress_client = WordpressClient(
                    host=unit_ip,
                    username=openid_username,
                    password=openid_password,
                    is_admin=True,
                    use_launchpad_login=True,
                )
            except AssertionError:
                if attempt == 0:
                    continue
                raise
        assert "administrator" in wordpress_client.list_roles(), (
            "An launchpad OpenID account should be associated with the WordPress admin user"
        )
