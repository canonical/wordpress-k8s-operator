# WordPress Operator

A Juju charm for a Kubernetes deployment of WordPress, configurable to use a
MySQL backend.

## Overview

WordPress powers more than 39% of the web — a figure that rises every day.
Everything from simple websites, to blogs, to complex portals and enterprise
websites, and even applications, are built with WordPress. WordPress combines
simplicity for users and publishers with under-the-hood complexity for
developers. This makes it flexible while still being easy-to-use.

## Usage

For details on using Kubernetes with Juju [see here](https://juju.is/docs/kubernetes), and for
details on using Juju with MicroK8s for easy local testing [see here](https://juju.is/docs/microk8s-cloud).

To deploy in a test environment, first of all deploy MySQL into a IaaS model:

    juju deploy cs:mysql

Initialise the database as follows:

    CREATE DATABASE wordpress CHARACTER SET utf8 COLLATE utf8_unicode_ci;
    CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress';
    GRANT ALL PRIVILEGES ON wordpress.* TO 'wordpress'@'%';
    FLUSH PRIVILEGES;

The WordPress k8s charm requires TLS secrets to be pre-configured to ensure
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

For further details, [see here](https://charmhub.io/wordpress/docs).
