# How to configure hostname

### Prerequisites

Deploy and relate [nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator) charm.

```
juju deploy nginx-ingress-integrator
juju relate wordpress-k8s nginx-ingress-integrator
```

### Configure hostname

To configure a different hostname for WordPress, you can configure the ingress hostname through the
wordpress-k8s configuration.

```
juju config wordpress-k8s blog_hostname=<desired-hostname>
```

The output of `juju status` should look similar to the following:

```
Model  Controller          Cloud/Region        Version  SLA          Timestamp
wordpress-k8s-tutorial    microk8s-localhost  microk8s/localhost  2.9.38   unsupported

App                       Version              Status  Scale  Charm     Channel  Rev  Address         Exposed  Message
mysql-k8s                                      active      1  mysql-k8s stable    35  <mysql-ip>  no       ready
nginx-ingress-integrator                       active      1  nginx-ingress-integrator  stable    54  <nginx-ingress-integrator-ip>   no       Service IP(s): <nginx-ingress-integrator-service-ip>
wordpress-k8s                                  active      1  wordpress-k8s 16  <wordpress-k8s-ip>  no

Unit                         Workload  Agent  Address       Ports     Message
mysql-k8s/0*                active    idle   <mysql-k8s-ip>
nginx-ingress-integrator/0*  active    idle  <nginx-ingress-integrator-ip>            Service IP(s
): <nginx-ingress-integrator-service-ip>
wordpress-k8s/0*             active    idle   <wordpress-k8s-ip>
```

Note the Service IP(s) next to nginx-ingress-integrator charm’s Status output.

Test the ingress by sending a GET request to the service with `Host` headers.

```
curl -H "Host: <desired-hostname>" http://<nginx-ingress-integrator-service-ip>
```
