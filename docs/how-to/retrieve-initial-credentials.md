(how_to_retrieve_initial_credentials)=

# How to retrieve initial credentials

Run the following command to get the initial admin password that can be used to log in at
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
    password: <password>
  status: completed
```

The password should look something like: `XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`.

You can use the password to log in to the admin account at `http://<wordpress-unit-ip>/wp-admin.php`.

```{note}
If the `admin_password` value was passed in the `initial_settings` configuration, the
password from this action is invalid.
```
