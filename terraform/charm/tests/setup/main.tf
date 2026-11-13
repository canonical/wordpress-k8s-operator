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

resource "juju_model" "test_model" {
  name = "tf-testing-${formatdate("YYYYMMDDhhmmss", timestamp())}"
}

output "model_uuid" {
  value = juju_model.test_model.uuid
}
