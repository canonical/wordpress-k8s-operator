#!/usr/bin/env bash
set -x

if [[ -f "/var/www/html/wp-info.php.bk" ]]; then
	mv -v /var/www/html/wp-info.php.bk /var/www/html/wp-info.php
else
	cp -v /var/www/html/wp-info.php{,.bk}
fi

sed -i -e "s/%%%WORDPRESS_DB_HOST%%%/$WORDPRESS_DB_HOST/" /var/www/html/wp-info.php
sed -i -e "s/%%%WORDPRESS_DB_NAME%%%/$WORDPRESS_DB_NAME/" /var/www/html/wp-info.php
sed -i -e "s/%%%WORDPRESS_DB_USER%%%/$WORDPRESS_DB_USER/" /var/www/html/wp-info.php
sed -i -e "s/%%%WORDPRESS_DB_PASSWORD%%%/$WORDPRESS_DB_PASSWORD/" /var/www/html/wp-info.php

for key in AUTH_KEY SECURE_AUTH_KEY LOGGED_IN_KEY NONCE_KEY AUTH_SALT SECURE_AUTH_SALT LOGGED_IN_SALT NONCE_SALT; do
	sed -i -e "s/%%%${key}%%%/$(printenv ${key})/" /var/www/html/wp-info.php
done

# If we have passed in SWIFT_URL, then append swift proxy config.
[ -z "${SWIFT_URL-}" ] || a2enconf docker-php-swift-proxy

function wp_admin() {
	/usr/local/bin/wp \
		--path="/var/www/html" \
		--allow-root "$@" 2> >(grep -v "PHP Notice")
}

if [ ${WORDPRESS_INSTALLED:false} ]; then
	if ! wp_admin core is-installed; then
		wp_admin core \
			install \
			--url="${WORDPRESS_BLOG_HOSTNAME}" \
			--title="The ${WORDPRESS_BLOG_HOSTNAME} Blog" \
			--admin_user="${WORDPRESS_ADMIN_USER}" \
			--admin_password="$(</admin_password)" \
			--admin_email="${WORDPRESS_ADMIN_EMAIL}"
		wp_admin core is-installed
	else
		echo "WordPress already installed, updating admin password instead"
		wp_admin \
			user update "${WORDPRESS_ADMIN_USER}" --user_pass="$(</admin_password)"
		exec sleep infinity
	fi
fi

# Match against either php 7.2 (bionic) or 7.4 (focal).
sed -i 's/max_execution_time = 30/max_execution_time = 300/' /etc/php/7.[24]/apache2/php.ini
sed -i 's/upload_max_filesize = 2M/upload_max_filesize = 10M/' /etc/php/7.[24]/apache2/php.ini
