#!/usr/bin/env bash
# ============================================================
# setup-ssl.sh — Issue SSL certificates for all subdomains
# Run once on VPS after DNS records are configured
# Usage: bash scripts/setup-ssl.sh
# ============================================================
set -euo pipefail

EMAIL="${1:-admin@iamazim.com}"

echo "============================================"
echo " SSL Certificate Setup"
echo "============================================"
echo ""

if ! command -v certbot &> /dev/null; then
    echo "Installing Certbot..."
    apt-get update -qq
    apt-get install -y -qq certbot python3-certbot-nginx
fi

DOMAINS=(
    "iamazim.com"
    "api.iamazim.com"
    "livekit.iamazim.com"
    "turn.iamazim.com"
    "voice.iamazim.com"
    "fazle.iamazim.com"
)

# Build -d flags for a single multi-domain certificate
DOMAIN_FLAGS=""
for domain in "${DOMAINS[@]}"; do
    DOMAIN_FLAGS="$DOMAIN_FLAGS -d $domain"
done

echo ""
echo "── Requesting certificate for all domains ──"
echo "  Domains: ${DOMAINS[*]}"
echo ""

certbot certonly \
    --nginx \
    $DOMAIN_FLAGS \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive \
    --expand \
    --cert-name iamazim.com \
    || echo "  ⚠ Certificate request failed — check DNS A records point to this server"

echo ""
echo "── Setting up auto-renewal cron ──"
if ! crontab -l 2>/dev/null | grep -q "certbot renew"; then
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --deploy-hook 'systemctl reload nginx'") | crontab -
    echo "  ✓ Added daily renewal cron"
else
    echo "  Already configured"
fi

echo ""
echo "============================================"
echo " SSL setup complete"
echo "============================================"
echo ""
echo "Installed certificates:"
certbot certificates 2>/dev/null | grep -E "Domains:|Expiry" || true
