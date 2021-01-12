"""
MySQL endpoint implementation for the Operator Framework.

Ported to the Operator Framework from the canonical-osm Reactive
charms at https://git.launchpad.net/canonical-osm
"""

import logging

import ops.charm
import ops.framework
import ops.model


__all__ = ["MySQLClient", "MySQLClientEvents", "MySQLRelationEvent", "MySQLDatabaseChangedEvent"]


class _MySQLConnectionDetails(object):
    database: str = None
    host: str = None
    port: int = 3306
    user: str = None
    password: str = None
    root_password: str = None
    connection_string: str = None
    sanitized_connection_string: str = None  # With no secrets, for logging.
    is_available: bool = False

    def __init__(self, relation: ops.model.Relation, unit: ops.model.Unit):
        reldata = relation.data.get(unit, {})
        self.database = reldata.get("database", None)
        self.host = reldata.get("host", None)
        self.port = int(reldata.get("port", 3306))
        self.user = reldata.get("user", None)
        self.password = reldata.get("password", None)
        self.root_password = reldata.get("root_password", None)

        if all([self.database, self.host, self.port, self.user, self.password, self.root_password]):
            self.sanitized_connection_string = (
                f"host={self.host} port={self.port} dbname={self.database} user={self.user}"
            )
            self.connection_string = (
                self.sanitized_connection_string + f" password={self.password} root_password={self.root_password}"
            )
        else:
            self.sanitized_connection_string = None
            self.connection_string = None
        self.is_available = self.connection_string is not None


class MySQLRelationEvent(ops.charm.RelationEvent):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._conn = _MySQLConnectionDetails(self.relation, self.unit)

    @property
    def is_available(self) -> bool:
        """True if the database is available for use."""
        return self._conn.is_available

    @property
    def connection_string(self) -> str:
        """The connection string, if available, or None.

        The connection string will be in the format:

            'host={host} port={port} dbname={database} user={user} password={password} root_password={root_password}'
        """
        return self._conn.connection_string

    @property
    def database(self) -> str:
        """The name of the provided database, or None."""
        return self._conn.database

    @property
    def host(self) -> str:
        """The host for the provided database, or None."""
        return self._conn.host

    @property
    def port(self) -> int:
        """The port to the provided database."""
        # If not available, returns the default port of 3306.
        return self._conn.port

    @property
    def user(self) -> str:
        """The username for the provided database, or None."""
        return self._conn.user

    @property
    def password(self) -> str:
        """The password for the provided database, or None."""
        return self._conn.password

    @property
    def root_password(self) -> str:
        """The password for the root user, or None."""
        return self._conn.root_password

    def restore(self, snapshot) -> None:
        super().restore(snapshot)
        self._conn = _MySQLConnectionDetails(self.relation, self.unit)


class MySQLDatabaseChangedEvent(MySQLRelationEvent):
    """The database connection details on the relation have changed.

    This event is emitted when the database first becomes available
    for use, when the connection details have changed, and when it
    becomes unavailable.
    """

    pass


class MySQLClientEvents(ops.framework.ObjectEvents):
    database_changed = ops.framework.EventSource(MySQLDatabaseChangedEvent)


class MySQLClient(ops.framework.Object):
    """Requires side of a MySQL Endpoint"""

    on = MySQLClientEvents()
    _state = ops.framework.StoredState()

    relation_name: str = None
    log: logging.Logger = None

    def __init__(self, charm: ops.charm.CharmBase, relation_name: str):
        super().__init__(charm, relation_name)

        self.relation_name = relation_name
        self.log = logging.getLogger("mysql.client.{}".format(relation_name))
        self._state.set_default(rels={})

        self.framework.observe(charm.on[relation_name].relation_changed, self._on_changed)
        self.framework.observe(charm.on[relation_name].relation_broken, self._on_broken)

    def _on_changed(self, event: ops.charm.RelationEvent) -> None:
        if event.unit is None:
            return  # Ignore application relation data events.

        prev_conn_str = self._state.rels.get(event.relation.id, None)
        new_cd = _MySQLConnectionDetails(event.relation, event.unit)
        new_conn_str = new_cd.connection_string

        if prev_conn_str != new_conn_str:
            self._state.rels[event.relation.id] = new_conn_str
            if new_conn_str is None:
                self.log.info(f"Database on relation {event.relation.id} is no longer available.")
            else:
                self.log.info(
                    f"Database on relation {event.relation.id} available at {new_cd.sanitized_connection_string}."
                )
            self.on.database_changed.emit(relation=event.relation, app=event.app, unit=event.unit)

    def _on_broken(self, event: ops.charm.RelationEvent) -> None:
        self.log.info(f"Database relation {event.relation.id} is gone.")
        prev_conn_str = self._state.rels.get(event.relation.id, None)
        if event.relation.id in self._state.rels:
            del self._state.rels[event.relation.id]
        if prev_conn_str is None:
            return
        self.on.database_changed.emit(relation=event.relation, app=event.app, unit=None)
