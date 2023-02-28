# Actions

- _get-initial-password_: Retrieve auto-generated initial password for accessing WordPress admin
  account. The password is set once during deployment. If the wordpress-k8s charm is configured
  with `initial_settings` paramters containing `admin_password`, this action has no effect.

- _rotate-wordpress-secrets_: Rotate all WordPress secrets, used for WordPress to encrypt
  information. The secret fields are used to enhance security by encrypting WordPress data. The
  following secrets are rotated: auth_key, secure_auth_key, logged_in_key, nonce_key, auth_salt,
  secure_auth_salt, logged_in_salt, nonce_salt
