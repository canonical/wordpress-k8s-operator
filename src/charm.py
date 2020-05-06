#!/usr/bin/env python3

import io
import logging
import sys
from pprint import pprint
from yaml import safe_load

from wordpress import Wordpress

sys.path.append("lib")

from ops.charm import CharmBase, CharmEvents  # NoQA: E402
from ops.framework import EventBase, EventSource, StoredState  # NoQA: E402
from ops.main import main  # NoQA: E402
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus  # NoQA: E402

logger = logging.getLogger()


def generate_pod_config(config, secured=True):
    """Kubernetes pod config generator.

    generate_pod_config generates Kubernetes deployment config.
    If the secured keyword is set then it will return a sanitised copy
    without exposing secrets.
    """
    pod_config = {}
    if config["container_config"].strip():
        pod_config = safe_load(config["container_config"])

    pod_config["WORDPRESS_DB_HOST"] = config["db_host"]
    pod_config["WORDPRESS_DB_NAME"] = config["db_name"]
    pod_config["WORDPRESS_DB_USER"] = config["db_user"]
    if config.get("wp_plugin_openid_team_map"):
        pod_config["WP_PLUGIN_OPENID_TEAM_MAP"] = config["wp_plugin_openid_team_map"]

    if secured:
        return pod_config

    # Add secrets from charm config
    pod_config["WORDPRESS_DB_PASSWORD"] = config["db_password"]
    if config.get("wp_plugin_akismet_key"):
        pod_config["WP_PLUGIN_AKISMET_KEY"] = config["wp_plugin_akismet_key"]
    if config.get("wp_plugin_openstack-objectstorage_config"):
        # actual plugin name is 'openstack-objectstorage', but 'swift' will do us!
        wp_plugin_swift_config = config.get("wp_plugin_openstack-objectstorage_config")
        pod_config["SWIFT_AUTH_URL"] = wp_plugin_swift_config.get('auth-url')
        pod_config["SWIFT_BUCKET"] = wp_plugin_swift_config.get('bucket')
        pod_config["SWIFT_PASSWORD"] = wp_plugin_swift_config.get('password')
        pod_config["SWIFT_PREFIX"] = wp_plugin_swift_config.get('prefix')
        pod_config["SWIFT_REGION"] = wp_plugin_swift_config.get('region')
        pod_config["SWIFT_TENANT"] = wp_plugin_swift_config.get('tenant')
        pod_config["SWIFT_URL"] = wp_plugin_swift_config.get('url')
        pod_config["SWIFT_USERNAME"] = wp_plugin_swift_config.get('username')
        pod_config["SWIFT_COPY_TO_SWIFT"] = wp_plugin_swift_config.get('copy-to-swift')
        pod_config["SWIFT_SERVE_FROM_SWIFT"] = wp_plugin_swift_config.get('serve-from-swift')
        pod_config["SWIFT_REMOVE_LOCAL_FILE"] = wp_plugin_swift_config.get('remove-local-file')

    return pod_config


class WordpressInitialiseEvent(EventBase):
    """Custom event for signalling Wordpress initialisation.

    WordpressInitialiseEvent allows us to signal the handler for
    the initial Wordpress setup logic.
    """

    pass


class WordpressCharmEvents(CharmEvents):
    """Register custom charm events.

    WordpressCharmEvents registeres the custom WordpressInitialiseEvent
    event to the charm.
    """

    wordpress_initialise = EventSource(WordpressInitialiseEvent)


class WordpressK8sCharm(CharmBase):
    state = StoredState()
    # Override the default list of event handlers with our WordpressCharmEvents subclass.
    on = WordpressCharmEvents()

    def __init__(self, *args):
        super().__init__(*args)

        self.framework.observe(self.on.start, self.on_config_changed)
        self.framework.observe(self.on.config_changed, self.on_config_changed)
        self.framework.observe(self.on.update_status, self.on_config_changed)
        self.framework.observe(self.on.wordpress_initialise, self.on_wordpress_initialise)

        self.state.set_default(
            initialised=False,
            valid=False,
        )

        self.wordpress = Wordpress(self.model.config)

    def on_config_changed(self, event):
        is_valid = self.is_valid_config()
        if not is_valid:
            return

        self.configure_pod()
        if not self.state.initialised:
            self.on.wordpress_initialise.emit()

    def on_wordpress_initialise(self, event):
        wordpress_needs_configuring = False
        pod_alive = self.model.unit.is_leader() and self.is_service_up()
        if pod_alive:
            wordpress_configured = self.wordpress.wordpress_configured(self.get_service_ip())
            wordpress_needs_configuring = not self.state.initialised and not wordpress_configured
        else:
            msg = "Workpress workload pod is not ready"
            logger.info(msg)
            self.model.unit.status = WaitingStatus(msg)
            return

        if wordpress_needs_configuring:
            msg = "Wordpress needs configuration"
            logger.info(msg)
            self.model.unit.status = MaintenanceStatus(msg)
            installed = self.wordpress.first_install(self.get_service_ip())
            if not installed:
                msg = "Failed to configure wordpress"
                logger.info(msg)
                self.model.unit.status = BlockedStatus(msg)
                return

            self.state.initialised = True
            logger.info("Wordpress configured and initialised")
            self.model.unit.status = ActiveStatus()

        else:
            logger.info("Wordpress workload pod is ready and configured")
            self.model.unit.status = ActiveStatus()

    def configure_pod(self):
        spec = self.make_pod_spec()
        # only the leader can set_spec()
        if self.model.unit.is_leader():
            spec = self.make_pod_spec()

            logger.info("Configuring pod")
            self.model.unit.status = MaintenanceStatus("Configuring pod")
            self.model.pod.set_spec(spec)

            logger.info("Pod configured")
            self.model.unit.status = MaintenanceStatus("Pod configured")
        else:
            logger.info("Spec changes ignored by non-leader")

    def make_pod_spec(self):
        config = self.model.config
        full_pod_config = generate_pod_config(config, secured=False)
        secure_pod_config = generate_pod_config(config, secured=True)

        ports = [
            {"name": name, "containerPort": int(port), "protocol": "TCP"}
            for name, port in [addr.split(":", 1) for addr in config["ports"].split()]
        ]

        spec = {
            "containers": [
                {
                    "name": self.app.name,
                    "imageDetails": {"imagePath": config["image"]},
                    "ports": ports,
                    "config": secure_pod_config,
                    "readinessProbe": {"exec": {"command": ["/bin/cat", "/srv/wordpress-helpers/.ready"]}},
                }
            ]
        }

        out = io.StringIO()
        pprint(spec, out)
        logger.info("This is the Kubernetes Pod spec config (sans secrets) <<EOM\n{}\nEOM".format(out.getvalue()))

        if config.get("image_user") and config.get("image_pass"):
            spec.get("containers")[0].get("imageDetails")["username"] = config["image_user"]
            spec.get("containers")[0].get("imageDetails")["password"] = config["image_pass"]

        secure_pod_config.update(full_pod_config)

        return spec

    def is_valid_config(self):
        is_valid = True
        config = self.model.config

        if not config["initial_settings"]:
            logger.info("No initial_setting provided. Skipping first install.")
            self.model.unit.status = BlockedStatus("Missing initial_settings")
            is_valid = False

        want = ("image", "db_host", "db_name", "db_user", "db_password")
        missing = [k for k in want if config[k].rstrip() == ""]
        if missing:
            message = "Missing required config: {}".format(" ".join(missing))
            logger.info(message)
            self.model.unit.status = BlockedStatus(message)
            is_valid = False

        return is_valid

    def get_service_ip(self):
        try:
            return str(self.model.get_binding("website").network.ingress_addresses[0])
        except Exception:
            logger.info("We don't have any ingress addresses yet")

    def is_service_up(self):
        """Check to see if the HTTP service is up"""
        service_ip = self.get_service_ip()
        if service_ip:
            return self.wordpress.is_vhost_ready(service_ip)
        return False


if __name__ == "__main__":
    main(WordpressK8sCharm)
