import io
import os
import random
import re
import requests
import string
from pprint import pprint
from urllib.parse import urlunparse
from yaml import safe_load

from charmhelpers.core import host, hookenv
from charms import reactive
from charms.layer import caas_base, status
from charms.osm.k8s import is_pod_up, get_service_ip
from charms.reactive import hook, when, when_not


@hook("upgrade-charm")
def upgrade_charm():
    reactive.clear_flag("wordpress.configured")


@when("config.changed")
def reconfig():
    status.maintenance("charm configuration changed")
    reactive.clear_flag("wordpress.configured")

    # Validate config
    valid = True
    config = hookenv.config()
    # Ensure required strings
    for k in ["image", "db_host", "db_name", "db_user", "db_password"]:
        if config[k].strip() == "":
            status.blocked("{!r} config is required".format(k))
            valid = False

    reactive.toggle_flag("wordpress.config.valid", valid)


@when("wordpress.config.valid")
@when_not("wordpress.configured")
def deploy_container():
    spec = make_pod_spec()
    if spec is None:
        return  # status already set
    if reactive.data_changed("wordpress.spec", spec):
        status.maintenance("configuring container")
        try:
            caas_base.pod_spec_set(spec)
        except Exception:
            status.blocked("pod_spec_set failed! Check logs and k8s dashboard.")
            return
    else:
        hookenv.log("No changes to pod spec")
    if first_install():
        reactive.set_flag("wordpress.configured")


@when("wordpress.configured")
def ready():
    status.active("Ready")


def sanitized_container_config():
    """Uninterpolated container config without secrets"""
    config = hookenv.config()
    if config["container_config"].strip() == "":
        container_config = {}
    else:
        container_config = safe_load(config["container_config"])
        if not isinstance(container_config, dict):
            status.blocked("container_config is not a YAML mapping")
            return None
    container_config["WORDPRESS_DB_HOST"] = config["db_host"]
    container_config["WORDPRESS_DB_NAME"] = config["db_name"]
    container_config["WORDPRESS_DB_USER"] = config["db_user"]
    return container_config


def full_container_config():
    """Uninterpolated container config with secrets"""
    config = hookenv.config()
    container_config = sanitized_container_config()
    if container_config is None:
        return None
    if config["container_secrets"].strip() == "":
        container_secrets = {}
    else:
        container_secrets = safe_load(config["container_secrets"])
        if not isinstance(container_secrets, dict):
            status.blocked("container_secrets is not a YAML mapping")
            return None
    container_config.update(container_secrets)
    container_config["WORDPRESS_DB_PASSWORD"] = config["db_password"]
    return container_config


def make_pod_spec():
    config = hookenv.config()
    container_config = sanitized_container_config()
    if container_config is None:
        return  # status already set

    ports = [
        {"name": name, "containerPort": int(port), "protocol": "TCP"}
        for name, port in [addr.split(":", 1) for addr in config["ports"].split()]
    ]

    # PodSpec v1? https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.13/#podspec-v1-core
    spec = {
        "containers": [
            {"name": hookenv.charm_name(), "image": config["image"], "ports": ports, "config": container_config}
        ]
    }
    out = io.StringIO()
    pprint(spec, out)
    hookenv.log("Container spec (sans secrets) <<EOM\n{}\nEOM".format(out.getvalue()))

    # Add the secrets after logging
    config_with_secrets = full_container_config()
    if config_with_secrets is None:
        return None  # status already set
    container_config.update(config_with_secrets)

    return spec


def first_install():
    """Perform initial configuration of wordpress if needed."""
    config = hookenv.config()
    if not is_pod_up("website"):
        hookenv.log("Pod not yet ready - retrying")
        return False
    elif wordpress_configured() or not config["initial_settings"]:
        hookenv.log("No initial_setting provided or wordpress already configured. Skipping first install.")
        return True
    elif not vhost_ready():
        hookenv.log("Wordpress vhost is not yet listening - retrying")
        return False
    hookenv.log("Starting wordpress initial configuration")
    # TODO: more of the below ought to be configurable
    payload = {"admin_password": mkpasswd(24), "blog_public": "checked", "Submit": "submit"}
    payload.update(safe_load(config["initial_settings"]))
    payload["admin_password2"] = payload["admin_password"]
    if not payload["blog_public"]:
        payload["blog_public"] = "unchecked"
    required_config = set(("user_name", "admin_email"))
    missing = required_config.difference(payload.keys())
    if missing:
        hookenv.log("Error: missing wordpress settings: {}".format(missing))
        return False
    call_wordpress("/wp-admin/install.php?step=2", payload=payload)
    host.write_file(os.path.join("/root/", "initial.passwd"), payload["admin_password"], perms=0o400)
    return True


def mkpasswd(length=64):
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(length))


def call_wordpress(uri, redirects=True, payload={}):
    config = hookenv.config()
    service_ip = get_service_ip("website")
    if service_ip:
        headers = {"Host": config["blog_hostname"]}
        url = urlunparse((
            'http',
            service_ip,
            uri,
            '',
            '',
            ''
        ))
        if payload:
            return requests.post(url, allow_redirects=redirects, headers=headers, data=payload)
        else:
            return requests.get(url, allow_redirects=redirects, headers=headers)
    else:
        hookenv.log("Error getting service IP")
        return False


class wordpress_configured(dict):
    """Check whether first install has been completed."""

    def __bool__(self):
        # Check whether pod is deployed
        if not is_pod_up("website"):
            return False
        # Check if we have WP code deployed at all
        if not vhost_ready():
            return False
        # We have code on disk, check if configured
        try:
            r = call_wordpress("/", redirects=False)
        except requests.exceptions.ConnectionError:
            return False
        if r.status_code == 302 and re.match("^.*/wp-admin/install.php", r.headers.get("location", "")):
            return False
        else:
            return True

    def __nonzero__(self):
        return self.__bool__()

    def is_ready(self):
        return self.__bool__()


class vhost_ready(dict):
    """Check whether wordpress is available using http."""

    def __bool__(self):
        # Check if we have WP code deployed at all
        try:
            r = call_wordpress("/wp-login.php", redirects=False)
        except requests.exceptions.ConnectionError:
            return False
        if r.status_code in (403, 404):
            return False
        else:
            return True

    def __nonzero__(self):
        return self.__bool__()

    def is_ready(self):
        return self.__bool__()
