# Initial credentials

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
    password: <password> # password should look something like: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
  status: completed
```

You can use the password to login to the admin account in `http://<wordpress-unit-ip>/wp-admin.php`.

Note that if `admin_password` value has been passed in the `initial_settings` configuration, the
password from the action is invalid.
