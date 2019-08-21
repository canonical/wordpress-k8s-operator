import io
from pprint import pprint
import yaml

from charms.layer import caas_base, status
from charms import reactive
from charms.reactive import hook, when, when_not
from charmhelpers.core import hookenv


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
    for k in ["image", "db_host", "db_user", "db_password"]:
        if config[k].strip() == "":
            status.blocked("{!r} config is required".format(k))
            valid = False

    reactive.toggle_flag("wordpress.config.valid", valid)


@when("wordpress.config.valid")
@when_not("wordpress.configured")
def config_container():
    spec = make_pod_spec()
    if spec is None:
        return  # status already set
    if reactive.data_changed("wordpress.spec", spec):
        status.maintenance("configuring container")
        caas_base.pod_spec_set(spec)  # Raises an exception on failure. Might change.
    else:
        hookenv.log("No changes to pod spec")
    reactive.set_flag("wordpress.configured")


def sanitized_container_config():
    """Uninterpolated container config without secrets"""
    config = hookenv.config()
    if config["container_config"].strip() == "":
        container_config = {}
    else:
        container_config = yaml.safe_load(config["container_config"])
        if not isinstance(container_config, dict):
            status.blocked("container_config is not a YAML mapping")
            return None
    container_config["WORDPRESS_DB_HOST"] = config["db_host"]
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
        container_secrets = yaml.safe_load(config["container_secrets"])
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

    ports = [{"name": "http", "containerPort": 80, "protocol": "TCP"}]

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
