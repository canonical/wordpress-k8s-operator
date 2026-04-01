## Build the rock

Use [Rockcraft](https://documentation.ubuntu.com/rockcraft/stable/) to create an
OCI image for the WordPress app, and then upload the image to a MicroK8s registry,
which stores OCI archives so they can be downloaded and deployed.

Enable the MicroK8s registry:

```bash
microk8s enable registry
```

The following commands pack the OCI image and push it into
the MicroK8s registry:

```bash
cd <project_dir>
rockcraft pack
skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:<rock-name>.rock docker://localhost:32000/<app-name>:latest
```