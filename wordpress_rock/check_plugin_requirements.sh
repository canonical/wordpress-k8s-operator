#!/bin/bash
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

# Fail when a bundled plugin needs a newer WordPress than the image ships.
# WordPress refuses to activate such a plugin ("does not work with your
# version of WordPress").
#
# Usage: check_plugin_requirements.sh <wp_version> <plugins_dir>
#
# A plugin's requirement is the "Requires at least:" header of its top-level
# PHP files. That is what WordPress checks on activation; readme.txt is only
# used by wordpress.org and is ignored here.

set -euo pipefail

wp_version="$1"
plugins_dir="$2"
failed=0

for plugin in "$plugins_dir"/*/; do
    slug=$(basename "$plugin")
    required=$(
        grep -ih '^[[:space:]*]*Requires at least:' "$plugin"*.php 2>/dev/null \
            | tr -d '\r' \
            | sed 's/.*Requires at least:[[:space:]]*//I; s/[[:space:]]*$//' \
            | sort -V | tail -n 1 || true
    )
    [ -n "$required" ] || continue
    newest=$(printf '%s\n%s\n' "$required" "$wp_version" | sort -V | tail -n 1)
    if [ "$newest" != "$wp_version" ]; then
        echo "$slug requires WordPress $required, image has $wp_version" >&2
        failed=1
    fi
done

exit "$failed"
