(how_to_integrate_with_cos)=

# How to integrate with COS

## Integrate with Prometheus K8s operator

Deploy and relate [prometheus-k8s](https://charmhub.io/prometheus-k8s) charm with wordpress-k8s
charm through the `metrics-endpoint` relation via `prometheus_scrape` interface. Prometheus should
start scraping the metrics exposed at `:9117/metrics` endpoint.

```
juju deploy prometheus-k8s
juju integrate wordpress-k8s prometheus-k8s
```

## Integrate with Loki K8s operator

Deploy and relate [loki-k8s](https://charmhub.io/loki-k8s) charm with wordpress-k8s charm through
the `logging` relation via `loki_push_api` interface. Promtail worker should spawn and start pushing
Apache access logs and error logs to Loki.

```
juju deploy loki-k8s
juju integrate wordpress-k8s loki-k8s
```

## Integrate with Grafana K8s operator

In order for the Grafana dashboard to function properly, Grafana should be able to connect to
Prometheus and Loki as its datasource. Deploy and relate the `prometheus-k8s` and `loki-k8s`
charms with [grafana-k8s](https://charmhub.io/grafana-k8s) charm through the `grafana-source` integration.

Note that the integration `grafana-source` has to be explicitly stated since `prometheus-k8s` and
`grafana-k8s` share multiple interfaces.

```
juju deploy grafana-k8s
juju integrate prometheus-k8s:grafana-source grafana-k8s:grafana-source
juju integrate loki-k8s:grafana-source grafana-k8s:grafana-source
```

Then, the `wordpress-k8s` charm can be related with Grafana using the `grafana-dashboard` relation with
`grafana_dashboard` interface.

```
juju integrate wordpress-k8s grafana-k8s
```

To access the Grafana dashboard for the WordPress charm, run the `get-admin-password` action
to obtain credentials for admin access.

```
juju run grafana-k8s/0 get-admin-password
```

Log into the Grafana dashboard by visiting `http://<grafana-unit-ip>:3000`. Navigate to
`http://<grafana-unit-ip>:3000/dashboards` and access the WordPress dashboard named **Wordpress Operator
Overview**.


