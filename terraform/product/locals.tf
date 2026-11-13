# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

locals {
  # The product owns each charm's track; `risk` selects the channel risk solution-wide.
  wordpress_k8s_channel = coalesce(var.wordpress_k8s.channel, "latest/${var.risk}")
  mysql_channel         = coalesce(var.mysql.channel, "8.0/${var.risk}")

  deploy_mysql = var.mysql_integration == null

  # The bundled mysql lives in the machine model, so wordpress-k8s consumes it through an offer.
  mysql_target = local.deploy_mysql ? {
    name      = null
    offer_url = one(juju_offer.mysql[*].url)
    endpoint  = null
  } : var.mysql_integration

  optional_integrations = {
    for key, target in {
      nginx_route = var.ingress_integration
      logging     = var.logging_integration
    } : key => target if target != null
  }
}
