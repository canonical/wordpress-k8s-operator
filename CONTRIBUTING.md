# Contributing

Build the OCI image:

```bash
docker build -t wordpress:test -f wordpress.Dockerfile .
```

Push the OCI image to microk8s:

```bash
sudo docker push localhost:32000/wordpress:test
```

Deploy the charm:

```bash
charmcraft pack
juju deploy ./wordpress-k8s_ubuntu-22.04-amd64.charm \
    --resource jenkins-image=localhost:32000/wordpress:test
```
