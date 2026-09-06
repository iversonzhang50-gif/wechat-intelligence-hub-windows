#!/usr/bin/env python3
"""Privacy-preserving black-box parity check for legacy and candidate readers."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REQUIRED_CAPABILITIES = ("sessions", "timeline", "search", "context", "tail", "media", "name_resolution")
NON_TIMELINE_SESSION_TYPES = {"folded"}


class ProbeFailure(RuntimeError):
    pass


def run_json(binary: str, arguments: list[str], stage: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [binary, *arguments],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeFailure(f"{stage} failed") from exc
    if result.returncode != 0:
        raise ProbeFailure(f"{stage} failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeFailure(f"{stage} returned invalid JSON") from exc
    if not isinstance(payload, dict) or payload.get("ok") is False:
        raise ProbeFailure(f"{stage} failed")
    return payload


def data(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("data")
    return value if isinstance(value, dict) else {}


def rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    def visit(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if not isinstance(value, dict):
            return []
        for key in ("messages", "sessions", "contacts", "items", "rows", "results", "data"):
            nested = value.get(key)
            found = visit(nested)
            if found or isinstance(nested, list):
                return found
        return []

    return visit(payload)


def first(row: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return None


def nested_first(row: dict[str, Any], names: tuple[str, ...]) -> Any:
    value = first(row, names)
    if value not in (None, "") and not isinstance(value, dict):
        return value
    identity = row.get("id")
    if isinstance(identity, dict):
        return first(identity, names)
    return value


def normalized_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().casefold() in {"1", "true", "yes"}


def version(binary: str, label: str) -> str:
    payload = run_json(binary, ["version"], f"{label}.version")
    return str(first(data(payload), ("version", "name")) or "unknown")


def status(binary: str, label: str) -> dict[str, Any]:
    payload = run_json(binary, ["--strict-read-only", "status"], f"{label}.status")
    value = data(payload).get("status", data(payload))
    return value if isinstance(value, dict) else {}


def list_rows(binary: str, label: str, command: str, limit: int) -> list[dict[str, Any]]:
    return rows(
        run_json(
            binary,
            ["--strict-read-only", command, "--limit", str(limit)],
            f"{label}.{command}",
        )
    )


def session_id(row: dict[str, Any]) -> str:
    return str(first(row, ("username", "talker", "chatroom_id", "session_id")) or "")


def session_type(row: dict[str, Any]) -> str:
    value = str(first(row, ("chat_type", "type")) or "unknown").lower()
    if value in {"1", "private"}:
        return "private"
    if value in {"2", "group"} or value.endswith("@chatroom"):
        return "group"
    return value


def stable_order(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def message_identity(row: dict[str, Any]) -> tuple[str, ...]:
    """Compare structural identity without retaining or hashing message text."""
    return (
        str(nested_first(row, ("local_id", "message_local_id")) or ""),
        str(nested_first(row, ("server_id", "server_id_str", "message_server_id")) or ""),
        str(first(row, ("create_time", "time", "time_iso")) or ""),
        str(first(row, ("kind", "kind_name")) or ""),
        str(normalized_bool(first(row, ("from_me", "is_from_me", "is_sender")))),
    )


def timeline(binary: str, label: str, talker: str, limit: int) -> list[dict[str, Any]]:
    return rows(
        run_json(
            binary,
            [
                "--strict-read-only",
                "timeline",
                talker,
                "--limit",
                str(limit),
                "--include-media-paths",
                "false",
            ],
            f"{label}.timeline",
        )
    )


def compare(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "privacy": "No identifiers, display names, paths, keys, or message text are emitted.",
        "legacy": {"version": version(args.legacy_bin, "legacy")},
        "candidate": {"version": version(args.candidate_bin, "candidate")},
    }
    legacy_status = status(args.legacy_bin, "legacy")
    candidate_status = status(args.candidate_bin, "candidate")
    legacy_capabilities = legacy_status.get("capabilities", {})
    candidate_capabilities = candidate_status.get("capabilities", {})
    if not isinstance(legacy_capabilities, dict):
        legacy_capabilities = {}
    if not isinstance(candidate_capabilities, dict):
        candidate_capabilities = {}
    capability_rows = {
        name: {
            "legacy": bool(legacy_capabilities.get(name)),
            "candidate": bool(candidate_capabilities.get(name)),
        }
        for name in REQUIRED_CAPABILITIES
    }
    report["capabilities"] = capability_rows

    legacy_sessions = list_rows(args.legacy_bin, "legacy", "sessions", args.session_limit)
    candidate_sessions = list_rows(args.candidate_bin, "candidate", "sessions", args.candidate_collection_limit)
    legacy_contacts = list_rows(args.legacy_bin, "legacy", "contacts", args.contact_limit)
    candidate_contacts = list_rows(args.candidate_bin, "candidate", "contacts", args.candidate_collection_limit)
    legacy_types = Counter(session_type(row) for row in legacy_sessions)
    candidate_types = Counter(session_type(row) for row in candidate_sessions)
    legacy_session_ids = {session_id(row) for row in legacy_sessions if session_id(row)}
    candidate_session_ids = {session_id(row) for row in candidate_sessions if session_id(row)}
    legacy_contact_ids = {session_id(row) for row in legacy_contacts if session_id(row)}
    candidate_contact_ids = {session_id(row) for row in candidate_contacts if session_id(row)}
    report["collections"] = {
        "sessions": {
            "legacy_count": len(legacy_sessions),
            "candidate_count": len(candidate_sessions),
            "legacy_types": dict(sorted(legacy_types.items())),
            "candidate_types": dict(sorted(candidate_types.items())),
            "legacy_coverage": legacy_session_ids <= candidate_session_ids,
            "match": legacy_session_ids <= candidate_session_ids,
        },
        "contacts": {
            "legacy_count": len(legacy_contacts),
            "candidate_count": len(candidate_contacts),
            "legacy_coverage": legacy_contact_ids <= candidate_contact_ids,
            "match": legacy_contact_ids <= candidate_contact_ids,
        },
    }

    legacy_session_rows = {session_id(row): row for row in legacy_sessions if session_id(row)}
    candidate_session_rows = {session_id(row): row for row in candidate_sessions if session_id(row)}
    readable_common_ids = {
        talker
        for talker in legacy_session_ids & candidate_session_ids
        if session_type(legacy_session_rows[talker]) not in NON_TIMELINE_SESSION_TYPES
        and session_type(candidate_session_rows[talker]) not in NON_TIMELINE_SESSION_TYPES
    }
    common_ids = sorted(readable_common_ids, key=stable_order)[: args.sample_sessions]
    timeline_checks = []
    for talker in common_ids:
        legacy_messages = timeline(args.legacy_bin, "legacy", talker, args.timeline_limit)
        candidate_messages = timeline(args.candidate_bin, "candidate", talker, args.timeline_limit)
        legacy_identities = Counter(message_identity(row) for row in legacy_messages)
        candidate_identities = Counter(message_identity(row) for row in candidate_messages)
        timeline_checks.append(
            {
                "legacy_count": len(legacy_messages),
                "candidate_count": len(candidate_messages),
                "structural_identity_match": legacy_identities == candidate_identities,
            }
        )
    report["timeline_samples"] = {
        "requested": args.sample_sessions,
        "eligible_sessions": len(readable_common_ids),
        "matched_sessions": len(common_ids),
        "checks": timeline_checks,
    }

    capability_match = all(
        row["legacy"] == row["candidate"] and row["candidate"]
        for row in capability_rows.values()
    )
    collections_match = all(row["match"] for row in report["collections"].values())
    timelines_match = (
        bool(common_ids)
        and len(common_ids) == min(args.sample_sessions, len(readable_common_ids))
        and all(row["structural_identity_match"] for row in timeline_checks)
    )
    ready = capability_match and collections_match and timelines_match
    report["result"] = "ready" if ready else "mismatch"
    return report, ready


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare legacy and candidate WeChat readers without exposing content")
    parser.add_argument("--legacy-bin", default="wechat-cli")
    parser.add_argument("--candidate-bin", default="rion-wechat-cli")
    parser.add_argument("--session-limit", type=int, default=20)
    parser.add_argument("--contact-limit", type=int, default=50)
    parser.add_argument("--candidate-collection-limit", type=int, default=100000)
    parser.add_argument("--sample-sessions", type=int, default=3)
    parser.add_argument("--timeline-limit", type=int, default=20)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when parity is not ready")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report, ready = compare(args)
    except ProbeFailure as exc:
        report = {
            "schema_version": 1,
            "result": "blocked",
            "privacy": "No identifiers, display names, paths, keys, or message text are emitted.",
            "error": str(exc),
        }
        ready = False
    print(json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None))
    return 1 if args.strict and not ready else 0


if __name__ == "__main__":
    sys.exit(main())
