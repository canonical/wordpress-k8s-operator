import pytest
import ops.model
import juju.application
import pytest_operator.plugin



@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: pytest_operator.plugin.OpsTest):
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

    application: juju.application.Application = ops_test.model.applications["wordpress"]
    for unit in application.units:
        assert (
            unit.workload_status == ops.model.BlockedStatus.name,
            "status should be 'blocked' since the default database info is empty"
        )
        assert (
            "Waiting for db" in unit.workload_status_message,
            "status message should contain the reason why it's blocked"
        )

@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_incorrect_db_info(ops_test: pytest_operator.plugin.OpsTest):
    """
    arrange: after WordPress charm has been deployed
    act: provide incorrect database info via config
    assert: charm should be blocked by WordPress installation errors, instead of lacking
    of database connection info
    """
    application: juju.application.Application = ops_test.model.applications["wordpress"]
    await application.set_config({
        "db_host": "test_db_host",
        "db_name": "test_db_name",
        "db_user": "test_db_user",
        "db_password": "test_db_password"
    })
    await ops_test.model.wait_for_idle()

    for unit in application.units:
        assert (
            unit.workload_status == ops.model.BlockedStatus.name,
            "unit status should be blocked"
        )
        assert (
            "installation failed" in unit.workload_status_message,
            "unit status message should show the reason for blocking: installation failure"
        )
        assert (
            "2005" in unit.workload_status_message,
            "unit status message should show detailed installation failure: MySQL Error 2005"
            "CR_UNKNOWN_HOST"
        )

    # resume database config for following test cases
    await application.set_config({
        "db_host": "",
        "db_name": "",
        "db_user": "",
        "db_password": ""
    })
    await ops_test.model.wait_for_idle()

@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_mysql_relation(ops_test: pytest_operator.plugin.OpsTest):
    """
    arrange: after WordPress charm has been deployed
    act: deploy a mariadb charm and add a relation between WordPress and mariadb
    assert: WordPress should be active
    """
    await ops_test.model.deploy("charmed-osm-mariadb-k8s", application_name="mariadb")
    await ops_test.model.add_relation("wordpress", "mariadb:mysql")
    await ops_test.model.wait_for_idle()

    application: juju.application.Application = ops_test.model.applications["wordpress"]
    assert (
        application.status == ops.model.ActiveStatus.name,
        "application status should be active once correct database connection info "
        "being provided via relation"
    )
