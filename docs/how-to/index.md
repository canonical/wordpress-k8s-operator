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

* {ref}`Retrieve initial credentials <how_to_retrieve_initial_credentials>`
* {ref}`Configure initial settings <how_to_configure_initial_settings>`

## Basic operations

Day-to-day operational tasks -- such as hostname configuration
and theme management -- keep a WordPress
deployment healthy and connected to the rest of your infrastructure.

* {ref}`Configure hostname <how_to_configure_hostname>`
* {ref}`Configure object storage <how_to_configure_object_storage>`
* {ref}`Install plugins <how_to_install_plugins>`
* {ref}`Install themes <how_to_install_themes>`
* {ref}`Integrate with COS <how_to_integrate_with_cos>`

## Security

A public-facing WordPress site is exposed to spam, malicious traffic, and
credential leakage. The charm comes equipped with basic security features
that help to mitigate these threats.

* {ref}`Enable antispam <how_to_enable_antispam>`
* {ref}`Enable WAF <how_to_enable_waf>`
* {ref}`Rotate secrets <how_to_rotate_secrets>`

## Maintenance and development

Upgrades, redeployments, and community contributions ensure the WordPress
charm stays current and benefits from ongoing improvements.

* {ref}`Upgrade <how_to_upgrade>`
* {ref}`Redeploy <how_to_redeploy>`
* {ref}`Contribute <how_to_contribute>`

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
Contribute <contribute>
```