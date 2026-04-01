## Build the charm

Build the charm in this git repository using:

```shell
charmcraft pack
```

### Deploy the charm

```bash
# Create a model
juju add-model charm-dev
# Enable DEBUG logging
juju model-config logging-config="<root>=INFO;unit=DEBUG"
# Deploy the charm
juju deploy ./wordpress-k8s*.charm
```