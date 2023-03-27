# How to enable antispam (Akismet)

Enabling anti spam filter can be easily done by just supplying `wp_plugin_akismet_key` to the
configurations.

To register for Akismet, please visit Akismet official [webpage](https://akismet.com/) and follow
the instructions. After obtaining the Akismet API key, you can now run the following command to
enable Akismet plugin.

```
juju config wordpress-k8s wp_plugin_akismet_key=<akismet-api-key>
```

The Akismet plugin should automatically be active after running the configuration.
