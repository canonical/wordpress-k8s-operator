# Tutorial

The wordpress-k8s charm helps deploy a horizontally scalable WordPress application with ease and
also helps operate the charm by liaising with the Canonical Observability Stack (COS). This
tutorial will walk you through each step of deployment to get a basic WordPress application
working.

### Prerequisites

To deploy wordpress-k8s charm, you will need a juju bootstrapped with any kubernetes controller.
To see how to bootstrap your juju installation with microk8s, please refer to the documentation
on microk8s [installation](https://juju.is/docs/olm/microk8s).

### Setting up the environment

To easily clean up the resources and to separate your workload from the contents of this tutorial,
it is recommended to set up another environment by adding a new model with the following command.

```
juju add-model wordpress-tutorial
```

### Deploy wordpress-k8s charm

Deployment of WordPress requires a database integration. A preferred method in juju is through the
native juju relation. In this case, a `mysql` interface is required by the wordpress-k8s charm and
hence, [`mysql-k8s`](https://charmhub.io/mysql-k8s) charm will be used.

Start off by deploying the wordpress charm. By default it will deploy the latest stable release of
the wordpress-k8s charm.

```
juju deploy wordpress-k8s
```

### Deploy and relate database

#### Database relation

The following commands deploys the mysql-k8s charm and relates wordpress-k8s charm through its mysql
interface.

```
juju deploy mysql-k8s \
    --config mysql-interface-user=wordpress \
    --config mysql-interface-database=test-database
juju relate wordpress-k8s mysql-k8s
```

#### Database configuration

Note: If you’ve completed the steps in the Database relation section, you may skip this part. If
you want to deploy your wordpress-k8s charm through configuration, you may continue to follow the
steps in this section.

The commands below create the MySQL deployment in microk8s which we can then use to configure the
database for wordpress-k8s. Note that the environment variables are for demonstration purposes only
and should not be used for production environments.

```
microk8s kubectl run mysql -n wordpress-tutorial --image=mysql:latest \
--env="MYSQL_ROOT_PASSWORD=mysecretpassword" \
--env=”MYSQL_DATABASE=wordpress” \
--env=”MYSQL_USER=wordpress” \
--env=”MYSQL_PASSWORD=wordpress”
WORDPRESS_IP=microk8s kubectl get pod mysql --template '{{.status.podIP}}'
juju config wordpress-k8s \
db_host=$WORDPRESS_IP \
db_name=wordpress \
db_user=wordpress \
db_password=wordpress
```

Use the following command to watch your deployment progress through different stages of deployment.

```
watch -c juju status --color
```

### Get admin credentials

After the database has been configured in step 2, you can now access the WordPress application by
accessing the IP of a wordpress-k8s unit. To start managing WordPress as an administrator, you need
to get the credentials for the admin account.

By running the `get-initial-password` action on a wordpress-k8s unit, juju will read and fetch the
admin credentials setup for you. You can use the following command below.

```
juju run-action wordpress-k8s/0 get-initial-password --wait
```

The result should look something similar to the contents below:

```
unit-wordpress-k8s-0:
  UnitId: wordpress-k8s/0
  id: "6"
  results:
    password: 7ioJgp2CS6iK7MrM9I-wCm48i25HaJLzeHT7MpEwdyk
  status: completed
  timing:
    completed: 2023-02-24 02:46:27 +0000 UTC
    enqueued: 2023-02-24 02:46:25 +0000 UTC
    started: 2023-02-24 02:46:26 +0000 UTC
```

You can now access your WordPress application at http://UNIT_IP/wp-login.php and login with
username admin and password the action above.

### Cleaning up the environment

Congratulations! You have successfully finished the wordpress-k8s tutorial. You can now remove the
model environment that you’ve created using the following command.

```
juju destroy model wordpress-tutorial -y --force --release-storage
```

### Next steps

To learn more about the wordpress-k8s charm and how to operate it, you can refer to the
[how-to-guide](https://charmhub.io/wordpress-k8s/docs/how-to-guide?channel=edge) of the documentation.  
To find out more information about the configuration and operational parameters, please visit the
[reference](https://charmhub.io/wordpress-k8s/docs/reference?channel=edge) documentation.  
To understand more about the wordpress-k8s charm and its background, please refer to the
[explanation](https://charmhub.io/wordpress-k8s/docs/explanation?channel=edge) documentation.
