[![CharmHub Badge](https://charmhub.io/wordpress-k8s/badge.svg)](https://charmhub.io/wordpress-k8s)
[![Publish to edge](https://github.com/canonical/wordpress-k8s-operator/actions/workflows/publish_charm.yaml/badge.svg)](https://github.com/canonical/wordpress-k8s-operator/actions/workflows/publish_charm.yaml)
[![Promote charm](https://github.com/canonical/wordpress-k8s-operator/actions/workflows/promote_charm.yaml/badge.svg)](https://github.com/canonical/wordpress-k8s-operator/actions/workflows/promote_charm.yaml)
[![Discourse Status](https://img.shields.io/discourse/status?server=https%3A%2F%2Fdiscourse.charmhub.io&style=flat&label=CharmHub%20Discourse)](https://discourse.charmhub.io)

# WordPress Operator

A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) deploying and managing WordPress on Kubernetes. [WordPress](https://wordpress.com) is the world's most popular website builder, and it's free and open-source.

This charm simplifies the deployment and operations of WordPress on Kubernetes,
including scaling the number of instances, integration with SSO, 
access to OpenStack Swift object storage for redundant file storage and more.
It allows for deployment on many different Kubernetes platforms, 
from [MicroK8s](https://microk8s.io/) to [Charmed Kubernetes](https://ubuntu.com/kubernetes) 
to public cloud Kubernetes offerings.

As such, the charm makes it easy for those looking to take control of their own content management system whilst keeping operations simple, 
and gives them the freedom to deploy on the Kubernetes platform of their choice.

For DevOps or SRE teams this charm will make operating WordPress simple and straightforward through Juju's clean interface.
It will allow easy deployment into multiple environments for testing of changes, 
and supports scaling out for enterprise deployments.

For information about how to deploy, integrate, and manage this charm, see the Official [wordpress-k8s-operator Documentation](https://charmhub.io/wordpress-k8s/docs).

## Get Started

To begin, refer to the [Getting Started](https://charmhub.io/wordpress-k8s/docs/tutorial) tutorial for step-by-step instructions.

### Basic Operations

The following actions are available for the charm:
- get-initial-password
- rotate-wordpress-secrets

You can find more information about supported actions in [the Charmhub documentation](https://charmhub.io/wordpress-k8s/actions).

## Integrations

Deployment of WordPress requires a relational database. The integration with the mysql interface is required by the wordpress-k8s charm for which `mysql-k8s` charm can be deployed as follows:

```
juju deploy mysql-k8s --trust
# 'database' interface is required since mysql-k8s charm provides multiple compatible interfaces
juju integrate wordpress-k8s mysql-k8s:database
```

Apart from this required integration, the charm can be integrated with other Juju charms and services as well. You can find the full list of integrations in [the Charmhub documentation](https://charmhub.io/wordpress-k8s/integrations).

## Learn more

- [Read more](https://charmhub.io/wordpress-k8s/docs)
- [Developer documentation](https://codex.wordpress.org/Developer_Documentation)
- [Official webpage](https://wordpress.com)
- [Troubleshooting](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)

## Project and community

The WordPress Operator is a member of the Ubuntu family. 
It's an open source project that warmly welcomes community projects, contributions, suggestions, fixes and constructive feedback.

- [Code of conduct](https://ubuntu.com/community/code-of-conduct)
- [Get support](https://discourse.charmhub.io/)
- [Contribute](https://charmhub.io/wordpress-k8s/docs/contributing-hacking)
- [Matrix](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)

