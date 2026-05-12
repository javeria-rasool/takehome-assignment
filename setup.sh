#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# setup.sh — Install all pipeline dependencies
# Run once before first use: bash setup.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

echo "📦 Installing Python dependencies…"
pip install -r requirements.txt

echo "🎭 Installing Playwright + Chromium browser…"
playwright install chromium

echo "✅ Setup complete. Next steps:"
echo "   1. cp .env.example .env"
echo "   2. Edit .env with your real credentials"
echo "   3. bash run.sh"
