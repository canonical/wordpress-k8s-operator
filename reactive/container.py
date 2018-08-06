import yaml

from charms.layer import caas_base
from charms import reactive
from charms.reactive import when, when_not
from charmhelpers.core import hookenv


# Run the create_container handler again whenever the config or
# database relation changes.
reactive.register_trigger(when='config.changed', clear_flag='container.configured')
reactive.register_trigger(when='db.master.changed', clear_flag='container.configured')


@when_not('container.configured')
# @when('db.master.available') Portal is not using relations to its databases, but it could be.
def create_container():
    hookenv.status_set('maintenance', 'configuring container')

    image = hookenv.config()['image']

    config = yaml.safe_load(hookenv.config()['container_config'])
    secrets = yaml.safe_load(hookenv.config()['container_secrets'])

    for k, v in secrets.items():
        config[k] = v

    # http://interface-pgsql.readthedocs.io on the PostgreSQL interface
    # ep = reactive.endpoint_from_flag('db.master.available')
    # conn_str = ep.master
    # dbname, host, port = ep.dbname, ep.host, ep.port

    caas_base.pod_spec_set({
        'containers': [
            {
                'name': hookenv.charm_name(),
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
    })
    reactive.set_flag('container.configured')


@when_not('db.connected')
def db_not_connected():
    hookenv.status_set('blocked', 'charm requires a PostgreSQL relation')


@when('db.connected')
def db_connected():
    ep = reactive.endpoint_from_flag('db.connected')
    ep.set_database('tasticles')
    ep.set_extensions(['citext'])
