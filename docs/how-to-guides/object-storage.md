# Object storage

### Prerequisites

Follow the instructions on installing OpenStack from the OpenStack
[documentation](https://docs.openstack.org/install-guide/). For testing purposes, you can install
[DevStack](https://docs.openstack.org/devstack/latest/).

After successful installations, you should be able to see `openrc` file at the location of
installation. The contents of the `openrc` file should look something similar to the following.

```
export OS_REGION_NAME=RegionOne
export OS_PROJECT_DOMAIN_ID=default
export OS_CACERT=
export OS_TENANT_NAME=demo
export OS_USER_DOMAIN_ID=default
export OS_USERNAME=demo
export OS_VOLUME_API_VERSION=3
export OS_AUTH_TYPE=<strong-password>
export OS_PROJECT_NAME=demo
export OS_PASSWORD=<strong-password>
export OS_IDENTITY_API_VERSION=3
export OS_AUTH_URL=http://<openstack-deployment-address>/identity
```

To use the openstack cli tools, source the file with the following command.

```
source openrc
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
something like http://<openstack-deployment-address>:8080/v1/AUTH_1d449b4237d3499dabd95210c33ca150, exported under
OS_STORAGE_URL key.
tenant: demo
username: demo
```
