# OCI Image

### wordpress-image

The wordpress-image is custom built to include a default set of plugins and themes. The list of
plugins and themes can be found at the reference section of the
[documentation](https://charmhub.io/wordpress-k8s/docs/reference-plugins). Since WordPress is
an application running on php, required libraries and dependencies are installed during the build
process.

WordPress application installation is done at runtime during database connection setup. This can
happen during database relation changed, database relation joined or database config changed
events.
To facilitate the WordPress installation process,
[WordPress CLI](https://make.wordpress.org/cli/handbook/guides/installing/) is embedded in the OCI
image during the build step. The latest CLI php archive file from source is used.

Currently, WordPress version 5.9.3 is used alongside Ubuntu 20.04 base image. The Ubuntu base image
hasn't yet been upgraded to 22.04 due to an unsupported php version 8 for
`wordpress-launchpad-integration` plugin (supported php version 7). All other plugins and themes use
the latest stable version by default, downloaded from the source.
