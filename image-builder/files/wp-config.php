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

/* That's all, stop editing! Happy blogging. */

/** Enable container debug level logging. **/
if ( getenv("WORDPRESS_DEBUG") ) {
        define( 'WP_DEBUG', true );
        define( 'WP_DEBUG_DISPLAY', false );
        define( 'WP_DEBUG_LOG', '/dev/stderr' );
}

/** Fixes for mixed content when WordPress is behind nginx TLS reverse proxy.
 * https://ahenriksson.com/2020/01/27/how-to-set-up-wordpress-behind-a-reverse-proxy-when-using-nginx/
 * Check if we have a WORDPRESS_TLS_DISABLED environment variable, and if so
 * don't force logins to the admin site to be via TLS (this can be done to
 * make local testing one step easier).
 * */
if ( getenv("WORDPRESS_TLS_DISABLED") ){
    define('FORCE_SSL_ADMIN', false);
} else {
    define('FORCE_SSL_ADMIN', true);
}
if ($_SERVER['HTTP_X_FORWARDED_PROTO'] == 'https')
 $_SERVER['HTTPS']='on';

/** Absolute path to the WordPress directory. */
if ( !defined('ABSPATH') )
        define('ABSPATH', dirname(__FILE__) . '/');

/** Pull in the config information */
require_once(ABSPATH . 'wp-info.php');

/** Sets up WordPress vars and included files. */
require_once(ABSPATH . 'wp-settings.php');

/** Prevent wordpress from attempting to update and make external requests.
 *
 * Our firewalls do not allow WordPress to communicate externally to wordpress.org
 * for auto-updates, this causes our kubernetes pods to timeout during initial configuration,
 * preventing the site from ever becoming available.
 * */
define( 'AUTOMATIC_UPDATER_DISABLED', true );
define( 'WP_AUTO_UPDATE_CORE', false );

$http_host = $_SERVER['HTTP_HOST'];
define('WP_HOME',"https://$http_host");
define('WP_SITEURL',"https://$http_host");
