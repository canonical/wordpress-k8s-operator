# How to update WordPress Charm

Before updating the Charm you need to backup the database using mysql charm's `create-backup` action.

```
juju run mysql/leader create-backup
```
Additional info can be found about backup on [Charmhub](https://charmhub.io/mysql/docs/h-create-and-list-backups)

Then you can update the WordPress Charm.

```
juju refresh wordpress-k8s
```