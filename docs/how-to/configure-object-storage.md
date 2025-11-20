(how_to_configure_object_storage)=

# How to configure object storage

Object storage configuration is required for the `wordpress-k8s` charm to work with
multi-unit deployments.

## Prerequisites

Follow the instructions on installing OpenStack from the OpenStack
[documentation](https://docs.openstack.org/install-guide/). For testing purposes, you can install
[DevStack](https://docs.openstack.org/devstack/latest/).

After a successful installation, you should be able to see the `openrc` file at the location of
installation. Source `openrc` and load the credentials with:

```bash
source openrc && printenv | grep OS_
```

The output of the command above should look something similar to the following.

```{terminal}
:input: source openrc && printenv | grep OS_
export OS_CACERT=
export OS_PROJECT_NAME=demo
export OS_TENANT_NAME=demo
export OS_USERNAME=demo
export OS_PASSWORD=<strong-password>
export OS_REGION_NAME=RegionOne
export OS_IDENTITY_API_VERSION=3
export OS_AUTH_TYPE=password
export OS_AUTH_URL=http://<openstack-deployment-address>/identity
export OS_USER_DOMAIN_ID=default
export OS_PROJECT_DOMAIN_ID=default
export OS_VOLUME_API_VERSION=3
```

## Configure the OpenStack object storage plugin

To configure Swift storage for `wordpress-k8s`, copy and paste the following YAML content and adjust
the values accordingly.

```
auth-url: http://<openstack-deployment-address>/identity/v3
bucket: WordPress
copy-to-swift: 1
domain: Default
object-prefix: wp-content/uploads/
password: <strong-password>
region: RegionOne
remove-local-file: 0
serve-from-swift: 1
swift-url: swift_auth_url
tenant: demo
username: demo
```

```{note}
The `swift-url` value can be obtained by running `swift auth`. The value should look
something like http://<openstack-deployment-address>:8080/v3/AUTH_1d449b4237d3499dabd95210c33ca150, exported under
OS_STORAGE_URL key.
```

You can then configure the `wordpress-k8s` charm using the YAML contents above.

```bash
juju config wordpress-k8s wp_plugin_openstack-objectstorage_config="$(cat <path-to-yaml>)"
```
