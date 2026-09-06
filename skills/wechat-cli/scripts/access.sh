#!/usr/bin/env bash
set -euo pipefail
codex_root="${CODEX_HOME:-$HOME/.codex}"
if command -v rion-wechat-access >/dev/null 2>&1; then
  exec "$(command -v rion-wechat-access)" "$@"
fi
if [ -x "$codex_root/bin/rion-wechat-access" ]; then
  exec "$codex_root/bin/rion-wechat-access" "$@"
fi
installed="$codex_root/share/wechat-intelligence-hub/projects/rion-wechat-reader/rion_wechat_access.py"
repo_candidate="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)/projects/rion-wechat-reader/rion_wechat_access.py"
if [ -f "$installed" ]; then
  exec python3 "$installed" "$@"
fi
if [ -f "$repo_candidate" ]; then
  exec python3 "$repo_candidate" "$@"
fi
echo "Optional access helper not installed; update the wechat-cli Skill." >&2
exit 127
