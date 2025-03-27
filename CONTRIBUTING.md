# How to contribute 

This document explains the processes and practices recommended for contributing enhancements to the
WordPress operator.

## Overview

- Generally, before developing enhancements to this charm, you should consider [opening an issue
  ](https://github.com/canonical/wordpress-k8s-operator/issues) explaining your use case.
- If you would like to chat with us about your use-cases or proposed implementation, you can reach
  us at [Canonical Matrix public channel](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
  or [Discourse](https://discourse.charmhub.io/).
- Familiarizing yourself with the [Juju documentation](https://canonical-juju.readthedocs-hosted.com/en/latest/user/howto/manage-charms/)
  will help you a lot when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically examines
  - code quality
  - test coverage
  - user experience for Juju operators of this charm.
- Please help us out in ensuring easy to review branches by rebasing your pull request branch onto
  the `main` branch. This also avoids merge commits and creates a linear Git commit history.
- For further information on contributing, please refer to our
  [Contributing Guide](https://github.com/canonical/is-charms-contributing-guide).

## Canonical contributor agreement

Canonical welcomes contributions to the WordPress Operator. Please check out our
[contributor agreement](https://ubuntu.com/legal/contributors) if you're interested in contributing
to the solution.

## Develop

### Building from source

To build and deploy the `wordpress-k8s` charm from source follow the steps below.

#### OCI image build and upload

Use [Rockcraft](https://documentation.ubuntu.com/rockcraft/en/latest/) to create an
OCI image for the WordPress app, and then upload the image to a MicroK8s registry,
which stores OCI archives so they can be downloaded and deployed.

Enable MicroK8S registry:

```bash
microk8s enable registry
```

The following commands pack the OCI image and push it into
the MicroK8s registry:

```bash
cd <project_dir>
rockcraft pack
skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:wordpress_1.0_amd64.rock docker://localhost:32000/wordpress:latest
```

#### Build the charm

Build the charm locally using Charmcraft. It should output a `.charm` file.

```bash
charmcraft pack
```

### Deploy the charm

Deploy the locally built WordPress charm with the following command.

```bash
juju deploy ./wordpress-k8s_ubuntu-22.04-amd64.charm \
  --resource wordpress-image=localhost:32000/wordpress:latest
```

You should now be able to see your local WordPress charm progress through the stages of the
deployment through `juju status --watch 2s`.

### Test

This project uses `tox` for managing test environments. There are some pre-configured environments
that can be used for linting and formatting code when you're preparing contributions to the charm:

* `tox`: Runs all of the basic checks (`lint`, `unit`, `static`, and `coverage-report`).
* `tox -e fmt`: Runs formatting using `black` and `isort`.
* `tox -e lint`: Runs a range of static code analysis to check the code.
* `tox -e static`: Runs other checks such as `bandit` for security issues.
* `tox -e unit`: Runs the unit tests.
* `tox -e integration`: Runs the integration tests.
