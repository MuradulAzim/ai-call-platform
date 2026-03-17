#!/bin/sh
set -e

# Expand environment variables in the Coturn config template
sed \
  -e "s|\${TURN_SECRET}|${TURN_SECRET}|g" \
  /etc/coturn/turnserver-template.conf > /tmp/turnserver.conf

exec turnserver -c /tmp/turnserver.conf
