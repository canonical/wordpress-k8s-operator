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

Operators control charm behaviour through configuration options and Juju
actions. Understanding the overall charm architecture provides the structural
context needed to see how those settings and actions interact at runtime.

* [Configurations](configurations.md)
* [Actions](actions.md)
* [Charm architecture](charm-architecture.md)

## Connectivity

The WordPress charm exposes its service externally and communicates with other
applications through Juju relation endpoints. Correct connectivity
configuration is essential for both end-user access and cross-application
integration.

* [Relation endpoints](relation-endpoints.md)
* [External access](external-access.md)

## Extensibility

Your WordPress site's functionality is extended through plugins and themes. The charm
provides specific mechanisms for adding or customizing them within a
Juju-managed deployment.

* [Plugins](plugins.md)
* [Themes](themes.md)

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