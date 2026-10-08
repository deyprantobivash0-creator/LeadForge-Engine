#!/bin/sh
set -eu
if [ "${LEADFORGE_RENDER:-false}" = false ]; then
    exec nginx "$@"
fi
fail() { echo "Render Nginx configuration rejected" >&2; exit 1; }
[ "${LEADFORGE_RENDER:-}" = true ] || fail
port="${PORT:-10000}"
printf '%s' "$port" | grep -Eq '^[0-9]{1,5}$' || fail
[ "$port" -ge 1024 ] && [ "$port" -le 65535 ] || fail
upstream="${LEADFORGE_RENDER_BACKEND_ORIGIN:-}"
printf '%s' "$upstream" | grep -Eq '^https://[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.onrender\.com$' || fail
host="${RENDER_EXTERNAL_HOSTNAME:-}"
printf '%s' "$host" | grep -Eq '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.onrender\.com$' || fail
backend_host="${upstream#https://}"
# Use the platform-provided DNS servers; no public resolver or Docker DNS assumption.
resolvers=$(awk '/^nameserver / { if ($2 ~ /^[0-9.]+$/) printf "%s ", $2; else if ($2 ~ /^[0-9a-fA-F:]+$/) printf "[%s] ", $2 }' /etc/resolv.conf)
[ -n "$resolvers" ] || fail
sed -e "s|@@PORT@@|$port|g" -e "s|@@UPSTREAM@@|$upstream|g" \
    -e "s|@@BACKEND_HOST@@|$backend_host|g" -e "s|@@FRONTEND_HOST@@|$host|g" \
    -e "s|@@RESOLVERS@@|$resolvers|g" /etc/nginx/render.conf.template > /tmp/render-nginx.conf
nginx -t -c /tmp/render-nginx.conf
exec nginx -c /tmp/render-nginx.conf "$@"
