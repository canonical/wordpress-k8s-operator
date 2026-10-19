# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

variable "database_model_uuid" {
  description = "UUID of the machine Juju model to deploy the bundled mysql into. Required unless `mysql_integration` is set."
  type        = string
  default     = null

  validation {
    condition     = var.database_model_uuid != null || var.mysql_integration != null
    error_message = "database_model_uuid must be set when mysql_integration is not provided."
  }
}

variable "ingress_integration" {
  description = "`nginx-route` provider (for example nginx-ingress-integrator) to integrate wordpress-k8s with, given as an application `name` in `model_uuid` or an `offer_url`. Leave null to skip the integration."
  type = object({
    name      = optional(string)
    offer_url = optional(string)
    endpoint  = optional(string)
  })
  default = null

  validation {
    condition     = var.ingress_integration == null || ((try(var.ingress_integration.name, null) == null) != (try(var.ingress_integration.offer_url, null) == null))
    error_message = "Set exactly one of name or offer_url in ingress_integration."
  }
}

variable "logging_integration" {
  description = "`loki_push_api` provider to send wordpress-k8s logs to, given as an application `name` in `model_uuid` or an `offer_url`. Leave null to skip the integration."
  type = object({
    name      = optional(string)
    offer_url = optional(string)
    endpoint  = optional(string)
  })
  default = null

  validation {
    condition     = var.logging_integration == null || ((try(var.logging_integration.name, null) == null) != (try(var.logging_integration.offer_url, null) == null))
    error_message = "Set exactly one of name or offer_url in logging_integration."
  }
}

variable "metadata_version" {
  description = "Version string reported in the product module `metadata` output."
  type        = string
  default     = "1.0.0"
}

variable "model_uuid" {
  description = "UUID of the Kubernetes Juju model to deploy wordpress-k8s into."
  type        = string
  nullable    = false
}

variable "mysql" {
  description = "Configuration of the bundled mysql machine charm, deployed in `database_model_uuid` unless `mysql_integration` is set. When `channel` is null it defaults to `8.0/<risk>`."
  type = object({
    app_name    = optional(string, "mysql")
    base        = optional(string, "ubuntu@22.04")
    channel     = optional(string)
    config      = optional(map(string), {})
    constraints = optional(string)
    revision    = optional(number)
    units       = optional(number, 1)
  })
  default = {}
}

variable "mysql_integration" {
  description = "Existing `mysql_client` provider to integrate wordpress-k8s with, given as an application `name` in `model_uuid` or an `offer_url`. When set, the bundled mysql is not deployed."
  type = object({
    name      = optional(string)
    offer_url = optional(string)
    endpoint  = optional(string)
  })
  default = null

  validation {
    condition     = var.mysql_integration == null || ((try(var.mysql_integration.name, null) == null) != (try(var.mysql_integration.offer_url, null) == null))
    error_message = "Set exactly one of name or offer_url in mysql_integration."
  }
}

variable "risk" {
  description = "Risk level controlling the channel risk of the charms in the solution. Every charm `channel` left unset defaults to `<track>/<risk>`."
  type        = string
  default     = "stable"

  validation {
    condition     = contains(["stable", "edge"], var.risk)
    error_message = "risk must be one of: stable, edge."
  }
}

variable "wordpress_k8s" {
  description = "Configuration of the wordpress-k8s charm. When `channel` is null it defaults to `latest/<risk>`."
  type = object({
    app_name           = optional(string, "wordpress-k8s")
    base               = optional(string, "ubuntu@22.04")
    channel            = optional(string)
    config             = optional(map(string), {})
    constraints        = optional(string)
    resources          = optional(map(string), {})
    revision           = optional(number)
    storage_directives = optional(map(string), {})
    units              = optional(number, 1)
  })
  default = {}
}
