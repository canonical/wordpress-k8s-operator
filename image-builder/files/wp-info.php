<?php
#
#    "             "
#  mmm   m   m   mmm   m   m
#    #   #   #     #   #   #
#    #   #   #     #   #   #
#    #   "mm"#     #   "mm"#
#    #             #
#  ""            ""
# This file is managed by Juju. Do not make local changes.
#

// We have to cheat a little because frontend service can terminate SSL
// If it does it should set X-Edge-Https header to "on" to tell us original
// request came on https

if (!empty($_SERVER['HTTP_X_EDGE_HTTPS']) && 'off' != $_SERVER['HTTP_X_EDGE_HTTPS']) {
        $_SERVER['HTTPS'] = 'on';
}

if (!empty($_SERVER['HTTPS']) && 'off' != $_SERVER['HTTPS']) {
    define('WP_PLUGIN_URL', 'https://' . $_SERVER['HTTP_HOST'] . '/wp-content/plugins');
    define('WP_CONTENT_URL', 'https://' . $_SERVER['HTTP_HOST'] . '/wp-content');
    define('WP_SITEURL', 'https://' . $_SERVER['HTTP_HOST']);
    define('WP_URL', 'https://' . $_SERVER['HTTP_HOST']);
    define('WP_HOME', 'https://' . $_SERVER['HTTP_HOST']);
}
else {
    define('WP_PLUGIN_URL', 'http://' . $_SERVER['HTTP_HOST'] . '/wp-content/plugins');
    define('WP_CONTENT_URL', 'http://' . $_SERVER['HTTP_HOST'] . '/wp-content');
    define('WP_SITEURL', 'http://' . $_SERVER['HTTP_HOST']);
    define('WP_URL', 'http://' . $_SERVER['HTTP_HOST']);
    define('WP_HOME', 'http://' . $_SERVER['HTTP_HOST']);
}

define('DB_NAME', '%%%WORDPRESS_DB_NAME%%%');
define('DB_USER', '%%%WORDPRESS_DB_USER%%%');
define('DB_HOST', '%%%WORDPRESS_DB_HOST%%%');

define('DB_PASSWORD', '%%%WORDPRESS_DB_PASSWORD%%%');

define('WP_CACHE', true);

define('AUTH_KEY', '%%%AUTH_KEY%%%');
define('SECURE_AUTH_KEY', '%%%SECURE_AUTH_KEY%%%');
define('LOGGED_IN_KEY', '%%%LOGGED_IN_KEY%%%');
define('NONCE_KEY', '%%%NONCE_KEY%%%');
define('AUTH_SALT', '%%%AUTH_SALT%%%');
define('SECURE_AUTH_SALT', '%%%SECURE_AUTH_SALT%%%');
define('LOGGED_IN_SALT', '%%%LOGGED_IN_SALT%%%');
define('NONCE_SALT', '%%%NONCE_SALT%%%');

$table_prefix  = 'wp_';
