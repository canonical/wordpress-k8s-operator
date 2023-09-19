#!/bin/bash

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

# Pre-run script for integration test operator-workflows action.
# https://github.com/canonical/operator-workflows/blob/main/.github/workflows/integration_test.yaml

# Jenkins machine agent charm is deployed on lxd and Jenkins-k8s server charm is deployed on
# microk8s.

TESTING_MODEL="$(juju switch)"

# lxd should be install and init by a previous step in integration test action.
echo "bootstrapping lxd juju controller"
sg microk8s -c "microk8s status --wait-ready"
sg microk8s -c "juju bootstrap localhost localhost"

echo "Switching to testing model"
sg microk8s -c "juju switch $TESTING_MODEL"
