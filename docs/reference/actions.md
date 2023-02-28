# Actions

- _get-initial-password_: Retrieve auto-generated initial password for accessing WordPress admin
  account. The password is set once during deployment. If the wordpress-k8s charm is configured
  with `initial_settings` parameters containing `admin_password`, this action has no effect.

- _rotate-wordpress-secrets_: Invalidate user sessions by rotating the following secrets:
  auth_key, auth_salt, logged_in_key, logged_in_salt, nonce_key, nonce_salt, secure_auth_key,
  secure_auth_salt.
  Users will be forced to log in again. This might be usedful under security breach circumstances.
