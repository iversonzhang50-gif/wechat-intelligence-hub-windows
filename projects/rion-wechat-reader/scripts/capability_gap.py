#!/usr/bin/env python3
"""Compare rion-wechat-cli's public tools with the 1.6.19 baseline.

This script reads tool metadata only. It never queries contacts or messages.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


OLD_BASELINE = {
    "read_os",
    "sessions",
    "resolve_chat",
    "contacts",
    "messages",
    "chat_timeline",
    "message_context",
    "read_events",
    "media_resources",
    "group_members",
    "sns",
    "sns_feed",
    "sns_search",
    "sns_notifications",
    "search",
    "search_with_context",
    "sql",
    "transfers",
    "red_packets",
    "favorites",
    "chatroom_announcements",
    "forward_history",
    "schema",
    "cache_status",
    "cache_refresh",
    "cache_rebuild",
    "unread",
    "stats",
    "export_messages",
}

NEW_TO_OLD = {
    "sessions": "sessions",
    "contacts": "contacts",
    "resolve_chat": "resolve_chat",
    "history": "messages",
    "timeline": "chat_timeline",
    "context": "message_context",
    "tail": "read_events",
    "members": "group_members",
    "search": "search",
    "search_context": "search_with_context",
    "schema": "schema",
    "unread": "unread",
    "stats": "stats",
    "agent": "read_os",
    "cache_status": "cache_status",
    "cache_refresh": "cache_refresh",
    "cache_rebuild": "cache_rebuild",
    "export": "export_messages",
    "announcements": "chatroom_announcements",
    "sql": "sql",
    "media": "media_resources",
    "transfers": "transfers",
    "red_packets": "red_packets",
    "forward_history": "forward_history",
    "favorites": "favorites",
    "sns_feed": ("sns", "sns_feed"),
    "sns_search": "sns_search",
    "sns_notifications": "sns_notifications",
}


def command_for(path: str) -> list[str]:
    candidate = Path(path)
    return [sys.executable, str(candidate)] if candidate.suffix == ".py" else [path]


def load_tools(path: str) -> list[dict[str, object]]:
    result = subprocess.run(
        [*command_for(path), "tools", "--profile", "all"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    payload = json.loads(result.stdout)
    return list(payload["data"]["tools"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--new", default=str(Path(__file__).resolve().parents[1] / "rion_wechat_reader.py"))
    parser.add_argument("--old", help="Optional old CLI path for live input-schema comparison")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    try:
        new_tools = load_tools(args.new)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    new_names = {str(item["name"]) for item in new_tools}
    implemented: set[str] = set()
    for name in new_names:
        mapped = NEW_TO_OLD.get(name)
        if isinstance(mapped, tuple):
            implemented.update(mapped)
        elif mapped:
            implemented.add(mapped)
    missing = sorted(OLD_BASELINE - implemented)
    report = {
        "baseline": "wechat-cli 1.6.19",
        "baseline_tool_count": len(OLD_BASELINE),
        "implemented_equivalent_count": len(implemented),
        "implemented": sorted(implemented),
        "missing": missing,
        "known_partial": [
            "runtime parity passed on one authorized current-WeChat dataset; other WeChat versions still require validation",
            "current macOS image, video, and file HardLink layouts passed locally; other WeChat versions still need samples",
            "macOS notification previews are intentionally incomplete and are not full message history",
        ],
    }
    contract_missing: dict[str, list[str]] = {}
    if args.old:
        try:
            old_tools = load_tools(args.old)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        new_properties: dict[str, set[str]] = {}
        for item in new_tools:
            mapped = NEW_TO_OLD.get(str(item["name"]))
            old_names = mapped if isinstance(mapped, tuple) else (mapped,) if mapped else ()
            properties = set(dict(dict(item.get("inputSchema") or {}).get("properties") or {}).keys())
            for old_name in old_names:
                new_properties[str(old_name)] = properties
        old_property_count = 0
        covered_property_count = 0
        for item in old_tools:
            old_name = str(item["name"])
            old_properties = set(dict(dict(item.get("inputSchema") or {}).get("properties") or {}).keys())
            old_property_count += len(old_properties)
            covered_property_count += len(old_properties & new_properties.get(old_name, set()))
            difference = sorted(old_properties - new_properties.get(old_name, set()))
            if difference:
                contract_missing[old_name] = difference
        report["property_contract"] = {
            "covered": covered_property_count,
            "baseline": old_property_count,
            "missing_by_tool": contract_missing,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.strict and (missing or contract_missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
