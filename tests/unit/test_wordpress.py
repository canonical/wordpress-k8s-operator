import copy
import string
import sys
import unittest
import yaml

sys.path.append("src")

import charm  # noqa: E402


TEST_MODEL_CONFIG = {
    "image": "testimageregistry/wordpress:bionic-latest",
    "image_user": "test-image-user",
    "image_pass": "dontleakme",
    "db_host": "10.215.74.139",
    "db_name": "wordpress",
    "db_user": "admin",
    "db_password": "letmein123",
    "wp_plugin_openid_team_map": True,
    "wp_plugin_akismet_key": "somerandomstring",
    "container_config": "test-key: test",
    "initial_settings": """\
    user_name: admin
    admin_email: root@admin.canonical.com
    weblog_title: Test Blog
    blog_public: False""",
}


class HelperTest(unittest.TestCase):

    test_model_config = TEST_MODEL_CONFIG

    def test_password_generator(self):
        password = charm.password_generator()
        self.assertEqual(len(password), 24)
        alphabet = string.ascii_letters + string.digits
        for char in password:
            self.assertTrue(char in alphabet)

    def test_generate_pod_config(self):
        # Ensure that secrets are stripped from config.
        result = charm.generate_pod_config(self.test_model_config, secured=True)
        secured_keys = ("WORDPRESS_DB_PASSWORD", "WP_PLUGIN_AKISMET_KEY")
        [self.assertNotIn(key, result) for key in secured_keys]
        self.assertIn("WP_PLUGIN_OPENID_TEAM_MAP", result)

        # Ensure that we receive the full pod config.
        result = charm.generate_pod_config(self.test_model_config, secured=False)
        [self.assertIn(key, result) for key in secured_keys]
        self.assertIn("WP_PLUGIN_AKISMET_KEY", result)

        # Test we don't break with missing non-essential config options.
        non_essential_model_config = copy.deepcopy(self.test_model_config)
        del non_essential_model_config["wp_plugin_openid_team_map"]
        del non_essential_model_config["wp_plugin_akismet_key"]
        result = charm.generate_pod_config(self.test_model_config, secured=False)
        self.assertTrue(result)

        # Test for initial container config.
        result = charm.generate_pod_config(self.test_model_config)
        test_container_config = yaml.safe_load(self.test_model_config["container_config"])
        self.assertEqual(test_container_config["test-key"], result["test-key"])
