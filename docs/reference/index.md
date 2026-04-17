---
myst:
  html_meta:
    "description lang=en": "Technical information related to the WordPress charm."
---

(reference_index)=

# Reference

The pages in this section contain technical specifications, API descriptions,
and architectural details for the WordPress charm. Use them as authoritative
look-up material when configuring, extending, or integrating the charm.

## Configuration and operations

This section documents the knobs available to operators and the automated
actions the charm exposes. It also describes the overall charm architecture,
providing the structural context needed to understand how those settings and
actions interact at runtime.

* [Configurations](configurations.md)
* [Actions](actions.md)
* [Charm architecture](charm-architecture.md)

## Connectivity

This section covers how the WordPress charm exposes its service externally and
how it integrates with other applications through Juju relation endpoints.

* [Relation endpoints](relation-endpoints.md)
* [External access](external-access.md)

## Extensibility

This section details the plugins and themes that the charm supports, including
the mechanisms for adding or customising them in your deployment.

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