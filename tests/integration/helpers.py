# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helpers for WordPress charm integration tests."""

import asyncio

from juju.client._definitions import FullStatus
from juju.model import Model


async def wait_unit_agents_idle(model: Model, application_name: str):
    """Wait for application unit agents to be in idle state.

    This function is used for applications status that stays in idle state while the unit agent
    states could be in executing. Accessing any of the application while the units are executing
    may lead to an incorrect state being returned, hence the wait_unit_agents_idle.

    Args:
        model: The model in test.
        application_name: The name of the application to wait for units to become idle.

    Raises:
        TimeoutError: if application units do not become idle within given time.
    """
    idle = False
    for _ in range(5):
        status: FullStatus = await model.get_status(filters=[application_name])
        idle = all(
            unit.agent_status.status == "idle"
            for unit in status.applications[application_name].units.values()
        )
        if idle:
            break
        await asyncio.sleep(10.0)
    if not idle:
        raise TimeoutError(f"{application_name} unit agent state not idle.")
