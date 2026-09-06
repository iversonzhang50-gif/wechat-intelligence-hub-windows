#!/usr/bin/env bash
set -euo pipefail

codex_root="${CODEX_HOME:-$HOME/.codex}"
installed="$codex_root/share/wechat-intelligence-hub/projects/rion-wechat-reader/rion_wechat_reader.py"
repo_candidate="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)/projects/rion-wechat-reader/rion_wechat_reader.py"
bundled_cli="$codex_root/bin/rion-wechat-cli"

if [ -n "${RION_WECHAT_CLI_BIN:-}" ]; then
  exec "$RION_WECHAT_CLI_BIN" "$@"
fi

if [ -n "${RION_WECHAT_READER_BIN:-}" ]; then
  exec "$RION_WECHAT_READER_BIN" "$@"
fi

if command -v rion-wechat-cli >/dev/null 2>&1; then
  exec "$(command -v rion-wechat-cli)" "$@"
fi

if [ -x "$bundled_cli" ]; then
  exec "$bundled_cli" "$@"
fi

if [ -f "$installed" ]; then
  exec python3 "$installed" "$@"
fi

if [ -f "$repo_candidate" ]; then
  exec python3 "$repo_candidate" "$@"
fi

echo "rion-wechat-cli engine not found. Reinstall the wechat-cli Skill." >&2
exit 127
