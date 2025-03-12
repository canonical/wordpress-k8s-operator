# Integrations

### ingress

_Interface_: ingress  
_Supported charms_: [nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator)

Ingress manages external http/https access to services in a kubernetes cluster.
Ingress relation through [nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator)
charm enables additional `blog_hostname` and `use_nginx_ingress_modesec` configurations. Note that the
kubernetes cluster must already have an nginx ingress controller already deployed. Documentation to
enable ingress in microk8s can be found [here](https://microk8s.io/docs/addon-ingress).

Example ingress integrate command: 
```
juju integrate wordpress-k8s nginx-ingress-integrator
```

### metrics-endpoint

_Interface_: [prometheus_scrape](https://charmhub.io/interfaces/prometheus_scrape-v0)  
_Supported charms_: [prometheus-k8s](https://charmhub.io/prometheus-k8s)

Metrics-endpoint relation allows scraping the `/metrics` endpoint provided by apache-exporter sidecar
on port 9117, which provides apache metrics from apache’s `/server-status` route. This internal
apache’s `/server-status` route is not exposed and can only be accessed from within the same
Kubernetes pod. The metrics are exposed in the [open metrics format](https://github.com/OpenObservability/OpenMetrics/blob/main/specification/OpenMetrics.md#data-model) and will only be scraped by Prometheus once the relation becomes active. For more
information about the metrics exposed, please refer to the apache-exporter [documentation](https://github.com/Lusitaniae/apache_exporter#collectors).

Metrics-endpoint integrate command: 
```
juju integrate wordpress-k8s prometheus-k8s
```

### logging

_Interface_: loki_push_api  
_Supported charms_: [loki-k8s](https://charmhub.io/loki-k8s)

Logging relation through the `loki_push_api` interface installs and runs promtail which ships the
contents of local logs found at `/var/log/apache2/access.log` and `/var/log/apache2/error.log` to Loki.
This can then be queried through the loki api or easily visualized through Grafana.

Logging-endpoint integrate command: 
```
juju integrate wordpress-k8s loki-k8s
```

### grafana-dashboard

_Interface_: grafana-dashboard  
_Supported charms_: [grafana-k8s](https://charmhub.io/grafana-k8s)

Grafana-dashboard relation enables quick dashboard access already tailored to fit the needs of
operators to monitor the charm. The template for the Grafana dashboard for wordpress-k8s charm can
be found at `/src/grafana_dashboards/wordpress.json`. In Grafana UI, it can be found as “WordPress
Operator Overview” under the General section of the dashboard browser (`/dashboards`). Modifications
to the dashboard can be made but will not be persisted upon restart/redeployment of the charm.

Grafana-Prometheus integrate command: 
```
juju integrate grafana-k8s:grafana-source prometheus-k8s:grafana-source
```  
Grafana-dashboard integrate command: 
```
juju integrate wordpress-k8s grafana-dashboard
```

### database:

_Interface_: mysql_client    
_Supported charms_: [Charmed MySQL](https://charmhub.io/mysql), [Charmed MySQL-K8s](https://charmhub.io/mysql-k8s)

Database endpoint can be related to mysql based charms, providing long term storage for wordpress.
Database relation connect wordpress-k8s with charms that support the `mysql_client` interface on port 3306
in the database side.

Example database integrate command: 
```
juju integrate wordpress-k8s:database mysql-k8s:database
```