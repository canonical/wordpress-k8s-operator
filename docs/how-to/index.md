---
myst:
  html_meta:
    "description lang=en": "How-to guides covering the entire WordPress charm operations lifecycle."
---

(how_to_index)=

# How-to guides

Manage the full operations lifecycle of the WordPress charm, from initial
deployment through production maintenance. Each guide assumes that you've
already deployed the charm with Juju.

## Initial setup

A freshly deployed WordPress charm requires admin credentials and baseline
configurations before the site is ready to serve traffic.

* [Retrieve initial credentials]
* [Configure initial settings]

## Basic operations

Day-to-day operational tasks -- such as hostname configuration
and theme management -- keep a WordPress
deployment healthy and connected to the rest of your infrastructure.

* [Configure hostname]
* [Configure object storage]
* [Install plugins]
* [Install themes]
* [Integrate with COS]

## Security

A public-facing WordPress site is exposed to spam, malicious traffic, and
credential leakage. The charm comes equipped with basic security features
that help to mitigate these threats.

* [Enable antispam]
* [Enable WAF]
* [Rotate secrets]

## Maintenance and development

Upgrades, redeployments, and community contributions ensure the WordPress
charm stays current and benefits from ongoing improvements.

* [Upgrade]
* [Redeploy]

<!--Links-->
[Retrieve initial credentials]: retrieve-initial-credentials.md
[Configure initial settings]: configure-initial-settings.md
[Integrate with COS]: integrate-with-cos.md
[Configure hostname]: configure-hostname.md
[Install plugins]: install-plugins.md
[Install themes]: install-themes.md
[Configure object storage]: configure-object-storage.md
[Enable antispam]: enable-antispam.md
[Enable WAF]: enable-waf.md
[Rotate secrets]: rotate-secrets.md
[Upgrade]: upgrade.md
[Redeploy]: redeploy.md

```{toctree}
:hidden:

Retrieve initial credentials <retrieve-initial-credentials.md>
Configure initial settings <configure-initial-settings.md>
Integrate with COS <integrate-with-cos.md>
Configure hostname <configure-hostname.md>
Install plugins <install-plugins.md>
Install themes <install-themes.md>
Configure object storage <configure-object-storage.md>
Enable antispam <enable-antispam.md>
Enable WAF <enable-waf.md>
Rotate secrets <rotate-secrets.md>
Upgrade <upgrade.md>
Redeploy <redeploy.md>
```