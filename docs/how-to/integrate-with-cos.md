# How to integrate with COS

### prometheus-k8s

Deploy and relate [prometheus-k8s](https://charmhub.io/prometheus-k8s) charm with wordpress-k8s
charm through the `metrics-endpoint` relation via `prometheus_scrape` interface. Prometheus should
start scraping the metrics exposed at `:9117/metrics` endpoint.

```
juju deploy prometheus-k8s
juju relate wordpress-k8s prometheus-k8s
```

### loki-k8s

Deploy and relate [loki-k8s](https://charmhub.io/loki-k8s) charm with wordpress-k8s charm through
the `logging` relation via `loki_push_api` interface. Promtail worker should spawn and start pushing
Apache access logs and error logs to loki.

```
juju deploy loki-k8s
juju relate wordpress-k8s loki-k8s
```

### grafana-k8s

In order for the Grafana dashboard to function properly, grafana should be able to connect to
Prometheus and Loki as its datasource. Deploy and relate prometheus-k8s and lok-k8s charm with
[grafana-k8s](https://charmhub.io/grafana-k8s) charm through `grafana-source` relation.

Note that the relation “grafana-source” has to be explicitly stated since prometheus-k8s and
grafana-k8s share multiple interfaces.

```
juju deploy grafana-k8s
juju relate prometheus-k8s:grafana-source grafana-k8s:grafana-source
juju relate loki-k8s:grafana-source grafana-k8s:grafana-source
```

Then, wordpress-k8s charm can be related with grafana using the `grafana-dashboard` relation with
`grafana_dashboard` interface.

```
juju relate wordpress-k8s grafana-k8s
```

To access the Grafana dashboard for wordpress-k8s charm, run the following command to obtain
credentials for admin access.

```
juju run grafana-k8s/0 get-admin-password
```

You can now log into the grafana dashboard by visiting `http://<grafana-unit-ip>:3000`. Navigate to
`http://<grafana-unit-ip>:3000/dashboards` and access the WordPress dashboard named Wordpress Operator
Overview.
