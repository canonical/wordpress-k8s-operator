# Deploy the Wordpress charm for the first time

## What you'll do

- Deploy the [wordpress-k8s charm](https://charmhub.io/wordpress-k8s)
- [Deploy and integrate database](#deploy-and-integrate-database)
- [Get admin credentials](#get-admin-credentials)

The wordpress-k8s charm helps deploy a horizontally scalable WordPress application with ease and
also helps operate the charm by liaising with the Canonical Observability Stack (COS). This
tutorial will walk you through each step of deployment to get a basic WordPress deployment.

## Requirements

To deploy wordpress-k8s charm, you will need a Juju bootstrapped with any Kubernetes controller.
To see how to bootstrap your Juju installation with MicroK8s, please refer to the documentation
on MicroK8s [installation](https://juju.is/docs/olm/microk8s).

## Steps
### Set up the tutorial model

To easily clean up the resources and to separate your workload from the contents of this tutorial,
set up a new model with the following command.

```
juju add-model wordpress-tutorial
```

### Deploy wordpress-k8s charm

Deployment of WordPress requires a relational database. The integration with the
`mysql` [interface](https://juju.is/docs/sdk/integration) is required by the wordpress-k8s
charm and hence, [`mysql-k8s`](https://charmhub.io/mysql-k8s) charm will be used.

Start off by deploying the Wordpress charm. By default it will deploy the latest stable release of
the wordpress-k8s charm.

```
juju deploy wordpress-k8s
```

### Deploy and integrate database <a name="deploy-and-integrate-database"></a>

The following commands deploy the mysql-k8s charm and integrate it with the wordpress-k8s charm.

```
juju deploy mysql-k8s --trust

# 'database' interface is required since mysql-k8s charm provides multiple compatible interfaces
juju integrate wordpress-k8s mysql-k8s:database
```

Run `juju status` to see the current status of the deployment. The output should be similar to the following:

```
Model               Controller          Cloud/Region        Version  SLA          Timestamp
wordpress-tutorial  microk8s-localhost  microk8s/localhost  3.5.3    unsupported  18:48:09Z

App            Version                  Status  Scale  Charm          Channel        Rev  Address         Exposed  Message
mysql-k8s      8.0.37-0ubuntu0.22.04.3  active      1  mysql-k8s      8.0/stable     180  10.152.183.254  no       
wordpress-k8s  6.4.3                    active      1  wordpress-k8s  latest/stable   87  10.152.183.56   no       

Unit              Workload  Agent  Address       Ports  Message
mysql-k8s/0*      active    idle   10.1.200.163         Primary
wordpress-k8s/0*  active    idle   10.1.200.161
```

The deployment finishes when the status shows "Active".

### Get admin credentials <a name="get-admin-credentials"></a>

After the database has been configured, you can now access the WordPress
application by accessing the IP of a wordpress-k8s unit. To start managing WordPress as an
administrator, you need to get the credentials for the admin account.

By running the `get-initial-password` action on a wordpress-k8s unit, Juju will read and fetch the
admin credentials setup for you. You can use the following command below.

```
juju run wordpress-k8s/0 get-initial-password 
```

The result should look something similar to the contents below:

```
Running operation 1 with 1 task
  - task 2 on unit-wordpress-k8s-0

Waiting for task 2...
password: <password> # should look something like: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

```

You can now access your WordPress application at `http://<UNIT_IP>/wp-login.php` and login with
username admin and password the action above.

### Clean up the environment

Congratulations! You have successfully finished the wordpress-k8s tutorial. You can now remove the
model environment that you’ve created using the following command.

```
juju destroy-model wordpress-tutorial --destroy-storage
```