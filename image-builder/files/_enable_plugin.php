<?php

# PHP cli helper which enables a plugin. Plugin name is in
# format returned by _list_inactive_plugins.php helper
#
# Example use:
# php ./_enable_plugin.php akismet/akismet.php openid/openid.php

@include "wp-config.php";
@include_once "wp-admin/includes/plugin.php";
$result = activate_plugins(array_slice($argv, 1));
if ( is_wp_error( $result ) ) {
    throw new Exception($result);
}
