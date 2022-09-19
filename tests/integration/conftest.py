import pytest
import juju.action
import pytest_asyncio
import juju.application
import pytest_operator.plugin

from wordpress_client import WordpressClient


@pytest_asyncio.fixture(scope="function", name="app_config")
async def fixture_app_config(request, ops_test: pytest_operator.plugin.OpsTest):
    """Change the charm config to specific values and revert that after test"""
    config = request.param
    application: juju.application.Application = ops_test.model.applications["wordpress"]
    original_config: dict = await application.get_config()
    original_config = {
        k: v["value"] for k, v in original_config.items()
        if k in config
    }
    await application.set_config(config)
    await ops_test.model.wait_for_idle()

    yield config

    await application.set_config(original_config)
    await ops_test.model.wait_for_idle()


@pytest.fixture(scope="module", name="application_name")
def fixture_application_name():
    return "wordpress"


@pytest_asyncio.fixture(scope="function", name="default_admin_password")
async def fixture_default_admin_password(
        ops_test: pytest_operator.plugin.OpsTest,
        application_name
):
    application: juju.application = ops_test.model.applications[application_name]
    action: juju.action.Action = await application.units[0].run_action("get-initial-password")
    await action.wait()

    yield action.results["password"]


@pytest_asyncio.fixture(scope="function", name="get_unit_ip_list")
async def fixture_get_unit_ip_list(
        ops_test: pytest_operator.plugin.OpsTest,
        application_name
):
    """Helper function to retrieve unit ip addresses, similar to fixture_get_unit_status_list"""

    async def _get_unit_ip_list():
        status = await ops_test.model.get_status()
        units = status.applications[application_name].units
        ip_list = []
        for key in sorted(units.keys(), key=lambda n: int(n.split("/")[-1])):
            ip_list.append(units[key].address)
        return ip_list

    yield _get_unit_ip_list


@pytest_asyncio.fixture(scope="function", name="unit_ip_list")
async def fixture_unit_ip_list(
        get_unit_ip_list
):
    """A fixture containing ip addresses of current units"""
    yield await get_unit_ip_list()


@pytest_asyncio.fixture(scope="function", name="get_theme_list_from_ip")
async def fixture_get_theme_list_from_ip(
        default_admin_password
):
    """Retrieve installed themes from the WordPress instance"""

    def _get_theme_list_from_ip(unit_ip):
        wordpress_client = WordpressClient(
            host=unit_ip,
            username="admin",
            password=default_admin_password,
            is_admin=True
        )
        return wordpress_client.list_themes()

    return _get_theme_list_from_ip
