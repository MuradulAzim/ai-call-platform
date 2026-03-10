#!/usr/bin/env bash
set -euo pipefail
cd ~/ai-call-platform

# ── Generate all 11 secrets ────────────────────────────────
PG_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
REDIS_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
MINIO_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
JWT_SECRET=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 48)
LK_KEY="API$(openssl rand -hex 6)"
LK_SECRET=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 48)
TURN_SEC=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
FAZLE_API_KEY=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
FAZLE_JWT_SECRET=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 48)
NEXTAUTH_SECRET=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 48)
GRAFANA_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)

# ── Write secrets to .env ──────────────────────────────────
sed -i "s|POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD|POSTGRES_PASSWORD=${PG_PASS}|" .env
sed -i "s|REDIS_PASSWORD=CHANGE_ME_REDIS_SECRET|REDIS_PASSWORD=${REDIS_PASS}|" .env
sed -i "s|MINIO_SECRET_KEY=CHANGE_ME_MINIO_SECRET|MINIO_SECRET_KEY=${MINIO_PASS}|" .env
sed -i "s|OSS_JWT_SECRET=CHANGE_ME_JWT_SECRET_32_CHARS_MIN|OSS_JWT_SECRET=${JWT_SECRET}|" .env
sed -i "s|LIVEKIT_API_KEY=CHANGE_ME_LIVEKIT_API_KEY|LIVEKIT_API_KEY=${LK_KEY}|" .env
sed -i "s|LIVEKIT_API_SECRET=CHANGE_ME_LIVEKIT_SECRET_MIN_32_CHARS|LIVEKIT_API_SECRET=${LK_SECRET}|" .env
sed -i "s|TURN_SECRET=CHANGE_ME_TURN_SHARED_SECRET|TURN_SECRET=${TURN_SEC}|" .env
sed -i "s|^FAZLE_API_KEY=.*|FAZLE_API_KEY=${FAZLE_API_KEY}|" .env
sed -i "s|^FAZLE_JWT_SECRET=.*|FAZLE_JWT_SECRET=${FAZLE_JWT_SECRET}|" .env
sed -i "s|^NEXTAUTH_SECRET=.*|NEXTAUTH_SECRET=${NEXTAUTH_SECRET}|" .env
sed -i "s|^GRAFANA_PASSWORD=.*|GRAFANA_PASSWORD=${GRAFANA_PASSWORD}|" .env

echo "Secrets generated and written to .env"
echo "  [SECRET GENERATED] PostgreSQL password set (value hidden)"
echo "  [SECRET GENERATED] Redis password set (value hidden)"
echo "  [SECRET GENERATED] MinIO secret key set (value hidden)"
echo "  [SECRET GENERATED] JWT secret set (value hidden)"
echo "  [SECRET GENERATED] LiveKit API key set (value hidden)"
echo "  [SECRET GENERATED] LiveKit API secret set (value hidden)"
echo "  [SECRET GENERATED] TURN secret set (value hidden)"
echo "  [SECRET GENERATED] Fazle API key set (value hidden)"
echo "  [SECRET GENERATED] Fazle JWT secret set (value hidden)"
echo "  [SECRET GENERATED] NextAuth secret set (value hidden)"
echo "  [SECRET GENERATED] Grafana password set (value hidden)"

# Self-delete after use
rm -f ~/ai-call-platform/gen-secrets.sh
