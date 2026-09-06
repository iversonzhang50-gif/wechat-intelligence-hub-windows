#!/usr/bin/env bash
set -euo pipefail

bin_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
prefix="$(cd "$bin_dir/.." && pwd)"
runtime="$prefix/share/rion-wechat-cli"
engine="$runtime/rion_wechat_reader.py"
if [ "$(basename "$0")" = "rion-wechat-access" ]; then
  engine="$runtime/rion_wechat_access.py"
fi
python_bin="$runtime/venv/bin/python"

if [ ! -f "$engine" ]; then
  echo "rion-wechat-cli engine not found: $engine" >&2
  exit 127
fi

if [ ! -x "$python_bin" ]; then
  python_bin="$(command -v python3 || true)"
fi

if [ -z "$python_bin" ]; then
  echo "python3 not found" >&2
  exit 127
fi

exec "$python_bin" "$engine" "$@"
