#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for WordPress on kubernetes."""

import collections
import itertools
import json
import logging
import os
import re
import secrets
import string
import textwrap
import time
import traceback
from typing import Any, Dict, List, Optional, Union

import mysql.connector
import ops.charm
import ops.pebble
import yaml
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.loki_k8s.v0.loki_push_api import LogProxyConsumer
from charms.nginx_ingress_integrator.v0.nginx_route import require_nginx_route
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from ops.charm import ActionEvent, CharmBase, LeaderElectedEvent, PebbleReadyEvent, StartEvent
from ops.framework import EventBase, StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
    RelationDataContent,
    WaitingStatus,
)
from ops.pebble import ExecProcess
from yaml import safe_load

import exceptions
import types_
from cos import APACHE_LOG_PATHS, PROM_EXPORTER_PEBBLE_CONFIG, WORDPRESS_SCRAPE_JOBS

# MySQL logger prints database credentials on debug level, silence it
logging.getLogger(mysql.connector.__name__).setLevel(logging.WARNING)
logger = logging.getLogger()


class WordpressCharm(CharmBase):
    """Charm for WordPress on kubernetes.

    Attrs:
        state: Persistent charm state used to store metadata after various events.
    """

    class _ReplicaRelationNotReady(Exception):
        """Replica databag was accessed before peer relations are established."""

    _WP_CONFIG_PATH = "/var/www/html/wp-config.php"
    _CONTAINER_NAME = "wordpress"
    _SERVICE_NAME = "wordpress"
    _WORDPRESS_USER = "www-data"
    _WORDPRESS_GROUP = "www-data"
    _WORDPRESS_DB_CHARSET = "utf8mb4"
    _DATABASE_RELATION_NAME = "database"

    # Default themes and plugins are installed in oci image build time and defined in Dockerfile
    _WORDPRESS_DEFAULT_THEMES = [
        "launchpad",
        "light-wordpress-theme",
        "mscom",
        "thematic",
        "twentyeleven",
        "twentytwenty",
        "twentytwentyone",
        "twentytwentytwo",
        "ubuntu-cloud-website",
        "ubuntu-community-wordpress-theme/ubuntu-community",
        "ubuntu-community/ubuntu-community",
        "ubuntu-fi",
        "ubuntu-light",
        "ubuntustudio-wp/ubuntustudio-wp",
        "xubuntu-website/xubuntu-eighteen",
        "xubuntu-website/xubuntu-fifteen",
        "xubuntu-website/xubuntu-fourteen",
        "xubuntu-website/xubuntu-thirteen",
    ]

    _WORDPRESS_DEFAULT_PLUGINS = [
        "404page",
        "akismet",
        "all-in-one-event-calendar",
        "powerpress",
        "coschedule-by-todaymade",
        "elementor",
        "essential-addons-for-elementor-lite",
        "favicon-by-realfavicongenerator",
        "feedwordpress",
        "genesis-columns-advanced",
        "line-break-shortcode",
        "wp-mastodon-share",
        "miniorange-saml-20-single-sign-on",
        "no-category-base-wpml",
        "openid",
        "wordpress-launchpad-integration",
        "wordpress-teams-integration",
        "openstack-objectstorage-k8s",
        "post-grid",
        "redirection",
        "relative-image-urls",
        "rel-publisher",
        "safe-svg",
        "show-current-template",
        "simple-301-redirects",
        "simple-custom-css",
        "so-widgets-bundle",
        "svg-support",
        "syntaxhighlighter",
        "wordpress-importer",
        "wp-markdown",
        "wp-polls",
        "wp-font-awesome",
        "wp-lightbox-2",
        "wp-statistics",
        "xubuntu-team-members",
        "wordpress-seo",
    ]

    _DB_CHECK_INTERVAL = 1
    _DB_CHECK_TIMEOUT = 300

    state = StoredState()

    def __init__(self, *args, **kwargs):
        """Initialize the instance.

        Args:
            args: arguments passed into Charmbase superclass.
            kwargs: keyword arguments passed into Charmbase superclass.
        """
        super().__init__(*args, **kwargs)

        self.database = DatabaseRequires(
            self, relation_name=self._DATABASE_RELATION_NAME, database_name=self.app.name
        )

        self.state.set_default(
            relation_db_host=None,
            relation_db_name=None,
            relation_db_user=None,
            relation_db_password=None,
            started=False,
        )

        self._require_nginx_route()
        self.metrics_endpoint = MetricsEndpointProvider(
            self,
            jobs=WORDPRESS_SCRAPE_JOBS,
        )
        self._logging = LogProxyConsumer(
            self, relation_name="logging", log_files=APACHE_LOG_PATHS, container_name="wordpress"
        )
        self._grafana_dashboards = GrafanaDashboardProvider(self)

        self.framework.observe(
            self.on.get_initial_password_action, self._on_get_initial_password_action
        )
        self.framework.observe(
            self.on.rotate_wordpress_secrets_action, self._on_rotate_wordpress_secrets_action
        )

        self.framework.observe(self.on.leader_elected, self._setup_replica_data)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.uploads_storage_attached, self._reconciliation)
        self.framework.observe(self.database.on.database_created, self._reconciliation)
        self.framework.observe(self.database.on.endpoints_changed, self._reconciliation)
        self.framework.observe(self.on.config_changed, self._reconciliation)
        self.framework.observe(self.on.upgrade_charm, self._setup_replica_data)
        self.framework.observe(self.on.wordpress_pebble_ready, self._set_version)
        self.framework.observe(self.on.wordpress_pebble_ready, self._reconciliation)
        self.framework.observe(self.on["wordpress-replica"].relation_changed, self._reconciliation)
        self.framework.observe(
            self.on.apache_prometheus_exporter_pebble_ready,
            self._on_apache_prometheus_exporter_pebble_ready,
        )

    def _on_start(self, _event: StartEvent):
        """Record if the start event is emitted."""
        self.state.started = True

    def _set_version(self, _: PebbleReadyEvent):
        """Set WordPress application version to Juju charm's app version status."""
        version_result = self._run_wp_cli(
            ["wp", "core", "version"],
            timeout=60,
        )
        if version_result.return_code != 0:
            logger.error(
                "WordPress version command failed with exit code %d.", version_result.return_code
            )
            return
        self.unit.set_workload_version(version_result.stdout)

    def _require_nginx_route(self):
        """Require nginx-route relation based on current configuration."""
        use_modsec = self.model.config["use_nginx_ingress_modsec"]
        owasp_modsecurity_custom_rules = 'SecAction "id:900130,phase:1,nolog,pass,t:none,setvar:tx.crs_exclusions_wordpress=1"\n'
        require_nginx_route(
            charm=self,
            service_hostname=self.model.config["blog_hostname"] or self.app.name,
            service_name=self.app.name,
            service_port=80,
            owasp_modsecurity_crs=True if use_modsec else None,
            owasp_modsecurity_custom_rules=owasp_modsecurity_custom_rules if use_modsec else None,
        )

    def _on_get_initial_password_action(self, event: ActionEvent):
        """Handle the get-initial-password action.

        Args:
            event: Used for returning result or failure of action.
        """
        if self._replica_consensus_reached():
            default_admin_password = self._replica_relation_data().get("default_admin_password")
            event.set_results({"password": default_admin_password})
        else:
            logger.error("Action get-initial-password failed. Replica consensus not reached.")
            event.fail("Default admin password has not been generated yet.")

    def _on_rotate_wordpress_secrets_action(self, event: ActionEvent):
        """Handle the rotate-wordpress_secrets action.

        This action is for rotating the secrets of WordPress. The leader unit is the one handling
        the rotation by updating the application relation data. The followers will pick up the
        event and update the secrets via the application `relation_changed` event.

        Args:
            event: Used for returning result or failure of action.
        """
        if not self._replica_consensus_reached():
            logger.error(
                "Action on-rotate-wordpress-secrets failed. Replica consensus not reached."
            )
            event.fail("Secrets have not been initialized yet.")
            return

        if not self.unit.is_leader():
            event.fail(
                "This unit is not leader."
                " Use <application>/leader to specify the leader unit when running action."
            )
            return

        # Update the secrets in peer relation.
        replica_relation_data = self._replica_relation_data()
        wordpress_secrets = self._generate_wp_secret_keys()
        for secret_key, secret_value in wordpress_secrets.items():
            replica_relation_data[secret_key] = secret_value

        # Leader need to call `_reconciliation` manually.
        # Followers call it automatically due to relation_changed event.
        self._reconciliation(event)
        event.set_results({"result": "ok"})

    @staticmethod
    def _wordpress_secret_key_fields():
        """Field names of secrets required for instantiation of WordPress.

        These secrets are used by WordPress to enhance the security by encrypting information.

        Returns:
            Secret key fields required for WordPress to encrypt information.
        """
        return [
            "auth_key",
            "secure_auth_key",
            "logged_in_key",
            "nonce_key",
            # These salts are for cookies. They should not affect user passwords.
            "auth_salt",
            "secure_auth_salt",
            "logged_in_salt",
            "nonce_salt",
        ]

    def _generate_wp_secret_keys(self) -> Dict[str, str]:
        """Generate random secure secrets for each secret required by WordPress.

        Returns:
            WordPress secret-value pairs.
        """

        def _wp_generate_password(length: int = 64) -> str:
            """Generate password.

            Args:
                length: Desired length of the password.

            Returns:
                Generated password.
            """
            characters = string.ascii_letters + "!@#$%^&*()" + "-_ []{}<>~`+=,.;:/?|"
            return "".join(secrets.choice(characters) for _ in range(length))

        wp_secrets = {
            field: _wp_generate_password() for field in self._wordpress_secret_key_fields()
        }
        wp_secrets["default_admin_password"] = secrets.token_urlsafe(32)
        return wp_secrets

    def _replica_relation_data(self) -> RelationDataContent:
        """Retrieve data shared with WordPress peers (replicas).

        The relation data content object is used to share (read and write) necessary secret data
        used by WordPress to enhance security and must be synchronized.

        Raises:
            _ReplicaRelationNotReady: if replica relation is not established.

        Returns:
            Read/Write-able mapping for WordPress application shared among its replicas.
        """
        relation = self.model.get_relation("wordpress-replica")
        if relation is None:
            raise self._ReplicaRelationNotReady(
                "Access replica peer relation data before relation established"
            )
        return relation.data[self.app]

    def _replica_consensus_reached(self):
        """Test if the synchronized data required for WordPress replication are initialized.

        Returns:
            True if the initialization of synchronized data has finished, else False.
        """
        fields = self._wordpress_secret_key_fields()
        try:
            replica_data = self._replica_relation_data()
        except self._ReplicaRelationNotReady:
            return False
        return all(replica_data.get(f) for f in fields)

    def _setup_replica_data(self, _event: LeaderElectedEvent) -> None:
        """Initialize the synchronized data required for WordPress replication.

        Only the leader can update the data shared with all replicas. Leader should check if
        the data exist when leadership is established, generate required data and set it in
        the peer relation if not.

        Args:
            _event: required by ops framework, not used.
        """
        if not self._replica_consensus_reached() and self.unit.is_leader():
            replica_relation_data = self._replica_relation_data()
            new_replica_data = self._generate_wp_secret_keys()
            for secret_key, secret_value in new_replica_data.items():
                replica_relation_data[secret_key] = secret_value

    def _gen_wp_config(self):
        """Generate the wp-config.php file WordPress needs based on charm config and relations.

        This method will not check the validity of the configuration or current state,
        unless they are security related, in that case, an exception will be raised.

        Returns:
            The content of wp-config.php file in string.
        """
        wp_config = [
            textwrap.dedent(
                """\
            <?php
            # This file is managed by Juju. Do not make local changes.
            if (strpos($_SERVER['HTTP_X_FORWARDED_PROTO'], 'https') !== false) {
                $_SERVER['HTTPS']='on';
            }
            $table_prefix = 'wp_';
            $_w_p_http_protocol = 'http://';
            if (!empty($_SERVER['HTTPS']) && 'off' != $_SERVER['HTTPS']) {
                $_w_p_http_protocol = 'https://';
            }
            define( 'WP_PLUGIN_URL', $_w_p_http_protocol . $_SERVER['HTTP_HOST'] . '/wp-content/plugins' );
            define( 'WP_CONTENT_URL', $_w_p_http_protocol . $_SERVER['HTTP_HOST'] . '/wp-content' );
            define( 'WP_SITEURL', $_w_p_http_protocol . $_SERVER['HTTP_HOST'] );
            define( 'WP_URL', $_w_p_http_protocol . $_SERVER['HTTP_HOST'] );
            define( 'WP_HOME', $_w_p_http_protocol . $_SERVER['HTTP_HOST'] );"""
            )
        ]

        if self._current_effective_db_info:
            wp_config.append(f"define( 'DB_HOST', '{self._current_effective_db_info.hostname}' );")
            wp_config.append(f"define( 'DB_NAME', '{self._current_effective_db_info.database}' );")
            wp_config.append(f"define( 'DB_USER', '{self._current_effective_db_info.username}' );")
            wp_config.append(
                f"define( 'DB_PASSWORD', '{self._current_effective_db_info.password}' );"
            )
            wp_config.append(f"define( 'DB_CHARSET',  '{self._WORDPRESS_DB_CHARSET}' );")

        replica_relation_data = self._replica_relation_data()
        for secret_key in self._wordpress_secret_key_fields():
            secret_value = replica_relation_data[secret_key]
            wp_config.append(f"define( '{secret_key.upper()}', '{secret_value}' );")

        # make WordPress immutable, user can not install or update any plugins or themes from
        # admin panel and all updates are disabled
        wp_config.append("define( 'DISALLOW_FILE_MODS', true );")
        wp_config.append("define( 'AUTOMATIC_UPDATER_DISABLED', true );")

        wp_config.append("define( 'WP_CACHE', true );")
        wp_config.append(
            textwrap.dedent(
                """\
                if ( ! defined( 'ABSPATH' ) ) {
                    define( 'ABSPATH', __DIR__ . '/' );
                }

                /** Sets up WordPress vars and included files. */
                require_once ABSPATH . 'wp-settings.php';
                """
            )
        )
        return "\n".join(wp_config)

    def _container(self):
        """Get the WordPress workload container.

        Returns:
            The pebble instance of the WordPress container.
        """
        return self.unit.get_container(self._CONTAINER_NAME)

    def _wordpress_service_exists(self) -> bool:
        """Check if the WordPress pebble layer exists.

        Returns:
            True if WordPress layer already exists, else False.
        """
        return self._SERVICE_NAME in self._container().get_plan().services

    def _stop_server(self) -> None:
        """Stop WordPress (apache) server, this operation is idempotent."""
        logger.info("Ensure WordPress (apache) server is down")
        if (
            self._wordpress_service_exists()
            and self._container().get_service(self._SERVICE_NAME).is_running()
        ):
            self._container().stop(self._SERVICE_NAME)

    def _run_cli(
        self,
        cmd: List[str],
        user: Union[str, None] = None,
        group: Union[str, None] = None,
        working_dir: Union[str, None] = None,
        combine_stderr: bool = False,
        timeout: int = 60,
    ) -> types_.CommandExecResult:
        """Execute a command in WordPress container.

        Args:
            cmd (List[str]): The command to be executed.
            user (str): Username to run this command as, use root when not provided.
            group (str): Name of the group to run this command as, use root when not provided.
            working_dir (str):  Working dir to run this command in, use home dir if not provided.
            combine_stderr (bool): Redirect stderr to stdout, when enabled, stderr in the result
                will always be empty.
            timeout (int): Set a timeout for the running program in seconds. Default is 60 seconds.
                ``TimeoutError`` will be raised if timeout exceeded.

        Returns:
            A named tuple with three fields: return code, stdout and stderr. Stdout and stderr are
            both string.
        """
        Result = collections.namedtuple("CommandExecResult", "return_code stdout stderr")
        process: ExecProcess = self._container().exec(
            cmd,
            user=user,
            group=group,
            working_dir=working_dir,
            combine_stderr=combine_stderr,
            timeout=timeout,
        )
        try:
            stdout, stderr = process.wait_output()
            result = types_.CommandExecResult(return_code=0, stdout=stdout, stderr=stderr)
        except ops.pebble.ExecError as error:
            result = Result(error.exit_code, error.stdout, error.stderr)
        return_code = result.return_code
        if combine_stderr:
            logger.debug(
                "Run command: %s return code %s\noutput: %s", cmd, return_code, result.stdout
            )
        else:
            logger.debug(
                "Run command: %s, return code %s\nstdout: %s\nstderr:%s",
                cmd,
                return_code,
                result.stdout,
                result.stderr,
            )
        return result

    def _run_wp_cli(
        self, cmd: List[str], timeout: int = 60, combine_stderr: bool = False
    ) -> types_.CommandExecResult:
        """Execute a wp-cli command, this is a wrapper of :meth:`charm.WordpressCharm._run_cli`.

        See :meth:`charm.WordpressCharm._run_cli` for documentation of the arguments and return
        value.

        Args:
            cmd: WordPress command to execute.
            timeout: timeout in seconds for the execution of command.
            combine_stderr: Redirect stderr to stdout, when enabled, stderr in the result
                will always be empty.

        Returns:
            Result of executed command in WordPress. See :meth:`charm.WordpressCharm._run_cli`.
        """
        result = self._run_cli(
            cmd,
            user=self._WORDPRESS_USER,
            group=self._WORDPRESS_GROUP,
            working_dir="/var/www/html",
            combine_stderr=combine_stderr,
            timeout=timeout,
        )
        return result

    def _wrapped_run_wp_cli(
        self, cmd: List[str], timeout: int = 60, error_message: Union[str, None] = None
    ) -> types_.ExecResult:
        """Run wp cli command and return the result as ``types_.ExecResult``.

        Stdout and stderr are discarded, the result field of ExecResult is always none. The
        execution is considered success if return code is 0. The message field will be generated
        automatically based on command if ``error_message`` is not provided.

        Args:
            cmd (List[str]): The command to be executed.
            timeout (int): Set a timeout for the running program, in seconds,
                default is 60 seconds. ``TimeoutError`` will be raised if timeout exceeded.
            error_message (str): message in the return result if the command failed, if None,
                a default error message will be provided in the result.

        Returns:
            A named tuple with three fields: success, result and message. ``success`` will be True
            if the command succeed. ``result`` will always be None and ``message`` represents the
            error message, in case of success, it will be empty.
        """
        result = self._run_wp_cli(cmd=cmd, timeout=timeout, combine_stderr=True)
        if result.return_code != 0:
            return types_.ExecResult(
                success=False,
                result=None,
                message=f"command {cmd} failed" if not error_message else error_message,
            )
        return types_.ExecResult(success=True, result=None, message="")

    def _wp_is_installed(self):
        """Check if WordPress is installed (check if WordPress related tables exist in database).

        Returns:
            True if WordPress is installed in the current connected database.
        """
        logger.debug("Check if WordPress is installed")
        return self._run_wp_cli(["wp", "core", "is-installed"]).return_code == 0

    def _parse_database_endpoints(self, endpoint: Optional[str]) -> Optional[str]:
        """Retrieve a single database endpoint.

        Args:
            endpoint: An endpoint of format host:port

        Returns:
            Hostname of database running on port 3306. None if no endpoints are provided.
            Note that WordPress will throw MySQL Error when supplying a port with the hostname
            (i.e. host:port).

        Raises:
            WordPressBlockedStatusException: Provided endpoint contains port other than 3306.
        """
        if not endpoint:
            return None
        host_port = endpoint.split(":")
        if len(host_port) == 2 and host_port[1] != "3306":
            raise exceptions.WordPressBlockedStatusException(f"Invalid port {host_port[1]}")
        # The endpoint might not contain port, we assume it to be 3306. If not, it will be caught
        # by `_test_database_connectivity` function later on.
        return host_port[0]

    @property
    def _current_effective_db_info(self) -> Optional[types_.DatabaseConfig]:
        """Get the current effective db connection information.

        Returns:
            Database configuration required to establish database connection.
            None if not exists.
        """
        relation = self.model.get_relation(self._DATABASE_RELATION_NAME)
        if not relation:
            return None
        return types_.DatabaseConfig(
            hostname=self._parse_database_endpoints(relation.data[relation.app].get("endpoints")),
            database=relation.data[relation.app].get("database"),
            username=relation.data[relation.app].get("username"),
            password=relation.data[relation.app].get("password"),
        )

    def _test_database_connectivity(self):
        """Test the connectivity of the current database config/relation.

        Returns:
            A tuple of connectivity as bool and error message as str, error message will be
            an empty string if charm can connect to the database.
        """
        try:
            # TODO: add database charset check later
            cnx = mysql.connector.connect(
                host=self._current_effective_db_info.hostname,
                database=self._current_effective_db_info.database,
                user=self._current_effective_db_info.username,
                password=self._current_effective_db_info.password,
                charset="latin1",
            )
            cnx.close()
            return True, ""
        except mysql.connector.Error as err:
            if err.errno < 0:
                logger.debug("MySQL connection test failed, traceback: %s", traceback.format_exc())
            return False, f"MySQL error {err.errno}"

    def _wp_install_cmd(self):
        """Generate wp-cli command used to install WordPress on database.

        Returns:
            Wp-cli WordPress install command, a list of strings.
        """
        initial_settings = yaml.safe_load(self.model.config["initial_settings"])
        admin_user = initial_settings.get("user_name", "admin_username")
        admin_email = initial_settings.get("admin_email", "name@example.com")
        default_admin_password = self._replica_relation_data()["default_admin_password"]
        admin_password = initial_settings.get("admin_password", default_admin_password)
        return [
            "wp",
            "core",
            "install",
            "--url=localhost",
            f"--title=The {self.model.config['blog_hostname'] or self.app.name} Blog",
            f"--admin_user={admin_user}",
            f"--admin_email={admin_email}",
            f"--admin_password={admin_password}",
        ]

    def _wp_install(self):
        """Install WordPress (create WordPress required tables in DB).

        Raises:
            WordPressInstallError: if WordPress installation fails.
        """
        logger.info("Install WordPress, create WordPress related table in the database")
        self.unit.status = ops.model.MaintenanceStatus("Initializing WordPress DB")
        process = self._run_wp_cli(self._wp_install_cmd(), combine_stderr=True, timeout=60)
        if process.return_code != 0:
            logger.error("WordPress installation failed: %s", process.stdout)
            raise exceptions.WordPressInstallError("check logs for more information")

    def _init_pebble_layer(self):
        """Ensure WordPress layer exists in pebble."""
        logger.debug("Ensure WordPress layer exists in pebble")
        layer = {
            "summary": "WordPress layer",
            "description": "WordPress server",
            "services": {
                self._SERVICE_NAME: {
                    "override": "replace",
                    "summary": "WordPress server (apache)",
                    "command": "apache2ctl -D FOREGROUND",
                }
            },
            "checks": {
                "wordpress-ready": {
                    "override": "replace",
                    "level": "alive",
                    "http": {"url": "http://localhost/index.php"},
                },
            },
        }
        self._container().add_layer("wordpress", layer, combine=True)

    def _start_server(self):
        """Start WordPress (apache) server. On leader unit, also make sure WordPress is installed.

        Check if the pebble layer has been added, then check the installation status of WordPress,
        finally start the server. The installation process only run on the leader unit. This
        operation is idempotence.

        Raises:
            WordPressBlockedStatusException: If unrecoverable error happens.
            FileNotFoundError: if WordPress configuration file does not exist.
        """
        logger.info("Ensure WordPress server is up")
        if self.unit.is_leader():
            msg = ""
            deadline = time.time() + self._DB_CHECK_TIMEOUT
            while time.time() < deadline:
                success, msg = self._test_database_connectivity()
                if success:
                    break
                time.sleep(self._DB_CHECK_INTERVAL)
            else:
                raise exceptions.WordPressBlockedStatusException(msg)

            if not self._wp_is_installed():
                self._wp_install()
        else:
            deadline = time.time() + self._DB_CHECK_TIMEOUT
            while time.time() < deadline:
                if self._wp_is_installed():
                    break
                self.unit.status = WaitingStatus("Waiting for leader unit to initialize database")
                time.sleep(self._DB_CHECK_INTERVAL)
            else:
                raise exceptions.WordPressBlockedStatusException(
                    "leader unit failed to initialize WordPress database in given time."
                )
        if self._current_wp_config() is None:
            # For security reasons, never start WordPress server if wp-config.php not exists
            raise FileNotFoundError(
                "required file (wp-config.php) for starting WordPress server does not exists"
            )
        self._init_pebble_layer()
        if not self._container().get_service(self._SERVICE_NAME).is_running():
            self._container().start(self._SERVICE_NAME)

    def _current_wp_config(self):
        """Retrieve the current version of wp-config.php from server, return None if not exists.

        Returns:
            The content of the current wp-config.php file, str.
        """
        wp_config_path = self._WP_CONFIG_PATH
        container = self._container()
        if container.exists(wp_config_path):
            return self._container().pull(wp_config_path).read()
        return None

    def _push_wp_config(self, wp_config: str) -> None:
        """Update the content of wp-config.php on server.

        Write the wp-config.php file in :attr:`charm.WordpressCharm._WP_CONFIG_PATH`.

        Args:
            wp_config (str): the content of wp-config.php file.
        """
        logger.info("Update wp-config.php content in container")
        self._container().push(
            self._WP_CONFIG_PATH,
            wp_config,
            user=self._WORDPRESS_USER,
            group=self._WORDPRESS_GROUP,
            permissions=0o600,
        )

    def _core_reconciliation(self) -> None:
        """Reconciliation process for the WordPress core services, returns True if successful.

        It will fail under the following two circumstances:
          - Peer relation data not ready
          - Config doesn't provide valid database information and db relation hasn't
            been established

        It will check if the current wp-config.php file matches the desired config.
        If not, update the wp-config.php file.

        It will also check if WordPress is installed (WordPress-related tables exist in db).
        If not, install WordPress (create WordPress required tables in db).

        If any update is needed, it will stop the apache server first to prevent any requests
        during the update for security reasons.

        Raises:
            WordPressWaitingStatusException: if replication data has not been synchronized yet.
            WordPressBlockedStatusException: if database relation/config has not been set yet.
        """
        logger.info("Start core reconciliation process")
        if not self._replica_consensus_reached():
            logger.info("Core reconciliation terminates early, replica consensus is not ready")
            self._stop_server()
            raise exceptions.WordPressWaitingStatusException("Waiting for unit consensus")
        if not self._current_effective_db_info:
            logger.info("Core reconciliation terminated early due to db info missing.")
            self._stop_server()
            raise exceptions.WordPressBlockedStatusException("Waiting for db relation/config")
        wp_config = self._gen_wp_config()
        if wp_config != self._current_wp_config():
            logger.info("Changes detected in wp-config.php, updating")
            self._stop_server()
            self._push_wp_config(wp_config)
        self._start_server()
        logger.info("Wait until the pebble container exists")

    def _check_addon_type(self, addon_type: str) -> None:
        """Check if addon_type is one of the accepted addon types (theme/plugin).

        Args:
            addon_type: type of WordPress addon, can be either "theme" or "plugin".

        Raises:
            ValueError: if addon_type is not one of theme/plugin.
        """
        if addon_type not in ("theme", "plugin"):
            raise ValueError(f"Addon type unknown {repr(addon_type)}, accept: (theme, plugin)")

    def _wp_addon_list(self, addon_type: str):
        """List all installed WordPress addons.

        Args:
            addon_type (str): ``"theme"`` or ``"plugin"``

        Returns:
            A named tuple with three fields: success, result and message. If list command failed,
            success will be False, result will be None and message will be the error message.
            Other than that, success will be True, message will be empty and result will be a list
            of dicts represents the status of currently installed addons. Each dict contains four
            keys: name, status, update and version.
        """
        self._check_addon_type(addon_type)
        process = self._run_wp_cli(["wp", addon_type, "list", "--format=json"], timeout=600)
        if process.return_code != 0:
            return types_.ExecResult(
                success=False, result=None, message=f"wp {addon_type} list command failed"
            )
        try:
            return types_.ExecResult(success=True, result=json.loads(process.stdout), message="")
        except json.decoder.JSONDecodeError:
            return types_.ExecResult(
                success=False,
                result=None,
                message=f"wp {addon_type} list command failed, stdout is not json",
            )

    def _wp_addon_install(self, addon_type: str, addon_name: str) -> types_.ExecResult:
        """Install WordPress addon (plugin/theme).

        Args:
            addon_type (str): ``"theme"`` or ``"plugin"``.
            addon_name (str): name of the addon that needs to be installed.

        Returns:
            Result of installation command.
        """
        self._check_addon_type(addon_type)
        if addon_type == "theme":
            # --force will overwrite any installed version of the theme,
            # without prompting for confirmation
            cmd = ["wp", "theme", "install", addon_name, "--force"]
        else:
            cmd = ["wp", "plugin", "install", addon_name]
        return self._wrapped_run_wp_cli(cmd, timeout=600)

    def _wp_addon_uninstall(self, addon_type: str, addon_name: str) -> types_.ExecResult:
        """Uninstall WordPress addon (theme/plugin).

        Args:
            addon_type (str): ``"theme"`` or ``"plugin"``.
            addon_name (str): name of the addon that needs to be uninstalled.

        Returns:
            Result of uninstallation command.
        """
        self._check_addon_type(addon_type)
        if addon_type == "theme":
            cmd = ["wp", "theme", "delete", addon_name, "--force"]
        else:
            cmd = ["wp", "plugin", "uninstall", addon_name, "--deactivate"]
        return self._wrapped_run_wp_cli(cmd, timeout=600)

    def _addon_reconciliation(self, addon_type: str) -> None:
        """Reconciliation process for WordPress addons (theme/plugin).

        Install and uninstall themes/plugins to match the themes/plugins setting in config.

        Args:
            addon_type (str): ``"theme"`` or ``"plugin"``.

        Raises:
            WordPressBlockedStatusException: if reconcilliation of an addon is unsuccessful.
        """
        self._check_addon_type(addon_type)
        logger.info("Start %s reconciliation process", addon_type)
        current_installed_addons = set(t["name"] for t in self._wp_addon_list(addon_type).result)
        logger.debug("Currently installed %s %s", addon_type, current_installed_addons)
        addons_in_config = [
            t.strip() for t in self.model.config[f"{addon_type}s"].split(",") if t.strip()
        ]
        default_addons = (
            self._WORDPRESS_DEFAULT_THEMES
            if addon_type == "theme"
            else self._WORDPRESS_DEFAULT_PLUGINS
        )
        desired_addons = set(itertools.chain(addons_in_config, default_addons))
        install_addons = desired_addons - current_installed_addons
        uninstall_addons = current_installed_addons - desired_addons
        for addon in install_addons:
            logger.info("Install %s: %s", addon_type, repr(addon))
            result = self._wp_addon_install(addon_type=addon_type, addon_name=addon)
            if not result.success:
                raise exceptions.WordPressBlockedStatusException(
                    f"failed to install {addon_type} {repr(addon)}"
                )
        for addon in uninstall_addons:
            logger.info("Uninstall %s: %s", addon_type, repr(addon))
            result = self._wp_addon_uninstall(addon_type=addon_type, addon_name=addon)
            if not result.success:
                raise exceptions.WordPressBlockedStatusException(
                    f"failed to uninstall {addon_type} {repr(addon)}"
                )

    def _theme_reconciliation(self) -> None:
        """Reconciliation process for WordPress themes.

        Install and uninstall themes to match the themes setting in config.
        """
        self._addon_reconciliation("theme")

    def _wp_option_update(
        self, option: str, value: Union[str, dict], format_: str = "plaintext"
    ) -> types_.ExecResult:
        """Create or update a WordPress option value.

        If the option does not exist, wp option update will create one.

        Args:
            option (str): WordPress option name.
            value (Union[str, dict]): WordPress option value. If the format is ``"plaintext"``,
                then it's a str. If the format is ``"json"``, the value should be a json compatible
                dict.
            format_ (str): ``"plaintext"`` or ``"json"``

        Returns:
            An instance of :attr:`types_.ExecResult`.
        """
        return self._wrapped_run_wp_cli(
            ["wp", "option", "update", option, value, f"--format={format_}"]
        )

    def _wp_option_delete(self, option: str) -> types_.ExecResult:
        """Delete a WordPress option.

        It's not an error to delete a non-existent option (it's a warning though).

        Args:
            option (str): option name.

        Returns:
            An instance of :attr:`types_.ExecResult`.
        """
        return self._wrapped_run_wp_cli(["wp", "option", "delete", option])

    def _wp_plugin_activate(self, plugin: str) -> types_.ExecResult:
        """Activate a WordPress plugin.

        Args:
            plugin (str): plugin slug.

        Returns:
            An instance of :attr:`types_.ExecResult`.
        """
        logger.info("activate plugin %s", repr(plugin))
        return self._wrapped_run_wp_cli(["wp", "plugin", "activate", plugin])

    def _wp_plugin_deactivate(self, plugin: str) -> types_.ExecResult:
        """Deactivate a WordPress plugin.

        Args:
            plugin (str): plugin slug.

        Returns:
            An instance of :attr:`types_.ExecResult`.
        """
        logger.info("deactivate plugin %s", repr(plugin))
        return self._wrapped_run_wp_cli(["wp", "plugin", "deactivate", plugin])

    def _perform_plugin_activate_or_deactivate(
        self, plugin: str, action: str
    ) -> types_.ExecResult:
        """Activate a WordPress plugin or deactivate a WordPress plugin.

        It's not an error to activate an active plugin or deactivate an inactive plugin.

        Args:
            plugin (str): plugin slug.
            action (str): ``"activate"`` or ``"deactivate"``

        Raises:
            ValueError: if invalid plugin action was input.

        Returns:
            An instance of :attr:`types_.ExecResult`.
        """
        if action not in ("activate", "deactivate"):
            raise ValueError(
                f"Unknown activation_status {repr(action)}, " "accept (activate, deactivate)"
            )
        current_plugins = self._wp_addon_list("plugin")
        if not current_plugins.success:
            return types_.ExecResult(
                success=False,
                result=None,
                message=f"failed to list installed plugins while {action} plugin {plugin}",
            )
        current_plugins = current_plugins.result
        current_plugins_activate_status = {p["name"]: p["status"] for p in current_plugins}

        if plugin not in current_plugins_activate_status:
            return types_.ExecResult(
                success=False, result=None, message=f"{action} a non-existent plugin {plugin}"
            )
        is_active = current_plugins_activate_status[plugin] == "active"
        target_activation_status = action == "activate"

        if is_active != target_activation_status:
            if action == "activate":
                result = self._wp_plugin_activate(plugin)
            else:
                result = self._wp_plugin_deactivate(plugin)
            if not result.success:
                return types_.ExecResult(
                    success=False, result=None, message=f"failed to {action} plugin {plugin}"
                )
        return types_.ExecResult(success=True, result=None, message="")

    def _activate_plugin(
        self, plugin: str, options: Dict[str, Union[str, dict]]
    ) -> types_.ExecResult:
        """Activate a WordPress plugin and set WordPress options after activation.

        Args:
            plugin (str): plugin slug.
            options (Dict[str, Union[str, dict])): options related to the plugin, if the value is
                a string, it will be passed as plaintext, else if the value is a dict, the option
                value will be passed as json.

        Returns:
            An instance of :attr:`types_.ExecResult`.
        """
        activate_result = self._perform_plugin_activate_or_deactivate(plugin, "activate")
        if not activate_result.success:
            return activate_result
        for option, value in options.items():
            if isinstance(value, dict):
                option_update_result = self._wp_option_update(
                    option=option, value=json.dumps(value), format_="json"
                )
            else:
                option_update_result = self._wp_option_update(option=option, value=value)
            if not option_update_result.success:
                return types_.ExecResult(
                    success=False,
                    result=None,
                    message=f"failed to update option {option} after activating plugin {plugin}",
                )
        return types_.ExecResult(success=True, result=None, message="")

    def _deactivate_plugin(self, plugin: str, options: List[str]) -> types_.ExecResult:
        """Deactivate a WordPress plugin and delete WordPress options after deactivation.

        Args:
            plugin: plugin slug.
            options: options related to the plugin that need to be removed.

        Returns:
            An instance of :attr:`types_.ExecResult`.
        """
        deactivate_result = self._perform_plugin_activate_or_deactivate(plugin, "deactivate")
        if not deactivate_result.success:
            return deactivate_result
        for option in options:
            option_update_result = self._wp_option_delete(option)
            if not option_update_result.success:
                return types_.ExecResult(
                    success=False,
                    result=None,
                    message=f"failed to delete option {option} after deactivating plugin {plugin}",
                )
        return types_.ExecResult(success=True, result=None, message="")

    def _plugin_akismet_reconciliation(self) -> None:
        """Reconciliation process for the akismet plugin.

        Raises:
            WordPressBlockedStatusException: if askimet plugin reconciliation process fails.
        """
        akismet_key = self.model.config["wp_plugin_akismet_key"].strip()
        if not akismet_key:
            result = self._deactivate_plugin(
                "akismet",
                ["akismet_strictness", "akismet_show_user_comments_approved", "wordpress_api_key"],
            )
        else:
            result = self._activate_plugin(
                "akismet",
                {
                    "akismet_strictness": "0",
                    "akismet_show_user_comments_approved": "0",
                    "wordpress_api_key": akismet_key,
                },
            )
        if not result.success:
            raise exceptions.WordPressBlockedStatusException(
                f"Unable to config akismet plugin, {result.message}"
            )

    def _wp_eval(self, php_code: str):
        """Execute arbitrary PHP code.

        Args:
            php_code: PHP code to be executed.

        Returns:
            An instance of :attr:`types_.ExecResult`.
        """
        return self._wrapped_run_wp_cli(["wp", "eval", php_code])

    @staticmethod
    def _encode_openid_team_map(team_map: str) -> str:
        """Convert wp_plugin_openid_team_map setting to openid_teams_trust_list WordPress option.

        example input: site-sysadmins=administrator,site-editors=editor,site-executives=editor

        Args:
            team_map (str): team definition.

        Returns:
            A PHP array, as a Python string.
        """
        array_items = []
        for idx, mapping in enumerate(team_map.split(","), start=1):
            launchpad_role, wordpress_role = mapping.split("=")
            launchpad_role = launchpad_role.strip()
            wordpress_role = wordpress_role.strip()
            array_items.append(
                f"{idx} => (object) array ("
                f"'id'=>{idx},"
                f"'team'=>'{launchpad_role}',"
                f"'role'=>'{wordpress_role}',"
                f"'server' => '0',),"
            )
        return f"array({''.join(array_items)})"

    def _plugin_openid_reconciliation(self) -> None:
        """Reconciliation process for the openid plugin."""
        openid_team_map = self.model.config["wp_plugin_openid_team_map"].strip()
        result = None

        def check_result():
            """Assert successful result of executed command.

            Raises:
                WordPressBlockedStatusException: if unsuccessful result was returned.
            """
            if not result or not result.success:
                raise exceptions.WordPressBlockedStatusException(
                    f"Unable to config openid plugin, {result.message}"
                )

        if not openid_team_map:
            result = self._wp_option_update("users_can_register", "0")
            check_result()
            result = self._deactivate_plugin(
                "wordpress-teams-integration", ["openid_teams_trust_list"]
            )
            check_result()
            result = self._deactivate_plugin("wordpress-launchpad-integration", [])
            check_result()
            result = self._deactivate_plugin("openid", ["openid_required_for_registration"])
            check_result()
        else:
            result = self._activate_plugin(
                "openid",
                {
                    "openid_required_for_registration": "1",
                },
            )
            check_result()
            result = self._activate_plugin("wordpress-launchpad-integration", {})
            check_result()
            result = self._activate_plugin("wordpress-teams-integration", {})
            check_result()
            result = self._wp_eval(
                "update_option("
                f"'openid_teams_trust_list', {self._encode_openid_team_map(openid_team_map)}"
                ");"
            )
            check_result()
            result = self._wp_option_update("users_can_register", "1")
            check_result()

    def _apache_config_is_enabled(self, conf_name: str) -> bool:
        """Check if a specified apache configuration file is enabled.

        Args:
            conf_name (str): name of the apache config, without trailing ``.conf``.

        Returns:
            True if certain apache config is enabled.
        """
        enabled_config = self._container().list_files("/etc/apache2/conf-enabled")
        return f"{conf_name}.conf" in enabled_config

    def _apache_enable_config(self, conf_name: str, conf: str) -> None:
        """Create and enable an apache2 configuration file.

        Args:
            conf_name (str): name of the apache config, without trailing ``.conf``.
            conf (str): content of the apache config.
        """
        self._stop_server()
        self._container().push(path=f"/etc/apache2/conf-available/{conf_name}.conf", source=conf)
        self._run_cli(["a2enconf", conf_name])
        self._start_server()

    def _apache_disable_config(self, conf_name: str) -> None:
        """Remove and disable a specified apache2 configuration file.

        Args:
            conf_name (str): name of the apache config, without trailing ``.conf``.
        """
        self._stop_server()
        self._container().remove_path(
            f"/etc/apache2/conf-available/{conf_name}.conf", recursive=True
        )
        self._run_cli(["a2disconf", conf_name])
        self._start_server()

    def _swift_config(self) -> Dict[str, Any]:
        """Load swift configuration from charm config.

        The legacy swift plugin options ``url`` or ``prefix`` will be converted to ``swift-url``
        and ``object-prefix`` by this function.

        Raises:
            WordPressBlockedStatusException: if openstack plugin setup process failed.

        Returns:
            Swift configuration in dict.
        """
        swift_config_str = self.model.config["wp_plugin_openstack-objectstorage_config"]
        required_swift_config_key = [
            "auth-url",
            "bucket",
            "password",
            "object-prefix",
            "region",
            "tenant",
            "domain",
            "swift-url",
            "username",
            "copy-to-swift",
            "serve-from-swift",
            "remove-local-file",
        ]
        swift_config = safe_load(swift_config_str)
        if not swift_config:
            return {}
        # legacy version of the WordPress charm accepts the ``url`` options
        # here's an example of the ``url`` option:
        # http://10.126.72.107:8080/v1/AUTH_fa8326b9fd4f405fb1c5eaafe988f5fd/WordPress/wp-content/uploads/
        # which is a combination of swift url, container name, and object prefix
        # the new WordPress charm will only take the swift url
        # TODO: instead of user input, lookup swift url using swift client automatically
        if "url" in swift_config:
            swift_url = swift_config["url"]
            swift_url = re.sub("/wp-content/uploads/?$", "", swift_url)
            swift_url = swift_url[: -(1 + len(swift_config.get("bucket", "")))]
            logger.warning(
                "Convert legacy openstack object storage configuration url (%s) to swift-url (%s)",
                swift_config["url"],
                swift_url,
            )
            del swift_config["url"]
            swift_config["swift-url"] = swift_url
        # rename the prefix in swift config to object-prefix as it's in the swift plugin option
        if "prefix" in swift_config:
            object_prefix = swift_config["prefix"]
            logger.warning(
                "Convert legacy openstack object storage configuration prefix (%s) to object-prefix (%s)",
                object_prefix,
                object_prefix,
            )
            del swift_config["prefix"]
            swift_config["object-prefix"] = object_prefix
        for key in required_swift_config_key:
            if key not in swift_config:
                raise exceptions.WordPressBlockedStatusException(
                    f"missing {key} in wp_plugin_openstack-objectstorage_config"
                )
        return swift_config

    def _config_swift_plugin(self, swift_config: Dict[str, Any]) -> None:
        """Activate or deactivate the swift plugin based on the swift config in the charm config.

        Args:
            swift_config: swift configuration parsed from wp_plugin_openstack-objectstorage_config
                config. Use :meth:`WordpressCharm._swift_config` to get the parsed swift config.

        Raises:
            WordPressBlockedStatusException: if configuration of openstack objectstorage failed.
        """
        if not swift_config:
            result = self._deactivate_plugin("openstack-objectstorage-k8s", ["object_storage"])
        else:
            result = self._activate_plugin(
                "openstack-objectstorage-k8s", {"object_storage": swift_config}
            )
        if not result.success:
            raise exceptions.WordPressBlockedStatusException(
                f"Unable to config openstack-objectstorage-k8s plugin, {result.message}"
            )

    def _plugin_swift_reconciliation(self) -> None:
        """Reconciliation process for swift object storage (openstack-objectstorage-k8s) plugin."""
        swift_config = self._swift_config()
        if self.unit.is_leader():
            self._config_swift_plugin(swift_config)
        apache_swift_conf = "docker-php-swift-proxy"
        swift_apache_config_enabled = self._apache_config_is_enabled(apache_swift_conf)
        if swift_config and not swift_apache_config_enabled:
            swift_url = swift_config.get("swift-url")
            bucket = swift_config.get("bucket")
            object_prefix = swift_config.get("object-prefix")
            redirect_url = os.path.join(swift_url, bucket, object_prefix)
            conf = textwrap.dedent(
                f"""\
            SSLProxyEngine on
            ProxyPass /wp-content/uploads/ {redirect_url}
            ProxyPassReverse /wp-content/uploads/ {redirect_url}
            Timeout 300
            """
            )
            self._apache_enable_config(apache_swift_conf, conf)
        elif not swift_config and swift_apache_config_enabled:
            self._apache_disable_config(apache_swift_conf)

    def _are_pebble_instances_ready(self) -> bool:
        """Check if all pebble instances are up and containers available.

        Returns:
            If the containers are up and available.
        """
        return all(
            self.unit.get_container(container_name).can_connect()
            for container_name in self.model.unit.containers
        )

    def _plugin_reconciliation(self) -> None:
        """Reconciliation process for WordPress plugins.

        Install and uninstall plugins to match the plugins setting in config.
        Activate and deactivate three charm managed plugins (akismet, openid, openstack-swift)
        and adjust plugin options for these three plugins according to charm config.
        """
        self._addon_reconciliation("plugin")
        self._plugin_swift_reconciliation()
        if self.unit.is_leader():
            self._plugin_akismet_reconciliation()
            self._plugin_openid_reconciliation()

    def _storage_mounted(self) -> bool:
        """Check if the upload storage mounted in the wordpress container.

        Returns:
            True if the storage "upload" is attached to the container.
        """
        container = self._container()
        if not container.can_connect():
            return False
        mount_info: str = container.pull("/proc/mounts").read()
        return "/var/www/html/wp-content/uploads" in mount_info

    def _reconciliation(self, _event: EventBase) -> None:
        """Reconcile the WordPress charm on juju event.

        Args:
            _event: Event fired by juju on WordPress charm related state change.
        """
        logger.info("Start reconciliation process, triggered by %s", _event)
        if not self.state.started:
            logger.info("Charm hasn't started yet, reconciliation deferred")
            self.unit.status = WaitingStatus("Waiting for charm start")
            _event.defer()
            return
        if not self._container().can_connect():
            logger.info("Reconciliation process terminated early, pebble is not ready")
            self.unit.status = WaitingStatus("Waiting for pebble")
            return
        if not self._storage_mounted():
            logger.info("Storage is not ready, reconciliation deferred")
            self.unit.status = WaitingStatus("Waiting for storage")
            _event.defer()
            return
        try:
            self._core_reconciliation()
            self._theme_reconciliation()
            self._plugin_reconciliation()
            logger.info("Reconciliation process finished successfully.")
        except exceptions.WordPressStatusException as status_exception:
            logger.info("Reconciliation process terminated early, reason: %s", status_exception)
            self.unit.status = status_exception.status
            return
        if self._are_pebble_instances_ready():
            self.unit.status = ActiveStatus()
        else:
            self.unit.status = WaitingStatus("Waiting for pebble")

    def _on_apache_prometheus_exporter_pebble_ready(self, event: PebbleReadyEvent):
        """Configure and start apache prometheus exporter.

        Args:
            event: Event triggering the handler.
        """
        if not event.workload:
            self.unit.status = BlockedStatus("Internal Error, pebble container not found.")
            return
        container = event.workload
        pebble: ops.pebble.Client = container.pebble
        self.unit.status = MaintenanceStatus(f"Adding {container.name} layer to pebble")
        container.add_layer(container.name, PROM_EXPORTER_PEBBLE_CONFIG, combine=True)
        self.unit.status = MaintenanceStatus(f"Starting {container.name} container")
        pebble.replan_services()
        self._reconciliation(event)


if __name__ == "__main__":  # pragma: no cover
    main(WordpressCharm)
