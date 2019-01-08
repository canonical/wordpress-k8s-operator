= generik8s charm =

A generic Juju k8s charm for deploying arbitrary container images to k8s services attached to the Juju controller.

== Overview ==

This is a k8s charm and can only be deployed to to a Juju k8s
pseudo-cloud, attached to a controller using 'juju add-k8s'.

The image to spin up is specified in the 'image' charm configuration
option using standard docker notation (eg. 'localhost:32000/mywork-rev42').
Images must be publicly accessible.

Image configuration is specified as YAML snippets in the charm config.
Both 'container_config' and 'container_secrets' items are provided,
and they are combined together. 'container_config' gets logged,
'container_secrets' does not. Variable interpolation is done on the
configuration, allowing configuration to be pulled from supported
relations (eg. `${PGHOST}` and similar to pull configuration from a
PostgreSQL relation; only a single relation is supported).

== Details ==

See config option descriptions in config.yaml.

== Future ==

* Add mechanisms for specifying keys and retrieving images from private repositories, as required.
* Add mechanism for images to pull secrets from k8s secret stores.
* Add heathchecks to container spec (confirm something is listening on the opened ports).
