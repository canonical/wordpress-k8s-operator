---
myst:
  html_meta:
    "description lang=en": "Technical information related to the WordPress charm."
---

(reference_index)=

# Reference

Technical specifications and architectural details for the
WordPress charm serve as authoritative look-up material when configuring,
extending, or integrating the charm.

## Configuration and operations

Operators control charm behavior through configuration options and Juju
actions. Understanding the overall charm architecture provides the structural
context needed to see how those settings and actions interact at runtime.

* {ref}`Configurations <reference_configurations>`
* {ref}`Actions <reference_actions>`
* {ref}`Charm architecture <reference_charm_architecture>`

## Connectivity

The WordPress charm exposes its service externally and communicates with other
applications through Juju relation endpoints. Correct connectivity
configuration is essential for both end-user access and cross-application
integration.

* {ref}`Relation endpoints <reference_relation_endpoints>`
* {ref}`External access <reference_external_access>`

## Extensibility

Your WordPress site's functionality is extended through plugins and themes. The charm
provides mechanisms for adding or customizing them within a
Juju-managed deployment.

* {ref}`Plugins <reference_plugins>`
* {ref}`Themes <reference_themes>`

```{toctree}
:hidden:

configurations.md
actions.md
charm-architecture
relation-endpoints
external-access
plugins
themes
```