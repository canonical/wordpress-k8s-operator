# Deploy the Wordpress charm for the first time

## What you'll do

- Deploy the [wordpress-k8s charm](https://charmhub.io/wordpress-k8s)
- [Deploy and relate database](#deploy-and-relate-database)
- [Get admin credentials](#get-admin-credentials)

The wordpress-k8s charm helps deploy a horizontally scalable WordPress application with ease and
also helps operate the charm by liaising with the Canonical Observability Stack (COS). This
tutorial will walk you through each step of deployment to get a basic WordPress deployment.

## Prerequisites

To deploy wordpress-k8s charm, you will need a juju bootstrapped with any kubernetes controller.
To see how to bootstrap your juju installation with microk8s, please refer to the documentation
on microk8s [installation](https://juju.is/docs/olm/microk8s).

## Steps
### Setting up the tutorial model

To easily clean up the resources and to separate your workload from the contents of this tutorial,
it is recommended to set up a new model with the following command.

```
juju add-model wordpress-tutorial
```

### Deploy wordpress-k8s charm

Deployment of WordPress requires a relational database. The integration with the
`mysql` [interface](https://juju.is/docs/sdk/integration) is required by the wordpress-k8s
charm and hence, [`mysql-k8s`](https://charmhub.io/mysql-k8s) charm will be used.

Start off by deploying the wordpress charm. By default it will deploy the latest stable release of
the wordpress-k8s charm.

```
juju deploy wordpress-k8s
```

### Deploy and integrate database

The following commands deploy the mysql-k8s charm and integrate it with the wordpress-k8s charm.

```
juju deploy mysql-k8s --trust

# 'database' interface is required since mysql-k8s charm provides multiple compatible interfaces
juju relate wordpress-k8s mysql-k8s:database
```

### Get admin credentials

After the database has been configured in the
[Deploy and relate database section](#deploy-and-relate-database), you can now access the WordPress
application by accessing the IP of a wordpress-k8s unit. To start managing WordPress as an
administrator, you need to get the credentials for the admin account.

By running the `get-initial-password` action on a wordpress-k8s unit, juju will read and fetch the
admin credentials setup for you. You can use the following command below.

```
juju run wordpress-k8s/0 get-initial-password 
```

The result should look something similar to the contents below:

```
unit-wordpress-k8s-0:
  UnitId: wordpress-k8s/0
  id: "6"
  results:
    password: <password> # should look something like: XXXXXXXXXXXXXXXXX-XXXXXXXXXXXXXXXXXXXXXXXX
  status: completed
  timing:
    completed: <timestamp>
    enqueued: <timestamp>
    started: <timestamp>
```

You can now access your WordPress application at `http://<UNIT_IP>/wp-login.php` and login with
username admin and password the action above.

### Cleaning up the environment

Congratulations! You have successfully finished the wordpress-k8s tutorial. You can now remove the
model environment that you’ve created using the following command.

```
juju destroy-model wordpress-tutorial --destroy-storage
```
