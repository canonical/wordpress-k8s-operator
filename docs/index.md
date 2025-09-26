---
myst:
  html_meta:
    "description lang=en": "A Juju charm deploying and managing WordPress on Kubernetes."
---

# WordPress operator

A [Juju](https://juju.is/) {ref}`charm <juju:charm>` deploying and managing WordPress on Kubernetes. [WordPress](https://wordpress.com/) is the world's most popular website builder, and it's free and open-source.

This charm simplifies initial deployment and operations of WordPress on Kubernetes, including scaling the number of instances, integration with SSO, access to OpenStack Swift object storage for redundant file storage, and more. It allows for deployment on many different Kubernetes platforms, from [MicroK8s](https://microk8s.io/) to [Charmed Kubernetes](https://ubuntu.com/kubernetes) to public cloud Kubernetes offerings.

This charm will make operating WordPress straightforward for DevOps or SRE teams through Juju's clean interface. It will allow deployment into multiple environments to test changes and support scaling out for enterprise deployments.

## In this documentation

| | |
|--|--|
|  [Tutorials](tutorial_index)</br>  Get started - a hands-on introduction to using the Charmed WordPress operator for new users </br> |  [How-to guides](how_to_index) </br> Step-by-step guides covering key operations and common tasks |
| [Reference](reference_index) </br> Technical information - specifications, APIs, architecture | [Explanation](explanation_index) </br> Concepts - discussion and clarification of key topics  |

## Contributing to this documentation

Documentation is an important part of this project, and we take the same open-source approach to the documentation as the code. As such, we welcome community contributions, suggestions, and constructive feedback on our documentation. See [How to contribute](how_to_contribute) for more information.

If there's a particular area of documentation that you'd like to see that's missing, please [file a bug](https://github.com/canonical/wordpress-k8s-operator/issues).

## Project and community

The WordPress Operator is a member of the Ubuntu family. It's an open-source project that warmly welcomes community projects, contributions, suggestions, fixes, and constructive feedback.

- [Code of conduct](https://ubuntu.com/community/code-of-conduct)
- [Get support](https://discourse.charmhub.io/)
- [Join our online chat](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
- [Contribute](how_to_contribute)

Thinking about using the WordPress Operator for your next project? [Get in touch](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)!

```{toctree}
:hidden:
:maxdepth: 1

Tutorial <tutorial>
how-to/index
reference/index
explanation/index
changelog
```