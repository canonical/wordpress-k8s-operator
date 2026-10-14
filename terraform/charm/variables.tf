# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

variable "app_name" {
  description = "Name of the application in the Juju model."
  type        = string
  default     = "wordpress-k8s"
  nullable    = false
}

variable "base" {
  description = "The operating system on which to deploy"
  type        = string
  default     = null
}

variable "channel" {
  description = "The channel to use when deploying a charm."
  type        = string
  default     = "latest/stable"
  nullable    = false
}

variable "config" {
  description = "Application config. Details about available options can be found at https://charmhub.io/wordpress-k8s/configurations"
  type        = map(string)
  default     = {}
}

variable "constraints" {
  description = "Juju constraints to apply for this application."
  type        = string
  default     = null
}

variable "model_uuid" {
  description = "UUID of the Juju model where the application will be deployed."
  type        = string
  nullable    = false
}

variable "resources" {
  description = "Resources to use with the charm, such as the wordpress-image OCI image."
  type        = map(string)
  default     = {}
}

variable "revision" {
  description = "Revision number of the charm"
  type        = number
  default     = null
}

variable "storage_directives" {
  description = "Map of storage used by the application."
  type        = map(string)
  default     = {}
}

variable "units" {
  description = "The number of units to deploy"
  type        = number
  default     = 1
}
