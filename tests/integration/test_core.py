import pytest
import ops.model
import pytest_operator.plugin

from charm import WordpressCharm
from wordpress_client import WordpressClient


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_build_and_deploy(
        ops_test: pytest_operator.plugin.OpsTest,
        application_name
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
    for unit in ops_test.model.applications[application_name].units:
        assert (
                unit.workload_status == ops.model.BlockedStatus.name
        ), "status should be 'blocked' since the default database info is empty"

        assert (
                "Waiting for db" in unit.workload_status_message
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
        application_name
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

    for unit in ops_test.model.applications[application_name].units:
        assert (
                unit.workload_status == ops.model.BlockedStatus.name
        ), "unit status should be blocked"
        msg = unit.workload_status_message
        assert (
                "MySQL error" in msg and
                ("2003" in msg or "2005" in msg)
        ), "unit status message should show detailed installation failure"


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_mysql_relation(
        ops_test: pytest_operator.plugin.OpsTest,
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
    app_status = ops_test.model.applications[application_name].status
    assert (
            app_status == ops.model.ActiveStatus.name
    ), (
        "application status should be active once correct database connection info "
        "being provided via relation"
    )


@pytest.mark.asyncio
async def test_wordpress_functionality(
        unit_ip_list,
        default_admin_password
):
    """
    arrange: after WordPress charm has been deployed and db relation established
    act: test WordPress basic functionality (login, post, comment)
    assert: WordPress works normally as a blog site
    """
    for unit_ip in unit_ip_list:
        WordpressClient.run_wordpress_functionality_test(
            host=unit_ip,
            admin_username="admin",
            admin_password=default_admin_password
        )


@pytest.mark.asyncio
async def test_wordpress_default_themes(
        unit_ip_list,
        get_theme_list_from_ip
):
    """
    arrange: after WordPress charm has been deployed and db relation established
    act: check installed WordPress themes
    assert: all default themes should be installed
    """
    for unit_ip in unit_ip_list:
        assert (
                set(WordpressCharm._WORDPRESS_DEFAULT_THEMES) ==
                set(get_theme_list_from_ip(unit_ip))
        ), "default themes installed should match default themes defined in WordpressCharm"


@pytest.mark.asyncio
async def test_wordpress_install_uninstall_themes(
        ops_test: pytest_operator.plugin.OpsTest,
        application_name,
        unit_ip_list,
        get_theme_list_from_ip
):
    """
    arrange: after WordPress charm has been deployed and db relation established
    act: change themes setting in config
    assert: themes should be installed and uninstalled accordingly
    """
    theme_change_list = [
        ["twentyfifteen", "classic"],
        ["tt1-blocks", "twentyfifteen"],
        ["tt1-blocks"],
        ["twentyeleven"],
        []
    ]
    for themes in theme_change_list:
        application = ops_test.model.applications[application_name]
        await application.set_config({"themes": ",".join(themes)})
        await ops_test.model.wait_for_idle()

        for unit_ip in unit_ip_list:
            expected_themes = set(themes)
            expected_themes.update(WordpressCharm._WORDPRESS_DEFAULT_THEMES)
            assert (
                    expected_themes == set(get_theme_list_from_ip(unit_ip))
            ), f"theme installed {themes} should match themes setting in config"


@pytest.mark.asyncio
async def test_wordpress_theme_installation_error(
        ops_test: pytest_operator.plugin.OpsTest,
        application_name
):
    """
    arrange: after WordPress charm has been deployed and db relation established
    act: install a nonexistent theme
    assert: charm should switch to blocked state and the reason should be included in the status
    message.
    """
    invalid_theme = "invalid-theme-sgkeahrgalejr"
    await ops_test.model.applications[application_name].set_config({"themes": invalid_theme})
    await ops_test.model.wait_for_idle()

    for unit in ops_test.model.applications[application_name].units:
        assert (
                unit.workload_status == ops.model.BlockedStatus.name
        ), "status should be 'blocked' since the theme in themes config does not exist"

        assert (
                invalid_theme in unit.workload_status_message
        ), "status message should contain the reason why it's blocked"

    await ops_test.model.applications[application_name].set_config({"themes": ""})
    await ops_test.model.wait_for_idle()

    for unit in ops_test.model.applications[application_name].units:
        assert (
                unit.workload_status == ops.model.ActiveStatus.name
        ), "status should back to active after invalid theme removed from config"
