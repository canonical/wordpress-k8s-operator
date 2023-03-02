# How-to guide

### Configure WordPress\*

\*This only works when setting up WordPress initially. Changing the value afterwards has no effect.

By providing configuration value for `initial_settings` at deployment, you can tweak a few
WordPress settings. For detailed information on configurable parameters, please refer to the
[reference guide](https://charmhub.io/wordpress-k8s/docs/reference?channel=edge).

```
WORDPRESS_SETTINGS=$(cat << EOF
user_name: admin
admin_email: admin@testing.com
admin_password: mysecretpassword
EOF
)
juju deploy wordpress-k8s --config initial_settings=$WORDPRESS_SETTINGS
```

You can verify your initial WordPress settings by navigating to ​​the general settings page in
WordPress(`http://<wordpress-unit-ip>/wp-admin/options-general.php`).

You can also pass in the wordpress-k8s configuration.yaml file with the parameters above. See how
to pass in a configuration file in the
[juju docs](https://juju.is/docs/olm/manage-applications#heading--configure-an-application-during-deployment).

### Get initial admin credentials

Run the following command to get the initial admin password that can be used to login at
`http://<wordpress-unit-ip>/wp-login.php`.

```
juju run-action wordpress-k8s/0 get-initial-password --wait
```

The output of the action should look something similar to the following:

```
unit-wordpress-k8s-0:
  UnitId: wordpress-k8s/0
  id: "10"
  results:
    password: <password> # password should look something like: ATEqzix_phnAEDJOwEWXuK2CJBXlMmTS9e90aIeH9ys
  status: completed
```

You can use the password to login to the admin account in `http://<wordpress-unit-ip>/wp-admin.php`.

Note that if `admin_password` value has been passed in the `initial_settings` configuration, the
password from the action is invalid.

### Rotate WordPress secrets

To securely update all the WordPress secrets, run the following action.

```
juju run-action wordpress-k8s/0 rotate-wordpress-secrets –wait
```

This action will force users to be logged out. All sessions and cookies will be invalidated.

### Install plugins

Start by locating the plugin from the WordPress [plugins page](https://wordpress.org/plugins/).
Once you’ve located the plugin, the plugin slug is the name of the plugin from the URL of the
selected theme page. For example, `https://wordpress.org/plugins/akismet/` the plugin slug is
“akismet” after the “/plugins/” path in the URL. You can now install the plugin using the plugin
slug with `juju config`.

```
juju config wordpress-k8s plugins=akismet
```

To install multiple plugins at once, append more plugins separated by a comma.

```
juju config wordpress-k8s plugins=akismet,404page
```

Once the configuration is complete, you can navigate to `http://<wordpress-unit-ip>/wp-admin/plugins.php` to
verify your new plugin installation.

### Install themes

Start by locating the theme from the WordPress themes page. Once you’ve located the theme, the
theme slug is the name of the theme from the URL of the selected theme page. For example,
https://wordpress.org/themes/twentytwentytwo/ the plugin slug is “twentytwentytwo” after the
“/themes/” path in the URL. You can now install the theme using the theme slug with `juju config`.

```
juju config wordpress-k8s themes=twentytwentytwo
```

To install multiple themes at once, append more themes separated by a comma.

```
juju config wordpress-k8s themes=twentytwentytwo,twentytwentythree
```

Once the configuration is complete, you can navigate to `http://<wordpress-unit-ip>/wp-admin/themes.php` to
verify your new theme installation.

### Enable antispam(Akismet)

Enabling anti spam filter can be easily done by just supplying wp_plugin_akismet_key to the
configurations.

To register for Akismet, please visit Akismet official [webpage](https://akismet.com/) and follow
the instructions. After obtaining the Akismet API key, you can now run the following command to
enable Akismet plugin.

```
juju config wordpress-k8s wp_plugin_akismet_key=AKISMET_API_KEY
```

The Akismet plugin should automatically be active after running the configuration.

### Ingress integration

This step will walk you through making your WordPress application accessible via an ingress
application using a hostname of your choice.

```
juju deploy nginx-ingress-integrator
juju relate wordpress-k8s nginx-ingress-integrator
```

### Enable Modsecurity 3.0 WAF\*

\*This feature is only available for
[nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator) charm.

The modsecurity WAF is enabled by default.

By running `kubectl describe wordpress-k8s-ingress` in the appropriate namespace, the result should
look something like the following:

```
Name:             wordpress-k8s-ingress
Labels:           app.juju.is/created-by=nginx-ingress-integrator
Namespace:        cos
Address:
Ingress Class:    <none>
Default backend:  <default>
Rules:
  Host           Path  Backends
  ----           ----  --------
  wordpress-k8s
                 /   wordpress-k8s-service:80 (10.1.158.121:80)
Annotations:     nginx.ingress.kubernetes.io/enable-modsecurity: true
                 nginx.ingress.kubernetes.io/enable-owasp-modsecurity-crs: true
                 nginx.ingress.kubernetes.io/modsecurity-snippet:
                   SecRuleEngine On
                   SecAction "id:900130,phase:1,nolog,pass,t:none,setvar:tx.crs_exclusions_wordpress=1"

                   Include /etc/nginx/owasp-modsecurity-crs/nginx-modsecurity.conf
                 nginx.ingress.kubernetes.io/proxy-body-size: 20m
                 nginx.ingress.kubernetes.io/rewrite-target: /
                 nginx.ingress.kubernetes.io/ssl-redirect: false
Events:          <none>
```

Note the `nginx.ingress.kubernetes.io/enable-modsecurity: true` annotation.

### Configure hostname

To configure a different hostname for WordPress, you can configure the ingress hostname through the
wordpress-k8s configuration.

```
juju config wordpress-k8s blog_hostname=myhostname.com
```

To test locally, append the service IP of nginx-ingress-integrator to `/etc/hosts` file with your
new hostname and curl the service using the hostname.

The output of `juju status` should look similar to the following:

```
Model  Controller          Cloud/Region        Version  SLA          Timestamp
cos    microk8s-localhost  microk8s/localhost  2.9.38   unsupported  20:15:53+08:0
0

App                       Version              Status  Scale  Charm
      Channel  Rev  Address         Exposed  Message
mariadb                   mariadb/server:10.3  active      1  charmed-osm-mariadb-
k8s   stable    35  10.152.183.119  no       ready
nginx-ingress-integrator                       active      1  nginx-ingress-integr
ator  stable    54  10.152.183.86   no       Service IP(s): 10.152.183.196
wordpress-k8s                                  active      1  wordpress-k8s
                16  10.152.183.163  no

Unit                         Workload  Agent  Address       Ports     Message
mariadb/4*                   active    idle   10.1.158.73   3306/TCP  ready
nginx-ingress-integrator/0*  active    idle   10.1.158.78             Service IP(s
): 10.152.183.196
wordpress-k8s/0*             active    idle   10.1.158.121
```

Note the Service IP(s): next to nginx-ingress-integrator charm’s Status output.

Append the new hostname with the ingress IP with following command.

```
echo 10.152.183.196 myhostname.com | sudo tee -a /etc/hosts
```

Test the ingress by sending a GET request to the hostname.

```
curl myhostname.com
```

### COS integrations

#### prometheus-k8s

Deploy and relate [prometheus-k8s](https://charmhub.io/prometheus-k8s) charm with wordpress-k8s
charm through the metrics-endpoint relation via prometheus_scrape interface. Prometheus should
start scraping the metrics exposed at `:9117/metrics` endpoint.

```
juju deploy prometheus-k8s
juju relate wordpress-k8s prometheus-k8s
```

#### loki-k8s

Deploy and relate [loki-k8s](https://charmhub.io/loki-k8s) charm with wordpress-k8s charm through
the logging relation via loki_push_api interface. Promtail worker should spawn and start pushing
Apache access logs and error logs to loki.

```
juju deploy loki-k8s
juju relate wordpress-k8s loki-k8s
```

#### grafana-k8s

In order for the Grafana dashboard to function properly, grafana should be able to connect to
Prometheus and Loki as its datasource. Deploy and relate prometheus-k8s and lok-k8s charm with
[grafana-k8s](https://charmhub.io/grafana-k8s) charm through grafana-source relation.

Note that the relation “grafana-source” has to be explicitly stated since prometheus-k8s and
grafana-k8s share multiple interfaces.

```
juju deploy grafana-k8s
juju relate prometheus-k8s:grafana-source grafana-k8s:grafana-source
juju relate loki-k8s:grafana-source grafana-k8s:grafana-source
```

Then, wordpress-k8s charm can be related with grafana using the grafana-dashboard relation with
grafana_dashboard interface.

```
juju relate wordpress-k8s grafana-k8s
```

To access the Grafana dashboard for wordpress-k8s charm, run the following command to obtain
credentials for admin access.

```
juju run-action grafana-k8s/0 get-admin-password --wait
```

You can now log into the grafana dashboard by visiting `http://<grafana-unit-ip>:3000`. Navigate to
`http://<grafana-unit-ip>:3000/dashboards` and access the WordPress dashboard named Wordpress Operator
Overview.

### ObjectStorage with Swift

Follow the instructions on installing OpenStack from the OpenStack
[documentation](https://docs.openstack.org/install-guide/). For testing purposes, you can install
[DevStack](https://docs.openstack.org/devstack/latest/).

After successful installations, you should be able to see `openrc` file at the location of
installation. The contents of the `openrc` file should look something similar to the following.

```
export OS_REGION_NAME=RegionOne
export OS_PROJECT_DOMAIN_ID=default
export OS_CACERT=
export OS_TENANT_NAME=demo
export OS_USER_DOMAIN_ID=default
export OS_USERNAME=demo
export OS_VOLUME_API_VERSION=3
export OS_AUTH_TYPE=<strong-password>
export OS_PROJECT_NAME=demo
export OS_PASSWORD=<strong-password>
export OS_IDENTITY_API_VERSION=3
export OS_AUTH_URL=http://10.100.115.2/identity
```

To use the openstack cli tools, source the file with the following command.

```
source openrc
```

To configure Swift storage for wordpress-k8s, copy and paste the following yaml content and adjust
the values accordingly.

```
auth-url: http://10.100.115.2/identity/v3
bucket: WordPress
copy-to-swift: 1
domain: Default
object-prefix: wp-content/uploads/
password: <strong-password>
region: RegionOne
remove-local-file: 0
serve-from-swift: 1
swift-url: swift_auth_url # obtain the value by running `swift auth`. The value should look
something like http://10.100.115.2:8080/v1/AUTH_1d449b4237d3499dabd95210c33ca150, exported under
OS_STORAGE_URL key.
tenant: demo
username: demo
```

### Building from source

To build and deploy wordpress-k8s charm from source follow the steps below.

#### Docker image build

Build the `wordpress.Dockerfile` image with the following command.

```
docker build -t wordpress -f wordpress.Dockerfile .
```

#### Microk8s upload docker artifacts

For microk8s to pick up the locally built image, you must export the image and import it within
microk8s.

```
docker save wordpress > wordpress.tar
microk8s ctr image import wordpress.tar
```

#### Build the charm

Build the charm locally using charmcraft. It should output a .charm file.

```
charmcraft pack
```

### Deploy WordPress

Deploy the locally built WordPress charm with the following command.

```
juju deploy ./wordpress-k8s_ubuntu-22.04-amd64_ubuntu-20.04-amd64.charm \
  --resource wordpress-image=wordpress \
  --resource apache-prometheus-exporter-image=bitnami/apache-exporter:0.11.0
```

You should now be able to see your local wordpress-k8s charm progress through the stages of the
deployoment through `juju status --watch 2s`.
