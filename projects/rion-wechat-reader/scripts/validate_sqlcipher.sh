#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_root="$(cd "$project_root/../.." && pwd)"
wheel="${RION_WECHAT_SQLCIPHER_WHEEL:-}"
zstandard_wheel="${RION_WECHAT_ZSTANDARD_WHEEL:-}"
runtime="$(mktemp -d)"
trap 'rm -r -- "$runtime"' EXIT

install_args=(--prefix "$runtime")
if [ -n "$wheel" ]; then
  install_args+=(--sqlcipher-wheel "$wheel")
else
  install_args+=(--with-sqlcipher)
fi
if [ -n "$zstandard_wheel" ]; then
  install_args+=(--zstandard-wheel "$zstandard_wheel")
fi

"$project_root/install.sh" "${install_args[@]}"
"$runtime/bin/rion-wechat-cli" self-test --require-sqlcipher >/dev/null
"$runtime/share/rion-wechat-cli/venv/bin/python" -m unittest discover \
  -s "$project_root/tests" \
  -v
(
  cd "$repo_root/projects/wechat-intelligence-hub"
  "$runtime/share/rion-wechat-cli/venv/bin/python" -m unittest discover \
    -s tests \
    -p 'test_rion_reader_integration.py' \
    -v
)
python3 "$project_root/scripts/capability_gap.py" --strict >/dev/null
python3 "$project_root/scripts/live_parity.py" --help >/dev/null

echo "SQLCipher encrypted Reader and WeChat Intelligence Hub checks passed."
