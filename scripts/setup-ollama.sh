#!/usr/bin/env bash
# ============================================================
# setup-ollama.sh — Pull required models into Ollama container
# Usage: bash scripts/setup-ollama.sh
# ============================================================
set -euo pipefail

echo "=== Ollama Model Setup ==="

echo "[1/3] Pulling llama3.1 (reasoning model)..."
docker exec -it ollama ollama pull llama3.1

echo "[2/3] Pulling nomic-embed-text (embeddings fallback)..."
docker exec -it ollama ollama pull nomic-embed-text

echo "[3/3] Listing installed models..."
docker exec -it ollama ollama list

echo ""
echo "=== Ollama setup complete ==="
