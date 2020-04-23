# Wordpress k8s charm

A Juju charm for a Kubernetes deployment of Wordpress, using the
official Dockerhub Wordpress image or an image built from this base.

## Overview

This is a k8s charm and can only be deployed to to a Juju k8s cloud,
attached to a controller using `juju add-k8s`.

The image to spin up is specified in the `image` charm configuration
option using standard docker notation (eg. 'localhost:32000/mywork-rev42').
The default image is Dockerhub's `wordpress:php7.3` image, but you can also
use private images by specifying `image_user` and `image_pass` charm
configuration.

Configuration for the Wordpress image is in standard Juju config. In particular:

* `db_host`, `db_user` & `db_password`. This charm may in future be relatable
   to a MySQL deployment, when the MySQL charm is updated to support cross
   model relations.
* `ports`. Custom images may require additional ports to be opened, such
   as those providing monitoring or metrics endpoints.

Additional runtime configuration is specified as YAML snippets in the charm config.
Both `container_config` and `container_secrets` items are provided,
and they are combined together. `container_config` gets logged,
`container_secrets` does not. This allows you to configure customized
Wordpress images.

## Details

See config option descriptions in config.yaml.

## Quickstart

Notes for deploying a test setup locally using microk8s:

    sudo snap install juju --classic
    sudo snap install juju-wait --classic
    sudo snap install microk8s --classic
    sudo snap alias microk8s.kubectl kubectl

    microk8s.reset  # Warning! Clean slate!
    microk8s.enable dns dashboard registry storage
    microk8s.status --wait-ready
    microk8s.config | juju add-k8s myk8s
    juju bootstrap myk8s
    juju add-model wordpress-test
    juju create-storage-pool operator-storage kubernetes storage-class=microk8s-hostpath
    juju deploy cs:~wordpress-charmers/wordpress-k8s --channel=edge wordpress
    juju config wordpress db_host=10.1.1.1 db_user=wp db_password=secret
    juju wait
    juju status # Shows IP address, and port is 80
