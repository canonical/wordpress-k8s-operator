import copy
import mock
import requests
import string
import sys
import unittest
import yaml

sys.path.append("src")

import charm  # noqa: E402
import wordpress  # noqa: E402


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


TEST_GENERATED_PASSWORD = "realsecure"


def dummy_password_generator():
    return TEST_GENERATED_PASSWORD


class RequestsResult:

    status_code = 0
    headers = {}

    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        if headers:
            self.headers["location"] = headers


class HelperTest(unittest.TestCase):

    test_model_config = TEST_MODEL_CONFIG

    def test_password_generator(self):
        password = wordpress.password_generator()
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


class WordpressTest(unittest.TestCase):

    test_model_config = TEST_MODEL_CONFIG

    def setUp(self):
        self.test_wordpress = wordpress.Wordpress(copy.deepcopy(self.test_model_config))
        self.test_service_ip = "1.1.1.1"

    def test__init__(self):
        self.assertEqual(self.test_wordpress.model_config, self.test_model_config)

    @mock.patch("wordpress.password_generator", side_effect=dummy_password_generator)
    def test_first_install(self, password_generator_func):
        mocked_call_wordpress = mock.MagicMock(name="call_wordpress", return_value=True)
        mocked__write_initial_password = mock.MagicMock(name="_write_initial_password", return_value=None)
        mocked_wordpress_configured = mock.MagicMock(name="wordpress_configured", return_value=True)
        self.test_wordpress.call_wordpress = mocked_call_wordpress
        self.test_wordpress._write_initial_password = mocked__write_initial_password
        self.test_wordpress.wordpress_configured = mocked_wordpress_configured

        test_payload = {
            'admin_password': TEST_GENERATED_PASSWORD,
            'admin_password2': TEST_GENERATED_PASSWORD,
            'blog_public': 'unchecked',
            'Submit': 'submit',
            'user_name': 'admin',
            'admin_email': 'root@admin.canonical.com',
            'weblog_title': 'Test Blog',
        }
        self.test_wordpress.first_install(self.test_service_ip)

        # Test that we wrote initial admin credentials inside the operator pod.
        self.test_wordpress._write_initial_password.assert_called_with(TEST_GENERATED_PASSWORD, "/root/initial.passwd")

        # Test that we POST'd our initial configuration options to the wordpress API.
        self.test_wordpress.call_wordpress.assert_called_with(
            self.test_service_ip, "/wp-admin/install.php?step=2", redirects=True, payload=test_payload
        )

        # Test that we don't call the Wordpress API with missing (admin_email) initial settings.
        mocked_call_wordpress = mock.MagicMock(name="call_wordpress", return_value=True)
        self.test_wordpress.call_wordpress = mocked_call_wordpress
        self.test_wordpress.model_config["initial_settings"] = (
            "user_name: admin\n" "weblog_title: Test Blog\n" "blog_public: False"
        )
        self.test_wordpress.first_install(self.test_service_ip)
        self.test_wordpress.call_wordpress.assert_not_called()

    def test_wordpress_configured(self):
        # Test install successful.
        success = RequestsResult(200)
        mocked_call_wordpress = mock.MagicMock(name="call_wordpress", return_value=success)
        self.test_wordpress.call_wordpress = mocked_call_wordpress
        self.test_wordpress.wordpress_configured(self.test_service_ip)
        self.test_wordpress.call_wordpress.assert_called_with(self.test_service_ip, "/", redirects=False)

        # Test install failed.
        for uri in ("/wp-admin/install.php", "/wp-admin/setup-config.php"):
            failure = RequestsResult(302, uri)
            mocked_call_wordpress = mock.MagicMock(name="call_wordpress", return_value=failure)
            self.test_wordpress.call_wordpress = mocked_call_wordpress
            rv = self.test_wordpress.wordpress_configured(self.test_service_ip)
            self.assertFalse(rv)

        # Test unexpected status code from webserver.
        for sc in (500, 403, 404):
            failure = RequestsResult(sc)
            mocked_call_wordpress = mock.MagicMock(name="call_wordpress", return_value=failure)
            self.test_wordpress.call_wordpress = mocked_call_wordpress
            with self.assertRaises(RuntimeError, msg="unexpected status_code returned from Wordpress"):
                self.test_wordpress.wordpress_configured(self.test_service_ip)

    def test_is_vhost_ready(self):
        # Test vhost not ready yet and called with expected args.
        mocked_call_wordpress = mock.MagicMock(name="call_wordpress", return_value=None)
        self.test_wordpress.call_wordpress = mocked_call_wordpress
        rv = self.test_wordpress.is_vhost_ready(self.test_service_ip)
        self.assertFalse(rv)
        self.test_wordpress.call_wordpress.assert_called_with(self.test_service_ip, "/wp-login.php", redirects=False)

        # Test vhost ready and has unexpected status_code
        failure = RequestsResult(403)
        mocked_call_wordpress = mock.MagicMock(name="call_wordpress", return_value=failure)
        self.test_wordpress.call_wordpress = mocked_call_wordpress
        rv = self.test_wordpress.is_vhost_ready(self.test_service_ip)
        self.assertFalse(rv)

        # Test vhost isn't up yet.
        mocked_call_wordpress = mock.MagicMock(name="call_wordpress", side_effect=requests.exceptions.ConnectionError)
        self.test_wordpress.call_wordpress = mocked_call_wordpress
        rv = self.test_wordpress.is_vhost_ready(self.test_service_ip)
        self.assertFalse(rv)

        # Test vhost is ready.
        mocked_call_wordpress = mock.MagicMock(name="call_wordpress", return_value=True)
        self.test_wordpress.call_wordpress = mocked_call_wordpress
        rv = self.test_wordpress.is_vhost_ready(self.test_service_ip)
        self.assertTrue(rv)
