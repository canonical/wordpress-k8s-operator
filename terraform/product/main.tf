# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

# Captures the initial deployment timestamp once and keeps it stable across
# subsequent applies, for the "metadata.deployed_at" output.
resource "terraform_data" "deployed_at" {
  input = timestamp()

  lifecycle {
    ignore_changes = [input]
  }
}

module "wordpress_k8s" {
  source = "../charm"

  app_name           = var.wordpress_k8s.app_name
  base               = var.wordpress_k8s.base
  channel            = local.wordpress_k8s_channel
  config             = var.wordpress_k8s.config
  constraints        = var.wordpress_k8s.constraints
  model_uuid         = var.model_uuid
  resources          = var.wordpress_k8s.resources
  revision           = var.wordpress_k8s.revision
  storage_directives = var.wordpress_k8s.storage_directives
  units              = var.wordpress_k8s.units
}

resource "juju_application" "mysql" {
  count = local.deploy_mysql ? 1 : 0

  name       = var.mysql.app_name
  model_uuid = var.database_model_uuid

  charm {
    name     = "mysql"
    channel  = local.mysql_channel
    revision = var.mysql.revision
    base     = var.mysql.base
  }

  config      = var.mysql.config
  constraints = var.mysql.constraints
  units       = var.mysql.units
}

resource "juju_offer" "mysql" {
  count = local.deploy_mysql ? 1 : 0

  model_uuid       = var.database_model_uuid
  application_name = juju_application.mysql[0].name
  endpoints        = ["database"]
}

resource "juju_integration" "wordpress_k8s_database" {
  model_uuid = var.model_uuid

  application {
    name     = module.wordpress_k8s.application.name
    endpoint = module.wordpress_k8s.requires.database.endpoint
  }

  application {
    name      = local.mysql_target.name
    offer_url = local.mysql_target.offer_url
    endpoint  = local.mysql_target.endpoint
  }
}

resource "juju_integration" "wordpress_k8s_optional" {
  for_each = local.optional_integrations

  model_uuid = var.model_uuid

  application {
    name     = module.wordpress_k8s.application.name
    endpoint = module.wordpress_k8s.requires[each.key].endpoint
  }

  application {
    name      = each.value.name
    offer_url = each.value.offer_url
    endpoint  = each.value.endpoint
  }
}
