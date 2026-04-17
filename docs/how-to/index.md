---
myst:
  html_meta:
    "description lang=en": "How-to guides covering the entire WordPress charm operations lifecycle."
---

(how_to_index)=

# How-to guides

These guides cover key processes and common tasks across the full operations
lifecycle of the WordPress charm. Whether you are standing up a new deployment
or maintaining one in production, each guide focuses on a specific task and
assumes you have a running Juju environment.

## Initial setup

These guides walk you through the first steps after deploying the charm, giving
you the credentials and baseline configuration needed before the site is ready
to serve traffic.

* [Retrieve initial credentials]
* [Configure initial settings]

## Basic operations

These guides cover the day-to-day operational tasks that keep a WordPress
deployment running and integrated with the rest of your infrastructure.

* [Configure hostname]
* [Configure object storage]
* [Install plugins]
* [Install themes]
* [Integrate with COS]

## Security

These guides help you harden your WordPress deployment against spam, malicious
traffic, and credential exposure. Apply them as a set for a defence-in-depth posture.

* [Enable antispam]
* [Enable WAF]
* [Rotate secrets]

## Maintenance and development

These guides cover keeping the charm up to date, recovering from a broken
deployment, and contributing improvements back to the project.

* [Upgrade]
* [Redeploy]
* [Contribute]

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
[Contribute]: contribute.md

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
Contribute <contribute.md>
```