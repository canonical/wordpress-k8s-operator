# Copyright 2022 Canonical Ltd.
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
- service-hostname (required)
- session-cookie-max-age
- service-name (required)
- service-namespace
- service-port (required)
- tls-secret-name
- owasp-modsecurity-crs
- owasp-modsecurity-custom-rules
- path-routes
- retry-errors
- rewrite-enabled
- rewrite-target

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

from ops.charm import CharmEvents, RelationBrokenEvent, RelationChangedEvent
from ops.framework import EventBase, EventSource, Object
from ops.model import BlockedStatus
from typing import Dict

# The unique Charmhub library identifier, never change it
LIBID = "db0af4367506491c91663468fb5caa4c"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 13

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
RELATION_INTERFACES_MAPPINGS_VALUES = {v for v in RELATION_INTERFACES_MAPPINGS.values()}


class IngressAvailableEvent(EventBase):
    pass


class IngressBrokenEvent(RelationBrokenEvent):
    pass


class IngressCharmEvents(CharmEvents):
    """Custom charm events."""

    ingress_available = EventSource(IngressAvailableEvent)
    ingress_broken = EventSource(IngressBrokenEvent)


class IngressRequires(Object):
    """This class defines the functionality for the 'requires' side of the 'ingress' relation.

    Hook events observed:
        - relation-changed
    """

    def __init__(self, charm, config_dict):
        super().__init__(charm, "ingress")

        self.framework.observe(charm.on["ingress"].relation_changed, self._on_relation_changed)

        # Set default values.
        DEFAULT_RELATION_FIELDS = {
            "service-namespace": self.model.name,
        }
        for default_key, default_value in DEFAULT_RELATION_FIELDS.items():
            if default_key not in config_dict or not config_dict[default_key]:
                config_dict[default_key] = default_value

        self.config_dict = self._convert_to_relation_interface(config_dict)

    @staticmethod
    def _convert_to_relation_interface(config_dict: Dict) -> Dict:
        """create a new relation dict that conforms with charm-relation-interfaces."""
        config_dict = copy.copy(config_dict)
        for old_key, new_key in RELATION_INTERFACES_MAPPINGS.items():
            if old_key in config_dict and config_dict[old_key]:
                config_dict[new_key] = config_dict[old_key]
        return config_dict

    def _config_dict_errors(self, update_only: bool=False) -> bool:
        """Check our config dict for errors."""
        blocked_message = "Error in ingress relation, check `juju debug-log`"
        unknown = [
            config_key
            for config_key in self.config_dict
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
            missing = [
                config_key
                for config_key in REQUIRED_INGRESS_RELATION_FIELDS
                if config_key not in self.config_dict
            ]
            if missing:
                LOGGER.error(
                    "Ingress relation error, missing required key(s) in config dictionary: %s",
                    ", ".join(sorted(missing)),
                )
                self.model.unit.status = BlockedStatus(blocked_message)
                return True
        return False

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Handle the relation-changed event."""
        # `self.unit` isn't available here, so use `self.model.unit`.
        if self.model.unit.is_leader():
            if self._config_dict_errors():
                return
            for key in self.config_dict:
                event.relation.data[self.model.app][key] = str(self.config_dict[key])

    def update_config(self, config_dict: Dict) -> None:
        """Allow for updates to relation."""
        if self.model.unit.is_leader():
            self.config_dict = self._convert_to_relation_interface(config_dict)
            if self._config_dict_errors(update_only=True):
                return
            relation = self.model.get_relation("ingress")
            if relation:
                for key in self.config_dict:
                    relation.data[self.model.app][key] = str(self.config_dict[key])


class IngressProvides(Object):
    """This class defines the functionality for the 'provides' side of the 'ingress' relation.

    Hook events observed:
        - relation-changed
    """

    def __init__(self, charm):
        super().__init__(charm, "ingress")
        # Observe the relation-changed hook event and bind
        # self.on_relation_changed() to handle the event.
        self.framework.observe(charm.on["ingress"].relation_changed, self._on_relation_changed)
        self.framework.observe(charm.on["ingress"].relation_broken, self._on_relation_broken)
        self.charm = charm

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Handle a change to the ingress relation.

        Confirm we have the fields we expect to receive.
        """
        # `self.unit` isn't available here, so use `self.model.unit`.
        if not self.model.unit.is_leader():
            return

        ingress_data = {
            field: event.relation.data[event.app].get(field)
            for field in REQUIRED_INGRESS_RELATION_FIELDS | OPTIONAL_INGRESS_RELATION_FIELDS
        }

        missing_fields = sorted(
            [
                field
                for field in REQUIRED_INGRESS_RELATION_FIELDS
                if ingress_data.get(field) is None
            ]
        )

        if missing_fields:
            LOGGER.error(
                "Missing required data fields for ingress relation: %s",
                ", ".join(missing_fields),
            )
            self.model.unit.status = BlockedStatus(
                f"Missing fields for ingress: {', '.join(missing_fields)}"
            )

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

    def _on_relation_broken(self, event: RelationBrokenEvent) -> None:
        """Handle a relation-broken event in the ingress relation."""
        if not self.model.unit.is_leader():
            return

        # Create an event that our charm can use to remove the ingress resource.
        self.charm.on.ingress_broken.emit(event.relation)
