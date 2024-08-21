# Lifecycle Events

Juju events allow progression of the charm in its lifecycle and encapsulates part of the execution
context of a charm. Below is the list of observed events for wordpress-k8s charm with how the charm
reacts to the event. For more information about the charm’s lifecycle in general, refer to the
charm’s life [documentation](https://juju.is/docs/sdk/a-charms-life#heading--the-graph).

### start

This event marks the charm’s state as started. The charm’s running state must be persisted by the
charm in its own state. See the documentation on the
[start event](https://juju.is/docs/sdk/start-event).

### uploads_storage_attached

This event marks the charm’s storage availability. The name of the event derived from the name of
the storage noted in the `metadata.yaml` configuration under "storage" key.
`containers.wordpress.mounts.storage` and `storage.uploads` section. The storage filesystem maps to
`/var/www/html/wp-content/uploads` directory of the WordPress application, which is used to store
uploaded content from the WordPress user.

### leader_elected

This event is fired when Juju elects a leader unit among the replica peers. Wordpress-k8s charm
then responds by setting up secrets and sharing them with peers through peer relation databag if
not already set.

### config-changed

WordPress-k8s charm reacts to any configuration change and runs reconciliation between the current
state and the desired state. See the list of
[configurations](https://charmhub.io/wordpress-k8s/configure).

### wordpress_pebble_ready

When this event is fired, wordpress-k8s charm installs, configures and starts Apache server for
WordPress through Pebble if the storage is available. Configurations that are set dynamically
include database connection and secrets used by the WordPress application. Dynamic configurations
are modified in `wp-config.php` file and the changes are pushed through Pebble.

### apache_prometheus_exporter_pebble_ready

This event signals that the `apache_prometheus_exporter` container is ready in the pod. Apache
prometheus exporter service is then started through Pebble.

### wordpress-replica_relation_changed

When any of the relation is changed, wordpress-k8s charm must run reconciliation between the
current state and the desired state with new relation data to synchronize the replication
instances. The reconciliation process is divided into 3 distinct steps: core, theme and plugin
reconciliation. Core reconciliation setups up the necessary WordPress application configuration:
secrets and database connection. Theme and Plugin respectively reconcile between currently
installed themes and plugins with the incoming list of themes and plugins.

### upgrade-charm

The `upgrade-charm` event is fired on the upgrade charm command `juju refresh wordpress-k8s`. The command sets up
secrets in peer-relation databag for upgraded deployment of WordPress if it was not already set.
