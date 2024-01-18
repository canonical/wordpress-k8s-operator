# Containers

The core component of wordpress-k8s charm consists of a wordpress-k8s main workload container with an Apache Prometheus exporter. The services inside the container are driven by
Pebble, a lightweight API-driven process supervisor that controls the lifecycle of a service.
Learn more about pebble and its layer configurations [here](https://github.com/canonical/pebble).

### wordpress

This container runs the main workload of the charm. The OCI image is custom built and includes
the WordPress cli, Apache server and default WordPress plugins and themes. By
default, Apache server accepts all the web traffic on port 80 and redirects the requests to
WordPress php index file, handled by the default `x-httpd-php` handler. The configuration of the
Apache server redirects can be found in
[`files/docker-php.conf`](https://github.com/canonical/wordpress-k8s-operator/blob/main/files/docker-php.conf)
file.

WordPress, by default, stores uploaded content files locally at `/wp-content/uploads` directory.
To make the content accessible across WordPress replication servers, a swift-proxy is added to
enable content storage on OpenStack Swift through the use of
`wp_plugin_openstack-objectstorage_config` configuration parameter. Swift proxy settings can be found
in [`files/docker-php-swift-proxy.conf`](https://github.com/canonical/wordpress-k8s-operator/blob/main/files/docker-php-swift-proxy.conf)
in the repository. The settings are dynamically modified during runtime when the
`wp_plugin_openstack-objectstorage_config` parameter is configured.

In order to enable monitoring of Apache server status, redirection to WordPress php for route
`/server-status` is overridden in
[`files/apache2.conf`](https://github.com/canonical/wordpress-k8s-operator/blob/main/files/apache2.conf).
`/server-status` endpoint is accessed by `apache-exporter` service to convert and re-expose with
open metrics compliant format for integration with `prometheus_scrape` interface.

When a logging relation is joined, a promtail application is started via pebble which starts
pushing Apache server logs to Loki. The configurations for Apache have been set up to stream logs
to both `access.log`, `error.log` files and container logs in
[`000-default.conf`](https://github.com/canonical/wordpress-k8s-operator/blob/main/files/000-default.conf).
These files are essential for promtail to read and push latest logs to loki periodically.

### charm

This container is the main point of contact with the juju controller. It communicates with juju to
run necessary charm code defined by the main `src/charm.py`. The source code is copied to the
`/var/lib/juju/agents/unit-UNIT_NAME/charm` directory.