#!/bin/bash
set -eu

sed -i -e "s/%%%WORDPRESS_DB_HOST%%%/$WORDPRESS_DB_HOST/" /var/www/html/wp-info.php
sed -i -e "s/%%%WORDPRESS_DB_NAME%%%/$WORDPRESS_DB_NAME/" /var/www/html/wp-info.php
sed -i -e "s/%%%WORDPRESS_DB_USER%%%/$WORDPRESS_DB_USER/" /var/www/html/wp-info.php
sed -i -e "s/%%%WORDPRESS_DB_PASSWORD%%%/$WORDPRESS_DB_PASSWORD/" /var/www/html/wp-info.php

for key in AUTH_KEY SECURE_AUTH_KEY LOGGED_IN_KEY NONCE_KEY AUTH_SALT SECURE_AUTH_SALT LOGGED_IN_SALT NONCE_SALT;
do
    sed -i -e "s/%%%${key}%%%/$(printenv ${key})/" /var/www/html/wp-info.php
done

# If we have passed in SWIFT_URL, then append swift proxy config.
[ -z "${SWIFT_URL-}" ] || a2enconf docker-php-swift-proxy

# TODO: this will eventually be called directly by the charm.
nohup bash -c "(cd /var/www/html/wp-content/ && /fetcher.py && chown -R www-data:www-data /var/www/html/wp-content/) &"

nohup bash -c "/srv/wordpress-helpers/plugin_handler.py &"

# Match against either php 7.2 (bionic) or 7.4 (focal).
sed -i 's/max_execution_time = 30/max_execution_time = 300/' /etc/php/7.[24]/apache2/php.ini
sed -i 's/upload_max_filesize = 2M/upload_max_filesize = 10M/' /etc/php/7.[24]/apache2/php.ini

exec "$@"
