# Configure object storage

Object storage configuration is required for wordpress-k8s charm to work with multi-unit
deployments.

### Prerequisites

Follow the instructions on installing OpenStack from the OpenStack
[documentation](https://docs.openstack.org/install-guide/). For testing purposes, you can install
[DevStack](https://docs.openstack.org/devstack/latest/).

After successful installations, you should be able to see `openrc` file at the location of
installation. Source `openrc` and load the credentials by running

```
source openrc && printenv | grep OS_
```

You should be able to see

The contents of the command above should look something similar to the following.

```
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

### Configure openstack-objectstorage plugin

To configure Swift storage for wordpress-k8s, copy and paste the following yaml content and adjust
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
swift-url: swift_auth_url # obtain the value by running `swift auth`. The value should look
something like http://<openstack-deployment-address>:8080/v3/AUTH_1d449b4237d3499dabd95210c33ca150, exported under
OS_STORAGE_URL key.
tenant: demo
username: demo
```

You can then configure wordpress-k8s charm using the yaml contents above.

```
juju config wordpress-k8s wp_plugin_openstack-objectstorage_config="$(cat <path-to-yaml>)"
```
