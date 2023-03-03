# Install plugins

Start by locating the plugin from the WordPress [plugins page](https://wordpress.org/plugins/).
Once you’ve located the plugin, the plugin slug is the name of the plugin from the URL of the
selected theme page. For example, `https://wordpress.org/plugins/akismet/` the plugin slug is
“akismet” after the “/plugins/” path in the URL. You can now install the plugin using the plugin
slug with `juju config`.

```
juju config wordpress-k8s plugins=<plugin-slug>
```

To install multiple plugins at once, append more plugins separated by a comma.

```
juju config wordpress-k8s plugins=<plugin-slug>,<plugin-slug>
```

Once the configuration is complete, you can navigate to `http://<wordpress-unit-ip>/wp-admin/plugins.php` to
verify your new plugin installation.
