# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

output "metadata" {
  description = "Metadata of the product module deployment."
  value = {
    version     = var.metadata_version
    risk        = var.risk
    deployed_at = terraform_data.deployed_at.output
    updated_at  = timestamp()
  }
}

output "models" {
  description = "Map of the model key to its model UUID and the components deployed in it."
  value = merge(
    {
      wordpress = {
        model_uuid = var.model_uuid
        components = { wordpress_k8s = module.wordpress_k8s.application }
      }
    },
    {
      for app in juju_application.mysql : "database" => {
        model_uuid = var.database_model_uuid
        components = { mysql = app }
      }
    },
  )
}

output "offers" {
  description = "Map of the offers created by the product module with their URLs."
  value       = { for offer in juju_offer.mysql : "mysql" => offer.url }
}
