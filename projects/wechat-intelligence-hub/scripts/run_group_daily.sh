#!/usr/bin/env bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${WECHAT_HUB_HOME:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TODAY="$(date +%F)"
OUT_DIR="$PROJECT_DIR/output/group-daily-$TODAY"
LOG_FILE="$OUT_DIR/run.log"

mkdir -p "$OUT_DIR"
cd "$PROJECT_DIR"

"$PYTHON_BIN" wechat_intelligence_hub.py compat-check \
  --force \
  --out "$OUT_DIR/wechat_compatibility.json" >"$LOG_FILE" 2>&1

GROUP_ARGS=(
  group-daily
  --hours "${WECHAT_HOURS:-24}"
  --group-limit "${WECHAT_GROUP_LIMIT:-60}"
  --per-group-limit "${WECHAT_PER_GROUP_LIMIT:-500}"
  --out "$OUT_DIR"
)
if [ "${WECHAT_DELIVERY:-md}" = "html" ] || [ "${WECHAT_DELIVERY:-md}" = "all" ]; then
  GROUP_ARGS+=(--html)
fi
if [ -f contacts/排除名单.txt ]; then
  GROUP_ARGS+=(--exclude-list contacts/排除名单.txt)
fi
"$PYTHON_BIN" wechat_intelligence_hub.py "${GROUP_ARGS[@]}" >>"$LOG_FILE" 2>&1

printf '%s\n' "$OUT_DIR/group_daily_digest.md"
printf '%s\n' "$OUT_DIR/group_daily_editorial_packet.json"
