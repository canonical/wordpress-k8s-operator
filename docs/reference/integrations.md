# Relation endpoints

### database

_Interface_: mysql_client    
_Supported charms_: [Charmed MySQL](https://charmhub.io/mysql), [Charmed MySQL-K8s](https://charmhub.io/mysql-k8s)

The database endpoint can be integrated with MySQL based charms, providing long term storage for WordPress.
Database relation connects wordpress-k8s with charms that support the `mysql_client` interface on port 3306
in the database side.

Example database integrate command: 
```
juju integrate wordpress-k8s:database mysql-k8s:database
```

### grafana-dashboard

_Interface_: grafana-dashboard  
_Supported charms_: [grafana-k8s](https://charmhub.io/grafana-k8s)

Grafana-dashboard is a part of the COS integrate to enhance observability.
The integration enables quick dashboard access already tailored to fit the needs of
operators to monitor the charm. The template for the Grafana dashboard for the
`wordpress-k8s` charm can be found at `/src/grafana_dashboards/wordpress.json`.
In the Grafana UI, it can be found as “WordPress
Operator Overview” under the General section of the dashboard browser (`/dashboards`). Modifications
to the dashboard can be made but will not be persisted upon restart or redeployment of the charm.

The `wordpress-k8s` charm
satisfies the `grafana_dashboard` interface by providing the pre-made dashboard template to the
Grafana relation data bag under the "dashboards" key. Requires Prometheus datasource to be already
integrated with Grafana.

Grafana-Prometheus integrate command: 
```
juju integrate grafana-k8s:grafana-source prometheus-k8s:grafana-source
```  
Grafana-dashboard integrate command: 
```
juju integrate wordpress-k8s grafana-dashboard
```

### ingress

_Interface_: ingress  
_Supported charms_: [nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator)

Ingress manages external http/https access to services in a Kubernetes cluster.
The ingress integration through [nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator)
charm enables additional `blog_hostname` and `use_nginx_ingress_modesec` configurations that
provide capabilities such as ModSecurity enabled
Web Application Firewall ([WAF](https://docs.nginx.com/nginx-waf/)).

Note that the
Kubernetes cluster must already have an nginx ingress controller deployed. Documentation to
enable ingress in MicroK8s can be found [here](https://microk8s.io/docs/addon-ingress).

Example ingress integrate command: 
```
juju integrate wordpress-k8s nginx-ingress-integrator
```

### logging

_Interface_: loki_push_api  
_Supported charms_: [loki-k8s](https://charmhub.io/loki-k8s)

The logging integration is a part of the COS integration to enhance logging observability.
Logging relation through the `loki_push_api` interface installs and runs promtail which ships the
contents of local logs found at `/var/log/apache2/access.log` and `/var/log/apache2/error.log` to Loki.
This can then be queried through the Loki API or easily visualized through Grafana. Learn more about COS
[here](https://charmhub.io/topics/canonical-observability-stack).

Logging-endpoint integrate command: 
```
juju integrate wordpress-k8s loki-k8s
```

### metrics-endpoint

_Interface_: [prometheus_scrape](https://charmhub.io/interfaces/prometheus_scrape-v0)  
_Supported charms_: [prometheus-k8s](https://charmhub.io/prometheus-k8s)

The metrics-endpoint integration allows scraping the `/metrics` endpoint provided by `apache-exporter` sidecar
on port 9117, which provides apache metrics from apache’s `/server-status` route. This internal
apache’s `/server-status` route is not exposed and can only be accessed from within the same
Kubernetes pod. The metrics are exposed in the [open metrics format](https://github.com/OpenObservability/OpenMetrics/blob/main/specification/OpenMetrics.md#data-model) and will only be scraped by Prometheus once the integration becomes active. For more
information about the metrics exposed, please refer to the [apache-exporter documentation](https://github.com/Lusitaniae/apache_exporter#collectors).

Metrics-endpoint integrate command: 
```
juju integrate wordpress-k8s prometheus-k8s
```




