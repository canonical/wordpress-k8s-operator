# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for commonly used internal types in testing WordPress charm."""

from typing import NamedTuple


class DatabaseConfig(NamedTuple):
    """Metadata needed to fulfill mysql relation.

    Attrs:
        name: Database name to create tables for WordPress.
        user: Username credential for WordPress's access to mysql db.
        password: Password credential for WordPress's access to mysql db.
    """

    name: str
    user: str
    password: str
