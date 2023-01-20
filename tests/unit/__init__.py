# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Enable ops.testing.SIMULATE_CAN_CONNECT for all unit tests."""

import ops.testing

ops.testing.SIMULATE_CAN_CONNECT = True
