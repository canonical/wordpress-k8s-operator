from typing import List, Dict
import ops
import ops.framework
import opslib.mysql


class WordpressCharm(ops.charm.CharmBase):
    state: ops.framework.StoredState

    @staticmethod
    def _wordpress_secret_key_fields() -> List[str]: ...

    def _generate_wp_secret_keys(self) -> Dict[str, str]: ...

    def _replica_relation_data(self) -> ops.charm.model.RelationDataContent: ...

    def _replica_consensus_reached(self) -> bool: ...

    def _on_leader_elected_replica_data_handler(self, event: ops.charm.LeaderElectedEvent): ...

    def _on_relation_database_changed(
            self,
            event: opslib.mysql.MySQLDatabaseChangedEvent
    ): ...

    def _gen_wp_config(self) -> str: ...