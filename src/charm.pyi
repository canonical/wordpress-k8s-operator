from typing import Optional, Union, List, Dict, Tuple, TypedDict

import ops
import ops.model
import ops.framework
import opslib.mysql


class DBInfoDict(TypedDict):
    DB_HOST: str
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str


class WordpressCharm(ops.charm.CharmBase):
    class _ReplicaRelationNotReady(Exception): ...

    state: ops.framework.StoredState
    _WP_CONFIG_PATH: str
    _CONTAINER_NAME: str
    _SERVICE_NAME: str
    _WORDPRESS_USER: str
    _WORDPRESS_GROUP: str
    _WORDPRESS_DB_CHARSET: str
    _DB_CHECK_INTERVAL: Union[float, int]

    @staticmethod
    def _wordpress_secret_key_fields() -> List[str]: ...

    def _generate_wp_secret_keys(self) -> Dict[str, str]: ...

    def _replica_relation_data(self) -> ops.charm.model.RelationDataContent: ...

    def _replica_consensus_reached(self) -> bool: ...

    def _on_leader_elected_replica_data_handler(
            self,
            event: ops.charm.LeaderElectedEvent
    ) -> None: ...

    def _on_relation_database_changed(
            self,
            event: opslib.mysql.MySQLDatabaseChangedEvent
    ) -> None: ...

    def _gen_wp_config(self) -> str: ...

    def _container(self) -> ops.charm.model.Container: ...

    def _wordpress_service_exists(self) -> bool: ...

    def _stop_server(self) -> None: ...

    def _wp_is_installed(self) -> None: ...

    def _current_effective_db_info(self) -> DBInfoDict: ...

    def _test_database_connectivity(self) -> Tuple[bool, str]: ...

    def _wp_install_cmd(self) -> List[str]: ...

    def _wp_install(self) -> None: ...

    def _init_pebble_layer(self) -> None: ...

    def _start_server(self) -> None: ...

    def _current_wp_config(self) -> Optional[str]: ...

    def _remove_wp_config(self) -> None: ...

    def _push_wp_config(self, wp_config: str) -> None: ...

    def _core_reconciliation(self) -> None: ...

    def _reconciliation(self, _event: ops.charm.EventBase) -> None: ...