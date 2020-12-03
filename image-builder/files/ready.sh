#!/bin/bash

READY=/srv/wordpress-helpers/.ready

# This script is designed to be called by the Kubernetes
# readinessProbe. If the WP plugins haven't been enabled
# which we know due to the $READY file not existing then
# return a failure, replace the shell with whatever curl
# returns for checking that the website is alive.
if [ -f "$READY" ]; then
    exec /usr/bin/curl --silent http://localhost
fi

exit 1
