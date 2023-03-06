# Integrations

### db

_Interface_: mysql  
_Supported charms_: [charmed-osm-mariadb-k8s](https://charmhub.io/charmed-osm-mariadb-k8s),
[mysql-k8s](https://charmhub.io/mysql-k8s)

Database integration is a required relation for the wordpress-k8s charm to supply structured data
storage for WordPress. It is recommended to use a juju native integration that provides a mysql
interface by providing `mysql-interface-user` and `mysql-interface-database` parameters to
wordpress-k8s charm configurations. See
[configuration](https://charmhub.io/wordpress-k8s/configure) for more detail.
Another way to establish database relation is to supply `db_host`, `db_name`, `db_user`, `db_password`
configuration parameters to the charm with a MySQL database. See Configuration section for detailed
information regarding each of the parameters.

### ingress

_Interface_: ingress  
_Supported charms_: [nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator)

Ingress manages external http/https access to services in a kubernetes cluster.
Ingress relation through [nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator)
charm enables additional `blog_hostname` and `use_nginx_ingress_modesec` configurations. Note that the
kubernetes cluster must already have an nginx ingress controller already deployed. Documentation to
enable ingress in microk8s can be found [here](https://microk8s.io/docs/addon-ingress).

Example ingress relate command: `juju relate wordpress-k8s nginx-ingress-integrator`

### metrics-endpoint

_Interface_: [prometheus_scrape](https://charmhub.io/interfaces/prometheus_scrape-v0)  
_Supported charms_: [prometheus-k8s](https://charmhub.io/prometheus-k8s)

Metrics-endpoint relation allows scraping the `/metrics` endpoint provided by apache-exporter sidecar
on port 9117, which provides apache metrics from apache’s `/server-status` route. This internal
apache’s `/server-status` route is not exposed and can only be accessed from within the same
Kubernetes pod. The metrics are exposed in the [open metrics format](https://github.com/OpenObservability/OpenMetrics/blob/main/specification/OpenMetrics.md#data-model) and will only be scraped by Prometheus once the relation becomes active. For more
information about the metrics exposed, please refer to the apache-exporter [documentation](https://github.com/Lusitaniae/apache_exporter#collectors).

Metrics-endpoint relate command: `juju relate wordpress-k8s prometheus-k8s`

### logging

_Interface_: loki_push_api  
_Supported charms_: [loki-k8s](https://charmhub.io/loki-k8s)

Logging relation through the `loki_push_api` interface installs and runs promtail which ships the
contents of local logs found at `/var/log/apache2/access.log` and `/var/log/apache2/error.log` to Loki.
This can then be queried through the loki api or easily visualized through Grafana.

Logging-endpoint relate command: `juju relate wordpress-k8s loki-k8s`

### grafana-dashboard

_Interface_: grafana-dashboard  
_Supported charms_: [grafana-k8s](https://charmhub.io/grafana-k8s)

Grafana-dashboard relation enables quick dashboard access already tailored to fit the needs of
operators to monitor the charm. The template for the Grafana dashboard for wordpress-k8s charm can
be found at `/src/grafana_dashboards/wordpress.json`. In Grafana UI, it can be found as “WordPress
Operator Overview” under the General section of the dashboard browser(`/dashboards`). Modifications
to the dashboard can be made but will not be persisted upon restart/redeployment of the charm.

Grafana-Prometheus relate command: `juju relate grafana-k8s:grafana-source prometheus-k8s:grafana-source`  
Grafana-dashboard relate command: `juju relate wordpress-k8s grafana-dashboard`
