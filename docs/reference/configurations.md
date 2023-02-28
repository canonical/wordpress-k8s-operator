# Configurations

- _blog_hostname_: Hostname for accessing WordPress, if ingress relation is active. Defaults to the
  application name.
- _db_host_: MySQL database host. Takes precedence over database relation if set. Must be set with
  a complete set of database configurations to take effect.
- _db_name_: MySQL database name. Takes precedence over database relation if set. Must be set with
  a complete set of database configurations to take effect.
- _db_user_: MySQL database user. Takes precedence over database relation if set. Must be set with
  a complete set of database configurations to take effect.
- _db_password_: MySQL database user’s password. Takes precedence over database relation if set.
  Must be set with a complete set of database configurations to take effect.
- _initial_settings_: YAML formatted WordPress configuration. It is used only
  during initial deployment. Changing it at a later stage has no effect.
  If set to non empty string required keys are:

  ```yaml
  user_name: admin_username
  admin_email: name@example.com
  ```

  Optionally you can also provide

  ```yaml
  admin_password: <secret> # auto generated if not set
  ```

  If _admin_password_ is not provided it will be automatically generated and stored on juju's peer
  relation data bag.

- _plugins_: Plugin slugs of plugins to be installed, separated by comma. Including or excluding a
  default plugin here has no effect.
- _themes_: Theme slugs of themes to be installed, separated by comma. Including or excluding a
  default theme here has no effect.
- _wp_plugin_akismet_key_: Akismet anti-spam plugin key. If empty, akismet will not be enabled
  automatically.
- _wp_plugin_openid_team_map_: Launchpad teams and corresponding access levels, for use with the
  openid plugins.

  Valid WordPress access levels are: administrator, editor, author, contributor, subscriber

  If empty, OpenID will not be enabled.

  Format is key=value pairs (where key is the Launchpad team, and value is
  the WordPress role) - commas separate multiple pairs.

  Example format:

  "site-sysadmins=administrator,site-editors=editor,site-executives=editor"

- _wp_plugin_openstack_objectstorage_config_: YAML dictionary with keys named after WordPress
  settings and the desired values. Please note that the settings will be reset to values provided
  every time hooks run. Below are available values of the configuration yaml.
  It is important to note that for multi-unit deployments, the `openstack-objectstorage-k8s` plugin
  must be enabled to sync data across WordPress applications.

  ```
  auth-url:authentication URL to openstack. Example: http://10.100.115.2/identity
  bucket: (string) name of the bucket for WordPress. Example: WordPress
  copy-to-shift: (string) string value ‘1’ or ‘0’ denoting true, false respectively on whether to
    copy the local data to swift. Example: 1
  domain: (string) OpenStack Project domain ID. Example: Default
  hidpi-images: (string) string value ‘1’ or ‘0’ denoting true, false respectively on whether to
    enable high resolution images.
  object-prefix: (string) Object path prefix. Example: wp-content/uploads/
  object-versioning: (string) string value ‘1’ or ‘0’ denoting true, false respectively on whether
    to enable object versioning in Swift bucket. Read more about object versioning from the source
    documentation.
  password: (string) OpenStack password. Example: openstack_secret_password
  permissions: (string)
  region: (string) OpenStack region
  remove-local-file: (string) string value ‘1’ or ‘0’ denoting true, false respectively on whether
    to remove local file. Example: 0
  serve-from-swift: (string) string value ‘1’ or ‘0’ denoting true, false respectively on whether
    to serve the contents file directly from swift. Example: 1
  swift-url: (string) OpenStack Swift URL. example: http://10.100.115.2:8080/v1
  tenant: (string) OpenStack tenant name. Example: demo
  username: (string) OpenStack username. Example: demo
  ```

- _use_nginx_ingress_modsec_: Boolean value denoting whether modsec based WAF should be enabled.
  Applied if ingress relation is available.
