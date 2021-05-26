#!/usr/bin/env python3
import logging
import re
import os
from yaml import safe_load

from ops.charm import CharmBase, CharmEvents
from ops.framework import EventBase, EventSource, StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus

from charms.nginx_ingress_integrator.v0.ingress import IngressRequires
from leadership import LeadershipSettings
from opslib.mysql import MySQLClient

from wordpress import Wordpress, password_generator, WORDPRESS_SECRETS


logger = logging.getLogger()


def juju_setting_to_list(config_string, split_char=" "):
    "Transforms Juju setting strings into a list, defaults to splitting on whitespace."
    return config_string.split(split_char)


class WordpressFirstInstallEvent(EventBase):
    """Custom event for signalling Wordpress initialisation.

    WordpressInitialiseEvent allows us to signal the handler for
    the initial Wordpress setup logic.
    """

    pass


class WordpressStaticDatabaseChanged(EventBase):
    """Custom event for static Database configuration changed.

    WordpressStaticDatabaseChanged provides the same interface as the db.on.database_changed
    event which enables the WordPressCharm's on_database_changed handler to update state
    for both relation and static database configuration events.
    """

    @property
    def database(self):
        return self.model.config["db_name"]

    @property
    def host(self):
        return self.model.config["db_host"]

    @property
    def user(self):
        return self.model.config["db_user"]

    @property
    def password(self):
        return self.model.config["db_password"]

    @property
    def model(self):
        return self.framework.model


class WordpressCharmEvents(CharmEvents):
    """Register custom charm events.

    WordpressCharmEvents registers the custom WordpressFirstInstallEvent
    event to the charm.
    """

    wordpress_initial_setup = EventSource(WordpressFirstInstallEvent)
    wordpress_static_database_changed = EventSource(WordpressStaticDatabaseChanged)


class WordpressCharm(CharmBase):

    _container_name = "wordpress"
    _default_service_port = 80

    state = StoredState()
    on = WordpressCharmEvents()

    def __init__(self, *args):
        super().__init__(*args)

        self.leader_data = LeadershipSettings()

        logger.debug("registering Framework handlers...")

        self.framework.observe(self.on.wordpress_pebble_ready, self.on_wordpress_pebble_ready)
        self.framework.observe(self.on.config_changed, self.on_config_changed)
        self.framework.observe(self.on.leader_elected, self.on_leader_elected)

        # Actions.
        self.framework.observe(self.on.get_initial_password_action, self._on_get_initial_password_action)

        self.db = MySQLClient(self, "db")
        self.framework.observe(self.on.db_relation_created, self.on_db_relation_created)
        self.framework.observe(self.on.db_relation_broken, self.on_db_relation_broken)

        # Handlers for if user supplies database connection details or a charm relation.
        self.framework.observe(self.on.config_changed, self.on_database_config_changed)
        for db_changed_handler in [self.db.on.database_changed, self.on.wordpress_static_database_changed]:
            self.framework.observe(db_changed_handler, self.on_database_changed)

        c = self.model.config
        self.state.set_default(
            installed_successfully=False,
            install_state=set(),
            has_db_relation=False,
            has_ingress_relation=False,
            db_host=c["db_host"] or None,
            db_name=c["db_name"] or None,
            db_user=c["db_user"] or None,
            db_password=c["db_password"] or None,
        )

        self.wordpress = Wordpress(c)

        self.ingress = IngressRequires(self, self.ingress_config)

        self.framework.observe(self.on.ingress_relation_changed, self.on_ingress_relation_changed)
        self.framework.observe(self.on.ingress_relation_broken, self.on_ingress_relation_broken)
        self.framework.observe(self.on.ingress_relation_changed, self.on_ingress_relation_changed)

        # TODO: It would be nice if there was a way to unregister an observer at runtime.
        # Once the site is installed there is no need for self.on_wordpress_uninitialised to continue to observe config-changed hooks.
        if self.state.installed_successfully is False:
            self.framework.observe(self.on.config_changed, self.on_wordpress_uninitialised)
            self.framework.observe(self.on.wordpress_initial_setup, self.on_wordpress_initial_setup)

        logger.debug("all observe hooks registered...")

    @property
    def container_name(self):
        return self._container_name

    @property
    def service_ip_address(self):
        return os.environ.get("WORDPRESS_SERVICE_SERVICE_HOST")

    @property
    def service_port(self):
        return self._default_service_port

    @property
    def wordpress_setup_workload(self):
        """Returns the initial WordPress pebble workload configuration."""
        return {
            "summary": "WordPress layer",
            "description": "pebble config layer for WordPress",
            "services": {
                "wordpress-ready": {
                    "override": "replace",
                    "summary": "WordPress setup",
                    "command": "bash -c '/srv/wordpress-helpers/plugin_handler.py && stat /srv/wordpress-helpers/.ready && sleep infinity'",
                    "startup": "false",
                    "requires": [self._container_name],
                    "after": [self._container_name],
                    "environment": self._env_config,
                },
                self._container_name: {
                    "override": "replace",
                    "summary": "WordPress setup",
                    "command": "bash -c '/charm/bin/wordpressInit.sh >> /wordpressInit.log 2>&1'",
                    "startup": "false",
                    "requires": [],
                    "before": ["wordpress-ready"],
                    "environment": self._env_config,
                },
            },
        }

    @property
    def wordpress_workload(self):
        """Returns the WordPress pebble workload configuration."""
        return {
            "summary": "WordPress layer",
            "description": "pebble config layer for WordPress",
            "services": {
                self._container_name: {
                    "override": "replace",
                    "summary": "WordPress production workload",
                    "command": "apache2ctl -D FOREGROUND",
                    "startup": "enabled",
                    "requires": [],
                    "before": [],
                    "environment": self._env_config,
                },
                "wordpress-ready": {
                    "override": "replace",
                    "summary": "Remove the WordPress initialiser",
                    "command": "/bin/true",
                    "startup": "false",
                    "requires": [],
                    "after": [],
                    "environment": {},
                },
            },
        }

    @property
    def ingress_config(self):
        ingress_config = {
            "service-hostname": self.config["blog_hostname"],
            "service-name": self._container_name,
            "service-port": self.service_port,
            "tls-secret-name": self.config["tls_secret_name"],
        }
        # TODO: Raise bug to handle additional hostnames for ingress rule.
        return ingress_config

    @property
    def _db_config(self):
        """Kubernetes Pod environment variables."""
        return {
            "WORDPRESS_DB_HOST": self.state.db_host,
            "WORDPRESS_DB_NAME": self.state.db_name,
            "WORDPRESS_DB_USER": self.state.db_user,
            "WORDPRESS_DB_PASSWORD": self.state.db_password,
        }

    @property
    def _env_config(self):
        """Kubernetes Pod environment variables."""
        config = dict(self.model.config)
        env_config = {}
        if config["container_config"].strip():
            env_config = safe_load(config["container_config"])

        env_config.update(self._get_wordpress_secrets())

        if not config["tls_secret_name"]:
            env_config["WORDPRESS_TLS_DISABLED"] = "true"
        if config.get("wp_plugin_openid_team_map"):
            env_config["WP_PLUGIN_OPENID_TEAM_MAP"] = config["wp_plugin_openid_team_map"]

        # Add secrets from charm config.
        if config.get("wp_plugin_akismet_key"):
            env_config["WP_PLUGIN_AKISMET_KEY"] = config["wp_plugin_akismet_key"]
        if config.get("wp_plugin_openstack-objectstorage_config"):
            # Actual plugin name is 'openstack-objectstorage', but we're only
            # implementing the 'swift' portion of it.
            wp_plugin_swift_config = safe_load(config.get("wp_plugin_openstack-objectstorage_config"))
            env_config["SWIFT_AUTH_URL"] = wp_plugin_swift_config.get("auth-url")
            env_config["SWIFT_BUCKET"] = wp_plugin_swift_config.get("bucket")
            env_config["SWIFT_PASSWORD"] = wp_plugin_swift_config.get("password")
            env_config["SWIFT_PREFIX"] = wp_plugin_swift_config.get("prefix")
            env_config["SWIFT_REGION"] = wp_plugin_swift_config.get("region")
            env_config["SWIFT_TENANT"] = wp_plugin_swift_config.get("tenant")
            env_config["SWIFT_URL"] = wp_plugin_swift_config.get("url")
            env_config["SWIFT_USERNAME"] = wp_plugin_swift_config.get("username")
            env_config["SWIFT_COPY_TO_SWIFT"] = wp_plugin_swift_config.get("copy-to-swift")
            env_config["SWIFT_SERVE_FROM_SWIFT"] = wp_plugin_swift_config.get("serve-from-swift")
            env_config["SWIFT_REMOVE_LOCAL_FILE"] = wp_plugin_swift_config.get("remove-local-file")

        env_config.update(self._db_config)
        return env_config

    def on_wordpress_pebble_ready(self, event):
        """Entry point into the WordPress Charm's lifecycle.

        Each new workload must signal to the ingress controller
        that it exists and should be updated with the additional
        backend.
        """
        self.ingress.update_config(self.ingress_config)
        self.on.config_changed.emit()

    def on_wordpress_uninitialised(self, event):
        """Setup the WordPress service with default values.

        WordPress will expose the setup page to the user to manually
        configure with their browser. This isn't ideal from a security
        perspective so the charm will initialise the site for you and
        expose the admin password via the `TODO: name of the action`
        action.

        This method observes all changes to the system by registering
        to the .on.config_changed event. This avoids current state split
        brain issues because all changes to the system sink into
        .on_config_changed.

        It defines the state of the install ready state as:
          * We aren't ready to setup WordPress yet (missing configuration data).
          * We're ready to do the initial setup of WordPress (all dependent configuration data set).
          * We're currently setting up WordPress, lock out any other events from attempting to install.
          * WordPress is operating in a production capacity, no more work to do, no-op.
        """
        if self.unit.is_leader() is False:
            # Poorly named, expect a separate flag for non leader units here.
            self.state.installed_successfully = True

        if self.state.installed_successfully is True:
            logger.warning("already installed, nothing more to do...")
            return

        # By using sets we're able to follow a state relay pattern. Each event handler that is
        # responsible for setting state adds their flag to the set. Once thet set is complete
        # it will be observed here. During the install phase we use StoredState as a mutex lock
        # to avoid race conditions with future events. By calling .emit() we flush the current
        # state to persistent storage which ensures future events do not observe stale state.
        first_time_ready = {"leader", "db", "ingress", "leader"}
        install_running = {"attempted", "ingress", "db", "leader"}

        logger.debug(
            f"DEBUG: install ready state is {self.state.install_state}, first_time_ready state is  {first_time_ready}"
        )

        if self.state.install_state == install_running:
            logger.info("Install phase currently running...")
            BlockedStatus("WordPress installing...")

        elif self.state.install_state == first_time_ready:
            # TODO:
            # Check if WordPress is already installed.
            # Would be something like
            #   if self.wordpress.wordpress_configured(self.service_ip_address): return
            WaitingStatus("WordPress not installed yet...")
            self.state.attempted_install = True
            self.state.install_state.add("attempted")
            logger.info("Attempting WordPress install...")
            self.on.wordpress_initial_setup.emit()

    def on_wordpress_initial_setup(self, event):
        container = self.unit.get_container(self._container_name)
        logger.info("Adding WordPress setup layer to container...")
        container.add_layer(self._container_name, self.wordpress_setup_workload, combine=True)
        logger.info("Beginning WordPress setup process...")
        pebble = container.pebble
        wait_on = pebble.start_services(["wordpress-ready", self._container_name])
        pebble.wait_change(wait_on)

        self.state.installed_successfully = self.wordpress.first_install(self._get_initial_password())
        if self.state.installed_successfully is False:
            logger.error("Failed to setup WordPress with the HTTP installer...")

            # TODO: We could defer the install and try again.
            return

        logger.info("Stopping WordPress setup layer...")
        container = self.unit.get_container(self._container_name)
        pebble = container.pebble
        wait_on = pebble.stop_services([self._container_name, "wordpress-ready"])
        pebble.wait_change(wait_on)

        self.unit.status = MaintenanceStatus("WordPress Initialised")
        logger.info("Replacing WordPress setup layer with production workload...")
        container.add_layer(self._container_name, self.wordpress_workload, combine=True)

        self.leader_data["installed"] = True
        self.state.installed_successfully = True
        self.on.config_changed.emit()

    def on_config_changed(self, event):
        """Merge charm configuration transitions."""
        logger.debug(f"Event {event} install ready state is {self.state.install_state}")

        is_valid = self.is_valid_config()
        if not is_valid:
            event.defer()
            return

        container = self.unit.get_container(self._container_name)
        services = container.get_plan().to_dict().get("services", {})

        if services != self.wordpress_workload["services"]:
            logger.info("WordPress configuration transition detected...")
            self.unit.status = MaintenanceStatus("Transitioning WordPress configuration")
            container.add_layer(self._container_name, self.wordpress_workload, combine=True)

            self.unit.status = MaintenanceStatus("Restarting WordPress")
            service = container.get_service(self._container_name)
            if service.is_running():
                container.stop(self._container_name)

        if not container.get_service(self._container_name).is_running():
            logger.info("WordPress is not running, starting it now...")
            container.autostart()

        self.ingress.update_config(self.ingress_config)

        self.unit.status = ActiveStatus()

    def on_database_config_changed(self, event):
        if self.state.has_db_relation is False:
            db_config = {k: v or None for (k, v) in self.model.config.items() if k.startswith("db_")}
            if any(db_config.values()) is True:  # User has supplied db config.
                current_db_data = {self.state.db_host, self.state.db_name, self.state.db_user, self.state.db_password}
                new_db_data = {db_config.values()}
                db_differences = current_db_data.difference(new_db_data)
                if db_differences:
                    self.on.wordpress_static_database_changed.emit()

    def on_db_relation_created(self, event):
        """Handle the db-relation-created hook.

        We need to handle this hook to switch from database
        credentials being specified in the charm configuration
        to being provided by the relation.
        """

        self.state.db_host = None
        self.state.db_name = None
        self.state.db_user = None
        self.state.db_password = None
        self.state.has_db_relation = False
        self.on.config_changed.emit()

    def on_db_relation_broken(self, event):
        """Handle the db-relation-broken hook.

        We need to handle this hook to switch from database
        credentials being provided by the relation to being
        specified in the charm configuration.
        """
        self.state.db_host = None
        self.state.db_name = None
        self.state.db_user = None
        self.state.db_password = None
        self.state.has_db_relation = False
        self.on.config_changed.emit()

    def on_database_changed(self, event):
        """Handle the MySQL configuration changed event.

        The MySQLClient (self.db) emits this event whenever the
        database credentials have changed, which includes when
        they disappear as part of relation tear down. In addition
        to handling the MySQLClient relation, this method handles the
        case where db configuration is supplied by the user via model
        config. See WordpressStaticDatabaseChanged for details.
        """
        self.leader_data["db_host"] = self.state.db_host = event.host
        self.leader_data["db_name"] = self.state.db_name = event.database
        self.leader_data["db_user"] = self.state.db_user = event.user
        self.leader_data["db_password"] = self.state.db_password = event.password
        self.state.has_db_relation = True
        self.state.install_state.add("db")
        self.on.config_changed.emit()

    def on_ingress_relation_broken(self, event):
        """Handle the ingress-relation-broken hook.

        ingress service IP is used else where in the charm
        to define current state. Ensure the state is wiped when a relation
        is removed.
        """
        self.state.has_ingress_relation = False
        self.on.config_changed.emit()

    def on_ingress_relation_created(self, event):
        """Signal the configuration change to the ingress."""
        self.ingress.update_config(self.ingress_config)
        self.state.has_ingress_relation = True
        self.on.config_changed.emit()

    def on_ingress_relation_changed(self, event):
        """Store the current ingress IP address on relation changed."""
        self.ingress.update_config(self.ingress_config)
        self.state.has_ingress_relation = True
        self.state.install_state.add("ingress")
        self.on.config_changed.emit()

    def on_leader_elected(self, event):
        """Setup common workload state.

        The charm has some requirements that do not exist in the current
        Docker image, so push those files into the workload container.
        """
        container = self.unit.get_container(self._container_name)
        setup_service = "wordpressInit"
        src_path = f"src/{setup_service}.sh"
        charm_bin = "/charm/bin"
        dst_path = f"{charm_bin}/{setup_service}.sh"

        if self.unit.is_leader() is True:
            with open(src_path, "r", encoding="utf-8") as f:
                container.push(dst_path, f, permissions=0o755)
            self.state.install_state.add("leader")

        with open("src/wp-info.php", "r", encoding="utf-8") as f:
            container.push("/var/www/html/wp-info.php", f, permissions=0o755)

        self.on.config_changed.emit()

    def is_valid_config(self):
        is_valid = True
        config = dict(self.model.config)

        if self.state.installed_successfully is False:
            logger.info("WordPress has not been setup yet...")
            is_valid = False

        if not self.unit.get_container(self._container_name).get_plan().services:
            logger.info("No pebble plan seen yet")
            is_valid = False

        if not config.get("initial_settings"):
            logger.info("No initial_setting provided. Skipping first install.")
            self.model.unit.status = BlockedStatus("Missing initial_settings")
            is_valid = False

        want = ["image"]

        if self.state.has_ingress_relation is False:
            message = "Ingress relation missing."
            logger.info(message)
            self.model.unit.status = WaitingStatus(message)
            is_valid = False

        if self.state.has_db_relation is True:
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
        service_ip = self.service_ip_address
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
