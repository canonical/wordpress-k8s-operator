# How to upgrade

Before updating the charm you need to back up the database using
the MySQL charm's `create-backup` action.

```bash
juju run mysql/leader create-backup
```

Additional information can be found about backing up in
[the MySQL documentation](https://charmhub.io/mysql/docs/h-create-and-list-backups).

Then you can upgrade the WordPress charm:

```
juju refresh wordpress-k8s
```

After upgrading the WordPress charm you need to update the database schema:

```
juju run wordpress-k8s/0 update-database
```