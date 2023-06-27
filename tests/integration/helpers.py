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
    func: typing.Callable[[], typing.Union[typing.Awaitable, typing.Any]],
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
    is_awaitable = inspect.iscoroutinefunction(func)
    while now - start_time < min_wait_seconds:
        if is_awaitable and await func():
            break
        if func():
            break
        now = datetime.now()
        sleep(check_interval)
    else:
        if is_awaitable and await func():
            return
        if func():
            return
        raise TimeoutError()
