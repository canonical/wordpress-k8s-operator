<?php
// Copyright 2026 Canonical Ltd.
// See LICENSE file for licensing details.

/**
 * Check bundled plugins against the WordPress core requirements parser.
 *
 * Usage: check_plugin_requirements.php <wordpress_dir> <plugins_dir>
 */

declare(strict_types=1);

if ($argc !== 3) {
    fwrite(STDERR, "Usage: check_plugin_requirements.php <wordpress_dir> <plugins_dir>\n");
    exit(2);
}

$wordpress_dir = realpath($argv[1]);
$plugins_dir = realpath($argv[2]);
if ($wordpress_dir === false || $plugins_dir === false) {
    fwrite(STDERR, "WordPress or plugin directory does not exist.\n");
    exit(2);
}

define('ABSPATH', rtrim($wordpress_dir, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR);
define('WPINC', 'wp-includes');
define('WP_PLUGIN_DIR', $plugins_dir);
define('WPMU_PLUGIN_DIR', $wordpress_dir . '/wp-content/mu-plugins');
$GLOBALS['wp_plugin_paths'] = array();
if (!defined('KB_IN_BYTES')) {
    define('KB_IN_BYTES', 1024);
}

require_once ABSPATH . WPINC . '/plugin.php';
require_once ABSPATH . WPINC . '/functions.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';

$wp_version = wp_get_wp_version();
$plugin_files = array_merge(
    glob($plugins_dir . '/*.php') ?: [],
    glob($plugins_dir . '/*/*.php') ?: []
);
sort($plugin_files);

$failed = false;
foreach ($plugin_files as $plugin_file) {
    $plugin_data = get_plugin_data($plugin_file, false, false);
    if (empty($plugin_data['Name'])) {
        continue;
    }

    $required = $plugin_data['RequiresWP'];
    if ($required !== '' && !is_wp_version_compatible($required)) {
        $relative_file = ltrim(substr($plugin_file, strlen($plugins_dir)), DIRECTORY_SEPARATOR);
        fwrite(
            STDERR,
            sprintf(
                "%s requires WordPress %s, image has %s\n",
                $relative_file,
                $required,
                $wp_version
            )
        );
        $failed = true;
    }
}

exit($failed ? 1 : 0);
