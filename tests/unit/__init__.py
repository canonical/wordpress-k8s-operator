# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Enable ops.testing.SIMULATE_CAN_CONNECT for all unit tests."""

import ops.testing

# The attribute exists
ops.testing.SIMULATE_CAN_CONNECT = True  # type: ignore[attr-defined]
