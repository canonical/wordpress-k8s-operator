(how_to_install_themes)=

# How to install themes

Start by locating the theme from the WordPress themes page. Once you’ve located the theme, the
theme slug is the name of the theme from the URL of the selected theme page. For example, for
https://wordpress.org/themes/twentytwentytwo/ the plugin slug is `twentytwentytwo` after the
`/themes/` path in the URL.

You can now install the theme using the theme slug with `juju config`:

```
juju config wordpress-k8s themes=<theme-slug>
```

To install multiple themes at once, append more themes separated by a comma.

```
juju config wordpress-k8s themes=<theme-slug>,<theme-slug>
```

To install a theme that isn't on wordpress.org, for example a zip from a GitHub release,
give its slug and URL as `<slug>=<url>`. The slug must be the theme's folder name inside the
zip, otherwise the charm removes the theme on the next reconciliation.

```
juju config wordpress-k8s themes=<theme-slug>=https://example.com/<theme-slug>.zip
```

Once the configuration is complete, you can navigate to `http://<wordpress-unit-ip>/wp-admin/themes.php` to
verify your new theme installation.