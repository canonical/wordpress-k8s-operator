#!/usr/bin/env python3

import re
import secrets
import subprocess
import string
import sys
from urllib.parse import urlparse, urlunparse
from yaml import safe_load

sys.path.append("lib")

from ops.charm import CharmBase, CharmEvents  # NoQA: E402
from ops.framework import EventBase, EventSource, StoredState  # NoQA: E402
from ops.main import main  # NoQA: E402
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus  # NoQA: E402

import logging  # NoQA: E402

logger = logging.getLogger()


def password_generator():
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(8))


class WordpressInitialiseEvent(EventBase):
    pass


class WordpressCharmEvents(CharmEvents):
    wp_initialise = EventSource(WordpressInitialiseEvent)


class WordpressK8sCharm(CharmBase):
    state = StoredState()
    on = WordpressCharmEvents()

    def __init__(self, *args):
        super().__init__(*args)
        for event in (
            self.on.start,
            self.on.config_changed,
            self.on.wp_initialise,
        ):
            self.framework.observe(event, self)

        self.state.set_default(_init=True)
        self.state.set_default(_started=False)
        self.state.set_default(_valid=False)
        self.state.set_default(_configured=False)

    def on_start(self, event):
        self.state._started = True

    def on_config_changed(self, event):
        if not self.state._valid:
            config = self.model.config
            want = ("image", "db_host", "db_name", "db_user", "db_password")
            missing = [k for k in want if config[k].rstrip() == ""]
            if missing:
                message = " ".join(missing)
                logger.info("Missing required config: {}".format(message))
                self.model.unit.status = BlockedStatus("{} config is required".format(message))
                event.defer()
                return

            self.state._valid = True

        if not self.state._configured:
            logger.info("Configuring pod")
            return self.configure_pod()

        if self.model.unit.is_leader() and self.state._init:
            self.on.wp_initialise.emit()

    def on_wp_initialise(self, event):
        if not self.state._init:
            return

        ready = self.install_ready()
        if not ready:
            # Until k8s supports telling Juju our pod is available we need to defer initial
            # site setup for a subsequent update-status or config-changed hook to complete.
            self.model.unit.status = WaitingStatus("Waiting for pod to be ready")
            event.defer()
            return

        installed = self.first_install()
        if not installed:
            event.defer()
            return

        logger.info("Wordpress installed and initialised")
        self.state._init = False

    def configure_pod(self):
        # only the leader can set_spec()
        if self.model.unit.is_leader():
            spec = self.make_pod_spec()
            self.model.unit.status = MaintenanceStatus("Configuring container")
            self.model.pod.set_spec(spec)
            self.state._configured = True

    def make_pod_spec(self):
        config = self.model.config
        container_config = self.sanitized_container_config()
        if container_config is None:
            return  # Status already set

        ports = [
            {"name": name, "containerPort": int(port), "protocol": "TCP"}
            for name, port in [addr.split(":", 1) for addr in config["ports"].split()]
        ]

        # PodSpec v1? https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.13/#podspec-v1-core
        spec = {
            "containers": [
                {
                    "name": self.app.name,
                    "imageDetails": {"imagePath": config["image"]},
                    "ports": ports,
                    "config": container_config,
                    "readinessProbe": {"exec": {"command": ["/bin/cat", "/srv/wordpress-helpers/.ready"]}},
                }
            ]
        }

        # If we need credentials (secrets) for our image, add them to the spec after logging
        if config.get("image_user") and config.get("image_pass"):
            spec.get("containers")[0].get("imageDetails")["username"] = config["image_user"]
            spec.get("containers")[0].get("imageDetails")["password"] = config["image_pass"]

        config_with_secrets = self.full_container_config()
        if config_with_secrets is None:
            return None  # Status already set
        container_config.update(config_with_secrets)

        return spec

    def sanitized_container_config(self):
        """Container config without secrets"""
        config = self.model.config
        if config["container_config"].strip() == "":
            container_config = {}
        else:
            container_config = safe_load(config["container_config"])
            if not isinstance(container_config, dict):
                self.model.unit.status = BlockedStatus("container_config is not a YAML mapping")
                return None
        container_config["WORDPRESS_DB_HOST"] = config["db_host"]
        container_config["WORDPRESS_DB_NAME"] = config["db_name"]
        container_config["WORDPRESS_DB_USER"] = config["db_user"]
        if config.get("wp_plugin_openid_team_map"):
            container_config["WP_PLUGIN_OPENID_TEAM_MAP"] = config["wp_plugin_openid_team_map"]
        return container_config

    def full_container_config(self):
        """Container config with secrets"""
        config = self.model.config
        container_config = self.sanitized_container_config()
        if container_config is None:
            return None
        if config["container_secrets"].strip() == "":
            container_secrets = {}
        else:
            container_secrets = safe_load(config["container_secrets"])
            if not isinstance(container_secrets, dict):
                self.model.unit.status = BlockedStatus("container_secrets is not a YAML mapping")
                return None
        container_config.update(container_secrets)
        # Add secrets from charm config
        container_config["WORDPRESS_DB_PASSWORD"] = config["db_password"]
        if config.get("wp_plugin_akismet_key"):
            container_config["WP_PLUGIN_AKISMET_KEY"] = config["wp_plugin_akismet_key"]
        return container_config

    def install_ready(self):
        ready = True
        config = self.model.config
        if not self.is_pod_up("website"):
            logger.info("Pod not yet ready - retrying")
            ready = False

        try:
            if not self.is_vhost_ready():
                ready = False
        except Exception as e:
            logger.info("Wordpress vhost is not yet listening - retrying: {}".format(e))
            ready = False

        if not config["initial_settings"]:
            logger.info("No initial_setting provided or wordpress already configured. Skipping first install.")
            logger.info("{} {}".format(self.state._configured, config["initial_settings"]))
            ready = False

        return ready

    def first_install(self):
        """Perform initial configuration of wordpress if needed."""
        config = self.model.config
        logger.info("Starting wordpress initial configuration")
        admin_password = password_generator()
        payload = {
            "admin_password": admin_password,
            "blog_public": "checked",
            "Submit": "submit",
        }
        payload.update(safe_load(config["initial_settings"]))
        payload["admin_password2"] = payload["admin_password"]

        with open("/root/initial.passwd", "w") as f:
            f.write(payload["admin_password"])

        if not payload["blog_public"]:
            payload["blog_public"] = "unchecked"
        required_config = set(("user_name", "admin_email"))
        missing = required_config.difference(payload.keys())
        if missing:
            logger.info("Error: missing wordpress settings: {}".format(missing))
            return
        try:
            self.call_wordpress("/wp-admin/install.php?step=2", redirects=True, payload=payload)
        except Exception as e:
            logger.info("failed to call_wordpress: {}".format(e))
            return

        if not self.wordpress_configured():
            self.model.unit.status = BlockedStatus("Failed to install wordpress")

        self.model.unit.status = ActiveStatus()
        return True

    def call_wordpress(self, uri, redirects=True, payload={}, _depth=1):
        try:
            import requests
        except ImportError:
            subprocess.check_call(['apt-get', 'update'])
            subprocess.check_call(['apt-get', '-y', 'install', 'python3-requests'])
            import requests

        max_depth = 10
        if _depth > max_depth:
            logger.info("Redirect loop detected in call_worpress()")
            raise RuntimeError("Redirect loop detected in call_worpress()")
        config = self.model.config
        service_ip = self.get_service_ip("website")
        if service_ip:
            headers = {"Host": config["blog_hostname"]}
            url = urlunparse(("http", service_ip, uri, "", "", ""))
            if payload:
                r = requests.post(url, allow_redirects=False, headers=headers, data=payload, timeout=30)
            else:
                r = requests.get(url, allow_redirects=False, headers=headers, timeout=30)
            if redirects and r.is_redirect:
                # Recurse, but strip the scheme and host first, we need to connect over HTTP by bare IP
                o = urlparse(r.headers.get("Location"))
                return self.call_wordpress(o.path, redirects=redirects, payload=payload, _depth=_depth + 1)
            else:
                return r
        else:
            logger.info("Error getting service IP")
            return False

    def wordpress_configured(self):
        """Check whether first install has been completed."""
        try:
            import requests
        except ImportError:
            subprocess.check_call(['apt-get', 'update'])
            subprocess.check_call(['apt-get', '-y', 'install', 'python3-requests'])
            import requests

        # Check whether pod is deployed
        if not self.is_pod_up("website"):
            return False
        # Check if we have WP code deployed at all
        if not self.is_vhost_ready():
            return False
        # We have code on disk, check if configured
        try:
            r = self.call_wordpress("/", redirects=False)
        except requests.exceptions.ConnectionError:
            return False

        if r.status_code == 302 and re.match("^.*/wp-admin/install.php", r.headers.get("location", "")):
            return False
        elif r.status_code == 302 and re.match("^.*/wp-admin/setup-config.php", r.headers.get("location", "")):
            logger.info("MySQL database setup failed, we likely have no wp-config.php")
            self.model.unit.status = BlockedStatus("MySQL database setup failed, we likely have no wp-config.php")
            return False
        else:
            return True

    def is_vhost_ready(self):
        """Check whether wordpress is available using http."""
        try:
            import requests
        except ImportError:
            subprocess.check_call(['apt-get', 'update'])
            subprocess.check_call(['apt-get', '-y', 'install', 'python3-requests'])
            import requests

        rv = True
        # Check if we have WP code deployed at all
        try:
            r = self.call_wordpress("/wp-login.php", redirects=False)
            if r is None:
                logger.error("call_wordpress() returned None")
                rv = False
            if hasattr(r, "status_code") and r.status_code in (403, 404):
                logger.info("Wordpress returned an unexpected status {}".format(r.status_code))
                rv = False
        except requests.exceptions.ConnectionError:
            logger.info("Apache vhost is not ready yet")
            rv = False

        return rv

    def get_service_ip(self, endpoint):
        try:
            return str(self.model.get_binding(endpoint).network.ingress_addresses[0])
        except Exception:
            logger.info("We don't have any ingress addresses yet")

    def is_pod_up(self, endpoint):
        """Check to see if the pod of a relation is up"""
        return self.get_service_ip(endpoint) or False


if __name__ == "__main__":
    main(WordpressK8sCharm)
