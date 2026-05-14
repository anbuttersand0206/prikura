#!/bin/sh
set -e
htpasswd -bc /etc/nginx/.htpasswd "$BASIC_AUTH_USER" "$BASIC_AUTH_PASSWORD"
exec nginx -g "daemon off;"
