(tutorial_index)=

# Deploy the WordPress charm for the first time

The `wordpress-k8s` charm helps deploy a horizontally scalable WordPress application. This
tutorial will walk you through each step to achieve a basic WordPress deployment.

## What you'll need
- A working station, e.g., a laptop, with AMD64 architecture.
- Juju 3 installed. For more information about how to install Juju, see [Get started with Juju](https://canonical-juju.readthedocs-hosted.com/en/3.6/user/tutorial/).
- Juju bootstrapped to a MicroK8s controller: `juju bootstrap microk8s tutorial-controller`

[note]
You can get a working setup by using a Multipass VM as outlined in the [Set up your test environment](https://canonical-juju.readthedocs-hosted.com/en/latest/user/howto/manage-your-deployment/manage-your-deployment-environment/#set-things-up) guide.
[/note]

## What you'll do

1. Deploy the [WordPress K8s charm](https://charmhub.io/wordpress-k8s)
2. Deploy and integrate a database
3. Get admin credentials
4. Access the WordPress instance
5. Clean up the environment

## Set up the environment

To be able to work inside the Multipass VM, log in with the following command:

```bash
multipass shell my-juju-vm
```

[note]
If you're working locally, you don't need to do this step.
[/note]

To manage resources effectively and to separate this tutorial's workload from
your usual work, create a new model in the MicroK8s controller using the following command:


```
juju add-model wordpress-tutorial
```

## Deploy the WordPress charm

Start off by deploying the WordPress charm. By default it will deploy the latest stable release of
the `wordpress-k8s` charm.

```
juju deploy wordpress-k8s
```

## Deploy and integrate database 

Deployment of WordPress requires a relational database. The integration with the
`mysql` [interface](https://documentation.ubuntu.com/juju/3.6/reference/relation/) is required by the `wordpress-k8s`
charm and hence, [`mysql-k8s`](https://charmhub.io/mysql-k8s) charm will be used.

The following commands deploy the `mysql-k8s` charm and integrate it with the `wordpress-k8s` charm.

```
juju deploy mysql-k8s --trust
juju integrate wordpress-k8s mysql-k8s:database
```
The `database` interface is required since `mysql-k8s` charm provides multiple compatible interfaces.

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

## Get admin credentials 

Now that we have an active deployment, let’s access the WordPress
application by accessing the IP of a `wordpress-k8s` unit. To start managing WordPress as an
administrator, you need to get the credentials for the admin account.

By running the `get-initial-password` action on a `wordpress-k8s` unit, Juju will read and fetch the
admin credentials setup for you. You can use the following command below.

```
juju run wordpress-k8s/0 get-initial-password
```

The result should look something similar to the contents below:

```
Running operation 1 with 1 task
  - task 2 on unit-wordpress-k8s-0

Waiting for task 2...
password: <password>

```

Password should look something like: `XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`.

[note]
 If you are using Multipass VM for this tutorial, you will need to route the IP from Multipass. To do this first get the IP of the Multipass VM.
 Outside the Multipass VM run:
 ```
 multipass info my-juju-vm
 ```
 The IP you see here will be called `<VM_IP>` in this example.

 Then route:
 ```
 sudo ip route add <UNIT_IP> via <VM_IP>
 ```
[/note]


You can now access your WordPress application at `http://<UNIT_IP>/wp-login.php` and log in with the admin username and password from the previous action.


## Clean up the environment

Congratulations! You have successfully deployed the WordPress charm, added a database, and accessed the application.

You can clean up your environment by following this guide:
[Tear down your test environment](https://canonical-juju.readthedocs-hosted.com/en/3.6/user/howto/manage-your-deployment/manage-your-deployment-environment/#tear-things-down)

## Next steps

You achieved a basic deployment of the WordPress charm. If you want to go farther in your deployment
or learn more about the charm, check out these pages:

- Perform basic operations with your deployment like
  [installing plugins](https://charmhub.io/wordpress-k8s/docs/how-to-install-plugins)
  or [themes](https://charmhub.io/wordpress-k8s/docs/how-to-install-themes).
- Set up monitoring for your deployment by
  [integrating with the Canonical Observability Stack (COS)](https://charmhub.io/wordpress-k8s/docs/how-to-integrate-with-cos).
- Make your deployment more secure by [enabling antispam](https://charmhub.io/wordpress-k8s/docs/how-to-enable-antispam) or
  [rotating secrets](https://charmhub.io/wordpress-k8s/docs/how-to-rotate-secrets),
  and learn more about the charm's security in
  [Security overview](https://charmhub.io/wordpress-k8s/docs/explanation-security).
- Learn more about the available [relation endpoints](https://charmhub.io/wordpress-k8s/docs/reference-integrations)
  for the WordPress charm.
