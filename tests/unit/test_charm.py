#!/usr/bin/env python3

import copy
import mock
import unittest

from unittest.mock import Mock

from charm import WordpressCharm
from wordpress import WORDPRESS_SECRETS
from ops import testing
from ops.model import BlockedStatus

from test_wordpress import TEST_MODEL_CONFIG


class TestWordpressCharm(unittest.TestCase):

    test_model_config = TEST_MODEL_CONFIG

    def setUp(self):
        self.harness = testing.Harness(WordpressCharm)

        self.harness.begin()
        self.harness.update_config(copy.deepcopy(self.test_model_config))

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

    def test_get_wordpress_secrets(self):
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
        ingress_name = 'wordpress-ingress'
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
                                                'backend': {'serviceName': 'wordpress', 'servicePort': 80},
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
        # And now test with no tls config.
        self.harness.update_config({"tls_secret_name": ""})
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
                                                'backend': {'serviceName': 'wordpress', 'servicePort': 80},
                                            }
                                        ]
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        }
        self.assertEqual(self.harness.charm.make_pod_resources(), expected)

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
