#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
validator="${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py"

if [ -f "$validator" ]; then
  for skill_dir in "$repo_root"/skills/*; do
    python3 "$validator" "$skill_dir"
  done
else
  echo "Skill validator not found; skipping metadata validation."
fi

(
  cd "$repo_root/projects/wechat-intelligence-hub"
  python3 wechat_intelligence_hub.py --help >/dev/null
  python3 wechat_deal_radar.py --help >/dev/null
  python3 -m unittest discover -s tests -v
)

hub_release_test="$(mktemp -d)"
trap 'rm -rf -- "$hub_release_test"' EXIT
python3 "$repo_root/projects/wechat-intelligence-hub/scripts/build_release.py" \
  --out "$hub_release_test/wechat-intelligence-hub"
test -f "$hub_release_test/wechat-intelligence-hub/release-manifest.json"
(
  cd "$hub_release_test/wechat-intelligence-hub"
  python3 -m unittest discover -s tests -v
)
rm -rf -- "$hub_release_test"
trap - EXIT

(
  cd "$repo_root/projects/rion-wechat-reader"
  python3 -m unittest discover -s tests -v
  python3 scripts/capability_gap.py --strict
)

reader_install_test="$(mktemp -d)"
trap 'rm -rf "$reader_install_test"' EXIT
"$repo_root/projects/rion-wechat-reader/install.sh" --prefix "$reader_install_test"
"$reader_install_test/bin/rion-wechat-cli" version >/dev/null
"$reader_install_test/bin/rion-wechat-cli" self-test >/dev/null
HOME="$reader_install_test/home" "$reader_install_test/bin/rion-wechat-cli" doctor >/dev/null
"$reader_install_test/bin/rion-wechat-reader" version >/dev/null
"$reader_install_test/bin/rion-wechat-access" --help >/dev/null
"$reader_install_test/bin/rion-wechat-access" onboard --help >/dev/null
test -f "$reader_install_test/share/rion-wechat-cli/rion_wechat_reader.py"
rm -rf "$reader_install_test"
trap - EXIT

python3 -m py_compile "$repo_root/projects/rion-wechat-reader/rion_wechat_reader.py"
python3 -m py_compile "$repo_root/projects/rion-wechat-reader/rion_wechat_access.py"

python3 -m py_compile "$repo_root/projects/rion-wechat-reader/scripts/capability_gap.py"
python3 -m py_compile "$repo_root/projects/rion-wechat-reader/scripts/live_parity.py"

bash -n \
  "$repo_root/projects/rion-wechat-reader/install.sh" \
  "$repo_root/projects/rion-wechat-reader/launcher.sh" \
  "$repo_root/projects/rion-wechat-reader/scripts/validate_sqlcipher.sh" \
  "$repo_root/skills/wechat-cli/scripts/reader.sh" \
  "$repo_root/skills/wechat-cli/scripts/access.sh"

if rg -n 'command -v wechat-cli' "$repo_root/skills/wechat-cli/scripts/reader.sh"; then
  echo "The public wrapper must not silently discover an old wechat-cli installation." >&2
  exit 1
fi

if rg -n \
  'rion-wechat-intelligence|WeChat Intelligence Stack|python3 wechat_deal_radar\.py' \
  "$repo_root" \
  --glob '!validate.sh'; then
  echo "Deprecated public naming found." >&2
  exit 1
fi

if rg -n \
  'Path\.home\(\) / "\.local" / "bin" / "wechat-cli"|调用 r266-tech/wechat-cli' \
  "$repo_root/projects/wechat-intelligence-hub"; then
  echo "The Hub must not silently select or advertise the retired generic CLI." >&2
  exit 1
fi

codex_skill_install_test="$(mktemp -d)"
trap 'rm -rf -- "$codex_skill_install_test"' EXIT
CODEX_HOME="$codex_skill_install_test" \
  "$repo_root/scripts/install.sh"
test -f "$codex_skill_install_test/skills/wechat-cli/SKILL.md"
test -f "$codex_skill_install_test/skills/wechat-cli/references/experimental-access.md"
test -f "$codex_skill_install_test/skills/wechat-intelligence-hub/SKILL.md"
test -f "$codex_skill_install_test/share/wechat-intelligence-hub/projects/rion-wechat-reader/rion_wechat_reader.py"
test -f "$codex_skill_install_test/share/wechat-intelligence-hub/projects/wechat-intelligence-hub/wechat_intelligence_hub.py"
PATH="/usr/bin:/bin" CODEX_HOME="$codex_skill_install_test" \
  "$codex_skill_install_test/skills/wechat-cli/scripts/reader.sh" self-test >/dev/null
PATH="/usr/bin:/bin" CODEX_HOME="$codex_skill_install_test" \
  "$codex_skill_install_test/skills/wechat-cli/scripts/access.sh" --help >/dev/null
HOME="$codex_skill_install_test/home" PATH="/usr/bin:/bin" CODEX_HOME="$codex_skill_install_test" \
  "$codex_skill_install_test/skills/wechat-intelligence-hub/scripts/hub.sh" --help >/dev/null
rm -rf -- "$codex_skill_install_test"
trap - EXIT

if [ -n "${RION_WECHAT_SQLCIPHER_WHEEL:-}" ]; then
  "$repo_root/projects/rion-wechat-reader/scripts/validate_sqlcipher.sh"

  codex_install_test="$(mktemp -d)"
  trap 'rm -r -- "$codex_install_test"' EXIT
  CODEX_HOME="$codex_install_test" \
    RION_WECHAT_SQLCIPHER_WHEEL="$RION_WECHAT_SQLCIPHER_WHEEL" \
    "$repo_root/scripts/install.sh" --with-sqlcipher wechat-cli
  PATH="/usr/bin:/bin" CODEX_HOME="$codex_install_test" \
    "$codex_install_test/skills/wechat-cli/scripts/reader.sh" self-test --require-sqlcipher >/dev/null
  rm -r -- "$codex_install_test"
  trap - EXIT
fi

if rg -n \
  'wxid_[A-Za-z0-9_-]{8,}|[A-Za-z0-9_-]{8,}@chatroom|/Users/rion|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY' \
  "$repo_root" \
  --glob '!release-manifest.json' \
  --glob '!build_release.py' \
  --glob '!validate.sh' \
  --glob '!test_compatibility.py'; then
  echo "Private marker scan failed." >&2
  exit 1
fi

echo "All release checks passed."
