[![CharmHub Badge](https://charmhub.io/wordpress-k8s/badge.svg)](https://charmhub.io/wordpress-k8s)
[![Publish to edge](https://github.com/canonical/wordpress-k8s-operator/actions/workflows/publish_charm.yaml/badge.svg)](https://github.com/canonical/wordpress-k8s-operator/actions/workflows/publish_charm.yaml)
[![Promote charm](https://github.com/canonical/wordpress-k8s-operator/actions/workflows/promote_charm.yaml/badge.svg)](https://github.com/canonical/wordpress-k8s-operator/actions/workflows/promote_charm.yaml)
[![Discourse Status](https://img.shields.io/discourse/status?server=https%3A%2F%2Fdiscourse.charmhub.io&style=flat&label=CharmHub%20Discourse)](https://discourse.charmhub.io)

# WordPress operator

A [Juju](https://juju.is/) [charm](https://documentation.ubuntu.com/juju/3.6/reference/charm/) deploying and managing WordPress on Kubernetes. [WordPress](https://wordpress.com) is the world's most popular website builder, and it's free and open-source.

This charm simplifies the deployment and operations of WordPress on Kubernetes,
including scaling the number of instances, integration with SSO, 
access to OpenStack Swift object storage for redundant file storage and more.
It allows for deployment on many different Kubernetes platforms, 
from [MicroK8s](https://microk8s.io/) to [Charmed Kubernetes](https://ubuntu.com/kubernetes) 
to public cloud Kubernetes offerings.

As such, the charm makes it straightforward for those looking to take control of their own content management system while simplifying operations, 
and gives them the freedom to deploy on the Kubernetes platform of their choice.

For DevOps or SRE teams this charm will make operating WordPress straightforward through Juju's clean interface.
It will allow deployment into multiple environments for testing of changes, 
and supports scaling out for enterprise deployments.

For information about how to deploy, integrate, and manage this charm, see the Official [WordPress K8s charm documentation](https://documentation.ubuntu.com/wordpress-k8s-charm/latest/).

## Get started

To begin, refer to the [Getting Started](docs/tutorial.md) tutorial for step-by-step instructions.

### Basic operations

The following actions are available for the charm:
- get-initial-password
- rotate-wordpress-secrets

You can find more information about supported actions in [the Charmhub documentation](https://charmhub.io/wordpress-k8s/actions).

The charm supports further customization, including:
- [Installing additional plugins](docs/how-to/install-plugins.md)
- [Installing additional themes](docs/how-to/install-themes.md)
- [Connecting to observability](docs/how-to/integrate-with-cos.md)

## Integrations

Deployment of WordPress requires a relational database. The integration with the MySQL interface is required by the wordpress-k8s charm for which `mysql-k8s` charm can be deployed as follows:

```
juju deploy mysql-k8s --trust
# 'database' interface is required since mysql-k8s charm provides multiple compatible interfaces
juju integrate wordpress-k8s mysql-k8s:database
```

Apart from this required integration, the charm can be integrated with other Juju charms and services as well. You can find the full list of integrations in [the Charmhub documentation](https://charmhub.io/wordpress-k8s/integrations).

## Documentation

Our documentation is stored in the `docs` directory.
It is based on the Canonical starter pack
and hosted on [Read the Docs](https://about.readthedocs.com/). In structuring,
the documentation employs the [Diátaxis](https://diataxis.fr/) approach.

You may open a pull request with your documentation changes, or you can
[file a bug](https://github.com/canonical/wordpress-k8s-operator/issues) to provide constructive feedback or suggestions.

To run the documentation locally before submitting your changes:

```bash
cd docs
make run
```

GitHub runs automatic checks on the documentation
to verify spelling, validate links and style guide compliance.

You can (and should) run the same checks locally:

```bash
make spelling
make linkcheck
make vale
```

## Learn more

- [Read more](https://documentation.ubuntu.com/wordpress-k8s-charm/latest/)
- [Developer documentation](https://codex.wordpress.org/Developer_Documentation)
- [Official webpage](https://wordpress.com)
- [Troubleshooting](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)

## Project and community

The WordPress Operator is a member of the Ubuntu family. 
It's an open source project that warmly welcomes community projects, contributions, suggestions, fixes and constructive feedback.

- [Code of conduct](https://ubuntu.com/community/code-of-conduct)
- [Get support](https://discourse.charmhub.io/)
- [Contribute](CONTRIBUTING.md)
- [Matrix](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)

