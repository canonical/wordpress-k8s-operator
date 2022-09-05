import unittest
import unittest.mock

import ops.testing
from charm import WordpressCharm


class TestWordpressK8s(unittest.TestCase):
    def setUp(self):
        self.harness = ops.testing.Harness(WordpressCharm)
        self.addCleanup(self.harness.cleanup)
        self._leadership_data = {}
        self.leadership_patch = unittest.mock.patch.multiple(
            "leadership.LeadershipSettings",
            __getitem__=self._leadership_data.get,
            __setitem__=lambda this, key, value: self._leadership_data.update({key: value}),
            setdefault=self._leadership_data.setdefault
        )
        self.leadership_patch.start()
        self.app_name = "wordpress-k8s"

    def tearDown(self) -> None:
        self.leadership_patch.stop()

    def test_generate_wp_secret_keys(self):
        """
        act: generate a group of WordPress secrets from scratch.
        assert: generated secrets should be safe .
        """
        self.harness.begin()
        secrets = self.harness.charm._generate_wp_secret_keys()
        key_values = list(secrets.values())
        self.assertSetEqual(
            set(secrets.keys()),
            set(self.harness.charm._wordpress_secret_key_fields()),
            "generated wordpress secrets should contain all required fields"
        )
        self.assertEqual(
            len(key_values),
            len(set(key_values)),
            "no two secret values should be the same"
        )
        for value in key_values:
            self.assertFalse(
                value.isalnum() or len(value) < 64,
                "secret values should not be too simple"
            )

    def test_replica_consensus(self):
        """
        arrange: deploy a new wordpress-k8s application
        act: simulate peer relation creating and leader electing during the start of deployment
        assert: units should reach consensus after leader elected
        """
        self.harness.add_relation("wordpress_replica", self.app_name)
        self.harness.set_leader()
        self.harness.begin_with_initial_hooks()
        self.assertTrue(
            self.harness.charm._replica_consensus_reached(),
            "units in application should reach consensus once leadership established"
        )

    def test_replica_consensus_stable_after_leader_reelection(self):
        """
        arrange: deploy a new wordpress-k8s application
        act: simulate a leader re-election after application deployed
        assert: consensus should not change
        """
        replica_relation_id = self.harness.add_relation("wordpress_replica", self.app_name)
        non_leader_peer_name = "wordpress-k8s/1"
        self.harness.add_relation_unit(replica_relation_id, non_leader_peer_name)
        self.harness.begin_with_initial_hooks()
        self.assertFalse(
            self.harness.charm._replica_consensus_reached(),
            "units in application should not reach consensus before leadership established"
        )
        self.harness.set_leader()
        self.assertTrue(
            self.harness.charm._replica_consensus_reached(),
            "units in application should reach consensus once leadership established"
        )
        consensus = self.harness.get_relation_data(replica_relation_id, self.app_name)
        # The harness will emit a leader-elected event when calling ``set_leader(True)`` no matter
        # what the situation is, ``set_leader(False)`` does nothing here currently, just for the
        # aesthetic.
        self.harness.set_leader(False)
        self.harness.set_leader(True)
        self.assertDictEqual(
            consensus,
            self.harness.get_relation_data(replica_relation_id, self.app_name),
            "consensus once established should not change after leadership changed"
        )

    def _setup_db_relation(self, db_info):
        db_relation_id = self.harness.add_relation("db", "mysql")
        self.harness.add_relation_unit(db_relation_id, "mysql/0")
        self.harness.update_relation_data(db_relation_id, "mysql/0", db_info)
        return db_relation_id

    def test_mysql_relation(self):
        """
        act: add and remove the database relation between WordPress application and mysql
        assert: database info in charm state should change accordingly
        """

        def get_db_info_from_state():
            return {
                "host": self.harness.charm.state.relation_db_host,
                "database": self.harness.charm.state.relation_db_name,
                "user": self.harness.charm.state.relation_db_user,
                "password": self.harness.charm.state.relation_db_password
            }

        self.harness.begin_with_initial_hooks()
        self.assertSetEqual(
            {None},
            set(get_db_info_from_state().values()),
            "database info in charm state should not exist before database relation created"
        )

        db_info = {
            "host": "test_database_host",
            "database": "test_database_name",
            "user": "test_database_user",
            "password": "test_database_password",
            "port": "3306",
            "root_password": "test_root_password",
        }
        db_relation_id = self._setup_db_relation(db_info)
        db_info_in_state = get_db_info_from_state()
        for db_info_key in db_info_in_state:
            self.assertEqual(
                db_info_in_state[db_info_key],
                db_info[db_info_key],
                "database info {} in charm state should be updated after database relation changed"
                .format(db_info_key)
            )
        self.harness.remove_relation(db_relation_id)
        db_info_in_state = get_db_info_from_state()
        for db_info_key in db_info_in_state:
            self.assertIsNone(
                db_info_in_state[db_info_key],
                "database info {} should be reset to None after database relation broken"
                .format(db_info_key)
            )
