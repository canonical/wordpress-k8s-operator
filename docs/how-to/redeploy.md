# Redeploy

This guide provides the necessary steps for migrating an existing WordPress
instance to a new charm instance.

## Migrate Database

Follow the instructions
in [the mysql charm migration guide](https://charmhub.io/mysql/docs/h-migrate-cluster-via-restore)
to migrate the content of the WordPress MySQL database.

## Migrate Media Files

### Media Files Stored in Kubernetes Storage

If your media files are stored in Kubernetes
storage (`wp_plugin_openstack-objectstorage_config` is not configured), use the
following steps to migrate your files:

1. Use the `juju scp` command to transfer files from
   the `/var/www/html/wp-content/uploads` directory of the old `wordpress`
   container to a local directory.
2. Use the `juju scp` command again to copy these files from the local
   directory to the `/var/www/html/wp-content/uploads` directory in the new
   WordPress charm instance's `wordpress` container.

### Media Files Stored in Object Storage

If your media files are stored in object storage and
the `wp_plugin_openstack-objectstorage_config` is not configured, you have two
options:

1. Provide the new WordPress charm instance with the same credentials and
   connection information for the object storage. This allows the new instance
   to automatically access the existing files.
2. Use tools like [rclone](https://rclone.org) to copy files from the old
   storage bucket to a new bucket for the new deployment.