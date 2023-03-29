# How to contribute

## Overview

This document explains the processes and practices recommended for contributing enhancements to the
WordPress operator.

- Generally, before developing enhancements to this charm, you should consider [opening an issue
  ](https://github.com/canonical/wordpress-k8s-operator/issues) explaining your use case.
- If you would like to chat with us about your use-cases or proposed implementation, you can reach
  us at [Canonical Mattermost public channel](https://chat.charmhub.io/charmhub/channels/charm-dev)
  or [Discourse](https://discourse.charmhub.io/).
- Familiarising yourself with the [Charmed Operator Framework](https://juju.is/docs/sdk) library
  will help you a lot when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically examines
  - code quality
  - test coverage
  - user experience for Juju operators of this charm.
- Please help us out in ensuring easy to review branches by rebasing your pull request branch onto
  the `main` branch. This also avoids merge commits and creates a linear Git commit history.
- For further information on contributing, please refer to our
  [Contributing Guide](https://github.com/canonical/is-charms-contributing-guide)

## Developing

### Building from source

To build and deploy wordpress-k8s charm from source follow the steps below.

#### Docker image build

Build the `wordpress.Dockerfile` image with the following command.

```
docker build -t wordpress -f wordpress.Dockerfile .
```

#### Microk8s upload docker artifacts

For microk8s to pick up the locally built image, you must export the image and import it within
microk8s.

```
docker save wordpress > wordpress.tar
microk8s ctr image import wordpress.tar
```

#### Build the charm

Build the charm locally using charmcraft. It should output a .charm file.

```
charmcraft pack
```

### Deploy WordPress

Deploy the locally built WordPress charm with the following command.

```
juju deploy ./wordpress-k8s_ubuntu-22.04-amd64_ubuntu-20.04-amd64.charm \
  --resource wordpress-image=wordpress \
  --resource apache-prometheus-exporter-image=bitnami/apache-exporter:0.11.0
```

You should now be able to see your local wordpress-k8s charm progress through the stages of the
deployment through `juju status --watch 2s`.

### Testing

The following commands can then be used to run the tests:

- `tox`: Runs all of the basic checks (`lint`, `unit`, `static`, and `coverage-report`).
- `tox -e fmt`: Runs formatting using `black` and `isort`.
- `tox -e lint`: Runs a range of static code analysis to check the code.
- `tox -e static`: Runs other checks such as `bandit` for security issues.
- `tox -e unit`: Runs the unit tests.
- `tox -e integration`: Runs the integration tests. Integration tests require
  [additional arguments](https://github.com/canonical/wordpress-k8s-operator/blob/main/tests/conftest.py)
  depending on the test module.

## Canonical contributor agreement

Canonical welcomes contributions to the WordPress Operator. Please check out our
[contributor agreement](https://ubuntu.com/legal/contributors) if you're interested in contributing
to the solution.
