#!/usr/bin/env bash
set -euo pipefail
cd ~/ai-call-platform

PG_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
REDIS_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
MINIO_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
JWT_SECRET=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 48)
LK_KEY="API$(openssl rand -hex 6)"
LK_SECRET=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 48)
TURN_SEC=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)

sed -i "s|POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD|POSTGRES_PASSWORD=${PG_PASS}|" .env
sed -i "s|REDIS_PASSWORD=CHANGE_ME_REDIS_SECRET|REDIS_PASSWORD=${REDIS_PASS}|" .env
sed -i "s|MINIO_SECRET_KEY=CHANGE_ME_MINIO_SECRET|MINIO_SECRET_KEY=${MINIO_PASS}|" .env
sed -i "s|OSS_JWT_SECRET=CHANGE_ME_JWT_SECRET_32_CHARS_MIN|OSS_JWT_SECRET=${JWT_SECRET}|" .env
sed -i "s|LIVEKIT_API_KEY=CHANGE_ME_LIVEKIT_API_KEY|LIVEKIT_API_KEY=${LK_KEY}|" .env
sed -i "s|LIVEKIT_API_SECRET=CHANGE_ME_LIVEKIT_SECRET_MIN_32_CHARS|LIVEKIT_API_SECRET=${LK_SECRET}|" .env
sed -i "s|TURN_SECRET=CHANGE_ME_TURN_SHARED_SECRET|TURN_SECRET=${TURN_SEC}|" .env

echo "Secrets generated and written to .env"
echo "  POSTGRES_PASSWORD=${PG_PASS}"
echo "  REDIS_PASSWORD=${REDIS_PASS}"
echo "  MINIO_SECRET_KEY=${MINIO_PASS}"
echo "  JWT_SECRET=${JWT_SECRET:0:8}..."
echo "  LIVEKIT_API_KEY=${LK_KEY}"
echo "  LIVEKIT_API_SECRET=${LK_SECRET:0:8}..."
echo "  TURN_SECRET=${TURN_SEC:0:8}..."

# Self-delete after use
rm -f ~/ai-call-platform/gen-secrets.sh
