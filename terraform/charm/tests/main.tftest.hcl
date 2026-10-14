# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

variables {
  app_name           = "wordpress-k8s"
  base               = "ubuntu@22.04"
  channel            = "latest/edge"
  config             = {}
  constraints        = "arch=amd64"
  model_uuid         = "00000000-0000-0000-0000-000000000001"
  resources          = { wordpress-image = "1" }
  revision           = 10
  storage_directives = { uploads = "1G" }
  units              = 2
}

mock_provider "juju" {
  mock_resource "juju_application" {
    override_during = plan
    defaults = {
      id         = "wordpress-k8s"
      model_type = "kubernetes"
    }
  }
}

run "deploys_application" {
  command = plan

  assert {
    condition     = output.application.name == "wordpress-k8s" && output.application.model_uuid == "00000000-0000-0000-0000-000000000001" && output.application.charm[0].name == "wordpress-k8s" && output.application.charm[0].channel == "latest/edge" && output.application.charm[0].base == "ubuntu@22.04" && output.application.charm[0].revision == 10
    error_message = "application identity did not match the expected deployment"
  }

  assert {
    condition     = output.application.constraints == "arch=amd64"
    error_message = "application constraints did not match expected"
  }

  assert {
    condition     = output.application.units == 2
    error_message = "application units did not match expected"
  }

  assert {
    condition = output.provides == {
      grafana_dashboard = {
        kind     = "endpoint"
        name     = "wordpress-k8s"
        endpoint = "grafana-dashboard"
      }
      metrics_endpoint = {
        kind     = "endpoint"
        name     = "wordpress-k8s"
        endpoint = "metrics-endpoint"
      }
    }
    error_message = "provides outputs did not match expected structure"
  }

  assert {
    condition = output.requires == {
      database = {
        kind     = "endpoint"
        name     = "wordpress-k8s"
        endpoint = "database"
      }
      logging = {
        kind     = "endpoint"
        name     = "wordpress-k8s"
        endpoint = "logging"
      }
      nginx_route = {
        kind     = "endpoint"
        name     = "wordpress-k8s"
        endpoint = "nginx-route"
      }
    }
    error_message = "requires outputs did not match expected structure"
  }
}
