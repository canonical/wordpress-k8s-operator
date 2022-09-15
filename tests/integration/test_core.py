import asyncio
import secrets

from wordpress_client import WordpressClient

import pytest
import ops.model
import pytest_operator.plugin


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_build_and_deploy(
        ops_test: pytest_operator.plugin.OpsTest,
        get_unit_status_list,
        get_unit_status_msg_list
):
    """
    arrange: no pre-condition
    act: build charm using charmcraft and deploy charm to test juju model
    assert: building and deploying should success and status should be "blocked" since the
    database info hasn't been provided yet.
    """
    my_charm = await ops_test.build_charm(".")
    await ops_test.model.deploy(
        my_charm,
        resources={"wordpress-image": "localhost:32000/wordpress:test"},
        application_name="wordpress",
    )
    await ops_test.model.wait_for_idle()

    status_list_msg_list = await asyncio.gather(get_unit_status_list(), get_unit_status_msg_list())
    for status, msg in zip(*status_list_msg_list):
        assert (
                status == ops.model.BlockedStatus.name
        ), "status should be 'blocked' since the default database info is empty"

        assert (
                "Waiting for db" in msg
        ), "status message should contain the reason why it's blocked"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
@pytest.mark.parametrize("app_config", [{
    "db_host": "test_db_host",
    "db_name": "test_db_name",
    "db_user": "test_db_user",
    "db_password": "test_db_password"
}], indirect=True, scope="function")
async def test_incorrect_db_config(
        ops_test: pytest_operator.plugin.OpsTest,
        app_config: dict,
        get_unit_status_list,
        get_unit_status_msg_list,
):
    """
    arrange: after WordPress charm has been deployed
    act: provide incorrect database info via config
    assert: charm should be blocked by WordPress installation errors, instead of lacking
    of database connection info
    """
    # Database configuration can retry for up to 30 seconds before giving up and showing an error.
    # Default wait_for_idle 15 seconds in ``app_config`` fixture is too short for incorrect
    # db config.
    await ops_test.model.wait_for_idle(idle_period=30)

    status_list_msg_list = await asyncio.gather(get_unit_status_list(), get_unit_status_msg_list())
    for status, msg in zip(*status_list_msg_list):
        assert (
                status == ops.model.BlockedStatus.name
        ), "unit status should be blocked"
        assert (
                "MySQL error" in msg and
                ("2003" in msg or "2005" in msg)
        ), "unit status message should show detailed installation failure"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_mysql_relation(
        ops_test: pytest_operator.plugin.OpsTest,
        get_app_status,
        application_name
):
    """
    arrange: after WordPress charm has been deployed
    act: deploy a mariadb charm and add a relation between WordPress and mariadb
    assert: WordPress should be active
    """
    await ops_test.model.deploy("charmed-osm-mariadb-k8s", application_name="mariadb")
    await ops_test.model.add_relation("wordpress", "mariadb:mysql")
    await ops_test.model.wait_for_idle()

    assert (
            await get_app_status("wordpress") == ops.model.ActiveStatus.name
    ), (
        "application status should be active once correct database connection info "
        "being provided via relation"
    )


@pytest.mark.asyncio
async def test_get_initial_password_action(
        ops_test: pytest_operator.plugin.OpsTest,
        application_name
):
    """
    arrange: after WordPress charm has been deployed
    act: run get-initial-password action
    assert: get-initial-password action should return the same default admin password on every unit
    """
    default_admin_password_from_all_units = set()
    for unit in ops_test.model.applications[application_name].units:
        action = await unit.run_action("get-initial-password")
        await action.wait()
        default_admin_password = action.results["password"]
        assert (
                len(default_admin_password) > 8
        ), "get-initial-password action should return the default password"
        default_admin_password_from_all_units.add(default_admin_password)

    assert (
            len(default_admin_password_from_all_units) == 1
    ), "get-initial-password action should return the same default admin password on every unit"


@pytest.mark.asyncio
async def test_wordpress_functionality(
        ops_test: pytest_operator.plugin.OpsTest,
        application_name,
        default_admin_password
):
    """
    arrange: after WordPress charm has been deployed and db relation established
    act: test WordPress basic functionality (login, post, comment)
    assert: WordPress works normally as a blog site
    """
    units = (await ops_test.model.get_status()).applications[application_name].units.values()
    for unit in units:
        unit_ip = unit.address
        wp_client = WordpressClient(
            host=unit_ip,
            username="admin",
            password=default_admin_password,
            is_admin=True
        )
        post_title = secrets.token_hex(16)
        post_content = secrets.token_hex(16)
        post = wp_client.create_post(
            title=post_title,
            content=post_content,
        )
        homepage = wp_client.get_homepage()
        assert (
                post_title in homepage and post_content in homepage
        ), "admin user should be able to create a new post"
        comment = secrets.token_hex(16)
        post_link = post["link"]
        wp_client.create_comment(
            post_id=post["id"],
            post_link=post_link,
            content=comment,
        )
        assert (
                comment in wp_client.get_post(post_link)
        ), "admin user should be able to create a comment"
