#!/usr/bin/env python3

import logging
import re
import secrets
import string
import subprocess
from urllib.parse import urlparse, urlunparse
from yaml import safe_load

logger = logging.getLogger()


WORDPRESS_SECRETS = [
    "AUTH_KEY",
    "SECURE_AUTH_KEY",
    "LOGGED_IN_KEY",
    "NONCE_KEY",
    "AUTH_SALT",
    "SECURE_AUTH_SALT",
    "LOGGED_IN_SALT",
    "NONCE_SALT",
]


def import_requests():
    # Workaround until https://github.com/canonical/operator/issues/156 is fixed.
    try:
        import requests
    except ImportError:
        subprocess.check_call(['apt-get', 'update'])
        subprocess.check_call(['apt-get', '-y', 'install', 'python3-requests'])
        import requests

    return requests


def password_generator(length=24):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(length))


class Wordpress:
    def __init__(self, model_config):
        self.model_config = model_config

    def _write_initial_password(self, password, filepath):
        with open(filepath, "w") as f:
            f.write(password)

    def first_install(self, service_ip):
        """Perform initial configuration of wordpress if needed."""
        config = self.model_config
        logger.info("Starting wordpress initial configuration")
        admin_password = password_generator()
        payload = {
            "admin_password": admin_password,
            "blog_public": "checked",
            "Submit": "submit",
        }
        payload.update(safe_load(config["initial_settings"]))
        payload["admin_password2"] = payload["admin_password"]

        # Ideally we would store this in state however juju run-action does not
        # currently support being run inside the operator pod which means the
        # StorageState will be split between workload and operator.
        # https://bugs.launchpad.net/juju/+bug/1870487
        self._write_initial_password(payload["admin_password"], "/root/initial.passwd")

        if not payload["blog_public"]:
            payload["blog_public"] = "unchecked"
        required_config = set(("user_name", "admin_email"))
        missing = required_config.difference(payload.keys())
        if missing:
            logger.info("Error: missing wordpress settings: {}".format(missing))
            return False
        try:
            self.call_wordpress(service_ip, "/wp-admin/install.php?step=2", redirects=True, payload=payload)
        except Exception as e:
            logger.info("failed to call_wordpress: {}".format(e))
            return False

        if not self.wordpress_configured(service_ip):
            return False

        return True

    def call_wordpress(self, service_ip, uri, redirects=True, payload={}, _depth=1):
        requests = import_requests()

        max_depth = 10
        if _depth > max_depth:
            logger.info("Redirect loop detected in call_worpress()")
            raise RuntimeError("Redirect loop detected in call_worpress()")
        config = self.model_config
        headers = {"Host": config["blog_hostname"]}
        url = urlunparse(("http", service_ip, uri, "", "", ""))
        if payload:
            r = requests.post(url, allow_redirects=False, headers=headers, data=payload, timeout=30)
        else:
            r = requests.get(url, allow_redirects=False, headers=headers, timeout=30)
        if redirects and r.is_redirect:
            # Recurse, but strip the scheme and host first, we need to connect over HTTP by bare IP
            o = urlparse(r.headers.get("Location"))
            return self.call_wordpress(service_ip, o.path, redirects=redirects, payload=payload, _depth=_depth + 1)
        else:
            return r

    def wordpress_configured(self, service_ip):
        """Check whether first install has been completed."""
        requests = import_requests()

        # We have code on disk, check if configured
        try:
            r = self.call_wordpress(service_ip, "/", redirects=False)
        except requests.exceptions.ConnectionError:
            return False

        if r.status_code == 302 and re.match("^.*/wp-admin/install.php", r.headers.get("location", "")):
            return False
        elif r.status_code == 302 and re.match("^.*/wp-admin/setup-config.php", r.headers.get("location", "")):
            logger.info("MySQL database setup failed, we likely have no wp-config.php")
            return False
        elif r.status_code in (500, 403, 404):
            raise RuntimeError("unexpected status_code returned from Wordpress")

        return True

    def is_vhost_ready(self, service_ip):
        """Check whether wordpress is available using http."""
        requests = import_requests()

        # Check if we have WP code deployed at all
        try:
            r = self.call_wordpress(service_ip, "/wp-login.php", redirects=False)
            if r is None:
                logger.error("call_wordpress() returned None")
                return False
            if hasattr(r, "status_code") and r.status_code in (403, 404):
                logger.info("Wordpress returned an unexpected status {}".format(r.status_code))
                return False
        except requests.exceptions.ConnectionError:
            logger.info("HTTP vhost is not ready yet")
            return False

        return True
