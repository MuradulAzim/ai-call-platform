#!/usr/bin/env bash
# ============================================================
# setup-firewall.sh — Configure UFW for AI Voice Platform
# Run once on VPS after initial setup
# Usage: bash scripts/setup-firewall.sh
# ============================================================
set -euo pipefail

echo "============================================"
echo " Firewall Configuration (UFW)"
echo "============================================"

if ! command -v ufw &> /dev/null; then
    echo "Installing UFW..."
    apt-get update -qq && apt-get install -y -qq ufw
fi

echo "[1/4] Setting default policies..."
ufw default deny incoming
ufw default allow outgoing

echo "[2/4] Allowing essential ports..."

# SSH
ufw allow 22/tcp comment "SSH"

# HTTP / HTTPS
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"

# LiveKit RTC (TCP)
ufw allow 7881/tcp comment "LiveKit RTC TCP"

# LiveKit WebRTC media (UDP)
ufw allow 50000:50200/udp comment "LiveKit WebRTC UDP"

# TURN server
ufw allow 3478/tcp comment "TURN STUN"
ufw allow 3478/udp comment "TURN STUN UDP"
ufw allow 5349/tcp comment "TURN TLS"
ufw allow 5349/udp comment "TURN TLS UDP"
ufw allow 49152:49252/udp comment "TURN relay UDP"

echo "[3/4] Enabling firewall..."
echo "y" | ufw enable

echo "[4/4] Status:"
ufw status verbose

echo ""
echo "============================================"
echo " Firewall configured successfully"
echo "============================================"
