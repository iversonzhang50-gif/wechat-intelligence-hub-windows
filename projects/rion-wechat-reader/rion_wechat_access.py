#!/usr/bin/env python3
"""Optional, explicit onboarding. Not part of the read-only reader contract."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import signal
import stat
import subprocess
import sys
import tempfile

import rion_wechat_reader as reader


class AccessError(Exception):
    pass


def private_path(path: Path) -> Path:
    path = path.expanduser().absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise AccessError("symlink_path_rejected")
    return path


def provider_digest(path: Path) -> str:
    path = private_path(path)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise AccessError("provider_unavailable")
    if path.stat().st_mode & 0o022:
        raise AccessError("provider_writable_by_others")
    with path.open("rb") as handle:
        digest = hashlib.sha256()
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_root(root: Path) -> Path:
    root = private_path(root)
    if not root.is_dir():
        raise AccessError("database_root_missing")
    accounts = [p for p in root.glob("*/db_storage") if p.is_dir()]
    if (root / "db_storage").is_dir():
        accounts.append(root / "db_storage")
    if len(accounts) > 1:
        raise AccessError("account_selection_required")
    return root


def inspect(provider: Path, expected: str, root: Path) -> dict:
    digest = provider_digest(provider)
    check_root(root)
    return {
        "state": "review_required",
        "experimental": True,
        "system": platform.system(),
        "provider_sha256": digest,
        "digest_matches": bool(expected) and digest == expected.lower(),
        "provider_executed": False,
        "password_route": "macOS administrator authorization; no password passed to this tool",
        "source_review_required": "Verify this exact build skips Keychain when root and honors WXKEY_NO_ELEVATE.",
        "effects_requiring_confirmation": ["process_debug_access", "quit_and_restart_wechat", "resign_shadow_copy"],
        "not_guaranteed": ["new_machine_compatibility", "automatic_gui_cleanup_after_timeout", "zero_account_risk"],
    }


def bounded_provider(argv: list[str], env: dict[str, str], timeout: int) -> str:
    """Suppress provider output; stop its process group, never an arbitrary PID."""
    process = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True)
    try:
        code = process.wait(timeout=timeout)
        return "provider_finished" if code == 0 else "provider_failed"
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        return "provider_timeout_cleanup_required"


def worker(args: argparse.Namespace) -> int:
    # This path is launched only through macOS's authorization prompt. No
    # password is requested, read from Keychain, or supplied to sudo by us.
    import pwd
    if os.geteuid() != 0 or args.uid <= 0:
        raise AccessError("administrator_worker_required")
    owner = pwd.getpwuid(args.uid)
    home = private_path(Path(owner.pw_dir))
    run_dir = private_path(args.run_dir)
    expected_parent = home / ".config" / "rion-wechat-reader" / "access-runs"
    if run_dir.parent != expected_parent or run_dir.stat().st_uid != args.uid or stat.S_IMODE(run_dir.stat().st_mode) != 0o700:
        raise AccessError("invalid_worker_directory")
    if provider_digest(args.provider) != args.sha256.lower():
        raise AccessError("provider_digest_mismatch")
    source = private_path(home / ".config" / "wxcli" / "config.json")
    if source.exists():
        raise AccessError("provider_config_exists_use_connect")
    root = check_root(args.database_root)
    # The reviewed provider can quit WeChat globally. Refuse shared-user runs.
    processes = subprocess.run(["/bin/ps", "-axo", "uid=,comm="], capture_output=True, text=True, check=True).stdout
    for line in processes.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) == 2 and Path(fields[1]).name == "WeChat" and int(fields[0]) != args.uid:
            raise AccessError("other_user_wechat_running")
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(home), "USER": owner.pw_name,
        "WXKEY_ORIG_HOME": str(home), "WXKEY_ORIG_USER": owner.pw_name,
        "WXKEY_NO_ELEVATE": "1", "WXKEY_ELEVATED": "1",
        "WXKEY_SETUP_TIMEOUT": "180s", "WXKEY_PBKDF_PROBE_TIMEOUT": "180s",
    }
    state = bounded_provider([str(args.provider), "bootstrap", "--root", str(root)], env, args.timeout)
    # Exclusive creation avoids replacing any existing recovery result.
    fd = os.open(str(run_dir / "worker-result.json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"state": state}, handle)
    os.chown(run_dir / "worker-result.json", args.uid, owner.pw_gid)
    return 0 if state == "provider_finished" else 1


def connect(source: Path | None, root: Path, config: Path, max_files: int = 500) -> dict:
    """Verify in a fresh private generation, then publish one config atomically."""
    if os.environ.get("RION_WECHAT_READER_KEYS"):
        raise AccessError("key_environment_override_requires_removal")
    source = private_path(source) if source is not None else None
    root, config = check_root(root), private_path(config)
    if config.exists():
        raise AccessError("reader_config_exists_not_overwritten")
    config.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(config.parent.stat().st_mode) & 0o077:
        raise AccessError("config_directory_not_private")
    run_dir = Path(tempfile.mkdtemp(prefix="verified-access-", dir=config.parent))
    keys = run_dir / "keys.json"
    staged_config = run_dir / "config.json"
    published = False
    try:
        verified = 0
        if source is not None:
            imported = reader.import_access_bundle(source, root, keys, force=False, verify=True, max_files=max_files)
            verified = imported["verification"]["matched_database_count"]
        else:
            reader.secure_write_json(keys, {"keys": {}}, force=False)
        plan = reader.access_plan(staged_config, root, keys, max_files)
        if plan["state"] != "ready_to_configure":
            return {"state": plan["state"], "configured": False, "counts": plan["counts"]}
        setup = reader.setup_cli(staged_config, root, keys, "", max_files, False)
        if setup["doctor"]["summary"] != "ready":
            raise AccessError("reader_verification_failed")
        # A hard link is an atomic no-replace publication on the same volume.
        os.link(staged_config, config)
        published = True
        staged_config.unlink()
        return {"state": "ready", "configured": True,
                "verified_database_count": verified,
                "live_database_read_ok": True,
                "scope": "local_databases_only", "next_step": "抽检所需私聊、群聊、标签和时间范围。"}
    finally:
        if not published:
            for path in (staged_config, keys):
                with contextlib.suppress(FileNotFoundError):
                    path.unlink()
            with contextlib.suppress(OSError):
                run_dir.rmdir()


def run(args: argparse.Namespace) -> dict:
    if platform.system() != "Darwin":
        raise AccessError("acquisition_platform_not_supported")
    if os.geteuid() == 0:
        raise AccessError("launch_from_normal_user_session")
    if not args.confirm_reviewed_provider or not args.confirm_side_effects:
        raise AccessError("explicit_confirmation_required")
    if os.environ.get("RION_WECHAT_READER_KEYS"):
        raise AccessError("key_environment_override_requires_removal")
    if not args.sha256 or provider_digest(args.provider) != args.sha256.lower():
        raise AccessError("provider_digest_mismatch")
    root, config = check_root(args.database_root), private_path(args.config)
    source = private_path(Path.home() / ".config" / "wxcli" / "config.json")
    if config.exists():
        raise AccessError("reader_config_exists_not_overwritten")
    if source.exists():
        raise AccessError("provider_config_exists_use_connect")
    if reader.sqlcipher_driver()[0] is None:
        raise AccessError("sqlcipher_driver_required")
    # mkdir(parents=True) does not apply mode to intermediate directories.
    # Prepare both private roots before authorization or acquisition begins.
    config.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(config.parent.stat().st_mode) & 0o077:
        raise AccessError("config_directory_not_private")
    state_root = private_path(Path.home() / ".config" / "rion-wechat-reader")
    state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(state_root.stat().st_mode) & 0o077:
        raise AccessError("run_directory_not_private")
    parent = private_path(state_root / "access-runs")
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(parent.stat().st_mode) & 0o077:
        raise AccessError("run_directory_not_private")
    lock = parent / "recovery-required.lock"
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise AccessError("previous_run_requires_review")
    os.close(fd)
    run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=parent))
    argv = [sys.executable, str(Path(__file__).resolve()), "_worker", "--provider", str(args.provider.absolute()),
            "--sha256", args.sha256, "--database-root", str(root), "--run-dir", str(run_dir),
            "--uid", str(os.getuid()), "--timeout", str(args.timeout)]
    command = "exec " + shlex.join(argv) + " >/dev/null 2>&1"
    script = "do shell script " + json.dumps(command, ensure_ascii=False) + " with administrator privileges"
    try:
        authorization = subprocess.run(["/usr/bin/osascript", "-e", script], stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       timeout=args.timeout + 180, check=False,
                                       env={"HOME": str(Path.home()), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"})
        result_file = run_dir / "worker-result.json"
        if not result_file.is_file():
            raise AccessError("authorization_or_worker_failed_review_required")
        state = json.loads(result_file.read_text(encoding="utf-8"))["state"]
        if state not in {"provider_finished", "provider_failed", "provider_timeout_cleanup_required"}:
            raise AccessError("worker_result_invalid")
        if authorization.returncode != 0 or state != "provider_finished":
            raise AccessError(state)
        if not source.is_file() or source.stat().st_uid != os.getuid():
            raise AccessError("provider_material_owner_invalid")
        result = connect(source, root, config, args.max_files)
        if result["state"] == "ready":
            lock.unlink()
        else:
            result["recovery_review_required"] = True
        return result
    except subprocess.TimeoutExpired:
        # An authorized child may still be cleaning up. Never silently retry.
        raise AccessError("authorization_timeout_review_required")


def onboard(args: argparse.Namespace) -> dict:
    """Idempotent workflow: inspect, reuse, connect, or request acquisition consent."""
    config = private_path(args.config)
    source = private_path(args.source) if args.source else None
    root = private_path(args.database_root) if args.database_root else None
    limit = max(1, args.max_files)
    plan = reader.access_plan(config, root, source, limit)
    outcome = {
        "workflow": "local_wechat_onboarding", "state": plan["state"],
        "live_database_read_ok": plan["live_database_read_ok"],
        "scope": plan["scope"], "counts": plan["counts"],
        "performed": dict(plan["performed"]), "next_actions": plan["next_actions"],
    }
    if plan["state"] == "ready":
        outcome["reused_existing_configuration"] = True
        return outcome
    if config.exists():
        outcome.update(state="existing_configuration_requires_review", diagnostic_state=plan["state"],
                       next_actions=["先修复或显式选择另一份配置；不会覆盖已有配置，也不会因读失败自动重新取key。"])
        return outcome
    if plan["state"] not in {"ready_to_configure", "needs_access"}:
        return outcome
    if os.environ.get("RION_WECHAT_READER_KEYS"):
        raise AccessError("key_environment_override_requires_removal")

    # Only read the caller's material or the Reader's own default, not another
    # application's private config. access_plan already checked its permissions.
    selected_keys = source or private_path(Path("~/.config/rion-wechat-reader/keys.json"))
    material = reader.load_json(selected_keys)
    if root is None:
        bundled = material.get("database_root") or material.get("db_root")
        root = Path(str(bundled)).expanduser() if bundled else reader.default_wechat_root()
    if root is None:
        outcome.update(state="needs_database_location", next_actions=["确认本人账号和数据库目录后继续。"])
        return outcome
    root = check_root(root)

    if plan["state"] == "ready_to_configure":
        if not args.apply:
            outcome["next_actions"] = ["已验证输入；加--apply继续导入和配置，不需要获取新key。"]
            return outcome
        result = connect(selected_keys if selected_keys.is_file() else None, root, config, limit)
        outcome.update(result)
        outcome["performed"]["configuration_write"] = result.get("configured", False)
        return outcome

    if source is not None:
        outcome.update(state="access_material_requires_review", next_actions=["指定材料尚不能读取数据库，先检查该文件和账号，不自动改走获取路线。"])
        return outcome
    if platform.system() != "Darwin":
        outcome.update(state="acquisition_platform_not_supported", next_actions=["此助手尚未实现本系统获取；可以验证用户已有的授权材料。"])
        return outcome
    if reader.sqlcipher_driver()[0] is None:
        outcome.update(state="dependency_required", next_actions=["先为当前CLI运行环境安装SQLCipher，再继续。"])
        return outcome
    if args.provider is None:
        outcome.update(state="provider_required", next_actions=["由Codex按接入指引核验并准备固定版本的本地获取工具，无需用户手工找key。"])
        return outcome
    inspection = inspect(args.provider, args.sha256, root)
    outcome["provider_review"] = inspection
    if not inspection["digest_matches"]:
        outcome.update(state="provider_review_required", next_actions=["核验源码和具体构建，再传入已审核的SHA256；不要自动接受现场计算出的哈希。"])
        return outcome
    if not args.apply or not args.confirm_reviewed_provider or not args.confirm_side_effects:
        outcome.update(state="authorization_required", next_actions=["向用户确认进程访问、微信退出/重启和副本重签名；确认后才继续，密码只在系统授权窗口输入。"])
        return outcome
    args.database_root = root
    args.config = config
    result = run(args)
    outcome.update(result)
    outcome["performed"].update(key_acquisition=True, provider_execution=True,
                                configuration_write=result.get("configured", False))
    return outcome


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Optional local access onboarding; acquisition is experimental and opt-in.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "run", "_worker"):
        p = sub.add_parser(name)
        p.add_argument("--provider", required=True, type=Path)
        p.add_argument("--sha256", default="")
        p.add_argument("--database-root", required=True, type=Path)
        if name != "plan":
            p.add_argument("--timeout", type=int, choices=range(30, 901), default=600, metavar="30..900")
        if name == "run":
            p.add_argument("--confirm-reviewed-provider", action="store_true")
            p.add_argument("--confirm-side-effects", action="store_true")
            p.add_argument("--config", type=Path, default=reader.DEFAULT_CONFIG)
            p.add_argument("--max-files", type=int, default=500)
        if name == "_worker":
            p.add_argument("--uid", type=int, required=True)
            p.add_argument("--run-dir", type=Path, required=True)
    p = sub.add_parser("connect")
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--database-root", required=True, type=Path)
    p.add_argument("--config", type=Path, default=reader.DEFAULT_CONFIG)
    p.add_argument("--max-files", type=int, default=500)
    p = sub.add_parser("onboard", help="Guided first-access workflow; defaults to inspection only")
    p.add_argument("--config", type=Path, default=Path(os.environ.get("RION_WECHAT_READER_CONFIG", str(reader.DEFAULT_CONFIG))))
    p.add_argument("--database-root", type=Path)
    p.add_argument("--source", type=Path)
    p.add_argument("--provider", type=Path)
    p.add_argument("--sha256", default="")
    p.add_argument("--apply", action="store_true", help="Allow verified configuration; acquisition still needs both confirmations")
    p.add_argument("--confirm-reviewed-provider", action="store_true")
    p.add_argument("--confirm-side-effects", action="store_true")
    p.add_argument("--max-files", type=int, default=500)
    p.add_argument("--timeout", type=int, choices=range(30, 901), default=600, metavar="30..900")
    args = parser.parse_args(argv)
    try:
        if args.command == "_worker":
            return worker(args)
        if args.command == "plan":
            result = inspect(args.provider, args.sha256, args.database_root)
        elif args.command == "onboard":
            result = onboard(args)
        elif args.command == "connect":
            result = connect(args.source, args.database_root, args.config, max(1, args.max_files))
        else:
            result = run(args)
        print(json.dumps({"ok": True, "data": result}, ensure_ascii=False, indent=2))
        return 0 if args.command == "plan" or result["state"] == "ready" else 1
    except (AccessError, reader.ReaderError, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        # Never forward provider or SQLCipher exception strings to the agent.
        exc = sys.exc_info()[1]
        code = str(exc) if isinstance(exc, AccessError) else "access_validation_failed"
        print(json.dumps({"ok": False, "error": {"code": code,
            "message": "操作未完成；未覆盖已有reader配置。不要循环重试或上传访问材料。"}}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
