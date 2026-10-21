# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

terraform {
  required_version = "~> 1.12"
  required_providers {
    juju = {
      source  = "juju/juju"
      version = "~> 1.0"
    }
  }
}

provider "juju" {}

# The lxd-controller-with-k8s-cloud test environment pre-creates a machine model
# and a Kubernetes model on the same controller.
data "juju_model" "k8s" {
  name  = "tf-testing-k8s"
  owner = "admin"
}

data "juju_model" "lxd" {
  name  = "tf-testing-lxd"
  owner = "admin"
}

output "model_uuid" {
  value = data.juju_model.k8s.uuid
}

output "database_model_uuid" {
  value = data.juju_model.lxd.uuid
}
