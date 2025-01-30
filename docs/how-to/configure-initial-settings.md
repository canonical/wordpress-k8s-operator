# How to configure initial settings\*

\*This only works when setting up WordPress initially, before database relation setup. Changing the
value afterwards has no effect.

By providing configuration value for `initial_settings` at deployment, you can tweak a few
WordPress settings. For detailed information on configurable parameters, please refer to the
[reference guide](https://charmhub.io/wordpress-k8s/docs/reference-configurations).

```
WORDPRESS_SETTINGS=$(cat << EOF
user_name: admin
admin_email: admin@testing.com
admin_password: <strong-password>
EOF
)
juju deploy wordpress-k8s --config initial_settings=$WORDPRESS_SETTINGS
```

You can verify your initial WordPress settings by navigating to ​​the general settings page in
WordPress(`http://<wordpress-unit-ip>/wp-admin/options-general.php`).

You can also pass in the wordpress-k8s `configuration.yaml` file with the parameters above. See how
to pass in a configuration file in the
[juju documentation](https://juju.is/docs/olm/manage-applications#heading--configure-an-application-during-deployment).