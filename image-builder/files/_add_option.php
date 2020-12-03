<?php

# PHP cli helper which adds new option to wp_settings table
#
# Example use:
# php ./_add_option.php akismet_strictness 0

@include "wp-config.php";
@include_once "wp-includes/option.php";
@include_once "wp-includes/functions.php";
add_option($argv[1], maybe_unserialize($argv[2]));
