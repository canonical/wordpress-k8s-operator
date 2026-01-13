---
myst:
  html_meta:
    "description lang=en": "The WordPress charm tutorial that walks a user through a basic WordPress deployment."
---

(tutorial_index)=

# Deploy the WordPress charm for the first time

The `wordpress-k8s` charm helps deploy a horizontally scalable WordPress application. This
tutorial will walk you through each step to achieve a basic WordPress deployment.

## What you'll do

1. Deploy the [WordPress K8s charm](https://charmhub.io/wordpress-k8s)
2. Deploy and integrate a database
3. Get admin credentials
4. Access the WordPress instance
5. Clean up the environment

## What you'll need

You will need a working station, e.g., a laptop, with AMD64 architecture. Your working station
should have at least 4 CPU cores, 8 GB of RAM, and 50 GB of disk space.

````{tip}
You can use Multipass to create an isolated environment by running:
```
multipass launch 24.04 --name charm-tutorial-vm --cpus 4 --memory 8G --disk 50G
```
````

This tutorial requires the following software to be installed on your working station
(either locally or in the Multipass VM):

- Juju 3
- MicroK8s 1.33

Use [Concierge](https://github.com/canonical/concierge) to set up Juju and MicroK8s:

```
sudo snap install --classic concierge
sudo concierge prepare -p microk8s
```

This first command installs Concierge, and the second command uses Concierge to install
and configure Juju and MicroK8s.

For this tutorial, Juju must be bootstrapped to a MicroK8s controller. Concierge should
complete this step for you, and you can verify by checking for `msg="Bootstrapped Juju" provider=microk8s`
in the terminal output and by running `juju controllers`.

If Concierge did not perform the bootstrap, run:

```
juju bootstrap microk8s tutorial-controller
```

To be able to work inside the Multipass VM, log in with the following command:

```bash
multipass shell charm-tutorial-vm 
```

```{note}
If you're working locally, you don't need to do this step.
```

## Set up the environment

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
`mysql` {ref}`interface <juju:relation>` is required by the `wordpress-k8s`
charm, so we will use the [`mysql-k8s`](https://charmhub.io/mysql-k8s) charm.

Let's deploy the `mysql-k8s` charm and integrate it with the `wordpress-k8s` charm:

```
juju deploy mysql-k8s --trust
juju integrate wordpress-k8s mysql-k8s:database
```

The `database` interface is required since `mysql-k8s` charm provides multiple compatible interfaces.

Wait for the charms to finish deploying:

```
juju wait-for application wordpress-k8s --query='status=="active"' --timeout 10m
juju wait-for application mysql-k8s --query='status=="active"' --timeout 10m
```

Run `juju status` to check the current status of the deployment. The output should be similar to the following:

```{terminal}
:output-only:

Model               Controller          Cloud/Region        Version  SLA          Timestamp
wordpress-tutorial  microk8s-localhost  microk8s/localhost  3.5.3    unsupported  18:48:09Z

App            Version                  Status  Scale  Charm          Channel        Rev  Address         Exposed  Message
mysql-k8s      8.0.37-0ubuntu0.22.04.3  active      1  mysql-k8s      8.0/stable     180  10.152.183.254  no
wordpress-k8s  6.4.3                    active      1  wordpress-k8s  latest/stable   87  10.152.183.56   no

Unit              Workload  Agent  Address       Ports  Message
mysql-k8s/0*      active    idle   10.1.200.163         Primary
wordpress-k8s/0*  active    idle   10.1.200.161
```

When the status shows "Active" for both the WordPress and MySQL charms, the deployment is considered finished.

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

```{terminal}
:output-only:

Running operation 1 with 1 task
  - task 2 on unit-wordpress-k8s-0

Waiting for task 2...
password: <password>

```

Password should look something like: `XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`.

````{note}
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
````

Now let's access the WordPress application in a browser. First, grab the IP address of the WordPress charm unit:

```
UNIT_IP=$(juju status --format json | jq -r '.applications.wordpress-k8s.units."wordpress-k8s/0"."address"')
```

Test that the application is reachable using `curl`:

```
curl http://$UNIT_IP/wp-login.php
```

Now access the WordPress application at `http://<UNIT_IP>/wp-login.php` and log in with the
admin username and password from the previous action.

## Clean up the environment

Congratulations! You successfully deployed the WordPress charm, added a database, and accessed the application.

You can clean up your environment by following this guide:
{ref}`Tear down your test environment <juju:tear-things-down>`

## Next steps

You achieved a basic deployment of the WordPress charm. If you want to go farther in your deployment
or learn more about the charm, check out these pages:

- Perform basic operations with your deployment like
  [installing plugins](how_to_install_plugins)
  or [themes](how_to_install_themes).
- Set up monitoring for your deployment by
  [integrating with the Canonical Observability Stack (COS)](how_to_integrate_with_cos).
- Make your deployment more secure by [enabling antispam](how_to_enable_antispam) or
  [rotating secrets](how_to_rotate_secrets),
  and learn more about the charm's security in
  [Security overview](explanation_security_overview).
- Learn more about the available [relation endpoints](reference_relation_endpoints)
  for the WordPress charm.
