from typing import Optional, Union, List, Dict, Tuple, TypedDict, NamedTuple, Any

import ops
import ops.model
import ops.framework
import opslib.mysql


class DBInfoDict(TypedDict):
    DB_HOST: str
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str


class WordpressCliExecResult(NamedTuple):
    return_code: int
    stdout: str
    stderr: str


class ThemeInfoDict(TypedDict):
    name: str
    status: str
    update: str
    version: str


class AddonInfoDict(TypedDict):
    name: str
    status: str
    update: str
    version: str


class WPAddonListExecResult(NamedTuple):
    success: bool
    result: Optional[List[AddonInfoDict]]
    message: str


class NoneReturnExecResult(NamedTuple):
    success: bool
    result: None
    message: str


class WordpressCharm(ops.charm.CharmBase):
    class _ReplicaRelationNotReady(Exception): ...

    class _ExecResult(NamedTuple):
        success: bool
        result: Any
        message: str

    state: ops.framework.StoredState
    _WP_CONFIG_PATH: str
    _CONTAINER_NAME: str
    _SERVICE_NAME: str
    _WORDPRESS_USER: str
    _WORDPRESS_GROUP: str
    _WORDPRESS_DB_CHARSET: str

    _DB_CHECK_INTERVAL: Union[float, int]

    _WORDPRESS_DEFAULT_THEMES: List[str]
    _WORDPRESS_DEFAULT_PLUGINS: List[str]

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

    def _run_wp_cli(
            self,
            cmd: List[str],
            timeout: Optional[int] = 60,
            combine_stderr: bool = False
    ) -> WordpressCliExecResult: ...

    def _wrapped_run_wp_cli(
            self,
            cmd: List[str],
            timeout: Optional[int] = 60,
            error_message: Optional[str] = None
    ) -> NoneReturnExecResult: ...

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

    def _check_addon_type(self, addon_type: str) -> None: ...

    def _wp_addon_list(self, addon_type: str) -> WPAddonListExecResult: ...

    def _wp_addon_install(self, addon_type: str, addon_name: str) -> NoneReturnExecResult: ...

    def _wp_addon_uninstall(self, addon_type: str, addon_name: str) -> NoneReturnExecResult: ...

    def _addon_reconciliation(self, addon_type: str) -> None: ...

    def _theme_reconciliation(self) -> None: ...

    def _plugin_reconciliation(self) -> None: ...

    def _core_reconciliation(self) -> None: ...

    def _reconciliation(self, _event: ops.charm.EventBase) -> None: ...
