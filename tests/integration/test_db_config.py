# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration test module for database configuration."""

import pytest

from tests.integration.helper import WordpressApp, WordpressClient


@pytest.mark.usefixtures("prepare_mysql_pod")
async def test_db_config(wordpress: WordpressApp):
    """
    arrange: config wordpress to connect to the non-charmed mysql server.
    act: test the wordpress functionality of the wordpress charm.
    assert: wordpress charm should provide wordpress functionality correctly.
    """
    default_admin_password = await wordpress.get_default_admin_password()
    for unit_ip in await wordpress.get_unit_ips():
        WordpressClient.run_wordpress_functionality_test(
            host=unit_ip,
            admin_username="admin",
            admin_password=default_admin_password,
        )
