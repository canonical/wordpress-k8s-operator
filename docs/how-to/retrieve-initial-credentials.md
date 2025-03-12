# How to retrieve initial credentials

Run the following command to get the initial admin password that can be used to login at
`http://<wordpress-unit-ip>/wp-login.php`.

```
juju run wordpress-k8s/0 get-initial-password 
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

> **NOTE** If the `admin_password` value was passed in the `initial_settings` configuration, the
password from the action is invalid.
