# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for WordPress charm COS addon management."""


from typing import List, Set

import pytest

from charm import WordpressCharm
from tests.integration.helper import WordpressApp


@pytest.mark.usefixtures("prepare_mysql", "prepare_swift")
async def test_wordpress_install_uninstall_themes(wordpress: WordpressApp):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: change themes setting in config.
    assert: themes should be installed and uninstalled accordingly.
    """
    theme_change_list: List[Set[str]] = [
        {"twentyfifteen", "classic"},
        {"tt1-blocks", "twentyfifteen"},
        {"tt1-blocks"},
        {"twentyeleven"},
        set(),
    ]
    for themes in theme_change_list:
        await wordpress.set_config({"themes": ",".join(themes)})
        await wordpress.model.wait_for_idle(status="active", apps=[wordpress.name])

        for wordpress_client in await wordpress.client_for_units():
            expected_themes = themes
            expected_themes.update(WordpressCharm._WORDPRESS_DEFAULT_THEMES)
            actual_themes = set(wordpress_client.list_themes())
            assert (
                expected_themes == actual_themes
            ), f"theme installed {themes} should match themes setting in config"


@pytest.mark.usefixtures("prepare_mysql", "prepare_swift")
async def test_wordpress_theme_installation_error(wordpress: WordpressApp):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: install a nonexistent theme.
    assert: charm should switch to blocked state and the reason should be included in the status
        message.
    """
    invalid_theme = "invalid-theme-sgkeahrgalejr"
    await wordpress.set_config({"themes": invalid_theme})
    await wordpress.wait_for_wordpress_idle()

    for unit in wordpress.get_units():
        assert (
            unit.workload_status == "blocked"
        ), "status should be 'blocked' since the theme in themes config does not exist"

        assert (
            invalid_theme in unit.workload_status_message
        ), "status message should contain the reason why it's blocked"

    await wordpress.set_config({"themes": ""})
    await wordpress.wait_for_wordpress_idle(status="active")


@pytest.mark.usefixtures("prepare_mysql", "prepare_swift")
async def test_wordpress_install_uninstall_plugins(wordpress: WordpressApp):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: change plugins setting in config.
    assert: plugins should be installed and uninstalled accordingly.
    """
    plugin_change_list: List[Set[str]] = [
        {"classic-editor", "classic-widgets"},
        {"classic-editor"},
        {"classic-widgets"},
        set(),
    ]
    for plugins in plugin_change_list:
        await wordpress.set_config({"plugins": ",".join(plugins)})
        await wordpress.wait_for_wordpress_idle(status="active")

        for wordpress_client in await wordpress.client_for_units():
            expected_plugins = plugins
            actual_plugins = set(wordpress_client.list_plugins())
            assert (
                expected_plugins == actual_plugins
            ), f"plugin installed {plugins} should match plugins setting in config"


@pytest.mark.usefixtures("prepare_mysql", "prepare_swift")
async def test_wordpress_plugin_installation_error(wordpress: WordpressApp):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: install a nonexistent plugin.
    assert: charm should switch to blocked state and the reason should be included in the status
        message.
    """
    invalid_plugin = "invalid-plugin-sgkeahrgalejr"
    await wordpress.set_config({"plugins": invalid_plugin})
    await wordpress.wait_for_wordpress_idle()

    for unit in wordpress.get_units():
        assert (
            unit.workload_status == "blocked"
        ), "status should be 'blocked' since the plugin in plugins config does not exist"

        assert (
            invalid_plugin in unit.workload_status_message
        ), "status message should contain the reason why it's blocked"

    await wordpress.set_config({"plugins": ""})
    await wordpress.wait_for_wordpress_idle(status="active")
