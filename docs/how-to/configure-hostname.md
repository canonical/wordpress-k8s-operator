# How to configure hostname

Configure the WordPress hostname with the `blog_hostname` configuration:

```
juju config wordpress-k8s blog_hostname=<desired-hostname>
```
Check that the configuration was updated with:

```bash
juju config wordpress-k8s | grep -A 6 blog_hostname
```

The `value:` label should list `<desired-hostname>`.