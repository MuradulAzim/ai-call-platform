#!/bin/sh
set -e

API_URL="${BACKEND_API_ENDPOINT:-https://api.iamazim.com}"

echo "==> Patching frontend bundle: localhost:8000 / 127.0.0.1:8000 → ${API_URL}"

# Replace hardcoded localhost references in compiled JS and source maps
find /app/.next -type f \( -name '*.js' -o -name '*.js.map' \) -exec \
  sed -i "s|http://localhost:8000|${API_URL}|g; s|http://127\.0\.0\.1:8000|${API_URL}|g" {} +

echo "==> Patch complete"

# Start the Next.js server (matches original CMD)
exec node server.js
