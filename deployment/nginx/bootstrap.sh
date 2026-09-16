#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
#
# nginx start-up for the AWS staging stack (GRM-103). Mounted with the rest of deployment/nginx at
# /etc/nginx/site, so it follows `git pull` like the site config does.
#
# Why a file and not an inline compose `command:`: the same logic has to run in two places — the
# real container, and the deploy's pre-flight validation — and the deploy sends its whole remote
# command inside single quotes over SSH, where an inline script full of quotes and `$` breaks
# silently. A script needs neither.
#
#   sh /etc/nginx/site/bootstrap.sh          start nginx serving $NGINX_SITE_CONF
#   sh /etc/nginx/site/bootstrap.sh --test   validate that exact config and exit (nginx -t)
set -e

# ⚠ The site file is `include`d from the MOUNTED DIRECTORY, never bind-mounted into conf.d as a
# single file: a single-file mount stays pinned to the inode git replaced, so reloads and even
# `nginx -t` would read the pre-pull copy (measured on staging, 2026-09-14).
site="/etc/nginx/site/${NGINX_SITE_CONF:?NGINX_SITE_CONF must name a file under deployment/nginx}"
[ -f "$site" ] || { echo "nginx bootstrap: $site not found" >&2; exit 1; }

# The image's default server would otherwise claim port 80 alongside ours.
rm -f /etc/nginx/conf.d/default.conf
printf 'include %s;\n' "$site" > /etc/nginx/conf.d/site.conf

if [ "${1:-}" = "--test" ]; then
    exec nginx -t
fi
exec /docker-entrypoint.sh nginx -g 'daemon off;'
