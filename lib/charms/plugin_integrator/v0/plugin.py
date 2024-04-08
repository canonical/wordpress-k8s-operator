#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# Licensed under the Apache2.0. See LICENSE file in charm source for details.

import typing

import ops


LIBID = "whatever goes here"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1

class ReconcilePluginsEvent(ops.RelationEvent):
    """ReconcileOCIPluginsEvent custom event.

    This event indicates the list of plugins to install or update with their versions.
    """


class PluginRequiresEvents(ops.CharmEvents):
    """SAML events.

    This class defines the events that a SAML requirer can emit.
    """

    reconcile_plugins = ops.EventSource(ReconcilePluginsEvent)


class PluginRequires(ops.Object):
    """Requirer side of the SAML relation.

    Attrs:
        on: events the provider can emit.
    """

    on = PluginRequiresEvents()

    def __init__(self, charm: ops.CharmBase, relation_name: str) -> None:
        """Construct.

        Args:
            charm: the provider charm.
            relation_name: the relation name.
        """
        super().__init__(charm, relation_name)
        self.charm = charm
        self.relation_name = relation_name
        self.framework.observe(charm.on[relation_name].relation_changed, self._on_relation_changed)

    def _on_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Event emitted when the relation has changed.

        Args:
            event: event triggering this handler.
        """
        assert event.relation.app
        if event.relation.data[event.relation.app]:
            self.on.reconcile_plugins.emit(event.relation, app=event.app, unit=event.unit)


class PluginProvides(ops.Object):
    """Provider side of the SAML relation.

    Attrs:
        relations: list of charm relations.
    """

    def __init__(self, charm: ops.CharmBase, relation_name: str) -> None:
        """Construct.

        Args:
            charm: the provider charm.
            relation_name: the relation name.
        """
        super().__init__(charm, relation_name)
        self.charm = charm
        self.relation_name = relation_name

    @property
    def relations(self) -> typing.List[ops.Relation]:
        """The list of Relation instances associated with this relation_name.

        Returns:
            List of relations to this charm.
        """
        return list(self.model.relations[self.relation_name])

    def update_relation_data(self, relation: ops.Relation, plugin_data: dict) -> None:
        """Update the relation data.

        Args:
            relation: the relation for which to update the data.
            saml_data: a SamlRelationData instance wrapping the data to be updated.
        """
        relation.data[self.charm.model.app].update(plugin_data.to_relation_data())
