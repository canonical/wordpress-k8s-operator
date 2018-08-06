from pprint import pprint
import yaml

from charms.layer import caas_base
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
def create_container():
    image = hookenv.config()['image']
    hookenv.status_set('maintenance', 'configuring {}'.format(image))

    config = yaml.safe_load(hookenv.config()['container_config'])

    print("Config:\n")
    pprint(config)
    secrets = yaml.safe_load(hookenv.config()['container_secrets'])

    for k, v in secrets.items():
        config[k] = v

    # http://interface-pgsql.readthedocs.io on the PostgreSQL interface
    # ep = reactive.endpoint_from_flag('db.master.available')
    # conn_str = ep.master
    # dbname, host, port = ep.dbname, ep.host, ep.port

    spec = {
        'containers': [
            {
                'name': hookenv.charm_name(),
                'image': image,
                'imageDetails': {
                    'imagePath': image,
                    # 'username': 'username',
                    # 'password': 'password',
                },
                'ports': [{'name': 'the_port_name', 'containerPort': 80}],
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
    if caas_base.pod_spec_set(spec):
        reactive.set_flag('container.configured')
        hookenv.status_set('maintenance', 'launching {}'.format(image))
    else:
        hookenv.status_set('blocked', 'k8s spec deployment failed. Check logs with kubectl')


# @when_not('db.connected')
# def db_not_connected():
#     hookenv.status_set('blocked', 'charm requires a PostgreSQL relation')
#
#
# @when('db.connected')
# def db_connected():
#     ep = reactive.endpoint_from_flag('db.connected')
#     ep.set_database('tasticles')
#     ep.set_extensions(['citext'])
