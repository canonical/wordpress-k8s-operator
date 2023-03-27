# How to enable WAF

This step will walk you through making your WordPress application secure using Modsecurity 3.0
Web Application Firewall.

### Prerequisites

Deploy and relate [nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator) charm.

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
Namespace:        wordpress-tutorial
Address:
Ingress Class:    <none>
Default backend:  <default>
Rules:
  Host           Path  Backends
  ----           ----  --------
  wordpress-k8s
                 /   wordpress-k8s-service:80
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
