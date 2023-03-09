# Copyright 2023 Canonical Ltd.
# Licensed under the Apache2.0, see LICENCE file in charm source for details.
"""Library for the ingress relation.

This library contains the Requires and Provides classes for handling
the ingress interface.

Import `IngressRequires` in your charm, with two required options:
- "self" (the charm itself)
- config_dict

`config_dict` accepts the following keys:
- additional-hostnames
- limit-rps
- limit-whitelist
- max-body-size
- owasp-modsecurity-crs
- owasp-modsecurity-custom-rules
- path-routes
- retry-errors
- rewrite-enabled
- rewrite-target
- service-hostname (required)
- service-name (required)
- service-namespace
- service-port (required)
- session-cookie-max-age
- tls-secret-name

See [the config section](https://charmhub.io/nginx-ingress-integrator/configure) for descriptions
of each, along with the required type.

As an example, add the following to `src/charm.py`:
```
from charms.nginx_ingress_integrator.v0.ingress import IngressRequires

# In your charm's `__init__` method.
self.ingress = IngressRequires(self, {
        "service-hostname": self.config["external_hostname"],
        "service-name": self.app.name,
        "service-port": 80,
    }
)

# In your charm's `config-changed` handler.
self.ingress.update_config({"service-hostname": self.config["external_hostname"]})
```
And then add the following to `metadata.yaml`:
```
requires:
  ingress:
    interface: ingress
```
You _must_ register the IngressRequires class as part of the `__init__` method
rather than, for instance, a config-changed event handler, for the relation
changed event to be properly handled.
"""

import copy
import logging
from typing import Dict

from ops.charm import CharmBase, CharmEvents, RelationBrokenEvent, RelationChangedEvent
from ops.framework import EventBase, EventSource, Object
from ops.model import BlockedStatus

INGRESS_RELATION_NAME = "ingress"
INGRESS_PROXY_RELATION_NAME = "ingress-proxy"

# The unique Charmhub library identifier, never change it
LIBID = "db0af4367506491c91663468fb5caa4c"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 15

LOGGER = logging.getLogger(__name__)

REQUIRED_INGRESS_RELATION_FIELDS = {"service-hostname", "service-name", "service-port"}

OPTIONAL_INGRESS_RELATION_FIELDS = {
    "additional-hostnames",
    "limit-rps",
    "limit-whitelist",
    "max-body-size",
    "owasp-modsecurity-crs",
    "owasp-modsecurity-custom-rules",
    "path-routes",
    "retry-errors",
    "rewrite-target",
    "rewrite-enabled",
    "service-namespace",
    "session-cookie-max-age",
    "tls-secret-name",
}

RELATION_INTERFACES_MAPPINGS = {
    "service-hostname": "host",
    "service-name": "name",
    "service-namespace": "model",
    "service-port": "port",
}
RELATION_INTERFACES_MAPPINGS_VALUES = set(RELATION_INTERFACES_MAPPINGS.values())


class IngressAvailableEvent(EventBase):
    """IngressAvailableEvent custom event.

    This event indicates the Ingress provider is available.
    """


class IngressProxyAvailableEvent(EventBase):
    """IngressProxyAvailableEvent custom event.

    This event indicates the IngressProxy provider is available.
    """


class IngressBrokenEvent(RelationBrokenEvent):
    """IngressBrokenEvent custom event.

    This event indicates the Ingress provider is broken.
    """


class IngressCharmEvents(CharmEvents):
    """Custom charm events.

    Attrs:
        ingress_available: Event to indicate that Ingress is available.
        ingress_proxy_available: Event to indicate that IngressProxy is available.
        ingress_broken: Event to indicate that Ingress is broken.
    """

    ingress_available = EventSource(IngressAvailableEvent)
    ingress_proxy_available = EventSource(IngressProxyAvailableEvent)
    ingress_broken = EventSource(IngressBrokenEvent)


class IngressRequires(Object):
    """This class defines the functionality for the 'requires' side of the 'ingress' relation.

    Hook events observed:
        - relation-changed

    Attrs:
        model: Juju model where the charm is deployed.
        config_dict: Contains all the configuration options for Ingress.
    """

    def __init__(self, charm: CharmBase, config_dict: Dict) -> None:
        """Init function for the IngressRequires class.

        Args:
            charm: The charm that requires the ingress relation.
            config_dict: Contains all the configuration options for Ingress.
        """
        super().__init__(charm, INGRESS_RELATION_NAME)

        self.framework.observe(
            charm.on[INGRESS_RELATION_NAME].relation_changed, self._on_relation_changed
        )

        # Set default values.
        default_relation_fields = {
            "service-namespace": self.model.name,
        }
        config_dict.update(
            (key, value)
            for key, value in default_relation_fields.items()
            if key not in config_dict or not config_dict[key]
        )

        self.config_dict = self._convert_to_relation_interface(config_dict)

    @staticmethod
    def _convert_to_relation_interface(config_dict: Dict) -> Dict:
        """Create a new relation dict that conforms with charm-relation-interfaces.

        Args:
            config_dict: Ingress configuration that doesn't conform with charm-relation-interfaces.

        Returns:
            The Ingress configuration conforming with charm-relation-interfaces.
        """
        config_dict = copy.copy(config_dict)
        config_dict.update(
            (key, config_dict[old_key])
            for old_key, key in RELATION_INTERFACES_MAPPINGS.items()
            if old_key in config_dict and config_dict[old_key]
        )
        return config_dict

    def _config_dict_errors(self, config_dict: Dict, update_only: bool = False) -> bool:
        """Check our config dict for errors.

        Args:
            config_dict: Contains all the configuration options for Ingress.
            update_only: If the charm needs to update only existing keys.

        Returns:
            If we need to update the config dict or not.
        """
        blocked_message = "Error in ingress relation, check `juju debug-log`"
        unknown = [
            config_key
            for config_key in config_dict
            if config_key
            not in REQUIRED_INGRESS_RELATION_FIELDS
            | OPTIONAL_INGRESS_RELATION_FIELDS
            | RELATION_INTERFACES_MAPPINGS_VALUES
        ]
        if unknown:
            LOGGER.error(
                "Ingress relation error, unknown key(s) in config dictionary found: %s",
                ", ".join(unknown),
            )
            self.model.unit.status = BlockedStatus(blocked_message)
            return True
        if not update_only:
            missing = tuple(
                config_key
                for config_key in REQUIRED_INGRESS_RELATION_FIELDS
                if config_key not in self.config_dict
            )
            if missing:
                LOGGER.error(
                    "Ingress relation error, missing required key(s) in config dictionary: %s",
                    ", ".join(sorted(missing)),
                )
                self.model.unit.status = BlockedStatus(blocked_message)
                return True
        return False

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Handle the relation-changed event.

        Args:
            event: Event triggering the relation-changed hook for the relation.
        """
        # `self.unit` isn't available here, so use `self.model.unit`.
        if self.model.unit.is_leader():
            if self._config_dict_errors(config_dict=self.config_dict):
                return
            event.relation.data[self.model.app].update(
                (key, str(self.config_dict[key])) for key in self.config_dict
            )

    def update_config(self, config_dict: Dict) -> None:
        """Allow for updates to relation.

        Args:
            config_dict: Contains all the configuration options for Ingress.

        Attrs:
            config_dict: Contains all the configuration options for Ingress.
        """
        if self.model.unit.is_leader():
            self.config_dict = self._convert_to_relation_interface(config_dict)
            if self._config_dict_errors(self.config_dict, update_only=True):
                return
            relation = self.model.get_relation(INGRESS_RELATION_NAME)
            if relation:
                for key in self.config_dict:
                    relation.data[self.model.app][key] = str(self.config_dict[key])


class IngressBaseProvides(Object):
    """Parent class for IngressProvides and IngressProxyProvides.

    Attrs:
        model: Juju model where the charm is deployed.
    """

    def __init__(self, charm: CharmBase, relation_name: str) -> None:
        """Init function for the IngressProxyProvides class.

        Args:
            charm: The charm that provides the ingress-proxy relation.
        """
        super().__init__(charm, relation_name)
        self.charm = charm

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Handle a change to the ingress/ingress-proxy relation.

        Confirm we have the fields we expect to receive.

        Args:
            event: Event triggering the relation-changed hook for the relation.
        """
        # `self.unit` isn't available here, so use `self.model.unit`.
        if not self.model.unit.is_leader():
            return

        relation_name = event.relation.name

        assert event.app is not None  # nosec
        if not event.relation.data[event.app]:
            LOGGER.info(
                "%s hasn't finished configuring, waiting until relation is changed again.",
                relation_name,
            )
            return

        ingress_data = {
            field: event.relation.data[event.app].get(field)
            for field in REQUIRED_INGRESS_RELATION_FIELDS | OPTIONAL_INGRESS_RELATION_FIELDS
        }

        missing_fields = sorted(
            field for field in REQUIRED_INGRESS_RELATION_FIELDS if ingress_data.get(field) is None
        )

        if missing_fields:
            LOGGER.warning(
                "Missing required data fields for %s relation: %s",
                relation_name,
                ", ".join(missing_fields),
            )
            self.model.unit.status = BlockedStatus(
                f"Missing fields for {relation_name}: {', '.join(missing_fields)}"
            )

        if relation_name == INGRESS_RELATION_NAME:
            # Conform to charm-relation-interfaces.
            if "name" in ingress_data and "port" in ingress_data:
                name = ingress_data["name"]
                port = ingress_data["port"]
            else:
                name = ingress_data["service-name"]
                port = ingress_data["service-port"]
            event.relation.data[self.model.app]["url"] = f"http://{name}:{port}/"

            # Create an event that our charm can use to decide it's okay to
            # configure the ingress.
            self.charm.on.ingress_available.emit()
        elif relation_name == INGRESS_PROXY_RELATION_NAME:
            self.charm.on.ingress_proxy_available.emit()


class IngressProvides(IngressBaseProvides):
    """Class containing the functionality for the 'provides' side of the 'ingress' relation.

    Attrs:
        charm: The charm that provides the ingress relation.

    Hook events observed:
        - relation-changed
    """

    def __init__(self, charm: CharmBase) -> None:
        """Init function for the IngressProvides class.

        Args:
            charm: The charm that provides the ingress relation.
        """
        super().__init__(charm, INGRESS_RELATION_NAME)
        # Observe the relation-changed hook event and bind
        # self.on_relation_changed() to handle the event.
        self.framework.observe(
            charm.on[INGRESS_RELATION_NAME].relation_changed, self._on_relation_changed
        )
        self.framework.observe(
            charm.on[INGRESS_RELATION_NAME].relation_broken, self._on_relation_broken
        )

    def _on_relation_broken(self, event: RelationBrokenEvent) -> None:
        """Handle a relation-broken event in the ingress relation.

        Args:
            event: Event triggering the relation-broken hook for the relation.
        """
        if not self.model.unit.is_leader():
            return

        # Create an event that our charm can use to remove the ingress resource.
        self.charm.on.ingress_broken.emit(event.relation)


class IngressProxyProvides(IngressBaseProvides):
    """Class containing the functionality for the 'provides' side of the 'ingress-proxy' relation.

    Attrs:
        charm: The charm that provides the ingress-proxy relation.

    Hook events observed:
        - relation-changed
    """

    def __init__(self, charm: CharmBase) -> None:
        """Init function for the IngressProxyProvides class.

        Args:
            charm: The charm that provides the ingress-proxy relation.
        """
        super().__init__(charm, INGRESS_PROXY_RELATION_NAME)
        # Observe the relation-changed hook event and bind
        # self.on_relation_changed() to handle the event.
        self.framework.observe(
            charm.on[INGRESS_PROXY_RELATION_NAME].relation_changed, self._on_relation_changed
        )
