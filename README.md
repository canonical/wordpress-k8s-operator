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

To deploy the charm and relate it to the [Maria K8s charm](https://jaas.ai/u/charmed-osm/mariadb-k8s) within a Juju
Kubernetes model:

    juju deploy cs:~charmed-osm/mariadb-k8s
    juju deploy cs:~wordpress-charmers/wordpress
    juju add-relation wordpress mariadb-k8s:mysql

It will take about 5 to 10 minutes for Juju hooks to discover the site is live
and perform the initial setup for you. Once the "Workload" status is "active",
your WordPress site is configured.

To retrieve the auto-generated admin password, run the following:

    juju run-action --wait wordpress/0 get-initial-password

You should now be able to browse to the IP address of the unit as follows:

    Unit            Workload     Agent  Address      Ports     Message
    mariadb-k8s/0*  active       idle   10.1.234.43  3306/TCP  ready
    wordpress/0*    active       idle   10.1.234.13  80/TCP    Pod configured

In this case our UNIT_IP is 10.1.234.13. If we visit `http://${UNIT_IP}/`
you'll see the WordPress site itself, or you can log in to the admin site
using a username of `admin` and the password value from the
`get-initial-password` action above at `http://{$UNIT_IP}/wp-admin`.

For further details, [see here](https://charmhub.io/wordpress/docs).
