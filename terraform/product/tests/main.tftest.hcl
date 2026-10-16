# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

run "setup_tests" {
  module {
    source = "./tests/setup"
  }
}

run "missing_database_model" {
  command = plan

  variables {
    model_uuid          = run.setup_tests.model_uuid
    database_model_uuid = null
  }

  expect_failures = [var.database_model_uuid]
}

run "external_integrations" {
  command = plan

  variables {
    model_uuid = run.setup_tests.model_uuid
    mysql_integration = {
      offer_url = "admin/database.mysql"
    }
    ingress_integration = {
      name     = "nginx-ingress-integrator"
      endpoint = "nginx-route"
    }
  }

  assert {
    condition     = length(juju_application.mysql) == 0 && length(juju_offer.mysql) == 0
    error_message = "the bundled mysql should not be deployed when mysql_integration is set"
  }

  assert {
    condition     = keys(juju_integration.wordpress_k8s_optional) == ["nginx_route"]
    error_message = "only the nginx-route optional integration should be created"
  }
}

run "basic_deploy" {
  variables {
    model_uuid          = run.setup_tests.model_uuid
    database_model_uuid = run.setup_tests.database_model_uuid
    risk                = "edge"
    wordpress_k8s = {
      # renovate: depName="wordpress-k8s"
      revision = 186
    }
    mysql = {
      # renovate: depName="mysql"
      revision = 541
    }
  }

  assert {
    condition     = output.models.wordpress.model_uuid == run.setup_tests.model_uuid
    error_message = "the wordpress model UUID did not match the provided model_uuid"
  }

  assert {
    condition     = output.models.wordpress.components.wordpress_k8s.name == "wordpress-k8s"
    error_message = "the wordpress model should contain wordpress-k8s"
  }

  assert {
    condition     = output.models.database.model_uuid == run.setup_tests.database_model_uuid
    error_message = "the database model UUID did not match the provided database_model_uuid"
  }

  assert {
    condition     = output.models.database.components.mysql.name == "mysql"
    error_message = "the database model should contain mysql"
  }

  assert {
    condition     = output.offers.mysql != ""
    error_message = "the mysql offer URL should be exposed"
  }

  assert {
    condition     = output.metadata.risk == "edge"
    error_message = "the metadata should report the requested risk"
  }
}
