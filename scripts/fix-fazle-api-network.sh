#!/bin/bash
# Permanently fix any orphaned fazle-api-blue container
if docker ps -a --format '{{.Names}}' | grep -q fazle-api-blue; then
  docker network connect app-network fazle-api-blue --alias fazle-api 2>/dev/null || true
  docker network connect ai-network fazle-api-blue 2>/dev/null || true
  docker network connect db-network fazle-api-blue 2>/dev/null || true
  echo 'fazle-api-blue networking fixed + aliased'
fi
