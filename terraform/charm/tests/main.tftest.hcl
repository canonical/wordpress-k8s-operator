# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

run "setup_tests" {
  module {
    source = "./tests/setup"
  }
}

run "basic_deploy" {
  variables {
    model_uuid = run.setup_tests.model_uuid
    base       = "ubuntu@22.04"
    channel    = "latest/edge"
    # renovate: depName="wordpress-k8s"
    revision = 186
  }

  assert {
    condition     = output.application.name == "wordpress-k8s"
    error_message = "wordpress-k8s application name did not match expected"
  }

  assert {
    condition     = output.provides.grafana_dashboard.endpoint == "grafana-dashboard"
    error_message = "wordpress-k8s module should provide 'provides.grafana_dashboard' output"
  }

  assert {
    condition     = output.provides.metrics_endpoint.endpoint == "metrics-endpoint"
    error_message = "wordpress-k8s module should provide 'provides.metrics_endpoint' output"
  }

  assert {
    condition     = output.requires.database.endpoint == "database"
    error_message = "wordpress-k8s module should provide 'requires.database' output"
  }

  assert {
    condition     = output.requires.logging.endpoint == "logging"
    error_message = "wordpress-k8s module should provide 'requires.logging' output"
  }

  assert {
    condition     = output.requires.nginx_route.endpoint == "nginx-route"
    error_message = "wordpress-k8s module should provide 'requires.nginx_route' output"
  }
}
