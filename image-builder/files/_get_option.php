<?php

# PHP cli helper which returns option value if present
#
# Example use:
# php ./_get_option.php akismet_strictness

@include "wp-config.php";
@include_once "wp-includes/option.php";
@include_once "/usr/share/php/Symfony/Component/Yaml/autoload.php";

use Symfony\Component\Yaml\Yaml;

$value = get_option($argv[1]);
print Yaml::dump($value);
