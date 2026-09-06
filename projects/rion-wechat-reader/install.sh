#!/usr/bin/env bash
set -euo pipefail

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
prefix="${RION_WECHAT_CLI_PREFIX:-${RION_WECHAT_READER_PREFIX:-$HOME/.local}}"
force=0
with_sqlcipher=0
sqlcipher_version="${RION_WECHAT_SQLCIPHER_VERSION:-0.6.2}"
sqlcipher_wheel=""
zstandard_version="${RION_WECHAT_ZSTANDARD_VERSION:-0.25.0}"
zstandard_wheel="${RION_WECHAT_ZSTANDARD_WHEEL:-}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix)
      [ "$#" -ge 2 ] || { echo "--prefix 需要一个目录" >&2; exit 2; }
      prefix="$2"
      shift 2
      ;;
    --force)
      force=1
      shift
      ;;
    --with-sqlcipher)
      with_sqlcipher=1
      shift
      ;;
    --sqlcipher-wheel)
      [ "$#" -ge 2 ] || { echo "--sqlcipher-wheel 需要一个 wheel 文件" >&2; exit 2; }
      with_sqlcipher=1
      sqlcipher_wheel="$2"
      shift 2
      ;;
    --zstandard-wheel)
      [ "$#" -ge 2 ] || { echo "--zstandard-wheel 需要一个 wheel 文件" >&2; exit 2; }
      zstandard_wheel="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: ./install.sh [--prefix DIR] [--force] [--with-sqlcipher] [--sqlcipher-wheel FILE] [--zstandard-wheel FILE]"
      exit 0
      ;;
    *)
      echo "未知参数：$1" >&2
      exit 2
      ;;
  esac
done

target_dir="$prefix/bin"
target="$target_dir/rion-wechat-cli"
compat_target="$target_dir/rion-wechat-reader"
access_target="$target_dir/rion-wechat-access"
runtime_dir="$prefix/share/rion-wechat-cli"
engine="$runtime_dir/rion_wechat_reader.py"
if [ "$force" -ne 1 ]; then
  for candidate in "$target" "$compat_target" "$access_target"; do
    if [ -e "$candidate" ]; then
      echo "目标已存在，未覆盖：${candidate}（确认升级时使用 --force）" >&2
      exit 3
    fi
  done
fi

mkdir -p "$target_dir"
mkdir -p "$runtime_dir"
install -m 0755 "$source_dir/rion_wechat_reader.py" "$engine"
install -m 0755 "$source_dir/rion_wechat_access.py" "$runtime_dir/rion_wechat_access.py"
install -m 0755 "$source_dir/launcher.sh" "$target"
install -m 0755 "$source_dir/launcher.sh" "$compat_target"
install -m 0755 "$source_dir/launcher.sh" "$access_target"

if [ "$with_sqlcipher" -eq 1 ]; then
  python3 -m venv "$runtime_dir/venv"
  if ! "$runtime_dir/venv/bin/python" -c 'from sqlcipher3 import dbapi2' >/dev/null 2>&1; then
    package="sqlcipher3==$sqlcipher_version"
    if [ -n "$sqlcipher_wheel" ]; then
      [ -f "$sqlcipher_wheel" ] || { echo "SQLCipher wheel 不存在：$sqlcipher_wheel" >&2; exit 4; }
      package="$sqlcipher_wheel"
    fi
    if ! "$runtime_dir/venv/bin/python" -m pip install \
      --disable-pip-version-check \
      --no-input \
      --timeout 60 \
      --retries 2 \
      "$package"; then
      echo "SQLCipher 安装失败。网络较慢时可先下载匹配平台的 wheel，再使用 --sqlcipher-wheel FILE。" >&2
      exit 5
    fi
  fi
  if ! "$runtime_dir/venv/bin/python" -c 'import zstandard' >/dev/null 2>&1; then
    zstandard_package="zstandard==$zstandard_version"
    if [ -n "$zstandard_wheel" ]; then
      [ -f "$zstandard_wheel" ] || { echo "zstandard wheel 不存在：$zstandard_wheel" >&2; exit 4; }
      zstandard_package="$zstandard_wheel"
    fi
    if ! "$runtime_dir/venv/bin/python" -m pip install \
      --disable-pip-version-check \
      --no-input \
      --timeout 60 \
      --retries 2 \
      "$zstandard_package"; then
      echo "zstandard 安装失败。可先下载匹配平台的 wheel，再使用 --zstandard-wheel FILE。" >&2
      exit 5
    fi
  fi
  "$runtime_dir/venv/bin/python" -c \
    'from sqlcipher3 import dbapi2 as db; c=db.connect(":memory:"); print("SQLCipher:", c.execute("PRAGMA cipher_version").fetchone()[0]); c.close()'
  "$runtime_dir/venv/bin/python" -c 'import zstandard; print("zstandard:", zstandard.__version__)'
fi

echo "Installed: $target"
echo "Compatibility alias: $compat_target"
echo "Optional experimental access helper: $access_target (not executed by installation)"
if [ "$with_sqlcipher" -eq 1 ]; then
  echo "SQLCipher runtime: $runtime_dir/venv"
fi
echo "Next: $target self-test; then $target access-plan --pretty"
echo "Setup configures supplied inputs; it does not acquire keys. Follow the access-plan state."
echo "Guided first access: ask Codex to follow the wechat-cli Skill's access.sh onboard workflow."
