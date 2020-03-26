#!/usr/bin/env python3

import io
import re
import requests
import sys
from pprint import pprint
from urllib.parse import urlparse, urlunparse
from yaml import safe_load

sys.path.append("lib")

from ops.charm import CharmBase  # NoQA: E402
from ops.framework import StoredState  # NoQA: E402
from ops.main import main  # NoQA: E402
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus  # NoQA: E402


class Wordpress(CharmBase):
    state = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        for event in (
            self.on.install,
            self.on.start,
            self.on.upgrade_charm,
            self.on.update_status,
            self.on.config_changed,
        ):
            self.framework.observe(event, self)

    def on_start(self, event):
        self.state._started = True

    def on_upgrade_charm(self, event):
        self.on_config_changed(event)

    def on_config_changed(self, event):
        valid = True
        config = self.model.config
        for k in ["image", "db_host", "db_name", "db_user", "db_password"]:
            if config[k].strip() == "":
                self.model.unit.status = BlockedStatus("{!r} config is required".format(k))
                valid = False
        self.state._valid = valid
        self.configure_pod(event)

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
                }
            ]
        }
        out = io.StringIO()
        pprint(spec, out)
        # TODO.log("Container environment config (sans secrets) <<EOM\n{}\nEOM".format(out.getvalue()))

        # If we need credentials (secrets) for our image, add them to the spec after logging
        if config.get("image_user") and config.get("image_pass"):
            spec.get("containers")[0].get("imageDetails")["username"] = config["image_user"]
            spec.get("containers")[0].get("imageDetails")["password"] = config["image_pass"]

        config_with_secrets = self.full_container_config()
        if config_with_secrets is None:
            return None  # Status already set
        container_config.update(config_with_secrets)

        return spec

    def first_install(self):
        """Perform initial configuration of wordpress if needed."""
        config = self.model.config
        if not self.is_pod_up("website"):
            # TODO.log("Pod not yet ready - retrying")
            return False
        elif not self.is_vhost_ready():
            # TODO.log("Wordpress vhost is not yet listening - retrying")
            return False
        elif self.wordpress_configured() or not config["initial_settings"]:
            # TODO.log("No initial_setting provided or wordpress already configured. Skipping first install.")
            return True
        # TODO.log("Starting wordpress initial configuration")
        payload = {
            # "admin_password": host.pwgen(24), ## TODO: pwgen
            "admin_password": "letmein123",
            "blog_public": "checked",
            "Submit": "submit",
        }
        payload.update(safe_load(config["initial_settings"]))
        payload["admin_password2"] = payload["admin_password"]
        if not payload["blog_public"]:
            payload["blog_public"] = "unchecked"
        required_config = set(("user_name", "admin_email"))
        missing = required_config.difference(payload.keys())
        if missing:
            # TODO.log("Error: missing wordpress settings: {}".format(missing))
            return False
        self.call_wordpress("/wp-admin/install.php?step=2", redirects=True, payload=payload)
        # TODO: write_file
        # host.write_file(os.path.join("/root/", "initial.passwd"), payload["admin_password"], perms=0o400)
        return True

    def call_wordpress(self, uri, redirects=True, payload={}, _depth=1):
        max_depth = 10
        if _depth > max_depth:
            # TODO.log("Redirect loop detected in call_worpress()")
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
            # TODO.log("Error getting service IP")
            return False

    def wordpress_configured(self):
        """Check whether first install has been completed."""
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
            # TODO.log("MySQL database setup failed, we likely have no wp-config.php")
            self.model.unit.status = BlockedStatus("MySQL database setup failed, we likely have no wp-config.php")
            return False
        else:
            return True

    def is_vhost_ready(self):
        """Check whether wordpress is available using http."""
        # Check if we have WP code deployed at all
        try:
            r = self.call_wordpress("/wp-login.php", redirects=False)
        except requests.exceptions.ConnectionError:
            # TODO.log("call_wordpress() returned requests.exceptions.ConnectionError")
            return False
        if r is None:
            # TODO.log("call_wordpress() returned None")
            return False
        if hasattr(r, "status_code") and r.status_code in (403, 404):
            # TODO.log("call_wordpress() returned status {}".format(r.status_code))
            return False
        else:
            return True

    def get_service_ip(self, endpoint):
        try:
            # TODO: replacement for network_get
            # info = hookenv.network_get(endpoint, hookenv.relation_id())
            info = ''  # BROKEN!
            if "ingress-addresses" in info:
                addr = info["ingress-addresses"][0]
                if len(addr):
                    return addr
            else:
                # TODO.log("No ingress-addresses: {}".format(info))
                pass
        except Exception as e:
            # TODO.log("Caught exception checking for service IP: {}".format(e))
            pass

        return None

    def is_pod_up(self, endpoint):
        """Check to see if the pod of a relation is up.

        application-vimdb: 19:29:10 INFO unit.vimdb/0.juju-log network info

        In the example below:
        - 10.1.1.105 is the address of the application pod.
        - 10.152.183.199 is the service cluster ip

        {
            'bind-addresses': [{
                'macaddress': '',
                'interfacename': '',
                'addresses': [{
                    'hostname': '',
                    'address': '10.1.1.105',
                    'cidr': ''
                }]
            }],
            'egress-subnets': [
                '10.152.183.199/32'
            ],
            'ingress-addresses': [
                '10.152.183.199',
                '10.1.1.105'
            ]
        }
        """
        try:
            # TODO: replacement for network_get
            # info = hookenv.network_get(endpoint, hookenv.relation_id())
            info = ''

            # Check to see if the pod has been assigned its internal and external ips
            for ingress in info["ingress-addresses"]:
                if len(ingress) == 0:
                    return False
        except Exception:
            return False
        return True

    def configure_pod(self, event):
        if not self._started:
            return
        if not self._valid:
            return
        elif self.model.unit.is_leader():
            # only the leader can set_spec()
            spec = self.make_pod_spec()
            if spec is None:
                return  # Status already set
            # TODO: Figured out operator equivalent of reactive.data_changed()
            # if reactive.data_changed("wordpress.spec", spec):
            if True:
                self.model.unit.status = MaintenanceStatus("Configuring container")
                try:
                    self.model.pod.set_spec(spec)
                except Exception as e:
                    # TODO.log("pod_spec_set failed: {}".format(e))
                    self.model.unit.status = BlockedStatus("pod_spec_set failed! Check logs and k8s dashboard.")
                    return
            else:
                # TODO.log("No changes to pod spec")
                pass
            if self.first_install():
                self.state._configured = True
                self.model.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(Wordpress)
