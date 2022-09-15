import json

import pytest
import juju.action
import pytest_asyncio
import juju.application
import pytest_operator.plugin


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


@pytest_asyncio.fixture(scope="module", name="get_app_status")
async def fixture_get_app_status(ops_test: pytest_operator.plugin.OpsTest):
    """Helper function to get the status of application

    Returns a async function that can retrieve the current status of a application, if application
    name not given, default to the WordPress application. The status is in string form.
    """

    async def _get_app_status(application_name: str = "wordpress"):
        status = await ops_test.model.get_status()
        return status.applications[application_name].status.status

    return _get_app_status


@pytest_asyncio.fixture(scope="module", name="get_app_status_msg")
async def fixture_get_app_status_msg(ops_test: pytest_operator.plugin.OpsTest):
    """Helper function to get the status message of application

    Similar to fixture_get_app_status, but return status message instead
    """

    async def _get_app_status(application_name: str = "wordpress"):
        status = await ops_test.model.get_status()
        return status.applications[application_name].info

    return _get_app_status


@pytest_asyncio.fixture(scope="module", name="get_unit_status_list")
async def fixture_get_unit_status_list(ops_test: pytest_operator.plugin.OpsTest):
    """Helper function to get status of units

    Returns a async function that can retrieve the current status of all the units from
    an application, if application name not given, default to the WordPress application.
    The status is in string form. The result list is sorted by unit id.
    """

    async def _get_unit_status_list(application_name: str = "wordpress"):
        status = await ops_test.model.get_status()
        result = []
        units_dict = status.applications[application_name].units
        unit_names = sorted(units_dict.keys(), key=lambda n: int(n.split("/")[-1]))
        for unit_name in unit_names:
            result.append(units_dict[unit_name].workload_status.status)
        return result

    return _get_unit_status_list


@pytest_asyncio.fixture(scope="module", name="get_unit_status_msg_list")
async def fixture_get_unit_status_msg_list(ops_test: pytest_operator.plugin.OpsTest):
    """Helper function to get status messages of units

    Similar to fixture_get_unit_status_list, but return status message instead
    """

    async def _get_unit_status_msg_list(application_name: str = "wordpress"):
        status = await ops_test.model.get_status()
        result = []
        units_dict = status.applications[application_name].units

        unit_names = sorted(units_dict.keys(), key=lambda n: int(n.split("/")[-1]))
        for unit_name in unit_names:
            result.append(units_dict[unit_name].workload_status.info)
        return result

    return _get_unit_status_msg_list


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

    return _get_unit_ip_list
