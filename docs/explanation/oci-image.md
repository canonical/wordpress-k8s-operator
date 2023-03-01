# OCI Image

### wordpress-image

The wordpress-image is custom built to include a default set of plugins and themes. The list of
plugins and themes can be found at the reference section of the
[documentation](https://charmhub.io/wordpress-k8s/docs/reference?channel=edge). Since WordPress is
an application running on php, required libraries and dependencies are installed during the build
process.

WordPress application installation is done at runtime during database connection setup. This can
happen during database relation changed, database relation joined or database config changed
events.
To facilitate the WordPress installation process, WordPress cli is embedded in the OCI image during
build step. The latest cli php archive file from source is used.

Currently, WordPress version 5.9.3 is used alongside Ubuntu 20.04 base image. The Ubuntu base image
is not being upgraded to 22.04 due to an unsupported php version 8 for
`wordpress-launchpad-integration` plugin(supported php version 7). All other plugins and themes use
the latest stable version by default, downloaded from the source.

### apache-prometheus-exporter-image

This is the image required for sidecar container apache-prometheus-exporter. Openly available image
`bitnami/apache-exporter` is used. Read more about the image from the official Docker hub
[source](https://hub.docker.com/r/bitnami/apache-exporter/).
