# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helpers for WordPress charm integration tests."""

import inspect
import typing
from datetime import datetime, timedelta
from time import sleep

from juju.client._definitions import FullStatus
from juju.model import Model


async def wait_for(
    func: typing.Union[typing.Awaitable, typing.Callable],
    timeout: int = 300,
    check_interval: int = 10,
) -> None:
    """Wait for function execution to become truthy.

    Args:
        func: A callback function to wait to return a truthy value.
        timeout: Time in seconds to wait for function result to become truthy.
        check_interval: Time in seconds to wait between ready checks.

    Raises:
        TimeoutError: if the callback function did not return a truthy value within timeout.
    """
    start_time = now = datetime.now()
    min_wait_seconds = timedelta(seconds=timeout)
    isAwaitable = inspect.iscoroutinefunction(func)
    while now - start_time < min_wait_seconds:
        if isAwaitable and await func():
            break
        elif func():
            break
        now = datetime.now()
        sleep(check_interval)
    else:
        if isAwaitable and await func():
            return
        elif func():
            return
        raise TimeoutError()


async def are_unit_agents_idle(model: Model, application_name: str):
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
    status: FullStatus = await model.get_status(filters=[application_name])
    return all(
        unit.agent_status.status == "idle"
        for unit in status.applications[application_name].units.values()
    )
