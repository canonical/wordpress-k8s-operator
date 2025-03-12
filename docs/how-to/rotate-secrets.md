# How to rotate secrets

To securely update all the WordPress secrets, run the following action.

```
juju run wordpress-k8s/0 rotate-wordpress-secrets
```

This action will force users to be logged out. All sessions and cookies will be invalidated.