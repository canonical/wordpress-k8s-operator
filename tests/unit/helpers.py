# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helpers for WordPress charm unit tests."""


def get_first_endpoint(endpoints: str):
    """Retrieve first endpoint from comma separated endpoints in host:port format.

    Args:
        endpoints: comma separated endpoints in host:port format.

    Returns:
        The first endpoint hostname.
    """
    return endpoints.split(",")[0].split(":")[0]
