#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
codex_root="${CODEX_HOME:-$HOME/.codex}"
skill_root="$codex_root/skills"
wechat_hub_source="$repo_root/projects/wechat-intelligence-hub"
wechat_hub_target="$codex_root/share/wechat-intelligence-hub/projects/wechat-intelligence-hub"
wechat_reader_source="$repo_root/projects/rion-wechat-reader"
wechat_reader_target="$codex_root/share/wechat-intelligence-hub/projects/rion-wechat-reader"
with_sqlcipher=0
skill_names=()

for argument in "$@"; do
  case "$argument" in
    --with-sqlcipher)
      with_sqlcipher=1
      ;;
    -h|--help)
      echo "Usage: ./scripts/install.sh [--with-sqlcipher] [wechat-cli] [wechat-intelligence-hub]"
      echo "With no skill names, the complete WeChat Intelligence Hub is installed."
      exit 0
      ;;
    --*)
      echo "Unknown option: $argument" >&2
      exit 2
      ;;
    *)
      skill_names+=("$argument")
      ;;
  esac
done

if [ "${#skill_names[@]}" -eq 0 ]; then
  skill_names=(wechat-cli wechat-intelligence-hub)
fi

# The intelligence Skill depends on the read-only CLI. Keep the dependency
# automatic so users install one product instead of assembling components.
has_hub=0
has_cli=0
for skill_name in "${skill_names[@]}"; do
  [ "$skill_name" = "wechat-intelligence-hub" ] && has_hub=1
  [ "$skill_name" = "wechat-cli" ] && has_cli=1
done
if [ "$has_hub" -eq 1 ] && [ "$has_cli" -eq 0 ]; then
  skill_names=(wechat-cli "${skill_names[@]}")
fi

# Deduplicate names while preserving order.
# Bash 3.2 with `set -u` treats an empty array expansion as unbound, so keep a
# sentinel until argument construction is complete.
resolved_skills=("__rion_sentinel__")
for skill_name in "${skill_names[@]}"; do
  already_added=0
  for existing in "${resolved_skills[@]}"; do
    [ "$existing" = "$skill_name" ] && already_added=1
  done
  [ "$already_added" -eq 0 ] && resolved_skills+=("$skill_name")
done

set -- "${resolved_skills[@]}"
shift

mkdir -p "$skill_root"

# Preflight every target before copying anything, so a conflict cannot leave a
# partially installed set of skills behind.
for skill_name in "$@"; do
  source_dir="$repo_root/skills/$skill_name"
  target_dir="$skill_root/$skill_name"
  if [ ! -f "$source_dir/SKILL.md" ]; then
    echo "Unknown skill: $skill_name" >&2
    exit 2
  fi
  if [ -e "$target_dir" ]; then
    echo "Already exists, not overwritten: $target_dir" >&2
    exit 3
  fi
  if [ "$skill_name" = "wechat-intelligence-hub" ] && [ -e "$wechat_hub_target" ]; then
    echo "Already exists, not overwritten: $wechat_hub_target" >&2
    exit 3
  fi
  if [ "$skill_name" = "wechat-cli" ] && [ -e "$wechat_reader_target" ]; then
    echo "Already exists, not overwritten: $wechat_reader_target" >&2
    exit 3
  fi
  if [ "$skill_name" = "wechat-cli" ] && [ "$with_sqlcipher" -eq 1 ]; then
    for entry in rion-wechat-cli rion-wechat-reader rion-wechat-access; do
      if [ -e "$codex_root/bin/$entry" ]; then
        echo "Already exists, not overwritten: $codex_root/bin/$entry" >&2
        exit 3
      fi
    done
  fi
done

installed_wechat_hub=0
installed_wechat_reader=0

for skill_name in "$@"; do
  source_dir="$repo_root/skills/$skill_name"
  target_dir="$skill_root/$skill_name"
  cp -R "$source_dir" "$target_dir"
  echo "Installed: $skill_name -> $target_dir"
  if [ "$skill_name" = "wechat-intelligence-hub" ]; then
    installed_wechat_hub=1
  fi
  if [ "$skill_name" = "wechat-cli" ]; then
    installed_wechat_reader=1
  fi
done

if [ "$installed_wechat_reader" -eq 1 ]; then
  mkdir -p "$(dirname "$wechat_reader_target")"
  cp -R "$wechat_reader_source" "$wechat_reader_target"
  echo "Installed reader core -> $wechat_reader_target"

  if [ "$with_sqlcipher" -eq 1 ]; then
    reader_install_args=(--prefix "$codex_root")
    if [ -n "${RION_WECHAT_SQLCIPHER_WHEEL:-}" ]; then
      reader_install_args+=(--sqlcipher-wheel "$RION_WECHAT_SQLCIPHER_WHEEL")
    else
      reader_install_args+=(--with-sqlcipher)
    fi
    if [ -n "${RION_WECHAT_ZSTANDARD_WHEEL:-}" ]; then
      reader_install_args+=(--zstandard-wheel "$RION_WECHAT_ZSTANDARD_WHEEL")
    fi
    "$wechat_reader_target/install.sh" "${reader_install_args[@]}"
  fi

  cat <<'EOF'

Rion WeChat CLI is installed in read-only mode.
Ask Codex to run the installed wechat-cli Skill's reader.sh self-test,
then reader.sh access-plan --pretty. Follow its state before running setup.
For guided first access, ask Codex to run access.sh onboard and follow the
five-step onboarding reference. You do not need to copy keys into the chat.
Installation does not acquire database keys. Never send keys or passwords
to Codex, maintainers, community chats, or Issues.

Without authorized database inputs, macOS notification previews may be
available as an explicitly incomplete incoming-only fallback.
EOF
fi

if [ "$installed_wechat_hub" -eq 1 ]; then
  mkdir -p "$(dirname "$wechat_hub_target")"
  python3 "$wechat_hub_source/scripts/build_release.py" \
    --root "$wechat_hub_source" \
    --out "$wechat_hub_target"
  echo "Installed engine -> $wechat_hub_target"

  cat <<'EOF'

WeChat Intelligence Hub needs a private local Profile before its daily ranking can match your work.
Next, ask Codex:
  $wechat-intelligence-hub 帮我初始化微信个人情报库。先检查个人说明、当前计划和微信标签；缺少时给我准备清单。

The installer also placed the local engine under CODEX_HOME, so no
WECHAT_HUB_HOME setting is required for normal Skill calls.
EOF
fi

echo "Restart Codex to refresh skill discovery."
