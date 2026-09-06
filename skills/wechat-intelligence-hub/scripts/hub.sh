#!/usr/bin/env bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${WECHAT_HUB_HOME:-}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ -z "$PROJECT_DIR" ]; then
  for candidate in \
    "$PWD" \
    "$SCRIPT_DIR/../../../../projects/wechat-intelligence-hub" \
    "$SCRIPT_DIR/../../../share/wechat-intelligence-hub/projects/wechat-intelligence-hub" \
    "$HOME/wechat-intelligence-hub" \
    "$HOME/Documents/wechat-intelligence-hub"
  do
    if [ -f "$candidate/wechat_intelligence_hub.py" ]; then
      PROJECT_DIR="$candidate"
      break
    fi
  done
fi

if [ -z "$PROJECT_DIR" ] && [ -d "$HOME/Documents" ]; then
  project_file="$(find "$HOME/Documents" -maxdepth 5 -type f -name wechat_intelligence_hub.py -path '*wechat-intelligence-hub*' -print -quit 2>/dev/null || true)"
  if [ -n "$project_file" ]; then
    PROJECT_DIR="$(dirname "$project_file")"
  fi
fi

if [ -z "$PROJECT_DIR" ] || [ ! -f "$PROJECT_DIR/wechat_intelligence_hub.py" ]; then
  echo "找不到 WeChat Intelligence Hub 项目。请设置 WECHAT_HUB_HOME=/path/to/wechat-intelligence-hub" >&2
  exit 2
fi

cd "$PROJECT_DIR"
exec "$PYTHON_BIN" wechat_intelligence_hub.py "$@"
