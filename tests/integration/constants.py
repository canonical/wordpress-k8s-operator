# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Constants used in integration tests."""

import typing

from ops.model import ActiveStatus, BlockedStatus

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore
BLOCKED_STATUS_NAME = typing.cast(str, BlockedStatus.name)  # type: ignore
