import pytest


def pytest_addoption(parser: pytest.Parser):
    # --openstack-rc points to an openstack credential file in the "rc" file style
    # Here's an example of that file
    # $ echo ~/openrc
    # export OS_REGION_NAME=RegionOne
    # export OS_PROJECT_DOMAIN_ID=default
    # export OS_AUTH_URL=http://10.0.0.1/identity
    # export OS_TENANT_NAME=demo
    # export OS_USER_DOMAIN_ID=default
    # export OS_USERNAME=demo
    # export OS_VOLUME_API_VERSION=3
    # export OS_AUTH_TYPE=password
    # export OS_PROJECT_NAME=demo
    # export OS_PASSWORD=nomoresecret
    # export OS_IDENTITY_API_VERSION=3
    parser.addoption("--openstack-rc", action="store", default="")
    # Akismet API key for testing the Akismet plugin
    parser.addoption("--akismet-api-key", action="store", default="")
    # OpenID username and password for testing the OpenID plugin
    parser.addoption("--openid-username", action="store", default="")
    parser.addoption("--openid-password", action="store", default="")
    # Kubernetes cluster configuration file
    parser.addoption("--kube-config", action="store", default="")
