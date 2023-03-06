# Relations

### Peer relations

When deploying multiple replications of the wordpress-k8s charm, peer relations are set up to
ensure synchronization of data among replications. Namely, secrets and admin credentials are shared
among peers. See more about the secrets in the `rotate-wordpress-secrets` action of the
[reference documentation](https://charmhub.io/wordpress-k8s/docs/reference).

### db

Database relation is required for the wordpress-k8s charm to become active. Any relation that can
fulfill the `mysql` interface can be used to integrate with the wordpress-k8s charm. Database
configuration parameters are also provided for non-k8s native integrations support. Configuration
replacements for db relation can be found in the reference documentation with the prefix `db_`.

### ingress

Ingress interface provides external http/https access to the WordPress application along with other
additional capabilities depending on the ingress charm. The wordpress-k8s charm's ingress relation
is best enhanced with the [nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator)
charm, providing additional capabilities such as ModSecurity enabled
Web Application Firewall ([WAF](https://docs.nginx.com/nginx-waf/)) through the wordpress-k8s charm
configuration parameter `use_nginx_ingress_modsec`. The ingress relation interface is subject to
renaming due to additional ingress interface definition supported by the Traefik charm.

### metrics-endpoint

This interface is a part of the COS integration to enhance metrics observability. The wordpress-k8s
charm satisfies the `prometheus_scrape` interface as a provider by exposing Open Metrics compliant
`/metrics` endpoint. Requires [prometheus-k8s](https://charmhub.io/prometheus-k8s) charm. Learn
more about COS [here](https://charmhub.io/topics/canonical-observability-stack).

### logging

Logging relation is a part of the COS integration to enhance logging observability. The
wordpress-k8s charm satisfies the loki_push_api by integrating promtail that pushes apache logs to
Loki. Requires [loki-k8s](https://charmhub.io/loki-k8s) charm. Learn more about COS
[here](https://charmhub.io/topics/canonical-observability-stack).

### grafana-dashboard

Grafana-dashboard is a part of the COS integration to enhance observability. This relation provides
a pre-made dashboard used for monitoring Apache server hosting WordPress. The wordpress-k8s charm
satisfies the `grafana_dashboard` interface by providing the pre-made dashboard template to the
Grafana relation data bag under the "dashboards" key. Requires Prometheus datasource to be already
integrated with Grafana.
