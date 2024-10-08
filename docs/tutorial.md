# Deploy the Wordpress charm for the first time

## What you'll do

- Deploy the [Wordpress K8s charm](https://charmhub.io/wordpress-k8s)
- [Deploy and integrate database](#deploy-and-integrate-database)
- [Get admin credentials](#get-admin-credentials)

The wordpress-k8s charm helps deploy a horizontally scalable WordPress application with ease and
also helps operate the charm by liaising with the Canonical Observability Stack (COS). This
tutorial will walk you through each step of deployment to get a basic WordPress deployment.

## Requirements
- A working station, e.g., a laptop, with amd64 architecture.
- Juju 3 installed and bootstrapped to a MicroK8s controller. You can accomplish this process by using a Multipass VM as outlined in this guide: [Set up / Tear down your test environment](https://juju.is/docs/juju/set-up--tear-down-your-test-environment)

For more information about how to install Juju, see [Get started with Juju](https://juju.is/docs/olm/get-started-with-juju).

### Shell into the Multipass VM
> NOTE: If you're working locally, you don't need to do this step.

To be able to work inside the Multipass VM first you need to log in with the following command:
```bash
multipass shell my-juju-vm
```

### Add a Juju model for the tutorial

To manage resources effectively and to separate this tutorial's workload from
your usual work, create a new model in the MicroK8s controller using the following command:


```
juju add-model wordpress-tutorial
```

### Deploy Wordpress K8s charm

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

The deployment finishes when the status shows "Active" for both the WordPress and MySQL charms.

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

> NOTE: If you are using Multipass VM for this tutorial, you will need to route the IP from Multipass. To do this first get the IP of the Multipass VM.
> Outside the Multipass VM run:
> ```
> multipass info my-juju-vm
> ```
> The IP you see here will be called <VM_IP> in this example.
>
> Then route:
> ```
> sudo ip route add <UNIT_IP> via <VM_IP>
> ```


You can now access your WordPress application at `http://<UNIT_IP>/wp-login.php` and log in with the admin username and password from the previous action.


### Clean up the environment

Congratulations! You have successfully finished the wordpress-k8s tutorial. You can now remove the
model environment that you’ve created using the following command.

```
juju destroy-model wordpress-tutorial --destroy-storage
```

If you used Multipass, to remove the Multipass instance you created for this tutorial, run the following command outside of the VM.

```
multipass delete --purge my-juju-vm
```