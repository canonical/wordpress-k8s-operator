# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Wordpress charm state."""
import dataclasses
import logging
import os
import typing

import ops

# pylint: disable=no-name-in-module
from pydantic import BaseModel, HttpUrl, ValidationError, tools

logger = logging.getLogger(__name__)


class CharmConfigInvalidError(Exception):
    """Exception raised when a charm configuration is found to be invalid.

    Attributes:
        msg: Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the CharmConfigInvalidError exception.

        Args:
            msg: Explanation of the error.
        """
        self.msg = msg


class ProxyConfig(BaseModel):
    """Configuration for accessing Jenkins through proxy.

    Attributes:
        http_proxy: The http proxy URL.
        https_proxy: The https proxy URL.
        no_proxy: Comma separated list of hostnames to bypass proxy.
    """

    http_proxy: typing.Optional[HttpUrl]
    https_proxy: typing.Optional[HttpUrl]
    no_proxy: typing.Optional[str]

    @classmethod
    def from_env(cls) -> typing.Optional["ProxyConfig"]:
        """Instantiate ProxyConfig from juju charm environment.

        Returns:
            ProxyConfig if proxy configuration is provided, None otherwise.
        """
        http_proxy = os.environ.get("JUJU_CHARM_HTTP_PROXY")
        https_proxy = os.environ.get("JUJU_CHARM_HTTPS_PROXY")
        no_proxy = os.environ.get("JUJU_CHARM_NO_PROXY")

        if not http_proxy and not https_proxy:
            return None

        return cls(
            http_proxy=tools.parse_obj_as(HttpUrl, http_proxy),
            https_proxy=tools.parse_obj_as(HttpUrl, https_proxy),
            no_proxy=no_proxy,
        )


@dataclasses.dataclass(frozen=True)
class State:
    """The Wordpress k8s operator charm state.

    Attributes:
        proxy_config: Proxy configuration to access Jenkins upstream through.
    """

    proxy_config: typing.Optional[ProxyConfig]

    @classmethod
    def from_charm(cls, _: ops.CharmBase) -> "State":
        """Initialize the state from charm.

        Returns:
            Current state of the charm.

        Raises:
            CharmConfigInvalidError: if invalid state values were encountered.
        """
        try:
            proxy_config = ProxyConfig.from_env()
        except ValidationError as exc:
            logger.error("Invalid juju model proxy configuration, %s", exc)
            raise CharmConfigInvalidError("Invalid model proxy configuration.") from exc

        return cls(
            proxy_config=proxy_config,
        )
