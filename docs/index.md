---
myst:
  html_meta:
    "description lang=en": "A Juju charm deploying and managing WordPress on Kubernetes."
---

# WordPress operator

A [Juju](https://juju.is/) {ref}`charm <juju:charm>` deploying and managing WordPress on Kubernetes. [WordPress](https://wordpress.org/) is the world's most popular website builder, and it's free and open-source.

Like any Juju charm, this charm supports one-line deployment, configuration, integration,
scaling, and more. For WordPress, this includes:

* Horizontal scaling with OpenStack Swift object storage
* Plugin and theme management through Juju configuration
* Web application firewall (ModSecurity) and Akismet spam protection
* Observability through the {external+cos:doc}`Canonical Observability Stack (COS) <index>`

The WordPress charm allows for deployment on many different Kubernetes platforms, from
[MicroK8s](https://canonical.com/microk8s) to [Charmed Kubernetes](https://ubuntu.com/kubernetes)
to public cloud Kubernetes offerings.

This charm will make operating WordPress straightforward for DevOps or SRE teams through Juju's
clean interface.

## In this documentation

```{list-table}
:header-rows: 1
:widths: 10 25

* -
  -
* - **Get started**
  - {ref}`Deploy the WordPress charm <tutorial_index>`
* - **Deployment**
  - {ref}`Retrieve initial credentials <how_to_retrieve_initial_credentials>` | {ref}`Configure initial settings <how_to_configure_initial_settings>` | {ref}`Configure hostname <how_to_configure_hostname>` | {ref}`Configurations <reference_configurations>`
* - **Operations**
  - {ref}`Upgrade <how_to_upgrade>` | {ref}`Redeploy <how_to_redeploy>` | {ref}`Integrate with COS <how_to_integrate_with_cos>` | {ref}`Relation endpoints <reference_relation_endpoints>` | {ref}`Actions <reference_actions>`
* - **Scaling and storage**
  - {ref}`Configure object storage <how_to_configure_object_storage>` | {ref}`External access requirements <reference_external_access>`
* - **Plugins and themes**
  - {ref}`Install plugins <how_to_install_plugins>` | {ref}`Install themes <how_to_install_themes>` | {ref}`Plugins <reference_plugins>` | {ref}`Themes <reference_themes>`
* - **Design**
  - {ref}`Charm architecture <reference_charm_architecture>`
* - **Security**
  - {ref}`Security overview <explanation_security_overview>` | {ref}`Enable WAF <how_to_enable_waf>` | {ref}`Enable antispam <how_to_enable_antispam>` | {ref}`Rotate secrets <how_to_rotate_secrets>`
```

## How this documentation is organized

This documentation uses the [Diátaxis documentation structure](https://diataxis.fr/).

* The {ref}`Tutorial <tutorial_index>` takes you step-by-step through a basic deployment of the WordPress charm.
* The {ref}`How-to guides <how_to_index>` assume you have basic familiarity with the WordPress charm. Learn more about setting up, using, maintaining, and contributing to this charm.
* {ref}`Reference <reference_index>` provides a guide to actions, configurations, relations, and other technical details.
* {ref}`Explanation <explanation_index>` includes topic overviews, background and context, and detailed discussion.
* The {ref}`Changelog <changelog>` holds all notable changes to the charm.

## Contributing to this documentation

Documentation is an important part of this project, and we take the same open-source approach to the documentation as the code. As such, we welcome community contributions, suggestions, and constructive feedback on our documentation. See [How to contribute](how_to_contribute) for more information.

If there's a particular area of documentation that you'd like to see that's missing, please [file a bug](https://github.com/canonical/wordpress-k8s-operator/issues).

## Project and community

The WordPress Operator is a member of the Ubuntu family. It's an open-source project that warmly welcomes community projects, contributions, suggestions, fixes, and constructive feedback.

### Governance and policies

- [Code of conduct](https://ubuntu.com/community/code-of-conduct)

### Get involved

- [Get support](https://discourse.charmhub.io/)
- [Join our online chat](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
- {ref}`Contribute <how_to_contribute>`

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
