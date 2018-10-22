from pprint import pprint
import yaml

from charms.layer import caas_base, status
from charms import reactive
from charms.reactive import hook, when_not
from charmhelpers.core import hookenv


# Run the create_container handler again whenever the config or
# database relation changes.
reactive.register_trigger(when='config.changed', clear_flag='container.configured')
reactive.register_trigger(when='db.master.changed', clear_flag='container.configured')


@hook('upgrade-charm')
def upgrade_charm():
    reactive.clear_flag('container.configured')


@when_not('container.configured')
# @when('db.master.available') Portal is not using relations to its databases, but it could be.
def config_container():
    status.maintenance('configuring container')
    spec = make_pod_spec()
    if caas_base.pod_spec_set(spec):
        reactive.set_flag('container.configured')
    else:
        status.blocked('k8s spec deployment failed. Check logs with kubectl')


def make_pod_spec():
    config = yaml.safe_load(hookenv.config()['container_config'])

    # http://interface-pgsql.readthedocs.io on the PostgreSQL interface
    # ep = reactive.endpoint_from_flag('db.master.available')
    # conn_str = ep.master
    # dbname, host, port = ep.dbname, ep.host, ep.port

    # Grab the details from resource-get.
    image_details_path = hookenv.resource_get("image")
    if not image_details_path:
        raise Exception("unable to retrieve image details")

    with open(image_details_path, "r") as f:
        image_details = yaml.safe_load(f)

    docker_image_path = image_details['registrypath']
    docker_image_username = image_details['username']
    docker_image_password = image_details['password']

    spec = {
        'containers': [
            {
                'name': hookenv.charm_name(),
                'imageDetails': {
                    'imagePath': docker_image_path,
                    'username': docker_image_username,
                    'password': docker_image_password,
                },
                'ports': [{'name': 'django_http', 'containerPort': 80, 'protocol': 'TCP'}],
                'config': config,
                # 'files': [
                #     {
                #         'name': 'configs',
                #         'mountPath': '/etc/config',
                #         'files': {
                #             'my-charm.conf': open('files/my-charm.conf', 'r').read().decode(),
                #         },
                #     },
                # ],
            },
        ],
    }
    print("\nSpec:\n")
    pprint(spec)

    # Add secrets, now spec logged. TODO: Use real secret management, rather than charm config.
    secrets = yaml.safe_load(hookenv.config()['container_secrets'])
    for k, v in secrets.items():
        config[k] = v
    spec['containers'][0]['config'] = config

    return spec


# @when_not('db.connected')
# def db_not_connected():
#     status.blocked('charm requires a PostgreSQL relation')
#
#
# @when('db.connected')
# def db_connected():
#     ep = reactive.endpoint_from_flag('db.connected')
#     ep.set_database('tasticles')
#     ep.set_extensions(['citext'])
