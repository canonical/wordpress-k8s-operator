(how_to_enable_antispam)=

# How to enable antispam (Akismet)

Obtain an API key for Akismet by visiting the [Askimet official webpage](https://akismet.com/developers/)
and following the instructions.

Using your key, enable the Akismet plugin with:

```
juju config wordpress-k8s wp_plugin_akismet_key=<akismet-api-key>
```

The Akismet plugin should automatically be active after running the configuration.