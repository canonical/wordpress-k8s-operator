# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

output "application" {
  description = "The deployed application object."
  value       = juju_application.wordpress_k8s
}

output "provides" {
  description = "Map of the provided integration endpoints."
  value = {
    grafana_dashboard = {
      kind     = "endpoint"
      name     = juju_application.wordpress_k8s.name
      endpoint = "grafana-dashboard"
    }
    metrics_endpoint = {
      kind     = "endpoint"
      name     = juju_application.wordpress_k8s.name
      endpoint = "metrics-endpoint"
    }
  }
}

output "requires" {
  description = "Map of the required integration endpoints."
  value = {
    database = {
      kind     = "endpoint"
      name     = juju_application.wordpress_k8s.name
      endpoint = "database"
    }
    logging = {
      kind     = "endpoint"
      name     = juju_application.wordpress_k8s.name
      endpoint = "logging"
    }
    nginx_route = {
      kind     = "endpoint"
      name     = juju_application.wordpress_k8s.name
      endpoint = "nginx-route"
    }
  }
}
