#!/usr/bin/env python3

import io
import logging
import re
from pprint import pprint
from yaml import safe_load

from ops.charm import CharmBase, CharmEvents
from ops.framework import EventBase, EventSource, StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus
from leadership import LeadershipSettings

from opslib.mysql import MySQLClient
from wordpress import Wordpress, password_generator, WORDPRESS_SECRETS


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
    if not config["tls_secret_name"]:
        pod_config["WORDPRESS_TLS_DISABLED"] = "true"
    if config.get("wp_plugin_openid_team_map"):
        pod_config["WP_PLUGIN_OPENID_TEAM_MAP"] = config["wp_plugin_openid_team_map"]

    if secured:
        return pod_config

    # Add secrets from charm config.
    pod_config["WORDPRESS_DB_PASSWORD"] = config["db_password"]
    if config.get("wp_plugin_akismet_key"):
        pod_config["WP_PLUGIN_AKISMET_KEY"] = config["wp_plugin_akismet_key"]
    if config.get("wp_plugin_openstack-objectstorage_config"):
        # Actual plugin name is 'openstack-objectstorage', but we're only
        # implementing the 'swift' portion of it.
        wp_plugin_swift_config = safe_load(config.get("wp_plugin_openstack-objectstorage_config"))
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


def juju_setting_to_list(config_string, split_char=" "):
    "Transforms Juju setting strings into a list, defaults to splitting on whitespace."
    return config_string.split(split_char)


class WordpressInitialiseEvent(EventBase):
    """Custom event for signalling Wordpress initialisation.

    WordpressInitialiseEvent allows us to signal the handler for
    the initial Wordpress setup logic.
    """

    pass


class WordpressCharmEvents(CharmEvents):
    """Register custom charm events.

    WordpressCharmEvents registers the custom WordpressInitialiseEvent
    event to the charm.
    """

    wordpress_initialise = EventSource(WordpressInitialiseEvent)


class WordpressCharm(CharmBase):
    state = StoredState()
    # Override the default list of event handlers with our WordpressCharmEvents subclass.
    on = WordpressCharmEvents()

    def __init__(self, *args):
        super().__init__(*args)

        self.leader_data = LeadershipSettings()

        self.framework.observe(self.on.start, self.on_config_changed)
        self.framework.observe(self.on.config_changed, self.on_config_changed)
        self.framework.observe(self.on.update_status, self.on_config_changed)
        self.framework.observe(self.on.wordpress_initialise, self.on_wordpress_initialise)

        # Actions.
        self.framework.observe(self.on.get_initial_password_action, self._on_get_initial_password_action)

        self.db = MySQLClient(self, 'db')
        self.framework.observe(self.on.db_relation_created, self.on_db_relation_created)
        self.framework.observe(self.on.db_relation_broken, self.on_db_relation_broken)
        self.framework.observe(self.db.on.database_changed, self.on_database_changed)

        c = self.model.config
        self.state.set_default(
            initialised=False, valid=False, has_db_relation=False,
            db_host=c["db_host"], db_name=c["db_name"], db_user=c["db_user"], db_password=c["db_password"]
        )
        self.wordpress = Wordpress(c)

    def on_config_changed(self, event):
        """Handle the config-changed hook."""
        self.config_changed()

    def on_wordpress_initialise(self, event):
        wordpress_needs_configuring = False
        pod_alive = self.model.unit.is_leader() and self.is_service_up()
        if pod_alive:
            wordpress_configured = self.wordpress.wordpress_configured(self.get_service_ip())
            wordpress_needs_configuring = not self.state.initialised and not wordpress_configured
        elif self.model.unit.is_leader():
            msg = "Wordpress workload pod is not ready"
            logger.info(msg)
            self.model.unit.status = WaitingStatus(msg)
            return

        if wordpress_needs_configuring:
            msg = "Wordpress needs configuration"
            logger.info(msg)
            self.model.unit.status = MaintenanceStatus(msg)
            initial_password = self._get_initial_password()
            installed = self.wordpress.first_install(self.get_service_ip(), initial_password)
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

    def on_db_relation_created(self, event):
        """Handle the db-relation-created hook.

        We need to handle this hook to switch from database
        credentials being specified in the charm configuration
        to being provided by the relation.
        """
        self.state.has_db_relation = True
        self.state.db_host = None
        self.state.db_name = None
        self.state.db_user = None
        self.state.db_password = None
        self.config_changed()

    def on_db_relation_broken(self, event):
        """Handle the db-relation-broken hook.

        We need to handle this hook to switch from database
        credentials being provided by the relation to being
        specified in the charm configuration.
        """
        self.state.has_db_relation = False
        self.config_changed()

    def on_database_changed(self, event):
        """Handle the MySQL endpoint database_changed event.

        The MySQLClient (self.db) emits this event whenever the
        database credentials have changed, which includes when
        they disappear as part of relation tear down.
        """
        self.state.db_host = event.host
        self.state.db_name = event.database
        self.state.db_user = event.user
        self.state.db_password = event.password
        self.config_changed()

    def config_changed(self):
        """Handle configuration changes.

        Configuration changes are caused by both config-changed
        and the various relation hooks.
        """
        if not self.state.has_db_relation:
            self.state.db_host = self.model.config["db_host"] or None
            self.state.db_name = self.model.config["db_name"] or None
            self.state.db_user = self.model.config["db_user"] or None
            self.state.db_password = self.model.config["db_password"] or None

        is_valid = self.is_valid_config()
        if not is_valid:
            return

        self.configure_pod()
        if not self.state.initialised:
            self.on.wordpress_initialise.emit()

    def configure_pod(self):
        # Only the leader can set_spec().
        if self.model.unit.is_leader():
            resources = self.make_pod_resources()
            spec = self.make_pod_spec()
            spec.update(resources)

            msg = "Configuring pod"
            logger.info(msg)
            self.model.unit.status = MaintenanceStatus(msg)
            self.model.pod.set_spec(spec)

            if self.state.initialised:
                msg = "Pod configured"
                logger.info(msg)
                self.model.unit.status = ActiveStatus(msg)
            else:
                msg = "Pod configured, but WordPress configuration pending"
                logger.info(msg)
                self.model.unit.status = MaintenanceStatus(msg)
        else:
            logger.info("Spec changes ignored by non-leader")

    def make_pod_resources(self):
        resources = {
            "kubernetesResources": {
                "ingressResources": [
                    {
                        "annotations": {
                            "nginx.ingress.kubernetes.io/proxy-body-size": "10m",
                            "nginx.ingress.kubernetes.io/proxy-send-timeout": "300s",
                        },
                        "name": self.app.name + "-ingress",
                        "spec": {
                            "rules": [
                                {
                                    "host": self.model.config["blog_hostname"],
                                    "http": {
                                        "paths": [
                                            {"path": "/", "backend": {"serviceName": self.app.name, "servicePort": 80}}
                                        ]
                                    },
                                }
                            ],
                        },
                    }
                ]
            },
        }

        if self.model.config["additional_hostnames"]:
            additional_hostnames = juju_setting_to_list(self.model.config["additional_hostnames"])
            rules = resources["kubernetesResources"]["ingressResources"][0]["spec"]["rules"]
            for hostname in additional_hostnames:
                rule = {
                    "host": hostname,
                    "http": {
                        "paths": [
                            {"path": "/", "backend": {"serviceName": self.app.name, "servicePort": 80}}
                        ]
                    },
                }
                rules.append(rule)

        ingress = resources["kubernetesResources"]["ingressResources"][0]
        if self.model.config["tls_secret_name"]:
            ingress["spec"]["tls"] = [
                {
                    "hosts": [self.model.config["blog_hostname"]],
                    "secretName": self.model.config["tls_secret_name"],
                }
            ]
        else:
            ingress["annotations"]['nginx.ingress.kubernetes.io/ssl-redirect'] = 'false'

        out = io.StringIO()
        pprint(resources, out)
        logger.info("This is the Kubernetes Pod resources <<EOM\n{}\nEOM".format(out.getvalue()))

        return resources

    def make_pod_spec(self):
        config = dict(self.model.config)
        config["db_host"] = self.state.db_host
        config["db_name"] = self.state.db_name
        config["db_user"] = self.state.db_user
        config["db_password"] = self.state.db_password

        full_pod_config = generate_pod_config(config, secured=False)
        full_pod_config.update(self._get_wordpress_secrets())
        secure_pod_config = generate_pod_config(config, secured=True)

        ports = [
            {"name": name, "containerPort": int(port), "protocol": "TCP"}
            for name, port in [addr.split(":", 1) for addr in config["ports"].split()]
        ]

        spec = {
            "version": 2,
            "containers": [
                {
                    "name": self.app.name,
                    "imageDetails": {"imagePath": config["image"]},
                    "ports": ports,
                    "config": secure_pod_config,
                    "kubernetes": {"readinessProbe": {"exec": {"command": ["/srv/wordpress-helpers/ready.sh"]}}},
                }
            ],
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

        want = ["image"]

        if self.state.has_db_relation:
            if not (self.state.db_host and self.state.db_name and self.state.db_user and self.state.db_password):
                logger.info("MySQL relation has not yet provided database credentials.")
                self.model.unit.status = WaitingStatus("Waiting for MySQL relation to become available")
                is_valid = False
        else:
            want.extend(["db_host", "db_name", "db_user", "db_password"])

        missing = [k for k in want if config[k].rstrip() == ""]
        if missing:
            message = "Missing required config or relation: {}".format(" ".join(missing))
            logger.info(message)
            self.model.unit.status = BlockedStatus(message)
            is_valid = False

        if config["additional_hostnames"]:
            additional_hostnames = juju_setting_to_list(config["additional_hostnames"])
            valid_domain_name_pattern = re.compile(r"^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$")
            valid = [re.match(valid_domain_name_pattern, h) for h in additional_hostnames]
            if not all(valid):
                message = "Invalid additional hostnames supplied: {}".format(config["additional_hostnames"])
                logger.info(message)
                self.model.unit.status = BlockedStatus(message)
                is_valid = False

        return is_valid

    def get_service_ip(self):
        try:
            return str(self.model.get_binding("website").network.ingress_addresses[0])
        except Exception:
            logger.info("We don't have any ingress addresses yet")

    def _get_wordpress_secrets(self):
        """Get secrets, creating them if they don't exist.

        These are part of the pod spec, and so this function can only be run
        on the leader. We can therefore safely generate them if they don't
        already exist."""
        wp_secrets = {}
        for secret in WORDPRESS_SECRETS:
            # `self.leader_data` itself will never return a KeyError, but
            # checking for the presence of an item before setting it will make
            # it easier to test, as we can simply set `self.leader_data` to
            # be a dictionary.
            if secret not in self.leader_data or not self.leader_data[secret]:
                self.leader_data[secret] = password_generator(64)
            wp_secrets[secret] = self.leader_data[secret]
        return wp_secrets

    def is_service_up(self):
        """Check to see if the HTTP service is up"""
        service_ip = self.get_service_ip()
        if service_ip:
            return self.wordpress.is_vhost_ready(service_ip)
        return False

    def _get_initial_password(self):
        """Get the initial password.

        If a password hasn't been set yet, create one if we're the leader,
        or return an empty string if we're not."""
        initial_password = self.leader_data["initial_password"]
        if not initial_password:
            if self.unit.is_leader():
                initial_password = password_generator()
                self.leader_data["initial_password"] = initial_password
        return initial_password

    def _on_get_initial_password_action(self, event):
        """Handle the get-initial-password action."""
        initial_password = self._get_initial_password()
        if initial_password:
            event.set_results({"password": initial_password})
        else:
            event.fail("Initial password has not been set yet.")


if __name__ == "__main__":  # pragma: no cover
    main(WordpressCharm)
