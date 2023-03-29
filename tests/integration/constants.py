# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Constants used in integration tests."""

import typing

from ops.model import ActiveStatus, BlockedStatus

ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)
BLOCKED_STATUS_NAME = typing.cast(str, BlockedStatus.name)
