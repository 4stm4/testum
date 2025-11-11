#!/bin/sh
set -e

echo "Setting up Nginx with loading page..."

# Copy loading page to nginx html directory
if [ -f /docker-entrypoint.d/loading.html ]; then
    cp /docker-entrypoint.d/loading.html /usr/share/nginx/html/index.html
    echo "Loading page installed as index.html"
else
    echo "Warning: loading.html not found"
fi

# Execute the original nginx entrypoint
exec /docker-entrypoint.sh "$@"
