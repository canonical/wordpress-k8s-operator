#!/usr/bin/env python3

import copy
import mock
import unittest

from unittest.mock import Mock

from charm import WordpressCharm
from wordpress import WORDPRESS_SECRETS
from ops import testing
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
)

from test_wordpress import (
    TEST_MODEL_CONFIG_MINIMAL,
    TEST_MODEL_CONFIG_FULL,
)


class TestWordpressCharm(unittest.TestCase):

    test_model_config = TEST_MODEL_CONFIG_FULL
    test_model_config_minimal = TEST_MODEL_CONFIG_MINIMAL

    def setUp(self):
        self.harness = testing.Harness(WordpressCharm)
        self.addCleanup(self.harness.cleanup)

        self.harness.begin()
        self.harness.update_config(copy.deepcopy(self.test_model_config))

    def test_db_relation(self):
        # Charm starts with no relation, defaulting to using db
        # connection details from the charm config.
        charm = self.harness.charm
        self.assertFalse(charm.state.has_db_relation)
        self.assertEqual(charm.state.db_host, TEST_MODEL_CONFIG_FULL["db_host"])
        self.assertEqual(charm.state.db_name, TEST_MODEL_CONFIG_FULL["db_name"])
        self.assertEqual(charm.state.db_user, TEST_MODEL_CONFIG_FULL["db_user"])
        self.assertEqual(charm.state.db_password, TEST_MODEL_CONFIG_FULL["db_password"])

        # Add a relation and remote unit providing connection details.
        # TODO: ops-lib-mysql should have a helper to set the relation data.
        relid = self.harness.add_relation("db", "mysql")
        self.harness.add_relation_unit(relid, "mysql/0")
        self.harness.update_relation_data(relid, "mysql/0", {
            "database": "wpdbname",
            "host": "hostname.local",
            "port": "3306",
            "user": "wpuser",
            "password": "s3cret",
            "root_password": "sup3r_s3cret",
        })
        # charm.db.on.database_changed fires here and is handled, updating state.
        self.assertTrue(charm.state.has_db_relation)
        self.assertEqual(charm.state.db_host, "hostname.local")
        self.assertEqual(charm.state.db_name, "wpdbname")
        self.assertEqual(charm.state.db_user, "wpuser")
        self.assertEqual(charm.state.db_password, "s3cret")

    def test_is_config_valid(self):
        # Test a valid model config.
        want_true = self.harness.charm.is_valid_config()
        self.assertTrue(want_true)

        # Test for invalid model config.
        want_msg_fmt = "Missing required config or relation: {}"
        want_keys = ["image", "db_host", "db_name", "db_user", "db_password"]
        for wanted_key in want_keys:
            self.harness.update_config({wanted_key: ""})
            want_false = self.harness.charm.is_valid_config()
            self.assertFalse(want_false)
            self.assertLogs(want_msg_fmt.format(wanted_key), level="INFO")
            self.harness.update_config(copy.deepcopy(self.test_model_config))

        # Test for missing initial_settings in model config.
        self.harness.update_config({"initial_settings": ""})
        want_false = self.harness.charm.is_valid_config()
        self.assertFalse(want_false)
        self.assertLogs("No initial_setting provided. Skipping first install.", level="INFO")
        self.harness.update_config(copy.deepcopy(self.test_model_config))

        # Test unit status msg.
        for wanted_key in want_keys:
            self.harness.update_config({wanted_key: ""})
        expected_msg = want_msg_fmt.format(" ".join(want_keys))
        self.harness.charm.is_valid_config()
        self.assertIsInstance(self.harness.charm.unit.status, BlockedStatus)
        self.assertEqual(self.harness.charm.unit.status.message, expected_msg)
        self.assertLogs(expected_msg, level="INFO")
        self.harness.update_config(copy.deepcopy(self.test_model_config))

        # Test for empty additional hostnames string.
        self.harness.update_config({"additional_hostnames": ""})
        want_true = self.harness.charm.is_valid_config()
        self.assertTrue(want_true)

        # Test for invalid additional hostnames.
        invalid_additional_hostnames = "forgot-my-tld invalid+character.com"
        expected_msg = "Invalid additional hostnames supplied: {}".format(invalid_additional_hostnames)
        self.harness.update_config({"additional_hostnames": invalid_additional_hostnames})
        self.harness.charm.is_valid_config()
        self.assertIsInstance(self.harness.charm.unit.status, BlockedStatus)
        self.assertEqual(self.harness.charm.unit.status.message, expected_msg)
        self.assertLogs(expected_msg, level="INFO")

    def test_get_wordpress_secrets(self):
        # Set leader_data to an empty dict to avoid subsequent calls to
        # `leader-get` and `leader-set` in this test.
        self.harness.charm.leader_data = {}
        wp_secrets = self.harness.charm._get_wordpress_secrets()
        for key in WORDPRESS_SECRETS:
            self.assertIsInstance(wp_secrets[key], str)
            self.assertEqual(len(wp_secrets[key]), 64)

    def test_make_pod_resources(self):
        self.harness.update_config({
            "blog_hostname": "blog.example.com",
            "tls_secret_name": "blog-example-com-tls"
        })
        # Test for https://bugs.launchpad.net/juju/+bug/1884674
        ingress_name = 'wordpress-k8s-ingress'
        self.assertNotEqual(ingress_name, self.harness.charm.app.name)

        expected = {
            'kubernetesResources': {
                'ingressResources': [
                    {
                        "annotations": {
                            "nginx.ingress.kubernetes.io/proxy-body-size": "10m",
                            "nginx.ingress.kubernetes.io/proxy-send-timeout": "300s",
                        },
                        'name': ingress_name,
                        'spec': {
                            'rules': [
                                {
                                    'host': 'blog.example.com',
                                    'http': {
                                        'paths': [
                                            {
                                                'path': '/',
                                                'backend': {'serviceName': 'wordpress-k8s', 'servicePort': 80},
                                            }
                                        ]
                                    },
                                },
                                {
                                    'host': 'cool-newsite.org',
                                    'http': {
                                        'paths': [
                                            {
                                                'path': '/',
                                                'backend': {'serviceName': 'wordpress-k8s', 'servicePort': 80},
                                            }
                                        ]
                                    },
                                },
                                {
                                    'host': 'blog.test.com',
                                    'http': {
                                        'paths': [
                                            {
                                                'path': '/',
                                                'backend': {'serviceName': 'wordpress-k8s', 'servicePort': 80},
                                            }
                                        ]
                                    },
                                }
                            ],
                            'tls': [{'hosts': ['blog.example.com'], 'secretName': 'blog-example-com-tls'}],
                        },
                    }
                ]
            }
        }
        self.assertEqual(self.harness.charm.make_pod_resources(), expected)

        # And now test with minimal config.
        self.harness.update_config(self.test_model_config_minimal)
        expected = {
            'kubernetesResources': {
                'ingressResources': [
                    {
                        "annotations": {
                            "nginx.ingress.kubernetes.io/proxy-body-size": "10m",
                            "nginx.ingress.kubernetes.io/proxy-send-timeout": "300s",
                            "nginx.ingress.kubernetes.io/ssl-redirect": "false",
                        },
                        'name': ingress_name,
                        'spec': {
                            'rules': [
                                {
                                    'host': 'blog.example.com',
                                    'http': {
                                        'paths': [
                                            {
                                                'path': '/',
                                                'backend': {'serviceName': 'wordpress-k8s', 'servicePort': 80},
                                            }
                                        ]
                                    },
                                },
                            ],
                        },
                    }
                ]
            }
        }
        self.assertEqual(self.harness.charm.make_pod_resources(), expected)

    def test_make_pod_spec(self):
        expected = {
            'version': 2,
            'containers': [{
                'config': {
                    'SWIFT_AUTH_URL': 'auth-url',
                    'SWIFT_BUCKET': 'bucket',
                    'SWIFT_COPY_TO_SWIFT': None,
                    'SWIFT_PASSWORD': 'password',
                    'SWIFT_PREFIX': None,
                    'SWIFT_REGION': None,
                    'SWIFT_REMOVE_LOCAL_FILE': None,
                    'SWIFT_SERVE_FROM_SWIFT': None,
                    'SWIFT_TENANT': None,
                    'SWIFT_URL': None,
                    'SWIFT_USERNAME': None,
                    'WORDPRESS_DB_HOST': '10.215.74.139',
                    'WORDPRESS_DB_NAME': 'wordpress',
                    'WORDPRESS_DB_PASSWORD': 'letmein123',
                    'WORDPRESS_DB_USER': 'admin',
                    'WP_PLUGIN_AKISMET_KEY': 'somerandomstring',
                    'WP_PLUGIN_OPENID_TEAM_MAP': True,
                    'test-key': 'test'
                },
                'imageDetails': {
                    'imagePath': 'testimageregistry/wordpress:bionic-latest',
                    'password': 'dontleakme',
                    'username': 'test-image-user'
                },
                'kubernetes': {
                    'readinessProbe': {
                        'exec': {'command': ['/srv/wordpress-helpers/ready.sh']}
                    }
                },
                'name': 'wordpress-k8s',
                'ports': [{
                    'containerPort': 80,
                    'name': 'http',
                    'protocol': 'TCP',
                }]}
            ],
        }
        self.harness.charm.leader_data = {}
        actual = self.harness.charm.make_pod_spec()
        # Remove values that are auto-generated so hard to test.
        for secret in WORDPRESS_SECRETS:
            del actual["containers"][0]["config"][secret]
        self.assertEqual(actual, expected)

        # And now test with minimal config.
        self.harness.update_config(self.test_model_config_minimal, unset=['image_user', 'image_pass',
                                                                          'wp_plugin_akismet_key'])
        expected = {
            'version': 2,
            'containers': [{
                'config': {
                    'SWIFT_AUTH_URL': 'auth-url',
                    'SWIFT_BUCKET': 'bucket',
                    'SWIFT_COPY_TO_SWIFT': None,
                    'SWIFT_PASSWORD': 'password',
                    'SWIFT_PREFIX': None,
                    'SWIFT_REGION': None,
                    'SWIFT_REMOVE_LOCAL_FILE': None,
                    'SWIFT_SERVE_FROM_SWIFT': None,
                    'SWIFT_TENANT': None,
                    'SWIFT_URL': None,
                    'SWIFT_USERNAME': None,
                    'WORDPRESS_DB_HOST': '10.215.74.139',
                    'WORDPRESS_DB_NAME': 'wordpress',
                    'WORDPRESS_DB_PASSWORD': 'letmein123',
                    'WORDPRESS_DB_USER': 'admin',
                    'WORDPRESS_TLS_DISABLED': 'true',
                },
                'imageDetails': {
                    'imagePath': 'testimageregistry/wordpress:bionic-latest',
                },
                'kubernetes': {
                    'readinessProbe': {
                        'exec': {'command': ['/srv/wordpress-helpers/ready.sh']}
                    }
                },
                'name': 'wordpress-k8s',
                'ports': [{
                    'containerPort': 80,
                    'name': 'http',
                    'protocol': 'TCP',
                }]}
            ],
        }
        self.harness.charm.leader_data = {}
        actual = self.harness.charm.make_pod_spec()
        # Remove values that are auto-generated so hard to test.
        for secret in WORDPRESS_SECRETS:
            del actual["containers"][0]["config"][secret]
        self.assertEqual(actual, expected)

    def test_get_initial_password(self):
        self.harness.charm.leader_data = {"initial_password": "supersekrit"}
        self.assertEqual(self.harness.charm._get_initial_password(), "supersekrit")
        # Now test with no password, but not leader.
        self.harness.charm.leader_data = {"initial_password": ""}
        self.harness.set_leader(False)
        self.assertEqual(self.harness.charm._get_initial_password(), "")
        # And with no password, but is leader.
        self.harness.charm.leader_data = {"initial_password": ""}
        self.harness.set_leader(True)
        self.assertEqual(len(self.harness.charm._get_initial_password()), 24)

    def test_on_get_initial_password_action(self):
        action_event = Mock()
        # First test with no initial password set.
        with mock.patch.object(self.harness.charm, "_get_initial_password") as get_initial_password:
            get_initial_password.return_value = ""
            self.harness.charm._on_get_initial_password_action(action_event)
            self.assertEqual(action_event.fail.call_args, mock.call("Initial password has not been set yet."))
        # Now test with initial password set.
        with mock.patch.object(self.harness.charm, "_get_initial_password") as get_initial_password:
            get_initial_password.return_value = "passwd"
            self.harness.charm._on_get_initial_password_action(action_event)
            self.assertEqual(action_event.set_results.call_args, mock.call({"password": "passwd"}))

    def test_configure_pod(self):
        # Set leader_data to an empty dict to avoid subsequent calls to
        # `leader-get` and `leader-set` in this test.
        self.harness.charm.leader_data = {}
        # First of all, test with leader set, but not initialised.
        self.harness.set_leader(True)
        self.assertEqual(self.harness.charm.state.initialised, False)
        self.harness.charm.configure_pod()
        expected_msg = "Pod configured, but WordPress configuration pending"
        self.assertEqual(self.harness.charm.unit.status.message, expected_msg)
        self.assertLogs(expected_msg, level="INFO")
        self.assertIsInstance(self.harness.charm.unit.status, MaintenanceStatus)
        # Now with state initialised.
        self.harness.charm.state.initialised = True
        self.harness.charm.configure_pod()
        expected_msg = "Pod configured"
        self.assertEqual(self.harness.charm.unit.status.message, expected_msg)
        self.assertLogs(expected_msg, level="INFO")
        self.assertIsInstance(self.harness.charm.unit.status, ActiveStatus)
        # And now test with non-leader.
        self.harness.set_leader(False)
        self.harness.charm.configure_pod()
        expected_msg = "Spec changes ignored by non-leader"
        self.assertLogs(expected_msg, level="INFO")
