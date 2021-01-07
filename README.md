# Wordpress k8s charm

A Juju charm for a Kubernetes deployment of Wordpress, using the
official Dockerhub Wordpress image or an image built from this base.

## Overview

This is a k8s charm and can only be deployed to to a Juju k8s cloud,
attached to a controller using `juju add-k8s`.

The image to spin up is specified in the `image` charm configuration
option using standard docker notation (eg. 'localhost:32000/mywork-rev42').
The default image is Dockerhub's `wordpresscharmers/wordpress:bionic-stable` image,
but you can also use private images by specifying `image_user` and `image_pass` charm
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

To deploy in a test environment, first of all deploy MySQL into a IaaS model:

    juju deploy cs:mysql

Initialise the database as follows:

    CREATE DATABASE wordpress CHARACTER SET utf8 COLLATE utf8_unicode_ci;
    CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress';
    GRANT ALL PRIVILEGES ON wordpress.* TO 'wordpress'@'%';
    FLUSH PRIVILEGES;

The Wordpress k8s charm requires TLS secrets to be pre-configured to ensure
logins are kept secure. Create a self-signed certificate and upload it as a
Kubernetes secret (assuming you're using MicroK8s):

    openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -keyout server.key -out server.crt
    microk8s.kubectl create secret tls -n wordpress tls-wordpress --cert=server.crt --key=server.key

Deploy the charm into your Kubernetes Juju model:

    DB_HOST=$IP_OF_YOUR_MYSQL_DATABASE
    juju deploy cs:~wordpress-charmers/wordpress \
        --config db_host=$DB_HOST \
        --config tls_secret_name=tls-wordpress

From there you can test the site by updating your `/etc/hosts` file and creating
a static entry for the IP address of the Kubernetes ingress gateway:

    App        Version        Status   Scale  Charm      Store  Rev  OS          Address         Message
    wordpress  wordpress:5.6  waiting      1  wordpress  local    0  kubernetes  10.152.183.140
    
    echo '10.152.183.140 myblog.example.com' | sudo tee -a /etc/hosts

It will take about 5 to 10 minutes for Juju hooks to discover the site is live
and perform the initial setup for you. Look for this line in the output of
`juju debug-log` to confirm:

    unit.wordpress/0.juju-log Wordpress configured and initialised

This is due to [issue #166](https://github.com/canonical/operator/issues/166) and will be fixed once Juju supports a Kubernetes
pod ready hook.

To retrieve the random admin password, run the following (until [LP#1907063](https://bugs.launchpad.net/charm-k8s-wordpress/+bug/1907063) is addressed):

    microk8s.kubectl exec -ti -n wordpress wordpress-operator-0 -- cat /root/initial.passwd

You should now be able to browse to https://myblog.example.com/wp-admin.

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
    # TLS certificates are required for the ingress to function properly, self-signed is okay
    # for testing but make sure you use valid ones in production.
    openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -keyout server.key -out server.crt
    kubectl create secret tls tls-wordpress --cert=server.crt --key=server.key
    juju config wordpress db_host=10.1.1.1 db_user=wp db_password=secret tls_secret_name=tls-wordpress \
        initial_settings="user_name: admin
        admin_email: devnull@canonical.com
        weblog_title: Test Blog
        blog_public: False"
    juju wait
    juju status # Shows IP address, and port is 80
