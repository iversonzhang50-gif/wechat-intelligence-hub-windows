#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DEMO_OUT="${WECHAT_DEMO_OUT:-${TMPDIR:-/tmp}/wechat-intelligence-hub-demo}"

mkdir -p "$DEMO_OUT"

"$PYTHON_BIN" "$PROJECT_DIR/wechat_intelligence_hub.py" scan \
  "$PROJECT_DIR/samples/sample_chat.txt" \
  --out "$DEMO_OUT/file-scan"

"$PYTHON_BIN" "$PROJECT_DIR/wechat_intelligence_hub.py" vault-status \
  --vault-cli "$PROJECT_DIR/samples/fake_vault_cli.py"

"$PYTHON_BIN" "$PROJECT_DIR/wechat_intelligence_hub.py" vault-scan \
  --vault-cli "$PROJECT_DIR/samples/fake_vault_cli.py" \
  --out "$DEMO_OUT/fake-vault" \
  --no-db

printf '\nDemo complete: %s\n' "$DEMO_OUT"
