#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# run.sh — Start the AI pipeline (foreground, with log tee)
# ──────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
  echo "❌  .env not found. Run: cp .env.example .env  and fill in your credentials."
  exit 1
fi

LOG_DIR="/tmp/pipeline-logs"
mkdir -p "$LOG_DIR"

echo "🚀 Starting AI Pipeline…"
echo "   Logs: $LOG_DIR/pipeline.log"
echo "   Press Ctrl+C to stop."
echo ""

python -m pipeline.main 2>&1 | tee -a "$LOG_DIR/pipeline.log"
