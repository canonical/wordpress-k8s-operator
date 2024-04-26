# External Access Requirements

The WordPress charm may need to connect to external services and resources for
certain functionalities.

## OpenStack Object Storage

When activated, the WordPress instance will need to connect to configured
OpenStack object storage for uploading and retrieval of media and assets.

## Akismet Spam Protection Plugin

The Akismet spam protection plugin, when enabled via the `wp_plugin_akismet_key`
configuration, requires internet access to connect with
the [Akismet API server](https://akismet.com/support/general/connection-issues/).
This connection is essential for verifying and managing spam content.

## Installing Additional Plugins or Themes

For the installation of additional plugins or themes, the WordPress instance
must access the main WordPress site to download installation files. Some plugins
or themes might also need internet access to operate correctly after they are
installed.
